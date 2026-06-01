"""CRUD cho user_fb_connections, oauth_states, ads_snapshots, ads_alert_cooldowns."""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


# ─── Helpers ────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _db():
    from storage import get_db
    return get_db()


# ─── user_fb_connections ────────────────────────────────────────

async def save_connection(
    user_id: int,
    encrypted_token: str,
    ad_account_id: str,
    account_name: str,
    expires_at: datetime,
) -> None:
    db = await _db()
    db.table("user_fb_connections").upsert({
        "user_id":          user_id,
        "encrypted_token":  encrypted_token,
        "ad_account_id":    ad_account_id,
        "account_name":     account_name,
        "expires_at":       expires_at.isoformat(),
        "connected_at":     _now().isoformat(),
        "notification_enabled": True,
    }, on_conflict="user_id").execute()


async def get_connection(user_id: int) -> Optional[dict]:
    db = await _db()
    res = db.table("user_fb_connections").select("*").eq("user_id", user_id).maybe_single().execute()
    return res.data if res else None


async def get_all_active_connections() -> list[dict]:
    """Trả về tất cả kết nối đang active (notification_enabled=true)."""
    db = await _db()
    res = db.table("user_fb_connections").select("*").eq("notification_enabled", True).execute()
    return res.data or []


async def update_last_pull(user_id: int) -> None:
    db = await _db()
    db.table("user_fb_connections").update({
        "last_pull_at": _now().isoformat()
    }).eq("user_id", user_id).execute()


async def update_token(user_id: int, encrypted_token: str, expires_at: datetime) -> None:
    db = await _db()
    db.table("user_fb_connections").update({
        "encrypted_token": encrypted_token,
        "expires_at":      expires_at.isoformat(),
    }).eq("user_id", user_id).execute()


async def update_notification_settings(user_id: int, **kwargs) -> None:
    """Cập nhật: notification_enabled, notify_time, timezone, tracked_metrics, alert thresholds."""
    allowed = {
        "notification_enabled", "notify_time", "timezone",
        "tracked_metrics", "alert_frequency_max", "alert_roas_drop_pct", "alert_cpm_spike_pct",
    }
    payload = {k: v for k, v in kwargs.items() if k in allowed}
    if payload:
        db = await _db()
        db.table("user_fb_connections").update(payload).eq("user_id", user_id).execute()


async def delete_connection(user_id: int) -> None:
    db = await _db()
    db.table("user_fb_connections").delete().eq("user_id", user_id).execute()


async def disable_connection(user_id: int) -> None:
    """Token revoked — tắt notification, không xóa settings."""
    db = await _db()
    db.table("user_fb_connections").update({
        "notification_enabled": False
    }).eq("user_id", user_id).execute()


# ─── oauth_states ───────────────────────────────────────────────

async def save_oauth_state(state_token: str, user_id: int) -> None:
    db = await _db()
    expires = _now() + timedelta(minutes=15)
    db.table("oauth_states").upsert({
        "state_token": state_token,
        "user_id":     user_id,
        "expires_at":  expires.isoformat(),
    }).execute()


async def consume_oauth_state(state_token: str) -> Optional[int]:
    """Validate + delete state (one-use). Returns user_id or None nếu invalid/expired."""
    db = await _db()
    res = db.table("oauth_states").select("*").eq("state_token", state_token).maybe_single().execute()
    if not res or not res.data:
        return None
    row = res.data
    db.table("oauth_states").delete().eq("state_token", state_token).execute()
    expires = datetime.fromisoformat(row["expires_at"])
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if _now() > expires:
        return None
    return row["user_id"]


# ─── ads_snapshots ──────────────────────────────────────────────

async def save_snapshot(user_id: int, date: datetime, campaigns: list[dict]) -> None:
    """Lưu snapshot ngày hôm nay cho user. campaigns = list từ fb_marketing.py."""
    db = await _db()
    rows = []
    date_str = date.strftime("%Y-%m-%d")
    for c in campaigns:
        spend = float(c.get("spend") or 0)
        impressions = float(c.get("impressions") or 0)
        leads = _extract_action(c, "lead")
        purchases = _extract_action(c, "purchase")
        purchase_value = float(c.get("action_values", {}).get("purchase", 0) if isinstance(c.get("action_values"), dict) else 0)
        video_3s = _extract_action(c, "video_view")  # FB returns 3s view under video_view
        rows.append({
            "user_id":        user_id,
            "snapshot_date":  date_str,
            "campaign_id":    c.get("campaign_id") or c.get("id") or "unknown",
            "campaign_name":  c.get("campaign_name") or c.get("name") or "Unknown",
            "spend":          spend,
            "impressions":    impressions,
            "reach":          float(c.get("reach") or 0),
            "clicks":         float(c.get("clicks") or 0),
            "ctr":            float(c.get("ctr") or 0),
            "cpm":            float(c.get("cpm") or 0),
            "frequency":      float(c.get("frequency") or 0),
            "leads":          leads,
            "purchases":      purchases,
            "purchase_value": purchase_value,
            "video_views_3s": video_3s,
            "roas":           round(purchase_value / spend, 4) if spend > 0 else 0,
            "cpl":            round(spend / leads, 0) if leads > 0 else 0,
            "vtr_3s":         round(video_3s / impressions * 100, 2) if impressions > 0 else 0,
        })
    if rows:
        db.table("ads_snapshots").upsert(rows, on_conflict="user_id,snapshot_date,campaign_id").execute()


def _extract_action(campaign: dict, action_type: str) -> float:
    """Extract value từ FB API actions array."""
    actions = campaign.get("actions") or []
    for a in actions:
        if a.get("action_type") == action_type:
            return float(a.get("value") or 0)
    return 0.0


async def get_snapshot(user_id: int, date: datetime) -> list[dict]:
    db = await _db()
    date_str = date.strftime("%Y-%m-%d")
    res = db.table("ads_snapshots").select("*").eq("user_id", user_id).eq("snapshot_date", date_str).execute()
    return res.data or []


async def get_snapshots_range(user_id: int, start: datetime, end: datetime) -> list[dict]:
    """Lấy snapshots trong khoảng ngày (inclusive). Dùng cho weekly report."""
    db = await _db()
    res = (
        db.table("ads_snapshots")
        .select("*")
        .eq("user_id", user_id)
        .gte("snapshot_date", start.strftime("%Y-%m-%d"))
        .lte("snapshot_date", end.strftime("%Y-%m-%d"))
        .execute()
    )
    return res.data or []


async def cleanup_old_snapshots() -> int:
    """Xóa snapshots > 90 ngày. Returns số rows deleted."""
    cutoff = (_now() - timedelta(days=90)).strftime("%Y-%m-%d")
    db = await _db()
    res = db.table("ads_snapshots").delete().lt("snapshot_date", cutoff).execute()
    return len(res.data or [])


# ─── ads_alert_cooldowns ────────────────────────────────────────

async def check_and_set_cooldown(user_id: int, campaign_id: str, alert_type: str) -> bool:
    """Returns True nếu alert có thể gửi (cooldown chưa active).
    Nếu True → tự động set cooldown 24h."""
    db = await _db()
    res = (
        db.table("ads_alert_cooldowns")
        .select("last_sent_at")
        .eq("user_id", user_id)
        .eq("campaign_id", campaign_id)
        .eq("alert_type", alert_type)
        .maybe_single()
        .execute()
    )
    if res and res.data:
        last = datetime.fromisoformat(res.data["last_sent_at"])
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if _now() - last < timedelta(hours=24):
            return False  # còn trong cooldown
    # Set / update cooldown
    db.table("ads_alert_cooldowns").upsert({
        "user_id":      user_id,
        "campaign_id":  campaign_id,
        "alert_type":   alert_type,
        "last_sent_at": _now().isoformat(),
    }, on_conflict="user_id,campaign_id,alert_type").execute()
    return True
