"""Poller: pull mode do clarification-agent.

Orquestra tick deterministico: pre-filter → fast-fail → context_load →
drafter → resolve. Zero LLM nos caminhos descartados.

Padrão inspirado em dispatcher-agent/lib/cron.py e reaper.py.
"""
import contextlib
import fcntl
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import store


CLARIFICATION_PREFIXES = (
    "clarification_required:",
    "clarification_escalation_required:",
)

DEFAULT_BUDGET_PER_TASK_PER_DAY = int(
    os.environ.get("OPENCLAW_CLR_BUDGET_PER_TASK_PER_DAY", "3"),
)


def _has_pending_clarification(task_id: str) -> bool:
    """Task tem clarification com question sem answer correspondente."""
    import re
    pat = re.compile(re.escape(task_id) + r"-clr-(\d+)\.md$")
    if not store.QUESTIONS_DIR.exists():
        return False
    for p in store.QUESTIONS_DIR.iterdir():
        m = pat.match(p.name)
        if not m:
            continue
        answer_path = store.ANSWERS_DIR / p.name
        if not answer_path.exists():
            return True
    return False


def _today_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")


def compute_dedup_hash(task_id: str, question_text: str,
                       dispatch_payload: Dict[str, Any]) -> str:
    """Hash estável pra dedup. Muda quando task_id, question OR payload-signature muda."""
    sig = {
        "task_id": task_id,
        "question": question_text.strip(),
        "spec_ref": dispatch_payload.get("spec_ref") or "",
        "ac": dispatch_payload.get("acceptance_criteria") or [],
        "goal": (dispatch_payload.get("goal") or "")[:500],
    }
    blob = json.dumps(sig, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(blob).hexdigest()


def prefilter(
    task: Dict[str, Any], *, proposed_question: Optional[str] = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """Retorna (skip, reason, detail)."""
    if not task.get("blocked"):
        return True, "not_blocked", {}
    reason = task.get("blocked_reason") or ""
    if not any(reason.startswith(p) for p in CLARIFICATION_PREFIXES):
        return True, "blocked_reason_not_clarification", {"blocked_reason": reason[:80]}
    if _has_pending_clarification(task["id"]):
        return True, "already_pending", {}

    payload = task.get("dispatch_payload") or {}
    budget = payload.get("clarification_budget") or {}
    if budget.get("day") == _today_iso() and budget.get("count_today", 0) >= budget.get("limit", DEFAULT_BUDGET_PER_TASK_PER_DAY):
        return True, "budget_exhausted", {"count": budget.get("count_today"), "limit": budget.get("limit")}

    if proposed_question is not None:
        last_hash = payload.get("clarification_dedup_hash_last")
        if last_hash:
            curr_hash = compute_dedup_hash(task["id"], proposed_question, payload)
            if curr_hash == last_hash:
                return True, "dedup_hash_match", {"hash": curr_hash}

    return False, "", {}


def is_payload_incomplete(task: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Detecta payload canonico faltando campos essenciais.

    Retorna (incomplete, missing_fields).
    """
    p = task.get("dispatch_payload") or {}
    missing = []
    spec_ref = p.get("spec_ref")
    if not spec_ref or (isinstance(spec_ref, list) and len(spec_ref) == 0):
        missing.append("spec_ref")
    ac = p.get("acceptance_criteria")
    if not ac or (isinstance(ac, list) and len(ac) == 0):
        missing.append("acceptance_criteria")
    return (len(missing) > 0, missing)


def killswitch_active() -> bool:
    return store.POLL_DISABLED.exists()


@contextlib.contextmanager
def _lock_file(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    f = open(path, "w")
    try:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield f
        except BlockingIOError:
            yield None
    finally:
        f.close()


def try_acquire_lock() -> Optional[Any]:
    """Tenta adquirir lock global. Retorna file handle ou None se contention."""
    f = open(store.POLL_LOCK, "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return f
    except BlockingIOError:
        f.close()
        return None


def make_tick_id() -> str:
    """Retorna ID unico para este tick: ISO timestamp + uuid prefix."""
    ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"{ts}-{uuid.uuid4().hex[:8]}"


def _list_blocked_tasks() -> List[Dict[str, Any]]:
    """Lê kanban-tasks state.json e retorna tasks com blocked=True."""
    kanban_state = Path(os.path.expanduser(
        "~/.openclaw/kanban-tasks/state.json"))
    if not kanban_state.exists():
        return []
    try:
        d = json.loads(kanban_state.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    tasks = d.get("tasks") or []
    return [t for t in tasks if t.get("blocked")]


def run_tick(*, once: bool = True, dry_run: bool = False,
             as_json: bool = False) -> Dict[str, Any]:
    """Orquestra um tick do poller: pre-filter → fast-fail → LLM → resolve.

    Retorna dict com resultado do tick, incluindo:
    - tick_id: ID único do tick
    - outcome: 'killswitch', 'lock_skipped', 'completed'
    - dry_run: bool
    - tasks_scanned: count
    - filtered, fast_failed, clarified_local, clarified_cloud, auto_unblocks, escalations_emitted: counts
    - decisions: list de decisões por task
    """
    import time as _time
    t_mono_start = _time.monotonic()
    tick_id = make_tick_id()

    if killswitch_active():
        if not dry_run:
            store.append_poll_event(tick_id, "tick_skipped_killswitch",
                                    {"killswitch_path": str(store.POLL_DISABLED)})
        return {"tick_id": tick_id, "outcome": "killswitch",
                "dry_run": dry_run, "tasks_scanned": 0}

    lock = try_acquire_lock()
    if lock is None:
        if not dry_run:
            store.append_poll_event(tick_id, "tick_skipped_lock", {})
        return {"tick_id": tick_id, "outcome": "lock_skipped",
                "dry_run": dry_run, "tasks_scanned": 0}

    try:
        if not dry_run:
            store.append_poll_event(tick_id, "tick_started",
                                    {"trigger": "cli", "dry_run": False})
        tasks = _list_blocked_tasks()
        if not dry_run:
            store.append_poll_event(tick_id, "tasks_blocked_scanned",
                                    {"count": len(tasks),
                                     "task_ids": [t["id"] for t in tasks]})

        summary = {
            "tick_id": tick_id, "outcome": "completed",
            "dry_run": dry_run, "tasks_scanned": len(tasks),
            "filtered": 0, "fast_failed": 0,
            "clarified_local": 0, "clarified_cloud": 0,
            "auto_unblocks": 0, "escalations_emitted": 0,
            "decisions": [],
        }

        for task in tasks:
            decision = _process_task(task, tick_id, dry_run=dry_run)
            summary["decisions"].append(decision)
            cat = decision["category"]
            if cat == "filtered": summary["filtered"] += 1
            elif cat == "fast_failed": summary["fast_failed"] += 1
            elif cat == "clarified_local_safe": summary["clarified_local"] += 1; summary["auto_unblocks"] += 1
            elif cat == "clarified_cloud_safe": summary["clarified_cloud"] += 1; summary["auto_unblocks"] += 1
            elif cat.startswith("escalated"): summary["escalations_emitted"] += 1

        if not dry_run:
            duration_ms = int((_time.monotonic() - t_mono_start) * 1000)
            store.append_poll_event(tick_id, "tick_finished", {
                "duration_ms": duration_ms,
                **{k: v for k, v in summary.items() if k != "decisions"},
            })
        return summary
    finally:
        if lock is not None:
            lock.close()


def _process_task(task: Dict[str, Any], tick_id: str, *, dry_run: bool) -> Dict[str, Any]:
    """Processa uma task individual: pre-filter → fast-fail → LLM (placeholder).

    Retorna dict com decisão da task.
    """
    skip, reason, detail = prefilter(task)
    if skip:
        if not dry_run:
            store.append_poll_event(tick_id, "poll_skipped_filter", {
                "task_id": task["id"], "reason": reason, "detail": detail,
            })
        return {"task_id": task["id"], "category": "filtered", "reason": reason}
    incomplete, missing = is_payload_incomplete(task)
    if incomplete:
        from . import lifecycle as lc
        if dry_run:
            return {"task_id": task["id"], "category": "fast_failed",
                    "missing_fields": missing, "dry_run": True}
        try:
            cid = lc.emit_payload_incomplete_escalation(task["id"], missing)
        except lc.LifecycleError as e:
            store.append_poll_event(tick_id, "fast_fail_error", {
                "task_id": task["id"], "code": e.code, "detail": e.detail[:200],
            })
            return {"task_id": task["id"], "category": "fast_fail_error"}
        store.append_poll_event(tick_id, "fast_fail_payload_incomplete", {
            "task_id": task["id"], "missing_fields": missing,
            "clarification_id": cid,
        })
        store.append_poll_event(tick_id, "unsafe_escalation_emitted", {
            "task_id": task["id"], "clarification_id": cid,
            "reason": "dispatch_payload_incomplete",
        })
        return {"task_id": task["id"], "category": "fast_failed",
                "missing_fields": missing, "clarification_id": cid}
    # LLM path — via local-first drafter
    from . import lifecycle as lc
    question = lc.extract_question_from_blocked(task.get("blocked_reason") or "")

    # Dedup-hash check (agora com proposed_question conhecido)
    skip2, reason2, detail2 = prefilter(task, proposed_question=question)
    if skip2:
        if not dry_run:
            store.append_poll_event(tick_id, "poll_skipped_filter", {
                "task_id": task["id"], "reason": reason2, "detail": detail2,
            })
        return {"task_id": task["id"], "category": "filtered", "reason": reason2}

    if dry_run:
        return {"task_id": task["id"], "category": "pending_llm",
                "dry_run": True, "question": question[:80]}

    # Acquire lock (mutates kanban; only in non-dry-run)
    if not lc.acquire_clarification_lock(task["id"], holder="clarification-poller"):
        store.append_poll_event(tick_id, "poll_skipped_filter", {
            "task_id": task["id"], "reason": "lock_held_elsewhere", "detail": {},
        })
        return {"task_id": task["id"], "category": "filtered",
                "reason": "lock_held_elsewhere"}

    try:
        result = lc.auto_draft_for_task(task["id"], question)
    except (lc.LifecycleError, Exception) as e:
        store.append_poll_event(tick_id, "auto_draft_error", {
            "task_id": task["id"], "error": str(e)[:200],
        })
        return {"task_id": task["id"], "category": "auto_draft_error"}

    # Log provider used
    ev_name = "drafter_escalated_to_cloud" if result.get("fallback_used") else "drafter_used_local"
    store.append_poll_event(tick_id, ev_name, {
        "task_id": task["id"],
        "clarification_id": result["clarification_id"],
        "provider_final": result.get("drafter_provider"),
        "outcome": result["outcome"],
    })

    if result["outcome"] == "safe":
        store.append_poll_event(tick_id, "clarification_auto_unblock", {
            "task_id": task["id"],
            "clarification_id": result["clarification_id"],
            "actor": "clarification-poller",
        })
        cat = "clarified_cloud_safe" if result.get("fallback_used") else "clarified_local_safe"
    else:
        store.append_poll_event(tick_id, "unsafe_escalation_emitted", {
            "task_id": task["id"],
            "clarification_id": result["clarification_id"],
            "reason": result.get("escalation_reason", "")[:200],
        })
        cat = "escalated_cloud" if result.get("fallback_used") else "escalated_local"

    return {"task_id": task["id"], "category": cat, **result}
