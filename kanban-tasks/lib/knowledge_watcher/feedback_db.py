"""SQLite store for skill V2 feedback (decisions + F3 outputs).

W8.P2.T2.1 — foundation for the feedback loop: every F1/F4 decision (`/keep`,
`/retire`, `/accept`, `/dismiss`, `/keep-permanent`, `/postpone`) is appended
to `decisions`; every F3 generated output gets a row in `f3_outputs`, linked
to the canonical content + edit_distance after `/accept`.

Python skill is the **sole writer**. MC reads via better-sqlite3 in readonly
mode (`?mode=ro&immutable=1`). WAL mode enabled so reads don't block writes.

Schema is versioned via `schema_version` table. Migrations are idempotent.
Future schema bumps: add columns via ALTER TABLE conditionally on
SCHEMA_VERSION + insert new row in schema_version.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Optional


SCHEMA_VERSION = 1


_DEFAULT_PATH = Path(
    os.environ.get(
        "OPENCLAW_KNOWLEDGE_FEEDBACK_DB",
        str(Path.home() / ".openclaw" / "knowledge-watcher" / "feedback.db"),
    )
)


# Schema v1 — initial. INSERT OR IGNORE on the UNIQUE constraint dedupes
# same-day repeated decisions for the same (gap_id, decision).
_SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    gap_id TEXT NOT NULL,
    source TEXT NOT NULL,
    doc_type TEXT,
    project_slug TEXT,
    signals_json TEXT,
    decision TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_decisions_ts ON decisions(ts);
CREATE INDEX IF NOT EXISTS idx_decisions_doctype ON decisions(doc_type);
CREATE INDEX IF NOT EXISTS idx_decisions_decision ON decisions(decision);
-- Unique on (gap_id, decision, day) via expression index (SQLite supports
-- expressions in INDEX since 3.9, but not in UNIQUE/PRIMARY KEY constraints
-- on table definition).
CREATE UNIQUE INDEX IF NOT EXISTS idx_decisions_dedup
    ON decisions(gap_id, decision, substr(ts, 1, 10));

CREATE TABLE IF NOT EXISTS f3_outputs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    doc_path TEXT NOT NULL,
    generator TEXT NOT NULL,
    prompt_hash TEXT,
    content_initial_sha TEXT,
    content_initial TEXT,
    content_accepted_sha TEXT,
    content_accepted TEXT,
    edit_distance_ratio REAL,
    cost_usd REAL,
    accepted_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_f3_generator ON f3_outputs(generator);
CREATE INDEX IF NOT EXISTS idx_f3_accepted_at ON f3_outputs(accepted_at);
"""


def init_db(path: Optional[Path] = None) -> sqlite3.Connection:
    """Open + create schema + stamp version. Idempotent.

    Returns a connection with WAL + autocommit (isolation_level=None) — we
    rely on `INSERT OR IGNORE` for write idempotency. Caller closes.
    """
    p = Path(path) if path else _DEFAULT_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p), isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(_SCHEMA_V1)
    cur = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
    if cur[0] is None:
        conn.execute(
            "INSERT INTO schema_version (version) VALUES (?)",
            (SCHEMA_VERSION,),
        )
    return conn


def get_db_path() -> Path:
    """Read latest path from env (re-evaluated each call so tests can override)."""
    return Path(
        os.environ.get(
            "OPENCLAW_KNOWLEDGE_FEEDBACK_DB",
            str(_DEFAULT_PATH),
        )
    )
