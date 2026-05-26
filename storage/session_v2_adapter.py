"""
Session V2 Adapter — bridge bot code ↔ v2 normalized schema.

Phase 2 strategy: bot vẫn dùng Session dataclass cũ, adapter này
load/save từ v2 tables thay vì sessions monolithic.

Enable bằng USE_DB_V2=true env var.

Workflow:
  get_session_v2(user_id) → load from users + profile + sessions_slim + skill_runs
                          → build Session object (same shape as v1)
  save_session_v2(session) → split data → upsert to 4 tables
"""
import logging
from typing import Optional

from storage.models import Session, BusinessProfile, PipelineStage, VersionedResult

logger = logging.getLogger(__name__)


async def get_session_v2(user_id: int) -> Session:
    """
    Build Session dataclass từ v2 tables.
    Fallback: nếu v2 trống → return empty Session.
    """
    from storage.v2 import (
        get_user, get_profile, get_session_slim,
        list_skill_runs,
    )

    user        = await get_user(user_id)
    profile_row = await get_profile(user_id)
    slim        = await get_session_slim(user_id)
    runs        = await list_skill_runs(user_id, limit=100)

    # ── Build BusinessProfile ───────────────────────────────
    profile_fields = {}
    if profile_row:
        profile_fields = {
            k: v for k, v in profile_row.items()
            if k in BusinessProfile.__dataclass_fields__
        }
    profile = BusinessProfile(**profile_fields)

    # ── Build preferences (from users + add token tracking) ─
    preferences: dict = {}
    if user:
        if user.get("name"):        preferences["user_name"]  = user["name"]
        if user.get("en_level"):    preferences["en_level"]    = user["en_level"]
        preferences["token_quota"] = str(user.get("token_quota", 500000))
        preferences["token_used"]  = str(user.get("token_used",  0))

    # ── Build results dict (skill_name → [VersionedResult]) ─
    results: dict[str, list[VersionedResult]] = {}
    for run in runs:
        skill_name = run["skill_name"]
        vr = VersionedResult(
            content=run["content"],
            version=run["version"],
            created_at=run.get("created_at"),
        )
        results.setdefault(skill_name, []).append(vr)
    # Sort each skill's versions ascending
    for k in results:
        results[k].sort(key=lambda v: v.version)

    return Session(
        user_id=user_id,
        stage=PipelineStage(slim.get("stage", "idle")),
        selected_task=slim.get("selected_task"),
        profile=profile,
        intake_history=slim.get("intake_history") or [],
        results=results,
        pending_intake=slim.get("pending_intake") or {},
        preferences=preferences,
        feedback={},  # TODO Phase 3: load from skill_runs.rating
        tone_calibration=slim.get("tone_calibration") or {},
        content_outputs={},  # TODO Phase 3: load from posts table
        created_at=(user or {}).get("created_at"),
        updated_at=(user or {}).get("updated_at"),
    )


async def save_session_v2(session: Session) -> None:
    """
    Split Session dataclass → upsert sang 3 v2 tables.
    skill_runs là append-only (insert mới khi có result mới).
    """
    from dataclasses import asdict
    from storage.v2 import (
        upsert_user, upsert_profile, upsert_session_slim,
        insert_skill_run, get_latest_skill_run,
    )

    user_id = session.user_id
    prefs = session.preferences or {}

    # ── 1. users ────────────────────────────────────────────
    await upsert_user(
        user_id=user_id,
        name=prefs.get("user_name"),
        en_level=prefs.get("en_level"),
        token_quota=int(prefs.get("token_quota", 500000)) if prefs.get("token_quota") else None,
        plan=prefs.get("plan"),
        industry_cached=session.profile.industry,
    )

    # Token tracking: nếu token_used trong session khác với DB → update
    if "token_used" in prefs:
        try:
            from storage.v2.users import get_user as _gu
            current = await _gu(user_id)
            new_used = int(prefs["token_used"])
            if current and current.get("token_used") != new_used:
                from storage.v2._client import get_client
                await get_client().table("users").update(
                    {"token_used": new_used}
                ).eq("user_id", user_id).execute()
        except Exception as e:
            logger.warning("token_used sync failed: %s", e)

    # ── 2. user_business_profile ────────────────────────────
    profile_dict = asdict(session.profile)
    profile_clean = {k: v for k, v in profile_dict.items() if v is not None}
    if profile_clean:
        await upsert_profile(user_id, **profile_clean)

    # ── 3. user_sessions_slim ───────────────────────────────
    await upsert_session_slim(
        user_id=user_id,
        stage=session.stage.value,
        selected_task=session.selected_task,
        pending_intake=session.pending_intake or {},
        intake_history=(session.intake_history or [])[-20:],
        tone_calibration=session.tone_calibration or {},
    )

    # ── 4. skill_runs — append-only, chỉ insert version mới ─
    for skill_name, versions in (session.results or {}).items():
        if skill_name.startswith("_") or not versions:
            continue
        latest_local = versions[-1]

        # Check DB latest version
        latest_db = await get_latest_skill_run(user_id, skill_name)
        db_version = (latest_db or {}).get("version", 0)

        if latest_local.version > db_version:
            await insert_skill_run(
                user_id=user_id,
                skill_name=skill_name,
                content=latest_local.content,
            )
