"""Storage pra test_runs + escalations.

Responsabilidade unica: I/O atomico em ~/.openclaw/tester-agent/.
NAO invoca claude, NAO chama kanban, NAO valida AC.
"""

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

ROOT = Path(os.path.expanduser("~/.openclaw/tester-agent"))
TEST_RUNS_DIR = ROOT / "test_runs"
ESCALATIONS_DIR = ROOT / "escalations"


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


def next_test_run_seq(task_id: str) -> int:
    """Acha proximo seq pra <task-id>-tr-<seq>.json."""
    TEST_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    pattern = re.compile(re.escape(task_id) + r"-tr-(\d+)\.json$")
    max_seq = 0
    for p in TEST_RUNS_DIR.iterdir():
        m = pattern.match(p.name)
        if m:
            max_seq = max(max_seq, int(m.group(1)))
    return max_seq + 1


def make_test_run_id(task_id: str, seq: int) -> str:
    return f"{task_id}-tr-{seq}"


def test_run_path(test_run_id: str) -> Path:
    return TEST_RUNS_DIR / f"{test_run_id}.json"


def write_test_run(test_run_id: str, data: Dict[str, Any]) -> Path:
    """Escreve test_run JSON atomico."""
    path = test_run_path(test_run_id)
    _atomic_write(path, json.dumps(data, ensure_ascii=False, indent=2))
    return path


def read_test_run(test_run_id: str) -> Optional[Dict[str, Any]]:
    path = test_run_path(test_run_id)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def list_test_runs(task_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lista test_runs (todos OR de uma task)."""
    if not TEST_RUNS_DIR.exists():
        return []
    out = []
    pattern = (re.compile(re.escape(task_id) + r"-tr-\d+\.json$")
               if task_id else re.compile(r".+-tr-\d+\.json$"))
    for p in sorted(TEST_RUNS_DIR.iterdir()):
        if not pattern.match(p.name):
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                out.append(json.load(f))
        except (OSError, json.JSONDecodeError):
            continue
    return out


def write_escalation(test_run_id: str, content: str) -> Path:
    """Escreve escalation file pra structural reject proposal."""
    path = ESCALATIONS_DIR / f"{test_run_id}.md"
    _atomic_write(path, content)
    return path


def list_escalations() -> List[Dict[str, Any]]:
    """Lista escalations pending."""
    if not ESCALATIONS_DIR.exists():
        return []
    out = []
    for p in sorted(ESCALATIONS_DIR.iterdir()):
        if p.is_file() and p.suffix == ".md":
            out.append({"test_run_id": p.stem, "escalation_path": str(p)})
    return out


def clear_escalation(test_run_id: str) -> None:
    path = ESCALATIONS_DIR / f"{test_run_id}.md"
    if path.exists():
        path.unlink()


def read_escalation(path: Union[str, Path]) -> Optional[Dict[str, str]]:
    """Le escalation file e retorna dict do frontmatter ou None.

    Required fields: test_run_id, task_id, decision.
    Files sem frontmatter (formato legacy pre-UBN) retornam None.

    Spec: bevox-knowledge/35_specs/openclaw/2026-04-30-universal-block-notifier.md §3.2
    """
    try:
        content = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    m = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
    if not m:
        return None
    data = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        data[key.strip()] = value.strip()
    if not all(k in data for k in ("test_run_id", "task_id", "decision")):
        return None
    return data
