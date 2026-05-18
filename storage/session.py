"""
Async Supabase session storage via supabase-py (HTTPS/REST).
Communicates over port 443 — works on any cloud platform.
"""
import json
import logging
from typing import Optional

from supabase import AsyncClient, acreate_client

from config import SUPABASE_URL, SUPABASE_KEY
from storage.models import Session, BusinessProfile, PipelineStage

logger = logging.getLogger(__name__)

_client: Optional[AsyncClient] = None
TABLE = "sessions"


async def init_pool():
    """Initialize Supabase async client. Called once at bot startup."""
    global _client
    _client = await acreate_client(SUPABASE_URL, SUPABASE_KEY)
    logger.info("Supabase client initialized.")


async def init_db():
    """Verify connection by pinging the sessions table."""
    try:
        await _client.table(TABLE).select("user_id").limit(1).execute()
        logger.info("Supabase sessions table reachable.")
    except Exception as e:
        logger.error(f"sessions table not found — run the setup SQL in Supabase: {e}")
        raise


def _row_to_session(row: dict) -> Session:
    profile_data = row.get("profile") or {}
    if isinstance(profile_data, str):
        profile_data = json.loads(profile_data)

    profile = BusinessProfile(**{
        k: v for k, v in profile_data.items()
        if k in BusinessProfile.__dataclass_fields__
    })

    intake_history = row.get("intake_history") or []
    results = row.get("results") or {}

    return Session(
        user_id=row["user_id"],
        stage=PipelineStage(row.get("stage", "idle")),
        profile=profile,
        intake_history=intake_history if isinstance(intake_history, list) else json.loads(intake_history),
        results=results if isinstance(results, dict) else json.loads(results),
        raw_description=row.get("raw_description") or "",
        created_at=str(row.get("created_at") or ""),
        updated_at=str(row.get("updated_at") or ""),
    )


async def get_session(user_id: int) -> Session:
    """Fetch existing session or return a fresh one."""
    resp = (
        await _client.table(TABLE)
        .select("*")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if resp.data:
        return _row_to_session(resp.data[0])
    return Session(user_id=user_id)


async def save_session(session: Session):
    """Upsert session via Supabase REST."""
    from dataclasses import asdict
    profile_dict = asdict(session.profile)

    payload = {
        "user_id":          session.user_id,
        "stage":            session.stage.value,
        "profile":          profile_dict,
        "intake_history":   session.intake_history,
        "results":          session.results,
        "raw_description":  session.raw_description,
    }

    await _client.table(TABLE).upsert(payload).execute()


async def reset_session(user_id: int):
    """Reset session to initial state."""
    payload = {
        "user_id":         user_id,
        "stage":           "idle",
        "profile":         {},
        "intake_history":  [],
        "results":         {},
        "raw_description": "",
    }
    await _client.table(TABLE).upsert(payload).execute()
