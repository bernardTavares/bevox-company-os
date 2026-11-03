"""git_ops — wrappers for skill-V2 W3.5 git operations.

All operations are local (no push by default unless explicitly requested).
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Tuple


def _git(args: list[str], cwd: Path, check: bool = True) -> Tuple[int, str, str]:
    p = subprocess.run(
        ["git"] + args, cwd=cwd, capture_output=True, text=True,
    )
    if check and p.returncode != 0:
        raise RuntimeError(f"git {args}: {p.stderr.strip()}")
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def commit_in_draft_branch(
    repo: Path, branch: str, file_relpath: str,
    commit_msg: str, push: bool = False,
) -> str:
    """Checkout/create draft branch, commit single file, optionally push.
    Restores original branch after operation. Returns commit SHA.
    """
    _, current, _ = _git(["rev-parse", "--abbrev-ref", "HEAD"], repo)
    # Use -B only for creation; if branch already exists, just switch to it
    # to avoid resetting it to current HEAD (which would drop prior commits).
    rc, _, _ = _git(["rev-parse", "--verify", branch], repo, check=False)
    if rc == 0:
        _git(["checkout", branch], repo)
    else:
        _git(["checkout", "-b", branch], repo)
    _git(["add", file_relpath], repo)
    _git(["commit", "-m", commit_msg, "--allow-empty"], repo)
    _, sha, _ = _git(["rev-parse", "HEAD"], repo)
    if push:
        _git(["push", "-u", "origin", branch], repo)
    _git(["checkout", current], repo)
    return sha


def branch_url(remote_url: str, branch: str) -> str:
    """Build GitHub tree URL from remote + branch."""
    base = remote_url.rstrip("/")
    if base.endswith(".git"):
        base = base[:-4]
    return f"{base}/tree/{branch}"


def move_to_retired(
    repo: Path, src_relpath: str, dest_relpath: str, branch: str,
    push: bool = False,
) -> str:
    """git mv src→dest in draft branch. Restores original branch after.

    Returns commit SHA (full 40-char). Branch is created if it does not exist.
    """
    _, current, _ = _git(["rev-parse", "--abbrev-ref", "HEAD"], repo)
    rc, _, _ = _git(["rev-parse", "--verify", branch], repo, check=False)
    if rc == 0:
        _git(["checkout", branch], repo)
    else:
        _git(["checkout", "-b", branch], repo)
    dest = repo / dest_relpath
    dest.parent.mkdir(parents=True, exist_ok=True)
    _git(["mv", src_relpath, dest_relpath], repo)
    _git(["commit", "-m", f"chore(retire): move {src_relpath} -> {dest_relpath}"], repo)
    _, sha, _ = _git(["rev-parse", "HEAD"], repo)
    if push:
        _git(["push", "-u", "origin", branch], repo)
    _git(["checkout", current], repo)
    return sha


def ff_merge_to_main(repo: Path, branch: str, push: bool = False) -> str:
    """Fast-forward merge `branch` into main. Fails if not FF-able.

    Returns SHA on main after merge (full 40-char).
    """
    _git(["checkout", "main"], repo)
    rc, _, err = _git(["merge", "--ff-only", branch], repo, check=False)
    if rc != 0:
        raise RuntimeError(f"FF-merge falhou: {err}")
    _, sha, _ = _git(["rev-parse", "HEAD"], repo)
    if push:
        _git(["push", "origin", "main"], repo)
    return sha
