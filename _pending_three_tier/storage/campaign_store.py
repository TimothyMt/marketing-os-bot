"""CRUD for campaigns table."""
import logging
from typing import Optional

from storage.models import Campaign

logger = logging.getLogger(__name__)

_TABLE = "campaigns"
_client = None


def set_client(c):
    global _client
    _client = c


def _row_to_campaign(row: dict) -> Campaign:
    return Campaign(
        id=row.get("id"),
        user_id=row["user_id"],
        name=row.get("name", "Campaign mới"),
        brief=row.get("brief"),
        content_calendar=row.get("content_calendar"),
        ad_copy=row.get("ad_copy"),
        video_script=row.get("video_script"),
        ugc_brief=row.get("ugc_brief"),
        email_zalo=row.get("email_zalo"),
        created_at=str(row.get("created_at") or ""),
        updated_at=str(row.get("updated_at") or ""),
    )


async def list_campaigns(user_id: int) -> list[Campaign]:
    resp = (
        await _client.table(_TABLE)
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    )
    return [_row_to_campaign(r) for r in resp.data]


async def get_campaign(campaign_id: str) -> Optional[Campaign]:
    resp = (
        await _client.table(_TABLE)
        .select("*")
        .eq("id", campaign_id)
        .limit(1)
        .execute()
    )
    if resp.data:
        return _row_to_campaign(resp.data[0])
    return None


async def create_campaign(user_id: int, name: str) -> Campaign:
    resp = (
        await _client.table(_TABLE)
        .insert({"user_id": user_id, "name": name})
        .execute()
    )
    return _row_to_campaign(resp.data[0])


async def save_campaign(campaign: Campaign) -> Campaign:
    """Insert or update a campaign record."""
    payload = {
        "user_id":          campaign.user_id,
        "name":             campaign.name,
        "brief":            campaign.brief,
        "content_calendar": campaign.content_calendar,
        "ad_copy":          campaign.ad_copy,
        "video_script":     campaign.video_script,
        "ugc_brief":        campaign.ugc_brief,
        "email_zalo":       campaign.email_zalo,
    }
    if campaign.id:
        resp = (
            await _client.table(_TABLE)
            .update(payload)
            .eq("id", campaign.id)
            .execute()
        )
    else:
        resp = await _client.table(_TABLE).insert(payload).execute()
    return _row_to_campaign(resp.data[0])


async def delete_campaign(campaign_id: str, user_id: int) -> bool:
    resp = (
        await _client.table(_TABLE)
        .delete()
        .eq("id", campaign_id)
        .eq("user_id", user_id)
        .execute()
    )
    return bool(resp.data)
