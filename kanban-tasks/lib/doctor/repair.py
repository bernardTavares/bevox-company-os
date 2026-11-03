"""Doctor repair phase — map drift → provisioner action.

Reuses W4 provisioner dispatch (cmd_project_adopt._run_provisioner pattern).
Idempotent: rerun with no remaining drift is no-op.

Spec: W5 §Repair (--fix phase).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from lib import projects_meta as _pm
from lib.capability_detect import DetectPaths
from lib.cli.cmd_project_adopt import _run_provisioner
from lib.doctor.scanner import DriftRow


@dataclass
class RepairOutcome:
    """One drift row repair attempt."""
    slug: str
    capability: str
    action: str  # "repaired" | "skipped" | "ambiguous" | "unsupported" | "user_declined"
    reason: str
    new_state: Optional[str] = None
    error: Optional[str] = None


# Drifts where repair direction is unambiguous and idempotent.
# We keep this conservative — anything outside is "ambiguous" in --auto-confirm.
_AUTO_REPAIRABLE = {
    # detected → declared transition rules:
    # "partial" detected: rerun provisioner (idempotent).
    "partial",
}


def _is_auto_repairable(drift: DriftRow) -> bool:
    """Return True iff drift can be auto-repaired without user disambiguation.

    Conservative policy:
    - declared=provisioned, detected=partial → re-run provisioner. SAFE.
    - declared=provisioned, detected=absent → re-run provisioner. SAFE.
    - declared=absent, detected=provisioned → meta lag (need to flip declared).
      We treat this as auto-repairable: write set_capability_state(provisioned).
    - drifted state → ambiguous.
    """
    det = drift.detected_state
    decl = drift.declared_state
    if det == "drifted":
        return False
    if decl == "provisioned" and det in ("partial", "absent"):
        return True
    if decl == "absent" and det == "provisioned":
        return True
    if decl == "partial" and det in ("provisioned",):
        return True
    return False


def _make_meta_entry_for_slug(meta_path: Path, slug: str) -> Dict[str, Any]:
    meta = _pm.read_meta(meta_path)
    return (meta.get("projects") or {}).get(slug) or {}


def repair_drift(
    drift: DriftRow,
    *,
    paths: DetectPaths,
    meta_path: Path,
    opts: Dict[str, Any],
    auto_confirm: bool,
    prompt_fn: Optional[Callable[[str], bool]] = None,
) -> RepairOutcome:
    """Repair one drift row. Idempotent.

    `prompt_fn(message) -> bool` controls user confirmation when not in
    auto_confirm mode.
    """
    cap = drift.capability
    slug = drift.slug

    # Inverse drift: declared=absent, detected=provisioned → just sync meta.
    if drift.declared_state == "absent" and drift.detected_state == "provisioned":
        if not auto_confirm:
            if prompt_fn is None or not prompt_fn(
                f"register existing {cap} for {slug} in meta? (Y/n) "
            ):
                return RepairOutcome(
                    slug=slug, capability=cap,
                    action="user_declined",
                    reason="inverse drift not synced",
                )
        try:
            fields = (drift.detected or {}).copy()
            fields.pop("state", None)
            fields.pop("drift_reason", None)
            _pm.set_capability_state(meta_path, slug, cap, "provisioned", **fields)
            return RepairOutcome(
                slug=slug, capability=cap,
                action="repaired",
                reason="inverse drift: meta updated to provisioned",
                new_state="provisioned",
            )
        except _pm.MetaError as e:
            return RepairOutcome(
                slug=slug, capability=cap,
                action="skipped",
                reason=f"meta update failed: {e}",
                error=str(e),
            )

    # Ambiguous in auto-confirm.
    if auto_confirm and not _is_auto_repairable(drift):
        return RepairOutcome(
            slug=slug, capability=cap,
            action="ambiguous",
            reason=(
                f"declared={drift.declared_state} detected={drift.detected_state} "
                "skipped in --auto-confirm"
            ),
        )

    # Interactive: prompt unless auto_confirm.
    if not auto_confirm:
        message = (
            f"fix drift in {slug}.{cap}? "
            f"(declared={drift.declared_state}, detected={drift.detected_state}) (Y/n) "
        )
        if prompt_fn is None or not prompt_fn(message):
            return RepairOutcome(
                slug=slug, capability=cap,
                action="user_declined",
                reason="user declined repair",
            )

    # Forward repair: invoke provisioner.
    meta_entry = _make_meta_entry_for_slug(meta_path, slug)
    if not meta_entry:
        return RepairOutcome(
            slug=slug, capability=cap,
            action="skipped",
            reason="meta entry vanished mid-repair",
        )

    try:
        prov_result = _run_provisioner(
            cap,
            slug=slug, paths=paths, meta_path=meta_path,
            meta_entry=meta_entry, opts=opts,
        )
    except Exception as e:  # noqa: BLE001 — provisioner may raise anything
        return RepairOutcome(
            slug=slug, capability=cap,
            action="skipped",
            reason=f"provisioner raised: {e}",
            error=str(e),
        )

    new_state = prov_result.get("state", "partial")
    fields = prov_result.get("fields") or {}
    err = prov_result.get("error")

    # Some provisioners (mission_control stub) return state=absent — treat as
    # unsupported. State='unsupported' (future provisioner contract per W5
    # §Contrato de provisioner repair_partial) treated same.
    if new_state == "unsupported":
        return RepairOutcome(
            slug=slug, capability=cap,
            action="unsupported",
            reason=prov_result.get("reason") or "provisioner reports unsupported",
        )

    persist_state = new_state if new_state in _pm.CAPABILITY_STATES else "partial"
    try:
        _pm.set_capability_state(meta_path, slug, cap, persist_state, **fields)
    except _pm.MetaError as e:
        return RepairOutcome(
            slug=slug, capability=cap,
            action="skipped",
            reason=f"meta persist failed: {e}",
            new_state=persist_state,
            error=str(e),
        )

    return RepairOutcome(
        slug=slug, capability=cap,
        action="repaired",
        reason="provisioner re-run",
        new_state=persist_state,
        error=err,
    )
