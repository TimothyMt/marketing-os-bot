"""Supabase REST CRUD for spy_targets, spy_cache, and fb_credentials.

Uses the same supabase-py AsyncClient as session.py.
Client is injected via set_client() called from storage.session.init_pool().
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from storage.models import SpyTarget, FbCredentials

logger = logging.getLogger(__name__)

_client = None  # injected by storage.session.init_pool()


def set_client(client) -> None:
    """Share the supabase AsyncClient from session.init_pool()."""
    global _client
    _client = client


def _require_client():
    if _client is None:
        raise RuntimeError("spy_store not initialized — call storage.session.init_pool() first")
    return _client


# ─── FB Credentials ──────────────────────────────────────────────────


async def save_fb_credentials(creds: FbCredentials) -> None:
    from storage.crypto import encrypt_token

    payload = {
        "user_id": creds.user_id,
        "encrypted_token": encrypt_token(creds.plaintext_token),
        "ad_account_id": creds.ad_account_id,
        "page_id": creds.page_id,
    }
    if creds.token_expires_at:
        payload["token_expires_at"] = creds.token_expires_at.isoformat()
    await _require_client().table("fb_credentials").upsert(payload).execute()


async def get_fb_credentials(user_id: int) -> Optional[FbCredentials]:
    from storage.crypto import decrypt_token

    resp = (
        await _require_client()
        .table("fb_credentials")
        .select("*")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not resp.data:
        return None
    row = resp.data[0]
    return FbCredentials(
        user_id=row["user_id"],
        plaintext_token=decrypt_token(row["encrypted_token"]),
        ad_account_id=row.get("ad_account_id", ""),
        page_id=row.get("page_id", ""),
        token_expires_at=(
            datetime.fromisoformat(row["token_expires_at"])
            if row.get("token_expires_at")
            else None
        ),
    )


# ─── Spy Targets ─────────────────────────────────────────────────────


async def add_spy_target(target: SpyTarget) -> SpyTarget:
    payload = {
        "user_id": target.user_id,
        "fanpage_url": target.fanpage_url,
        "label": target.label,
        "poll_interval_h": target.poll_interval_h,
        "is_active": True,
    }
    resp = await _require_client().table("spy_targets").insert(payload).execute()
    if resp.data:
        target.id = resp.data[0]["id"]
    return target


async def list_spy_targets(user_id: int) -> list[SpyTarget]:
    resp = (
        await _require_client()
        .table("spy_targets")
        .select("*")
        .eq("user_id", user_id)
        .eq("is_active", True)
        .order("created_at")
        .execute()
    )
    return [_row_to_target(r) for r in (resp.data or [])]


async def remove_spy_target(target_id: str, user_id: int) -> bool:
    """Soft-delete. Returns True if a row was updated."""
    resp = (
        await _require_client()
        .table("spy_targets")
        .update({"is_active": False})
        .eq("id", target_id)
        .eq("user_id", user_id)
        .execute()
    )
    return bool(resp.data)


async def get_all_active_spy_targets() -> list[SpyTarget]:
    """All active targets across all users — for the spy worker."""
    resp = (
        await _require_client()
        .table("spy_targets")
        .select("*")
        .eq("is_active", True)
        .execute()
    )
    return [_row_to_target(r) for r in (resp.data or [])]


async def save_spy_snapshot(target_id: str, snapshot: dict, analysis: str) -> None:
    client = _require_client()
    await client.table("spy_cache").insert({
        "target_id": target_id,
        "snapshot": snapshot,
        "analysis": analysis,
        "alert_sent": False,
    }).execute()
    await client.table("spy_targets").update(
        {"last_polled_at": datetime.utcnow().isoformat()}
    ).eq("id", target_id).execute()


async def get_unsent_alerts() -> list[dict]:
    resp = (
        await _require_client()
        .table("spy_cache")
        .select("*, spy_targets(user_id, label, fanpage_url)")
        .eq("alert_sent", False)
        .order("created_at")
        .limit(50)
        .execute()
    )
    return resp.data or []


async def mark_alert_sent(cache_id: str) -> None:
    await _require_client().table("spy_cache").update({"alert_sent": True}).eq("id", cache_id).execute()


def _row_to_target(row: dict) -> SpyTarget:
    return SpyTarget(
        id=row["id"],
        user_id=row["user_id"],
        fanpage_url=row["fanpage_url"],
        label=row.get("label", ""),
        poll_interval_h=row.get("poll_interval_h", 24),
        is_active=row.get("is_active", True),
        last_polled_at=(
            datetime.fromisoformat(row["last_polled_at"])
            if row.get("last_polled_at")
            else None
        ),
    )
