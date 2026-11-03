"""Storage pra questions, answers, escalations, signals."""

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ROOT = Path(os.path.expanduser("~/.openclaw/clarification-agent"))
QUESTIONS_DIR = ROOT / "questions"
ANSWERS_DIR = ROOT / "answers"
ESCALATIONS_DIR = ROOT / "escalations"
SIGNALS_DIR = ROOT / "signals"
POLL_JSONL = ROOT / "poll.jsonl"
POLL_LOCK = ROOT / "poll.lock"
POLL_DISABLED = ROOT / "poll.disabled"
TELEGRAM_REPLY_STATE = ROOT / "telegram-reply-state.json"


def now_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.rename(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def next_clarification_seq(task_id: str) -> int:
    QUESTIONS_DIR.mkdir(parents=True, exist_ok=True)
    pattern = re.compile(re.escape(task_id) + r"-clr-(\d+)\.md$")
    max_seq = 0
    for p in QUESTIONS_DIR.iterdir():
        m = pattern.match(p.name)
        if m:
            max_seq = max(max_seq, int(m.group(1)))
    return max_seq + 1


def make_clarification_id(task_id: str, seq: int) -> str:
    return f"{task_id}-clr-{seq}"


def write_question(clarification_id: str, question_text: str) -> Path:
    path = QUESTIONS_DIR / f"{clarification_id}.md"
    header = (f"# Clarification question — {clarification_id}\n"
              f"\n**Received at:** {now_iso()}\n\n---\n\n")
    _atomic_write(path, header + question_text + "\n")
    return path


def write_answer(
    clarification_id: str, question_path: Path, answer_text: str,
    confidence: str, sources: List[str],
    drafter: str = "clarification-agent (claude-haiku-4-5)",
    escalation_reason: Optional[str] = None,
) -> Path:
    path = ANSWERS_DIR / f"{clarification_id}.md"
    sources_block = "\n".join(f"- {s}" for s in sources) if sources else "(nenhuma)"
    body = f"""# Clarification answer — {clarification_id}

**Question file:** {question_path}
**Generated at:** {now_iso()}
**Drafter:** {drafter}
**Confidence:** {confidence}
**Sources used:**
{sources_block}

---

## Answer

{answer_text}
"""
    if escalation_reason and confidence == "unsafe":
        body += f"\n---\n\n## Escalation reason\n\n{escalation_reason}\n"
    _atomic_write(path, body)
    return path


def write_escalation_symlink(clarification_id: str) -> Path:
    target = ANSWERS_DIR / f"{clarification_id}.md"
    link = ESCALATIONS_DIR / f"{clarification_id}.md"
    ESCALATIONS_DIR.mkdir(parents=True, exist_ok=True)
    if link.exists() or link.is_symlink():
        link.unlink()
    os.symlink(str(target), str(link))
    return link


def clear_escalation_symlink(clarification_id: str) -> None:
    link = ESCALATIONS_DIR / f"{clarification_id}.md"
    if link.exists() or link.is_symlink():
        link.unlink()


def signal_path(clarification_id: str) -> Path:
    return SIGNALS_DIR / f"{clarification_id}.signal"


def emit_signal(clarification_id: str, outcome: str) -> Path:
    SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
    path = signal_path(clarification_id)
    _atomic_write(path, json.dumps({
        "clarification_id": clarification_id,
        "outcome": outcome,
        "emitted_at": now_iso(),
    }, indent=2))
    return path


def read_signal(clarification_id: str) -> Optional[Dict[str, Any]]:
    path = signal_path(clarification_id)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def list_escalations() -> List[Dict[str, Any]]:
    if not ESCALATIONS_DIR.exists():
        return []
    out = []
    for p in sorted(ESCALATIONS_DIR.iterdir()):
        if not (p.is_symlink() or p.is_file()):
            continue
        out.append({"clarification_id": p.stem, "escalation_path": str(p)})
    return out


def append_poll_event(tick_id: str, event: str, payload: Dict[str, Any]) -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": now_iso(),
        "tick_id": tick_id,
        "event": event,
        "payload": payload,
    }
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    with open(POLL_JSONL, "a", encoding="utf-8") as f:
        f.write(line)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def save_json(path: Path, payload: Any) -> None:
    _atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# Schema v2 helpers — notifier-state.json with full clarification tuple
# ---------------------------------------------------------------------------

SCHEMA_V2_EMPTY = {
    "schema_version": 2,
    "heartbeat_at": None,
    "notifications": {},
}


def load_state_v2(path: Path) -> dict:
    """Load notifier-state.json. Returns dict with schema_version field intact.

    Caller must check schema_version and call migrate_v1_to_v2() if needed.
    Missing/corrupt file returns empty v2 shape.
    """
    if not path.exists():
        return dict(SCHEMA_V2_EMPTY, notifications={})
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return dict(SCHEMA_V2_EMPTY, notifications={})
    if not isinstance(data, dict) or "notifications" not in data:
        return dict(SCHEMA_V2_EMPTY, notifications={})
    data.setdefault("schema_version", 1)
    data.setdefault("heartbeat_at", None)
    return data


def save_state_v2(path: Path, state: dict) -> None:
    """Atomic write of schema v2 state. Uses _atomic_write helper.

    Does NOT mutate the input dict — schema_version defaulting happens on
    a shallow copy so callers can pass live state objects safely.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(state)
    payload.setdefault("schema_version", 2)
    _atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2))


def migrate_v1_to_v2(state: dict, resolver: Callable[[str], Optional[dict]]) -> dict:
    """Convert schema v1 entries to schema v2.

    `resolver(task_id) -> dict or None` is called per entry to resolve
    `(project, token_alias, chat_id, thread_id)`. If resolver returns
    None, entry is marked status="orphan".

    Idempotent: if state already has schema_version>=2, returns unchanged.
    """
    if state.get("schema_version", 1) >= 2:
        return state

    new_notifications = {}
    for cid, old in state.get("notifications", {}).items():
        resolved = resolver(old.get("task_id"))
        if resolved:
            new_notifications[cid] = {
                "task_id": old.get("task_id"),
                "project": resolved.get("project"),
                "token_alias": resolved.get("token_alias"),
                "chat_id": resolved.get("chat_id"),
                "thread_id": resolved.get("thread_id"),
                "telegram_message_id": old.get("telegram_message_id"),
                "sent_at": old.get("notified_at"),
                "status": "pending",
                "resolved_at": None,
                "resolved_via": None,
            }
        else:
            new_notifications[cid] = {
                "task_id": old.get("task_id"),
                "project": None,
                "token_alias": None,
                "chat_id": None,
                "thread_id": None,
                "telegram_message_id": old.get("telegram_message_id"),
                "sent_at": old.get("notified_at"),
                "status": "orphan",
                "resolved_at": None,
                "resolved_via": None,
            }
    return {
        "schema_version": 2,
        "heartbeat_at": state.get("heartbeat_at"),
        "notifications": new_notifications,
    }
