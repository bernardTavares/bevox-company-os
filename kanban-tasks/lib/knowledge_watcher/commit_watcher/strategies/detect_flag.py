"""detect_flag.py — Strategy DETECT_FLAG (entry-only, no draft file)."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from lib.knowledge_watcher.commit_watcher import (
    ClassifierResult, Commit, GapDraft, Strategy,
)


def apply_detect_flag_strategy(
    *, commit: Commit, classifier_result: ClassifierResult,
    slug: str, kb_root: Path, doc_type_label: str, dry_run: bool = False,
) -> GapDraft:
    """Entry-only strategy. Does NOT create a draft file in the kb.

    Used for architecture / PRD / roadmap doc-types where auto-template
    would be too speculative. Just flags the commit for human review.

    `dry_run` is accepted for signature consistency with other strategies;
    this strategy never writes a draft file regardless.
    """
    today = datetime.now(timezone.utc).date().isoformat()
    branch = f"draft/auto/{today}-{commit.short_sha}-{doc_type_label}"
    return GapDraft(
        project_slug=slug, commit=commit, classifier_result=classifier_result,
        strategy=Strategy.DETECT_FLAG, draft_branch=branch,
        draft_file_relative=None,  # no draft file
        gaps_entry=f"- [ ] [{commit.short_sha}] {doc_type_label}: {commit.subject} (flagged) — /review | /dismiss | /postpone",
        digest_line=f"{commit.short_sha} {commit.subject} → {doc_type_label} missing | confidence: {classifier_result.confidence:.2f} ({classifier_result.source.value})",
    )
