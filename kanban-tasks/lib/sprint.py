"""Sprint logic: bootstrap, create, close (with carry-over), promote."""

from typing import Any, Dict, List, Optional

from . import store


# ============ ID generation ============

def _next_sprint_seq(state: Dict[str, Any]) -> int:
    """Highest sprint-N seq + 1."""
    max_n = 0
    for sp in state["sprints"]:
        sid = sp["id"]
        if sid.startswith("sprint-"):
            try:
                n = int(sid[len("sprint-"):])
                max_n = max(max_n, n)
            except ValueError:
                continue
    return max_n + 1


def _make_sprint(seq: int, sprint_state: str, project: Optional[str], actor: str) -> Dict[str, Any]:
    return {
        "id": f"sprint-{seq}",
        "name": f"Sprint {seq}",
        "state": sprint_state,
        "project": project,
        "created_at": store.now_iso(),
        "closed_at": None,
        "created_by": actor,
    }


# ============ Lookups ============

def find_sprint(state: Dict[str, Any], sprint_id: str,
                project: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Resolve aliases 'current'/'next' (per-project) ou literal sprint_id.

    Aliases requerem project arg (raise ValueError sem). Literal id
    aceita project=None (id já é único).
    """
    if sprint_id in ("current", "next"):
        if project is None:
            raise ValueError(
                f"project required for alias resolution (got sprint_id={sprint_id!r})"
            )
        for sp in state["sprints"]:
            if sp["state"] == sprint_id and sp.get("project") == project:
                return sp
        return None
    for sp in state["sprints"]:
        if sp["id"] == sprint_id:
            return sp
    return None


def get_current(state: Dict[str, Any], project: str) -> Optional[Dict[str, Any]]:
    return find_sprint(state, "current", project=project)


def get_next(state: Dict[str, Any], project: str) -> Optional[Dict[str, Any]]:
    return find_sprint(state, "next", project=project)


# ============ Bootstrap ============

def bootstrap(actor: str = "bernard", projects: Optional[List[str]] = None,
              dry_run: bool = False) -> Dict[str, Any]:
    """Cria current+next pra cada projeto que ainda não tem.

    Se `projects` é None, lê de projects.yml (fonte canônica).
    Idempotente: projetos que já têm current+next são skipped.
    `dry_run=True` retorna plano sem mutar.
    """
    if projects is None:
        projects = store.read_projects()

    plan = []   # lista de (project, "current"|"next")

    if dry_run:
        # Ler state sem lock pra montar plano
        state = store.read_state()
        for proj in projects:
            has_current = any(
                sp["state"] == "current" and sp.get("project") == proj
                for sp in state["sprints"]
            )
            has_next = any(
                sp["state"] == "next" and sp.get("project") == proj
                for sp in state["sprints"]
            )
            if not has_current:
                plan.append((proj, "current"))
            if not has_next:
                plan.append((proj, "next"))
        return {"ok": True, "dry_run": True, "would_create": plan}

    created = []
    with store.mutate_state() as state:
        for proj in projects:
            has_current = any(
                sp["state"] == "current" and sp.get("project") == proj
                for sp in state["sprints"]
            )
            has_next = any(
                sp["state"] == "next" and sp.get("project") == proj
                for sp in state["sprints"]
            )
            if has_current and has_next:
                continue
            if not has_current:
                seq = _next_sprint_seq(state)
                sp = _make_sprint(seq, "current", proj, actor)
                state["sprints"].append(sp)
                seqn = store.next_seq(state)
                store.append_event({
                    "seq": seqn, "ts": store.now_iso(), "type": "sprint_created",
                    "actor": actor, "sprint_id": sp["id"], "state": "current",
                    "project": proj, "name": sp["name"],
                })
                state["last_event_seq"] = seqn
                created.append(sp)
            if not has_next:
                seq = _next_sprint_seq(state)
                sp = _make_sprint(seq, "next", proj, actor)
                state["sprints"].append(sp)
                seqn = store.next_seq(state)
                store.append_event({
                    "seq": seqn, "ts": store.now_iso(), "type": "sprint_created",
                    "actor": actor, "sprint_id": sp["id"], "state": "next",
                    "project": proj, "name": sp["name"],
                })
                state["last_event_seq"] = seqn
                created.append(sp)

    return {"ok": True, "dry_run": False, "created": created}


# ============ Mutations ============

def set_project(sprint_id: str, project: Optional[str], actor: str) -> Dict[str, Any]:
    with store.mutate_state() as state:
        sp = find_sprint(state, sprint_id)
        if sp is None:
            raise ValueError(f"sprint not found: {sprint_id}")
        if project is not None and project not in state["projects"]:
            raise ValueError(f"unknown project: {project}")
        sp["project"] = project
        seq = store.next_seq(state)
        store.append_event({
            "seq": seq, "ts": store.now_iso(), "type": "sprint_project_set",
            "actor": actor, "sprint_id": sp["id"], "project": project,
        })
        state["last_event_seq"] = seq
        return {"ok": True, "sprint": sp}


def set_session_id(sprint_id: str, session_id: str, actor: str) -> Dict[str, Any]:
    """Define execution_session_id pra primeira task da sprint.

    Idempotente: se já tem session_id, retorna noop com o existing.
    Sprint closed: rejeita (closed = imutável).
    """
    with store.mutate_state() as state:
        sp = find_sprint(state, sprint_id)
        if sp is None:
            raise ValueError(f"sprint not found: {sprint_id}")
        if sp["state"] == "closed":
            raise ValueError(f"cannot set session on closed sprint: {sprint_id}")
        if sp.get("execution_session_id"):
            return {"ok": True, "noop": True, "existing": sp["execution_session_id"]}
        sp["execution_session_id"] = session_id
        seq = store.next_seq(state)
        store.append_event({
            "seq": seq, "ts": store.now_iso(),
            "type": "sprint_session_id_set",
            "actor": actor, "sprint_id": sprint_id,
            "session_id": session_id,
        })
        state["last_event_seq"] = seq
        return {"ok": True, "noop": False, "session_id": session_id}


def clear_session_id(sprint_id: str, actor: str, reason: str = "") -> Dict[str, Any]:
    """Limpa execution_session_id (recovery operacional).

    Proxima task dispatchada gera fresh UUID. Sprints closed rejeitadas.
    Idempotente: ja null -> noop.
    """
    with store.mutate_state() as state:
        sp = find_sprint(state, sprint_id)
        if sp is None:
            raise ValueError(f"sprint not found: {sprint_id}")
        if sp["state"] == "closed":
            raise ValueError(f"cannot clear session on closed sprint: {sprint_id}")
        if not sp.get("execution_session_id"):
            return {"ok": True, "noop": True}
        old = sp["execution_session_id"]
        sp["execution_session_id"] = None
        seq = store.next_seq(state)
        store.append_event({
            "seq": seq, "ts": store.now_iso(),
            "type": "sprint_session_id_cleared",
            "actor": actor, "sprint_id": sprint_id,
            "previous_session_id": old, "reason": reason,
        })
        state["last_event_seq"] = seq
        return {"ok": True, "noop": False, "cleared": old}


def set_name(sprint_id: str, name: str, actor: str) -> Dict[str, Any]:
    """Edit sprint.name (follow-up wave-1: added because UI needs it)."""
    if not name or not name.strip():
        raise ValueError("name required")
    with store.mutate_state() as state:
        sp = find_sprint(state, sprint_id)
        if sp is None:
            raise ValueError(f"sprint not found: {sprint_id}")
        if sp["name"] == name.strip():
            return {"ok": True, "noop": True, "sprint": sp}
        sp["name"] = name.strip()
        seq = store.next_seq(state)
        store.append_event({
            "seq": seq, "ts": store.now_iso(), "type": "sprint_name_set",
            "actor": actor, "sprint_id": sp["id"], "name": sp["name"],
        })
        state["last_event_seq"] = seq
        return {"ok": True, "sprint": sp}


def list_pending_in_current(state: Dict[str, Any], project: str) -> List[Dict[str, Any]]:
    cur = get_current(state, project=project)
    if cur is None:
        return []
    return [
        t for t in state["tasks"]
        if t["sprint_id"] == cur["id"]
        and t["status"] not in ("done", "archived")
    ]


def close_current(carryover: List[Dict[str, str]], actor: str,
                  project: str) -> Dict[str, Any]:
    """Fecha current sprint do projeto P com carry-over decisions.

    Pos-execucao em P: current vira closed, next vira current,
    novo next nasce vazio. Outros projetos intocados.
    """
    with store.mutate_state() as state:
        cur = get_current(state, project=project)
        nxt = get_next(state, project=project)
        if cur is None or nxt is None:
            raise ValueError(
                f"invariant broken: project={project} missing current or next"
            )

        pending = list_pending_in_current(state, project=project)
        pending_ids = {t["id"] for t in pending}
        provided = {c["task_id"] for c in carryover}
        missing = pending_ids - provided
        if missing:
            raise ValueError(
                f"carryover incomplete for project={project}; "
                f"missing: {sorted(missing)}"
            )

        seq = store.next_seq(state)
        store.append_event({
            "seq": seq, "ts": store.now_iso(), "type": "sprint_closed",
            "actor": actor, "sprint_id": cur["id"],
            "project": project, "carryover": carryover,
        })
        state["last_event_seq"] = seq

        cur["state"] = "closed"
        cur["closed_at"] = store.now_iso()

        nxt["state"] = "current"
        seq = store.next_seq(state)
        store.append_event({
            "seq": seq, "ts": store.now_iso(), "type": "sprint_promoted",
            "actor": actor, "from_id": nxt["id"], "to_state": "current",
            "project": project,
        })
        state["last_event_seq"] = seq

        new_seq = _next_sprint_seq(state)
        new_next = _make_sprint(new_seq, "next", project, actor)
        state["sprints"].append(new_next)
        seq = store.next_seq(state)
        store.append_event({
            "seq": seq, "ts": store.now_iso(), "type": "sprint_created",
            "actor": actor, "sprint_id": new_next["id"], "state": "next",
            "project": project, "name": new_next["name"],
        })
        state["last_event_seq"] = seq

        new_current_id = nxt["id"]
        new_next_id = new_next["id"]
        tasks_by_id = {t["id"]: t for t in state["tasks"]}
        for entry in carryover:
            tid = entry["task_id"]
            action = entry["action"]
            t = tasks_by_id.get(tid)
            if t is None:
                continue
            if action == "move_current":
                old = t["sprint_id"]
                t["sprint_id"] = new_current_id
                t["updated_at"] = store.now_iso()
                seq = store.next_seq(state)
                store.append_event({
                    "seq": seq, "ts": store.now_iso(), "type": "task_resprinted",
                    "actor": actor, "task_id": tid,
                    "from_sprint_id": old, "to_sprint_id": new_current_id,
                })
                state["last_event_seq"] = seq
            elif action == "move_next":
                old = t["sprint_id"]
                t["sprint_id"] = new_next_id
                t["updated_at"] = store.now_iso()
                seq = store.next_seq(state)
                store.append_event({
                    "seq": seq, "ts": store.now_iso(), "type": "task_resprinted",
                    "actor": actor, "task_id": tid,
                    "from_sprint_id": old, "to_sprint_id": new_next_id,
                })
                state["last_event_seq"] = seq
            elif action == "archive":
                t["status"] = "archived"
                t["archived_at"] = store.now_iso()
                t["updated_at"] = store.now_iso()
                seq = store.next_seq(state)
                store.append_event({
                    "seq": seq, "ts": store.now_iso(), "type": "task_archived",
                    "actor": actor, "task_id": tid,
                })
                state["last_event_seq"] = seq
            else:
                raise ValueError(f"unknown carryover action: {action}")

        return {
            "ok": True,
            "project": project,
            "closed": cur["id"],
            "promoted_to_current": new_current_id,
            "new_next": new_next_id,
        }


def history(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    return sorted(
        [sp for sp in state["sprints"] if sp["state"] == "closed"],
        key=lambda s: s.get("closed_at") or "",
        reverse=True,
    )
