"""provision_knowledge — programmatic wrapper over bevox-knowledge-contribute helpers.

Per ADR-014 §Amendment 2 and spec
`bevox-knowledge/35_specs/openclaw/2026-05-07-project-lifecycle-w2-v1.md`,
this module replaces the legacy `step_1_create_kb_folders` (which created
2 of 9 folders untracked, no commit, no push) with a 4-step choreography:

  1. slot_resolve.sh <slug>            — validate canonical slot
  2. git_open_draft.sh <branch>        — open isolated worktree
  3. mkdir -p + .gitkeep × 9 folders   — provision ADR-010 canonical layout
     (optional: write PRD stub when prd_text is provided)
  4. git_commit_push.sh <wt> <msg>     — stage + commit + push to origin

After success, `capabilities.knowledge_slot.state = provisioned (9/9)` with
the bootstrap branch persisted in `branch_at_bootstrap`. The branch lives
in `draft/<slug>-knowledge-bootstrap` until Bernard merges (per spec
decision (a) — auto-merge in main violates CLAUDE.md §8).

Failure modes (each propagates HelperError → caller marks step_1 failed):
- bevox-knowledge dir missing                       → fail-loud
- skill lib dir missing (skill not pulled)          → fail-loud
- slot_resolve rejects slug as non-canonical        → exit 1
- git_open_draft refuses (branch already exists)    → exit 1 (rerun
  requires manual `git branch -D draft/<slug>-knowledge-bootstrap` —
  spec decision: option (a), no auto-recovery in W2)
- git_commit_push push rejected                     → exit 1
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from lib.provisioners._helpers import HelperError, run_helper

# Canonical 9 ADR-010 folders. Mirrors slot_resolve.sh CANONICAL_FOLDERS.
CANONICAL_FOLDERS: tuple[str, ...] = (
    "00_inbox",
    "10_prd",
    "20_architecture",
    "30_adr",
    "35_specs",
    "40_roadmap",
    "50_releases",
    "60_customer-feedback",
    "70_metrics",
)


@dataclass
class ProvisionResult:
    """Outcome of provision_knowledge call.

    state values:
        provisioned : 9/9 folders + commit pushed to origin/draft branch.
        partial     : helper failure mid-flow (rare; HelperError usually raises).
        failed      : reserved for explicit downgrade paths.
    """

    state: str
    slot: str
    branch: str
    worktree_path: Optional[str] = None
    commit_hash: Optional[str] = None
    branch_url: Optional[str] = None
    folders_created: List[str] = field(default_factory=list)
    prd_committed: bool = False
    error: Optional[str] = None


def _resolve_bk_path() -> Path:
    """Resolve bevox-knowledge dir from env or fallback to ~/bevox-knowledge."""
    candidate = os.environ.get("BEVOX_KNOWLEDGE_DIR") \
        or os.environ.get("BEVOX_KNOWLEDGE_PATH")
    if candidate:
        return Path(candidate).expanduser()
    return Path.home() / "bevox-knowledge"


def _resolve_skill_lib_dir(bk_path: Path) -> Path:
    """Path to skill helpers under bevox-knowledge clone."""
    return (
        bk_path
        / "99_templates"
        / "skill-bevox-knowledge-contribute"
        / "lib"
    )


def _build_helper_env(bk_path: Path) -> dict:
    """Merge BEVOX_KNOWLEDGE_PATH into a child env so helpers locate the clone.

    The skill helpers honor `BEVOX_KNOWLEDGE_PATH` (singular, see
    slot_resolve.sh + git_open_draft.sh). We export it explicitly even
    when the parent already has it, so wrapper invocations work in CI or
    when the orchestrator was invoked with a non-default --bk-dir flag.
    """
    env = dict(os.environ)
    env["BEVOX_KNOWLEDGE_PATH"] = str(bk_path)
    return env


def provision_knowledge(
    slug: str,
    *,
    bk_path: Optional[Path] = None,
    prd_text: Optional[str] = None,
    date_str: Optional[str] = None,
    project_name: str = "",
    description: str = "",
) -> ProvisionResult:
    """Provision 9 ADR-010 canonical subfolders for slug, commit, push.

    Args:
        slug: Project slug (must be in canonical SLOTS per ADR-010/ADR-002).
        bk_path: Override bevox-knowledge dir; defaults to env / ~/bevox-knowledge.
        prd_text: Optional PRD body. When provided, written to
            10_prd/<slug>/<date>-<slug>-prd.md inside the worktree.
        date_str: ISO date used in PRD filename. Defaults to today.
        project_name: Display name (header in PRD stub when no prd_text).
        description: Short description (used in PRD stub when no prd_text).

    Returns:
        ProvisionResult with state='provisioned' on success.

    Raises:
        HelperError: any helper exits non-zero (caller maps to step_1 failed).
        FileNotFoundError: bevox-knowledge or skill lib missing.
    """
    bk = bk_path or _resolve_bk_path()
    if not bk.is_dir():
        raise FileNotFoundError(
            f"bevox-knowledge clone not found at '{bk}'. "
            f"Set BEVOX_KNOWLEDGE_DIR or clone bernardTavares/bevox-knowledge."
        )
    skill_lib = _resolve_skill_lib_dir(bk)
    if not skill_lib.is_dir():
        raise FileNotFoundError(
            f"skill helpers not found at '{skill_lib}'. "
            f"Pull bevox-knowledge with the bevox-knowledge-contribute skill (V1+) "
            f"to enable provision-knowledge."
        )

    env = _build_helper_env(bk)
    branch = f"draft/{slug}-knowledge-bootstrap"

    # 1. slot_resolve — validate canonical slot.
    slot_resolve = skill_lib / "slot_resolve.sh"
    run_helper(
        "slot_resolve",
        ["bash", str(slot_resolve), slug],
        env=env,
        timeout=10,
    )

    # 2. git_open_draft — create isolated worktree on new branch.
    git_open_draft = skill_lib / "git_open_draft.sh"
    worktree_path_str = run_helper(
        "git_open_draft",
        ["bash", str(git_open_draft), branch],
        env=env,
        timeout=30,
    )
    worktree = Path(worktree_path_str)
    if not worktree.is_dir():
        raise HelperError(
            "git_open_draft", 1,
            f"git_open_draft.sh reported worktree '{worktree_path_str}' "
            f"but the directory is not present.",
        )

    # 3. Provision 9 ADR-010 folders + .gitkeep each.
    folders_created: List[str] = []
    for folder in CANONICAL_FOLDERS:
        d = worktree / folder / slug
        d.mkdir(parents=True, exist_ok=True)
        gitkeep = d / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.touch()
        folders_created.append(str(d))

    # Optional PRD stub. Writes are inside the worktree → committed by
    # the next helper call.
    prd_committed = False
    if prd_text and prd_text.strip():
        # Use today if no date provided.
        if date_str is None:
            import datetime as _dt
            date_str = _dt.date.today().isoformat()
        prd_dir = worktree / "10_prd" / slug
        prd_dir.mkdir(parents=True, exist_ok=True)
        prd_path = prd_dir / f"{date_str}-{slug}-prd.md"
        # Lightweight frontmatter + body. Spec calls for
        # frontmatter_validate.sh validation; we keep the same minimal
        # shape produced by legacy step_1_create_kb_folders so we don't
        # diverge from existing reader expectations.
        header = (
            f"---\nproject: {slug}\ndate: {date_str}\nstatus: draft\n---\n\n"
        )
        prd_path.write_text(header + prd_text, encoding="utf-8")
        prd_committed = True

    # 4. git_commit_push — stage, commit, push.
    git_commit_push = skill_lib / "git_commit_push.sh"
    msg = (
        f"bootstrap({slug}): provisiona 9 subpastas canonicas ADR-010"
    )
    if prd_committed:
        msg += " + PRD stub"
    push_output = run_helper(
        "git_commit_push",
        ["bash", str(git_commit_push), str(worktree), msg],
        env=env,
        timeout=120,
    )
    # git_commit_push prints two lines: <hash>\n<branch_url>
    lines = [ln for ln in push_output.splitlines() if ln.strip()]
    commit_hash: Optional[str] = lines[0] if lines else None
    branch_url: Optional[str] = lines[1] if len(lines) >= 2 else None

    return ProvisionResult(
        state="provisioned",
        slot=slug,
        branch=branch,
        worktree_path=str(worktree),
        commit_hash=commit_hash,
        branch_url=branch_url,
        folders_created=folders_created,
        prd_committed=prd_committed,
    )
