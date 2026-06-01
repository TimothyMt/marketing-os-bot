"""Ads Scheduler — chạy 2 jobs nền:

Job A — Daily Digest:  8:00 AM Asia/Ho_Chi_Minh mỗi ngày
Job B — Alert Monitor: mỗi 4 tiếng, check thresholds
Job C — Weekly Report: mỗi thứ Hai 8:00 AM (gửi thay vì Daily Digest)
Job D — Token Refresh: mỗi ngày, refresh token gần hết hạn
Job E — Snapshot Cleanup: mỗi tuần, xóa snapshots > 90 ngày

Tích hợp: gọi start_ads_scheduler(bot) từ post_init trong main.py.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta, date

logger = logging.getLogger(__name__)


async def start_ads_scheduler(bot) -> None:
    """Entry point — chạy vô tận dưới dạng asyncio task."""
    logger.info("[AdsScheduler] Starting background scheduler")
    while True:
        try:
            await _tick(bot)
        except Exception as e:
            logger.error("[AdsScheduler] tick error: %s", e)
        await asyncio.sleep(60)  # check mỗi phút


async def _tick(bot) -> None:
    """Gọi mỗi phút — quyết định job nào cần chạy."""
    now_utc = datetime.now(timezone.utc)
    # Convert sang Asia/Ho_Chi_Minh (UTC+7)
    now_vn = now_utc + timedelta(hours=7)
    hour, minute, weekday = now_vn.hour, now_vn.minute, now_vn.weekday()  # 0=Mon

    # Job A/C: Daily/Weekly digest — chạy lúc 8:00 (minute=0 để không chạy 8:01, 8:02...)
    if hour == 8 and minute == 0:
        if weekday == 0:  # Thứ Hai → weekly report
            asyncio.create_task(_run_weekly_report(bot))
        else:
            asyncio.create_task(_run_daily_digest(bot))

    # Job B: Alert monitor — mỗi 4 tiếng (0h, 4h, 8h, 12h, 16h, 20h)
    if hour % 4 == 0 and minute == 0:
        asyncio.create_task(_run_alert_monitor(bot))

    # Job D: Token refresh — mỗi ngày lúc 2:00
    if hour == 2 and minute == 0:
        asyncio.create_task(_run_token_refresh(bot))

    # Job E: Snapshot cleanup — mỗi Chủ Nhật lúc 3:00
    if weekday == 6 and hour == 3 and minute == 0:
        asyncio.create_task(_run_cleanup())


# ── Job A: Daily Digest ──────────────────────────────────────────

async def _run_daily_digest(bot) -> None:
    from storage.fb_connections import get_all_active_connections, get_snapshot
    from services.ads_notifier import pull_and_snapshot, compute_delta, format_daily_digest, send_message_safe

    logger.info("[AdsScheduler] Running daily digest")
    connections = await get_all_active_connections()

    for conn in connections:
        user_id      = conn["user_id"]
        account_name = conn.get("account_name") or "Ads Account"
        try:
            today_campaigns = await pull_and_snapshot(conn)

            # Lấy snapshot hôm qua để tính delta
            yesterday = datetime.now(timezone.utc) - timedelta(days=1)
            prev_rows = await get_snapshot(user_id, yesterday)

            delta = compute_delta(today_campaigns, prev_rows)
            text  = format_daily_digest(today_campaigns, delta, conn, account_name)
            await send_message_safe(bot, user_id, text)

        except Exception as e:
            logger.warning("[AdsScheduler] daily digest failed user=%d: %s", user_id, e)
            if "401" in str(e) or "190" in str(e) or "Invalid OAuth" in str(e):
                await _handle_token_revoked(bot, conn)


# ── Job C: Weekly Report ─────────────────────────────────────────

async def _run_weekly_report(bot) -> None:
    from storage.fb_connections import get_all_active_connections, get_snapshots_range
    from services.ads_notifier import pull_and_snapshot, format_weekly_digest, send_message_safe

    logger.info("[AdsScheduler] Running weekly report (Monday)")
    connections = await get_all_active_connections()
    today = date.today()

    for conn in connections:
        user_id      = conn["user_id"]
        account_name = conn.get("account_name") or "Ads Account"
        try:
            this_week_campaigns = await pull_and_snapshot(conn)

            # Snapshot 7 ngày vừa rồi vs 7 ngày trước đó
            this_week_start = datetime.combine(today - timedelta(days=6), datetime.min.time()).replace(tzinfo=timezone.utc)
            this_week_end   = datetime.now(timezone.utc)
            prev_week_start = this_week_start - timedelta(days=7)
            prev_week_end   = this_week_start - timedelta(seconds=1)

            this_rows = await get_snapshots_range(user_id, this_week_start, this_week_end)
            prev_rows = await get_snapshots_range(user_id, prev_week_start, prev_week_end)

            text = format_weekly_digest(this_rows, prev_rows, conn, account_name)
            await send_message_safe(bot, user_id, text)

        except Exception as e:
            logger.warning("[AdsScheduler] weekly report failed user=%d: %s", user_id, e)
            if "401" in str(e) or "190" in str(e):
                await _handle_token_revoked(bot, conn)


# ── Job B: Alert Monitor ─────────────────────────────────────────

async def _run_alert_monitor(bot) -> None:
    from storage.fb_connections import get_all_active_connections, get_snapshot
    from services.ads_notifier import pull_and_snapshot, check_alerts, format_alert, send_message_safe

    logger.info("[AdsScheduler] Running alert monitor")
    connections = await get_all_active_connections()

    for conn in connections:
        user_id      = conn["user_id"]
        account_name = conn.get("account_name") or "Ads Account"
        try:
            today_campaigns = await pull_and_snapshot(conn)
            yesterday = datetime.now(timezone.utc) - timedelta(days=1)
            prev_rows = await get_snapshot(user_id, yesterday)

            alerts = await check_alerts(today_campaigns, prev_rows, conn)
            for alert in alerts:
                text = format_alert(alert, account_name)
                await send_message_safe(bot, user_id, text)

        except Exception as e:
            logger.warning("[AdsScheduler] alert monitor failed user=%d: %s", user_id, e)


# ── Job D: Token Refresh ─────────────────────────────────────────

async def _run_token_refresh(bot) -> None:
    from storage.fb_connections import get_all_active_connections
    from services.fb_oauth import refresh_token_if_needed

    logger.info("[AdsScheduler] Running token refresh check")
    connections = await get_all_active_connections()
    for conn in connections:
        user_id = conn["user_id"]
        try:
            still_valid = await refresh_token_if_needed(user_id)
            if not still_valid:
                await _handle_token_revoked(bot, conn)
        except Exception as e:
            logger.warning("[AdsScheduler] token refresh failed user=%d: %s", user_id, e)


# ── Job E: Snapshot Cleanup ──────────────────────────────────────

async def _run_cleanup() -> None:
    from storage.fb_connections import cleanup_old_snapshots
    deleted = await cleanup_old_snapshots()
    logger.info("[AdsScheduler] Snapshot cleanup: deleted %d rows > 90 days", deleted)


# ── Token revoked handler ────────────────────────────────────────

async def _handle_token_revoked(bot, conn: dict) -> None:
    from storage.fb_connections import disable_connection
    from services.ads_notifier import send_message_safe

    user_id = conn["user_id"]
    await disable_connection(user_id)
    await send_message_safe(
        bot, user_id,
        "⚠️ *Kết nối Facebook Ads đã ngắt*\n\n"
        "Token hết hạn hoặc quyền bị thu hồi.\n"
        "Gõ /connect\\_ads để kết nối lại — settings cũ vẫn giữ nguyên."
    )
    logger.info("[AdsScheduler] Token revoked, disabled connection for user=%d", user_id)
