"""
Async Supabase session storage via supabase-py (HTTPS/REST).
Communicates over port 443 — works on any cloud platform.
"""
import json
import logging
from typing import Optional

from supabase import AsyncClient, acreate_client

from config import SUPABASE_URL, SUPABASE_KEY
from storage.models import Session, BusinessProfile, PipelineStage, VersionedResult

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


def _normalize_results(raw_results: dict) -> dict[str, list[VersionedResult]]:
    """Convert stored results into VersionedResult list per skill.
    Backward-compat: if a value is a string (old schema), wrap into a single v1.
    If a value is already list[dict], convert each dict → VersionedResult.
    """
    normalized: dict[str, list[VersionedResult]] = {}
    for skill_key, value in raw_results.items():
        if isinstance(value, str):
            # Old schema: single string → wrap as v1
            normalized[skill_key] = [VersionedResult.new(value, version=1)]
        elif isinstance(value, list):
            # New schema: list of dicts
            normalized[skill_key] = [VersionedResult.from_dict(v) for v in value if isinstance(v, dict)]
        # else: skip unknown types
    return normalized


def _row_to_session(row: dict) -> Session:
    profile_data = row.get("profile") or {}
    if isinstance(profile_data, str):
        profile_data = json.loads(profile_data)

    profile = BusinessProfile(**{
        k: v for k, v in profile_data.items()
        if k in BusinessProfile.__dataclass_fields__
    })

    intake_history = row.get("intake_history") or []
    raw_results = row.get("results") or {}
    if isinstance(raw_results, str):
        raw_results = json.loads(raw_results)

    # Extract meta fields stored inside results (NOT versioned skill results)
    selected_task = raw_results.pop("_selected_task", None) or None
    pending_intake = raw_results.pop("_pending_intake", {}) or {}
    preferences = raw_results.pop("_preferences", {}) or {}
    feedback = raw_results.pop("_feedback", {}) or {}
    pending_followup_skill = raw_results.pop("_pending_followup_skill", None) or None
    raw_results.pop("_brand_candidates", None)  # backward-compat: drop old field

    results = _normalize_results(raw_results)

    return Session(
        user_id=row["user_id"],
        stage=PipelineStage(row.get("stage", "idle")),
        selected_task=selected_task,
        profile=profile,
        intake_history=intake_history if isinstance(intake_history, list) else json.loads(intake_history),
        results=results,
        pending_intake=pending_intake if isinstance(pending_intake, dict) else {},
        preferences=preferences if isinstance(preferences, dict) else {},
        feedback=feedback if isinstance(feedback, dict) else {},
        pending_followup_skill=pending_followup_skill,
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
    """Upsert session via Supabase REST.
    Serializes VersionedResult list per skill as list of dicts.
    Packs meta fields (selected_task, pending_intake) inside `results` to avoid schema change.
    """
    from dataclasses import asdict
    profile_dict = asdict(session.profile)

    # Serialize results: skill_key → list[dict] per version
    results_serialized: dict = {
        skill_key: [v.to_dict() for v in versions]
        for skill_key, versions in session.results.items()
    }

    # Pack meta fields inside results dict
    results_serialized["_selected_task"] = session.selected_task or ""
    if session.pending_intake:
        results_serialized["_pending_intake"] = session.pending_intake
    if session.preferences:
        results_serialized["_preferences"] = session.preferences
    if session.feedback:
        results_serialized["_feedback"] = session.feedback
    if session.pending_followup_skill:
        results_serialized["_pending_followup_skill"] = session.pending_followup_skill

    payload = {
        "user_id":          session.user_id,
        "stage":            session.stage.value,
        "profile":          profile_dict,
        "intake_history":   session.intake_history,
        "results":          results_serialized,
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
    }
    await _client.table(TABLE).upsert(payload).execute()
