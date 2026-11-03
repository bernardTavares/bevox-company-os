"""Selector: escolhe proxima task ready via state.json + 1-task-per-project guard.

Le state.json direto (mesmo pattern do scrum-master materializer).
Evita dep em HTTP/auth, e MC eh projecao do mesmo state.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

KANBAN_STATE = Path(f"{Path.home()}/.openclaw/kanban-tasks/state.json")


class SelectorError(Exception):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _read_state() -> Dict[str, Any]:
    if not KANBAN_STATE.exists():
        raise SelectorError(
            "KANBAN_STATE_MISSING",
            f"{KANBAN_STATE} nao existe. Rode `kanban-tasks/cli.sh sprint init`",
        )
    try:
        return json.loads(KANBAN_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise SelectorError(
            "KANBAN_STATE_INVALID",
            f"falha lendo {KANBAN_STATE}: {e}",
        )


def _in_progress_tasks_for_project(state: Dict[str, Any],
                                    project: Optional[str]) -> List[Dict[str, Any]]:
    result = []
    for t in state.get("tasks", []):
        if t.get("status") != "in_progress":
            continue
        if project is not None and t.get("project") != project:
            continue
        result.append(t)
    return result


def check_one_task_per_project_guard(project: Optional[str]) -> None:
    """Valida que zero tasks in_progress no scope. Raise WORK_IN_PROGRESS_LIMIT."""
    state = _read_state()
    in_progress = _in_progress_tasks_for_project(state, project)
    if in_progress:
        detail = f"{len(in_progress)} task(s) em in_progress"
        if project:
            detail += f" no projeto '{project}'"
        detail += ": " + ", ".join(
            f"{t['id']}({t.get('title', '')[:30]})" for t in in_progress[:3]
        )
        raise SelectorError("WORK_IN_PROGRESS_LIMIT", detail)


def _get_current_sprint_for(state, project):
    for sp in state.get("sprints", []):
        if sp.get("state") == "current" and sp.get("project") == project:
            return sp
    return None


def select_next_ready(project):
    """Retorna primeira task ready nao-blocked do projeto, no current sprint.

    Filtro por current sprint do projeto (schema v4).
    Kill-switch via OPENCLAW_DISPATCHER_IGNORE_SPRINT=1 → pula filtro.
    Ordena por created_at ascendente. Raise NO_READY_TASK ou NO_CURRENT_SPRINT.
    """
    state = _read_state()
    ignore_sprint = os.environ.get("OPENCLAW_DISPATCHER_IGNORE_SPRINT") == "1"

    current = None
    if not ignore_sprint:
        current = _get_current_sprint_for(state, project)
        if current is None:
            raise SelectorError(
                "NO_CURRENT_SPRINT",
                f"projeto {project!r} não tem current sprint. "
                f"Rode `kanban-tasks/cli.sh sprint bootstrap`."
            )

    candidates = []
    for t in state.get("tasks", []):
        if t.get("status") != "ready":
            continue
        if t.get("blocked"):
            continue
        if project is not None and t.get("project") != project:
            continue
        if not ignore_sprint and t.get("sprint_id") != current["id"]:
            continue
        candidates.append(t)

    if not candidates:
        msg = "nenhuma task ready nao-blocked"
        if project:
            msg += f" no projeto '{project}'"
        if not ignore_sprint and current is not None:
            msg += f" no current sprint ({current['id']})"
        msg += (". Rode `vox scrum-master` OU `kanban-tasks/cli.sh task move <id> ready`")
        raise SelectorError("NO_READY_TASK", msg)

    candidates.sort(key=lambda t: t.get("created_at", ""))
    return candidates[0]
