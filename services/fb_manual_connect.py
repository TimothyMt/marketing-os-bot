"""Manual-token FB connect — thay thế OAuth flow.

User tự tạo FB App (Meta for Developers) + lấy Access Token qua Graph API
Explorer trong app của chính họ (scopes: ads_read, ads_management,
read_insights, pages_show_list, pages_read_engagement, pages_manage_posts),
rồi paste token vào chat.

Flow:
  1. cmd_connect_ads hiển thị hướng dẫn → set pending_intake["_awaiting_fb_token"]
  2. User paste token → fetch_token_info(token) → validate + lấy ad accounts + pages
  3. save_connection(...) lưu encrypted token (user) + encrypted page tokens
"""
import logging

import httpx

from config import GRAPH_API_VERSION

logger = logging.getLogger(__name__)

GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


async def fetch_token_info(token: str) -> dict:
    """Validate token + lấy /me, ad accounts, pages.

    Raises ValueError nếu token không hợp lệ (kèm message tiếng Việt từ FB).
    """
    async with httpx.AsyncClient(timeout=15) as client:
        me_resp = await client.get(
            f"{GRAPH_BASE}/me",
            params={"fields": "id,name", "access_token": token},
        )
        me_data = me_resp.json()
        if "error" in me_data:
            raise ValueError(me_data["error"].get("message", "Token không hợp lệ"))

        accounts_resp = await client.get(
            f"{GRAPH_BASE}/me/adaccounts",
            params={"fields": "name,account_id,account_status", "access_token": token},
        )
        accounts_data = accounts_resp.json()
        ad_accounts = accounts_data.get("data") or [] if "error" not in accounts_data else []

        pages_resp = await client.get(
            f"{GRAPH_BASE}/me/accounts",
            params={"fields": "id,name,access_token", "access_token": token},
        )
        pages_data = pages_resp.json()
        pages = pages_data.get("data") or [] if "error" not in pages_data else []

    return {
        "me": me_data,
        "ad_accounts": ad_accounts,
        "pages": pages,
    }


async def is_token_valid(token: str) -> bool:
    """Ping /me để check token còn dùng được không (dùng cho job refresh định kỳ)."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{GRAPH_BASE}/me", params={"fields": "id", "access_token": token})
            data = r.json()
            return "error" not in data
    except Exception as e:
        logger.warning("is_token_valid check failed: %s", e)
        return False


def norm_account_id(acc: dict) -> str:
    aid = acc.get("id") or acc.get("account_id") or ""
    return aid if aid.startswith("act_") else f"act_{aid.replace('act_', '')}"
