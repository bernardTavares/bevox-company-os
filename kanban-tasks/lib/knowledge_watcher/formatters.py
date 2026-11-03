"""formatters.py — render gap_report + retirement-scan → human markdown OR JSON."""
from __future__ import annotations

import json
from typing import List

from lib.knowledge_watcher.gap_report import ProjectGapReport
from lib.knowledge_watcher.expectations import Severity
from lib.knowledge_watcher.retirement import RetirementCandidate


def format_human(reports: List[ProjectGapReport]) -> str:
    """Markdown-style table per project with gaps."""
    if not reports:
        return "📊 [knowledge-watcher cross-project audit]\n\nNo opted-in projects to audit.\n"

    lines = ["📊 [knowledge-watcher cross-project audit]", ""]
    projects_with_gaps = [r for r in reports if r.gaps]
    projects_clean = [r for r in reports if not r.gaps]

    if projects_with_gaps:
        lines.append(f"{len(projects_with_gaps)} project(s) with gaps:")
        lines.append("")
        for r in projects_with_gaps:
            lines.append(f"**{r.slug}**:")
            missing = [g for g in r.gaps if g.severity == Severity.ALWAYS_REQUIRED]
            conditional = [g for g in r.gaps if g.severity == Severity.CONDITIONAL]
            if missing:
                folders = ", ".join(f"`{g.folder}/`" for g in missing)
                lines.append(f"  ❌ MISSING (always-required): {folders}")
            if conditional:
                for g in conditional:
                    lines.append(f"  ⚠️ GAP `{g.folder}/` — {g.reason}")
            lines.append("")
    else:
        lines.append("No gaps detected. ✅")
        lines.append("")

    if projects_clean:
        lines.append(f"Clean (no gaps): {', '.join(r.slug for r in projects_clean)}")
        lines.append("")

    return "\n".join(lines)


def format_json(reports: List[ProjectGapReport]) -> str:
    """JSON output (machine-parseable)."""
    payload = []
    for r in reports:
        payload.append({
            "slug": r.slug,
            "context": r.context,
            "gaps": [
                {
                    "folder": g.folder,
                    "severity": g.severity.value,
                    "canonical_count": g.canonical_count,
                    "reason": g.reason,
                }
                for g in r.gaps
            ],
        })
    return json.dumps(payload, indent=2, ensure_ascii=False)


# --- F4 retirement formatters ---


def format_retirement_human(candidates: List[RetirementCandidate]) -> str:
    """Render retirement candidates as human-readable markdown.

    W3.5: include /retire /keep /keep-permanent gap_id commands per
    slugged candidate. _shared candidates render sem comandos.
    """
    if not candidates:
        return "🔎 [retirement scan]\n\nNo retirement candidates detected. ✅\n"

    from lib.knowledge_watcher.gap_registry import derive_gap_id_f4

    lines = ["🔎 [retirement scan]", ""]
    lines.append(f"{len(candidates)} retirement candidate(s):")
    lines.append("")

    for c in candidates:
        slug = c.project_slug if c.project_slug else "_shared"
        lines.append(
            f"**{c.relative_path}** (score {c.score:.2f}, project={slug})"
        )
        for sig in c.signals:
            lines.append(
                f"  - {sig.category.value} ({sig.confidence:.2f}): {sig.evidence}"
            )
        if c.project_slug is not None:
            gid = derive_gap_id_f4(c.project_slug, c.relative_path)
            lines.append(f"  /retire {gid} | /keep {gid} | /keep-permanent {gid}")
        else:
            lines.append("  (_shared — sem comandos diretos; resolver manual)")
        lines.append("")

    lines.append("Review humano obrigatório (nunca auto-retira).")
    lines.append("")
    return "\n".join(lines)


def format_retirement_json(candidates: List[RetirementCandidate]) -> str:
    """Render retirement candidates as JSON (machine-parseable)."""
    payload = []
    for c in candidates:
        payload.append({
            "path": c.relative_path,
            "project_slug": c.project_slug,
            "score": c.score,
            "signals": [
                {
                    "category": sig.category.value,
                    "confidence": sig.confidence,
                    "evidence": sig.evidence,
                }
                for sig in c.signals
            ],
        })
    return json.dumps(payload, indent=2, ensure_ascii=False)
