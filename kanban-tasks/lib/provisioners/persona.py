"""provision_persona — wraps step_4_persona_llm for adopt path.

Per W4 spec, persona is provisioned only when PRD text is provided. Without
PRD, returns state=absent (caller may regenerate later via
`openclaw project regenerate-persona`).

Idempotent: if IDENTITY.md already has `persona_status: generated`, the
underlying step_4 short-circuits and returns already_generated.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class PersonaResult:
    state: str  # provisioned | partial | absent
    persona_status: Optional[str] = None
    workspace_path: Optional[str] = None
    error: Optional[str] = None


def provision_persona(
    slug: str,
    *,
    openclaw_dir: Path,
    name: str = "",
    domain: str = "",
    date_str: Optional[str] = None,
    prd_text: Optional[str] = None,
) -> PersonaResult:
    """Run persona LLM for slug if PRD provided.

    Args:
        slug: project id.
        openclaw_dir: ~/.openclaw root.
        name: display name.
        domain: project domain.
        date_str: ISO date.
        prd_text: full PRD text. If None/empty → state=absent (no-op).

    Returns:
        PersonaResult with state/persona_status fields.
    """
    from lib.project_factory import step_4_persona_llm

    workspace_dir = openclaw_dir / f"workspace-{slug}"
    if not workspace_dir.is_dir():
        return PersonaResult(
            state="absent",
            error=f"workspace-{slug} dir missing",
        )

    if not prd_text or not prd_text.strip():
        # No PRD → cannot generate. Stay absent (idempotent: re-run with PRD
        # later promotes to provisioned).
        return PersonaResult(
            state="absent",
            persona_status="no_prd",
            workspace_path=str(workspace_dir),
        )

    if date_str is None:
        date_str = _dt.date.today().isoformat()

    result = step_4_persona_llm(
        slug=slug,
        name=name or slug,
        domain=domain,
        date_str=date_str,
        prd_text=prd_text,
        workspace_dir=workspace_dir,
    )
    status = result.get("persona_status")
    if status in ("generated", "already_generated"):
        cap_state = "provisioned"
    elif status == "pending":
        cap_state = "partial"
    elif status == "skipped_flag":
        cap_state = "absent"
    else:
        cap_state = "partial"

    return PersonaResult(
        state=cap_state,
        persona_status=status,
        workspace_path=str(workspace_dir),
        error=result.get("error"),
    )
