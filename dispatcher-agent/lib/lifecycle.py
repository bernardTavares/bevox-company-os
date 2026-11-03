"""Lifecycle: transitions de status no kanban + dispatch metadata merge."""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

from . import store
from . import notifier
from . import runner

KANBAN_CLI = Path(f"{Path.home()}/.openclaw/kanban-tasks/cli.sh")


class LifecycleError(Exception):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _run_kanban(args: list, actor: str = "dispatcher") -> Dict[str, Any]:
    cmd = [str(KANBAN_CLI)] + args + ["--json", "--actor", actor]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=False, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise LifecycleError("KANBAN_CLI_TIMEOUT", str(e))
    if result.returncode != 0:
        raise LifecycleError(
            "KANBAN_CLI_FAILED",
            f"exit={result.returncode} stderr={result.stderr.strip()[:200]}",
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise LifecycleError("KANBAN_CLI_BAD_JSON", str(e))


def move_to_in_progress(task_id: str) -> None:
    _run_kanban(["task", "move", task_id, "in_progress"], actor="dispatcher")


def merge_dispatch_payload(task_id: str, merge_fields: Dict[str, Any]) -> None:
    _run_kanban(
        ["task", "set-dispatch-payload", task_id,
         "--payload", json.dumps(merge_fields, ensure_ascii=False),
         "--merge"],
        actor="dispatcher",
    )


def auto_move_to_testing(task_id: str) -> None:
    _run_kanban(["task", "move", task_id, "testing"], actor="dispatcher")


def mark_execution_failed(task_id: str, reason_summary: str,
                         blocked_reason: str = "execution_failed") -> None:
    reason = f"{blocked_reason}: {reason_summary[:80]}"
    _run_kanban(
        ["task", "block", task_id, "--reason", reason],
        actor="dispatcher",
    )


def unblock_for_relaunch(task_id: str) -> None:
    _run_kanban(["task", "unblock", task_id], actor="dispatcher")


def _extract_delivered_artifacts(log_path: Path) -> List[str]:
    """Extrai paths explicitamente entregues do execution log.

    Heuristica pequena e conservadora, voltada para frases como:
    - Entreguei o documento em `path`
    - entregue em `path`
    - criado em `path`
    """
    if not log_path.exists() or not log_path.is_file():
        return []
    try:
        content = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    matches = re.findall(r"`([^`]+)`", content)
    out: List[str] = []
    for m in matches:
        s = m.strip()
        if not s:
            continue
        if s.startswith(("bevox-knowledge/", "~/", f"{Path.home()}/", ".openclaw/", "openclaw/")):
            if s not in out:
                out.append(s)
    return out


def _build_notifier_context(task_id: str, status: Dict[str, Any]) -> Dict[str, Any]:
    """Monta context para notifier. Campos missing → '?' (never raise)."""
    ctx = {
        "project": "?",
        "title": "?",
        "log_path": status.get("log_path", "?"),
        "finished_at": status.get("finished_at"),
        "exit_code": status.get("exit_code"),
    }
    try:
        result = subprocess.run(
            [str(KANBAN_CLI), "task", "show", task_id, "--json"],
            capture_output=True, text=True, check=False, timeout=10,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            task = data.get("task") if isinstance(data, dict) else None
            if task:
                ctx["project"] = task.get("project") or "?"
                ctx["title"] = task.get("title") or "?"
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    return ctx


def process_finished_session(task_id: str) -> Dict[str, Any]:
    """Aplica transition kanban dado status finalizado."""
    status = store.read_execution_status(task_id)
    if status is None:
        raise LifecycleError("SESSION_NOT_FOUND", f"{task_id}: sem status.json")
    if status.get("finished_at") is None:
        raise LifecycleError(
            "SESSION_NOT_FINISHED", f"{task_id}: ainda em execucao",
        )
    if status.get("post_action_applied"):
        return status
    exit_code = status.get("exit_code")
    ts = store.now_iso()
    if exit_code == 0:
        auto_move_to_testing(task_id)
        delivered_artifacts = _extract_delivered_artifacts(
            Path(status.get("log_path", "")),
        )
        merge_fields = {
            "execution_finished_at": status["finished_at"],
            "execution_exit_code": 0,
            "auto_moved_to_testing_at": ts,
        }
        if delivered_artifacts:
            merge_fields["expected_outputs"] = delivered_artifacts
        merge_dispatch_payload(task_id, merge_fields)
        status["post_action"] = "auto_moved_to_testing"
        try:
            notifier.send_task_event(
                task_id, "moved_to_testing",
                context=_build_notifier_context(task_id, status),
            )
        except Exception as e:  # double-safety; notifier is already graceful
            print(f"notifier raised (swallowed): {e}", file=sys.stderr)
    else:
        log_path = Path(status.get("log_path", ""))
        stderr_tail = "(sem log)"
        if log_path.exists():
            try:
                content = log_path.read_text(encoding="utf-8", errors="replace")
                stderr_tail = content[-300:].replace("\n", " ").strip()[:150]
            except OSError:
                pass
        # Check if killed by max runtime timeout
        unit_name = status.get("unit_name")
        blocked_reason = "execution_failed"
        if unit_name and runner._was_killed_by_max_runtime(unit_name):
            blocked_reason = "executor_timeout_max_runtime"
        mark_execution_failed(task_id, stderr_tail, blocked_reason=blocked_reason)
        merge_dispatch_payload(task_id, {
            "execution_finished_at": status["finished_at"],
            "execution_exit_code": exit_code,
            "execution_failed_marked_at": ts,
        })
        status["post_action"] = f"blocked_{blocked_reason}_exit_{exit_code}"
        try:
            ctx = _build_notifier_context(task_id, status)
            ctx["failure_reason"] = stderr_tail
            notifier.send_task_event(task_id, "failed_execution", context=ctx)
        except Exception as e:
            print(f"notifier raised (swallowed): {e}", file=sys.stderr)
    status["post_action_applied"] = True
    status["post_action_at"] = ts
    store.write_execution_status(task_id, status)
    return status
