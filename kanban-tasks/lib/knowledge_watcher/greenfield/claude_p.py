"""claude_p.py — subprocess wrapper para `claude -p` calls.

Mirror do lib/persona_extractor.py pattern (mc-projects-factory wave-2).
Used by Tier JUDGMENT (ADR generation, parallel via ThreadPoolExecutor).
"""
from __future__ import annotations

import subprocess
from typing import Optional

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_TIMEOUT_S = 300


def run_claude_p(
    prompt: str, *, model: str = DEFAULT_MODEL, timeout_s: int = DEFAULT_TIMEOUT_S,
) -> Optional[str]:
    """Run `claude -p --model <model>` with prompt as stdin.

    Returns stdout on success, None on:
    - subprocess timeout
    - claude CLI not found (FileNotFoundError)
    - non-zero exit code
    - empty stdout
    - any other OSError
    """
    cmd = ["claude", "-p", "--model", model]
    try:
        result = subprocess.run(
            cmd, input=prompt, capture_output=True, text=True, timeout=timeout_s,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if result.returncode != 0:
        return None
    output = (result.stdout or "").strip()
    return output if output else None
