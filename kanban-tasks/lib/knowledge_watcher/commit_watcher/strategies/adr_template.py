"""adr_template.py — Strategy DETECT_FLAG_TEMPLATE for ADR doc-type."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from lib.knowledge_watcher.commit_watcher import (
    ClassifierResult, Commit, GapDraft, Strategy,
)


_ADR_TEMPLATE = """\
---
title: <preencher: ADR — decisão arquitetural>
status: Proposta
data: {today}
source-commit: {short_sha}
source-subject: {subject}
generated-by: openclaw knowledge audit
---

# ADR — <preencher>

_Auto-generated template from commit `{short_sha}` — preencher antes de aceitar._

## Contexto

<!-- Que problema/situação levou a esta decisão? Restrições e trade-offs. -->

## Decisão

<!-- O que foi decidido. Seja específico. -->

## Alternativas consideradas

- <preencher>

## Consequências

- <preencher: positivas e negativas>

---

> Auto-flagged from commit `{short_sha}: {subject}`. Topic hint: {topic_hint}
> Review humano obrigatório antes de Status: Aceita.
"""


def _topic_hint(commit: Commit) -> str:
    """Heuristic on what kind of decision this likely is."""
    files = " ".join(commit.files_changed)
    if "prisma/schema.prisma" in files:
        return "schema/data model"
    if "middleware/auth" in files:
        return "auth/security"
    if any(f.endswith((".dockerfile", "Dockerfile")) or "docker-compose" in f for f in commit.files_changed):
        return "infra/deploy"
    if any("integration" in f.lower() or "provider" in f.lower() for f in commit.files_changed):
        return "external integration"
    return "general architectural"


def apply_adr_template_strategy(
    *, commit: Commit, classifier_result: ClassifierResult,
    slug: str, kb_root: Path, dry_run: bool = False,
) -> GapDraft:
    today = datetime.now(timezone.utc).date().isoformat()
    body = _ADR_TEMPLATE.format(
        today=today, short_sha=commit.short_sha, subject=commit.subject,
        topic_hint=_topic_hint(commit),
    )

    target = kb_root / "00_inbox" / slug / f"{today}-{commit.short_sha}-adr-template.md"
    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body)

    rel = str(target.relative_to(kb_root))
    branch = f"draft/auto/{today}-{commit.short_sha}-adr"
    return GapDraft(
        project_slug=slug, commit=commit, classifier_result=classifier_result,
        strategy=Strategy.DETECT_FLAG_TEMPLATE, draft_branch=branch,
        draft_file_relative=rel,
        gaps_entry=f"- [ ] [{commit.short_sha}] adr: {commit.subject} (template) — /review | /dismiss | /postpone",
        digest_line=f"{commit.short_sha} {commit.subject} → ADR missing | confidence: {classifier_result.confidence:.2f} ({classifier_result.source.value})",
    )
