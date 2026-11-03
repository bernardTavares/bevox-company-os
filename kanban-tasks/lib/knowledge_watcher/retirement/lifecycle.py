"""lifecycle.py — Categoria D (status:done + age threshold)."""
from __future__ import annotations

import datetime as _dt
import re
import subprocess
from pathlib import Path
from typing import List, Optional

from lib.knowledge_watcher.retirement import (
    CategorySignal, RetirementCategory,
)


_STATUS_DONE_RE = re.compile(
    r"(?im)^\s*status\s*:\s*(done|completed|complete|conclu[ií]da)\b",
)


def _get_file_last_commit_age_days(doc_path: Path) -> Optional[int]:
    """Days since last git commit touching this file. None if not in git."""
    if not doc_path.is_file():
        return None
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%ct", str(doc_path)],
            capture_output=True, text=True, timeout=5,
            cwd=doc_path.parent,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    output = (result.stdout or "").strip()
    if not output:
        return None
    try:
        last_ts = int(output)
    except ValueError:
        return None
    delta = _dt.datetime.now().timestamp() - last_ts
    return int(delta // 86400)


def detect_lifecycle(doc_path: Path, age_threshold_days: int = 90) -> List[CategorySignal]:
    """Cat D: Status: Done + last commit >= threshold days ago."""
    if not doc_path.is_file():
        return []
    try:
        content = doc_path.read_text(encoding="utf-8")
    except OSError:
        return []
    if not _STATUS_DONE_RE.search(content):
        return []
    age = _get_file_last_commit_age_days(doc_path)
    if age is None or age < age_threshold_days:
        return []
    return [CategorySignal(
        category=RetirementCategory.D_LIFECYCLE,
        confidence=0.5,
        evidence=f"Status: Done/Completed + last commit {age}d ago (threshold {age_threshold_days}d)",
    )]
