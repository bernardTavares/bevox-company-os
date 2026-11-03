"""provision_telegram_topics — wraps scripts/init_telegram_topics.py.

Calls the existing python initializer in subprocess. Idempotent: the
underlying script is itself idempotent (existing topic ids are preserved,
only missing ones are created via Telegram API).

Pre-conditions:
- bot_id present in projects-meta entry (script reads chat_id from there).
- BOT_TOKEN_<UPPER_BOT_ID> env var available (script enforces).

Returns state per detect contract: provisioned (3/3 thread_ids) /
partial (1-2/3) / absent (0/3, or script failure).
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class TopicsResult:
    state: str  # provisioned | partial | absent
    created: List[str] = field(default_factory=list)
    existing: List[str] = field(default_factory=list)
    failed: List[Dict] = field(default_factory=list)
    error: Optional[str] = None
    stdout: Optional[str] = None


def provision_telegram_topics(
    slug: str,
    *,
    openclaw_dir: Path,
    meta_path: Optional[Path] = None,
    timeout: int = 30,
) -> TopicsResult:
    """Initialize canonical Telegram forum topics for slug's group.

    Args:
        slug: project id.
        openclaw_dir: ~/.openclaw root (locates init_telegram_topics.py).
        meta_path: explicit projects-meta.json path (defaults to script default).
        timeout: subprocess timeout seconds.

    Returns:
        TopicsResult.
    """
    script = openclaw_dir / "scripts" / "init_telegram_topics.py"
    if not script.is_file():
        return TopicsResult(
            state="absent",
            error=f"init_telegram_topics.py not found at {script}",
        )

    cmd = ["python3", str(script), "--slug", slug]
    if meta_path is not None:
        cmd.extend(["--meta", str(meta_path)])

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
    except FileNotFoundError as e:
        return TopicsResult(
            state="absent",
            error=f"python3 not found: {e}",
        )
    except subprocess.TimeoutExpired:
        return TopicsResult(
            state="partial",
            error=f"init_telegram_topics timed out after {timeout}s",
        )

    if result.returncode != 0:
        return TopicsResult(
            state="absent",
            error=(result.stderr or "").strip()
                  or f"init_telegram_topics exit {result.returncode}",
            stdout=(result.stdout or "").strip(),
        )

    # Parse stdout JSON: {"created": [...], "existing": [...], "failed": [...]}
    try:
        payload = json.loads((result.stdout or "").strip() or "{}")
    except json.JSONDecodeError:
        return TopicsResult(
            state="partial",
            error="init_telegram_topics returned non-JSON stdout",
            stdout=(result.stdout or "").strip(),
        )

    created = payload.get("created") or []
    existing = payload.get("existing") or []
    failed = payload.get("failed") or []

    total_ok = len(created) + len(existing)
    if failed:
        cap_state = "partial"
    elif total_ok >= 2:
        # Script handles 2 canonical (clarifications, dispatcher); 'blocks' is
        # added separately by UBN and tolerated by detect.
        cap_state = "provisioned"
    elif total_ok > 0:
        cap_state = "partial"
    else:
        cap_state = "absent"

    return TopicsResult(
        state=cap_state,
        created=created,
        existing=existing,
        failed=failed,
        stdout=(result.stdout or "").strip(),
    )
