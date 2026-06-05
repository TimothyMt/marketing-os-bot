"""
Tier 2 Pipeline: Campaign Planning.
Input: Session with completed Tier 1 (session.results['synthesis'] must exist)
Stages: campaign_select → campaign_brief → content_calendar
"""
import asyncio
from typing import AsyncGenerator, Optional

import anthropic

from config import CLAUDE_SONNET_MODEL, ANTHROPIC_API_KEY, AGENT_TIMEOUT
from storage.models import Session, PipelineStage
from agents.tier2_skills import CampaignBriefSkill, ContentCalendarSkill

client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)


async def _run_tier2_skill(skill, session: Session) -> str:
    from agents.tier2_prompts import CAMPAIGN_BRIEF_SYSTEM, CONTENT_CALENDAR_SYSTEM
    context = skill.build_context(session)
    user_msg = skill.build_user_msg(session)

    response = await client.messages.create(
        model=CLAUDE_SONNET_MODEL,
        max_tokens=skill.max_tokens,
        system=[{"type": "text", "text": skill.system_prompt, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": f"{context}\n\n---\n\n{user_msg}"}],
    )
    return response.content[0].text


async def run_campaign_brief(session: Session) -> str:
    result = await _run_tier2_skill(CampaignBriefSkill(), session)
    session.results["campaign_brief"] = result
    return result


async def run_content_calendar(session: Session) -> str:
    result = await _run_tier2_skill(ContentCalendarSkill(), session)
    session.results["content_calendar"] = result
    return result


TIER2_PIPELINE_SEQUENCE = [
    (PipelineStage.CAMPAIGN_BRIEF, run_campaign_brief, "campaign_brief"),
    (PipelineStage.CONTENT_CALENDAR, run_content_calendar, "content_calendar"),
]

TIER2_PROGRESS_MESSAGES = {
    "campaign_brief":   "📋 Đang xây dựng Campaign Brief...",
    "content_calendar": "📅 Đang lập lịch nội dung 30 ngày...",
}


async def run_tier2_pipeline(
    session: Session,
    progress_callback=None,
) -> AsyncGenerator[tuple[str, str], None]:
    if "synthesis" not in session.results:
        yield "error", "⚠️ Cần hoàn thành phân tích Tier 1 (synthesis) trước khi lập kế hoạch chiến dịch."
        return

    session.current_tier = 2

    for stage_enum, stage_fn, stage_key in TIER2_PIPELINE_SEQUENCE:
        session.stage = stage_enum

        if progress_callback and stage_key in TIER2_PROGRESS_MESSAGES:
            await progress_callback(TIER2_PROGRESS_MESSAGES[stage_key])

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

    session.stage = PipelineStage.TIER2_COMPLETE
