"""
Operational skill instances — combines OperationalSkill generic + special subclasses.

Standard skills (6): instances of OperationalSkill driven by config.
Special skills (2): subclass with custom logic.
  - AdsCopySkill: tier batching (TOFU/MOFU/BOFU selection)
  - VideoScriptsSkill: 4 creator type variants
"""
from agents.operational_skill import OperationalSkill, OperationalSkillConfig
from agents.skills import (
    AgentSkill,
    OutputFormat,
    IntakePattern,
    ContextStrategy,
    PrimaryDeliverable,
)
from agents.operational_prompts import (
    CAMPAIGN_BRIEF_SYSTEM,
    CONTENT_CALENDAR_SYSTEM,
    CONTENT_GENERATOR_SYSTEM,
    VIDEO_SCRIPT_GEN_SYSTEM,
    UGC_BRIEF_SYSTEM,
    ADS_COPY_SYSTEM,
    VIDEO_SCRIPTS_SYSTEM,
    SALES_INBOX_SCRIPT_SYSTEM,
    EMAIL_ZALO_SEQUENCE_SYSTEM,
    COMPETITOR_SPY_SYSTEM,
    COMPETITOR_COMPARISON_SYSTEM,
    BRAND_VOICE_SYSTEM,
    CONTENT_REPURPOSE_SYSTEM,
    RETENTION_STRATEGY_SYSTEM,
    WINBACK_CAMPAIGN_SYSTEM,
    ADS_ANALYTICS_SYSTEM,
    ADS_OPTIMIZER_SYSTEM,
    VIRAL_VIDEO_ANALYZER_SYSTEM,
)
from agents.content_suite_prompts import (
    POST_WRITE_SYSTEM,
    POST_ADAPT_SYSTEM,
    POST_VOICE_CHECK_SYSTEM,
    POST_HOOKS_SYSTEM,
    POST_BATCH_SYSTEM,
)
from agents.task_registry import OPERATIONAL_TASKS
from storage.models import Session


# ─────────────────────────────────────────────────────────────────
# STANDARD operational skills (6) — via generic OperationalSkill
# ─────────────────────────────────────────────────────────────────

def _config_for(skill_name: str, system_prompt: str, **overrides) -> OperationalSkillConfig:
    """Helper to build config from task_registry entry."""
    task = OPERATIONAL_TASKS.get(skill_name)
    if not task:
        raise ValueError(f"Unknown ops skill: {skill_name}")

    # Default user msg template — embeds intake fields with placeholder
    default_template = _build_default_template(task)

    defaults = dict(
        name=skill_name,
        label=task.label,
        system_prompt=system_prompt,
        user_msg_template=default_template,
        intake_fields=task.intake_fields,
        max_tokens=4000,
        output_format=OutputFormat.OPERATIONAL_DELIVERABLE,
        context_strategy=ContextStrategy.PROFILE_PLUS_STRATEGY,
        primary_deliverable=PrimaryDeliverable.HTML,
        enable_critic=False,
    )
    defaults.update(overrides)
    return OperationalSkillConfig(**defaults)


def _build_default_template(task) -> str:
    """Build user message template from task intake fields."""
    parts = [f"## Yêu cầu skill: {task.label}", ""]
    parts.append("**Thông tin user cung cấp:**")
    for f in task.intake_fields:
        parts.append(f"- **{f['label']}**: {{{f['key']}}}")
    parts.append("")
    parts.append("**Context business (từ profile đã thu thập):**")
    parts.append("- Ngành: {industry}")
    parts.append("- Tên business: {business_name}")
    parts.append("- Sản phẩm/dịch vụ: {product_service}")
    parts.append("- Khách hàng: {target_customer}")
    parts.append("- Địa bàn: {location}")
    parts.append("")
    parts.append(f"Hãy {task.description.lower()} dựa trên thông tin trên.")
    return "\n".join(parts)


# Instance factories — return fresh skill instance each call
def make_campaign_brief_skill() -> OperationalSkill:
    return OperationalSkill(_config_for(
        "campaign_brief",
        CAMPAIGN_BRIEF_SYSTEM,
        max_tokens=10000,  # bumped — 10-section brief is comprehensive
        context_strategy=ContextStrategy.PROFILE_PLUS_STRATEGY,
        primary_deliverable=PrimaryDeliverable.HTML,
    ))


def make_content_calendar_skill() -> OperationalSkill:
    """Sprint 3.4: Pillar % DYNAMIC theo stage + goal + challenge."""
    return OperationalSkill(_config_for(
        "content_calendar",
        CONTENT_CALENDAR_SYSTEM,
        max_tokens=10000,
        context_strategy=ContextStrategy.PROFILE_PLUS_CAMPAIGN,
        primary_deliverable=PrimaryDeliverable.EXCEL,
    ))


def calc_dynamic_pillar_mix(profile, synthesis: str = "") -> dict:
    """Sprint 3.4: Calculate Pillar % dynamically dựa profile + synthesis.
    Returns dict {educate, trust, engage, convert} that sums to 1.0.

    Heuristics:
    - MVP/Early stage → Educate cao (new brand cần educate)
    - Growth → balanced
    - Scale → Trust + Retention cao
    - Goal "brand_awareness" → Educate + Engage
    - Goal "revenue/conversion" → Convert cao
    - Goal "retention" → Trust cao
    """
    base = {"educate": 0.30, "trust": 0.30, "engage": 0.20, "convert": 0.20}

    # Stage adjustment
    stage = (profile.stage or "").lower() if profile else ""
    if stage in ("idea", "mvp"):
        base["educate"] += 0.15
        base["convert"] -= 0.10
        base["engage"] -= 0.05
    elif stage == "scale":
        base["trust"] += 0.10
        base["educate"] -= 0.05
        base["convert"] -= 0.05

    # Goal adjustment
    goal = (profile.primary_goal or "").lower() if profile else ""
    synthesis_lower = (synthesis or "").lower()

    if any(k in goal + synthesis_lower for k in ["awareness", "brand", "nhận diện"]):
        base["educate"] += 0.10
        base["engage"] += 0.05
        base["convert"] -= 0.15
    elif any(k in goal + synthesis_lower for k in ["revenue", "doanh thu", "conversion", "chốt"]):
        base["convert"] += 0.15
        base["educate"] -= 0.10
        base["trust"] -= 0.05
    elif any(k in goal + synthesis_lower for k in ["retention", "giữ chân", "repeat", "loyalty"]):
        base["trust"] += 0.15
        base["convert"] -= 0.05
        base["educate"] -= 0.10

    # Normalize (handle negatives or sum != 1.0)
    for k in base:
        if base[k] < 0.05:
            base[k] = 0.05
    total = sum(base.values())
    return {k: round(v / total, 2) for k, v in base.items()}


def make_sales_inbox_script_skill() -> OperationalSkill:
    return OperationalSkill(_config_for(
        "sales_inbox_script",
        SALES_INBOX_SCRIPT_SYSTEM,
        max_tokens=8000,  # bumped — 7 sections with objection handling
        context_strategy=ContextStrategy.PROFILE_PLUS_CAMPAIGN,
        primary_deliverable=PrimaryDeliverable.MARKDOWN,
    ))


def make_email_zalo_sequence_skill() -> OperationalSkill:
    return OperationalSkill(_config_for(
        "email_zalo_sequence",
        EMAIL_ZALO_SEQUENCE_SYSTEM,
        max_tokens=8000,  # bumped — multi-day sequence with email + zalo for each
        context_strategy=ContextStrategy.PROFILE_PLUS_CAMPAIGN,
        primary_deliverable=PrimaryDeliverable.EXCEL,  # Template: 📧 Email & Zalo sheet
    ))


def make_video_script_gen_skill() -> OperationalSkill:
    """video_script_gen — kịch bản video chuyên sâu từ Calendar → 🎬 Video Script."""
    return OperationalSkill(_config_for(
        "video_script_gen",
        VIDEO_SCRIPT_GEN_SYSTEM,
        max_tokens=14000,  # 5-beat full dialogue × N video — output dài
        context_strategy=ContextStrategy.PROFILE_PLUS_CAMPAIGN,
        primary_deliverable=PrimaryDeliverable.EXCEL,
    ))


def make_ugc_brief_skill() -> OperationalSkill:
    """Creator Brief (UGC/KOL/EGC) → 🤝 UGC Brief sheet."""
    return OperationalSkill(_config_for(
        "ugc_brief",
        UGC_BRIEF_SYSTEM,
        max_tokens=8000,
        context_strategy=ContextStrategy.PROFILE_PLUS_CAMPAIGN,
        primary_deliverable=PrimaryDeliverable.EXCEL,
    ))


class ContentGeneratorPipeline:
    """Pipeline content suite: chạy lần lượt các skill chuyên sâu theo từng loại
    nội dung → mỗi skill xuất 1 file Excel (sheet riêng).

    Full suite: content_gen (bài viết) → video_script_gen (kịch bản video) →
    ugc_brief (creator brief) → ads_generator (ads copy) → email_zalo_sequence.

    Không phải AgentSkill — không gọi LLM trực tiếp.
    run_pipeline(session) được gọi bởi run_operational_skill khi detect pipeline.
    """
    name = "content_generator"
    primary_deliverable = PrimaryDeliverable.EXCEL
    output_format = OutputFormat.OPERATIONAL_DELIVERABLE
    SUB_SKILLS = [
        "post_batch",         # bài đăng — Content Suite v2, narrative output
        "video_script_gen",   # kịch bản video
        "ugc_brief",          # creator brief
        "ads_generator",      # ads copy
    ]

    def _prefill_intake(self, session) -> None:
        """Pre-fill intake cho các sub-skill từ gate answers + profile.

        Gate answers (weeks, highlight_angles, video_type, fgc_channel_mode,
        ugc_outsource, ads_usp) đã được user cung cấp qua form content_generator.
        Pipeline auto-chain đọc từ pending_intake thay vì hardcode defaults.
        """
        pi = session.pending_intake
        profile = session.profile
        goal = pi.get("campaign_goal") or profile.primary_goal or "Thu lead / chốt đơn"

        # video_script_gen — derive creator_type from gate video_type answer
        video_type_raw = (pi.get("video_type") or "").lower()
        if not pi.get("creator_type"):
            if "fgc" in video_type_raw:
                pi["creator_type"] = "fgc"
            elif "egc" in video_type_raw:
                pi["creator_type"] = "egc"
            elif "kol" in video_type_raw:
                pi["creator_type"] = "kol"
            else:
                pi["creator_type"] = "ugc"

        # video_script_gen + VideoScriptsSkill — pass scope from gate
        pi.setdefault("scope", pi.get("scope") or f"{pi.get('weeks', '4 tuần')} — theo calendar")
        pi.setdefault("funnel", "TOFU")
        pi.setdefault("duration", "45s")

        # ugc_brief — pass outsource flag so prompt knows context
        pi.setdefault("creator_types", pi.get("ugc_outsource") or "UGC micro (1K-10K)")

        # ads_generator (AdsCopySkill) — prefer gate answers, fallback to profile
        pi.setdefault("selected_tiers", "all")
        pi.setdefault("product", profile.product_service or "Sản phẩm/dịch vụ chính")
        pi.setdefault("insight", profile.target_customer or "Tệp khách mục tiêu")
        pi.setdefault("campaign_goal", goal)
        pi.setdefault("offer", pi.get("ads_usp") or pi.get("key_offer") or "Ưu đãi theo campaign")

    async def run_pipeline(self, session) -> str:
        from agents.pipeline import run_operational_skill as _run_ops
        import logging
        self._prefill_intake(session)
        ran: list[str] = []
        for skill_name in self.SUB_SKILLS:
            try:
                await _run_ops(skill_name, session)
                ran.append(skill_name)
            except Exception as e:
                logging.getLogger(__name__).warning(
                    "ContentGeneratorPipeline: sub-skill %s failed: %s", skill_name, e
                )
        return f"MULTI_OUTPUT:{','.join(ran)}"


class AdsIntelligencePipeline:
    """Pipeline: Competitor Spy + Ads Analytics — full ads intelligence suite.

    Chạy lần lượt:
      1. competitor_spy  — spy đối thủ từ FB Ads Library
      2. ads_analytics   — phân tích account của mình từ FB Marketing API

    Handler prefetches FB data TRƯỚC khi pipeline chạy và lưu vào hai key riêng:
      _fb_data_spy:       competitor ads (Ads Library)
      _fb_data_analytics: account insights (Marketing API)

    Pipeline swap _fb_data cho đúng skill trước mỗi lần chạy.
    Nếu một nguồn fail → vẫn chạy skill còn lại (graceful degradation).
    """
    name = "ads_intelligence"
    primary_deliverable = PrimaryDeliverable.HTML
    output_format = OutputFormat.OPERATIONAL_ANALYSIS
    SUB_SKILLS = ["competitor_spy", "ads_analytics"]

    def _prefill_intake(self, session) -> None:
        pi = session.pending_intake
        profile = session.profile
        # competitor_spy: fallback competitor_name từ profile nếu user không nhập
        if not pi.get("competitor_name"):
            raw = profile.competitors or ""
            first = raw.split(",")[0].strip() if raw else "Đối thủ chính ngành"
            pi.setdefault("competitor_name", first)
        pi.setdefault("focus_area", "Hook style + Offer mechanics + Budget signals")
        pi.setdefault("pasted_ads", "")
        # ads_analytics
        pi.setdefault("date_range", "30 ngày")
        pi.setdefault("level", "campaign")

    async def run_pipeline(self, session) -> str:
        from agents.pipeline import run_operational_skill as _run_ops
        import logging
        _logger = logging.getLogger(__name__)
        self._prefill_intake(session)
        ran: list[str] = []

        # Run competitor_spy — inject spy-specific FB data
        session.pending_intake["_fb_data"] = session.pending_intake.get("_fb_data_spy") or ""
        try:
            await _run_ops("competitor_spy", session)
            ran.append("competitor_spy")
        except Exception as e:
            _logger.warning("AdsIntelligencePipeline: competitor_spy failed: %s", e)

        # Run ads_analytics — inject analytics-specific FB data
        session.pending_intake["_fb_data"] = session.pending_intake.get("_fb_data_analytics") or ""
        try:
            await _run_ops("ads_analytics", session)
            ran.append("ads_analytics")
        except Exception as e:
            _logger.warning("AdsIntelligencePipeline: ads_analytics failed: %s", e)

        return f"MULTI_OUTPUT:{','.join(ran)}"


def make_competitor_spy_skill() -> OperationalSkill:
    """Sprint 3: NEW — phân tích FB Ads Library của đối thủ.
    Hiện tại em không tự gọi FB API (chờ key). User paste ads content/screenshots → em phân tích."""
    return OperationalSkill(_config_for(
        "competitor_spy",
        COMPETITOR_SPY_SYSTEM,
        max_tokens=8000,
        context_strategy=ContextStrategy.PROFILE_PLUS_STRATEGY,
        primary_deliverable=PrimaryDeliverable.HTML,
    ))


def make_competitor_comparison_skill() -> OperationalSkill:
    """Sprint 4: Follow-up sau competitor analysis — so sánh business sếp vs đối thủ."""
    return OperationalSkill(_config_for(
        "competitor_comparison",
        COMPETITOR_COMPARISON_SYSTEM,
        max_tokens=6000,
        context_strategy=ContextStrategy.FULL_PIPELINE,  # Đọc cả competitor + profile
        primary_deliverable=PrimaryDeliverable.HTML,
    ))


def make_brand_voice_skill() -> OperationalSkill:
    """NEW (test branch): Build bộ quy tắc giọng văn brand."""
    return OperationalSkill(_config_for(
        "brand_voice",
        BRAND_VOICE_SYSTEM,
        max_tokens=8000,
        context_strategy=ContextStrategy.PROFILE_ONLY,
        primary_deliverable=PrimaryDeliverable.HTML,
    ))


def make_content_repurpose_skill() -> OperationalSkill:
    """NEW (test branch): 1 bài content → 5 phiên bản khác audience."""
    return OperationalSkill(_config_for(
        "content_repurpose",
        CONTENT_REPURPOSE_SYSTEM,
        max_tokens=10000,
        context_strategy=ContextStrategy.PROFILE_PLUS_STRATEGY,
        primary_deliverable=PrimaryDeliverable.MARKDOWN,
    ))


def make_retention_strategy_skill() -> OperationalSkill:
    """NEW (from Full-stack-mkt-v0.2): Hệ thống retention 3 giai đoạn."""
    return OperationalSkill(_config_for(
        "retention_strategy",
        RETENTION_STRATEGY_SYSTEM,
        max_tokens=10000,
        context_strategy=ContextStrategy.PROFILE_PLUS_STRATEGY,
        primary_deliverable=PrimaryDeliverable.EXCEL,
    ))


# ─────────────────────────────────────────────────────────────────
# Content Suite v2 — 6 factories
# ─────────────────────────────────────────────────────────────────

def make_post_write_skill() -> OperationalSkill:
    """v2: Single Post Generator — narrative output, NO pipe table."""
    return OperationalSkill(_config_for(
        "post_write",
        POST_WRITE_SYSTEM,
        max_tokens=5000,
        context_strategy=ContextStrategy.PROFILE_PLUS_CAMPAIGN,
        primary_deliverable=PrimaryDeliverable.MARKDOWN,
    ))


def make_post_adapt_skill() -> OperationalSkill:
    """v2: Channel Adapter — 1 post → FB/TikTok/Zalo/IG."""
    return OperationalSkill(_config_for(
        "post_adapt",
        POST_ADAPT_SYSTEM,
        max_tokens=6000,
        context_strategy=ContextStrategy.PROFILE_ONLY,
        primary_deliverable=PrimaryDeliverable.MARKDOWN,
    ))


def make_post_voice_check_skill() -> OperationalSkill:
    """v2: Voice Lock — check draft theo brand voice rules."""
    return OperationalSkill(_config_for(
        "post_voice_check",
        POST_VOICE_CHECK_SYSTEM,
        max_tokens=4000,
        context_strategy=ContextStrategy.PROFILE_ONLY,
        primary_deliverable=PrimaryDeliverable.MARKDOWN,
    ))


def make_post_hooks_skill() -> OperationalSkill:
    """v2: Hook Bank — 15 hooks chia 5 nhóm."""
    return OperationalSkill(_config_for(
        "post_hooks",
        POST_HOOKS_SYSTEM,
        max_tokens=3000,
        context_strategy=ContextStrategy.PROFILE_ONLY,
        primary_deliverable=PrimaryDeliverable.MARKDOWN,
    ))


def make_post_batch_skill() -> OperationalSkill:
    """v2: Batch Producer — N bài cùng lúc."""
    return OperationalSkill(_config_for(
        "post_batch",
        POST_BATCH_SYSTEM,
        max_tokens=15000,  # batch lớn cần nhiều tokens
        context_strategy=ContextStrategy.PROFILE_PLUS_CAMPAIGN,
        primary_deliverable=PrimaryDeliverable.MARKDOWN,
    ))


def make_winback_campaign_skill() -> OperationalSkill:
    """NEW (from Full-stack-mkt-v0.2): Winback khách cũ — sequence 3 bước."""
    return OperationalSkill(_config_for(
        "winback_campaign",
        WINBACK_CAMPAIGN_SYSTEM,
        max_tokens=8000,
        context_strategy=ContextStrategy.PROFILE_ONLY,
        primary_deliverable=PrimaryDeliverable.MARKDOWN,
    ))


def make_ads_analytics_skill() -> OperationalSkill:
    return OperationalSkill(_config_for(
        "ads_analytics",
        ADS_ANALYTICS_SYSTEM,
        max_tokens=5000,
        context_strategy=ContextStrategy.PROFILE_PLUS_STRATEGY,
    ))


class AdsOptimizerSkill(AgentSkill):
    """Special ops skill: phân tích + đề xuất actions trên campaign hierarchy.

    build_user_msg() embeds prefetched hierarchy data từ session.pending_intake["_optimizer_hierarchy"].
    Output chứa [ACTION:...] markers mà handler parse để show confirmation flow.
    """
    name = "ads_optimizer"
    system_prompt = ADS_OPTIMIZER_SYSTEM
    max_tokens = 4000
    enable_critic = False
    output_format = OutputFormat.OPERATIONAL_ANALYSIS
    intake_pattern = IntakePattern.SINGLE_SHOT_FORM
    context_strategy = ContextStrategy.PROFILE_ONLY
    primary_deliverable = PrimaryDeliverable.MARKDOWN
    accumulate_to_report = False

    def build_context(self, session: Session) -> str:
        return session.profile.to_context_string()

    def build_user_msg(self, session: Session) -> str:
        intake = session.pending_intake or {}
        hierarchy = intake.get("_optimizer_hierarchy", "⚠️ Chưa load được hierarchy — hãy kiểm tra kết nối Marketing API")
        account_id = intake.get("_optimizer_account_id", "act_???")

        return f"""## Yêu cầu Tối Ưu Ads

**Tài khoản:** {account_id}
**Muốn thao tác:** {intake.get('target', 'toàn account')}
**Hành động:** {intake.get('action', 'chưa xác định')}
**Lý do / metric tham chiếu:** {intake.get('reason', '(không có)')}

---

## Hierarchy Data (live từ Marketing API)

{hierarchy}

---

Phân tích hierarchy trên, áp dụng Andromeda signals, đề xuất action plan cụ thể với đầy đủ [ACTION:...] markers.
Nếu object sếp yêu cầu không có trong hierarchy → thông báo rõ ràng."""


# ─────────────────────────────────────────────────────────────────
# SPECIAL skills — custom subclasses with extra logic
# ─────────────────────────────────────────────────────────────────

class CampaignBriefDynamicSkill(OperationalSkill):
    """Campaign Brief với channels + source_mix per-channel injected từ intake.
    Brief phải viết chiến lược THEO ĐÚNG kênh + tỉ trọng source sếp đã chốt."""

    def __init__(self):
        config = _config_for(
            "campaign_brief",
            CAMPAIGN_BRIEF_SYSTEM,
            max_tokens=10000,
            context_strategy=ContextStrategy.PROFILE_PLUS_STRATEGY,
            primary_deliverable=PrimaryDeliverable.HTML,
        )
        super().__init__(config)

    def build_user_msg(self, session: Session) -> str:
        msg = super().build_user_msg(session)
        pi = session.pending_intake
        channels = (pi.get("channels") or "").strip()
        total_budget = (pi.get("total_budget") or "").strip()
        media_mix = (pi.get("media_mix") or "").strip()
        hero_channel = (pi.get("hero_channel") or "").strip()
        if total_budget:
            msg += (
                "\n\n---\n\n**TỔNG NGÂN SÁCH DO SẾP CHỐT (dùng ĐÚNG con số này):**\n"
                + total_budget
                + "\n_(Section 5 Budget allocation phân bổ TRONG tổng này. KHÔNG bịa con số khác.)_"
            )
        else:
            msg += (
                "\n\n---\n\n**SẾP CHƯA CUNG CẤP NGÂN SÁCH:**\n"
                "TUYỆT ĐỐI KHÔNG bịa con số ngân sách tuyệt đối (vd '45 triệu'). "
                "Section 5 trình bày phân bổ theo % + ghi rõ '[Sếp xác nhận ngân sách thực tế]'. "
                "Có thể đưa khung benchmark gợi ý nhưng PHẢI ghi chú là 'gợi ý tham khảo'."
            )
        if channels:
            msg += (
                "\n\n---\n\n**KÊNH TRIỂN KHAI DO SẾP CHỐT (chỉ viết brief cho CÁC KÊNH NÀY):**\n"
                + channels
                + "\n_(Section 5 Channel mix + Section 8 KPI PHẢI ghi rõ từng kênh này, KHÔNG thêm kênh khác.)_"
            )
        if media_mix:
            msg += (
                "\n\n**ORGANIC / ADS DO SẾP CHỐT (BẮT BUỘC theo đúng):**\n"
                + media_mix
                + "\n_(Section 5 Budget allocation phải phản ánh đúng kênh nào organic, kênh nào chạy ads + ngân sách ads. "
                "Kênh organic → KPI theo reach/engagement tự nhiên; kênh ads → KPI theo CPM/CPC/CPMess + budget cụ thể.)_"
            )
        if hero_channel:
            msg += (
                "\n\n**KÊNH CHỦ LỰC vs HỖ TRỢ DO SẾP CHỐT:**\n"
                + hero_channel
                + "\n_(Dồn phần lớn budget + nội dung vào kênh chủ lực. Kênh hỗ trợ chỉ repurpose/amplify. "
                "Section 5 + Section 9 timeline phải reflect ưu tiên này.)_"
            )
        return msg


class ContentCalendarDynamicSkill(OperationalSkill):
    """Sprint 3.4: Content Calendar với Pillar % dynamic theo business stage + goal."""

    def __init__(self):
        config = _config_for(
            "content_calendar",
            CONTENT_CALENDAR_SYSTEM,
            max_tokens=10000,
            context_strategy=ContextStrategy.PROFILE_PLUS_CAMPAIGN,
            primary_deliverable=PrimaryDeliverable.EXCEL,
        )
        super().__init__(config)

    def build_user_msg(self, session: Session) -> str:
        base_msg = super().build_user_msg(session)
        # Inject dynamic pillar mix
        synthesis = session.get_latest_result("synthesis") or ""
        pillar_mix = calc_dynamic_pillar_mix(session.profile, synthesis)
        pillar_str = " / ".join(
            f"{k.title()} {int(v*100)}%" for k, v in pillar_mix.items()
        )
        msg = (
            base_msg
            + "\n\n---\n\n**PILLAR MIX TÍNH ĐỘNG cho business này (dùng đúng số này, không tự thay):**\n"
            + pillar_str
            + "\n\n_(Tính dựa trên: stage = "
            + str(session.profile.stage or "unknown")
            + ", goal = "
            + str(session.profile.primary_goal or "unknown")
            + ")_"
        )
        # Inject calendar edit feedback nếu có
        feedback = session.pending_intake.get("_calendar_feedback", "")
        if feedback:
            msg += f"\n\n---\n\n**🔄 YÊU CẦU SỬA LỊCH từ sếp (BẮT BUỘC áp dụng):**\n{feedback}"
        return msg


class AdsCopySkill(AgentSkill):
    """Special ops skill: user picks which tier(s) to generate.

    Reads `session.pending_intake["selected_tiers"]` to determine scope:
      - "tofu" / "mofu" / "bofu" → only that tier (2 variants)
      - "all" → 3 tiers × 2 variants = 6 copy units
    """
    name = "ads_copy"
    system_prompt = ADS_COPY_SYSTEM
    max_tokens = 12000  # bumped — full 3-tier × 2 variants × 2 platforms = 12 copy units
    enable_critic = False
    output_format = OutputFormat.OPERATIONAL_DELIVERABLE
    intake_pattern = IntakePattern.SINGLE_SHOT_FORM
    context_strategy = ContextStrategy.PROFILE_PLUS_CAMPAIGN
    primary_deliverable = PrimaryDeliverable.EXCEL  # Template: ✍️ Ad Copy sheet
    accumulate_to_report = False

    def build_context(self, session: Session) -> str:
        parts = [session.profile.to_context_string()]
        # Inject campaign_brief if available for tone consistency
        campaign_brief = session.get_latest_result("campaign_brief")
        if campaign_brief:
            parts.append(f"## Campaign Brief context\n{campaign_brief}")
        # Tactical Playbook (T5) — copy mẫu / hook / kênh trong ads phải khớp tactics
        playbook = session.get_latest_result("tactical_playbook")
        if playbook:
            parts.append(f"## Tactical Playbook (bám copy mẫu + kênh + hook style)\n{playbook[:4000]}")
        return "\n\n---\n\n".join(parts)

    def build_user_msg(self, session: Session) -> str:
        intake = session.pending_intake or {}
        tier = (intake.get("selected_tiers") or "all").lower()
        profile = session.profile

        scope_instruction = {
            "tofu": "CHỈ generate TẦNG 1 — TOFU (2 variants). Bỏ qua MOFU/BOFU.",
            "mofu": "CHỈ generate TẦNG 2 — MOFU (2 variants). Bỏ qua TOFU/BOFU.",
            "bofu": "CHỈ generate TẦNG 3 — BOFU (2 variants). Bỏ qua TOFU/MOFU.",
            "all":  "Generate FULL 3 tầng (TOFU + MOFU + BOFU), mỗi tầng 2 variants. Tổng 6 copy units.",
        }.get(tier, "Generate FULL 3 tầng (TOFU + MOFU + BOFU).")

        return f"""## Yêu cầu: Viết Ads Copy cho campaign

**Sản phẩm/giá:** {intake.get('product', 'chưa có')}
**Insight cốt lõi:** {intake.get('insight', 'chưa có')}
**Mục tiêu campaign:** {intake.get('campaign_goal', 'chưa có')}
**Ưu đãi + deadline:** {intake.get('offer', 'chưa có')}

**Context business:**
- Ngành: {profile.industry or 'chưa xác định'}
- Khách hàng: {profile.target_customer or 'chưa xác định'}
- Địa bàn: {profile.location or 'Việt Nam'}

**Scope:** {scope_instruction}

Viết copy thật sự dùng được ngay, không generic."""


class VideoScriptsSkill(AgentSkill):
    """Special ops skill: 4 creator type variants.

    Reads `session.pending_intake["creator_type"]` to determine variant style:
      - "ugc" / "egc" / "fgc" / "kol"
    """
    name = "video_scripts"
    system_prompt = VIDEO_SCRIPTS_SYSTEM
    max_tokens = 8000  # bumped — 2 variants + production guide
    enable_critic = False
    output_format = OutputFormat.OPERATIONAL_DELIVERABLE
    intake_pattern = IntakePattern.SINGLE_SHOT_FORM
    context_strategy = ContextStrategy.PROFILE_PLUS_CAMPAIGN
    primary_deliverable = PrimaryDeliverable.EXCEL  # Template: 🎬 Video Script sheet
    accumulate_to_report = False

    def build_context(self, session: Session) -> str:
        parts = [session.profile.to_context_string()]
        campaign_brief = session.get_latest_result("campaign_brief")
        if campaign_brief:
            parts.append(f"## Campaign Brief context\n{campaign_brief}")
        # Tactical Playbook (T5) — hook / format / kênh video phải khớp tactics
        playbook = session.get_latest_result("tactical_playbook")
        if playbook:
            parts.append(f"## Tactical Playbook (bám hook + format + kênh)\n{playbook[:4000]}")
        return "\n\n---\n\n".join(parts)

    def build_user_msg(self, session: Session) -> str:
        intake = session.pending_intake or {}
        creator_type = (intake.get("creator_type") or "").lower()
        creator_chosen = bool(creator_type)
        fgc_channel_mode = (intake.get("fgc_channel_mode") or "").lower()
        profile = session.profile

        # ── Loại nội dung (TYPE) quyết định format + hook — đây là trục chính ──
        content_type_raw = (intake.get("content_type") or "").lower()
        if any(k in content_type_raw for k in ("educate", "dạy", "day", "hướng dẫn", "huong dan", "chỉ", "tips")):
            type_guidance = (
                "EDUCATE — dạy/giải thích. Format gợi ý: tutorial how-to, "
                "myth-busting (phá vỡ hiểu lầm), hoặc '3 sai lầm phổ biến'. "
                "Hook 0-3s = câu hỏi nhức nhối hoặc 1 sai lầm đa số đang mắc."
            )
        elif any(k in content_type_raw for k in ("bán", "ban", "sell", "sale", "mua", "chốt", "convert")):
            type_guidance = (
                "BÁN HÀNG — đẩy hành động mua. Format gợi ý: demo/review sản phẩm, "
                "before-after, hoặc unbox. Hook = pain point cụ thể → solution. CTA rõ ràng cuối video."
            )
        elif any(k in content_type_raw for k in ("giải trí", "giai tri", "entertain", "hài", "hai", "trend", "vui")):
            type_guidance = (
                "GIẢI TRÍ — tạo tương tác & lan toả. Format gợi ý: skit/tiểu phẩm, "
                "relatable situation, hoặc bắt trend. Hook = tình huống đời thường gây cười/đồng cảm. "
                "Bán hàng ẩn rất nhẹ hoặc không bán."
            )
        elif any(k in content_type_raw for k in ("tin", "trust", "uy tín", "uy tin", "niềm tin", "niem tin", "thật", "that")):
            type_guidance = (
                "XÂY NIỀM TIN — tăng độ tin cậy. Format gợi ý: behind-the-scenes, "
                "testimonial/câu chuyện khách thật, hoặc số liệu/quy trình minh bạch. "
                "Hook = câu chuyện thật hoặc con số bất ngờ."
            )
        else:
            type_guidance = (
                "Loại nội dung linh hoạt — chọn format phù hợp nhất với thông điệp. "
                "Hook 0-3s phải chặn người xem ngay."
            )

        # ── Người xuất hiện (creator type) — phụ, chỉ nêu nếu user đã chọn ──
        if creator_chosen and creator_type == "fgc":
            is_rieng = any(k in fgc_channel_mode for k in ("riêng", "rièng", "rieng", "separate", "cá nhân"))
            if is_rieng:
                creator_guidance = (
                    "FGC (Founder-Generated Content) — KÊNH RIÊNG CỦA FOUNDER.\n"
                    "• Tone: cá nhân hoàn toàn — viết như người thật nói chuyện thật, KHÔNG mention brand trực tiếp.\n"
                    "• Story: hành trình founder, cuộc sống, bài học kinh doanh, góc nhìn ngành.\n"
                    "• CTA mềm: 'Follow theo dõi hành trình' / 'Save để đọc lại' — KHÔNG đẩy product.\n"
                    "• Style: authentic, không chỉn chu quá — vibe founder thật, đời thường hơn brand channel.\n"
                    "• Background: nhà/văn phòng riêng, KHÔNG có logo brand hay banner sản phẩm."
                )
            else:  # merge / kết hợp brand
                creator_guidance = (
                    "FGC (Founder-Generated Content) — KẾT HỢP VÀO KÊNH BRAND.\n"
                    "• Tone: founder voice + brand-connected — câu chuyện liên quan đến sản phẩm/dịch vụ.\n"
                    "• Story: OK mention brand nhẹ, dẫn đến product benefit một cách tự nhiên.\n"
                    "• CTA rõ hơn: 'Xem chi tiết link bio' / 'Inbox để tư vấn' / 'Comment hỏi em'.\n"
                    "• Style: founder vibe nhưng brand-forward hơn kênh riêng — chỉn chu vừa phải.\n"
                    "• Background: có thể xuất hiện sản phẩm/không gian brand, logo nhỏ OK."
                )
        elif creator_chosen:
            creator_guidance = {
                "ugc": "UGC (User-Generated Content) — khách hàng thật chia sẻ. Tone bình thản, kể chuyện với bạn thân. Authentic > polished.",
                "egc": "EGC (Employee-Generated Content) — nhân viên chia sẻ insider knowledge. Tone expert nhẹ, backstage style.",
                "kol": "KOL/KOC (Paid Creator) — creator paid để promote. Tone theo persona của KOC, integrated organic. Brief tập trung message + Do/Don't.",
            }.get(creator_type, "UGC — authentic style.")
        else:
            creator_guidance = (
                "Chưa chốt — em tự chọn người xuất hiện phù hợp nội dung "
                "(khách thật / nhân viên / founder / KOC) và ghi rõ trong mỗi variant."
            )

        highlight = (intake.get("highlight") or "").strip()
        highlight_line = f"\n**Điểm nhấn đặc biệt:** {highlight}" if highlight else ""

        return f"""## Yêu cầu: Viết Video Script (TikTok/Reels/Shorts)

**Chủ đề / sản phẩm:** {intake.get('topic', 'chưa có')}
**Thông điệp chính (người xem PHẢI nhớ):** {intake.get('key_message', 'chưa có')}
**Loại nội dung:** {intake.get('content_type', 'chưa rõ')}{highlight_line}

**Định hướng theo loại nội dung (quyết định format + hook):**
{type_guidance}

**Người xuất hiện trong video:**
{creator_guidance}

**Context business:**
- Ngành: {profile.industry or 'chưa xác định'}
- Khách hàng: {profile.target_customer or 'chưa xác định'}

NGUYÊN TẮC: Nội dung & thông điệp là gốc — format/cách quay do em tự chọn cho khớp loại nội dung, KHÔNG gò ép.
Output 2 VARIANTS A/B với góc tiếp cận KHÁC NHAU (vd 1 bản kể chuyện, 1 bản thẳng vào vấn đề).
Mỗi variant: hook 0-3s, script timing chi tiết theo giây, caption + hashtag gợi ý, gợi ý hình ảnh/cách quay.

Lưu ý: KHÔNG bao gồm hợp đồng/commercial terms."""


class ViralVideoAnalyzerSkill(AgentSkill):
    """Special analysis skill: reverse-engineer kịch bản video viral.

    Flow:
      1. Đọc `session.pending_intake["video_source"]` (URL hoặc transcript paste sẵn)
      2. Nếu là URL → gọi tools.krillin_client.extract_transcript() (KrillinAI binary
         hoặc Whisper API fallback) + trả về local_video_path
      3. Nếu local_video_path có sẵn → tools.video_vision.extract_visual_analysis()
         dùng ffmpeg + Claude vision phân tích keyframes
      4. Nếu là transcript paste → dùng trực tiếp, đánh dấu source="user_paste",
         skip vision
      5. Inject transcript + visual analysis vào user_msg
      6. Claude phân tích 9 sections

    Vision is optional — graceful degrade nếu ffmpeg không có hoặc extract fail.
    Cache extract result vào session.pending_intake để không gọi 2 lần.

    KrillinAI repo: https://github.com/krillinai/KlicStudio
    Setup: KRILLIN_BINARY (transcript), OPENAI_API_KEY (whisper fallback),
    ffmpeg binary + ANTHROPIC_API_KEY (vision).
    """
    name = "viral_video_analyzer"
    system_prompt = VIRAL_VIDEO_ANALYZER_SYSTEM
    max_tokens = 10000
    enable_critic = True
    output_format = OutputFormat.OPERATIONAL_ANALYSIS
    intake_pattern = IntakePattern.SINGLE_SHOT_FORM
    context_strategy = ContextStrategy.PROFILE_PLUS_STRATEGY
    primary_deliverable = PrimaryDeliverable.HTML
    accumulate_to_report = False

    def build_context(self, session: Session) -> str:
        parts = [session.profile.to_context_string()]
        synthesis = session.get_latest_result("synthesis")
        if synthesis:
            parts.append(
                "## Marketing Strategy nền (dùng để tailor công thức replicate cho business sếp)\n"
                f"{synthesis[:4000]}"
            )
        return "\n\n---\n\n".join(parts)

    def build_user_msg(self, session: Session) -> str:
        intake = session.pending_intake or {}
        video_source = (intake.get("video_source") or "").strip()
        platform = intake.get("platform") or "chưa rõ"
        niche_context = intake.get("niche_context") or "chưa cung cấp"
        creator_persona = intake.get("creator_persona") or "chưa rõ — Max default UGC nữ 24-30t"
        engagement_data = intake.get("engagement_data") or "không rõ"
        why_picked = intake.get("why_picked") or ""
        profile = session.profile

        # Resolve transcript (URL → extract, hoặc paste trực tiếp)
        transcript_block, local_video_path, segments = self._resolve_transcript(video_source)

        # Resolve visual analysis (chỉ chạy nếu có local file từ extract)
        visual_block = ""
        if local_video_path:
            visual_block = self._resolve_visual_analysis(local_video_path, segments)

        why_line = f"\n**Lý do sếp chọn video này:** {why_picked}" if why_picked else ""

        visual_section = ""
        if visual_block:
            visual_section = f"\n\n---\n\n{visual_block}\n"
        else:
            visual_section = (
                "\n\n---\n\n"
                "### VISUAL ANALYSIS\n\n"
                "_(Vision analysis không khả dụng — ffmpeg/Claude vision chưa setup hoặc input là paste transcript. "
                "Section 9.1 shot list sẽ suy từ transcript, đánh dấu rõ '(suy từ transcript)' những chỗ không chắc.)_\n"
            )

        return f"""## Yêu cầu: Phân Tích Video Viral

**Platform:** {platform}
**Niche video:** {niche_context}
**Creator persona sẽ quay video replicate:** {creator_persona}
**Số liệu engagement (nếu có):** {engagement_data}{why_line}

**Context business sếp (để tailor công thức replicate):**
- Ngành: {profile.industry or 'chưa xác định'}
- Sản phẩm/dịch vụ: {profile.product_service or 'chưa xác định'}
- Khách hàng: {profile.target_customer or 'chưa xác định'}
- Địa bàn: {profile.location or 'Việt Nam'}

---

### TRANSCRIPT VIDEO (đã extract sẵn)

{transcript_block}{visual_section}
---

Phân tích đầy đủ 9 sections theo system prompt.

QUAN TRỌNG:
- Section 8 (Replicate Formula): tailor cho business sếp — không generic
- Section 9 (Production Brief): BẮT BUỘC viết shoot-ready cho creator persona đã nêu —
  shot list theo timestamp (tham chiếu VISUAL ANALYSIS phía trên nếu có), audio strategy,
  edit pacing số cụ thể, caption + first comment paste-ready, hashtag stack 10-15 cái,
  cover frame, posting plan, budget realistic,
  và 3 SCRIPT HOÀN CHỈNH (KHÔNG dùng placeholder, viết thoại cụ thể quay được luôn)."""

    def _resolve_transcript(self, video_source: str) -> tuple[str, str, list]:
        """Resolve video_source → (formatted_block, local_video_path, segments).

        local_video_path != "" chỉ khi extract URL thành công và có file cục bộ
        → vision có thể dùng tiếp.
        """
        from tools import krillin_client
        import asyncio

        if not video_source:
            return ("**(Không có transcript — sếp chưa cung cấp link hay paste lời thoại)**", "", [])

        is_url = bool(krillin_client.URL_REGEX.match(video_source))

        if is_url:
            if not krillin_client.is_available():
                return (
                    f"**⚠️ Không extract được transcript từ URL** ({video_source})\n\n"
                    f"Engine status:\n{krillin_client.availability_report()}\n\n"
                    "Workaround: sếp paste trực tiếp transcript vào ô `video_source` thay link, "
                    "Max vẫn phân tích được kịch bản đầy đủ.",
                    "",
                    [],
                )
            try:
                extract = _run_async_sync(
                    krillin_client.extract_transcript(video_source, language_hint="vi"),
                    timeout=320,
                )
                block = krillin_client.format_transcript_for_prompt(extract)
                return (
                    block,
                    extract.get("local_video_path", "") or "",
                    extract.get("segments") or [],
                )
            except Exception as e:
                return (
                    f"**⚠️ Extract transcript thất bại** ({type(e).__name__}: {str(e)[:200]})\n\n"
                    "Sếp paste trực tiếp transcript thay link, Max phân tích lại được.",
                    "",
                    [],
                )

        # User paste transcript trực tiếp — không có file để vision
        return (
            f"**Transcript engine:** user_paste (sếp đã paste trực tiếp lời thoại)\n\n"
            f"```\n{video_source[:8000]}\n```",
            "",
            [],
        )

    def _resolve_visual_analysis(self, local_video_path: str, segments: list) -> str:
        """Run ffmpeg + Claude vision trên video file. Trả về text block hoặc rỗng."""
        try:
            from tools import video_vision
            if not video_vision.is_available():
                return ""
            return _run_async_sync(
                video_vision.extract_visual_analysis(local_video_path, segments),
                timeout=180,
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"vision analysis failed: {e}")
            return ""


def _run_async_sync(coro, timeout: int = 60):
    """Run async coro from sync context — handle both 'in loop' and 'no loop' cases.

    Pipeline runner calls build_user_msg synchronously, nhưng nó nằm trong asyncio
    event loop. Pattern: nếu loop đang chạy → schedule trên thread pool.
    """
    import asyncio
    import concurrent.futures
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result(timeout=timeout)
    return asyncio.run(coro)


# ─────────────────────────────────────────────────────────────────
# Registry: skill_name → factory function
# ─────────────────────────────────────────────────────────────────

OPS_SKILL_FACTORIES: dict[str, callable] = {
    "campaign_brief":      CampaignBriefDynamicSkill,
    "content_calendar":    ContentCalendarDynamicSkill,  # Sprint 3.4 — Pillar dynamic
    "content_generator":   ContentGeneratorPipeline,
    "video_script_gen":    make_video_script_gen_skill,
    "ugc_brief":           make_ugc_brief_skill,
    "ads_intelligence":    AdsIntelligencePipeline,
    "competitor_spy":      make_competitor_spy_skill,
    "competitor_comparison": make_competitor_comparison_skill,
    "sales_inbox_script":  make_sales_inbox_script_skill,
    "email_zalo_sequence": make_email_zalo_sequence_skill,
    "ads_analytics":       make_ads_analytics_skill,
    "ads_optimizer":       AdsOptimizerSkill,
    "ads_copy":            AdsCopySkill,
    "ads_generator":       AdsCopySkill,
    "video_scripts":       VideoScriptsSkill,
    "viral_video_analyzer": ViralVideoAnalyzerSkill,
    # NEW skills (test branch)
    "brand_voice":         make_brand_voice_skill,
    "content_repurpose":   make_content_repurpose_skill,
    "retention_strategy":  make_retention_strategy_skill,
    "winback_campaign":    make_winback_campaign_skill,
    # Content Suite v2 (branch: content-gen-suite)
    "post_write":          make_post_write_skill,
    "post_adapt":          make_post_adapt_skill,
    "post_voice_check":    make_post_voice_check_skill,
    "post_hooks":          make_post_hooks_skill,
    "post_batch":          make_post_batch_skill,
}


def get_operational_skill(skill_name: str) -> AgentSkill:
    """Factory entry point — returns an AgentSkill instance for the named operational skill."""
    factory = OPS_SKILL_FACTORIES.get(skill_name)
    if not factory:
        raise ValueError(f"Unknown operational skill: {skill_name}")
    return factory() if callable(factory) else factory
