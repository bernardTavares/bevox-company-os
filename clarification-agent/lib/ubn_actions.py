"""UBN canonical actions — Python CLI ponto único que muda kanban.

Plugin JS de Telegram (knowledge-sync) despacha pra cá via
clarification-agent/cli.sh ubn <subcmd>.

Spec: bevox-knowledge/35_specs/openclaw/2026-04-30-universal-block-notifier.md §6
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional, Tuple

KANBAN_CLI = f"{Path.home()}/.openclaw/kanban-tasks/cli.sh"
TESTER_CLI = f"{Path.home()}/.openclaw/tester-agent/cli.sh"
ANSWERS_DIR = Path(f"{Path.home()}/.openclaw/clarification-agent/answers")
QUESTIONS_DIR = Path(f"{Path.home()}/.openclaw/clarification-agent/questions")
SIGNALS_DIR = Path(f"{Path.home()}/.openclaw/clarification-agent/signals")


@dataclass
class ActionResult:
    summary: str
    success: bool = True
    details: Optional[dict] = None


# ============== Retry strategies ==============

def retry_move_to_testing(task_id: str) -> ActionResult:
    """Use quando task está in_progress + blocked após tester decision.
    Transição válida: in_progress → testing.
    Reaper resilience auto-invoca tester via _needs_tester_reinvoke."""
    _kanban(["task", "unblock", task_id, "--actor", "ubn"])
    _kanban(["task", "move", task_id, "testing", "--actor", "ubn"])
    return ActionResult(summary=f"{task_id} unblocked + moved to testing")


def retry_move_to_ready(task_id: str) -> ActionResult:
    """Use quando task precisa re-dispatch (clarification, branch_checkout)."""
    _kanban(["task", "unblock", task_id, "--actor", "ubn"])
    _kanban(["task", "move", task_id, "ready", "--actor", "ubn"])
    return ActionResult(summary=f"{task_id} unblocked + moved to ready")


def retry_invoke_tester_direct(task_id: str) -> ActionResult:
    """Use quando task está em testing (stuck case). Não muda status."""
    r = subprocess.run([TESTER_CLI, "check", task_id],
                       capture_output=True, text=True, check=False, timeout=600)
    if r.returncode != 0:
        return ActionResult(summary=f"tester check failed: {r.stderr.strip()[:120]}",
                            success=False)
    return ActionResult(summary=f"{task_id} tester check completed")


def retry_noop_wait_cron(task_id: str) -> ActionResult:
    """Use quando task já está ready esperando cron.
    Sem action — escalation marcada resolved com nota."""
    return ActionResult(summary="task already ready; waiting for next cron tick")


# ============== Smart retry matrix ==============

# (block_reason_regex, current_status, action_callable)
_RETRY_MATRIX: List[Tuple[str, str, Callable[[str], ActionResult]]] = [
    (r"^test_(failed|inconclusive)", "in_progress", retry_move_to_testing),
    (r"^precheck_failed",            "in_progress", retry_move_to_testing),
    (r"^clarification_escalation",   "in_progress", retry_move_to_ready),
    (r"^branch_checkout_failed",     "in_progress", retry_move_to_ready),
    (r"^branch_checkout_failed",     "ready",       retry_noop_wait_cron),
    (r"^stuck-in-testing",           "testing",     retry_invoke_tester_direct),
]


def _select_retry_action(block_reason: str, current_status: str) -> Callable[[str], ActionResult]:
    for pattern, status_match, action in _RETRY_MATRIX:
        if re.match(pattern, block_reason) and status_match == current_status:
            return action
    return retry_move_to_ready  # fallback


# ============== Kanban CLI helper ==============

def _kanban(args: List[str]) -> dict:
    cmd = [KANBAN_CLI] + args + ["--json"]
    r = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=30)
    if r.returncode != 0:
        raise RuntimeError(f"kanban CLI failed: {' '.join(args)} → {r.stderr.strip()[:200]}")
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"raw": r.stdout}


# ============== Force actions ==============

def force_done(task_id: str, escalation_id: str, reason: str) -> ActionResult:
    """Force task to done status via kanban CLI --force flag.
    Unblocks first, then moves with audit reason."""
    _kanban(["task", "unblock", task_id, "--actor", "ubn"])
    _kanban(["task", "move", task_id, "done", "--force", "--actor", "ubn",
             "--reason", f"manual via UBN escalation {escalation_id}: {reason[:150]}"])
    return ActionResult(summary=f"{task_id} forced to done")


def force_reject(task_id: str, escalation_id: str, reason: str) -> ActionResult:
    """Force task to rejected status via kanban CLI --force flag.
    Unblocks first, then moves with audit reason."""
    _kanban(["task", "unblock", task_id, "--actor", "ubn"])
    _kanban(["task", "move", task_id, "rejected", "--force", "--actor", "ubn",
             "--reason", f"rejected via UBN escalation {escalation_id}: {reason[:150]}"])
    return ActionResult(summary=f"{task_id} forced to rejected")


# ============== Manual answer (clarification) ==============

def _find_latest_open_question(task_id: str) -> Optional[Path]:
    """Lookup latest question file for task. None if no agent waiting."""
    if not QUESTIONS_DIR.is_dir():
        return None
    matches = sorted(QUESTIONS_DIR.glob(f"{task_id}-clr-*.md"))
    return matches[-1] if matches else None


def manual_answer(task_id: str, answer_text: str) -> ActionResult:
    """Record free-form answer to clarification. Files share name across dirs.
    If no open question, records as audit only. Otherwise writes answer file
    and signals agent to resume."""
    q_path = _find_latest_open_question(task_id)
    if q_path is None:
        return ActionResult(
            summary=f"no open clarification for {task_id}; recorded as audit only")
    answer_path = ANSWERS_DIR / q_path.name  # same name, different dir
    ANSWERS_DIR.mkdir(parents=True, exist_ok=True)
    answer_path.write_text(
        f"# Manual answer (via UBN)\n\n{answer_text}\n", encoding="utf-8")
    SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
    (SIGNALS_DIR / f"{q_path.stem}.signal").touch()
    return ActionResult(summary=f"{task_id} answer written; agent should resume")


# ============== Backfill overrides ==============

UBN_ESCALATIONS_DIR = Path(f"{Path.home()}/.openclaw/clarification-agent/escalations")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def backfill_override(stale_task_ids: List[str],
                      renotify_task_ids: List[str]) -> ActionResult:
    """Single-shot: marca task_ids como stale OR renotify (escalation file
    minimal pra que próximo reaper tick reconheça)."""
    UBN_ESCALATIONS_DIR.mkdir(parents=True, exist_ok=True)
    for task_id in stale_task_ids:
        path = UBN_ESCALATIONS_DIR / f"{task_id}-blk-1.md"
        if path.exists():
            continue
        path.write_text(f"""---
escalation_id: {task_id}-blk-1
task_id: {task_id}
detector: ubn-backfill
criterion: blocked
block_session_key: backfill-{_now_iso()}
block_reason: backfill manual override pre-deploy
detected_at: {_now_iso()}
dispatched_at: null
status: stale
resolved_at: {_now_iso()}
resolved_action: backfill_stale
resolved_response: marked stale via ubn-backfill --override
resolved_by: ubn-backfill
---

# Backfill stale escalation for {task_id}
""", encoding="utf-8")
    for task_id in renotify_task_ids:
        # Cria com status=open + block_session_key forçando reaper a re-dispatch.
        path = UBN_ESCALATIONS_DIR / f"{task_id}-blk-renotify.md"
        path.write_text(f"""---
escalation_id: {task_id}-blk-renotify
task_id: {task_id}
detector: ubn-backfill
criterion: blocked
block_session_key: backfill-renotify-{_now_iso()}
block_reason: backfill renotify pre-deploy
detected_at: {_now_iso()}
dispatched_at: null
status: open
---

# Backfill renotify escalation for {task_id}
""", encoding="utf-8")
    return ActionResult(
        summary=f"backfill: {len(stale_task_ids)} stale, "
                f"{len(renotify_task_ids)} renotify")


def find_open_escalation_for_task(task_id: str) -> Optional[Path]:
    """Procura primeira escalation aberta pra task_id."""
    if not UBN_ESCALATIONS_DIR.is_dir():
        return None
    for path in sorted(UBN_ESCALATIONS_DIR.glob(f"{task_id}-blk-*.md")):
        content = path.read_text(encoding="utf-8")
        if "status: open" in content:
            return path
    return None


# ============== CLI entry point ==============


def main(argv: Optional[List[str]] = None) -> int:
    """Argparse CLI dispatcher para UBN actions.

    Subcommands:
    - retry <task_id>: lookup task + select smart action
    - done <task_id> [--reason]: force task to done
    - reject <task_id> [--reason]: force task to rejected
    - answer <task_id> --text <text>: record manual clarification answer
    - backfill --override [--stale T,T] [--renotify T,T]: backfill escalation files
    - list: list all open escalations

    Output: JSON {ok, summary, details}.
    Exit: 0 success / 1 failure.
    """
    parser = argparse.ArgumentParser(prog="ubn_actions")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # retry subcommand
    p_retry = sub.add_parser("retry")
    p_retry.add_argument("task_id")

    # done subcommand
    p_done = sub.add_parser("done")
    p_done.add_argument("task_id")
    p_done.add_argument("--reason", default="(no reason)")

    # reject subcommand
    p_reject = sub.add_parser("reject")
    p_reject.add_argument("task_id")
    p_reject.add_argument("--reason", default="(no reason)")

    # answer subcommand
    p_answer = sub.add_parser("answer")
    p_answer.add_argument("task_id")
    p_answer.add_argument("--text", required=True)

    # backfill subcommand
    p_backfill = sub.add_parser("backfill")
    p_backfill.add_argument("--override", action="store_true")
    p_backfill.add_argument("--stale", default="")
    p_backfill.add_argument("--renotify", default="")

    # list subcommand
    p_list = sub.add_parser("list")

    args = parser.parse_args(argv)

    # Dispatch to action handlers
    result = None
    if args.cmd == "retry":
        # Lookup task status from kanban to determine retry action
        task_data = json.loads(
            subprocess.run(
                [KANBAN_CLI, "task", "show", args.task_id, "--json"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
        )["task"]
        block_reason = task_data.get("blocked_reason") or "(unknown)"
        current_status = task_data.get("status")
        action = _select_retry_action(block_reason, current_status)
        result = action(args.task_id)

    elif args.cmd == "done":
        result = force_done(args.task_id, "via-telegram", args.reason)

    elif args.cmd == "reject":
        result = force_reject(args.task_id, "via-telegram", args.reason)

    elif args.cmd == "answer":
        result = manual_answer(args.task_id, args.text)

    elif args.cmd == "backfill":
        if args.override:
            stale = [t.strip() for t in args.stale.split(",") if t.strip()]
            renotify = [t.strip() for t in args.renotify.split(",") if t.strip()]
            result = backfill_override(stale, renotify)
        else:
            parser.error("backfill requires --override flag")
            return 1

    elif args.cmd == "list":
        # List all open escalations
        items = []
        if UBN_ESCALATIONS_DIR.is_dir():
            for path in sorted(UBN_ESCALATIONS_DIR.glob("*.md")):
                content = path.read_text(encoding="utf-8")
                if "status: open" in content:
                    items.append(path.name)
        result = ActionResult(
            summary=f"{len(items)} open", details={"items": items}
        )

    else:
        parser.error("unknown command")
        return 1

    # Output JSON result
    output = {
        "ok": result.success if result else False,
        "summary": result.summary if result else "unknown",
        "details": result.details if result else {},
    }
    print(json.dumps(output, ensure_ascii=False))
    return 0 if (result and result.success) else 1


if __name__ == "__main__":
    sys.exit(main())
