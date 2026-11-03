"""provision_code_repo — adopt-time helper for code_repo capability.

Per ADR-013 §state-machine, code_repo provisioning in greenfield is handled
by `cmd_project_create` (which calls `step_5_code_init` + `step_6_github_push`).
In adopt mode the typical case is "code repo already exists locally and on
GitHub" — provisioner is a no-op recorder.

When code is partial (local only, no GitHub), this provisioner is intentionally
minimal: it does NOT push to GitHub automatically (to avoid inadvertent public
exposure or org confusion). Caller must run greenfield create or use a
follow-up `gh repo create` flow. We expose state with the actionable error.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class CodeRepoResult:
    state: str  # provisioned | partial | absent
    path: Optional[str] = None
    github: Optional[str] = None
    error: Optional[str] = None


def provision_code_repo(
    slug: str,
    *,
    code_dir: Path,
    org: str = "bernardTavares",
) -> CodeRepoResult:
    """Detect existing code_repo and record state. No mutation in adopt mode.

    Args:
        slug: project id (= repo name on GitHub).
        code_dir: parent dir holding local clones (e.g. ~/code).
        org: GitHub org slug.

    Returns:
        CodeRepoResult mirroring detect_code_repo (without remote check).
    """
    local_path = code_dir / slug
    has_local = local_path.is_dir()
    github_url = f"https://github.com/{org}/{slug}"

    if has_local:
        return CodeRepoResult(
            state="provisioned",
            path=str(local_path),
            github=github_url,
        )
    return CodeRepoResult(
        state="absent",
        github=github_url,
        error=(
            f"code repo not found at {local_path}; adopt does not auto-create. "
            f"Use `openclaw project create` for greenfield."
        ),
    )
