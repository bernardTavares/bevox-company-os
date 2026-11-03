"""spec_skeleton.py — Strategy DRAFT_SKELETON for spec doc-type."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from lib.knowledge_watcher.commit_watcher import (
    ClassifierResult, Commit, GapDraft, Strategy,
)


_SKELETON_TEMPLATE = """\
---
title: <preencher: spec curta descritiva>
status: Proposta
data: {today}
source-commit: {short_sha}
source-subject: {subject}
generated-by: openclaw knowledge audit
---

# <preencher>

_Auto-generated skeleton from commit `{short_sha}` — preencher antes de aceitar._

## Contexto

<!-- Por que esta spec existe? Que problema operacional/de produto resolve? -->

## Goals

- [ ] <preencher>

## Non-goals

- <preencher>

## Approach

<!-- Como vamos resolver? Decisões técnicas chave. -->

## Acceptance criteria

- [ ] <preencher>

## Risks

- <preencher>

---

> Auto-flagged from commit `{short_sha}: {subject}`. Review humano obrigatório.
"""


def apply_spec_skeleton_strategy(
    *, commit: Commit, classifier_result: ClassifierResult,
    slug: str, kb_root: Path, dry_run: bool = False,
) -> GapDraft:
    today = datetime.now(timezone.utc).date().isoformat()
    body = _SKELETON_TEMPLATE.format(
        today=today, short_sha=commit.short_sha, subject=commit.subject,
    )

    target = kb_root / "00_inbox" / slug / f"{today}-{commit.short_sha}-spec-draft.md"
    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body)

    rel = str(target.relative_to(kb_root))
    branch = f"draft/auto/{today}-{commit.short_sha}-spec"
    return GapDraft(
        project_slug=slug, commit=commit, classifier_result=classifier_result,
        strategy=Strategy.DRAFT_SKELETON, draft_branch=branch,
        draft_file_relative=rel,
        gaps_entry=f"- [ ] [{commit.short_sha}] spec: {commit.subject} (skeleton draft) — /review | /dismiss | /postpone",
        digest_line=f"{commit.short_sha} {commit.subject} → spec missing | confidence: {classifier_result.confidence:.2f} ({classifier_result.source.value})",
    )
