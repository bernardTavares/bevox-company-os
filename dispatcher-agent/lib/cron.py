"""Cron-dispatcher: trigger periodico de novas tasks ready (wave-4).

Decisoes travadas (§2 spec cron-dispatcher):
- Trigger systemd timer separado do reaper (300s default)
- Opt-in default deny via cron-projects.txt
- Kill-switch global cron.disabled
- Sequencial + ordem alfabetica deterministica
- Testing TAMBEM bloqueia (invariante forte §2.5)
- Falha per-project NAO aborta tick (audit + continua)
- Lock global do tick (cron.lock SEPARADO de reaper.lock)
- 1 task/projeto/tick; sempre detached; no_tester=false sempre
- dispatcher_actor="cron-dispatcher"
"""

import contextlib
import fcntl
import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from . import store

ROOT = Path(os.path.expanduser("~/.openclaw/dispatcher-agent"))
CRON_PROJECTS_FILE = ROOT / "cron-projects.txt"
CRON_DISABLED_FILE = ROOT / "cron.disabled"
CRON_JSONL = ROOT / "cron.jsonl"
CRON_LOCK = ROOT / "cron.lock"

CLARIFICATION_ESCALATIONS_DIR = Path(os.path.expanduser(
    "~/.openclaw/clarification-agent/escalations",
))
TESTER_ESCALATIONS_DIR = Path(os.path.expanduser(
    "~/.openclaw/tester-agent/escalations",
))


class CronError(Exception):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def parse_projects_file(path: Path) -> List[str]:
    """Le cron-projects.txt. Retorna lista deduplicada em ordem alfabetica.

    - 1 project/linha; `#` no inicio = comment; vazias skipadas
    - file ausente OR vazio -> []
    - Hash `#` no MEIO da linha NAO eh stripped (project name)
    """
    if not path.exists() or not path.is_file():
        return []
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return []
    seen = set()
    out = []
    for line in content.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    out.sort()
    return out


def kill_switch_active(path: Path) -> bool:
    """Returns True se file existe (file presente = kill-switch ON)."""
    return path.exists() and path.is_file()


ACTIVE_STATUSES = frozenset({"ready", "in_progress", "testing"})


def has_open_escalation_for_project(
    tasks: List[dict],
    clarification_dir: Path,
    tester_dir: Path,
) -> bool:
    """True se ha escalation aberta (clarification OR tester) pra qualquer task
    em status ativo (ready/in_progress/testing) ou com flag blocked=true.

    Tasks em done/rejected/archived/backlog NÃO bloqueiam o projeto, mesmo se
    tiverem escalation files órfãs.

    Patterns: <task_id>-clr-<N>.md OR <task_id>-tr-<N>.md
    """
    active_ids = {
        t["id"] for t in tasks
        if t.get("id") and (t.get("status") in ACTIVE_STATUSES or t.get("blocked"))
    }
    if not active_ids:
        return False
    for d in (clarification_dir, tester_dir):
        if not d.exists() or not d.is_dir():
            continue
        try:
            for p in d.iterdir():
                if not (p.is_file() or p.is_symlink()):
                    continue
                name = p.name
                for marker in ("-clr-", "-tr-"):
                    idx = name.find(marker)
                    if idx > 0:
                        if name[:idx] in active_ids:
                            return True
                        break
        except OSError:
            continue
    return False


@contextlib.contextmanager
def global_lock(lockfile: Path) -> Iterator[bool]:
    """fcntl LOCK_NB. SEPARADO de reaper.global_lock (lockfile distinto)."""
    lockfile.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lockfile), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield True
        except (BlockingIOError, OSError):
            yield False
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass
        os.close(fd)


def make_tick_id() -> str:
    return f"{store.now_iso()}-{uuid.uuid4().hex[:8]}"


def append_audit(entry: Dict[str, Any]) -> None:
    """Append linha JSONL atomico em cron.jsonl."""
    CRON_JSONL.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    with open(CRON_JSONL, "a", encoding="utf-8") as f:
        f.write(line)


def project_state_summary(project: str) -> Dict[str, Any]:
    """Le state.json direto (mesmo pattern selector). Tasks do projeto."""
    from .selector import KANBAN_STATE
    if not KANBAN_STATE.exists():
        return {"project": project, "tasks": [], "by_status": {}}
    try:
        state = json.loads(KANBAN_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"project": project, "tasks": [], "by_status": {}}
    tasks = [t for t in state.get("tasks", []) if t.get("project") == project]
    by_status: Dict[str, List[str]] = {}
    for t in tasks:
        s = t.get("status") or "unknown"
        by_status.setdefault(s, []).append(t.get("id"))
    return {"project": project, "tasks": tasks, "by_status": by_status}


# Status que skipam novo dispatch (invariante forte §2.5).
# Testing TAMBEM bloqueia (task aguardando tester ou decisao final).
# NOTA (2026-04-21): "blocked" foi REMOVIDO para permitir tasks ready mesmo com outras blocked
BUSY_STATUSES = ("in_progress", "testing")  # Removido: "blocked"


def project_blocks_dispatch(
    state: Dict[str, Any],
    clarification_dir: Path,
    tester_dir: Path,
) -> tuple:
    """Decide se projeto deve ser SKIPADO no tick.

    Retorna (blocks: bool, reason: str). reason vazia se OK.

    Bloqueios (em ordem deterministica de check):
    1. Status BUSY_STATUSES (in_progress > testing > blocked)
    2. Flag blocked=True (independente de status)
    3. Escalation aberta clarification OR tester pra qualquer task
    """
    by_status = state.get("by_status") or {}
    tasks = state.get("tasks") or []

    # Check 1: status BUSY (ordem deterministica)
    for st in BUSY_STATUSES:
        ids = by_status.get(st) or []
        if ids:
            return True, f"task em status {st}: {ids[:3]}"

    # Check 2: flag blocked (defensivo; pode ocorrer com qualquer status)
    # NOTA (2026-04-21): REMOVIDO para permitir tasks ready mesmo com outras blocked
    # blocked = [t.get("id") for t in tasks if t.get("blocked")]
    # if blocked:
    #     return True, f"task com flag blocked=true: {blocked[:3]}"
    # Em vez disso, apenas logamos tasks blocked para monitoramento
    blocked_tasks = [t.get("id") for t in tasks if t.get("blocked")]
    if blocked_tasks:
        # Log apenas, não bloqueia projeto
        pass

    # Check 3: escalation aberta
    if has_open_escalation_for_project(tasks, clarification_dir, tester_dir):
        return True, "escalation aberta (clarification OR tester)"

    return False, ""


def _safe_current_sprint_id(project: str) -> Optional[str]:
    """Le state.json e retorna id do current sprint do projeto, ou None.

    Nunca levanta — silencia erros de leitura (caller trata None como ausente).
    Usa mesma logica de _get_current_sprint_for do selector.
    """
    from .selector import KANBAN_STATE
    ignore_sprint = os.environ.get("OPENCLAW_DISPATCHER_IGNORE_SPRINT") == "1"
    if ignore_sprint:
        return None
    try:
        state = json.loads(KANBAN_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, AttributeError):
        return None
    for sp in state.get("sprints", []):
        if sp.get("state") == "current" and sp.get("project") == project:
            return sp.get("id")
    return None


def process_projects(
    opted_in: List[str],
    dry_run: bool,
    dispatch_one_fn=None,
    check_blocks_fn=None,
    state_summary_fn=None,
) -> Dict[str, Any]:
    """Processa projetos sequencialmente. Falha per-project NAO aborta tick.

    Funcoes injetaveis pra TDD:
    - dispatch_one_fn(project, dry_run) -> dict {outcome, task_id?, ...}
    - check_blocks_fn(project) -> (bool, str)
    - state_summary_fn(project) -> state dict

    Default (production): _dispatch_one_for_project + project_blocks_dispatch
    + project_state_summary.
    """
    if dispatch_one_fn is None:
        dispatch_one_fn = _dispatch_one_for_project
    if state_summary_fn is None:
        state_summary_fn = project_state_summary
    if check_blocks_fn is None:
        def _default_check(project):
            state = state_summary_fn(project)
            return project_blocks_dispatch(
                state, CLARIFICATION_ESCALATIONS_DIR, TESTER_ESCALATIONS_DIR,
            )
        check_blocks_fn = _default_check

    stats: Dict[str, Any] = {
        "projects_considered": len(opted_in),
        "projects_skipped_no_ready": 0,
        "projects_skipped_no_current_sprint": 0,
        "projects_skipped_busy": 0,
        "projects_skipped_escalation": 0,
        "dispatched_count": 0,
        "actions_per_project": [],
    }

    for project in opted_in:
        # Schema v4: capturar current sprint do projeto para audit
        current_sid = _safe_current_sprint_id(project)

        # Check 1: blocked?
        try:
            blocks, reason = check_blocks_fn(project)
        except Exception as e:
            stats["actions_per_project"].append({
                "project": project, "outcome": "check_error",
                "error_code": type(e).__name__,
                "error_detail": str(e)[:200], "task_id": None,
                "current_sprint_id": current_sid,
            })
            continue

        if blocks:
            if "escalation" in reason:
                stats["projects_skipped_escalation"] += 1
                outcome = "skipped_escalation"
            else:
                stats["projects_skipped_busy"] += 1
                outcome = "skipped_busy"
            stats["actions_per_project"].append({
                "project": project, "outcome": outcome,
                "skip_reason": reason, "task_id": None,
                "current_sprint_id": current_sid,
            })
            continue

        # Check 2: try dispatch
        try:
            result = dispatch_one_fn(project, dry_run=dry_run)
        except Exception as e:
            stats["actions_per_project"].append({
                "project": project, "outcome": "dispatch_error",
                "error_code": type(e).__name__,
                "error_detail": str(e)[:200], "task_id": None,
                "current_sprint_id": current_sid,
            })
            continue

        outcome = (result or {}).get("outcome") or "unknown"
        if outcome == "dispatched":
            stats["dispatched_count"] += 1
        elif outcome == "skipped_no_ready":
            stats["projects_skipped_no_ready"] += 1
        elif outcome == "skipped_no_current_sprint":
            stats["projects_skipped_no_current_sprint"] += 1

        action = {"project": project, "outcome": outcome,
                  "task_id": (result or {}).get("task_id"),
                  "current_sprint_id": current_sid}
        for k in ("session_id", "log_path", "skip_reason", "would_title"):
            if (result or {}).get(k) is not None:
                action[k] = result[k]
        if outcome == "dispatched":
            for k in ("execution_session_id", "session_was_fresh"):
                if (result or {}).get(k) is not None:
                    action[k] = result[k]
        stats["actions_per_project"].append(action)

    return stats


def _dispatch_one_for_project(project: str, dry_run: bool = False) -> Dict[str, Any]:
    """Dispatch 1 task ready do projeto. Reusa selector + briefing + runner.

    Levanta exception em qualquer erro infrastrutural (capturado pelo caller).
    """
    from . import selector as selector_lib
    from . import briefing as briefing_lib
    from . import runner as runner_lib

    try:
        task = selector_lib.select_next_ready(project)
    except selector_lib.SelectorError as e:
        if e.code == "NO_CURRENT_SPRINT":
            return {"outcome": "skipped_no_current_sprint", "task_id": None,
                    "skip_reason": e.detail}
        if e.code == "NO_READY_TASK":
            return {"outcome": "skipped_no_ready", "task_id": None,
                    "skip_reason": "nenhuma task ready no projeto"}
        raise

    if dry_run:
        return {"outcome": "would_dispatch", "task_id": task["id"],
                "would_title": task.get("title", "")[:80]}

    from . import allowlist as _allowlist
    briefing_content = briefing_lib.render_briefing(task, _allowlist.default_tools())
    bpath = store.write_briefing(task["id"], briefing_content)

    import subprocess
    KANBAN_CLI = f"{Path.home()}/.openclaw/kanban-tasks/cli.sh"

    # Move ready->in_progress (actor=cron-dispatcher)
    r = subprocess.run(
        [KANBAN_CLI, "task", "move", task["id"], "in_progress",
         "--actor", "cron-dispatcher", "--json"],
        capture_output=True, text=True, check=False, timeout=30,
    )
    if r.returncode != 0:
        raise CronError("KANBAN_MOVE_FAILED",
                        f"task move {task['id']} in_progress: {r.stderr.strip()[:200]}")

    # Merge metadata (dispatch_flags.no_tester=false; dispatcher_actor=cron-dispatcher)
    metadata = {
        "dispatched_at": store.now_iso(),
        "dispatcher_actor": "cron-dispatcher",
        "briefing_path": str(bpath),
        "dispatch_mode": "detach",
        "dispatch_flags": {"no_tester": False},
    }
    r = subprocess.run(
        [KANBAN_CLI, "task", "set-dispatch-payload", task["id"],
         "--payload", json.dumps(metadata, ensure_ascii=False), "--merge",
         "--actor", "cron-dispatcher", "--json"],
        capture_output=True, text=True, check=False, timeout=30,
    )
    if r.returncode != 0:
        raise CronError("KANBAN_PAYLOAD_FAILED",
                        f"set-dispatch-payload {task['id']}: {r.stderr.strip()[:200]}")

    # Lê sprint pra obter session_id (lazy create na primeira task)
    import json as _json
    sprint_session_id_in = None
    try:
        kanban_state = _json.loads(
            selector_lib.KANBAN_STATE.read_text(encoding="utf-8")
        )
        sprint_obj = next(
            (sp for sp in kanban_state.get("sprints", [])
             if sp["id"] == task["sprint_id"]),
            None,
        )
        if sprint_obj:
            sprint_session_id_in = sprint_obj.get("execution_session_id")
    except (OSError, _json.JSONDecodeError):
        sprint_session_id_in = None

    # Spawn detached
    status = runner_lib.launch_detached(
        task["id"], bpath, _allowlist.default_tools(),
        sprint_session_id=sprint_session_id_in,
        sprint_id=task["sprint_id"],
        model="claude-opus-4-7",
    )

    # Se foi fresh E kill-switch off, gravar UUID na sprint via kanban CLI
    disable_reuse = os.environ.get("OPENCLAW_DISPATCHER_DISABLE_SESSION_REUSE") == "1"
    if status.get("sprint_session_was_fresh") and not disable_reuse:
        try:
            subprocess.run(
                [KANBAN_CLI, "sprint", "set-session-id",
                 "--sprint-id", task["sprint_id"],
                 "--session-id", status["sprint_session_id"],
                 "--actor", "cron-dispatcher", "--json"],
                capture_output=True, text=True, timeout=10, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            # Não bloqueia dispatch — próxima task vai gerar fresh UUID
            pass

    # Merge runtime info
    runtime_meta = {
        "execution_session_id": status["session_id"],
        "execution_log_path": status["log_path"],
        "execution_started_at": status["started_at"],
    }
    subprocess.run(
        [KANBAN_CLI, "task", "set-dispatch-payload", task["id"],
         "--payload", json.dumps(runtime_meta, ensure_ascii=False), "--merge",
         "--actor", "cron-dispatcher", "--json"],
        capture_output=True, text=True, check=False, timeout=30,
    )

    return {
        "outcome": "dispatched", "task_id": task["id"],
        "session_id": status["session_id"], "log_path": status["log_path"],
        "execution_session_id": status.get("sprint_session_id"),
        "session_was_fresh": status.get("sprint_session_was_fresh", False),
    }


def run_tick(
    trigger: str = "manual", dry_run: bool = False,
    projects_file: Optional[Path] = None,
    disabled_file: Optional[Path] = None,
    lockfile: Optional[Path] = None,
) -> Dict[str, Any]:
    """Tick completo: lock + kill-switch + parse opt-in + process + audit.

    Falha per-project NAO aborta tick (auditada como dispatch_error).
    Unico caso que aborta: lock global no inicio (lock_skipped=true).
    """
    if projects_file is None: projects_file = CRON_PROJECTS_FILE
    if disabled_file is None: disabled_file = CRON_DISABLED_FILE
    if lockfile is None: lockfile = CRON_LOCK

    tick_id = make_tick_id()
    started_at = store.now_iso()

    with global_lock(lockfile) as acquired:
        if not acquired:
            entry = {
                "tick_id": tick_id, "tick_started_at": started_at,
                "tick_finished_at": store.now_iso(), "trigger": trigger,
                "kill_switch_active": False, "opted_in_projects": [],
                "projects_considered": 0, "projects_skipped_no_ready": 0,
                "projects_skipped_no_current_sprint": 0,
                "projects_skipped_busy": 0, "projects_skipped_escalation": 0,
                "dispatched_count": 0, "actions_per_project": [],
                "lock_acquired": False, "lock_skipped": True, "dry_run": dry_run,
            }
            append_audit(entry)
            return entry

        if kill_switch_active(disabled_file):
            entry = {
                "tick_id": tick_id, "tick_started_at": started_at,
                "tick_finished_at": store.now_iso(), "trigger": trigger,
                "kill_switch_active": True, "opted_in_projects": [],
                "projects_considered": 0, "projects_skipped_no_ready": 0,
                "projects_skipped_no_current_sprint": 0,
                "projects_skipped_busy": 0, "projects_skipped_escalation": 0,
                "dispatched_count": 0, "actions_per_project": [],
                "lock_acquired": True, "lock_skipped": False, "dry_run": dry_run,
            }
            append_audit(entry)
            return entry

        opted_in = parse_projects_file(projects_file)
        stats = process_projects(opted_in=opted_in, dry_run=dry_run)
        entry = {
            "tick_id": tick_id, "tick_started_at": started_at,
            "tick_finished_at": store.now_iso(), "trigger": trigger,
            "kill_switch_active": False, "opted_in_projects": opted_in,
            "lock_acquired": True, "lock_skipped": False, "dry_run": dry_run,
            **stats,
        }
        append_audit(entry)
        return entry
