"""
Pipeline Orchestration Engine.
Manages the sequential execution of all 8 agents via Claude API.

All agent entry points are timeout-wrapped — Claude API can hang on rare network
issues, and tool-use loops can iterate indefinitely if the model misbehaves.
"""
import json
import logging
import re
import asyncio
from typing import AsyncGenerator, Optional

import anthropic

from config import (
    CLAUDE_MODEL,
    ANTHROPIC_API_KEY,
    AGENT_TIMEOUT,
    PIPELINE_STAGE_TIMEOUT,
)
from tools.search import web_search, WEB_SEARCH_TOOL
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
from agents._decorators import with_timeout, AgentTimeoutError, AgentExecutionError
from frameworks.kpi_library import get_framework_as_text
from frameworks.save_framework import generate_save_analysis
from frameworks.smart_framework import format_smart_prompt

logger = logging.getLogger(__name__)
client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)


# ─────────────────────────────────────────────────────────────────
# INTAKE AGENT — conversational, multi-turn
# ─────────────────────────────────────────────────────────────────

@with_timeout(AGENT_TIMEOUT)
async def run_intake(session: Session, user_message: str) -> tuple[str, bool]:
    """
    Run one turn of the intake conversation.
    Returns (response_text, is_profile_complete).
    """
    session.add_to_history("user", user_message)

    system_prompt = get_intake_system(session.selected_task or "full")
    system_def = [{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}]
    # Local copy — tool call turns stay here only, NOT written to session.intake_history
    messages = session.intake_history.copy()

    while True:
        response = await client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=system_def,
            messages=messages,
            tools=[WEB_SEARCH_TOOL],
        )

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use" and block.name == "web_search":
                    result = await web_search(block.input["query"])
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
        else:
            assistant_text = "".join(
                b.text for b in response.content if hasattr(b, "text")
            )
            session.add_to_history("assistant", assistant_text)
            profile, is_complete = _extract_profile_from_response(assistant_text)
            if is_complete and profile:
                session.profile = profile
            return assistant_text, is_complete


@with_timeout(AGENT_TIMEOUT)
async def run_followup(session: Session, question: str) -> str:
    """Answer a follow-up question after the full pipeline has completed."""
    context_str = session.build_pipeline_context()
    followup_system = (
        STRATEGY_SYNTHESIZER_SYSTEM
        + "\n\nBạn đã hoàn thành phân tích. Trả lời câu hỏi follow-up dựa trên kết quả đã có."
    )
    response = await client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1500,
        system=[{
            "type": "text",
            "text": followup_system,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{
            "role": "user",
            "content": f"{context_str}\n\n---\n\nCâu hỏi follow-up: {question}",
        }],
    )
    return response.content[0].text


def _extract_profile_from_response(text: str) -> tuple[Optional[BusinessProfile], bool]:
    """Parse JSON block from AI response into BusinessProfile."""
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if not match:
        return None, False

    try:
        data = json.loads(match.group(1))
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
        )
        return profile, profile.is_ready_for_analysis()
    except (json.JSONDecodeError, TypeError):
        return None, False


# ─────────────────────────────────────────────────────────────────
# PIPELINE STAGES — single-shot Claude calls
# ─────────────────────────────────────────────────────────────────

@with_timeout(AGENT_TIMEOUT)
async def _run_agent(
    system_prompt: str,
    user_message: str,
    context: str,
    max_tokens: int = 2048,
) -> str:
    """Generic agent runner with prompt caching on system."""
    response = await client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=[
            {
                "type": "text",
                "text": system_prompt,
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


@with_timeout(PIPELINE_STAGE_TIMEOUT)
async def _run_agent_with_tools(
    system_prompt: str,
    user_message: str,
    context: str,
    max_tokens: int = 2048,
) -> str:
    """
    Agent runner that can call web_search tool before producing final answer.
    Uses higher timeout (PIPELINE_STAGE_TIMEOUT) because tool-use loops add latency.
    """
    system_def = [{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}]
    messages = [{"role": "user", "content": f"{context}\n\n---\n\n{user_message}"}]

    while True:
        response = await client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=max_tokens,
            system=system_def,
            messages=messages,
            tools=[WEB_SEARCH_TOOL],
        )

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use" and block.name == "web_search":
                    result = await web_search(block.input["query"])
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
        else:
            return "".join(b.text for b in response.content if hasattr(b, "text"))


async def run_market_research(session: Session) -> str:
    context = session.profile.to_context_string()
    kpi_text = get_framework_as_text(session.profile.industry or "")

    user_msg = f"""Hãy phân tích TAM/SAM/SOM cho business này.

{kpi_text}

Đặc biệt chú ý methodology ước tính TAM phù hợp với ngành {session.profile.industry}.
Location: {session.profile.location or 'Việt Nam'}
Target customer: {session.profile.target_customer}"""

    result = await _run_agent_with_tools(MARKET_RESEARCH_SYSTEM, user_msg, context)
    session.results["market_research"] = result
    return result


async def run_competitor_analysis(session: Session) -> str:
    context = session.build_pipeline_context()
    competitors_known = session.profile.competitors or "chưa xác định"

    user_msg = f"""Phân tích landscape cạnh tranh cho business này.

Đối thủ founder đề cập: {competitors_known}

Hãy:
1. Phân tích các đối thủ đã biết (nếu có)
2. Identify thêm các đối thủ điển hình trong ngành {session.profile.industry} tại {session.profile.location or 'VN'}
3. Tìm market gaps rõ ràng nhất
4. Đề xuất positioning opportunity"""

    result = await _run_agent_with_tools(COMPETITOR_SYSTEM, user_msg, context, max_tokens=2048)
    session.results["competitor"] = result
    return result


async def run_customer_insight(session: Session) -> str:
    context = session.build_pipeline_context()

    user_msg = f"""Xây dựng Customer Insight đầy đủ cho business này.

Product/Service: {session.profile.product_service}
Target customer: {session.profile.target_customer}
Location: {session.profile.location or 'Việt Nam'}

Hãy đào sâu vào psychographics, JTBD, và Vietnamese cultural context của ngành {session.profile.industry}."""

    result = await _run_agent(CUSTOMER_INSIGHT_SYSTEM, user_msg, context, max_tokens=2048)
    session.results["customer_insight"] = result
    return result


async def run_psychology_and_pricing(session: Session) -> str:
    context = session.build_pipeline_context()

    user_msg = f"""Áp dụng Marketing Psychology VÀ đề xuất Pricing Strategy cho business này.

Budget marketing: {session.profile.monthly_marketing_budget or 'chưa xác định'}
Mục tiêu: {session.profile.primary_goal}
Stage: {session.profile.stage}

Phần 1: Map psychological principles vào từng touchpoint của funnel
Phần 2: Đề xuất pricing model và tactics cụ thể (với số liệu)"""

    # Combine psychology + pricing into one call to save time
    combined_system = f"""{MARKETING_PSYCHOLOGY_SYSTEM}

---

{PRICING_STRATEGY_SYSTEM}

Hãy output CẢ HAI phần: Psychology Application VÀ Pricing Strategy trong một response duy nhất, chia section rõ ràng."""

    result = await _run_agent(combined_system, user_msg, context, max_tokens=3000)
    session.results["psychology_pricing"] = result
    return result


async def run_social_listening(session: Session) -> str:
    context = session.build_pipeline_context()

    user_msg = f"""Thiết kế Social Listening System cho business này.

Business: {session.profile.business_name or session.profile.product_service}
Ngành: {session.profile.industry}
Team size: {session.profile.team_size or 'nhỏ'}
Đối thủ biết đến: {session.profile.competitors or 'chưa xác định'}

Tạo system thực tế, phù hợp với team nhỏ, tập trung vào platform VN."""

    result = await _run_agent_with_tools(SOCIAL_LISTENING_SYSTEM, user_msg, context, max_tokens=2048)
    session.results["social_listening"] = result
    return result


async def run_strategy_synthesis(session: Session) -> str:
    context = session.build_pipeline_context()

    # Inject SAVE + SMART frameworks
    save_prompt = generate_save_analysis(
        industry=session.profile.industry or "",
        business_description=session.profile.product_service or "",
        target_customer=session.profile.target_customer or "",
        product_service=session.profile.product_service or "",
    )
    smart_prompt = format_smart_prompt(
        industry=session.profile.industry or "",
        stage=session.profile.stage or "growth",
        goals=[session.profile.primary_goal or "tăng doanh thu"],
    )

    user_msg = f"""Tổng hợp tất cả insights đã phân tích thành Marketing Strategy hoàn chỉnh.

{save_prompt}

{smart_prompt}

Yêu cầu:
- Apply SAVE Framework cụ thể cho {session.profile.business_name or 'business này'}
- Tạo 2-3 SMART goals với số liệu thực tế
- 90-day roadmap cụ thể, actionable
- KPI dashboard với targets 30/60/90 ngày
- Quick wins có thể làm ngay trong 2 tuần đầu
- Budget allocation đề xuất"""

    result = await _run_agent(
        STRATEGY_SYNTHESIZER_SYSTEM, user_msg, context, max_tokens=4000
    )
    session.results["synthesis"] = result
    return result


# ─────────────────────────────────────────────────────────────────
# PIPELINE RUNNER — orchestrates all stages
# ─────────────────────────────────────────────────────────────────

PIPELINE_SEQUENCE = [
    (PipelineStage.MARKET_RESEARCH, run_market_research, "market_research"),
    (PipelineStage.COMPETITOR, run_competitor_analysis, "competitor"),
    (PipelineStage.CUSTOMER_INSIGHT, run_customer_insight, "customer_insight"),
    (PipelineStage.PSYCHOLOGY_PRICING, run_psychology_and_pricing, "psychology_pricing"),
    (PipelineStage.SOCIAL_LISTENING, run_social_listening, "social_listening"),
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


# ─────────────────────────────────────────────────────────────────
# TARGETED PIPELINE — runs only stages relevant to selected task
# ─────────────────────────────────────────────────────────────────

TASK_PIPELINE_MAP: dict[str, list] = {
    "full":       PIPELINE_SEQUENCE,
    "market":     [(PipelineStage.MARKET_RESEARCH, run_market_research, "market_research")],
    "competitor": [(PipelineStage.COMPETITOR, run_competitor_analysis, "competitor")],
    "customer":   [(PipelineStage.CUSTOMER_INSIGHT, run_customer_insight, "customer_insight")],
    "pricing":    [(PipelineStage.PSYCHOLOGY_PRICING, run_psychology_and_pricing, "psychology_pricing")],
    "social":     [(PipelineStage.SOCIAL_LISTENING, run_social_listening, "social_listening")],
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
