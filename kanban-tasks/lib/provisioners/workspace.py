"""provision_workspace — clone workspace-template/ → workspace-<slug>/.

Wraps `step_3_create_workspace` (from project_factory) so adopt and create share
the same idempotent populator. Idempotent: re-run when workspace dir already
exists is a no-op (returns already_existed=True).

Per W4 spec
`bevox-knowledge/35_specs/openclaw/2026-05-07-project-lifecycle-w4-v1.md`.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class WorkspaceResult:
    """Outcome of provision_workspace.

    state values:
        provisioned : workspace-<slug>/ exists with IDENTITY.md.
        partial     : dir exists but IDENTITY.md missing (drift).
        absent      : provisioner ran in dry-run / pre-conditions failed.
    """

    state: str
    path: Optional[str] = None
    runtime_dir: Optional[str] = None
    files_written: List[str] = field(default_factory=list)
    already_existed: bool = False
    error: Optional[str] = None


def provision_workspace(
    slug: str,
    *,
    openclaw_dir: Path,
    name: str = "",
    domain: str = "",
    date_str: Optional[str] = None,
) -> WorkspaceResult:
    """Provision openclaw workspace dir from template.

    Args:
        slug: project id (kebab-case).
        openclaw_dir: ~/.openclaw root.
        name: display name (template substitution).
        domain: project domain (template substitution).
        date_str: ISO date for {{DATE}}; defaults to today.

    Returns:
        WorkspaceResult with state set per detect contract.
    """
    from lib.project_factory import step_3_create_workspace, StepFailure

    if date_str is None:
        date_str = _dt.date.today().isoformat()

    try:
        details = step_3_create_workspace(
            slug=slug,
            name=name or slug,
            openclaw_dir=openclaw_dir,
            templates_dir=openclaw_dir / "kanban-tasks" / "templates",
            date_str=date_str,
            domain=domain,
        )
    except StepFailure as e:
        return WorkspaceResult(
            state="absent",
            error=f"{e.code}: {e}",
        )

    workspace_dir = openclaw_dir / f"workspace-{slug}"
    identity = workspace_dir / "IDENTITY.md"
    if identity.is_file():
        cap_state = "provisioned"
    else:
        cap_state = "partial"

    return WorkspaceResult(
        state=cap_state,
        path=str(workspace_dir),
        runtime_dir=details.get("runtime_dir"),
        files_written=details.get("files_written") or [],
        already_existed=details.get("already_existed", False),
    )
