"""High-level feedback capture (W8.P3.T3.1).

Wraps feedback_db with friendly Python signatures used by F1/F4 commands +
F3 generators. Idempotent same-day decisions; F3 edit-distance computed via
difflib.SequenceMatcher on /accept.

Failures are non-fatal — feedback is best-effort instrumentation and must
never block the user-facing F1/F4/F3 workflows.
"""
from __future__ import annotations

import datetime as _dt
import difflib
import hashlib
import json
import sqlite3
from typing import Any, List, Optional

from lib.knowledge_watcher.feedback_db import init_db, get_db_path


def _now_iso() -> str:
    return (
        _dt.datetime.now(_dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        + "Z"
    )


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _serialize_signals(signals: List[Any]) -> str:
    out = []
    for s in signals or []:
        cat = getattr(s, "category", None)
        cat_value = getattr(cat, "value", str(cat) if cat else None)
        out.append({
            "category": cat_value,
            "confidence": getattr(s, "confidence", None),
            "evidence": getattr(s, "evidence", None),
        })
    return json.dumps(out)


def record_decision(
    *,
    gap_id: str,
    source: str,
    doc_type: Optional[str],
    project_slug: Optional[str],
    signals: List[Any],
    decision: str,
) -> bool:
    """Append a decision row. Idempotent: (gap_id, decision, day) unique.

    Returns True on insert, False on duplicate-skip or any error.
    """
    try:
        conn = init_db(get_db_path())
    except sqlite3.Error:
        return False
    try:
        conn.execute(
            "INSERT OR IGNORE INTO decisions "
            "(ts, gap_id, source, doc_type, project_slug, "
            " signals_json, decision) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                _now_iso(), gap_id, source, doc_type, project_slug,
                _serialize_signals(signals), decision,
            ),
        )
        return conn.total_changes > 0
    except sqlite3.Error:
        return False
    finally:
        conn.close()


def record_f3_output_initial(
    *,
    doc_path: str,
    generator: str,
    prompt_hash: str,
    content: str,
    cost_usd: float,
) -> int:
    """Stamp F3 output at generation time. Returns row id (or 0 on error)."""
    try:
        conn = init_db(get_db_path())
    except sqlite3.Error:
        return 0
    try:
        cur = conn.execute(
            "INSERT INTO f3_outputs "
            "(ts, doc_path, generator, prompt_hash, content_initial_sha, "
            " content_initial, cost_usd) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                _now_iso(), doc_path, generator, prompt_hash,
                _sha(content), content, cost_usd,
            ),
        )
        return cur.lastrowid or 0
    except sqlite3.Error:
        return 0
    finally:
        conn.close()


def record_f3_accept(
    *,
    doc_path: str,
    content_accepted: str,
) -> bool:
    """Link /accept event to most-recent f3_outputs row for doc_path.

    Computes `edit_distance_ratio = 1 - SequenceMatcher.ratio()` (0 = same,
    1 = completely different). No-op if no prior generation row matches —
    e.g. doc was authored by hand or accepted before W8.

    Returns True on update, False otherwise.
    """
    try:
        conn = init_db(get_db_path())
    except sqlite3.Error:
        return False
    try:
        row = conn.execute(
            "SELECT id, content_initial FROM f3_outputs "
            "WHERE doc_path = ? AND accepted_at IS NULL "
            "ORDER BY ts DESC LIMIT 1",
            (doc_path,),
        ).fetchone()
        if row is None:
            return False
        rid, initial = row
        ratio = difflib.SequenceMatcher(
            None, initial or "", content_accepted,
        ).ratio()
        edit_distance = round(1.0 - ratio, 4)
        conn.execute(
            "UPDATE f3_outputs SET "
            "content_accepted_sha = ?, content_accepted = ?, "
            "edit_distance_ratio = ?, accepted_at = ? "
            "WHERE id = ?",
            (
                _sha(content_accepted), content_accepted, edit_distance,
                _now_iso(), rid,
            ),
        )
        return True
    except sqlite3.Error:
        return False
    finally:
        conn.close()
