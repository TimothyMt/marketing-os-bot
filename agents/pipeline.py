"""
Pipeline Orchestration Engine.
Manages the sequential execution of all 8 agents via Claude API.
"""
import json
import re
import asyncio
import logging
from typing import AsyncGenerator, Optional

import anthropic

logger = logging.getLogger(__name__)

from config import (
    CLAUDE_SONNET_MODEL,
    CLAUDE_HAIKU_MODEL,
    ANTHROPIC_API_KEY,
    AGENT_TIMEOUT,
)


async def _auto_save_history(session) -> None:
    """Background task: save pipeline run to campaign history after COMPLETE.
    Non-fatal — any error is logged and swallowed."""
    try:
        from storage.campaign_history import save_campaign_history
        await save_campaign_history(session)
    except Exception as e:
        logger.warning("_auto_save_history failed (user=%s): %s", getattr(session, "user_id", "?"), e)
from storage.models import Session, BusinessProfile, PipelineStage
from agents.prompts import (
    INTAKE_SYSTEM,
    MARKET_RESEARCH_SYSTEM,
    COMPETITOR_SYSTEM,
    CUSTOMER_INSIGHT_SYSTEM,
    MARKETING_PSYCHOLOGY_SYSTEM,
    PRICING_STRATEGY_SYSTEM,
    SOCIAL_LISTENING_SYSTEM,
    STRATEGY_SYNTHESIZER_SYSTEM,
    PROGRESS_MESSAGES,
    get_intake_system,
)
from agents.skills import (
    AgentSkill,
    MarketResearchSkill,
    CompetitorSkill,
    CustomerInsightSkill,
    PsychologyPricingSkill,
    UspDefinitionSkill,
    SocialListeningSkill,
    StrategySynthesisSkill,
)
from agents.critic import run_critic
from agents.output_formats import get_format_instruction, get_lang_instruction
from frameworks.kpi_library import get_framework_as_text
from frameworks.save_framework import generate_save_analysis
from frameworks.smart_framework import format_smart_prompt

client = anthropic.AsyncAnthropic(
    api_key=ANTHROPIC_API_KEY,
    timeout=300.0,  # 5 min — long structured outputs need headroom (was 180s)
    max_retries=1,
)


# DEPRECATED — kept temporarily for backward-compat in legacy _run_agent function.
# New code uses get_format_instruction(skill.output_format).
OUTPUT_FORMAT_INSTRUCTION = """

---

**OUTPUT FORMAT (BẮT BUỘC) — Tuân thủ chính xác cấu trúc 4 sections sau:**

## 💡 Insight quan trọng nhất
[1-2 câu cốt lõi, đặt trong dấu ngoặc kép — điều quan trọng nhất user cần nhớ về phân tích này.]

## 🎯 Tóm tắt
- bullet 1 (key finding ngắn, max 15 từ)
- bullet 2
- bullet 3
- bullet 4 (tối đa 5 bullets, mỗi bullet 1 finding)

## 📊 Benchmarks
[2-4 dòng KPI/số liệu/threshold cụ thể. Bỏ qua section này nếu không có data số.]

## 📄 Phân tích chi tiết
[Full analysis dài, có sub-sections]

---

**NGUYÊN TẮC DỮ LIỆU (BẮT BUỘC — áp dụng cho TẤT CẢ con số/claim):**

**1. CITE NGUỒN khi có data thật trong training:**
- Dùng tên nguồn rõ ràng: "Theo Statista...", "GSO báo cáo...", "Nielsen 2024 chỉ ra..."
- CHỈ được cite nguồn từ danh sách sau:
  `Statista, GSO, Tổng cục Thống kê, WorldBank, World Bank, Nielsen, Q&Me, Decision Lab, Vietcetera, CafeF, VnEconomy, Brands Vietnam, Advertising Vietnam, iPrice, Cốc Cốc, Adsota, Kantar`
- KHÔNG bịa tên báo cáo: SAI = "Vietnam Beauty Insights 2024" — không tồn tại
- Hệ thống tự thêm hyperlink cho các nguồn trong list

**2. KHÔNG CHẮC SỐ LIỆU → dùng RANGE hoặc QUALIFIER:**
- SAI: "TAM ngành F&B = 60 nghìn tỷ VND/năm" (số chính xác không nguồn)
- ĐÚNG: "TAM ước tính ~50-80 nghìn tỷ VND/năm (industry estimate)"
- SAI: "ROAS trung bình 3.7x"
- ĐÚNG: "ROAS ngành thường rơi vào 3-5x"

**3. CLAIM VỀ BRAND CỤ THỂ — chỉ nói CHUNG, không số:**
- SAI: "Cocoon có 50,000 active customers"
- SAI: "M.O.I founded 2018 bởi Hồ Ngọc Hà, doanh thu 200 tỷ"
- ĐÚNG: "Cocoon là local clean beauty brand đã build được presence rõ rệt"
- ĐÚNG: "M.O.I là brand mass-premium do celebrity backing"
- Nếu cần con số → dùng "các brand lớn trong segment" + range

**4. ƯU TIÊN THỨ TỰ:**
- Best: Data thật + cite nguồn từ list known
- OK: Range + qualifier ("ước tính ngành", "benchmark", "industry estimate")
- Worst: Số chính xác không nguồn → CẤM TUYỆT ĐỐI

---

**NGÔN NGỮ (BẮT BUỘC):**

1. **Ưu tiên tiếng Việt tự nhiên** — viết như tư vấn cho founder VN, không dịch word-by-word

2. **Thuật ngữ marketing tiếng Anh BẮT BUỘC kèm giải thích tiếng Việt trong ngoặc lần đầu xuất hiện:**
   - "TAM (Total Addressable Market — tổng quy mô thị trường tối đa)"
   - "CAC (Customer Acquisition Cost — chi phí thu hút 1 khách hàng)"
   - "ROAS (Return On Ad Spend — tỷ lệ doanh thu trên chi phí ads)"
   - "AOV (Average Order Value — giá trị đơn hàng trung bình)"
   - "ICP (Ideal Customer Profile — chân dung khách hàng lý tưởng)"
   - "JTBD (Jobs-to-be-Done — nhiệm vụ khách hàng cần hoàn thành)"
   - "MoM (Month-over-Month — tăng trưởng so với tháng trước)"
   - "YoY (Year-over-Year — tăng trưởng so với năm trước)"
   - "MRR (Monthly Recurring Revenue — doanh thu định kỳ hàng tháng)"
   - "NPS (Net Promoter Score — chỉ số đo lường độ hài lòng)"
   - Sau khi đã giải thích lần đầu → có thể dùng viết tắt tự do

3. **SMART Goals — viết FULL ngay từ đầu:**
   - SAI: "S: Đạt 300 đơn..."
   - ĐÚNG: "**S (Specific — Cụ thể):** Đạt 300 đơn..."
   - ĐÚNG: "**M (Measurable — Đo lường được):** 300-600 đơn..."
   - ĐÚNG: "**A (Achievable — Khả thi):** ..."
   - ĐÚNG: "**R (Relevant — Liên quan đến mục tiêu):** ..."
   - ĐÚNG: "**T (Time-bound — Có thời hạn):** Trong 90 ngày..."

4. **SAVE Framework — tương tự:**
   - "**S (Solution — Giải pháp cho vấn đề):** ..."
   - "**A (Access — Cách khách hàng tiếp cận):** ..."
   - "**V (Value — Tổng giá trị nhận được):** ..."
   - "**E (Education — Giáo dục khách hàng):** ..."

5. **TRÁNH dịch literal:**
   - SAI: "khách hàng được tip" → ĐÚNG: "khách hàng được tư vấn"
   - SAI: "performance review" → ĐÚNG: "đánh giá hiệu suất"
   - SAI: "implement strategy" → ĐÚNG: "triển khai chiến lược"
   - SAI: "leverage data" → ĐÚNG: "tận dụng/khai thác dữ liệu"

---

**Quy tắc viết Phân tích chi tiết (BẮT BUỘC tuân theo):**

1. **Dùng markdown tables** cho MỌI data so sánh:
   ```
   | Brand | Position | Strength | Threat |
   |---|---|---|---|
   | A | Premium | Strong brand | HIGH |
   ```

2. **Bold cho mọi con số/KPI/%** trong text:
   - "Tăng từ **80tr** lên **200tr/tháng** (**40% MoM**)"
   - "CAC giảm xuống **< 180k**"

3. **Blockquote (>) cho key takeaway**:
   ```
   > 🎯 ThaiHa có 18-24 tháng để chiếm thị phần trước khi big players tham gia.
   ```

4. **Sub-headings `### Tên section`** cho các nhóm nội dung lớn

5. **Bullet lists với emoji prefix** cho action items:
   - 🟢 Quick wins: ...
   - 🟡 Medium term: ...
   - 🔴 Risks: ...

6. **Bold tên brand/product** khi mention lần đầu trong section

LƯU Ý:
- KHÔNG dùng triple backticks (```) trong output — Telegram render xấu
- KHÔNG dùng nested code blocks
- Tables phải có header row đầy đủ
- Mỗi bullet không quá 25 từ"""


# ─────────────────────────────────────────────────────────────────
# INTAKE AGENT — conversational, multi-turn
# ─────────────────────────────────────────────────────────────────

async def run_intake(session: Session, user_message: str) -> tuple[str, bool]:
    """
    Run one turn of the intake conversation.

    Sau Smart Intake update: route qua llm_router (INTAKE_JSON chain).
    Primary GPT-5 mini → Haiku fallback → Sonnet last resort.

    Returns (response_text, is_profile_complete).
    """
    session.add_to_history("user", user_message)

    system_prompt = get_intake_system(session.selected_task or "full")
    user_name = (session.preferences.get("user_name", "") or "").strip()
    if user_name:
        system_prompt = system_prompt + (
            f"\n\n**Tên user:** {user_name}. Khi xưng hô gọi 'sếp {user_name}' "
            f"(vd: 'Em cảm ơn sếp {user_name}'), KHÔNG chỉ gọi 'sếp'."
        )

    # Build user prompt = concatenated history (router không hỗ trợ multi-turn messages
    # đồng nhất cross-provider — flatten thành single user message).
    history_text = "\n\n".join(
        f"**{m['role'].upper()}:** {m['content']}" for m in session.intake_history
    )

    try:
        from tools.llm_router import call as router_call, TaskType, AllProvidersFailedError
        result = await router_call(
            task_type=TaskType.INTAKE_JSON,
            system=system_prompt,
            user=history_text,
            max_tokens=2048,  # GPT-5 mini cần buffer cho reasoning
        )
        assistant_text = result["output"]
        provider = result.get("provider", "unknown")

        # Token tracking (raw — router trả tokens_in/out)
        try:
            from tools.token_tracker import track_usage_raw
            track_usage_raw(
                session,
                input_tokens=result.get("tokens_in", 0),
                output_tokens=result.get("tokens_out", 0),
                label=f"intake_{provider}",
            )
        except Exception as e:
            logger.warning("Token tracking failed (intake via router): %s", e)
    except AllProvidersFailedError as e:
        # Last-resort: legacy Anthropic Haiku path
        logger.error("Intake all router providers failed, fallback Haiku direct: %s", e)
        response = await client.messages.create(
            model=CLAUDE_HAIKU_MODEL,
            max_tokens=1024,
            system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
            messages=session.intake_history.copy(),
        )
        try:
            from tools.token_tracker import track_usage
            track_usage(session, response, label="intake")
        except Exception:
            pass
        assistant_text = response.content[0].text

    session.add_to_history("assistant", assistant_text)
    profile, is_complete = _extract_profile_from_response(assistant_text)
    if is_complete and profile:
        session.profile = profile
    return assistant_text, is_complete


def _extract_profile_from_response(text: str) -> tuple[Optional[BusinessProfile], bool]:
    """Parse JSON block from AI response into BusinessProfile."""
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if not match:
        return None, False

    try:
        data = json.loads(match.group(1))
        # Sprint 2 — normalize usp_confidence (accept variations)
        raw_confidence = (data.get("usp_confidence") or "").strip().lower()
        if raw_confidence in ("clear", "draft", "missing"):
            usp_confidence = raw_confidence
        else:
            usp_confidence = None
        profile = BusinessProfile(
            industry=data.get("industry"),
            stage=data.get("stage"),
            business_name=data.get("business_name"),
            product_service=data.get("product_service"),
            target_customer=data.get("target_customer"),
            monthly_revenue=data.get("monthly_revenue"),
            team_size=data.get("team_size"),
            monthly_marketing_budget=data.get("monthly_marketing_budget"),
            primary_goal=data.get("primary_goal"),
            current_channels=data.get("current_channels"),
            main_challenge=data.get("main_challenge"),
            competitors=data.get("competitors"),
            location=data.get("location"),
            usp=data.get("usp"),                       # Sprint 2
            usp_confidence=usp_confidence,             # Sprint 2
        )
        # Smart Intake v2: HARD rule 8 fields — LLM hay exit early khi gặp
        # user trả lời ngắn gọn. Return profile (partial OK) nhưng KHÔNG
        # mark complete cho đến khi đủ 8 must-have fields.
        is_complete = profile.is_intake_complete()
        if not is_complete:
            missing = []
            for f in ("industry", "product_service", "target_customer", "location",
                     "monthly_revenue", "current_channels", "primary_goal", "main_challenge"):
                if not getattr(profile, f, None):
                    missing.append(f)
            logger.info(
                "Intake JSON found but incomplete (missing %d/8 fields): %s",
                len(missing), missing,
            )
        return profile, is_complete
    except (json.JSONDecodeError, TypeError):
        return None, False


# ─────────────────────────────────────────────────────────────────
# PIPELINE STAGES — single-shot Claude calls
# ─────────────────────────────────────────────────────────────────

async def _run_agent(
    system_prompt: str,
    user_message: str,
    context: str,
    max_tokens: int = 2048,
) -> str:
    """Legacy raw agent runner (kept for backward compat).
    Pipeline now uses _run_skill which adds Critic review."""
    augmented_system = system_prompt + OUTPUT_FORMAT_INSTRUCTION
    response = await client.messages.create(
        model=CLAUDE_SONNET_MODEL,
        max_tokens=max_tokens,
        system=[
            {
                "type": "text",
                "text": augmented_system,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": f"{context}\n\n---\n\n{user_message}",
            }
        ],
    )
    return response.content[0].text


async def _run_skill(skill: AgentSkill, session: Session) -> str:
    """Execute a skill: build context+msg → Sonnet executor → optional Critic → return.

    Uses get_format_instruction(skill.output_format) to inject correct output format
    (Strategic 4-section vs Operational Deliverable vs Operational Analysis).
    Critic call only happens when skill.enable_critic = True.
    """
    # Mở 1 job mới — mọi LLM call trong skill này (main + critic) được gom
    # chung job_seq để hiển thị token theo API.
    try:
        from tools.token_tracker import begin_job
        begin_job(session)
    except Exception:
        pass

    context = skill.build_context(session)
    user_msg = skill.build_user_msg(session)

    # Sprint 5: Inject Brand Voice nếu user đã setup — chỉ cho creative ops skills
    BV_INJECTED_SKILLS = {
        "post_write", "post_adapt", "post_batch", "post_hooks", "post_visual",
        "ads_generator", "ads_copy", "video_scripts",
        "sales_inbox_script", "email_zalo_sequence", "content_repurpose",
        "content_generator", "social_posts", "ugc_brief",
    }
    if skill.name in BV_INJECTED_SKILLS:
        try:
            from storage import get_brand_voice
            bv = await get_brand_voice(session.user_id)
            if bv and not bv.is_empty():
                bv_block = bv.to_prompt_block()
                context = f"{bv_block}\n\n---\n\n{context}"
                logger.info("[BV] Injected for skill=%s user=%d", skill.name, session.user_id)
        except Exception as e:
            logger.warning("[BV] Inject failed (non-fatal) skill=%s: %s", skill.name, e)

    # Sprint 2: Strategic skills cũng cần inject user_correction nếu đang regen
    user_correction = (session.pending_intake or {}).get("_user_correction")
    if user_correction and "USER CORRECTION" not in user_msg:
        user_msg += (
            "\n\n---\n\n"
            "**USER CORRECTION (sếp đã feedback ở lần chạy trước):**\n"
            f"{user_correction}\n\n"
            "Apply correction vào output mới."
        )

    format_instruction = get_format_instruction(skill.output_format)
    en_level = (session.preferences or {}).get("en_level", "moderate")
    lang_instruction = get_lang_instruction(en_level)

    # Inject user name directive
    user_name = ((session.preferences or {}).get("user_name", "") or "").strip()
    name_directive = (
        f"\n\n---\n\n**Tên user:** {user_name}. Khi xưng hô gọi 'sếp {user_name}' "
        f"(vd: 'Em recommend sếp {user_name}'), KHÔNG chỉ gọi 'sếp'."
    ) if user_name else ""

    augmented_system = skill.system_prompt + format_instruction + "\n\n---\n\n" + lang_instruction + name_directive

    from tools.llm_router import route, TaskType, OPS_SKILL_TASK_TYPES
    task_type = OPS_SKILL_TASK_TYPES.get(skill.name, TaskType.GENERIC_CREATIVE)

    import time as _time
    _t0 = _time.monotonic()
    full_user_content = f"{context}\n\n---\n\n{user_msg}"
    logger.info(
        "Skill %s: routing via %s (max_tokens=%d, ctx_chars=%d)",
        skill.name, task_type.value, skill.max_tokens, len(full_user_content),
    )
    try:
        result = await route(
            task_type=task_type,
            system=augmented_system,
            user=full_user_content,
            max_tokens=skill.max_tokens,
        )
    except Exception as e:
        logger.exception(
            "Skill %s: route() FAILED after %.1fs: %s",
            skill.name, _time.monotonic() - _t0, e,
        )
        raise
    logger.info(
        "Skill %s: done in %.1fs (provider=%s, out_tok=%s)",
        skill.name, _time.monotonic() - _t0,
        result.get("provider", "?"), result.get("tokens_out", "?"),
    )

    # Token tracking — per-skill với provider + latency
    try:
        from tools.token_tracker import track_skill
        track_skill(
            session,
            skill_name=skill.name,
            provider=result.get("provider", "unknown"),
            input_tok=result.get("tokens_in", 0),
            output_tok=result.get("tokens_out", 0),
            cache_read=0,
            cache_create=0,
            latency_sec=result.get("latency_sec", _time.monotonic() - _t0),
        )
    except Exception as e:
        logger.warning("Token tracking failed (%s): %s", skill.name, e)

    raw_output = result["output"]

    if skill.enable_critic:
        return await run_critic(raw_output, agent_name=skill.name, session=session)
    return raw_output


async def run_market_research(session: Session) -> str:
    result = await _run_skill(MarketResearchSkill(), session)
    session.add_result("market_research", result)
    return result


async def run_competitor_analysis(session: Session) -> str:
    result = await _run_skill(CompetitorSkill(), session)
    session.add_result("competitor", result)
    return result


async def run_customer_insight(session: Session) -> str:
    result = await _run_skill(CustomerInsightSkill(), session)
    session.add_result("customer_insight", result)
    return result


async def run_psychology_and_pricing(session: Session) -> str:
    result = await _run_skill(PsychologyPricingSkill(), session)
    session.add_result("psychology_pricing", result)
    return result


async def run_social_listening(session: Session) -> str:
    result = await _run_skill(SocialListeningSkill(), session)
    session.add_result("social_listening", result)
    return result


async def run_retention_strategy_stage(session: Session) -> str:
    """Sprint 3: Retention Strategy as Full Pipeline stage 5.

    Reuses operational `retention_strategy` skill nhưng inject FULL_PIPELINE context
    (market + competitor + customer + pricing + usp đã chạy).

    Skill này có "adaptive depth" — khi no intake fields → Tier 1 (assumption-based
    với collection guide). Trong pipeline mode đây là behavior đúng.
    """
    from agents.operational_skills_config import get_operational_skill
    from agents.skills import ContextStrategy as _CS

    skill = get_operational_skill("retention_strategy")
    # Override context strategy to FULL_PIPELINE for this run (don't break standalone)
    skill.context_strategy = _CS.FULL_PIPELINE
    if hasattr(skill, "_config"):
        skill._config.context_strategy = _CS.FULL_PIPELINE
    result = await _run_skill(skill, session)
    session.add_result("retention_strategy", result)
    return result


async def run_winback_vision_stage(session: Session) -> str:
    """Sprint 3: Winback Vision as Full Pipeline stage 6.

    Reuses operational `winback_campaign` skill — output strategic-grade
    cho Synthesis consume.
    """
    from agents.operational_skills_config import get_operational_skill
    from agents.skills import ContextStrategy as _CS

    skill = get_operational_skill("winback_campaign")
    skill.context_strategy = _CS.FULL_PIPELINE
    if hasattr(skill, "_config"):
        skill._config.context_strategy = _CS.FULL_PIPELINE
    result = await _run_skill(skill, session)
    session.add_result("winback_campaign", result)
    return result


async def run_usp_definition(session: Session) -> str:
    """Sprint 2: Conditional USP skill — chỉ chạy khi cần.

    Skip nếu usp_confidence == 'clear' (user đã có USP rõ ràng từ intake).
    Run REFINE mode nếu == 'draft'.
    Run FIND mode nếu == 'missing' hoặc None (legacy).
    """
    confidence = (session.profile.usp_confidence or "").lower()
    if confidence == "clear":
        # Skip — user đã có USP rõ. Lưu placeholder + dùng profile.usp trong Synthesis.
        skipped_msg = (
            "## USP — Skipped (đã có từ intake)\n\n"
            f"USP user đã định nghĩa: \"{session.profile.usp or 'N/A'}\"\n\n"
            "Synthesis sẽ dùng USP này trực tiếp, không cần Max tìm/refine."
        )
        session.add_result("usp_definition", skipped_msg)
        return skipped_msg

    result = await _run_skill(UspDefinitionSkill(), session)
    session.add_result("usp_definition", result)
    return result


async def run_strategy_synthesis(session: Session) -> str:
    result = await _run_skill(StrategySynthesisSkill(), session)
    session.add_result("synthesis", result)
    return result


# ─────────────────────────────────────────────────────────────────
# OPERATIONAL SKILLS — dispatched via get_operational_skill()
# ─────────────────────────────────────────────────────────────────

async def run_operational_skill(skill_name: str, session: Session) -> str:
    """Run an operational skill by name. Stores result in session with versioning.

    Pipeline skills (e.g. ContentGeneratorPipeline) are detected via run_pipeline()
    and dispatch to sub-skills instead of calling the LLM directly.
    """
    from agents.operational_skills_config import get_operational_skill
    skill = get_operational_skill(skill_name)

    if hasattr(skill, "run_pipeline"):
        result = await skill.run_pipeline(session)
        session.add_result(skill_name, result)
        return result

    result = await _run_skill(skill, session)
    session.add_result(skill_name, result)
    return result


# Phase 3: Strategic single-shot tasks runner — dùng skill class trực tiếp
# (4 strategic skills market/competitor/customer/pricing đã chuyển sang single-shot template)

# Map task name → result key trong session.results
STRATEGIC_RESULT_KEYS = {
    "market":     "market_research",
    "competitor": "competitor",
    "customer":   "customer_insight",
    "pricing":    "psychology_pricing",
    "strategy":   "synthesis",
}

# Map task name → AgentSkill class
STRATEGIC_SKILL_CLASSES = {
    "market":     MarketResearchSkill,
    "competitor": CompetitorSkill,
    "customer":   CustomerInsightSkill,
    "pricing":    PsychologyPricingSkill,
    "strategy":   StrategySynthesisSkill,
}


async def run_strategic_single_skill(task_name: str, session: Session) -> str:
    """Phase 3: Run 1 strategic skill standalone (single-shot mode).
    Different from full pipeline — only runs 1 stage, no aggregate report.
    """
    skill_class = STRATEGIC_SKILL_CLASSES.get(task_name)
    if not skill_class:
        raise ValueError(f"Unknown strategic task: {task_name}")
    result = await _run_skill(skill_class(), session)
    result_key = STRATEGIC_RESULT_KEYS[task_name]
    session.add_result(result_key, result)
    return result


# ─────────────────────────────────────────────────────────────────
# PIPELINE RUNNER — orchestrates all stages
# ─────────────────────────────────────────────────────────────────

PIPELINE_SEQUENCE = [
    (PipelineStage.MARKET_RESEARCH, run_market_research, "market_research"),
    (PipelineStage.COMPETITOR, run_competitor_analysis, "competitor"),
    (PipelineStage.CUSTOMER_INSIGHT, run_customer_insight, "customer_insight"),
    (PipelineStage.PSYCHOLOGY_PRICING, run_psychology_and_pricing, "psychology_pricing"),
    # Sprint 2 — USP Definition (conditional, skip if usp_confidence='clear')
    (PipelineStage.USP_DEFINITION, run_usp_definition, "usp_definition"),
    # Sprint 3 — Retention + Winback strategic integration (A2 decision)
    (PipelineStage.RETENTION_STRATEGY, run_retention_strategy_stage, "retention_strategy"),
    (PipelineStage.WINBACK_VISION, run_winback_vision_stage, "winback_campaign"),
    # Social Listening tạm tắt — chờ web search VN coverage tốt hơn
    # (PipelineStage.SOCIAL_LISTENING, run_social_listening, "social_listening"),
    (PipelineStage.SYNTHESIS, run_strategy_synthesis, "synthesis"),
]


async def run_full_pipeline(  # kept for backwards compatibility — use run_targeted_pipeline
    session: Session,
    progress_callback=None,
) -> AsyncGenerator[tuple[str, str], None]:
    """
    Run all pipeline stages sequentially.
    Yields (stage_name, result_text) for each stage.
    progress_callback: async fn(message: str) called before each stage.
    """
    for stage_enum, stage_fn, stage_key in PIPELINE_SEQUENCE:
        session.stage = stage_enum

        # Notify progress
        if progress_callback and stage_key in PROGRESS_MESSAGES:
            await progress_callback(PROGRESS_MESSAGES[stage_key][0])

        try:
            result = await asyncio.wait_for(
                stage_fn(session),
                timeout=AGENT_TIMEOUT,
            )
            yield stage_key, result
        except asyncio.TimeoutError:
            error_msg = f"⚠️ Bước {stage_key} mất quá nhiều thời gian. Bỏ qua và tiếp tục..."
            yield stage_key, error_msg
        except Exception as e:
            error_msg = f"⚠️ Lỗi ở bước {stage_key}: {str(e)[:200]}"
            yield stage_key, error_msg

    session.stage = PipelineStage.COMPLETE
    asyncio.ensure_future(_auto_save_history(session))  # S8: fire-and-forget


# ─────────────────────────────────────────────────────────────────
# TARGETED PIPELINE — runs only stages relevant to selected task
# ─────────────────────────────────────────────────────────────────

TASK_PIPELINE_MAP: dict[str, list] = {
    "full":       PIPELINE_SEQUENCE,
    "market":     [(PipelineStage.MARKET_RESEARCH, run_market_research, "market_research")],
    "competitor": [(PipelineStage.COMPETITOR, run_competitor_analysis, "competitor")],
    "customer":   [(PipelineStage.CUSTOMER_INSIGHT, run_customer_insight, "customer_insight")],
    "pricing":    [(PipelineStage.PSYCHOLOGY_PRICING, run_psychology_and_pricing, "psychology_pricing")],
    # "social":   [(PipelineStage.SOCIAL_LISTENING, run_social_listening, "social_listening")],  # tạm tắt
    "strategy":   [(PipelineStage.SYNTHESIS, run_strategy_synthesis, "synthesis")],
}


async def run_targeted_pipeline(
    session: Session,
    progress_callback=None,
) -> AsyncGenerator[tuple[str, str], None]:
    """
    Run only the pipeline stages relevant to session.selected_task.
    Yields (stage_name, result_text) for each stage.
    """
    task = session.selected_task or "full"
    sequence = TASK_PIPELINE_MAP.get(task, PIPELINE_SEQUENCE)

    for stage_enum, stage_fn, stage_key in sequence:
        session.stage = stage_enum

        if progress_callback and stage_key in PROGRESS_MESSAGES:
            await progress_callback(PROGRESS_MESSAGES[stage_key][0])

        try:
            result = await asyncio.wait_for(
                stage_fn(session),
                timeout=AGENT_TIMEOUT,
            )
            yield stage_key, result
        except asyncio.TimeoutError:
            yield stage_key, f"⚠️ Bước {stage_key} mất quá nhiều thời gian. Bỏ qua và tiếp tục..."
        except Exception as e:
            yield stage_key, f"⚠️ Lỗi ở bước {stage_key}: {str(e)[:200]}"

    session.stage = PipelineStage.COMPLETE
    asyncio.ensure_future(_auto_save_history(session))  # S8: fire-and-forget


# ─────────────────────────────────────────────────────────────────
# Sprint 8.5 — Multi-Agent Pipeline Adapter
# ─────────────────────────────────────────────────────────────────

# Mapping agent_name → stage_keys cho HTML report rendering
# Chain agents (T3) produces nhiều stage results trong session.results
_AGENT_TO_STAGE_KEYS: dict[str, list[str]] = {
    "market_research_agent":         ["market_research"],
    "competitor_agent":              ["competitor"],
    "customer_insight_agent":        ["customer_insight"],
    "usp_definition_agent":          ["usp_definition"],
    "psychology_pricing_agent":      ["psychology_pricing"],
    "retention_then_winback_chain":  ["retention_strategy", "winback_campaign"],
    "synthesizer_agent":             ["synthesis"],
}


async def run_multi_agent_targeted(
    session: Session,
    progress_callback=None,
) -> AsyncGenerator[tuple[str, str], None]:
    """Multi-Agent Pipeline adapter — matches handler's streaming interface.

    Wraps run_multi_agent_pipeline (returns dict) thành async generator
    yielding (stage_key, output) per stage. Streams sau MỖI TIER complete,
    không phải mỗi agent (vì agents trong tier chạy parallel, order không
    deterministic).

    Used khi USE_MULTI_AGENT_PIPELINE=True và task=full.
    Single skill tasks (market/competitor/.../strategy) vẫn dùng
    run_targeted_pipeline (existing path).
    """
    from agents.orchestrator import (
        get_strategic_pipeline_tiers,
        run_tier,
        PipelineAbortError,
    )

    tiers = get_strategic_pipeline_tiers()
    session.stage = PipelineStage.MARKET_RESEARCH  # Mark pipeline started

    for tier_idx, tier in enumerate(tiers, start=1):
        if progress_callback:
            await progress_callback(
                f"📍 *Tier {tier_idx}/{len(tiers)}: {tier.name}*"
            )

        try:
            tier_results = await run_tier(tier, session, progress_callback)
        except PipelineAbortError as e:
            logger.error(f"Multi-agent pipeline aborted at {tier.name}: {e}")
            # Yield error stage để handler hiển thị
            yield "pipeline_abort", f"⚠️ Pipeline dừng tại {tier.name}: {e}"
            session.stage = PipelineStage.COMPLETE
            return

        # Yield results theo declared agent order (preserve UI consistency)
        for agent in tier.agents:
            agent_name = agent.__name__
            result = tier_results.get(agent_name)
            if not result:
                continue

            stage_keys = _AGENT_TO_STAGE_KEYS.get(agent_name, [agent_name])
            for stage_key in stage_keys:
                if not result.success:
                    yield stage_key, f"⚠️ Bước {stage_key} fail: {result.error or 'unknown'}"
                    continue

                # Chain agents save individual results vào session.results
                if len(stage_keys) > 1:
                    output = session.get_latest_result(stage_key) or ""
                    if not output:
                        # Fallback — chain output có thể chứa cả 2 substages
                        output = result.output
                else:
                    output = result.output
                yield stage_key, output

    session.stage = PipelineStage.COMPLETE
    asyncio.ensure_future(_auto_save_history(session))  # S8: fire-and-forget
