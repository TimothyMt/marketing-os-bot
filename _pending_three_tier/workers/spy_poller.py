"""Spy Radar poller logic.

poll_spy_target()     — fetch + analyze one target, write to spy_cache
run_spy_poll_cycle()  — called by APScheduler (spy_worker.py)
dispatch_pending_alerts() — read spy_cache, push Telegram alerts
                            called from bot JobQueue (Service #1) every 2 min
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

import anthropic

from config import ANTHROPIC_API_KEY, CLAUDE_HAIKU_MODEL

logger = logging.getLogger(__name__)

_SPY_ANALYZER_SYSTEM = """Bạn là Spy Analyzer — phân tích quảng cáo đối thủ trên Facebook.

Khi nhận snapshot ads của một fanpage:
1. Liệt kê 3–5 patterns copy nổi bật (hook, offer, CTA)
2. Nhận xét funnel mix: TOFU/MOFU/BOFU
3. Phát hiện angle mới hoặc thay đổi
4. Output ≤ 400 từ, bullet points

Nếu không có ads: "Không có quảng cáo mới từ [fanpage] trong kỳ này."
Không bịa số liệu — chỉ phân tích data trong snapshot."""


async def poll_spy_target(target) -> None:
    """Fetch page ads via Meta MCP, analyze with Haiku, write snapshot to DB."""
    from storage.spy_store import save_spy_snapshot

    try:
        from tier3.mcp_client import get_page_ads

        snapshot = await get_page_ads(target.fanpage_url)
    except ImportError:
        logger.warning("mcp not installed — spy poll skipped for %s", target.fanpage_url)
        return
    except Exception as e:
        logger.error("MCP fetch failed for %s: %s", target.fanpage_url, e)
        return

    if not snapshot:
        logger.info("No ads for %s", target.fanpage_url)
        return

    try:
        client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        resp = await client.messages.create(
            model=CLAUDE_HAIKU_MODEL,
            max_tokens=600,
            system=_SPY_ANALYZER_SYSTEM,
            messages=[{
                "role": "user",
                "content": (
                    f"Fanpage: {target.label or target.fanpage_url}\n"
                    f"Snapshot:\n{json.dumps(snapshot[:20], ensure_ascii=False)}"
                ),
            }],
        )
        analysis = resp.content[0].text
    except Exception as e:
        logger.error("Haiku analysis failed for %s: %s", target.fanpage_url, e)
        analysis = f"[Lỗi phân tích: {e}]"

    await save_spy_snapshot(
        target.id,
        {"ads": snapshot, "fetched_at": datetime.utcnow().isoformat()},
        analysis,
    )
    logger.info("Snapshot saved for target %s (%s)", target.id, target.label or target.fanpage_url)


async def run_spy_poll_cycle() -> None:
    """Poll all targets that are due. Called by APScheduler in spy_worker."""
    from storage.spy_store import get_all_active_spy_targets

    targets = await get_all_active_spy_targets()
    now = datetime.utcnow()
    due = [
        t for t in targets
        if t.last_polled_at is None
        or (now - t.last_polled_at) >= timedelta(hours=t.poll_interval_h)
    ]
    logger.info("Poll cycle: %d active, %d due", len(targets), len(due))
    for target in due:
        await poll_spy_target(target)


async def dispatch_pending_alerts(bot) -> None:
    """Read unsent spy_cache rows and push to Telegram.

    Called from the bot JobQueue (Service #1) on a 2-minute interval.
    """
    from storage.spy_store import get_unsent_alerts, mark_alert_sent

    alerts = await get_unsent_alerts()
    for alert in alerts:
        spy_info = alert.get("spy_targets") or {}
        user_id = spy_info.get("user_id")
        label = spy_info.get("label") or spy_info.get("fanpage_url", "Đối thủ")
        analysis = alert.get("analysis", "")

        if not user_id or not analysis:
            continue

        date_str = (alert.get("created_at") or "")[:10]
        msg = (
            f"🕵️ *Spy Radar Alert*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 *Fanpage*: {label}\n\n"
            f"{analysis}\n\n"
            f"_Dữ liệu từ Meta — {date_str}_"
        )
        try:
            await bot.send_message(chat_id=user_id, text=msg, parse_mode="Markdown")
            await mark_alert_sent(alert["id"])
        except Exception as e:
            logger.error("Alert dispatch failed for user %s: %s", user_id, e)
