"""Prechecks deterministicos: 5 invariantes antes de invocar LLM checks.

Decisao #8 da spec: auto-promote done exige TODOS pass:
- task.status == "testing"
- task.blocked == false
- execution log existe + nao-vazio
- nenhuma escalation aberta no clarification-agent
- acceptance_criteria nao-vazio

Senao: blocked com test_failed: precheck_X.
"""

from pathlib import Path
from typing import Any, Callable, Dict, Optional


def _check_task_in_testing(task: Dict[str, Any]) -> bool:
    return task.get("status") == "testing"


def _check_task_not_blocked(task: Dict[str, Any]) -> bool:
    return task.get("blocked") is False


def _check_execution_log_exists(log_path: Path) -> bool:
    if not log_path.exists() or not log_path.is_file():
        return False
    try:
        return log_path.stat().st_size > 0
    except OSError:
        return False


def _check_acceptance_criteria_non_empty(task: Dict[str, Any]) -> bool:
    ac = (task.get("dispatch_payload") or {}).get("acceptance_criteria") or []
    return isinstance(ac, list) and len(ac) > 0


def _check_no_open_clarification_escalation(
    task_id: str, escalation_check: Callable[[str], bool],
) -> bool:
    """escalation_check(task_id) returns True if escalation pending."""
    return not escalation_check(task_id)


def run_prechecks(
    task: Dict[str, Any],
    log_path: Path,
    escalation_check: Callable[[str], bool],
) -> Dict[str, Any]:
    """Executa 5 invariantes. Retorna dict com 'passed' + 'details' + 'failure_reason'."""
    details = {
        "task_in_testing": _check_task_in_testing(task),
        "task_not_blocked": _check_task_not_blocked(task),
        "execution_log_exists": _check_execution_log_exists(log_path),
        "acceptance_criteria_non_empty": _check_acceptance_criteria_non_empty(task),
        "no_open_clarification_escalation": _check_no_open_clarification_escalation(
            task.get("id", ""), escalation_check,
        ),
    }
    failed = [k for k, v in details.items() if not v]
    return {
        "passed": len(failed) == 0,
        "details": details,
        "failure_reason": (
            f"precheck_failed: {','.join(failed)}" if failed else ""
        ),
    }


def default_escalation_check(task_id: str) -> bool:
    """Verifica se ha escalation pending no clarification-agent (filesystem)."""
    import os
    import re
    esc_dir = Path(os.path.expanduser(
        "~/.openclaw/clarification-agent/escalations",
    ))
    if not esc_dir.exists():
        return False
    pattern = re.compile(re.escape(task_id) + r"-clr-\d+\.md$")
    for p in esc_dir.iterdir():
        if (p.is_symlink() or p.is_file()) and pattern.match(p.name):
            return True
    return False
