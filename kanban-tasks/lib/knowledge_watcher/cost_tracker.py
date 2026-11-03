"""F3 cost tracking — accumulate per-month spend in state.json.

W8.T1.2 — bootstrap_project() retorna total_cost_usd; runner ou cmd_bootstrap
records via record_f3_cost(). MC reads via read_cost_summary() para surfacing
em Watcher · Status (F3 cost MTD: $X.XX / $5 budget).

Reset mensal automático (history dict: "YYYY-MM" → cumulative usd). lifetime
total acumula sem reset.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Any, Dict, Optional

from lib.knowledge_watcher import state as _state


_DEFAULT_BUDGET_MONTHLY_USD = 5.0


def _today_str() -> str:
    return _dt.date.today().isoformat()


def _month_key(today: Optional[str]) -> str:
    """'YYYY-MM-DD' → 'YYYY-MM'. Accepts None → today."""
    return (today or _today_str())[:7]


def record_f3_cost(
    state_path: Path,
    cost_usd: float,
    *,
    today: Optional[str] = None,
) -> None:
    """Accumulate cost in state.json global block. Atomic via state.write_state.

    No-op if cost_usd <= 0 (avoids cluttering history with empty months).
    """
    if cost_usd <= 0:
        return
    state = _state.read_state(state_path)
    g = state.setdefault("global", {})
    history = g.setdefault("f3_cost_history", {})
    month = _month_key(today)
    history[month] = round(history.get(month, 0.0) + cost_usd, 4)
    g["f3_cost_total_lifetime_usd"] = round(
        g.get("f3_cost_total_lifetime_usd", 0.0) + cost_usd, 4,
    )
    _state.write_state(state_path, state)


def read_cost_summary(
    state_path: Path,
    *,
    today: Optional[str] = None,
    budget_monthly_usd: float = _DEFAULT_BUDGET_MONTHLY_USD,
) -> Dict[str, Any]:
    """Return MTD + lifetime + remaining budget for the given month."""
    if not state_path.exists():
        return {
            "f3_cost_mtd_usd": 0.0,
            "f3_cost_lifetime_usd": 0.0,
            "budget_remaining_mtd_usd": budget_monthly_usd,
            "budget_monthly_usd": budget_monthly_usd,
        }
    state = _state.read_state(state_path)
    g = state.get("global", {}) or {}
    history = g.get("f3_cost_history", {}) or {}
    mtd = float(history.get(_month_key(today), 0.0))
    lifetime = float(g.get("f3_cost_total_lifetime_usd", 0.0))
    return {
        "f3_cost_mtd_usd": round(mtd, 4),
        "f3_cost_lifetime_usd": round(lifetime, 4),
        "budget_remaining_mtd_usd": round(max(budget_monthly_usd - mtd, 0.0), 4),
        "budget_monthly_usd": budget_monthly_usd,
    }
