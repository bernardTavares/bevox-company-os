"""workflow.py — Process repo commits through classify → strategy → gaps.md.

T9 — orchestrator that ties together git_scan + classifier + strategies and
appends entries to `00_inbox/<slug>/_gaps.md`. Always advances last_sha (even
for NONE-classified commits) for idempotência. Never auto-merges; review
humano sempre.

Spec: bevox-knowledge/35_specs/_shared/2026-05-08-bevox-knowledge-contribute-skill-v2.md §7
Plan: bevox-knowledge/35_specs/_shared/plans/2026-05-08-skill-v2-W3-f1-commit-watcher-plan.md
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from lib.knowledge_watcher.commit_watcher import (
    Commit,
    ClassifierResult,
    DocType,
    GapDraft,
)
from lib.knowledge_watcher.commit_watcher.classifier import classify
from lib.knowledge_watcher.commit_watcher.git_scan import list_unprocessed_commits
from lib.knowledge_watcher.commit_watcher.strategies.adr_template import (
    apply_adr_template_strategy,
)
from lib.knowledge_watcher.commit_watcher.strategies.detect_flag import (
    apply_detect_flag_strategy,
)
from lib.knowledge_watcher.commit_watcher.strategies.release_note import (
    apply_release_note_strategy,
)
from lib.knowledge_watcher.commit_watcher.strategies.spec_skeleton import (
    apply_spec_skeleton_strategy,
)


_GAPS_HEADER = """\
# Documentation gaps — {slug}

> Auto-flagged by `openclaw knowledge audit`. Review humano obrigatório.
> Cada entrada vincula a um commit + decisão do classifier.

"""


def _append_gaps_entry(kb_root: Path, slug: str, entry: str) -> None:
    target = kb_root / "00_inbox" / slug / "_gaps.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_text(_GAPS_HEADER.format(slug=slug))
    with target.open("a", encoding="utf-8") as f:
        f.write(entry + "\n")


def _dispatch_strategy(
    commit: Commit,
    result: ClassifierResult,
    *,
    slug: str,
    repo_root: Path,
    kb_root: Path,
    dry_run: bool = False,
) -> Optional[GapDraft]:
    dt = result.doc_type
    if dt == DocType.RELEASE_NOTE:
        return apply_release_note_strategy(
            commit=commit,
            classifier_result=result,
            repo_root=repo_root,
            slug=slug,
            kb_root=kb_root,
            dry_run=dry_run,
        )
    if dt == DocType.SPEC:
        return apply_spec_skeleton_strategy(
            commit=commit,
            classifier_result=result,
            slug=slug,
            kb_root=kb_root,
            dry_run=dry_run,
        )
    if dt == DocType.ADR:
        return apply_adr_template_strategy(
            commit=commit,
            classifier_result=result,
            slug=slug,
            kb_root=kb_root,
            dry_run=dry_run,
        )
    if dt in (DocType.ARCHITECTURE, DocType.PRD, DocType.ROADMAP):
        return apply_detect_flag_strategy(
            commit=commit,
            classifier_result=result,
            slug=slug,
            kb_root=kb_root,
            doc_type_label=dt.value,
            dry_run=dry_run,
        )
    return None  # NONE / unknown


def process_repo_commits(
    *,
    slug: str,
    repo_root: Path,
    kb_root: Path,
    state_path: Path,
    state: Optional[Dict[str, Any]] = None,
    since_sha: Optional[str] = None,
    dry_run: bool = False,
    backfill_limit: int = 50,
) -> Tuple[List[GapDraft], Optional[str]]:
    """Process new commits in repo: classify each, apply strategy, append _gaps.md.

    Returns (gaps_list, last_processed_sha). last_sha is None when there are
    no unprocessed commits AND no since_sha was provided; if since_sha was
    provided we keep it stable. Always advances last_sha for every commit
    iterated (even NONE-classified) for idempotência.
    """
    commits = list_unprocessed_commits(
        repo_root,
        since_sha=since_sha,
        backfill_limit=backfill_limit,
    )
    if not commits:
        return ([], since_sha)

    gaps: List[GapDraft] = []
    last_sha = since_sha
    for commit in commits:
        result = classify(commit, state_path=state_path)
        last_sha = commit.sha
        if result.doc_type == DocType.NONE:
            continue
        gap = _dispatch_strategy(
            commit,
            result,
            slug=slug,
            repo_root=repo_root,
            kb_root=kb_root,
            dry_run=dry_run,
        )
        if gap is None:
            continue
        gaps.append(gap)
        if not dry_run:
            _append_gaps_entry(kb_root, slug, gap.gaps_entry)
        if state is not None and not dry_run:
            from datetime import datetime, timezone
            from ..gap_registry import GapRecord, GapStatus, GapSource, add_gap
            record = GapRecord(
                gap_id=gap.gap_id,
                repo=slug,
                source=GapSource.F1,
                status=GapStatus.OPEN,
                doc_type=gap.classifier_result.doc_type.value,
                commit_sha=gap.commit.sha,
                path=gap.draft_file_relative or "",
                draft_branch=gap.draft_branch,
                created_at=datetime.now(timezone.utc),
                snooze_until=None,
            )
            add_gap(state, record)
    return (gaps, last_sha)
