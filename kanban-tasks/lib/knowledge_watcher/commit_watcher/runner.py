"""runner.py — F1 top-level audit orchestrator (cross-project).

Iterates opted-in projects (via projects_meta), per-project loads
last_commit_processed from state.json, calls process_repo_commits,
dispatches digest via escalation_dispatcher kind=doc-gap (Telegram),
persists last_sha + last_run_at per repo and last_full_audit_at globally.
Cross-project aging integration after loop (warn list → reminder; archive
list → auto-move). dry_run skips state write + Telegram.
Workflow exceptions don't crash loop (poison-commit safety per T9 review).

Spec: bevox-knowledge/35_specs/_shared/2026-05-08-bevox-knowledge-contribute-skill-v2.md §7
Plan: bevox-knowledge/35_specs/_shared/plans/2026-05-08-skill-v2-W3-f1-commit-watcher-plan.md
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

from lib import projects_meta
from lib.knowledge_watcher import state as state_mod
from lib.knowledge_watcher.commit_watcher import AuditResult
from lib.knowledge_watcher.commit_watcher.workflow import process_repo_commits
from lib.knowledge_watcher.commit_watcher.digest import (
    build_digest, build_aging_reminder,
)
from lib.knowledge_watcher.commit_watcher.aging import (
    find_aging_drafts, auto_archive_orphaned,
)


_DEFAULT_STATE_PATH = Path(os.environ.get(
    "OPENCLAW_KNOWLEDGE_WATCHER_STATE",
    str(Path.home() / ".openclaw" / "knowledge-watcher" / "state.json"),
))


from lib.knowledge_watcher.telegram import dispatch_to_telegram as _dispatch_to_telegram


def run_audit(
    meta_path: Path,
    kb_root: Path,
    code_root: Path,
    *,
    project: Optional[str] = None,
    since: Optional[str] = None,
    dry_run: bool = False,
    backfill_limit: int = 50,
    state_path: Optional[Path] = None,
) -> List[AuditResult]:
    """Top-level audit: iterate opted-in projects, process commits, dispatch digests."""
    state_path = state_path or _DEFAULT_STATE_PATH
    if not dry_run:
        state_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        meta = projects_meta.read_meta(meta_path)
    except Exception:
        return []
    state = state_mod.read_state(state_path)

    results: List[AuditResult] = []
    for slug, entry in meta.get("projects", {}).items():
        if project is not None and slug != project:
            continue
        if not projects_meta.is_knowledge_watcher_opted_in(entry):
            results.append(AuditResult(
                repo_slug=slug, new_commits_processed=0,
                gaps_detected=0, gaps=[], last_commit_processed="",
                skipped_reason="knowledge_watcher.opt_in=false",
            ))
            continue
        repo_root = code_root / slug
        if not repo_root.is_dir():
            results.append(AuditResult(
                repo_slug=slug, new_commits_processed=0,
                gaps_detected=0, gaps=[], last_commit_processed="",
                skipped_reason=f"repo missing: {repo_root}",
            ))
            continue

        repo_state = state_mod.get_repo_state(state, slug)
        since_sha = since or repo_state.get("last_commit_processed") or None

        try:
            gaps, last_sha = process_repo_commits(
                slug=slug, repo_root=repo_root, kb_root=kb_root,
                state_path=state_path, state=state,
                since_sha=since_sha, dry_run=dry_run,
                backfill_limit=backfill_limit,
            )
        except Exception as e:
            print(f"[knowledge-watcher] error processing {slug}: {type(e).__name__}: {e}",
                  file=sys.stderr)
            results.append(AuditResult(
                repo_slug=slug, new_commits_processed=0,
                gaps_detected=0, gaps=[], last_commit_processed="",
                skipped_reason=f"error: {type(e).__name__}",
            ))
            continue

        # Always stamp last_run_at on successful processing (even when no
        # new commits arrived). Only bump last_commit_processed when we
        # actually advanced the SHA. Per-repo state is what surfaces in MC
        # /knowledge Watcher · Per-repo and what humans use to detect
        # stalled crons.
        if not dry_run:
            update_fields = {"last_run_at": _now_iso()}
            if last_sha:
                update_fields["last_commit_processed"] = last_sha
            state_mod.set_repo_state(state, slug, update_fields)

        digest_text = build_digest(slug, gaps)
        if digest_text and not dry_run:
            _dispatch_to_telegram(slug, digest_text)

        results.append(AuditResult(
            repo_slug=slug,
            new_commits_processed=len(gaps),
            gaps_detected=len(gaps),
            gaps=gaps,
            last_commit_processed=last_sha or "",
        ))

    # Aging integration (cross-project)
    try:
        warn, archive = find_aging_drafts(kb_root)
    except Exception as e:
        print(f"[knowledge-watcher] aging scan error: {type(e).__name__}: {e}",
              file=sys.stderr)
        warn, archive = [], []

    if warn and not dry_run:
        reminder = build_aging_reminder(warn)
        if reminder:
            _dispatch_to_telegram(None, reminder)
    if archive:
        try:
            moved = auto_archive_orphaned(kb_root, archive, dry_run=dry_run)
            if moved:
                print(f"[knowledge-watcher] auto-archived {len(moved)} aged drafts",
                      file=sys.stderr)
        except Exception as e:
            print(f"[knowledge-watcher] auto-archive error: {type(e).__name__}: {e}",
                  file=sys.stderr)

    if not dry_run:
        # Stamp global audit completion timestamp (visible in MC and used
        # by F2 cross-project digest as "last full audit" reference).
        state.setdefault("global", {})["last_full_audit_at"] = _now_iso()
        state_mod.write_state(state_path, state)

    return results
