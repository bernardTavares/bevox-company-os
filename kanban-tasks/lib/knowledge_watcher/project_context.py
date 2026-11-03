"""project_context.py — detect signals about a project for gap-report rules.

Reads:
- git log (age, commits, tags, recent activity)
- filesystem (schema.prisma presence, apps/ subdirs)
- projects-meta entry (source, has_customers, has_metrics flags)

Output: dict with normalized signals consumed by expectations.py.

All helpers degrade gracefully — missing repo, git missing, etc. return
zero/False values rather than raising.
"""
from __future__ import annotations

import datetime as _dt
import subprocess
from pathlib import Path
from typing import Optional


def _run_git(repo: Path, args: list, timeout: int = 5) -> Optional[str]:
    """Run `git -C <repo> <args>`. Return stdout stripped, or None on failure."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo)] + args,
            capture_output=True, text=True, timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return (result.stdout or "").strip()


def _git_age_months(repo: Path) -> int:
    """Months since first commit. 0 if repo missing or no commits."""
    if not repo.is_dir():
        return 0
    output = _run_git(repo, ["log", "--reverse", "--format=%ct", "-n", "1"])
    if not output:
        return 0
    try:
        first_ts = int(output.split("\n")[0])
    except (ValueError, IndexError):
        return 0
    now_ts = _dt.datetime.now().timestamp()
    delta_seconds = now_ts - first_ts
    return int(delta_seconds // (30.44 * 24 * 3600))  # avg month


def _git_commit_count(repo: Path) -> int:
    """Total commits in HEAD. 0 if repo missing."""
    if not repo.is_dir():
        return 0
    output = _run_git(repo, ["rev-list", "--count", "HEAD"])
    if not output:
        return 0
    try:
        return int(output)
    except ValueError:
        return 0


def _git_commits_last_n_days(repo: Path, days: int) -> int:
    """Commits in last N days."""
    if not repo.is_dir():
        return 0
    output = _run_git(repo, [
        "rev-list", "--count", "HEAD", f"--since={days}.days",
    ])
    if not output:
        return 0
    try:
        return int(output)
    except ValueError:
        return 0


def _git_has_tags(repo: Path) -> bool:
    """True if repo has at least 1 tag."""
    if not repo.is_dir():
        return False
    output = _run_git(repo, ["tag", "-l"])
    return bool(output)


def _detect_has_schema_prisma(repo: Path) -> bool:
    """True if any prisma/schema.prisma exists in repo."""
    if not repo.is_dir():
        return False
    candidates = [
        repo / "prisma" / "schema.prisma",
        repo / "apps" / "api" / "prisma" / "schema.prisma",
        repo / "packages" / "db" / "prisma" / "schema.prisma",
    ]
    for c in candidates:
        if c.is_file():
            return True
    return False


def _detect_service_count(repo: Path) -> int:
    """Count distinct subdirs in apps/ + packages/ (not counting node_modules)."""
    if not repo.is_dir():
        return 0
    count = 0
    for top in ("apps", "packages"):
        d = repo / top
        if not d.is_dir():
            continue
        for sub in d.iterdir():
            if sub.is_dir() and sub.name != "node_modules":
                count += 1
    return count


def detect_project_context(repo: Path, meta_entry: dict) -> dict:
    """Build context dict for expectations.py rules.

    Args:
        repo: filesystem path to project repo (e.g. ~/code/<slug>).
        meta_entry: projects-meta.json entry for the slug.

    Returns:
        dict with all signals defined in expectations.py docstring.
    """
    source = meta_entry.get("source") if isinstance(meta_entry, dict) else None
    return {
        "is_adopted": source in ("adopted", "user_created"),
        "age_months": _git_age_months(repo),
        "commit_count": _git_commit_count(repo),
        "commits_last_30d": _git_commits_last_n_days(repo, 30),
        "has_git_tags": _git_has_tags(repo),
        "has_schema_prisma": _detect_has_schema_prisma(repo),
        "service_count": _detect_service_count(repo),
        "has_customers_flag": bool((meta_entry or {}).get("has_customers")),
        "has_metrics_flag": bool((meta_entry or {}).get("has_metrics")),
    }
