"""Task logic: CRUD, move (status/sprint), archive, block/unblock, reopen."""

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import sprint as sprint_lib
from . import store
from . import transitions

# Status enum canonico (sem `todo`; `archived` e ortogonal).
VALID_STATUS = transitions.STATUS_ENUM + ("archived",)

# F2: Escalation cleanup directories
UBN_CLR_ESCALATIONS_DIR = Path(f"{Path.home()}/.openclaw/clarification-agent/escalations")
TESTER_ESCALATIONS_DIR = Path(f"{Path.home()}/.openclaw/tester-agent/escalations")
TERMINAL_STATUSES = ("done", "rejected", "archived")


class TaskError(Exception):
    """Raised em erros semanticos de task ops (wave-5+).

    Attr `code` para mapping a exit code / HTTP status.
    Canonical codes: CYCLE_DETECTED, PRED_NOT_FOUND, TASK_NOT_FOUND,
    BLOCKED_BY_INVALID, BLOCKED_BY_UNRESOLVED.
    """

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _next_task_seq(state: Dict[str, Any]) -> int:
    max_n = 0
    for t in state["tasks"]:
        tid = t["id"]
        if tid.startswith("T-"):
            try:
                n = int(tid[2:])
                max_n = max(max_n, n)
            except ValueError:
                continue
    return max_n + 1


def _resolve_sprint_id(state: Dict[str, Any], sprint_arg: str,
                       project: Optional[str] = None) -> str:
    """Resolve aliases (current/next) com project obrigatório, ou literal id."""
    sp = sprint_lib.find_sprint(state, sprint_arg, project=project)
    if sp is None:
        raise ValueError(f"sprint not found: {sprint_arg} (project={project!r})")
    return sp["id"]


def find_task(state: Dict[str, Any], task_id: str) -> Optional[Dict[str, Any]]:
    for t in state["tasks"]:
        if t["id"] == task_id:
            return t
    return None


def create(
    title: str,
    sprint: str = "current",
    project: Optional[str] = None,
    epic_id: Optional[str] = None,
    wave_ref: Optional[str] = None,
    description: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    actor: str = "bernard",
) -> Dict[str, Any]:
    if not title or not title.strip():
        raise ValueError("title is required")
    with store.mutate_state() as state:
        sprint_id = _resolve_sprint_id(state, sprint, project=project)
        if project is not None and project not in state["projects"]:
            raise ValueError(f"unknown project: {project}")
        # Invariant: sprint.project == task.project (skip for legacy sprints with project=None)
        sp = sprint_lib.find_sprint(state, sprint_id)
        if sp is None:
            raise ValueError(f"sprint not found: {sprint_id}")
        if sp.get("project") is not None and sp["project"] != project:
            raise ValueError(
                f"INVALID_SPRINT_PROJECT_MISMATCH: sprint={sprint_id} "
                f"belongs to project={sp['project']!r}, task project={project!r}"
            )
        seq_id = _next_task_seq(state)
        tid = f"T-{seq_id:04d}"
        ts = store.now_iso()
        task = {
            "id": tid,
            "title": title.strip(),
            "description": description or "",
            "status": "backlog",
            "sprint_id": sprint_id,
            "project": project,
            "epic_id": epic_id,
            "wave_ref": wave_ref,
            "created_at": ts,
            "updated_at": ts,
            "created_by": actor,
            "archived_at": None,
            # Wave-3 fields:
            "blocked": False,
            "blocked_reason": None,
            "blocked_at": None,
            "rejected_reason": None,
            "dispatch_payload": payload if payload else None,
            "test_result": None,
        }
        state["tasks"].append(task)
        seq = store.next_seq(state)
        payload_keys = sorted(payload.keys()) if isinstance(payload, dict) else []
        store.append_event({
            "seq": seq, "ts": ts, "type": "task_created", "actor": actor,
            "task_id": tid, "sprint_id": sprint_id, "title": task["title"],
            "project": project, "epic_id": epic_id, "wave_ref": wave_ref,
            "payload_keys": payload_keys,
        })
        state["last_event_seq"] = seq
        return {"ok": True, "task": task}


def update(
    task_id: str,
    actor: str = "bernard",
    **fields: Any,
) -> Dict[str, Any]:
    """fields: title, description, project, epic_id, wave_ref, clear_project."""
    with store.mutate_state() as state:
        t = find_task(state, task_id)
        if t is None:
            raise ValueError(f"task not found: {task_id}")
        changed: Dict[str, Any] = {}

        if fields.pop("clear_project", False):
            if t["project"] is not None:
                changed["project"] = None
                t["project"] = None
        if "project" in fields and fields["project"] is not None:
            new_p = fields["project"]
            if new_p not in state["projects"]:
                raise ValueError(f"unknown project: {new_p}")
            if t["project"] != new_p:
                changed["project"] = new_p
                t["project"] = new_p
        for f in ("title", "description", "epic_id", "wave_ref"):
            if f in fields and fields[f] is not None:
                if t.get(f) != fields[f]:
                    changed[f] = fields[f]
                    t[f] = fields[f]

        if not changed:
            return {"ok": True, "noop": True, "task": t}

        t["updated_at"] = store.now_iso()
        seq = store.next_seq(state)
        store.append_event({
            "seq": seq, "ts": store.now_iso(), "type": "task_updated",
            "actor": actor, "task_id": task_id, "fields_changed": changed,
        })
        state["last_event_seq"] = seq
        return {"ok": True, "noop": False, "task": t}


def move_status(
    task_id: str,
    status: str,
    actor: str = "bernard",
    force: bool = False,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Move task status com whitelist soft. Emite satellites quando aplicavel."""
    if status not in transitions.STATUS_ENUM:
        raise ValueError(
            f"invalid status: {status} (use archive/unarchive for archived; "
            f"valid: {transitions.STATUS_ENUM})"
        )
    with store.mutate_state() as state:
        t = find_task(state, task_id)
        if t is None:
            raise ValueError(f"task not found: {task_id}")
        if t["status"] == "archived":
            raise ValueError("task is archived; unarchive first")
        if t["status"] == status:
            return {"ok": True, "noop": True, "task": t}
        old = t["status"]
        # Wave-5 gate: can_move_to_ready (AND semantics: todos preds done).
        if status == "ready":
            ok_ready, missing = transitions.can_move_to_ready(t, state)
            if not ok_ready:
                raise TaskError(
                    "BLOCKED_BY_UNRESOLVED",
                    f"preds nao done: {missing}",
                )
        # blocked task indo para terminal: bloquear ANTES da whitelist
        # (regra dura, nao bypassavel com --force)
        if status in transitions.TERMINAL and t.get("blocked"):
            raise ValueError(
                "MUST_UNBLOCK_BEFORE_TERMINAL: task is blocked; "
                "run `task unblock` before moving to terminal"
            )
        # Mover task terminal sempre exige force ou reason
        if transitions.is_terminal(old):
            if not force and (not reason or not reason.strip()):
                raise ValueError(
                    f"TERMINAL_MOVE_REQUIRES_FORCE_OR_REASON: task is in terminal "
                    f"status '{old}'; use `task reopen` cmd or pass --force/--reason"
                )
        # Validacao whitelist soft
        transitions.validate_or_raise(
            old, status, force=force, reason=reason, actor=actor
        )
        # rejected_reason populado quando movendo pra rejected (precisa reason)
        if status == "rejected":
            if not reason or not reason.strip():
                raise ValueError(
                    "REJECTED_REQUIRES_REASON: moving to 'rejected' requires --reason"
                )
            t["rejected_reason"] = reason.strip()
        # Aplica
        t["status"] = status
        ts = store.now_iso()
        t["updated_at"] = ts
        # Evento principal
        seq = store.next_seq(state)
        ev_main: Dict[str, Any] = {
            "seq": seq, "ts": ts, "type": "task_moved",
            "actor": actor, "task_id": task_id, "from": old, "to": status,
        }
        if force:
            ev_main["forced"] = True
        if reason and reason.strip():
            ev_main["reason"] = reason.strip()
        store.append_event(ev_main)
        state["last_event_seq"] = seq
        # Satellites
        if status == "testing":
            seq2 = store.next_seq(state)
            store.append_event({
                "seq": seq2, "ts": ts, "type": "task_entered_testing",
                "actor": actor, "task_id": task_id, "from": old,
            })
            state["last_event_seq"] = seq2
        elif status == "rejected":
            seq2 = store.next_seq(state)
            store.append_event({
                "seq": seq2, "ts": ts, "type": "task_rejected_with_reason",
                "actor": actor, "task_id": task_id, "from": old,
                "reason": reason.strip(),
            })
            state["last_event_seq"] = seq2
        # Wave-5 atomic hooks (dentro do mesmo mutate_state).
        if status == "done":
            _auto_release_dependents(state, task_id, actor)
        elif status == "rejected":
            _block_dependents_upstream_failed(state, task_id, "rejected", actor)
        # F2: escalation cleanup hook
        if status in TERMINAL_STATUSES:
            _auto_close_escalations(state, task_id, status, actor)
        return {"ok": True, "noop": False, "task": t}


# Wave-5 convenience alias: canonical name per spec §3 is `move`. Preserves
# back-compat com calls a `move_status` (API, CLI wrappers existentes).
move = move_status


def move_sprint(task_id: str, sprint_arg: str, actor: str = "bernard") -> Dict[str, Any]:
    with store.mutate_state() as state:
        t = find_task(state, task_id)
        if t is None:
            raise ValueError(f"task not found: {task_id}")
        task_project = t.get("project")
        new_sid = _resolve_sprint_id(state, sprint_arg, project=task_project)
        if t["sprint_id"] == new_sid:
            return {"ok": True, "noop": True, "task": t}
        # Invariant: sprint.project == task.project (skip for legacy sprints with project=None)
        new_sp = sprint_lib.find_sprint(state, new_sid)
        if new_sp is None:
            raise ValueError(f"sprint not found: {new_sid}")
        if new_sp.get("project") is not None and new_sp["project"] != task_project:
            raise ValueError(
                f"INVALID_SPRINT_PROJECT_MISMATCH: sprint={new_sid} "
                f"belongs to project={new_sp['project']!r}, task project={task_project!r}"
            )
        old = t["sprint_id"]
        t["sprint_id"] = new_sid
        t["updated_at"] = store.now_iso()
        seq = store.next_seq(state)
        store.append_event({
            "seq": seq, "ts": store.now_iso(), "type": "task_resprinted",
            "actor": actor, "task_id": task_id,
            "from_sprint_id": old, "to_sprint_id": new_sid,
        })
        state["last_event_seq"] = seq
        return {"ok": True, "noop": False, "task": t}


def archive(task_id: str, actor: str = "bernard") -> Dict[str, Any]:
    with store.mutate_state() as state:
        t = find_task(state, task_id)
        if t is None:
            raise ValueError(f"task not found: {task_id}")
        if t["status"] == "archived":
            return {"ok": True, "noop": True, "task": t}
        ts = store.now_iso()
        # Auto-unblock antes de archive (invariant: archived nunca tem blocked=true)
        if t.get("blocked"):
            t["blocked"] = False
            t["blocked_reason"] = None
            t["blocked_at"] = None
            seq_unblock = store.next_seq(state)
            store.append_event({
                "seq": seq_unblock, "ts": ts, "type": "task_unblocked",
                "actor": actor, "task_id": task_id,
            })
            state["last_event_seq"] = seq_unblock
        t["status"] = "archived"
        t["archived_at"] = ts
        t["updated_at"] = ts
        seq = store.next_seq(state)
        store.append_event({
            "seq": seq, "ts": ts, "type": "task_archived",
            "actor": actor, "task_id": task_id,
        })
        state["last_event_seq"] = seq
        # Wave-5 atomic hook: downstream dependents marcados upstream_failed.
        _block_dependents_upstream_failed(state, task_id, "archived", actor)
        # F2: escalation cleanup hook
        _auto_close_escalations(state, task_id, "archived", actor)
        return {"ok": True, "task": t}


def unarchive(task_id: str, status: str = "backlog", actor: str = "bernard") -> Dict[str, Any]:
    if status not in transitions.STATUS_ENUM:
        raise ValueError(
            f"invalid restore status: {status} (valid: {transitions.STATUS_ENUM})"
        )
    with store.mutate_state() as state:
        t = find_task(state, task_id)
        if t is None:
            raise ValueError(f"task not found: {task_id}")
        if t["status"] != "archived":
            return {"ok": True, "noop": True, "task": t}
        t["status"] = status
        t["archived_at"] = None
        t["updated_at"] = store.now_iso()
        seq = store.next_seq(state)
        store.append_event({
            "seq": seq, "ts": store.now_iso(), "type": "task_unarchived",
            "actor": actor, "task_id": task_id, "restored_to": status,
        })
        state["last_event_seq"] = seq
        return {"ok": True, "task": t}


def list_tasks(
    sprint: Optional[str] = None,
    status: Optional[str] = None,
    project: Optional[str] = None,
    epic_id: Optional[str] = None,
    archived: bool = False,
    blocked: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    state = store.read_state()
    out: List[Dict[str, Any]] = []
    sprint_id_filter: Optional[str] = None
    if sprint is not None:
        sp = sprint_lib.find_sprint(state, sprint, project=project)
        if sp is None:
            raise ValueError(f"sprint not found: {sprint} (project={project!r})")
        sprint_id_filter = sp["id"]
    for t in state["tasks"]:
        is_archived = t["status"] == "archived"
        if status is not None:
            if t["status"] != status:
                continue
        else:
            if archived and not is_archived:
                continue
            if not archived and is_archived:
                continue
        if sprint_id_filter and t["sprint_id"] != sprint_id_filter:
            continue
        if project and t.get("project") != project:
            continue
        if epic_id and t.get("epic_id") != epic_id:
            continue
        if blocked is not None and bool(t.get("blocked", False)) != blocked:
            continue
        out.append(t)
    return out


def block(task_id: str, reason: str, actor: str = "bernard") -> Dict[str, Any]:
    """Set blocked=True. Requer reason nao-vazio. Rejeita em status terminal."""
    if not reason or not reason.strip():
        raise ValueError("reason is required for block")
    with store.mutate_state() as state:
        t = find_task(state, task_id)
        if t is None:
            raise ValueError(f"task not found: {task_id}")
        if t["status"] == "archived":
            raise ValueError("task is archived; unarchive first")
        if not transitions.is_blockable(t["status"]):
            raise ValueError(
                f"BLOCKED_NOT_ALLOWED_ON_TERMINAL: cannot block task in status '{t['status']}'"
            )
        if t.get("blocked"):
            return {"ok": True, "noop": True, "task": t}
        ts = store.now_iso()
        t["blocked"] = True
        t["blocked_reason"] = reason.strip()
        t["blocked_at"] = ts
        t["updated_at"] = ts
        seq = store.next_seq(state)
        store.append_event({
            "seq": seq, "ts": ts, "type": "task_blocked",
            "actor": actor, "task_id": task_id, "reason": reason.strip(),
        })
        state["last_event_seq"] = seq
        return {"ok": True, "noop": False, "task": t}


def unblock(task_id: str, actor: str = "bernard") -> Dict[str, Any]:
    """Set blocked=False. Idempotente em not-blocked."""
    with store.mutate_state() as state:
        t = find_task(state, task_id)
        if t is None:
            raise ValueError(f"task not found: {task_id}")
        if t["status"] == "archived":
            raise ValueError("task is archived; unarchive first")
        if not t.get("blocked"):
            return {"ok": True, "noop": True, "task": t}
        ts = store.now_iso()
        t["blocked"] = False
        t["blocked_reason"] = None
        t["blocked_at"] = None
        t["updated_at"] = ts
        seq = store.next_seq(state)
        store.append_event({
            "seq": seq, "ts": ts, "type": "task_unblocked",
            "actor": actor, "task_id": task_id,
        })
        state["last_event_seq"] = seq
        return {"ok": True, "noop": False, "task": t}


def reopen(
    task_id: str,
    to_status: str,
    reason: str,
    actor: str = "bernard",
) -> Dict[str, Any]:
    """Reabre task terminal. `to_status` deve ser nao-terminal. `reason` obrigatorio."""
    if to_status not in transitions.STATUS_ENUM:
        raise ValueError(f"invalid to status: {to_status}")
    if transitions.is_terminal(to_status):
        raise ValueError(f"cannot reopen to terminal status: {to_status}")
    if not reason or not reason.strip():
        raise ValueError("reason is required for reopen")
    with store.mutate_state() as state:
        t = find_task(state, task_id)
        if t is None:
            raise ValueError(f"task not found: {task_id}")
        if t["status"] == "archived":
            raise ValueError("task is archived; unarchive first")
        if not transitions.is_terminal(t["status"]):
            raise ValueError(
                f"TASK_NOT_TERMINAL: task is in '{t['status']}'; reopen only valid from terminal"
            )
        old = t["status"]
        ts = store.now_iso()
        t["status"] = to_status
        if old == "rejected":
            t["rejected_reason"] = None
        t["updated_at"] = ts
        seq = store.next_seq(state)
        store.append_event({
            "seq": seq, "ts": ts, "type": "task_reopened",
            "actor": actor, "task_id": task_id, "from": old,
            "to": to_status, "reason": reason.strip(),
        })
        state["last_event_seq"] = seq
        return {"ok": True, "noop": False, "task": t}


def set_dispatch_payload(
    task_id: str,
    payload: Dict[str, Any],
    merge: bool = False,
    actor: str = "bernard",
) -> Dict[str, Any]:
    """Set task.dispatch_payload.

    Modos:
    - replace (default): substitui dispatch_payload inteiro pelo payload novo.
    - merge=True: **shallow merge top-level**. Chave por chave, o valor novo
      substitui o valor antigo. Arrays e scalars sao substituidos por
      inteiro (NAO ha deep merge de dicts nem concatenacao de arrays).

    Rejeita em status='archived'.

    Wave-5 gate: se new_payload contem blocked_by, aplica validacao de formato,
    existencia de preds e cycle detection antes da mutacao.

    Evento emitido: task_dispatch_payload_set, carregando payload completo
    + merge flag + keys_set. Rebuild puro de events.jsonl reconstroi
    dispatch_payload corretamente (contrato operacional pra agents).
    """
    if not isinstance(payload, dict):
        raise ValueError(f"payload must be dict, got {type(payload).__name__}")
    with store.mutate_state() as state:
        t = find_task(state, task_id)
        if t is None:
            raise ValueError(f"task not found: {task_id}")
        if t["status"] == "archived":
            raise ValueError("task is archived; unarchive first")
        existing = t.get("dispatch_payload") or {}
        if merge:
            # Shallow merge top-level: valor novo substitui chave por chave.
            new_payload = {**existing, **payload}
        else:
            new_payload = payload

        # ========= Wave-5 cycle gate (fechamento do loophole) =========
        if "blocked_by" in new_payload:
            bb = new_payload.get("blocked_by")
            # 1. Format validation.
            valid, errors = transitions.validate_blocked_by_field(bb)
            if not valid:
                raise TaskError(
                    "BLOCKED_BY_INVALID",
                    f"blocked_by formato invalido: {errors}",
                )
            # 2. Pred existence.
            by_id = {x["id"]: x for x in state["tasks"]}
            missing_preds = [p for p in (bb or []) if p not in by_id]
            if missing_preds:
                raise TaskError(
                    "PRED_NOT_FOUND",
                    f"preds nao existem: {missing_preds}",
                )
            # 3. Cycle detect.
            cycle = transitions.detect_cycle(state, task_id, bb or [])
            if cycle:
                raise TaskError(
                    "CYCLE_DETECTED",
                    f"ciclo detectado: {' -> '.join(cycle)}",
                )
        # ==============================================================

        keys_set = sorted(payload.keys())
        t["dispatch_payload"] = new_payload
        ts = store.now_iso()
        t["updated_at"] = ts
        seq = store.next_seq(state)
        store.append_event({
            "seq": seq, "ts": ts, "type": "task_dispatch_payload_set",
            "actor": actor, "task_id": task_id,
            "payload": payload, "merge": merge, "keys_set": keys_set,
        })
        state["last_event_seq"] = seq
        return {"ok": True, "noop": False, "task": t}


# ============ Project management ============

def add_project(name: str, actor: str = "bernard") -> Dict[str, Any]:
    if not name or not name.strip():
        raise ValueError("project name required")
    name = name.strip()
    with store.mutate_state() as state:
        if name in state["projects"]:
            return {"ok": True, "noop": True, "name": name}
        state["projects"].append(name)
        store.write_projects(state["projects"])
        seq = store.next_seq(state)
        store.append_event({
            "seq": seq, "ts": store.now_iso(), "type": "project_added",
            "actor": actor, "project_name": name,
        })
        state["last_event_seq"] = seq
        return {"ok": True, "name": name}


# ============ Blocked-by (wave-5) ============


def _auto_release_dependents(state: Dict[str, Any], trigger_pred_id: str, actor: str) -> None:
    """Hook atomic: trigger_pred virou done. Varre dependentes; se TODOS
    os preds agora done, promove pra ready (+unblock se flag blocked).

    Emite task_blocked_by_auto_released com payload nested. Chamado DENTRO
    do mesmo mutate_state do task_moved que triggerou.
    """
    for t in state["tasks"]:
        preds = (t.get("dispatch_payload") or {}).get("blocked_by") or []
        if trigger_pred_id not in preds:
            continue
        if t.get("status") not in ("backlog", "ready"):
            continue
        ok, _missing = transitions.can_move_to_ready(t, state)
        if not ok:
            continue
        if t.get("status") != "ready":
            t["status"] = "ready"
        t["updated_at"] = store.now_iso()
        if t.get("blocked"):
            t["blocked"] = False
            t["blocked_reason"] = None
            t["blocked_at"] = None
        seq = store.next_seq(state)
        state["last_event_seq"] = seq
        store.append_event({
            "seq": seq, "ts": store.now_iso(),
            "type": "task_blocked_by_auto_released",
            "actor": actor or "system",
            "payload": {
                "task_id": t["id"],
                "trigger_pred": trigger_pred_id,
                "preds": list(preds),
            },
        })


def _block_dependents_upstream_failed(
    state: Dict[str, Any],
    trigger_pred_id: str,
    failure_status: str,
    actor: str,
) -> None:
    """Hook atomic: trigger_pred virou rejected OR foi archived. Marca
    dependentes nao-terminais como blocked com reason upstream_rejected.
    Emite task_blocked_upstream_failed com payload nested.
    """
    for t in state["tasks"]:
        preds = (t.get("dispatch_payload") or {}).get("blocked_by") or []
        if trigger_pred_id not in preds:
            continue
        if t.get("status") in ("done", "rejected") or t.get("archived_at"):
            continue  # terminal; nao mexe
        t["blocked"] = True
        t["blocked_reason"] = f"upstream_rejected: {trigger_pred_id}"
        t["blocked_at"] = store.now_iso()
        t["updated_at"] = store.now_iso()
        dp = dict(t.get("dispatch_payload") or {})
        dp["upstream_failure"] = {
            "failed_pred": trigger_pred_id,
            "failure_status": failure_status,
            "detected_at": store.now_iso(),
        }
        t["dispatch_payload"] = dp
        seq = store.next_seq(state)
        state["last_event_seq"] = seq
        store.append_event({
            "seq": seq, "ts": store.now_iso(),
            "type": "task_blocked_upstream_failed",
            "actor": actor or "system",
            "payload": {
                "task_id": t["id"],
                "failed_pred": trigger_pred_id,
                "failure_status": failure_status,
            },
        })


def _rewrite_ubn_status_to_closed(path: Path) -> bool:
    """Rewrite frontmatter status:open → status:closed_task_resolved.
    Idempotent: returns False se já estava closed_task_resolved ou não open.

    Limitation: regex-based, assumes UBN file convention (bare scalar
    'status: open' on own line, no quotes/comments). Quoted forms
    ('status: "open"') ou comments após valor são silently noop —
    seguros (não corrompem), só não tocam.
    """
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return False
    m = re.match(r"(---\n)(.*?)(\n---\n)", content, re.DOTALL)
    if not m:
        return False
    fm = m.group(2)
    if "status: closed_task_resolved" in fm:
        return False
    new_fm = re.sub(
        r"^status:\s*open\s*$",
        "status: closed_task_resolved",
        fm,
        flags=re.MULTILINE,
    )
    if new_fm == fm:
        return False
    new_content = m.group(1) + new_fm + m.group(3) + content[m.end():]
    path.write_text(new_content, encoding="utf-8")
    return True


def _move_orphan_to_resolved(path: Path, esc_dir: Path) -> Path:
    """Move file pra <esc_dir>/_resolved-YYYYMMDD/<filename>.
    Cria diretório se não existir. Se destino já existe (mesmo file movido
    em backfill anterior do mesmo dia), adiciona sufixo numérico (-2, -3, ...).
    Retorna novo path."""
    resolved_dir = esc_dir / f"_resolved-{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    resolved_dir.mkdir(exist_ok=True)
    new_path = resolved_dir / path.name
    if new_path.exists():
        # Collision: stem-N.ext
        stem = path.stem
        suffix = path.suffix
        n = 2
        while True:
            new_path = resolved_dir / f"{stem}-{n}{suffix}"
            if not new_path.exists():
                break
            n += 1
    path.rename(new_path)
    return new_path


def _auto_close_escalations(
    state: Dict[str, Any], task_id: str, new_status: str, actor: str
) -> Dict[str, Any]:
    """Hook: task entrou em terminal status. Fecha/arquiva files relacionadas.

    UBN -blk- files: rewrite frontmatter status: open → closed_task_resolved
    -clr- e -tr- files em escalations/: mv pra _resolved-YYYYMMDD/ (Phase 2.4)
    Question/answer files: leave alone (history)

    Emite evento task_escalations_auto_closed se houver mudança.

    Trade-off: roda DENTRO de mutate_state() pra atomicidade com state change,
    o que estende o tempo de lock com filesystem I/O. Aceitável pra N pequeno
    (1-5 escalation files típico). Se N crescer, considerar batch outside lock.

    Returns: {affected_files: [...], errors: [...]}
    """
    if new_status not in TERMINAL_STATUSES:
        return {"affected_files": [], "errors": []}
    affected = []
    errors = []

    # -blk- files: rewrite frontmatter status: open → closed_task_resolved
    if UBN_CLR_ESCALATIONS_DIR.is_dir():
        for path in UBN_CLR_ESCALATIONS_DIR.glob(f"{task_id}-blk-*.md"):
            try:
                if _rewrite_ubn_status_to_closed(path):
                    affected.append({
                        "path": str(path),
                        "action": "frontmatter_closed",
                    })
            except OSError as e:
                errors.append({"path": str(path), "error": str(e)})

    # -clr- files orphan in clarification-agent/escalations/
    if UBN_CLR_ESCALATIONS_DIR.is_dir():
        for path in UBN_CLR_ESCALATIONS_DIR.glob(f"{task_id}-clr-*.md"):
            try:
                new_path = _move_orphan_to_resolved(path, UBN_CLR_ESCALATIONS_DIR)
                affected.append({
                    "path": str(new_path),
                    "action": "moved_to_resolved",
                })
            except OSError as e:
                errors.append({"path": str(path), "error": str(e)})

    # -tr- files orphan in tester-agent/escalations/
    if TESTER_ESCALATIONS_DIR.is_dir():
        for path in TESTER_ESCALATIONS_DIR.glob(f"{task_id}-tr-*.md"):
            try:
                new_path = _move_orphan_to_resolved(path, TESTER_ESCALATIONS_DIR)
                affected.append({
                    "path": str(new_path),
                    "action": "moved_to_resolved",
                })
            except OSError as e:
                errors.append({"path": str(path), "error": str(e)})

    if affected:
        seq = store.next_seq(state)
        state["last_event_seq"] = seq
        store.append_event({
            "seq": seq, "ts": store.now_iso(),
            "type": "task_escalations_auto_closed",
            "actor": actor or "system",
            "payload": {
                "task_id": task_id,
                "new_status": new_status,
                "affected_files": affected,
                "errors": errors,
            },
        })
    return {"affected_files": affected, "errors": errors}


def set_blocked_by(
    task_id: str,
    preds: List[str],
    actor: str = "unknown",
) -> Dict[str, Any]:
    """Central write-path para blocked_by.

    Aplica, nesta ordem:
      1. validacao de formato (fail-fast, antes do lock)
      2. existencia da target task
      3. existencia de todos os preds
      4. cycle detect universal (inclui a proposta no grafo)
      5. mutacao + emissao de evento DENTRO do mesmo mutate_state (atomic)

    Args:
        task_id: target task.
        preds: list[str] de task_ids (preds).
        actor: quem origina.

    Raises:
        TaskError(BLOCKED_BY_INVALID|TASK_NOT_FOUND|PRED_NOT_FOUND|CYCLE_DETECTED).

    Returns:
        {"ok": True, "task": <task_dict>}
    """
    # 1. Format validation (fail-fast, antes de abrir lock).
    valid, errors = transitions.validate_blocked_by_field(preds)
    if not valid:
        raise TaskError(
            "BLOCKED_BY_INVALID",
            f"blocked_by formato invalido: {errors}",
        )

    with store.mutate_state() as state:
        # 2. Target task exists.
        t = find_task(state, task_id)
        if t is None:
            raise TaskError(
                "TASK_NOT_FOUND",
                f"task nao existe: {task_id}",
            )

        # 3. All preds exist.
        by_id = {x["id"]: x for x in state["tasks"]}
        missing = [p for p in preds if p not in by_id]
        if missing:
            raise TaskError(
                "PRED_NOT_FOUND",
                f"preds nao existem: {missing}",
            )

        # 4. Cycle detect universal (inclui proposta no grafo).
        cycle = transitions.detect_cycle(state, task_id, list(preds))
        if cycle:
            raise TaskError(
                "CYCLE_DETECTED",
                f"ciclo detectado: {' -> '.join(cycle)}",
            )

        # 5. Apply mutation + event (atomic dentro do mesmo mutate_state).
        dp = dict(t.get("dispatch_payload") or {})
        previous = list(dp.get("blocked_by") or [])
        dp["blocked_by"] = list(preds)
        t["dispatch_payload"] = dp
        t["updated_at"] = store.now_iso()

        seq = store.next_seq(state)
        store.append_event({
            "seq": seq,
            "ts": store.now_iso(),
            "type": "task_blocked_by_set",
            "actor": actor,
            "task_id": task_id,
            "payload": {
                "preds": list(preds),
                "previous_preds": previous,
            },
        })
        state["last_event_seq"] = seq

        return {"ok": True, "task": t}
