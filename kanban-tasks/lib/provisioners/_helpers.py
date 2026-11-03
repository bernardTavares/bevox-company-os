"""Subprocess wrapper that bubbles helper failures with rich context.

The skill helpers (slot_resolve.sh, git_open_draft.sh, git_commit_push.sh)
exit non-zero on validation failures and write diagnostic output to stderr.
We don't want raw `CalledProcessError` strings reaching the orchestrator —
we want the helper name + stderr captured + exit code so JSONL log entries
and operator-facing error messages stay legible.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Sequence


class HelperError(Exception):
    """Raised when a skill helper script returns non-zero.

    Attributes:
        helper: Logical name of the helper (e.g. 'slot_resolve').
        exit_code: Process exit code.
        stderr: Captured stderr (stripped).
        stdout: Captured stdout (stripped).
    """

    def __init__(
        self,
        helper: str,
        exit_code: int,
        stderr: str,
        stdout: str = "",
    ):
        self.helper = helper
        self.exit_code = exit_code
        self.stderr = (stderr or "").strip()
        self.stdout = (stdout or "").strip()
        msg = (
            f"helper '{helper}' failed with exit code {exit_code}"
        )
        if self.stderr:
            msg += f": {self.stderr}"
        super().__init__(msg)


def run_helper(
    helper_name: str,
    cmd: Sequence[str],
    *,
    env: dict | None = None,
    cwd: str | Path | None = None,
    timeout: int = 60,
) -> str:
    """Run a helper script, return stdout. Raise HelperError on non-zero exit.

    Args:
        helper_name: Logical label used in error messages (no path).
        cmd: argv to execute.
        env: Optional env vars (merged on top of os.environ by caller if needed).
        cwd: Optional working directory.
        timeout: Seconds; defaults 60s. Helpers should be quick.

    Returns:
        stdout (stripped).
    """
    try:
        result = subprocess.run(
            list(cmd),
            capture_output=True,
            text=True,
            env=env,
            cwd=str(cwd) if cwd else None,
            timeout=timeout,
        )
    except FileNotFoundError as e:
        raise HelperError(
            helper_name, 127, f"helper script not found: {e}",
        )
    except subprocess.TimeoutExpired as e:
        raise HelperError(
            helper_name, 124,
            f"helper timed out after {timeout}s: {e}",
        )
    if result.returncode != 0:
        raise HelperError(
            helper_name,
            result.returncode,
            result.stderr,
            result.stdout,
        )
    return (result.stdout or "").strip()
