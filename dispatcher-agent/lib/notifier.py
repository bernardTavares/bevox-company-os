"""Telegram notifier — terminal events from dispatcher and tester.

Outcomes emitted:
  - moved_to_testing  (dispatcher, exit_code==0, informational)
  - failed_execution  (dispatcher, exit_code!=0)
  - passed            (tester, decision=done)
  - failed_test       (tester, decision=in_progress_test_failed)
  - inconclusive      (tester, decision=in_progress_test_inconclusive)

Graceful, env-gated. Failures never raise to caller. Audit trail in
notifier.jsonl (append-only).

Spec: bevox-knowledge/35_specs/openclaw/2026-04-29-dispatcher-notifier-tester-decision-and-capability-gating.md
Supersedes (parcial): 2026-04-24-dispatcher-telegram-notifier.md
"""
from __future__ import annotations

import fcntl
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional, Tuple

# --- Phase 4 import shim: shared telegram_meta helper -----------------------
import sys as _sys
_TM_LIB = f"{Path.home()}/.openclaw/scripts/lib"
if _TM_LIB not in _sys.path:
    _sys.path.insert(0, _TM_LIB)
from telegram_meta import resolve_thread_id  # noqa: E402
# ----------------------------------------------------------------------------

JSONL_PATH = Path(f"{Path.home()}/.openclaw/dispatcher-agent/notifier.jsonl")
_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
_HTTP_TIMEOUT = 10.0
_REQUIRED_ENV = (
    "TELEGRAM_BOT_TOKEN",
    "OPENCLAW_DISPATCHER_TELEGRAM_CHAT_ID",
    "OPENCLAW_DISPATCHER_TELEGRAM_THREAD_ID",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _append_jsonl(event: str, task_id: str, outcome: str, detail: dict) -> None:
    try:
        JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": _now_iso(),
            "event": event,
            "task_id": task_id,
            "outcome": outcome,
            "detail": detail,
        }
        line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
        with JSONL_PATH.open("a", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.write(line)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except (OSError, TypeError, ValueError) as e:
        print(f"notifier.jsonl write failed: {e}", file=sys.stderr)


def _validate_env() -> Tuple[Optional[Tuple[str, str, int]], Optional[str]]:
    missing = [k for k in _REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        return None, "env_missing"
    raw_thread = os.environ["OPENCLAW_DISPATCHER_TELEGRAM_THREAD_ID"]
    try:
        thread_id = int(raw_thread)
    except (TypeError, ValueError):
        return None, "env_invalid"
    return (
        os.environ["TELEGRAM_BOT_TOKEN"],
        os.environ["OPENCLAW_DISPATCHER_TELEGRAM_CHAT_ID"],
        thread_id,
    ), None


def _send_http(url: str, payload: bytes) -> Tuple[bool, dict]:
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")
            parsed = json.loads(raw)
        if parsed.get("ok") is True and "result" in parsed:
            return True, {"message_id": parsed["result"].get("message_id")}
        safe_body = {
            "error_code": parsed.get("error_code") if isinstance(parsed, dict) else None,
            "description": str(parsed.get("description"))[:200] if isinstance(parsed, dict) else None,
        }
        return False, {"error": "telegram_api_not_ok", "body": safe_body}
    except urllib.error.HTTPError as e:
        return False, {"error": f"telegram_api_{e.code}", "detail": str(e)}
    except urllib.error.URLError as e:
        return False, {"error": "telegram_api_network", "detail": str(e.reason)}
    except (OSError, json.JSONDecodeError, TimeoutError) as e:
        return False, {"error": "telegram_api_exception", "detail": str(e)}


Outcome = Literal[
    "moved_to_testing",
    "failed_execution",
    "passed",
    "failed_test",
    "inconclusive",
]

_OUTCOMES = (
    "moved_to_testing",
    "failed_execution",
    "passed",
    "failed_test",
    "inconclusive",
)


def _format_message(task_id: str, outcome: str, context: dict) -> str:
    project = context.get("project", "?")
    title = context.get("title", "?")
    log_path = context.get("log_path", "?")
    if outcome == "moved_to_testing":
        return (
            f"🟡 {task_id} moved to testing\n"
            f"project: {project}\n"
            f"title: {title}\n"
            f"log: {log_path}"
        )
    if outcome == "failed_execution":
        reason = context.get("failure_reason", "?")
        exit_code = context.get("exit_code")
        if exit_code is None:
            exit_code = "?"
        return (
            f"❌ {task_id} execution failed\n"
            f"project: {project}\n"
            f"title: {title}\n"
            f"reason: {reason}\n"
            f"exit: {exit_code}\n"
            f"log: {log_path}"
        )
    if outcome == "passed":
        test_run_id = context.get("test_run_id", "?")
        return (
            f"✅ {task_id} passed\n"
            f"project: {project}\n"
            f"title: {title}\n"
            f"tester: {test_run_id}"
        )
    if outcome == "failed_test":
        first_failed_ac = context.get("first_failed_ac", "?")
        test_run_path = context.get("test_run_path", "?")
        return (
            f"❌ {task_id} failed test\n"
            f"project: {project}\n"
            f"title: {title}\n"
            f"AC: {first_failed_ac}\n"
            f"tester run: {test_run_path}"
        )
    # inconclusive
    decision_reason = context.get("decision_reason", "?")
    test_run_path = context.get("test_run_path", "?")
    return (
        f"⚠️ {task_id} inconclusive\n"
        f"project: {project}\n"
        f"title: {title}\n"
        f"reason: {decision_reason}\n"
        f"tester run: {test_run_path}"
    )


def _suppressed(outcome: str) -> bool:
    """Per-outcome env-gate (informational events only)."""
    if outcome == "moved_to_testing":
        return os.environ.get(
            "OPENCLAW_DISPATCHER_NOTIFIER_SUPPRESS_MOVED_TO_TESTING") == "1"
    return False


def send_task_event(
    task_id: str,
    outcome: Outcome,
    *,
    context: dict,
) -> None:
    """Emit Telegram message for task terminal state. Graceful."""
    if outcome not in _OUTCOMES:
        _append_jsonl("skipped:unknown_outcome", task_id, outcome, {})
        return
    if _suppressed(outcome):
        _append_jsonl("skipped:suppressed", task_id, outcome, {})
        return
    creds, skip_reason = _validate_env()
    if skip_reason is not None:
        _append_jsonl(f"skipped:{skip_reason}", task_id, outcome, {})
        if os.environ.get("OPENCLAW_DEBUG_NOTIFIER") == "1":
            print(f"notifier skipped ({skip_reason}) for {task_id}", file=sys.stderr)
        return
    token, chat_id, thread_id = creds
    # Phase 4: prefer per-project bot/group/thread when available.
    # CRITICAL: token+chat_id+thread_id must be a coherent triple — overriding
    # only thread_id while keeping legacy chat_id triggers Telegram 400
    # ("message thread not found"). resolve_telegram_target returns the full
    # triple atomically or None (caller falls back to legacy env triple).
    slug = context.get("project")
    if slug:
        try:
            from telegram_meta import resolve_telegram_target  # type: ignore
        except ImportError:
            resolve_telegram_target = None  # type: ignore
        if resolve_telegram_target is not None:
            target = resolve_telegram_target(slug, "dispatcher")
            if target is not None:
                token, chat_id, thread_id = target
    text = _format_message(task_id, outcome, context)
    body = {
        "chat_id": chat_id,
        "message_thread_id": thread_id,
        "text": text,
    }
    url = _TELEGRAM_API.format(token=token)
    payload = json.dumps(body).encode("utf-8")
    ok, result = _send_http(url, payload)
    if ok:
        _append_jsonl("task_event_sent", task_id, outcome, result)
    else:
        err = result.get("error", "unknown")
        _append_jsonl(f"failed:{err}", task_id, outcome, result)
        print(f"notifier delivery failed: {err} (task {task_id})", file=sys.stderr)
