"""git_scan.py — list unprocessed commits per repo via subprocess git."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List, Optional

from lib.knowledge_watcher.commit_watcher import Commit


def _run_git(repo: Path, args: List[str]) -> Optional[str]:
    try:
        out = subprocess.run(
            ["git"] + args, cwd=repo, capture_output=True, text=True, check=True,
        )
        return out.stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def list_unprocessed_commits(
    repo_root: Path,
    *,
    since_sha: Optional[str] = None,
    backfill_limit: int = 50,
    skip_marker: bool = True,
) -> List[Commit]:
    """List new commits in chronological order (oldest first).

    If since_sha is None: returns last `backfill_limit` commits.
    If since_sha is provided: returns commits in <since>..HEAD range.

    Drops commits with [skip-knowledge] in body when skip_marker=True.
    """
    if not (repo_root / ".git").is_dir():
        return []

    if since_sha:
        rev_range = f"{since_sha}..HEAD"
        log_args = ["log", rev_range, "--reverse",
                    "--pretty=format:%H%x1f%h%x1f%s%x1f%b%x1f%an%x1f%aI%x1e"]
    else:
        log_args = [
            "log", "--reverse", f"-n{backfill_limit}",
            "--pretty=format:%H%x1f%h%x1f%s%x1f%b%x1f%an%x1f%aI%x1e",
        ]

    raw = _run_git(repo_root, log_args)
    if not raw:
        return []

    commits: List[Commit] = []
    for record in raw.split("\x1e"):
        record = record.strip()
        if not record:
            continue
        parts = record.split("\x1f")
        if len(parts) < 6:
            continue
        sha, short, subject, body, author, ts = parts[:6]
        if skip_marker and "[skip-knowledge]" in body:
            continue
        files = (_run_git(repo_root, ["show", "--name-only", "--pretty=format:", sha]) or "").strip().splitlines()
        files = [f for f in files if f]
        diffstat = (_run_git(repo_root, ["show", "--stat", "--format=", sha]) or "")[:2000]
        commits.append(Commit(
            sha=sha, short_sha=short, subject=subject.strip(),
            body=body.strip(), files_changed=files, diffstat=diffstat,
            author=author, timestamp_iso=ts,
        ))
    return commits
