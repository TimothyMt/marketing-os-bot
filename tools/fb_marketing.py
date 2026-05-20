"""
Facebook Marketing API wrapper.
Dùng cho skill "Báo Cáo Ads" (performance_audit) — pull data ads của sếp.

Docs: https://developers.facebook.com/docs/marketing-api/insights
Endpoint: GET /v20.0/act_{ad_account_id}/insights

Requires:
- FB_ACCESS_TOKEN với permissions: ads_read, read_insights
- FB_AD_ACCOUNT_ID: dạng "act_XXXXXXXXXX"
"""
import logging
from typing import Optional
import httpx

from config import FB_ACCESS_TOKEN, FB_AD_ACCOUNT_ID

logger = logging.getLogger(__name__)

FB_GRAPH_VERSION = "v20.0"
FB_BASE_URL = f"https://graph.facebook.com/{FB_GRAPH_VERSION}"

# Default insight fields để pull
DEFAULT_INSIGHT_FIELDS = [
    "campaign_name",
    "adset_name",
    "ad_name",
    "spend",
    "impressions",
    "reach",
    "clicks",
    "ctr",
    "cpc",
    "cpm",
    "cpp",
    "frequency",
    "actions",          # conversions, link_clicks, etc.
    "cost_per_action_type",
    "video_play_actions",
    "date_start",
    "date_stop",
]


# ─────────────────────────────────────────────────────────────────
# Ad Account Insights
# ─────────────────────────────────────────────────────────────────

async def get_account_insights(
    date_preset: str = "last_30d",
    level: str = "campaign",
    ad_account_id: Optional[str] = None,
    access_token: Optional[str] = None,
    extra_fields: Optional[list] = None,
) -> list[dict]:
    """Pull insights từ Ad Account của sếp.

    Args:
        date_preset: "today" | "yesterday" | "last_7d" | "last_30d" | "last_90d" | "this_month" | "last_month"
        level: "account" | "campaign" | "adset" | "ad"
        ad_account_id: Override account ID (dạng "act_XXXXXXXXXX")
        access_token: Override token
        extra_fields: Fields bổ sung ngoài DEFAULT_INSIGHT_FIELDS

    Returns:
        List of insight dicts, sorted by spend desc
    """
    token = access_token or FB_ACCESS_TOKEN
    account_id = ad_account_id or FB_AD_ACCOUNT_ID

    if not token:
        raise RuntimeError("FB_ACCESS_TOKEN chưa setup trong env vars")
    if not account_id:
        raise RuntimeError(
            "FB_AD_ACCOUNT_ID chưa setup — sếp cần thêm env var này.\n"
            "Tìm trong Business Manager → Ad Accounts → copy số act_XXXXXXXX"
        )

    # Ensure format act_XXXXXXXX
    if not account_id.startswith("act_"):
        account_id = f"act_{account_id}"

    fields = DEFAULT_INSIGHT_FIELDS + (extra_fields or [])

    params = {
        "fields": ",".join(fields),
        "date_preset": date_preset,
        "level": level,
        "sort": "spend_descending",
        "limit": 50,
        "access_token": token,
    }

    url = f"{FB_BASE_URL}/{account_id}/insights"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, params=params)

    if response.status_code != 200:
        error_data = response.json()
        error_msg = error_data.get("error", {}).get("message", response.text)
        logger.error(f"FB Marketing API error: {error_msg}")
        raise RuntimeError(f"FB Marketing API lỗi: {error_msg}")

    data = response.json()
    results = data.get("data", [])
    logger.info(f"Marketing API: account {account_id} | {date_preset} | {level} → {len(results)} rows")
    return results


async def get_active_campaigns(
    ad_account_id: Optional[str] = None,
    access_token: Optional[str] = None,
) -> list[dict]:
    """Lấy danh sách campaigns đang active."""
    token = access_token or FB_ACCESS_TOKEN
    account_id = ad_account_id or FB_AD_ACCOUNT_ID

    if not token or not account_id:
        return []

    if not account_id.startswith("act_"):
        account_id = f"act_{account_id}"

    params = {
        "fields": "id,name,status,objective,daily_budget,lifetime_budget,start_time,stop_time",
        "effective_status": '["ACTIVE","PAUSED"]',
        "limit": 30,
        "access_token": token,
    }

    url = f"{FB_BASE_URL}/{account_id}/campaigns"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, params=params)

    if response.status_code != 200:
        return []

    return response.json().get("data", [])


# ─────────────────────────────────────────────────────────────────
# Format helpers
# ─────────────────────────────────────────────────────────────────

def format_insights_for_analysis(insights: list[dict], period: str) -> str:
    """Convert raw Marketing API response → structured text cho Claude phân tích."""
    if not insights:
        return f"**Không có data ads trong period: {period}**\n(Ad Account chưa có campaign nào chạy hoặc không có spend)"

    # Tính tổng account
    total_spend = sum(float(r.get("spend", 0)) for r in insights)
    total_impressions = sum(int(r.get("impressions", 0)) for r in insights)
    total_clicks = sum(int(r.get("clicks", 0)) for r in insights)
    avg_ctr = (total_clicks / total_impressions * 100) if total_impressions else 0
    avg_cpm = (total_spend / total_impressions * 1000) if total_impressions else 0

    lines = [
        f"## Facebook Ads Data — {period}",
        "",
        "### TỔNG QUAN ACCOUNT",
        f"- **Tổng spend:** {total_spend:,.0f} VND",
        f"- **Tổng impressions:** {total_impressions:,}",
        f"- **Tổng clicks:** {total_clicks:,}",
        f"- **CTR trung bình:** {avg_ctr:.2f}%",
        f"- **CPM trung bình:** {avg_cpm:,.0f} VND",
        "",
        f"### BREAKDOWN THEO CAMPAIGN ({len(insights)} campaigns)",
    ]

    for r in insights[:20]:  # Cap ở 20
        name = r.get("campaign_name") or r.get("adset_name") or r.get("ad_name", "Unknown")
        spend = float(r.get("spend", 0))
        impressions = int(r.get("impressions", 0))
        clicks = int(r.get("clicks", 0))
        ctr = float(r.get("ctr", 0)) * 100
        cpm = float(r.get("cpm", 0))
        cpc = float(r.get("cpc", 0))
        frequency = float(r.get("frequency", 0))

        # Extract conversions from actions
        actions = r.get("actions") or []
        conversions = next(
            (int(a.get("value", 0)) for a in actions if a.get("action_type") in ("purchase", "lead", "complete_registration")),
            0
        )

        lines.append(f"\n**{name}**")
        lines.append(f"  Spend: {spend:,.0f} VND | Imp: {impressions:,} | Clicks: {clicks:,}")
        lines.append(f"  CTR: {ctr:.2f}% | CPM: {cpm:,.0f} | CPC: {cpc:,.0f} | Frequency: {frequency:.1f}")
        if conversions:
            cost_per_conv = spend / conversions if conversions else 0
            lines.append(f"  Conversions: {conversions} | Cost/Conv: {cost_per_conv:,.0f} VND")

    lines.append("")
    return "\n".join(lines)


def is_available() -> bool:
    """Check nếu Marketing API đã được config."""
    return bool(FB_ACCESS_TOKEN and FB_AD_ACCOUNT_ID)


def has_token() -> bool:
    """Check chỉ cần token (cho Ads Library, không cần account ID)."""
    return bool(FB_ACCESS_TOKEN)
