"""Aggregated feedback queries (W8.P4.T4.1) — drives CLI + MC + tune-suggest.

All queries are read-only and time-windowed by `days`. Default 30d. Returns
list of dicts (JSON-serializable). Empty results → empty list (not None).
"""
from __future__ import annotations

import datetime as _dt
import json as _json
import sqlite3
from typing import Dict, List, Tuple

from lib.knowledge_watcher.feedback_db import get_db_path


def _connect() -> sqlite3.Connection:
    return sqlite3.connect(str(get_db_path()))


def _since(days: int) -> str:
    cutoff = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=days)
    return cutoff.replace(microsecond=0).isoformat() + "Z"


def stats_by_doc_type(days: int = 30) -> List[Dict]:
    """Per doc_type: total + keep_ratio + retire_ratio + keep_permanent_ratio.

    Sorted by descending sample size.
    """
    try:
        conn = _connect()
    except sqlite3.Error:
        return []
    try:
        rows = conn.execute(
            "SELECT doc_type, decision, COUNT(*) AS n "
            "FROM decisions "
            "WHERE ts >= ? AND doc_type IS NOT NULL "
            "GROUP BY doc_type, decision",
            (_since(days),),
        ).fetchall()
    except sqlite3.Error:
        return []
    finally:
        conn.close()

    by_type: Dict[str, Dict[str, int]] = {}
    for dt, dec, n in rows:
        by_type.setdefault(dt, {})[dec] = n
    out = []
    for dt, decs in by_type.items():
        total = sum(decs.values())
        if total == 0:
            continue
        out.append({
            "doc_type": dt,
            "n": total,
            "keep_ratio": round(decs.get("keep", 0) / total, 3),
            "retire_ratio": round(decs.get("retire", 0) / total, 3),
            "keep_permanent_ratio": round(
                decs.get("keep_permanent", 0) / total, 3,
            ),
            "dismiss_ratio": round(decs.get("dismiss", 0) / total, 3),
            "accept_ratio": round(decs.get("accept", 0) / total, 3),
            "postpone_ratio": round(decs.get("postpone", 0) / total, 3),
        })
    return sorted(out, key=lambda r: -r["n"])


def stats_f3_edit_distance(days: int = 30) -> List[Dict]:
    """Per generator: p50, p90, mean edit_distance_ratio + n_accepted."""
    try:
        conn = _connect()
    except sqlite3.Error:
        return []
    try:
        rows = conn.execute(
            "SELECT generator, edit_distance_ratio "
            "FROM f3_outputs "
            "WHERE accepted_at IS NOT NULL "
            "  AND accepted_at >= ? "
            "  AND edit_distance_ratio IS NOT NULL",
            (_since(days),),
        ).fetchall()
    except sqlite3.Error:
        return []
    finally:
        conn.close()

    by_gen: Dict[str, List[float]] = {}
    for gen, dist in rows:
        by_gen.setdefault(gen, []).append(float(dist))
    out = []
    for gen, vals in by_gen.items():
        if not vals:
            continue
        vals_sorted = sorted(vals)
        n = len(vals_sorted)
        p50 = vals_sorted[min(n // 2, n - 1)]
        p90 = vals_sorted[min(int(n * 0.9), n - 1)]
        out.append({
            "generator": gen,
            "n": n,
            "p50": round(p50, 3),
            "p90": round(p90, 3),
            "mean": round(sum(vals) / n, 3),
        })
    return sorted(out, key=lambda r: -r["n"])


def _combo_key(signals_json: str) -> str:
    """Canonical combo: alphabetical category prefixes joined with '+'."""
    try:
        sigs = _json.loads(signals_json or "[]")
    except _json.JSONDecodeError:
        sigs = []
    cats = sorted({
        (s.get("category") or "").split("_")[0]
        for s in sigs if s.get("category")
    })
    return "+".join(c for c in cats if c) or "none"


def stats_by_signal_combo(
    days: int = 30, min_n: int = 4,
) -> List[Dict]:
    """Per (doc_type, signal_combo): keep_ratio + retire_ratio. Filtered by min_n.

    Used by tune-suggest to find patterns where humans consistently keep.
    """
    try:
        conn = _connect()
    except sqlite3.Error:
        return []
    try:
        rows = conn.execute(
            "SELECT doc_type, signals_json, decision "
            "FROM decisions "
            "WHERE ts >= ? AND doc_type IS NOT NULL",
            (_since(days),),
        ).fetchall()
    except sqlite3.Error:
        return []
    finally:
        conn.close()

    by_key: Dict[Tuple[str, str], Dict[str, int]] = {}
    for dt, sj, dec in rows:
        k = (dt, _combo_key(sj))
        bucket = by_key.setdefault(k, {})
        bucket[dec] = bucket.get(dec, 0) + 1

    out = []
    for (dt, combo), decs in by_key.items():
        total = sum(decs.values())
        if total < min_n:
            continue
        out.append({
            "doc_type": dt,
            "signal_combo": combo,
            "n": total,
            "keep_ratio": round(decs.get("keep", 0) / total, 3),
            "retire_ratio": round(decs.get("retire", 0) / total, 3),
            "keep_permanent_ratio": round(
                decs.get("keep_permanent", 0) / total, 3,
            ),
        })
    return sorted(out, key=lambda r: -r["n"])
