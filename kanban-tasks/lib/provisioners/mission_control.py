"""provision_mission_control — honest no-op provisioner.

MC reads `~/.openclaw/projects-meta.json` directly (see
`mission-control/src/lib/projects/meta.ts`); visibility is implicit
once `_ensure_meta_entry` has written the entry — which adopt does
before this provisioner runs.

There is no sync API to call. Returning `state="absent"` keeps the
matrix honest (a real `/api/projects/<slug>` probe with auth would be
needed for `provisioned`), but `error=None` so adopt does not surface
this as a failure on the result table.

When MC moves to push-based registration, replace with a real client.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class MCResult:
    state: str = "absent"
    note: str = (
        "MC integration is implicit/file-based; project is visible to MC "
        "as soon as its entry exists in ~/.openclaw/projects-meta.json. "
        "No-op until a real sync API is wired in."
    )
    error: Optional[str] = None


def provision_mission_control(slug: str, **opts) -> MCResult:
    """No-op success. Returns absent without error."""
    return MCResult()
