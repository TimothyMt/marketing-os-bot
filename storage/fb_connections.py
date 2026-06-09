"""CRUD cho user_fb_connections (token + available accounts),
user_ads_subscriptions (digest settings per ad account),
oauth_states, ads_snapshots, ads_alert_cooldowns.

Sau migration 011: 1 user có nhiều subscription cho nhiều ad account, mỗi sub
có notify_time/tracked_metrics/alert thresholds riêng. user_fb_connections
chỉ giữ token + active ad_account_id (cho live tasks như /ads_analytics).
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


# ─── Helpers ────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _client():
    from storage import session as _session_mod
    return _session_mod._client


DEFAULT_NOTIFY_TIME    = "08:00"
DEFAULT_TRACKED_METRICS = ["spend", "roas", "cpl", "frequency"]


# ─── user_fb_connections (token + active account) ───────────────

async def save_connection(
    user_id: int,
    encrypted_token: str,
    ad_account_id: str,
    account_name: str,
    expires_at: datetime,
    available_accounts: list | None = None,
) -> None:
    """Lưu OAuth token + active ad account. Tự động tạo subscription mặc định
    cho ad_account_id vừa pick (để user nhận daily digest ngay mà không cần
    setup thêm)."""
    import json
    client = _client()
    if client is None:
        logger.warning("save_connection: client not init")
        return
    payload = {
        "user_id":          user_id,
        "encrypted_token":  encrypted_token,
        "ad_account_id":    ad_account_id,
        "account_name":     account_name,
        "expires_at":       expires_at.isoformat(),
        "connected_at":     _now().isoformat(),
    }
    if available_accounts is not None:
        payload["available_accounts"] = json.dumps([
            {
                "id":     (a.get("id") or a.get("account_id") or ""),
                "name":   a.get("name") or "",
                "status": a.get("account_status"),
            }
            for a in available_accounts
        ])
    await client.table("user_fb_connections").upsert(payload, on_conflict="user_id").execute()

    # Tạo subscription mặc định cho account vừa pick — chỉ insert nếu chưa có,
    # giữ nguyên settings cũ nếu user đã từng subscribe rồi (vd reconnect).
    await client.table("user_ads_subscriptions").upsert(
        {
            "user_id":              user_id,
            "ad_account_id":        ad_account_id,
            "account_name":         account_name,
            "notification_enabled": True,
            "notify_time":          DEFAULT_NOTIFY_TIME,
            "tracked_metrics":      DEFAULT_TRACKED_METRICS,
        },
        on_conflict="user_id,ad_account_id",
        ignore_duplicates=True,
    ).execute()


async def update_active_account(user_id: int, account_id: str, account_name: str) -> None:
    """Đổi active Ad Account dùng cho live tasks (/ads_analytics, /ads_optimizer).
    KHÔNG tự động tạo subscription — sub chỉ tạo qua /ads_settings → Thêm account."""
    client = _client()
    if client is None:
        return
    await client.table("user_fb_connections").update({
        "ad_account_id": account_id,
        "account_name":  account_name,
    }).eq("user_id", user_id).execute()


async def get_available_accounts(user_id: int) -> list[dict]:
    """Trả list accounts đã lưu lúc OAuth: [{'id': 'act_...', 'name': '...', 'status': 1}]."""
    import json
    conn = await get_connection(user_id)
    if not conn:
        return []
    raw = conn.get("available_accounts")
    if not raw:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return []
    return raw if isinstance(raw, list) else []


async def get_connection(user_id: int) -> Optional[dict]:
    """Trả connection (token + active account). KHÔNG có digest settings —
    cho digest settings dùng get_subscription(user_id, ad_account_id)."""
    client = _client()
    if client is None:
        return None
    res = (
        await client.table("user_fb_connections")
        .select("*").eq("user_id", user_id).limit(1).execute()
    )
    return res.data[0] if res.data else None


async def update_token(user_id: int, encrypted_token: str, expires_at: datetime) -> None:
    client = _client()
    if client is None:
        return
    await client.table("user_fb_connections").update({
        "encrypted_token": encrypted_token,
        "expires_at":      expires_at.isoformat(),
    }).eq("user_id", user_id).execute()


async def delete_connection(user_id: int) -> None:
    """Xóa token + tất cả subscriptions của user (ON DELETE CASCADE)."""
    client = _client()
    if client is None:
        return
    await client.table("user_fb_connections").delete().eq("user_id", user_id).execute()


async def disable_connection(user_id: int) -> None:
    """Token revoked — tắt tất cả subscriptions, không xóa token/settings."""
    client = _client()
    if client is None:
        return
    await client.table("user_ads_subscriptions").update({
        "notification_enabled": False,
    }).eq("user_id", user_id).execute()


# ─── user_ads_subscriptions (digest settings per account) ───────

async def list_subscriptions(user_id: int) -> list[dict]:
    """Trả tất cả subs của user (mọi account, kể cả tắt notification)."""
    client = _client()
    if client is None:
        return []
    res = (
        await client.table("user_ads_subscriptions")
        .select("*").eq("user_id", user_id).order("ad_account_id").execute()
    )
    return res.data or []


async def get_subscription(user_id: int, ad_account_id: str) -> Optional[dict]:
    client = _client()
    if client is None:
        return None
    res = (
        await client.table("user_ads_subscriptions")
        .select("*")
        .eq("user_id", user_id)
        .eq("ad_account_id", ad_account_id)
        .limit(1).execute()
    )
    return res.data[0] if res.data else None


async def upsert_subscription(
    user_id: int,
    ad_account_id: str,
    account_name: Optional[str] = None,
    **fields,
) -> None:
    """Tạo hoặc update sub. Các trường được phép trong **fields:
    notification_enabled, notify_time, tracked_metrics,
    alert_frequency_max, alert_roas_drop_pct, alert_cpm_spike_pct, last_pull_at.
    """
    allowed = {
        "notification_enabled", "notify_time", "tracked_metrics",
        "alert_frequency_max", "alert_roas_drop_pct", "alert_cpm_spike_pct",
        "last_pull_at",
    }
    payload = {
        "user_id":       user_id,
        "ad_account_id": ad_account_id,
    }
    if account_name is not None:
        payload["account_name"] = account_name
    for k, v in fields.items():
        if k in allowed:
            payload[k] = v
    client = _client()
    if client is None:
        return
    await client.table("user_ads_subscriptions").upsert(
        payload, on_conflict="user_id,ad_account_id"
    ).execute()


async def delete_subscription(user_id: int, ad_account_id: str) -> None:
    client = _client()
    if client is None:
        return
    await client.table("user_ads_subscriptions").delete().eq(
        "user_id", user_id
    ).eq("ad_account_id", ad_account_id).execute()


async def get_active_subscriptions_with_token() -> list[dict]:
    """Tất cả sub đang bật notification, kèm encrypted_token từ user_fb_connections.

    Trả list dict đã merge — mỗi item có token + ad_account_id của sub + settings:
        {user_id, encrypted_token, expires_at,
         ad_account_id, account_name, notify_time, tracked_metrics, alert_*, ...}

    Dùng cho scheduler tick (lọc theo notify_time tiếp ở Python-side) và
    alert monitor (chạy mỗi 4h cho TẤT CẢ sub đang bật).
    """
    client = _client()
    if client is None:
        return []
    # Supabase Python client chưa hỗ trợ JOIN trực tiếp — query 2 lần rồi merge in-memory.
    subs_res = (
        await client.table("user_ads_subscriptions")
        .select("*").eq("notification_enabled", True).execute()
    )
    subs = subs_res.data or []
    if not subs:
        return []

    user_ids = list({s["user_id"] for s in subs})
    conn_res = (
        await client.table("user_fb_connections")
        .select("user_id,encrypted_token,expires_at")
        .in_("user_id", user_ids).execute()
    )
    conn_by_uid = {c["user_id"]: c for c in (conn_res.data or [])}

    merged = []
    for s in subs:
        c = conn_by_uid.get(s["user_id"])
        if not c:
            continue  # connection bị xóa nhưng sub còn → skip (ON DELETE CASCADE thường lo, fail-safe)
        merged.append({**s, "encrypted_token": c["encrypted_token"], "expires_at": c.get("expires_at")})
    return merged


# ─── oauth_states ───────────────────────────────────────────────

async def save_oauth_state(state_token: str, user_id: int) -> None:
    client = _client()
    if client is None:
        return
    expires = _now() + timedelta(minutes=15)
    await client.table("oauth_states").upsert({
        "state_token": state_token,
        "user_id":     user_id,
        "expires_at":  expires.isoformat(),
    }).execute()


async def consume_oauth_state(state_token: str) -> Optional[int]:
    """Validate + delete state (one-use). Returns user_id or None nếu invalid/expired."""
    client = _client()
    if client is None:
        return None
    res = (
        await client.table("oauth_states")
        .select("*").eq("state_token", state_token).limit(1).execute()
    )
    if not res.data:
        return None
    row = res.data[0]
    await client.table("oauth_states").delete().eq("state_token", state_token).execute()
    expires = datetime.fromisoformat(row["expires_at"])
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if _now() > expires:
        return None
    return row["user_id"]


# ─── ads_snapshots ──────────────────────────────────────────────

def compute_campaign_metrics(c: dict) -> dict:
    """Tính các metric derived (roas/cpl/vtr_3s/...) từ 1 raw insight row của FB
    (đã pull kèm extra_fields=['campaign_id','action_values']).

    Dùng chung cho save_snapshot (lưu DB) và các chỗ cần xem nhanh không lưu
    (vd Báo Cáo Nhanh) — đảm bảo cách tính nhất quán ở mọi nơi.
    """
    spend = float(c.get("spend") or 0)
    impressions = float(c.get("impressions") or 0)
    leads = _extract_action(c, "lead")
    purchases = _extract_action(c, "purchase")
    purchase_value = _extract_action_value(c, "purchase")
    video_3s = _extract_action(c, "video_view")
    return {
        "campaign_id":    c.get("campaign_id") or c.get("campaign_name") or "unknown",
        "campaign_name":  c.get("campaign_name") or "Unknown",
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
    }


async def save_snapshot(
    user_id: int,
    ad_account_id: str,
    date: datetime,
    campaigns: list[dict],
) -> list[dict]:
    """Lưu snapshot ngày `date` cho (user, ad_account). campaigns = list từ
    fb_marketing.py (đã pull kèm extra_fields=['campaign_id','action_values']).

    Returns rows đã compute (roas/cpl/vtr_3s) — cùng shape với data đọc từ DB,
    để delta nhất quán.
    """
    client = _client()
    date_str = date.strftime("%Y-%m-%d")
    rows = [
        {
            "user_id":       user_id,
            "ad_account_id": ad_account_id,
            "snapshot_date": date_str,
            **compute_campaign_metrics(c),
        }
        for c in campaigns
    ]
    if rows and client is not None:
        await client.table("ads_snapshots").upsert(
            rows, on_conflict="user_id,ad_account_id,snapshot_date,campaign_id"
        ).execute()
    return rows


def _extract_action(campaign: dict, action_type: str) -> float:
    actions = campaign.get("actions") or []
    for a in actions:
        if a.get("action_type") == action_type:
            return float(a.get("value") or 0)
    return 0.0


def _extract_action_value(campaign: dict, action_type: str) -> float:
    values = campaign.get("action_values") or []
    if isinstance(values, list):
        for a in values:
            if a.get("action_type") == action_type:
                return float(a.get("value") or 0)
    return 0.0


async def get_snapshot(user_id: int, ad_account_id: str, date: datetime) -> list[dict]:
    client = _client()
    if client is None:
        return []
    date_str = date.strftime("%Y-%m-%d")
    res = (
        await client.table("ads_snapshots")
        .select("*")
        .eq("user_id", user_id)
        .eq("ad_account_id", ad_account_id)
        .eq("snapshot_date", date_str)
        .execute()
    )
    return res.data or []


async def get_snapshots_range(
    user_id: int,
    ad_account_id: str,
    start: datetime,
    end: datetime,
) -> list[dict]:
    """Snapshots trong khoảng ngày (inclusive) cho 1 ad account cụ thể."""
    client = _client()
    if client is None:
        return []
    res = (
        await client.table("ads_snapshots")
        .select("*")
        .eq("user_id", user_id)
        .eq("ad_account_id", ad_account_id)
        .gte("snapshot_date", start.strftime("%Y-%m-%d"))
        .lte("snapshot_date", end.strftime("%Y-%m-%d"))
        .execute()
    )
    return res.data or []


async def cleanup_old_snapshots() -> int:
    """Xóa snapshots > 90 ngày. Returns số rows deleted."""
    client = _client()
    if client is None:
        return 0
    cutoff = (_now() - timedelta(days=90)).strftime("%Y-%m-%d")
    res = await client.table("ads_snapshots").delete().lt("snapshot_date", cutoff).execute()
    return len(res.data or [])


# ─── ads_alert_cooldowns ────────────────────────────────────────

async def check_and_set_cooldown(
    user_id: int,
    ad_account_id: str,
    campaign_id: str,
    alert_type: str,
) -> bool:
    """Returns True nếu alert có thể gửi (cooldown chưa active).
    Nếu True → tự động set cooldown 24h. Cooldown scope theo (user, account, campaign, type)."""
    client = _client()
    if client is None:
        return False
    res = (
        await client.table("ads_alert_cooldowns")
        .select("last_sent_at")
        .eq("user_id", user_id)
        .eq("ad_account_id", ad_account_id)
        .eq("campaign_id", campaign_id)
        .eq("alert_type", alert_type)
        .limit(1)
        .execute()
    )
    if res.data:
        last = datetime.fromisoformat(res.data[0]["last_sent_at"])
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if _now() - last < timedelta(hours=24):
            return False  # còn trong cooldown
    await client.table("ads_alert_cooldowns").upsert({
        "user_id":       user_id,
        "ad_account_id": ad_account_id,
        "campaign_id":   campaign_id,
        "alert_type":    alert_type,
        "last_sent_at":  _now().isoformat(),
    }, on_conflict="user_id,ad_account_id,campaign_id,alert_type").execute()
    return True
