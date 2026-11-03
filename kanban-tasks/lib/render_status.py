"""Pure rendering helpers for `openclaw project status`.

Spec: bevox-knowledge/35_specs/openclaw/2026-05-07-project-lifecycle-w3-v1.md §Output
ADR: bevox-knowledge/30_adr/openclaw/ADR-013-project-capability-state-machine.md

This module is intentionally side-effect free (no I/O, no time.now()) so renderings
are deterministic and trivially testable. ASCII only — no ANSI escapes.
"""
from __future__ import annotations

from typing import Any

# Canonical capability order (matches projects_meta.CAPABILITY_NAMES + ADR-013).
CAPABILITY_ORDER = (
    "code_repo",
    "knowledge_slot",
    "kanban_sprints",
    "workspace",
    "persona",
    "bot",
    "telegram_topics",
    "mission_control",
)

# Short column headers for dispatcher (horizontal) table — must fit 80-col.
DISPATCHER_HEADERS = {
    "code_repo": "code",
    "knowledge_slot": "know",
    "kanban_sprints": "kan",
    "workspace": "wks",
    "persona": "per",
    "bot": "bot",
    "telegram_topics": "top",
    "mission_control": "mc",
}

# Single-letter codes for dispatcher matrix.
# P=provisioned, p=partial, -=absent, ?=drifted/skipped, !=error
STATE_CODE = {
    "provisioned": "P",
    "partial": "p",
    "absent": "-",
    "drifted": "?",
    "skipped": "?",
    "error": "!",
}

LEGEND = (
    "Legend: P=provisioned, p=partial, -=absent, "
    "?=drifted/skipped, !=error"
)


def _state_code(detected: dict | None, drift: bool) -> str:
    """Pick single-letter code for dispatcher matrix.

    Priority: error > drift > raw state. `detected=None` (--no-detect) → `-`
    semantically falls back to declared state by callers; this helper assumes
    caller passes the chosen dict.
    """
    if detected is None:
        return "-"
    state = detected.get("state", "absent")
    if state == "error":
        return "!"
    if drift:
        return "?"
    return STATE_CODE.get(state, "-")


def _is_drift(declared: dict | None, detected: dict | None) -> bool:
    """True iff declared.state != detected.state (and both present).

    `skipped` never marks drift (we couldn't compare).
    `--no-detect` (detected=None) never marks drift.
    Missing declared (None) is treated as 'absent'.
    """
    if detected is None:
        return False
    det_state = detected.get("state")
    if det_state in (None, "skipped"):
        return False
    decl_state = (declared or {}).get("state", "absent")
    return decl_state != det_state


def compute_diff(
    capabilities_declared: dict,
    capabilities_detected: dict | None,
) -> dict:
    """Build per-capability diff dict consumable by both renderers + JSON.

    Output shape (per capability):
    {
        "declared": dict | None,
        "detected": dict | None,
        "drift": bool,
        "drift_reason": str | None,
    }
    """
    out: dict[str, dict] = {}
    detected_map = capabilities_detected or {}
    for cap in CAPABILITY_ORDER:
        declared = (capabilities_declared or {}).get(cap)
        detected = (
            detected_map.get(cap) if capabilities_detected is not None else None
        )
        drift = _is_drift(declared, detected)
        reason: str | None = None
        if drift:
            decl_state = (declared or {}).get("state", "absent")
            det_state = (detected or {}).get("state", "absent")
            # Prefer detect's own drift_reason if any.
            reason = (detected or {}).get("drift_reason") or \
                f"declared={decl_state}, detected={det_state}"
        elif detected and detected.get("drift_reason"):
            # Surface non-drift caveats (e.g., skipped reason).
            reason = detected.get("drift_reason")
        out[cap] = {
            "declared": declared,
            "detected": detected,
            "drift": drift,
            "drift_reason": reason,
        }
    return out


def _state_label(d: dict | None) -> str:
    if d is None:
        return "-"
    return d.get("state", "?")


def render_single_project(
    slug: str,
    meta_entry: dict,
    diff: dict,
    *,
    detect_skipped: bool = False,
) -> str:
    """Vertical table for single-project mode (human-readable).

    `diff` is the output of compute_diff().
    `detect_skipped` flips the "Detected" column to '(skipped)' label.
    """
    lines: list[str] = []
    source = meta_entry.get("source", "?")
    created = meta_entry.get("created_at", "?")
    lines.append(f"Project: {slug}  (source: {source}, created {created})")
    lines.append("")

    # Column widths sized to spec layout.
    name_w, decl_w, det_w = 18, 13, 13
    header = (
        f"  {'Capability':<{name_w}}| {'Declared':<{decl_w}}| "
        f"{'Detected':<{det_w}}| Drift"
    )
    lines.append(header)
    lines.append(
        "  " + "-" * name_w + "|" + "-" * (decl_w + 1)
        + "|" + "-" * (det_w + 1) + "|------"
    )

    n_provisioned = n_partial = n_absent = n_drift = 0
    for cap in CAPABILITY_ORDER:
        row = diff[cap]
        decl_state = _state_label(row["declared"])
        if detect_skipped:
            det_state = "(skipped)"
        else:
            det_state = _state_label(row["detected"])
        # Drift column.
        if row["drift"]:
            n_drift += 1
            reason = row.get("drift_reason") or ""
            # Truncate reason to keep line printable.
            short = reason[:40]
            drift_col = f"DRIFT ({short})" if short else "DRIFT"
        else:
            drift_col = ""
        lines.append(
            f"  {cap:<{name_w}}| {decl_state:<{decl_w}}| "
            f"{det_state:<{det_w}}| {drift_col}"
        )
        if decl_state == "provisioned":
            n_provisioned += 1
        elif decl_state == "partial":
            n_partial += 1
        elif decl_state == "absent":
            n_absent += 1

    lines.append("")
    lines.append(
        f"  Summary: {n_provisioned} provisioned, {n_partial} partial, "
        f"{n_absent} absent, {n_drift} drift detected."
    )
    return "\n".join(lines)


def render_dispatcher_table(diffs_by_slug: dict[str, dict]) -> str:
    """Horizontal table for all-projects mode.

    `diffs_by_slug`: {slug: diff_dict_from_compute_diff}.
    """
    if not diffs_by_slug:
        return "(no projects in projects-meta.json)"

    slug_w = max(len("Slug"), max(len(s) for s in diffs_by_slug))
    cell_w = 4  # fits ' P  ', ' -  ', etc.

    header_cells = [DISPATCHER_HEADERS[cap].center(cell_w) for cap in CAPABILITY_ORDER]
    header = (
        f"{'Slug':<{slug_w}} | " + " | ".join(header_cells) + " | Drifts"
    )
    sep = (
        "-" * slug_w + "-|-"
        + "-|-".join("-" * cell_w for _ in CAPABILITY_ORDER)
        + "-|-------"
    )

    lines = [header, sep]
    for slug in sorted(diffs_by_slug):
        diff = diffs_by_slug[slug]
        cells = []
        n_drift = 0
        for cap in CAPABILITY_ORDER:
            row = diff[cap]
            detected = row["detected"]
            declared = row["declared"]
            # If detect was skipped (None), fall back to declared state code.
            if detected is None:
                code = STATE_CODE.get(
                    (declared or {}).get("state", "absent"), "-"
                )
            else:
                code = _state_code(detected, row["drift"])
            if row["drift"]:
                n_drift += 1
            cells.append(code.center(cell_w))
        drift_col = str(n_drift) if n_drift else ""
        lines.append(
            f"{slug:<{slug_w}} | " + " | ".join(cells) + f" | {drift_col}"
        )
    return "\n".join(lines)


def build_json_payload(
    generated_at: str,
    projects_diff: dict[str, tuple[dict, dict]],
    *,
    detect_skipped: bool = False,
) -> dict:
    """Build ADR-013 §Drift detection contract JSON.

    `projects_diff[slug] = (meta_entry, diff_dict)`.
    """
    out: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": generated_at,
        "detect_skipped": detect_skipped,
        "projects": {},
    }
    for slug, (meta_entry, diff) in projects_diff.items():
        capabilities_out = {}
        drifts: list[str] = []
        for cap in CAPABILITY_ORDER:
            row = diff[cap]
            cap_payload = {
                "declared": row["declared"],
                "detected": None if detect_skipped else row["detected"],
                "drift": row["drift"],
            }
            if row["drift_reason"]:
                cap_payload["drift_reason"] = row["drift_reason"]
            capabilities_out[cap] = cap_payload
            if row["drift"]:
                drifts.append(cap)
        out["projects"][slug] = {
            "source": meta_entry.get("source"),
            "created_at": meta_entry.get("created_at"),
            "capabilities": capabilities_out,
            "drifts": drifts,
        }
    return out
