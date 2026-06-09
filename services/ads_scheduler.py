"""Ads Scheduler — chạy background jobs cho ads digest + alert + maintenance.

Job A — Daily Digest:  Theo notify_time của từng subscription (preset: 06/07/08/09/10/12h VN)
Job B — Alert Monitor: Mỗi 4 tiếng, check thresholds cho TẤT CẢ sub đang bật
Job C — Weekly Report: Thứ Hai cùng khung giờ với daily digest (thay vì daily)
Job D — Token Refresh: Mỗi ngày 2h, refresh token gần hết hạn
Job E — Snapshot Cleanup: Chủ Nhật 3h, xóa snapshots > 90 ngày
Job F — Snapshot Backfill: chạy 1 lần lúc khởi động, sửa snapshot lịch sử bị nhiễm

Tích hợp: gọi start_ads_scheduler(bot) từ post_init trong main.py.

Sau migration 011: 1 user có nhiều subscription (nhiều ad account), mỗi sub có
notify_time riêng → scheduler loop per-subscription, không phải per-user.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta, date

logger = logging.getLogger(__name__)


# Dedup guard — đảm bảo mỗi job fire đúng 1 lần/khung giờ (sleep có thể drift).
# Key = job:identifier, value = slot key đã chạy.
_last_fired: dict[str, str] = {}


def _should_fire(job_key: str, slot_key: str) -> bool:
    """True nếu job chưa chạy ở slot này. Đánh dấu đã chạy."""
    if _last_fired.get(job_key) == slot_key:
        return False
    _last_fired[job_key] = slot_key
    return True


def _vn_now() -> datetime:
    """Giờ VN (UTC+7). Hard-code timezone vì sản phẩm VN-only — sếp đã chốt."""
    return datetime.now(timezone.utc) + timedelta(hours=7)


async def start_ads_scheduler(bot) -> None:
    """Entry point — chạy vô tận dưới dạng asyncio task."""
    logger.info("[AdsScheduler] Starting background scheduler")
    asyncio.create_task(_run_snapshot_backfill())
    while True:
        try:
            await _tick(bot)
        except Exception as e:
            logger.error("[AdsScheduler] tick error: %s", e)
        await asyncio.sleep(30)  # check mỗi 30s — bắt khung giờ HH:MM chính xác hơn


async def _tick(bot) -> None:
    """Gọi định kỳ — quyết định job nào cần chạy. Dùng _should_fire chống double-fire."""
    from storage.fb_connections import get_active_subscriptions_with_token

    now_vn   = _vn_now()
    hour     = now_vn.hour
    weekday  = now_vn.weekday()  # 0=Mon
    hhmm     = now_vn.strftime("%H:%M")
    day_key  = now_vn.strftime("%Y-%m-%d")
    hour_key = now_vn.strftime("%Y-%m-%d-%H")

    # Job A/C: per-subscription digest theo notify_time
    # Chỉ query DB khi có khả năng có sub fire (mỗi phút đầu của 1 giờ tròn —
    # vì notify_time preset chỉ có dạng "HH:00")
    if now_vn.minute < 2:
        subs = await get_active_subscriptions_with_token()
        for sub in subs:
            if sub.get("notify_time") != hhmm:
                continue
            slot = f"{sub['user_id']}:{sub['ad_account_id']}:{day_key}"
            if not _should_fire(f"digest:{slot}", slot):
                continue
            if weekday == 0:  # Thứ Hai → weekly report
                asyncio.create_task(_run_weekly_report_one(bot, sub))
            else:
                asyncio.create_task(_run_daily_digest_one(bot, sub))

    # Job B: Alert monitor — mỗi 4 tiếng (0,4,8,12,16,20h), 1 lần/khung giờ, TẤT CẢ sub
    if hour % 4 == 0 and now_vn.minute < 2 and _should_fire("alert", hour_key):
        asyncio.create_task(_run_alert_monitor(bot))

    # Job D: Token refresh — 2:00 (1 lần/ngày)
    if hour == 2 and now_vn.minute < 2 and _should_fire("refresh", day_key):
        asyncio.create_task(_run_token_refresh(bot))

    # Job E: Snapshot cleanup — Chủ Nhật 3:00 (1 lần/ngày)
    if weekday == 6 and hour == 3 and now_vn.minute < 2 and _should_fire("cleanup", day_key):
        asyncio.create_task(_run_cleanup())


# ── Job A: Daily Digest (per-subscription) ───────────────────────

async def _run_daily_digest_one(bot, sub: dict) -> None:
    from storage.fb_connections import get_snapshot
    from services.ads_notifier import pull_and_snapshot, compute_delta, format_daily_digest, send_message_safe

    user_id       = sub["user_id"]
    ad_account_id = sub["ad_account_id"]
    account_name  = _safe_name(sub.get("account_name") or ad_account_id)

    logger.info("[AdsScheduler] Running daily digest user=%d account=%s", user_id, ad_account_id)
    try:
        yesterday_campaigns, report_date = await pull_and_snapshot(sub)

        day_before = report_date - timedelta(days=1)
        prev_rows  = await get_snapshot(user_id, ad_account_id, day_before)

        delta = compute_delta(yesterday_campaigns, prev_rows)
        text  = format_daily_digest(yesterday_campaigns, delta, sub, account_name, report_date=report_date)
        await send_message_safe(bot, user_id, text)

    except Exception as e:
        logger.warning("[AdsScheduler] daily digest failed user=%d account=%s: %s",
                       user_id, ad_account_id, e)
        if "401" in str(e) or "190" in str(e) or "Invalid OAuth" in str(e):
            await _handle_token_revoked(bot, sub)


# ── Job C: Weekly Report (per-subscription, Monday) ──────────────

async def _run_weekly_report_one(bot, sub: dict) -> None:
    from storage.fb_connections import get_snapshots_range
    from services.ads_notifier import pull_and_snapshot, format_weekly_digest, send_message_safe

    user_id       = sub["user_id"]
    ad_account_id = sub["ad_account_id"]
    account_name  = _safe_name(sub.get("account_name") or ad_account_id)

    logger.info("[AdsScheduler] Running weekly report user=%d account=%s", user_id, ad_account_id)
    try:
        await pull_and_snapshot(sub)  # đảm bảo snapshot hôm qua đã có trước khi query range

        today = date.today()
        this_week_start = datetime.combine(today - timedelta(days=6), datetime.min.time()).replace(tzinfo=timezone.utc)
        this_week_end   = datetime.now(timezone.utc)
        prev_week_start = this_week_start - timedelta(days=7)
        prev_week_end   = this_week_start - timedelta(seconds=1)

        this_rows = await get_snapshots_range(user_id, ad_account_id, this_week_start, this_week_end)
        prev_rows = await get_snapshots_range(user_id, ad_account_id, prev_week_start, prev_week_end)

        text = format_weekly_digest(this_rows, prev_rows, sub, account_name)
        await send_message_safe(bot, user_id, text)

    except Exception as e:
        logger.warning("[AdsScheduler] weekly report failed user=%d account=%s: %s",
                       user_id, ad_account_id, e)
        if "401" in str(e) or "190" in str(e):
            await _handle_token_revoked(bot, sub)


# ── Job B: Alert Monitor (all active subs) ───────────────────────

async def _run_alert_monitor(bot) -> None:
    from storage.fb_connections import get_active_subscriptions_with_token, get_snapshot
    from services.ads_notifier import pull_and_snapshot, check_alerts, format_alert, send_message_safe

    logger.info("[AdsScheduler] Running alert monitor")
    subs = await get_active_subscriptions_with_token()

    for sub in subs:
        user_id       = sub["user_id"]
        ad_account_id = sub["ad_account_id"]
        account_name  = _safe_name(sub.get("account_name") or ad_account_id)
        try:
            yesterday_campaigns, report_date = await pull_and_snapshot(sub)
            day_before = report_date - timedelta(days=1)
            prev_rows  = await get_snapshot(user_id, ad_account_id, day_before)

            alerts = await check_alerts(yesterday_campaigns, prev_rows, sub)
            for alert in alerts:
                text = format_alert(alert, account_name)
                await send_message_safe(bot, user_id, text)

        except Exception as e:
            logger.warning("[AdsScheduler] alert monitor failed user=%d account=%s: %s",
                           user_id, ad_account_id, e)


# ── Job D: Token Refresh ─────────────────────────────────────────

async def _run_token_refresh(bot) -> None:
    """Refresh token cho tất cả connection có sub đang active."""
    from storage.fb_connections import get_active_subscriptions_with_token
    from services.fb_oauth import refresh_token_if_needed

    logger.info("[AdsScheduler] Running token refresh check")
    subs = await get_active_subscriptions_with_token()
    seen_users = set()
    for sub in subs:
        user_id = sub["user_id"]
        if user_id in seen_users:
            continue  # 1 user N sub → refresh token 1 lần
        seen_users.add(user_id)
        try:
            still_valid = await refresh_token_if_needed(user_id)
            if not still_valid:
                await _handle_token_revoked(bot, sub)
        except Exception as e:
            logger.warning("[AdsScheduler] token refresh failed user=%d: %s", user_id, e)


# ── One-time: Snapshot Backfill/Repair ───────────────────────────

async def _run_snapshot_backfill() -> None:
    """Chạy 1 lần khi scheduler khởi động — sửa snapshot lịch sử bị nhiễm bởi
    bug cũ (pull date_preset="last_7d" nhưng lưu/nhãn như 1 ngày → mỗi snapshot
    chứa tổng cumulative 7-ngày thay vì số liệu thực của ngày đó).

    Backfill cho TẤT CẢ subscription đang active (multi-account). Idempotent:
    chạy lại chỉ ghi đè bằng đúng số liệu closed-day, không gây sai lệch thêm.
    """
    from storage.fb_connections import get_active_subscriptions_with_token
    from services.ads_notifier import backfill_snapshots

    logger.info("[AdsScheduler] Running one-time snapshot backfill/repair")
    subs = await get_active_subscriptions_with_token()
    for sub in subs:
        user_id       = sub["user_id"]
        ad_account_id = sub["ad_account_id"]
        try:
            n = await backfill_snapshots(sub, days=9)
            logger.info("[AdsScheduler] Backfill: repaired %d days user=%d account=%s",
                        n, user_id, ad_account_id)
        except Exception as e:
            logger.warning("[AdsScheduler] snapshot backfill failed user=%d account=%s: %s",
                           user_id, ad_account_id, e)


# ── Job E: Snapshot Cleanup ──────────────────────────────────────

async def _run_cleanup() -> None:
    from storage.fb_connections import cleanup_old_snapshots
    deleted = await cleanup_old_snapshots()
    logger.info("[AdsScheduler] Snapshot cleanup: deleted %d rows > 90 days", deleted)


# ── Token revoked handler ────────────────────────────────────────

async def _handle_token_revoked(bot, sub: dict) -> None:
    """Tắt tất cả subscription của user (token chung) và thông báo."""
    from storage.fb_connections import disable_connection
    from services.ads_notifier import send_message_safe

    user_id = sub["user_id"]
    await disable_connection(user_id)
    await send_message_safe(
        bot, user_id,
        "⚠️ *Kết nối Facebook Ads đã ngắt*\n\n"
        "Token hết hạn hoặc quyền bị thu hồi.\n"
        "Gõ `/connect_ads` để kết nối lại — settings cũ vẫn giữ nguyên."
    )
    logger.info("[AdsScheduler] Token revoked, disabled subs for user=%d", user_id)


# ── Helpers ──────────────────────────────────────────────────────

def _safe_name(name: str) -> str:
    """Sanitize tên account để dùng trong Markdown — tránh phá entity."""
    return str(name).replace("*", "").replace("_", "-").replace("`", "'").replace("[", "(").replace("]", ")")
