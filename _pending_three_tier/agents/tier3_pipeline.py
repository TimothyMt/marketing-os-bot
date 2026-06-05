"""
Tier 3 Pipeline: Content Generation.
Input: Session with completed Tier 2 (session.results['campaign_brief'] must exist)
Stages: ad_copy | video_script | ugc_brief | email_zalo
"""
import asyncio
from typing import AsyncGenerator

import anthropic

from config import CLAUDE_SONNET_MODEL, ANTHROPIC_API_KEY, AGENT_TIMEOUT
from storage.models import Session, PipelineStage
from agents.tier3_skills import (
    AdCopySkill,
    VideoScriptSkill,
    UGCBriefSkill,
    EmailZaloSkill,
)

client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)


async def _run_tier3_skill(skill, session: Session) -> str:
    context = skill.build_context(session)
    user_msg = skill.build_user_msg(session)

    response = await client.messages.create(
        model=CLAUDE_SONNET_MODEL,
        max_tokens=skill.max_tokens,
        system=[{"type": "text", "text": skill.system_prompt, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": f"{context}\n\n---\n\n{user_msg}"}],
    )
    return response.content[0].text


async def run_ad_copy(session: Session) -> str:
    result = await _run_tier3_skill(AdCopySkill(), session)
    session.results["ad_copy"] = result
    return result


async def run_video_script(session: Session) -> str:
    result = await _run_tier3_skill(VideoScriptSkill(), session)
    session.results["video_script"] = result
    return result


async def run_ugc_brief(session: Session) -> str:
    result = await _run_tier3_skill(UGCBriefSkill(), session)
    session.results["ugc_brief"] = result
    return result


async def run_email_zalo(session: Session) -> str:
    result = await _run_tier3_skill(EmailZaloSkill(), session)
    session.results["email_zalo"] = result
    return result


TIER3_RUNNERS: dict[str, tuple] = {
    "ad_copy":      (PipelineStage.AD_COPY, run_ad_copy),
    "video_script": (PipelineStage.VIDEO_SCRIPT, run_video_script),
    "ugc_brief":    (PipelineStage.UGC_BRIEF, run_ugc_brief),
    "email_zalo":   (PipelineStage.EMAIL_ZALO, run_email_zalo),
}

TIER3_PROGRESS_MESSAGES = {
    "ad_copy":      "✍️ Đang viết Ad Copy...",
    "video_script": "🎬 Đang viết Video Script...",
    "ugc_brief":    "📝 Đang soạn UGC Creator Brief...",
    "email_zalo":   "📧 Đang thiết kế chuỗi Email & Zalo...",
}


async def run_tier3_pipeline(
    session: Session,
    content_types: list[str],
    progress_callback=None,
) -> AsyncGenerator[tuple[str, str], None]:
    if "campaign_brief" not in session.results:
        yield "error", "⚠️ Cần hoàn thành Campaign Brief (Tier 2) trước khi sản xuất nội dung."
        return

    session.current_tier = 3

    valid_types = [ct for ct in content_types if ct in TIER3_RUNNERS]
    if not valid_types:
        yield "error", f"⚠️ Không tìm thấy loại content hợp lệ. Chọn từ: {', '.join(TIER3_RUNNERS.keys())}"
        return

    for content_type in valid_types:
        stage_enum, stage_fn = TIER3_RUNNERS[content_type]
        session.stage = stage_enum

        if progress_callback and content_type in TIER3_PROGRESS_MESSAGES:
            await progress_callback(TIER3_PROGRESS_MESSAGES[content_type])

        try:
            result = await asyncio.wait_for(
                stage_fn(session),
                timeout=AGENT_TIMEOUT,
            )
            yield content_type, result
        except asyncio.TimeoutError:
            yield content_type, f"⚠️ Bước {content_type} mất quá nhiều thời gian. Bỏ qua và tiếp tục..."
        except Exception as e:
            yield content_type, f"⚠️ Lỗi ở bước {content_type}: {str(e)[:200]}"

    session.stage = PipelineStage.TIER3_COMPLETE
