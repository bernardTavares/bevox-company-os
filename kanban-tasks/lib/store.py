"""Storage layer for kanban-tasks: paths, lock, atomic I/O, events append."""

import fcntl
import json
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

# ============ Paths ============

ROOT = Path(os.environ.get("KANBAN_ROOT", os.path.expanduser("~/.openclaw/kanban-tasks")))
STATE_PATH = ROOT / "state.json"
EVENTS_PATH = ROOT / "events.jsonl"
PROJECTS_PATH = ROOT / "projects.yml"
LOCK_PATH = ROOT / "state.json.lock"

LOCK_TIMEOUT_SEC = 5
LOCK_STALE_TTL_SEC = 30
SCHEMA_VERSION = 4


# ============ Lock ============

class LockContentionError(Exception):
    """Raised when lock cannot be acquired within timeout."""


@contextmanager
def acquire_lock(timeout: float = LOCK_TIMEOUT_SEC) -> Iterator[None]:
    """File lock via fcntl. Stale lock (mtime > TTL) is force-acquired."""
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)

    if LOCK_PATH.exists():
        age = time.time() - LOCK_PATH.stat().st_mtime
        if age > LOCK_STALE_TTL_SEC:
            try:
                LOCK_PATH.unlink()
            except FileNotFoundError:
                pass

    deadline = time.time() + timeout
    lock_fd = None
    while True:
        try:
            lock_fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_RDWR, 0o644)
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            os.utime(LOCK_PATH, None)
            break
        except (OSError, BlockingIOError) as e:
            if lock_fd is not None:
                os.close(lock_fd)
                lock_fd = None
            if time.time() >= deadline:
                raise LockContentionError(
                    f"Could not acquire lock within {timeout}s"
                ) from e
            time.sleep(0.1)

    try:
        yield
    finally:
        try:
            if lock_fd is not None:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                os.close(lock_fd)
        finally:
            try:
                LOCK_PATH.unlink()
            except FileNotFoundError:
                pass


# ============ State I/O ============

def now_iso() -> str:
    """UTC ISO timestamp."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _empty_state() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_iso(),
        "last_event_seq": 0,
        "projects": [],
        "sprints": [],
        "tasks": [],
    }


def read_state() -> Dict[str, Any]:
    """Read state.json or return empty skeleton if missing."""
    if not STATE_PATH.exists():
        return _empty_state()
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def write_state_atomic(state: Dict[str, Any]) -> None:
    """Atomic write via tmpfile + os.rename."""
    state["generated_at"] = now_iso()
    ROOT.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix="state.", suffix=".json.tmp", dir=str(ROOT)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, STATE_PATH)
    except Exception:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        raise


# ============ Events ============

def next_seq(state: Dict[str, Any]) -> int:
    return state.get("last_event_seq", 0) + 1


def append_event(event: Dict[str, Any]) -> None:
    """Append a JSON event line to events.jsonl."""
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(EVENTS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def iter_events(
    n: Optional[int] = None,
    since: Optional[str] = None,
    actor: Optional[str] = None,
    type_: Optional[str] = None,
    task_id: Optional[str] = None,
    sprint_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Iterate events with filters. n=None means all."""
    if not EVENTS_PATH.exists():
        return []
    out: List[Dict[str, Any]] = []
    with open(EVENTS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if since and ev.get("ts", "") < since:
                continue
            if actor and ev.get("actor") != actor:
                continue
            if type_ and ev.get("type") != type_:
                continue
            if task_id and ev.get("task_id") != task_id:
                continue
            if sprint_id and ev.get("sprint_id") != sprint_id:
                continue
            out.append(ev)
    if n is not None:
        out = out[-n:]
    return out


def read_event_by_seq(seq: int) -> Optional[Dict[str, Any]]:
    if not EVENTS_PATH.exists():
        return None
    with open(EVENTS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("seq") == seq:
                return ev
    return None


# ============ Projects ============

def read_projects() -> List[str]:
    """Parse projects.yml (simple flat YAML list)."""
    if not PROJECTS_PATH.exists():
        return []
    out: List[str] = []
    with open(PROJECTS_PATH, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("projects:"):
                continue
            if line.startswith("- "):
                out.append(line[2:].strip().strip('"').strip("'"))
    return out


def write_projects(projects: List[str]) -> None:
    """Rewrite projects.yml preserving header comments."""
    header = (
        "# kanban-tasks projects - HOST-LOCAL.\n"
        "# Editavel manualmente; rode `cli.sh rebuild` apos editar.\n"
        "# Adicionar via CLI: cli.sh project add <name>\n"
    )
    body = "projects:\n" + "".join(f"  - {p}\n" for p in projects)
    PROJECTS_PATH.write_text(header + body, encoding="utf-8")


# ============ Mutate helper ============

@contextmanager
def mutate_state() -> Iterator[Dict[str, Any]]:
    """
    Mutate state inside the lock. Yields the state dict; caller mutates
    and (separately) appends events. On exit, writes state atomically.
    """
    with acquire_lock():
        state = read_state()
        yield state
        write_state_atomic(state)
