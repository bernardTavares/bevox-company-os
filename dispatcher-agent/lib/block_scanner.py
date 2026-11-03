"""UBN block_scanner — detecta tasks em estado de atenção do operador.

3 critérios paralelos + dedup. Roda no reaper tick (10s via override
cadence-10s.conf).

Spec: bevox-knowledge/35_specs/openclaw/2026-04-30-universal-block-notifier.md §3
"""
from __future__ import annotations

import os
import re
import importlib.util
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional

# Lazy proxy: reaper.py importa este módulo no try/except — top-level
# `from .reaper import _backoff_delay_for` cria circular import porque
# reaper ainda está mid-load nessa hora. Inline lookup quando chamado.
def _backoff_delay_for(retry_count: int) -> int:
    from .reaper import _backoff_delay_for as _impl  # lazy
    return _impl(retry_count)


@dataclass(frozen=True)
class Candidate:
    """Task que merece escalation. Imutável pra dedup safety."""
    task_id: str
    criterion: str  # "blocked" | "proposed_rejected" | "stuck_in_testing" | "stuck_in_ready"
    block_session_key: Optional[str]
    block_reason: str
    project: Optional[str]


def candidates_blocked(state: dict) -> List[Candidate]:
    """Critério 3.1: tasks com task.blocked == True."""
    out = []
    for t in state.get("tasks", []) or []:
        if t.get("blocked") is True:
            out.append(Candidate(
                task_id=t["id"],
                criterion="blocked",
                block_session_key=t.get("blocked_at"),
                block_reason=t.get("blocked_reason") or "(unknown)",
                project=t.get("project"),
            ))
    return out


TESTER_ESCALATIONS_DIR = Path(f"{Path.home()}/.openclaw/tester-agent/escalations")
PROPOSED_REJECTED_WINDOW_HOURS = 24


def _lookup_project_from_kanban(task_id: str) -> Optional[str]:
    """Lookup project pelo state.json. Retorna None se não achar."""
    import json
    try:
        state_path = Path(f"{Path.home()}/.openclaw/kanban-tasks/state.json")
        data = json.loads(state_path.read_text(encoding="utf-8"))
        for t in data.get("tasks", []):
            if t.get("id") == task_id:
                return t.get("project")
    except (OSError, json.JSONDecodeError, KeyError):
        return None
    return None


def candidates_proposed_rejected() -> List[Candidate]:
    """Critério 3.2: tester escalation files com decision proposed_rejected
    no window de 24h."""
    # Import read_escalation from tester-agent (avoid name collision with local lib.store)
    tester_store_path = f"{Path.home()}/.openclaw/tester-agent/lib/store.py"
    spec = importlib.util.spec_from_file_location("_tester_store_impl", tester_store_path)
    _tester_store = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_tester_store)

    if not TESTER_ESCALATIONS_DIR.is_dir():
        return []
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=PROPOSED_REJECTED_WINDOW_HOURS)).timestamp()
    out = []
    for path in TESTER_ESCALATIONS_DIR.glob("T-*-tr-*.md"):
        if not path.is_file() or path.stat().st_mtime < cutoff:
            continue
        data = _tester_store.read_escalation(path)
        if data is None or data.get("decision") != "proposed_rejected":
            continue
        out.append(Candidate(
            task_id=data["task_id"],
            criterion="proposed_rejected",
            block_session_key=data["test_run_id"],
            block_reason=f"proposed_rejected: {data.get('structural_concern','?')}",
            project=_lookup_project_from_kanban(data["task_id"]),
        ))
    return out


def _parse_iso(s: Optional[str]) -> Optional[datetime]:
    """Parse ISO timestamp string (with optional Z suffix) to datetime.
    Returns None on parse failure."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def candidates_stuck_testing(state: dict) -> List[Candidate]:
    """Critério 3.3: tasks em testing > threshold_min sem decisão E fora
    de backoff window do reaper resilience.

    Threshold env var: OPENCLAW_REAPER_STUCK_TESTING_THRESHOLD_MIN (default 30min).
    Exclui tasks com last_test_overall=inconclusive que estão ainda dentro
    da backoff window (REINVOKE_BACKOFF_SCHEDULE), pois estão legitimamente
    esperando próxima invocação do reaper."""
    threshold_min = int(os.environ.get(
        "OPENCLAW_REAPER_STUCK_TESTING_THRESHOLD_MIN", "30"))
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=threshold_min)
    out = []
    for t in state.get("tasks", []) or []:
        if t.get("status") != "testing" or t.get("blocked"):
            continue
        updated_at = _parse_iso(t.get("updated_at"))
        if not updated_at or updated_at >= cutoff:
            continue
        # Exclude tasks within reaper backoff window (legítima espera)
        tr = (t.get("dispatch_payload") or {}).get("test_result") or {}
        if tr.get("last_test_overall") == "inconclusive":
            last_finished = _parse_iso(tr.get("last_test_finished_at"))
            if last_finished:
                backoff_s = _backoff_delay_for(tr.get("test_run_count", 1))
                elapsed = (datetime.now(timezone.utc) - last_finished).total_seconds()
                if elapsed < backoff_s:
                    continue
        out.append(Candidate(
            task_id=t["id"],
            criterion="stuck_in_testing",
            block_session_key=t.get("updated_at"),
            block_reason=f"stuck-in-testing >{threshold_min}min",
            project=t.get("project"),
        ))
    return out


UBN_ESCALATIONS_DIR = Path(f"{Path.home()}/.openclaw/clarification-agent/escalations")
_UBN_FILENAME_RE = re.compile(r"^(T-[\w-]+?)-blk-(\d+)\.md$")


def _parse_ubn_frontmatter(path: Path) -> dict:
    """Parse frontmatter de UBN escalation file. Retorna {} se inválido."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    m = re.match(r"---\n(.*?)\n---\n", content, re.DOTALL)
    if not m:
        return {}
    data = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            data[k.strip()] = v.strip()
    return data


def find_open_escalation(candidate: Candidate) -> Optional[Path]:
    """Retorna path da escalation aberta com mesmo task_id+block_session_key,
    ou None."""
    if not UBN_ESCALATIONS_DIR.is_dir():
        return None
    expected = candidate.block_session_key or "(none)"
    for path in UBN_ESCALATIONS_DIR.glob(f"{candidate.task_id}-blk-*.md"):
        data = _parse_ubn_frontmatter(path)
        if (data.get("status") == "open"
                and data.get("block_session_key") == expected):
            return path
    return None


def next_escalation_seq(task_id: str) -> int:
    """Próximo número sequencial de escalation pra task_id."""
    if not UBN_ESCALATIONS_DIR.is_dir():
        return 1
    max_seq = 0
    for path in UBN_ESCALATIONS_DIR.glob(f"{task_id}-blk-*.md"):
        m = _UBN_FILENAME_RE.match(path.name)
        if m:
            max_seq = max(max_seq, int(m.group(2)))
    return max_seq + 1


def find_undispatched_open_escalations(
    max_age_hours: int = 24,
) -> List[tuple]:
    """Lista escalations open + dispatched_at:null + idade < max_age_hours.

    Usado pelo reaper retry loop pra re-tentar Telegram em escalations
    que foram criadas mas Telegram falhou (env vars ausentes, API down,
    bot sem acesso ao chat). Sem essa função, escalation file fica órfã
    porque dedup detecta-a como existing e scanner não re-tenta.

    Retorna list of (path, frontmatter_dict). Caller reconstrói Candidate
    a partir do frontmatter pra invocar dispatch_telegram.

    Spec: bevox-knowledge/35_specs/openclaw/2026-04-30-universal-block-notifier.md §6.7
    """
    if not UBN_ESCALATIONS_DIR.is_dir():
        return []
    cutoff_ts = (datetime.now(timezone.utc)
                 - timedelta(hours=max_age_hours)).timestamp()
    out = []
    for path in UBN_ESCALATIONS_DIR.glob("T-*-blk-*.md"):
        if not path.is_file() or path.stat().st_mtime < cutoff_ts:
            continue
        data = _parse_ubn_frontmatter(path)
        if data.get("status") != "open":
            continue
        if data.get("dispatched_at") not in ("null", "", None):
            continue
        out.append((path, data))
    return out


def candidates_stuck_ready(state: dict) -> List[Candidate]:
    """Critério F4: tasks em status=ready com sprint_id == current sprint do
    projeto, idle (updated_at) > threshold_min sem dispatch.

    Detecta sprint travada por qualquer razão (cron-dispatcher skipping,
    operator forgot, kill-switch on, etc).

    Threshold env: OPENCLAW_REAPER_STUCK_READY_THRESHOLD_MIN (default 30).
    Kill switch: 0 desabilita.
    """
    threshold_min = int(os.environ.get(
        "OPENCLAW_REAPER_STUCK_READY_THRESHOLD_MIN", "30"))
    if threshold_min == 0:
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=threshold_min)
    sprints = state.get("sprints", []) or []
    current_by_project = {
        s.get("project"): s.get("id")
        for s in sprints if s.get("state") == "current"
    }
    out = []
    for t in state.get("tasks", []) or []:
        if t.get("status") != "ready":
            continue
        proj = t.get("project")
        if not proj:
            continue
        if t.get("sprint_id") != current_by_project.get(proj):
            continue
        updated = _parse_iso(t.get("updated_at"))
        if not updated or updated >= cutoff:
            continue
        out.append(Candidate(
            task_id=t["id"],
            criterion="stuck_in_ready",
            block_session_key=t.get("updated_at"),
            block_reason=(
                f"stuck-in-ready >{threshold_min}min "
                f"(sprint current, sem dispatch)"
            ),
            project=proj,
        ))
    return out


def scan_all(state: dict) -> List[Candidate]:
    """Roda os 4 critérios + filtra candidates já com escalation aberta."""
    all_candidates = (
        candidates_blocked(state)
        + candidates_stuck_testing(state)
        + candidates_proposed_rejected()
        + candidates_stuck_ready(state)
    )
    new_candidates = []
    seen = set()
    for c in all_candidates:
        # In-tick dedup (mesma task pode hit 2 critérios) — preferir o primeiro.
        if c.task_id in seen:
            continue
        seen.add(c.task_id)
        if find_open_escalation(c) is None:
            new_candidates.append(c)
    return new_candidates
