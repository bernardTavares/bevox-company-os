"""Doctor human-readable rendering.

Pure helpers, no I/O. Spec: W5 §Output humano.
"""
from __future__ import annotations

from typing import List

from lib.doctor.scanner import DraftPending, OrphanReport, ScanResult


def render_scan(result: ScanResult, *, generated_at: str) -> str:
    """Format ScanResult as human-readable text. Mirrors W3 dispatcher style."""
    lines: List[str] = []
    lines.append(f"Project doctor scan @ {generated_at}")
    lines.append("")

    n_projects = len(result.projects)
    lines.append(f"Projects ({n_projects} scanned):")
    if n_projects == 0:
        lines.append("  (no projects in projects-meta.json)")
    else:
        slug_w = max(len("Slug"), max((len(s) for s in result.projects), default=4))
        header = f"  {'Slug':<{slug_w}} | Drifts | Detail"
        sep = "  " + "-" * slug_w + "-+--------+" + "-" * 40
        lines.append(header)
        lines.append(sep)
        for slug in sorted(result.projects):
            proj = result.projects[slug]
            drifts = proj.get("drifts") or []
            n_drift = len(drifts)
            details = []
            for cap in drifts:
                cap_payload = (proj.get("capabilities") or {}).get(cap) or {}
                reason = cap_payload.get("drift_reason") or (
                    f"declared={cap_payload.get('declared')}, "
                    f"detected={cap_payload.get('detected')}"
                )
                short = reason[:60]
                details.append(f"{cap}: {short}")
            detail_col = "; ".join(details) if details else ""
            lines.append(
                f"  {slug:<{slug_w}} | {n_drift:^6} | {detail_col}"
            )

    # Orphans block.
    o = result.orphans
    has_orphans = bool(
        o.code_dirs or o.bot_profiles or o.workspaces or o.bevox_knowledge_slots
    )
    if has_orphans:
        lines.append("")
        lines.append("Orphans:")
        if o.code_dirs:
            lines.append("  code_dirs:")
            for p in o.code_dirs:
                lines.append(f"    {p}")
        if o.bot_profiles:
            lines.append("  bot_profiles:")
            for p in o.bot_profiles:
                lines.append(f"    {p}")
        if o.workspaces:
            lines.append("  workspaces:")
            for p in o.workspaces:
                lines.append(f"    {p}")
        if o.bevox_knowledge_slots:
            lines.append("  bevox_knowledge_slots:")
            for p in o.bevox_knowledge_slots:
                lines.append(f"    {p}")

    # Drafts pending block.
    if result.drafts_pending:
        lines.append("")
        lines.append("Drafts pending merge (knowledge bootstrap):")
        for d in result.drafts_pending:
            slug_part = f"slug: {d.slug}" if d.slug else "slug: ?"
            lines.append(f"  {d.branch}  ({slug_part})")

    # Summary.
    total_orphans = (
        len(o.code_dirs) + len(o.bot_profiles)
        + len(o.workspaces) + len(o.bevox_knowledge_slots)
    )
    n_with_drift = sum(1 for p in result.projects.values() if p.get("drifts"))
    lines.append("")
    lines.append(
        f"Summary: {n_projects} projects, {len(result.drifts)} drifts "
        f"({n_with_drift} projects affected), {total_orphans} orphans, "
        f"{len(result.drafts_pending)} drafts pending."
    )
    if result.drifts or total_orphans:
        lines.append(
            "Run with --fix to repair (interactive) or "
            "--fix --auto-confirm (non-interactive)."
        )
    return "\n".join(lines)


def render_repair_outcomes(outcomes: list) -> str:
    """Format repair phase outcomes as human-readable text."""
    if not outcomes:
        return "No repairs attempted."
    lines: List[str] = ["Repair outcomes:"]
    for o in outcomes:
        suffix = ""
        if o.new_state:
            suffix = f" → {o.new_state}"
        if o.error:
            suffix += f"  [error: {o.error}]"
        lines.append(
            f"  {o.slug}.{o.capability}: {o.action} ({o.reason}){suffix}"
        )
    n_repaired = sum(1 for o in outcomes if o.action == "repaired")
    n_skipped = sum(1 for o in outcomes if o.action != "repaired")
    lines.append("")
    lines.append(f"Total: {n_repaired} repaired, {n_skipped} skipped.")
    return "\n".join(lines)


def build_json_payload(
    result: ScanResult,
    *,
    generated_at: str,
    schema_version: int = 1,
    repair_outcomes: list | None = None,
) -> dict:
    """Build ADR-013 §Drift detection contract estendido (JSON)."""
    o = result.orphans
    payload = {
        "schema_version": schema_version,
        "generated_at": generated_at,
        "projects": result.projects,
        "orphans": {
            "code_dirs": list(o.code_dirs),
            "bot_profiles": list(o.bot_profiles),
            "workspaces": list(o.workspaces),
            "bevox_knowledge_slots": list(o.bevox_knowledge_slots),
        },
        "drafts_pending": [
            {"branch": d.branch, "slug": d.slug, "age_days": d.age_days}
            for d in result.drafts_pending
        ],
        "summary": {
            "projects_scanned": len(result.projects),
            "projects_with_drift": sum(
                1 for p in result.projects.values() if p.get("drifts")
            ),
            "total_drifts": len(result.drifts),
            "total_orphans": (
                len(o.code_dirs) + len(o.bot_profiles)
                + len(o.workspaces) + len(o.bevox_knowledge_slots)
            ),
            "drafts_pending": len(result.drafts_pending),
        },
    }
    if repair_outcomes is not None:
        payload["repairs"] = [
            {
                "slug": x.slug,
                "capability": x.capability,
                "action": x.action,
                "reason": x.reason,
                "new_state": x.new_state,
                "error": x.error,
            }
            for x in repair_outcomes
        ]
    return payload
