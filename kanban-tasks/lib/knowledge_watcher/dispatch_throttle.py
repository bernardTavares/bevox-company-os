"""Dispatch throttle (W9.T2.1) — evita spam de digest Telegram em re-runs.

Cada `kind` (gap-report, retirement-scan, tune-suggest, cron-failure) tem
janela default 30min. Stamps `state.global.last_dispatch_at[<kind>]` em
record_dispatch; consultado por is_throttled antes do envio HTTP real.

Persistência via state.py write_state (atomic temp+rename). Janela
customizável por chamada (`throttle_seconds=` em is_throttled).

Use case principal: durante development session com várias re-runs
`systemctl --user start <service>`, evita re-spam do mesmo digest pra
Bernard. `--force-dispatch` flag bypassa.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Optional

from lib.knowledge_watcher import state as _state


_DEFAULT_THROTTLE_SECONDS = 30 * 60  # 30 minutes


def _now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def _now_iso() -> str:
    return _now().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_iso(s: str) -> Optional[_dt.datetime]:
    try:
        return _dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def is_throttled(
    kind: str,
    state_path: Path,
    *,
    throttle_seconds: int = _DEFAULT_THROTTLE_SECONDS,
) -> bool:
    """True if last dispatch for `kind` was less than throttle_seconds ago."""
    if not state_path.exists():
        return False
    state = _state.read_state(state_path)
    last = (state.get("global", {}) or {}).get("last_dispatch_at", {}) or {}
    stamp = last.get(kind)
    if not stamp:
        return False
    parsed = _parse_iso(stamp)
    if parsed is None:
        return False  # defensive: malformed → allow dispatch
    elapsed = (_now() - parsed).total_seconds()
    return elapsed < throttle_seconds


def record_dispatch(kind: str, state_path: Path) -> None:
    """Stamp `now` as last dispatch for `kind`. Atomic write."""
    state = _state.read_state(state_path)
    g = state.setdefault("global", {})
    last = g.setdefault("last_dispatch_at", {})
    last[kind] = _now_iso()
    _state.write_state(state_path, state)
