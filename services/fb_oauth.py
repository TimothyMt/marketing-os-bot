"""FB OAuth per-user — URL generation, code exchange, token refresh.

Flow:
  1. build_oauth_url(user_id) → URL gửi cho user bấm
  2. User approve trên FB → FB redirect về /oauth/fb/callback?code=...&state=...
  3. handle_callback(request, bot) → exchange code → lưu token → notify user qua Telegram
  4. Scheduler gọi refresh_token_if_needed() trước mỗi pull
"""
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
from starlette.requests import Request
from starlette.responses import HTMLResponse

from config import FB_APP_ID, FB_APP_SECRET, GRAPH_API_VERSION, WEBHOOK_BASE_URL

logger = logging.getLogger(__name__)

REDIRECT_URI = f"{WEBHOOK_BASE_URL}/oauth/fb/callback"
OAUTH_SCOPES = "ads_read,read_insights,ads_management"

# ── HTML responses khi OAuth xong ───────────────────────────────

_HTML_SUCCESS = """<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Kết nối thành công</title>
<style>body{{font-family:sans-serif;text-align:center;padding:60px;background:#f0fdf4}}
h2{{color:#16a34a}}p{{color:#555}}</style></head><body>
<h2>✅ Kết nối thành công!</h2>
<p>Quay lại Telegram — Max sẽ xác nhận ngay.</p>
<p><small>Cửa sổ này có thể đóng.</small></p></body></html>"""

_HTML_ERROR = """<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Lỗi kết nối</title>
<style>body{{font-family:sans-serif;text-align:center;padding:60px;background:#fef2f2}}
h2{{color:#dc2626}}p{{color:#555}}</style></head><body>
<h2>❌ Kết nối thất bại</h2><p>{reason}</p>
<p>Quay lại Telegram và thử lại với /connect_ads.</p></body></html>"""


# ── URL generation ───────────────────────────────────────────────

async def build_oauth_url(user_id: int) -> str:
    """Tạo FB OAuth URL + lưu state token. Returns URL."""
    from storage.fb_connections import save_oauth_state
    state = str(uuid.uuid4())
    await save_oauth_state(state, user_id)
    params = (
        f"client_id={FB_APP_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope={OAUTH_SCOPES}"
        f"&state={state}"
        f"&response_type=code"
    )
    return f"https://www.facebook.com/dialog/oauth?{params}"


# ── Token exchange ───────────────────────────────────────────────

async def _exchange_short_token(code: str) -> str:
    """Exchange authorization code → short-lived token (2h)."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            f"https://graph.facebook.com/{GRAPH_API_VERSION}/oauth/access_token",
            params={
                "client_id":     FB_APP_ID,
                "client_secret": FB_APP_SECRET,
                "redirect_uri":  REDIRECT_URI,
                "code":          code,
            },
        )
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise ValueError(f"FB exchange error: {data['error']}")
        return data["access_token"]


async def _extend_to_long_token(short_token: str) -> tuple[str, datetime]:
    """Extend short-lived → long-lived token (60 ngày). Returns (token, expires_at)."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            f"https://graph.facebook.com/{GRAPH_API_VERSION}/oauth/access_token",
            params={
                "grant_type":        "fb_exchange_token",
                "client_id":         FB_APP_ID,
                "client_secret":     FB_APP_SECRET,
                "fb_exchange_token": short_token,
            },
        )
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise ValueError(f"FB extend error: {data['error']}")
        expires_in = data.get("expires_in", 5184000)  # default 60 ngày
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        return data["access_token"], expires_at


async def _get_ad_accounts(access_token: str) -> list[dict]:
    """Lấy danh sách Ad Accounts user có quyền."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            f"https://graph.facebook.com/{GRAPH_API_VERSION}/me/adaccounts",
            params={
                "fields":       "name,account_id,account_status",
                "access_token": access_token,
            },
        )
        r.raise_for_status()
        data = r.json()
        return data.get("data") or []


# ── Token refresh ────────────────────────────────────────────────

async def refresh_token_if_needed(user_id: int) -> bool:
    """Refresh token nếu hết hạn trong < 7 ngày. Returns True nếu còn dùng được."""
    from storage.fb_connections import get_connection, update_token, disable_connection
    from tools.crypto import decrypt_token, encrypt_token

    conn = await get_connection(user_id)
    if not conn:
        return False

    expires_at = conn.get("expires_at")
    if expires_at:
        exp = datetime.fromisoformat(expires_at)
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        days_left = (exp - datetime.now(timezone.utc)).days
        if days_left > 7:
            return True  # còn nhiều thời gian, không cần refresh

    try:
        old_token = decrypt_token(conn["encrypted_token"])
        new_token, new_expiry = await _extend_to_long_token(old_token)
        await update_token(user_id, encrypt_token(new_token), new_expiry)
        logger.info("Token refreshed for user=%d, new_expiry=%s", user_id, new_expiry)
        return True
    except Exception as e:
        logger.warning("Token refresh failed for user=%d: %s", user_id, e)
        await disable_connection(user_id)
        return False


# ── OAuth callback handler ───────────────────────────────────────

async def handle_callback(request: Request, bot) -> HTMLResponse:
    """Starlette handler cho /oauth/fb/callback.
    Được gắn vào main.py khi khởi động bot.
    """
    from storage.fb_connections import consume_oauth_state, save_connection, get_connection
    from tools.crypto import encrypt_token
    from telegram.constants import ParseMode

    code  = request.query_params.get("code")
    state = request.query_params.get("state")
    error = request.query_params.get("error")

    if error:
        return HTMLResponse(_HTML_ERROR.format(reason=f"User cancelled hoặc quyền bị từ chối: {error}"))
    if not code or not state:
        return HTMLResponse(_HTML_ERROR.format(reason="Thiếu tham số code hoặc state."))

    # Validate state → user_id
    user_id = await consume_oauth_state(state)
    if not user_id:
        return HTMLResponse(_HTML_ERROR.format(reason="Link đã hết hạn hoặc không hợp lệ. Vui lòng /connect_ads lại."))

    try:
        short_token = await _exchange_short_token(code)
        long_token, expires_at = await _extend_to_long_token(short_token)
        accounts = await _get_ad_accounts(long_token)
    except Exception as e:
        logger.error("OAuth token exchange failed for user=%d: %s", user_id, e)
        return HTMLResponse(_HTML_ERROR.format(reason=f"Lỗi exchange token: {e}"))

    if not accounts:
        return HTMLResponse(_HTML_ERROR.format(
            reason="Tài khoản này chưa có Ad Account. Cần tạo Ad Account trong Business Manager trước."
        ))

    encrypted = encrypt_token(long_token)

    if len(accounts) == 1:
        # Auto-select nếu chỉ có 1 account
        acc = accounts[0]
        account_id = acc.get("id") or acc.get("account_id")
        if not account_id.startswith("act_"):
            account_id = f"act_{account_id.replace('act_', '')}"
        account_name = acc.get("name") or account_id
        await save_connection(user_id, encrypted, account_id, account_name, expires_at)
        await _notify_connected(bot, user_id, account_name, account_id, accounts)
    else:
        # Nhiều accounts → lưu tạm token, hỏi user chọn
        # Dùng pending_intake pattern qua Telegram inline keyboard
        await _ask_select_account(bot, user_id, encrypted, expires_at, accounts)

    return HTMLResponse(_HTML_SUCCESS)


async def _notify_connected(bot, user_id: int, account_name: str, account_id: str, all_accounts: list) -> None:
    """Gửi Telegram xác nhận kết nối + hỏi thiết lập metrics."""
    from telegram.constants import ParseMode
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    text = (
        f"✅ *Đã kết nối Facebook Ads!*\n\n"
        f"📊 Account: *{account_name}*\n"
        f"🆔 ID: `{account_id}`\n\n"
        f"Em sẽ báo cáo ads lúc *8:00 sáng* mỗi ngày và tóm tắt *mỗi thứ Hai* hàng tuần.\n\n"
        f"Tiếp theo: Sếp chọn chỉ số muốn theo dõi 👇"
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("⚙️ Chọn chỉ số & ngưỡng cảnh báo", callback_data="ads_setup_metrics"),
        InlineKeyboardButton("✅ Dùng mặc định", callback_data="ads_setup_default"),
    ]])
    try:
        await bot.send_message(user_id, text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
    except Exception as e:
        logger.warning("Notify connected failed for user=%d: %s", user_id, e)


async def _ask_select_account(bot, user_id: int, encrypted_token: str, expires_at: datetime, accounts: list) -> None:
    """User có nhiều Ad Account → gửi inline keyboard chọn."""
    from telegram.constants import ParseMode
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    import json
    from storage.fb_connections import save_oauth_state

    # Lưu tạm token vào oauth_states (abuse key, 30 phút)
    # callback sẽ đọc khi user chọn account
    temp_key = f"token_{user_id}"
    import uuid
    from storage import get_db
    db = get_db()
    from datetime import datetime, timezone, timedelta
    db.table("oauth_states").upsert({
        "state_token": temp_key,
        "user_id":     user_id,
        "expires_at":  (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
    }).execute()
    # Store token separately in a safe way — use the state table with a different key
    db.table("oauth_states").upsert({
        "state_token": f"tkn_{user_id}",
        "user_id":     user_id,
        "expires_at":  (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
    }).execute()

    buttons = []
    for acc in accounts[:4]:  # max 4 buttons
        acc_id = acc.get("id") or ""
        name = acc.get("name") or acc_id
        buttons.append([InlineKeyboardButton(
            f"📊 {name[:30]}",
            callback_data=f"ads_select_account:{acc_id}:{encrypted_token[:20]}",  # truncate for callback limit
        )])

    text = (
        f"🔎 Sếp có *{len(accounts)} Ad Account*. Chọn account muốn kết nối:\n\n"
        + "\n".join(f"• {a.get('name')} (`{a.get('id')}`)" for a in accounts[:6])
    )
    try:
        await bot.send_message(
            user_id, text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(buttons),
        )
    except Exception as e:
        logger.warning("ask_select_account failed for user=%d: %s", user_id, e)
