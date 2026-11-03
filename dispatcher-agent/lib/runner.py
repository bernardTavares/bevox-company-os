"""Runner: invoca claude -p como subprocess (detached ou foreground).

Detached (default): start_new_session=True (setsid) + redirect stdout/stderr.
Foreground (debug): subprocess streaming pro TTY.
"""

import json
import os
import subprocess
import uuid as _uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import store


# HOTFIX 2026-04-28: cwd injection per-project (interim).
# Substituido pela spec completa local_repo_path (~/.openclaw/docs/superpowers/
# specs/2026-04-28-project-local-repo-path.md) quando implementada.
# Ate la, mapeamento hard-coded somente para bevox-site.
_HOTFIX_REPO_PATHS = {
    "bevox-site": f"{Path.home()}/code/bevox-site",
}

# F3.1: path to state.json for max_runtime_seconds + hotfix_resolve_local_repo_path
_KANBAN_STATE_PATH = Path(f"{Path.home()}/.openclaw/kanban-tasks/state.json")


def _hotfix_resolve_local_repo_path(task_id: str) -> Optional[str]:
    """HOTFIX: lookup task project no kanban-state.json e mapeia pra repo local.

    Retorna None se project ausente, nao mapeado, ou dir inexistente.
    Substituicao por spec local_repo_path resolverá via projects-meta.
    """
    try:
        with open(_KANBAN_STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    project = None
    for t in data.get("tasks", []) or []:
        if t.get("id") == task_id:
            project = t.get("project")
            break
    if not project:
        return None
    path = _HOTFIX_REPO_PATHS.get(project)
    if path and Path(path).is_dir():
        return path
    return None


class RunnerError(Exception):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _build_session_id(task_id: str) -> str:
    ts = store.now_iso().replace(":", "").replace("-", "")
    return f"{task_id}-{ts}"


def _resolve_max_runtime_seconds(task_id: str) -> int:
    """Resolve executor max runtime: per-task override > env > default 12h.

    Returns 0 quando OPENCLAW_EXECUTOR_MAX_RUNTIME_HOURS=0 (kill switch — sem limite).
    """
    env_val = os.environ.get("OPENCLAW_EXECUTOR_MAX_RUNTIME_HOURS")
    if env_val == "0":
        return 0
    try:
        state = json.loads(_KANBAN_STATE_PATH.read_text(encoding="utf-8"))
        task = next(
            (t for t in state.get("tasks", []) if t.get("id") == task_id),
            None,
        )
        if task:
            override_raw = (task.get("dispatch_payload") or {}).get("max_runtime_hours")
            override_hours = None
            if isinstance(override_raw, (int, float)):
                override_hours = float(override_raw)
            elif isinstance(override_raw, str):
                try:
                    override_hours = float(override_raw)
                except ValueError:
                    pass
            if override_hours is not None and override_hours > 0:
                # Use float multiplication then int(), so 0.5h → 1800s (not 0)
                return int(override_hours * 3600)
    except (OSError, json.JSONDecodeError):
        pass
    try:
        hours = int(env_val) if env_val else 12
    except ValueError:
        hours = 12
    return hours * 3600


def _claude_cmd(briefing_path: Path, allowed_tools: str,
                 model: Optional[str] = None) -> List[str]:
    briefing_content = briefing_path.read_text(encoding="utf-8")
    cmd = ["claude", "-p", briefing_content]
    if model:
        cmd += ["--model", model]
    cmd += ["--allowedTools", allowed_tools]
    return cmd


def launch_detached(
    task_id: str, briefing_path: Path, allowed_tools: str,
    *, sprint_session_id: Optional[str] = None,
    sprint_id: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """Spawn `claude -p` como transient systemd-run user service.

    Branching session reuse:
    - sprint_session_id is None → fresh: gera UUID novo + retorna is_fresh=True
    - sprint_session_id presente → resume: spawn com --resume <uuid>
    - Kill-switch OPENCLAW_DISPATCHER_DISABLE_SESSION_REUSE=1 → sempre fresh
    """
    transient_unit_id = _build_session_id(task_id)
    log_path = store.execution_log_path(task_id)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    disable_reuse = os.environ.get("OPENCLAW_DISPATCHER_DISABLE_SESSION_REUSE") == "1"

    if sprint_session_id and not disable_reuse:
        claude_session_arg = ["--resume", sprint_session_id]
        sprint_session_id_used = sprint_session_id
        is_fresh = False
    else:
        new_uuid = str(_uuid.uuid4())
        claude_session_arg = ["--session-id", new_uuid]
        sprint_session_id_used = new_uuid
        is_fresh = True

    # Pre-write log header (metadata + delimiter) before spawn.
    log_path.write_text(
        f"# DISPATCHER METADATA\n"
        f"# task_id: {task_id}\n"
        f"# sprint_id: {sprint_id or '?'}\n"
        f"# execution_session_id: {sprint_session_id_used}\n"
        f"# session_was_fresh: {is_fresh}\n"
        f"# kill_switch_active: {disable_reuse}\n"
        f"# briefing_path: {briefing_path}\n"
        f"# spawned_at: {store.now_iso()}\n"
        f"# ----- claude output below -----\n",
        encoding="utf-8",
    )

    unit_name = f"claude-task-{transient_unit_id}.service"
    briefing_content = briefing_path.read_text(encoding="utf-8")

    max_seconds = _resolve_max_runtime_seconds(task_id)
    sd_cmd = [
        "systemd-run", "--user",
        f"--unit={unit_name}",
        "--collect",
        "--property=Type=exec",
        f"--property=StandardOutput=append:{log_path}",
        "--property=StandardError=inherit",
    ]
    if max_seconds > 0:
        sd_cmd.append(f"--property=RuntimeMaxSec={max_seconds}")
    sd_cmd += [
        "--",
        "claude", "-p", briefing_content,
        *claude_session_arg,
        "--allowedTools", allowed_tools,
    ]
    if model:
        sd_cmd += ["--model", model]

    # HOTFIX 2026-04-28: inject WorkingDirectory para projetos mapeados
    # (ver _hotfix_resolve_local_repo_path acima). Substituido pela spec
    # 2026-04-28-project-local-repo-path.md quando implementada.
    repo_path = _hotfix_resolve_local_repo_path(task_id)
    if repo_path:
        sep_idx = sd_cmd.index("--")
        sd_cmd.insert(sep_idx, f"--property=WorkingDirectory={repo_path}")

    try:
        result = subprocess.run(
            sd_cmd, capture_output=True, text=True, timeout=15, check=False,
        )
    except subprocess.TimeoutExpired:
        raise RunnerError(
            "SYSTEMD_RUN_TIMEOUT",
            f"systemd-run --user excedeu 15s pra spawnar claude-task {task_id}",
        )
    if result.returncode != 0:
        raise RunnerError(
            "SYSTEMD_RUN_FAILED",
            f"systemd-run exit={result.returncode}: {result.stderr.strip()[:300]}",
        )

    status = {
        "task_id": task_id,
        "session_id": transient_unit_id,
        "sprint_session_id": sprint_session_id_used,
        "sprint_session_was_fresh": is_fresh,
        "sprint_id": sprint_id,
        "kill_switch_active": disable_reuse,
        "unit_name": unit_name,
        "pid": None,
        "run_mode": "detach",
        "started_at": store.now_iso(),
        "briefing_path": str(briefing_path),
        "log_path": str(log_path),
        "finished_at": None,
        "exit_code": None,
        "model": model or "default",
    }
    store.write_execution_status(task_id, status)
    return status


def launch_foreground(
    task_id: str, briefing_path: Path, allowed_tools: str,
    *, sprint_session_id: Optional[str] = None,
    sprint_id: Optional[str] = None,
    model: Optional[str] = None,
    timeout_seconds: int = 1800,
) -> Dict[str, Any]:
    """Spawn `claude -p` em foreground (debug). Bloqueia ate terminar.

    Mesmo branching session reuse que launch_detached.
    """
    log_path = store.execution_log_path(task_id)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    disable_reuse = os.environ.get("OPENCLAW_DISPATCHER_DISABLE_SESSION_REUSE") == "1"

    if sprint_session_id and not disable_reuse:
        claude_session_arg = ["--resume", sprint_session_id]
        sprint_session_id_used = sprint_session_id
        is_fresh = False
    else:
        new_uuid = str(_uuid.uuid4())
        claude_session_arg = ["--session-id", new_uuid]
        sprint_session_id_used = new_uuid
        is_fresh = True

    log_path.write_text(
        f"# DISPATCHER METADATA (FOREGROUND)\n"
        f"# task_id: {task_id}\n"
        f"# sprint_id: {sprint_id or '?'}\n"
        f"# execution_session_id: {sprint_session_id_used}\n"
        f"# session_was_fresh: {is_fresh}\n"
        f"# kill_switch_active: {disable_reuse}\n"
        f"# spawned_at: {store.now_iso()}\n"
        f"# ----- claude output below -----\n",
        encoding="utf-8",
    )

    briefing_content = briefing_path.read_text(encoding="utf-8")
    cmd = [
        "claude", "-p", briefing_content,
        *claude_session_arg,
        "--allowedTools", allowed_tools,
    ]
    if model:
        cmd += ["--model", model]

    started_at = store.now_iso()
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            proc = subprocess.Popen(
                cmd, stdout=f, stderr=subprocess.STDOUT, text=True,
            )
            try:
                _, _ = proc.communicate(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                proc.kill()
                raise RunnerError(
                    "CLAUDE_TIMEOUT",
                    f"claude -p excedeu {timeout_seconds}s",
                )
        exit_code = proc.returncode
    except FileNotFoundError as e:
        raise RunnerError("CLAUDE_NOT_FOUND", str(e))

    status = {
        "task_id": task_id,
        "session_id": _build_session_id(task_id),
        "sprint_session_id": sprint_session_id_used,
        "sprint_session_was_fresh": is_fresh,
        "sprint_id": sprint_id,
        "kill_switch_active": disable_reuse,
        "pid": proc.pid,
        "run_mode": "foreground",
        "started_at": started_at,
        "briefing_path": str(briefing_path),
        "log_path": str(log_path),
        "finished_at": store.now_iso(),
        "exit_code": exit_code,
        "model": model or "default",
    }
    store.write_execution_status(task_id, status)
    return status


def is_session_alive(status: Dict[str, Any]) -> bool:
    pid = status.get("pid")
    if not pid:
        return False
    if status.get("finished_at") is not None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _was_killed_by_max_runtime(unit_name: str) -> bool:
    """Inspects systemd unit Result property. Returns True if Result=timeout."""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "show", "--property=Result", "--value", unit_name],
            capture_output=True, text=True, timeout=5, check=False,
        )
        return result.stdout.strip() == "timeout"
    except (subprocess.TimeoutExpired, OSError):
        return False


def kill_session(task_id: str, sig: int = 15) -> Dict[str, Any]:
    status = store.read_execution_status(task_id)
    if status is None:
        raise RunnerError("SESSION_NOT_FOUND", f"{task_id}: sem status.json")
    pid = status.get("pid")
    if not pid:
        raise RunnerError("SESSION_NO_PID", f"{task_id}: pid ausente")
    try:
        os.kill(pid, sig)
    except (OSError, ProcessLookupError) as e:
        raise RunnerError("KILL_FAILED", f"{task_id}: {e}")
    status["finished_at"] = store.now_iso()
    status["exit_code"] = -sig
    status["canceled"] = True
    store.write_execution_status(task_id, status)
    return status


def reap_finished(task_id: str) -> Optional[Dict[str, Any]]:
    """Checa se transient service terminou (wave-8 via systemctl show).

    Fluxo:
      1. Le status.json; se ja finished → return
      2. Query `systemctl --user show UNIT --property=ActiveState,ExecMainStatus,Result`
      3. ActiveState in {activating,active,deactivating,reloading} → still running
      4. Finished (inactive|failed|gone): marca finished + exit_code=ExecMainStatus
    """
    status = store.read_execution_status(task_id)
    if status is None or status.get("finished_at") is not None:
        return status
    unit_name = status.get("unit_name")
    if not unit_name:
        # Status pre-wave-8 sem unit_name (task criada antes do upgrade)
        return status
    try:
        result = subprocess.run(
            ["systemctl", "--user", "show", unit_name,
             "--property=ActiveState,ExecMainStatus,Result"],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except subprocess.TimeoutExpired:
        return status
    props: Dict[str, str] = {}
    for line in result.stdout.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            props[k] = v
    active_state = props.get("ActiveState", "")
    if active_state in ("activating", "active", "deactivating", "reloading"):
        return status
    # Finished state: inactive | failed | gone (post --collect cleanup)
    exit_code_s = props.get("ExecMainStatus", "")
    try:
        exit_code = int(exit_code_s) if exit_code_s else -1
    except ValueError:
        exit_code = -1
    status["finished_at"] = store.now_iso()
    status["exit_code"] = exit_code
    status["systemd_result"] = props.get("Result", "")
    status["unit_final_state"] = active_state or "gone"
    store.write_execution_status(task_id, status)
    return status
