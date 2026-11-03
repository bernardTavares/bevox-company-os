"""Storage para session state: briefings, logs, status.json atomicos.

Responsabilidade unica: I/O dos arquivos em ~/.openclaw/dispatcher-agent/.
NAO invoca Claude Code, NAO chama kanban, NAO resolve contexto.
"""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(os.path.expanduser("~/.openclaw/dispatcher-agent"))
BRIEFINGS_DIR = ROOT / "briefings"
EXECUTIONS_DIR = ROOT / "executions"


def now_iso() -> str:
    """UTC ISO8601 com Z suffix, match kanban convention."""
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _atomic_write(path: Path, content: str) -> None:
    """tmpfile + os.rename (atomic em POSIX)."""
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


def write_briefing(task_id: str, content: str) -> Path:
    path = BRIEFINGS_DIR / f"{task_id}.md"
    _atomic_write(path, content)
    return path


def briefing_path(task_id: str) -> Path:
    return BRIEFINGS_DIR / f"{task_id}.md"


def execution_log_path(task_id: str) -> Path:
    return EXECUTIONS_DIR / f"{task_id}.log"


def execution_status_path(task_id: str) -> Path:
    return EXECUTIONS_DIR / f"{task_id}.status.json"


def write_execution_status(task_id: str, status: Dict[str, Any]) -> Path:
    path = execution_status_path(task_id)
    _atomic_write(path, json.dumps(status, ensure_ascii=False, indent=2))
    return path


def read_execution_status(task_id: str) -> Optional[Dict[str, Any]]:
    path = execution_status_path(task_id)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def list_executions() -> list:
    if not EXECUTIONS_DIR.exists():
        return []
    out = []
    for p in sorted(EXECUTIONS_DIR.glob("*.status.json")):
        try:
            with open(p, "r", encoding="utf-8") as f:
                out.append(json.load(f))
        except (OSError, json.JSONDecodeError):
            continue
    return out
