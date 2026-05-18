"""
SQLite-based session storage.
"""
import sqlite3
import json
import asyncio
from datetime import datetime
from dataclasses import asdict
from typing import Optional
from contextlib import contextmanager

from config import DATABASE_PATH
from storage.models import Session, BusinessProfile, PipelineStage


@contextmanager
def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                user_id     INTEGER PRIMARY KEY,
                stage       TEXT NOT NULL DEFAULT 'idle',
                profile     TEXT NOT NULL DEFAULT '{}',
                intake_history TEXT NOT NULL DEFAULT '[]',
                results     TEXT NOT NULL DEFAULT '{}',
                raw_description TEXT NOT NULL DEFAULT '',
                created_at  TEXT,
                updated_at  TEXT
            )
        """)


def _row_to_session(row) -> Session:
    profile_data = json.loads(row["profile"])
    profile = BusinessProfile(**profile_data)

    session = Session(
        user_id=row["user_id"],
        stage=PipelineStage(row["stage"]),
        profile=profile,
        intake_history=json.loads(row["intake_history"]),
        results=json.loads(row["results"]),
        raw_description=row["raw_description"] or "",
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
    return session


def get_session(user_id: int) -> Session:
    """Get or create session for user."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE user_id = ?", (user_id,)
        ).fetchone()

        if row:
            return _row_to_session(row)

        # Create new session
        now = datetime.utcnow().isoformat()
        conn.execute(
            """INSERT INTO sessions (user_id, created_at, updated_at)
               VALUES (?, ?, ?)""",
            (user_id, now, now),
        )
        return Session(user_id=user_id, created_at=now, updated_at=now)


def save_session(session: Session):
    """Persist session to database."""
    now = datetime.utcnow().isoformat()
    profile_dict = asdict(session.profile)

    with get_db() as conn:
        conn.execute(
            """INSERT INTO sessions
               (user_id, stage, profile, intake_history, results, raw_description, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                 stage = excluded.stage,
                 profile = excluded.profile,
                 intake_history = excluded.intake_history,
                 results = excluded.results,
                 raw_description = excluded.raw_description,
                 updated_at = excluded.updated_at
            """,
            (
                session.user_id,
                session.stage.value,
                json.dumps(profile_dict, ensure_ascii=False),
                json.dumps(session.intake_history, ensure_ascii=False),
                json.dumps(session.results, ensure_ascii=False),
                session.raw_description,
                session.created_at or now,
                now,
            ),
        )


def reset_session(user_id: int):
    """Reset session to initial state (keep user_id)."""
    with get_db() as conn:
        now = datetime.utcnow().isoformat()
        conn.execute(
            """UPDATE sessions SET
               stage = 'idle',
               profile = '{}',
               intake_history = '[]',
               results = '{}',
               raw_description = '',
               updated_at = ?
               WHERE user_id = ?
            """,
            (now, user_id),
        )
