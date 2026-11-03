"""workflow.py — F3 top-level greenfield bootstrap pipeline orchestrator."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Set

import lib.projects_meta as _pm
from lib.knowledge_watcher.greenfield import (
    BootstrapResult, DocGenResult, SourceSignals, Tier,
)
from lib.knowledge_watcher.greenfield.signals import read_source_signals
from lib.knowledge_watcher.greenfield.topic_detector import detect_adr_topics
from lib.knowledge_watcher.greenfield.adr_canonical_scan import (
    scan_canonical_adrs, detect_overlap, _topic_keywords,
)
from lib.knowledge_watcher.greenfield.generators.architecture import (
    generate_architecture,
)
from lib.knowledge_watcher.greenfield.generators.release_notes import (
    generate_release_notes,
)
from lib.knowledge_watcher.greenfield.generators.prd import generate_prd
from lib.knowledge_watcher.greenfield.generators.roadmap import generate_roadmap
from lib.knowledge_watcher.greenfield.generators.adr import generate_adrs


_DEFAULT_META_PATH = Path.home() / ".openclaw" / "projects-meta.json"


_DEFAULT_STATE_PATH = (
    Path.home() / ".openclaw" / "knowledge-watcher" / "state.json"
)


def _dry_run_placeholders(signals: SourceSignals) -> List[DocGenResult]:
    today = datetime.now(timezone.utc).date().isoformat()
    return [
        DocGenResult(
            tier=Tier.SEMI_AUTO,
            doc_type="prd",
            relative_path=f"10_prd/{signals.slug}/{today}-{signals.slug}-prd.md",
            content="(dry-run)",
            cost_usd=0.0,
            warnings=["dry_run"],
        ),
        DocGenResult(
            tier=Tier.SEMI_AUTO,
            doc_type="roadmap",
            relative_path=f"40_roadmap/{signals.slug}/{today}-{signals.slug}-roadmap.md",
            content="(dry-run)",
            cost_usd=0.0,
            warnings=["dry_run"],
        ),
    ]


def _apply_idempotence(kb_root: Path, results: List[DocGenResult]) -> None:
    for r in results:
        if not r.content:
            continue
        target = kb_root / r.relative_path
        if target.exists():
            r.content = ""
            r.cost_usd = 0.0
            r.warnings.append("already exists, skipped")


def _write_results(kb_root: Path, results: List[DocGenResult]) -> None:
    for r in results:
        if not r.content:
            continue
        if "already exists, skipped" in r.warnings:
            continue
        target = kb_root / r.relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(r.content, encoding="utf-8")


def bootstrap_project(
    slug: str,
    kb_root: Path,
    code_root: Path,
    *,
    dry_run: bool = False,
    no_adr: bool = False,
    state_path: Optional[Path] = None,
    budget_usd: float = 5.0,
    force_topics: Optional[List[str]] = None,  # W5: bypass overlap filter
    push_draft: bool = False,  # W7-extras: auto-push to draft branch
) -> BootstrapResult:
    """Top-level F3 bootstrap pipeline. Returns BootstrapResult."""
    started = time.perf_counter()
    repo_root = code_root / slug
    if not repo_root.is_dir():
        return BootstrapResult(
            slug=slug, docs_generated=[],
            total_cost_usd=0.0, duration_seconds=0.0,
            skipped_reason=f"repo missing: {repo_root}",
        )

    signals = read_source_signals(slug, repo_root)
    state_path = state_path or _DEFAULT_STATE_PATH

    all_results: List[DocGenResult] = []

    # Tier MECÂNICO
    all_results.append(generate_architecture(signals))
    all_results.extend(generate_release_notes(signals))

    # Tier SEMI-AUTO
    if dry_run:
        all_results.extend(_dry_run_placeholders(signals))
    else:
        all_results.append(generate_prd(signals, state_path=state_path, budget_usd=budget_usd))
        all_results.append(generate_roadmap(signals, state_path=state_path, budget_usd=budget_usd))

    # Tier JUDGMENT
    if not no_adr:
        topics = detect_adr_topics(signals)
        if topics:
            # W5: scan canonical 30_adr/<slug>/ once; filter overlapping topics
            override_prefix: Optional[str] = None
            try:
                meta = _pm.read_meta(_DEFAULT_META_PATH)
                override_prefix = _pm.get_adr_prefix(slug, meta)
            except Exception:
                pass  # safe fallback to auto-detect

            adr_scan = scan_canonical_adrs(kb_root, slug, override_prefix=override_prefix)

            force_set: Set[str] = set(force_topics or [])
            filtered_topics = []
            for t in topics:
                if t.slug in force_set:
                    filtered_topics.append(t)
                    continue
                kws = _topic_keywords(t.slug, t.title)
                overlap = detect_overlap(adr_scan, t.slug, kws)
                if overlap:
                    all_results.append(DocGenResult(
                        tier=Tier.JUDGMENT,
                        doc_type="adr",
                        relative_path=f"30_adr/{slug}/(skipped)-{t.slug}.md",
                        content="",
                        cost_usd=0.0,
                        warnings=[
                            f"overlap with {', '.join(overlap)} (skipped; "
                            f"use --force-topic {t.slug} to override)"
                        ],
                    ))
                else:
                    filtered_topics.append(t)

            if filtered_topics:
                all_results.extend(generate_adrs(
                    signals, filtered_topics, kb_root,
                    dry_run=dry_run, scan=adr_scan,
                ))

    _apply_idempotence(kb_root, all_results)
    if not dry_run:
        _write_results(kb_root, all_results)

        # Stamp each generated output (skip placeholders + already-existing
        # docs; those didn't actually run a generator). Best-effort — silent
        # on errors so feedback never blocks F3.
        try:
            from lib.knowledge_watcher.feedback import (
                record_f3_output_initial,
            )
            for r in all_results:
                if "(skipped)" in r.relative_path:
                    continue
                if any("already exists" in w for w in r.warnings):
                    continue
                if not r.content:
                    continue
                record_f3_output_initial(
                    doc_path=r.relative_path,
                    generator=r.doc_type,
                    prompt_hash="",
                    content=r.content,
                    cost_usd=r.cost_usd,
                )
        except Exception:
            pass

    duration = time.perf_counter() - started
    total_cost = sum(r.cost_usd for r in all_results)

    if not dry_run and total_cost > 0:
        from lib.knowledge_watcher.cost_tracker import record_f3_cost
        record_f3_cost(state_path, total_cost)

    draft_branch_name: Optional[str] = None
    if push_draft and not dry_run:
        from lib.knowledge_watcher.greenfield.draft_branch import (
            push_to_draft_branch,
        )
        written: List[Path] = []
        for r in all_results:
            if "(skipped)" in r.relative_path:
                continue
            if any("already exists" in w for w in r.warnings):
                continue
            p = kb_root / r.relative_path
            if p.exists():
                written.append(p)
        if written:
            db = push_to_draft_branch(kb_root, slug, written)
            if db.ok:
                draft_branch_name = db.branch

    return BootstrapResult(
        slug=slug,
        docs_generated=all_results,
        total_cost_usd=total_cost,
        duration_seconds=duration,
        skipped_reason=None,
        draft_branch=draft_branch_name,
    )
