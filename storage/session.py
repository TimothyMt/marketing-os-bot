"""
Async PostgreSQL session storage via asyncpg.
Connection pool is initialized once at bot startup.
"""
import asyncpg
import json
import logging
from datetime import datetime
from typing import Optional

from config import DATABASE_URL
from storage.models import Session, BusinessProfile, PipelineStage

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None


async def init_pool():
    """Create the asyncpg connection pool. Call once at startup."""
    global _pool
    _pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=2,
        max_size=10,
        command_timeout=30,
    )
    logger.info("PostgreSQL connection pool created.")


async def init_db():
    """Create sessions table if it doesn't exist."""
    async with _pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                user_id          BIGINT PRIMARY KEY,
                stage            TEXT NOT NULL DEFAULT 'idle',
                profile          JSONB NOT NULL DEFAULT '{}',
                intake_history   JSONB NOT NULL DEFAULT '[]',
                results          JSONB NOT NULL DEFAULT '{}',
                raw_description  TEXT NOT NULL DEFAULT '',
                created_at       TIMESTAMPTZ DEFAULT NOW(),
                updated_at       TIMESTAMPTZ DEFAULT NOW()
            )
        """)
    logger.info("Database schema ready.")


def _row_to_session(row) -> Session:
    profile_data = dict(row["profile"]) if row["profile"] else {}
    profile = BusinessProfile(**{
        k: v for k, v in profile_data.items()
        if k in BusinessProfile.__dataclass_fields__
    })
    return Session(
        user_id=row["user_id"],
        stage=PipelineStage(row["stage"]),
        profile=profile,
        intake_history=list(row["intake_history"] or []),
        results=dict(row["results"] or {}),
        raw_description=row["raw_description"] or "",
        created_at=str(row["created_at"]) if row["created_at"] else None,
        updated_at=str(row["updated_at"]) if row["updated_at"] else None,
    )


async def get_session(user_id: int) -> Session:
    """Fetch existing session or return a fresh one (not yet persisted)."""
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM sessions WHERE user_id = $1", user_id
        )
    if row:
        return _row_to_session(row)
    return Session(user_id=user_id)


async def save_session(session: Session):
    """Upsert session to PostgreSQL."""
    from dataclasses import asdict
    profile_dict = asdict(session.profile)

    async with _pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO sessions
                (user_id, stage, profile, intake_history, results, raw_description, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, NOW())
            ON CONFLICT (user_id) DO UPDATE SET
                stage           = EXCLUDED.stage,
                profile         = EXCLUDED.profile,
                intake_history  = EXCLUDED.intake_history,
                results         = EXCLUDED.results,
                raw_description = EXCLUDED.raw_description,
                updated_at      = NOW()
        """,
            session.user_id,
            session.stage.value,
            json.dumps(profile_dict, ensure_ascii=False),
            json.dumps(session.intake_history, ensure_ascii=False),
            json.dumps(session.results, ensure_ascii=False),
            session.raw_description,
        )


async def reset_session(user_id: int):
    """Reset session fields to initial state, keep the row."""
    async with _pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO sessions (user_id) VALUES ($1)
            ON CONFLICT (user_id) DO UPDATE SET
                stage           = 'idle',
                profile         = '{}',
                intake_history  = '[]',
                results         = '{}',
                raw_description = '',
                updated_at      = NOW()
        """, user_id)
