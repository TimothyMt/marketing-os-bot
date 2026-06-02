"""
Dream Engine storage — persist autonomous marketing ideas ("dreams").

Bot mơ ban đêm (workers/dream_engine.py) → lưu dreams vào table `user_dreams`,
gửi morning digest. User có thể "phát triển" hoặc "bỏ qua" từng dream.

Graceful degradation: mọi DB error → return None/[]/False, KHÔNG block bot.
"""
import logging
import re
import unicodedata
import uuid
from typing import Optional

logger = logging.getLogger(__name__)

TABLE = "user_dreams"

VALID_STATUSES = {"new", "developed", "dismissed"}


def _get_client():
    """Lazy import Supabase client từ session module (đã init pool ở startup)."""
    from storage import session as _session_mod
    return _session_mod._client


def make_signature(title: str) -> str:
    """Chuẩn hoá title → signature để dedupe (lowercase, bỏ dấu, gọn space)."""
    if not title:
        return ""
    # Bỏ dấu tiếng Việt
    nfkd = unicodedata.normalize("NFKD", title)
    ascii_str = "".join(c for c in nfkd if not unicodedata.combining(c))
    ascii_str = ascii_str.replace("đ", "d").replace("Đ", "D")
    ascii_str = ascii_str.lower()
    ascii_str = re.sub(r"[^a-z0-9\s]", "", ascii_str)
    return re.sub(r"\s+", " ", ascii_str).strip()


async def save_dreams(user_id: int, dreams: list[dict], batch_id: Optional[str] = None) -> list[dict]:
    """
    Lưu 1 batch dreams. Mỗi dream dict: {title, angle, why_now, first_step, inspired_by, impact}.
    Returns list rows đã insert (có id) — empty list nếu fail/skip.
    """
    client = _get_client()
    if client is None or not dreams:
        return []

    batch_id = batch_id or str(uuid.uuid4())
    payloads = []
    for d in dreams:
        title = (d.get("title") or "").strip()
        if not title:
            continue
        payloads.append({
            "user_id":     user_id,
            "title":       title[:300],
            "angle":       (d.get("angle") or "")[:1500] or None,
            "why_now":     (d.get("why_now") or "")[:1000] or None,
            "first_step":  (d.get("first_step") or "")[:1000] or None,
            "inspired_by": (d.get("inspired_by") or "mix")[:50],
            "impact":      (d.get("impact") or "medium")[:20],
            "signature":   make_signature(title),
            "status":      "new",
            "batch_id":    batch_id,
        })

    if not payloads:
        return []

    try:
        ins = await client.table(TABLE).insert(payloads).execute()
        return ins.data or []
    except Exception as e:
        logger.warning("save_dreams failed (user=%d): %s", user_id, e)
        return []


async def mark_surfaced(dream_ids: list[str]) -> bool:
    """Đánh dấu các dream đã gửi cho user (surfaced_at = now)."""
    client = _get_client()
    if client is None or not dream_ids:
        return False
    from datetime import datetime
    try:
        await (
            client.table(TABLE)
            .update({"surfaced_at": datetime.utcnow().isoformat()})
            .in_("id", dream_ids)
            .execute()
        )
        return True
    except Exception as e:
        logger.warning("mark_surfaced failed: %s", e)
        return False


async def get_dream(dream_id: str) -> Optional[dict]:
    """Lấy 1 dream theo id."""
    client = _get_client()
    if client is None:
        return None
    try:
        resp = await client.table(TABLE).select("*").eq("id", dream_id).limit(1).execute()
        return resp.data[0] if resp.data else None
    except Exception as e:
        logger.warning("get_dream failed (id=%s): %s", dream_id, e)
        return None


async def update_status(dream_id: str, status: str) -> bool:
    """Cập nhật status của dream: 'new' | 'developed' | 'dismissed'."""
    client = _get_client()
    if client is None or status not in VALID_STATUSES:
        return False
    try:
        await client.table(TABLE).update({"status": status}).eq("id", dream_id).execute()
        return True
    except Exception as e:
        logger.warning("update_status failed (id=%s): %s", dream_id, e)
        return False


async def list_dreams(user_id: int, limit: int = 10, status: Optional[str] = None) -> list[dict]:
    """Liệt kê dreams gần đây của user (mới nhất trước). Lọc theo status nếu có."""
    client = _get_client()
    if client is None:
        return []
    try:
        q = client.table(TABLE).select("*").eq("user_id", user_id)
        if status:
            q = q.eq("status", status)
        resp = await q.order("created_at", desc=True).limit(limit).execute()
        return resp.data or []
    except Exception as e:
        logger.warning("list_dreams failed (user=%d): %s", user_id, e)
        return []


async def recent_signatures(user_id: int, limit: int = 30) -> list[str]:
    """Signatures của dreams gần đây — feed vào prompt để tránh lặp ý tưởng."""
    client = _get_client()
    if client is None:
        return []
    try:
        resp = (
            await client.table(TABLE)
            .select("signature")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [r["signature"] for r in (resp.data or []) if r.get("signature")]
    except Exception as e:
        logger.warning("recent_signatures failed (user=%d): %s", user_id, e)
        return []
