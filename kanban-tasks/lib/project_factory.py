"""Project factory orchestrator — creates new projects across 6 filesystems.

Spec: bevox-knowledge/35_specs/company-os/2026-04-26-mc-projects-factory.md §3.1
"""
import fcntl
import json
import os
import re
import shutil
import string
import subprocess
import unicodedata
from pathlib import Path
from typing import Any, Dict

import yaml

from lib import task, sprint, projects_meta, persona_extractor
from lib.provisioners.knowledge import (
    ProvisionResult,
    provision_knowledge,
)

# Reserved IDs (folders in bevox-knowledge structure that aren't projects)
RESERVED_IDS = frozenset({"_shared", "_retired", "templates"})

# kebab-case validation regex: start with letter, contain only a-z0-9-, end with letter/digit
_ID_RE = re.compile(r"^[a-z][a-z0-9-]*[a-z0-9]$")


def slugify(name: str) -> str:
    """Convert display name to kebab-case ID.

    Steps:
    1. lowercase + NFD normalize + strip diacritics
    2. replace non-[a-z0-9-] by hyphen
    3. collapse repeated hyphens
    4. strip leading/trailing hyphens
    5. truncate to 40 chars (trim trailing hyphen if cut creates one)
    """
    # Normalize + strip diacritics
    nfd = unicodedata.normalize("NFD", name.lower())
    ascii_str = nfd.encode("ascii", "ignore").decode("ascii")
    # Replace non-allowed chars with hyphen
    slug = re.sub(r"[^a-z0-9-]+", "-", ascii_str)
    # Collapse repeated hyphens
    slug = re.sub(r"-+", "-", slug)
    # Strip leading/trailing hyphens
    slug = slug.strip("-")
    # Truncate to 40 chars + clean trailing hyphen
    if len(slug) > 40:
        slug = slug[:40].rstrip("-")
    return slug


def is_valid_id(slug: str) -> bool:
    """Validate ID against schema rules.

    Returns True if:
    - matches kebab-case regex (^[a-z][a-z0-9-]*[a-z0-9]$)
    - length 2-40
    - not in RESERVED_IDS
    """
    if not slug or len(slug) < 2 or len(slug) > 40:
        return False
    if slug in RESERVED_IDS:
        return False
    return bool(_ID_RE.match(slug))


class PreflightFailure(Exception):
    """Raised when a pre-flight check fails. Code attribute identifies which check."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


class RemovePreflightFailure(Exception):
    """Code: 'cannot_delete_canonical' | 'project_not_found' | 'cannot_delete_non_user_created'."""
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


def check_id_collision(slug: str, projects_yml: Path, meta_json: Path) -> None:
    """Raise PreflightFailure if slug exists in either projects.yml or projects-meta.json."""
    if projects_yml.exists():
        data = yaml.safe_load(projects_yml.read_text()) or {}
        if slug in (data.get("projects") or []):
            raise PreflightFailure(
                "collision", f"id '{slug}' já existe em projects.yml"
            )
    if meta_json.exists():
        meta = json.loads(meta_json.read_text())
        if slug in (meta.get("projects") or {}):
            raise PreflightFailure(
                "collision", f"id '{slug}' já existe em projects-meta.json"
            )


def check_filesystems_writable(
    kb_dir: Path, openclaw_dir: Path, code_dir: Path
) -> None:
    for label, p in [
        ("bevox-knowledge", kb_dir),
        ("openclaw", openclaw_dir),
        ("code", code_dir),
    ]:
        if not p.exists():
            raise PreflightFailure(
                f"{label}_missing",
                f"diretório {label} não existe: {p}",
            )
        if not os.access(p, os.W_OK):
            raise PreflightFailure(
                f"{label}_readonly",
                f"diretório {label} não é writable: {p}",
            )


def check_gh_auth() -> None:
    result = subprocess.run(
        ["gh", "auth", "status"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        raise PreflightFailure(
            "gh_auth_required",
            "gh CLI não autenticado — rode 'gh auth login' primeiro",
        )


def check_github_repo_free(org: str, repo: str) -> None:
    result = subprocess.run(
        ["gh", "repo", "view", f"{org}/{repo}"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode == 0:
        raise PreflightFailure(
            "github_collision",
            f"GitHub repo {org}/{repo} já existe",
        )


def check_kb_clean_or_only_stubs(kb_dir: Path, slug: str) -> None:
    result = subprocess.run(
        ["git", "-C", str(kb_dir), "status", "--porcelain"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        raise PreflightFailure("kb_status_error", f"git status falhou: {result.stderr}")
    allowed_prefixes = (
        f"10_prd/{slug}/",
        f"40_roadmap/{slug}/",
    )
    for line in result.stdout.strip().splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if not any(path.startswith(p) for p in allowed_prefixes):
            raise PreflightFailure(
                "kb_dirty",
                f"bevox-knowledge tem mudanças não relacionadas: {path}",
            )


def check_claude_cli(prd_provided: bool) -> None:
    """Raise PreflightFailure if PRD provided but `claude` CLI missing/unauthed.

    Skipped when no PRD (persona LLM step will be no-op via step_4 fallback).
    Also skipped if OPENCLAW_PERSONA_LLM=0.
    """
    if not prd_provided:
        return
    if os.environ.get("OPENCLAW_PERSONA_LLM", "1") == "0":
        return
    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True, text=True, timeout=10,
        )
    except FileNotFoundError:
        raise PreflightFailure(
            "claude_cli_missing",
            "`claude` CLI não encontrado no PATH. "
            "Instale e autentique (claude.ai subscription) antes de criar projeto com PRD, "
            "ou rode com OPENCLAW_PERSONA_LLM=0 pra criar com stubs.",
        )
    except subprocess.TimeoutExpired:
        raise PreflightFailure(
            "claude_cli_timeout",
            "`claude --version` excedeu 10s — possível auth pendente ou ambiente travado.",
        )
    if result.returncode != 0:
        raise PreflightFailure(
            "claude_cli_unhealthy",
            f"`claude --version` retornou {result.returncode}: {result.stderr.strip()}",
        )


def run_preflight(
    slug: str,
    org: str,
    kb_dir: Path,
    openclaw_dir: Path,
    code_dir: Path,
    projects_yml: Path,
    meta_json: Path,
    prd_provided: bool = False,
) -> None:
    if not is_valid_id(slug):
        raise PreflightFailure("invalid_id", f"id '{slug}' inválido")
    check_id_collision(slug, projects_yml, meta_json)
    check_filesystems_writable(kb_dir, openclaw_dir, code_dir)
    check_gh_auth()
    check_github_repo_free(org, slug)
    check_kb_clean_or_only_stubs(kb_dir, slug)
    check_claude_cli(prd_provided)


def run_remove_preflight(slug: str, meta_path: Path) -> None:
    """Validates project exists in meta with source=user_created.

    Canonical projects rejected — must be removed via ADR + canonical.ts edit.
    """
    meta = projects_meta.read_meta(meta_path)
    entry = meta.get("projects", {}).get(slug)
    if not entry:
        raise RemovePreflightFailure(
            "project_not_found",
            f"'{slug}' not found in projects-meta.json",
        )
    source = entry.get("source")
    if source == "canonical":
        raise RemovePreflightFailure(
            "cannot_delete_canonical",
            f"'{slug}' is canonical (ADR-002); deletar requer ADR update + canonical.ts edit",
        )
    if source != "user_created":
        raise RemovePreflightFailure(
            "cannot_delete_non_user_created",
            f"'{slug}' has source='{source}' — only user_created can be deleted",
        )


def render_template(tmpl_path: Path, **kwargs) -> str:
    """Read template file and substitute $name placeholders (string.Template — only $X special)."""
    return string.Template(tmpl_path.read_text()).safe_substitute(**kwargs)


def step_1_create_kb_folders(
    slug: str,
    name: str,
    description: str,
    kb_dir: Path,
    templates_dir: Path,
    date_str: str,
    prd_text: str = "",
) -> list[str]:
    """**DEPRECATED (W2)** — legacy 2/9 folder layout, untracked.

    Replaced by `provisioners.knowledge.provision_knowledge` per
    ADR-014 §Amendment 2 + spec
    `bevox-knowledge/35_specs/openclaw/2026-05-07-project-lifecycle-w2-v1.md`.

    The new step (`step_1_provision_knowledge`) uses the
    `bevox-knowledge-contribute` skill V1 helpers to provision **all 9**
    canonical ADR-010 subfolders for the slug, in an isolated draft
    worktree, with commit + push to origin/draft branch.

    This legacy function remains for tests / direct callers that pre-date
    W2; it does NOT commit to git and stops at 2 folders. Removal slated
    for W4 (`adopt`) which will retroactively upgrade existing projects.

    Idempotent: skips creation if files already exist.

    Returns list of file paths created/updated.
    """
    prd_tmpl = templates_dir / "prd-stub.md.tmpl"
    rm_tmpl = templates_dir / "roadmap-stub.md.tmpl"

    prd_dir = kb_dir / "10_prd" / slug
    rm_dir = kb_dir / "40_roadmap" / slug
    prd_dir.mkdir(parents=True, exist_ok=True)
    rm_dir.mkdir(parents=True, exist_ok=True)

    prd_path = prd_dir / f"{date_str}-{slug}-prd.md"
    rm_path = rm_dir / f"{date_str}-{slug}-roadmap.md"

    if not prd_path.exists():
        if prd_text.strip():
            # Use real PRD content; prepend lightweight frontmatter
            prd_path.write_text(
                f"---\nproject: {slug}\ndate: {date_str}\nstatus: draft\n---\n\n"
                + prd_text
            )
        else:
            prd_path.write_text(render_template(
                prd_tmpl, name=name, description=description, date=date_str
            ))
    if not rm_path.exists():
        rm_path.write_text(render_template(
            rm_tmpl, name=name, date=date_str
        ))

    return [str(prd_path), str(rm_path)]


def step_1_provision_knowledge(
    slug: str,
    *,
    bk_dir: Path,
    date_str: str,
    project_name: str = "",
    description: str = "",
    prd_text: str = "",
) -> dict:
    """W2 step 1 wrapper around `provisioners.knowledge.provision_knowledge`.

    Calls the bevox-knowledge-contribute skill helpers (slot_resolve,
    git_open_draft, git_commit_push) to provision the 9 canonical
    ADR-010 subfolders for `slug` in an isolated draft worktree, then
    pushes the bootstrap branch.

    Returns a JSONL-serializable details dict consumed by
    `_apply_capability_state_after_step` to populate
    `capabilities.knowledge_slot` with state=provisioned + branch +
    commit metadata.

    Raises:
        HelperError, FileNotFoundError, StepFailure (re-wrapped).
    """
    try:
        result: ProvisionResult = provision_knowledge(
            slug,
            bk_path=bk_dir,
            prd_text=prd_text or None,
            date_str=date_str,
            project_name=project_name,
            description=description,
        )
    except FileNotFoundError as e:
        raise StepFailure(1, "knowledge_path_missing", str(e))
    return {
        "state": result.state,
        "slot": result.slot,
        "branch": result.branch,
        "worktree_path": result.worktree_path,
        "commit_hash": result.commit_hash,
        "branch_url": result.branch_url,
        "folders_created": result.folders_created,
        "prd_committed": result.prd_committed,
    }


def _substitute_markers(
    text: str, *, slug: str, name: str, domain: str, date_str: str
) -> str:
    """Replace {{PROJECT_NAME}}, {{SLUG}}, {{DOMAIN}}, {{DATE}} in text."""
    return (
        text.replace("{{PROJECT_NAME}}", name)
        .replace("{{SLUG}}", slug)
        .replace("{{DOMAIN}}", domain)
        .replace("{{DATE}}", date_str)
    )


def step_3_create_workspace(
    slug: str,
    name: str,
    openclaw_dir: Path,
    templates_dir: Path,  # kept for signature compat; unused now
    date_str: str,
    domain: str = "",
) -> dict:
    """Clone ~/.openclaw/workspace-template/ → ~/.openclaw/workspace-<slug>/.

    Substitutes {{PROJECT_NAME}}, {{SLUG}}, {{DOMAIN}}, {{DATE}} in file
    contents AND filenames (e.g., memory/projects/{{SLUG}}.md → memory/projects/<slug>.md).

    Idempotent: returns {"already_existed": True} if workspace-<slug>/ exists.

    Raises StepFailure(code="template_missing") if workspace-template/ absent.
    """
    template_dir = openclaw_dir / "workspace-template"
    if not template_dir.is_dir():
        raise StepFailure(
            3, "template_missing",
            f"workspace-template not found at {template_dir}",
        )

    runtime_dir = openclaw_dir / slug
    workspace_dir = openclaw_dir / f"workspace-{slug}"

    # Runtime dirs (always create)
    for sub in ("clarifications", "notifications", "scripts"):
        (runtime_dir / sub).mkdir(parents=True, exist_ok=True)

    if workspace_dir.exists():
        return {
            "runtime_dir": str(runtime_dir),
            "workspace_dir": str(workspace_dir),
            "files_written": [],
            "already_existed": True,
        }

    # Clone tree, substituting markers in both file CONTENT and PATH
    files_written = []
    for src in template_dir.rglob("*"):
        rel = src.relative_to(template_dir)
        # Substitute path
        rel_str = _substitute_markers(
            str(rel), slug=slug, name=name, domain=domain, date_str=date_str,
        )
        dst = workspace_dir / rel_str

        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            continue

        dst.parent.mkdir(parents=True, exist_ok=True)
        # Substitute content (text files only — JSON memory/feedback/*.json
        # carry no markers but are valid UTF-8 anyway)
        try:
            content = src.read_text(encoding="utf-8")
            content = _substitute_markers(
                content, slug=slug, name=name, domain=domain, date_str=date_str,
            )
            dst.write_text(content, encoding="utf-8")
        except UnicodeDecodeError:
            # Binary file — copy bytes
            dst.write_bytes(src.read_bytes())
        files_written.append(str(dst))

    return {
        "runtime_dir": str(runtime_dir),
        "workspace_dir": str(workspace_dir),
        "files_written": files_written,
        "already_existed": False,
    }


def step_4_persona_llm(
    *,
    slug: str,
    name: str,
    domain: str,
    date_str: str,
    prd_text: str,
    workspace_dir: Path,
) -> dict:
    """Generate persona files via LLM (claude -p subprocess); fall back gracefully.

    Honors feature flag OPENCLAW_PERSONA_LLM (default '1'; set to '0' to no-op).
    Idempotent: skips if IDENTITY.md already has frontmatter persona_status: generated.
    Skips with pending marker if no PRD text provided.

    Returns dict with at least {"persona_status": str}. On failure also includes
    {"error": str}.
    """
    if os.environ.get("OPENCLAW_PERSONA_LLM", "1") == "0":
        return {"persona_status": "skipped_flag"}

    identity_path = workspace_dir / "IDENTITY.md"
    if identity_path.exists():
        text = identity_path.read_text(encoding="utf-8")
        if "persona_status: generated" in text:
            return {"persona_status": "already_generated"}

    if not prd_text or not prd_text.strip():
        return _write_pending_marker(
            workspace_dir, slug, error="no PRD text provided"
        )

    result = persona_extractor.extract_persona(
        slug=slug,
        project_display_name=name,
        domain=domain,
        date_str=date_str,
        prd_text=prd_text,
    )

    if result["status"] != "generated":
        return _write_pending_marker(
            workspace_dir, slug,
            error=result.get("error", result["status"]),
        )

    # Write the 3 files
    identity_path.write_text(result["identity"], encoding="utf-8")
    (workspace_dir / "SOUL.md").write_text(result["soul"], encoding="utf-8")
    project_md = workspace_dir / "memory" / "projects" / f"{slug}.md"
    project_md.parent.mkdir(parents=True, exist_ok=True)
    project_md.write_text(result["memory_projects"], encoding="utf-8")

    # Remove any stale PENDING marker file
    pending = workspace_dir / "PERSONA_PENDING.md"
    if pending.exists():
        pending.unlink()

    return {"persona_status": "generated"}


def _write_pending_marker(
    workspace_dir: Path, slug: str, error: str
) -> dict:
    """Write PERSONA_PENDING.md with recovery instructions; return pending status."""
    pending_md = workspace_dir / "PERSONA_PENDING.md"
    pending_md.write_text(
        f"""# Persona pending — {slug}

Persona LLM generation did not complete.

**Reason:** {error}

To regenerate, run:

```bash
openclaw project regenerate-persona {slug}
```

(Requires `claude` CLI authenticated via subscription and a PRD at
`bevox-knowledge/10_prd/{slug}/`.)
""",
        encoding="utf-8",
    )
    return {"persona_status": "pending", "error": error}


def step_2_kanban_bootstrap(slug: str, actor: str = "bernard") -> Dict[str, Any]:
    """Add slug to kanban-tasks projects.yml + state.json + bootstrap 1 current + 1 next sprint.

    Reusa task.add_project + sprint.bootstrap (idempotent helpers).
    Cria entry em projects.yml + 1 current + 1 next sprint em state.json.

    Returns dict com 'sprints_created' count.
    """
    add_result = task.add_project(slug, actor=actor)
    bootstrap_result = sprint.bootstrap(
        actor=actor, projects=[slug], dry_run=False
    )
    return {
        "project_add": add_result,
        "sprints_created": len(bootstrap_result.get("created", [])),
    }


def step_4_meta_insert(
    slug: str,
    name: str,
    description: str,
    github_url: str,
    meta_path: Path,
    date_iso: str,
) -> dict:
    """Insert project entry into projects-meta.json with source=user_created.

    Legacy direct-call entry point. New orchestrator uses
    `_register_skeleton_entry` upfront (which calls this then upgrades) and
    `step_5_meta_finalize` as the in-loop sentinel.

    .. deprecated:: W1
        Legacy direct-call entry point. Kept for backwards compat with
        callers that invoked step_4_meta_insert directly. New orchestrator
        (cmd_project_create) uses step_5_meta_finalize. Remove in W3 after
        all callers migrated.
    """
    entry = {
        "name": name,
        "description": description,
        "github_url": github_url,
        "bot_id": None,
        "bot_username": None,
        "bot_port": None,
        "created_at": date_iso,
        "source": "user_created",
    }
    projects_meta.insert_project(meta_path, slug, entry)
    return {"meta_path": str(meta_path), "entry": entry}


def _register_skeleton_entry(
    slug: str,
    name: str,
    description: str,
    github_url: str,
    meta_path: Path,
    date_iso: str,
    domain: str = "",
) -> dict:
    """Create projects-meta entry with capabilities skeleton (all absent)
    + capabilities_schema_version=1 + flat legacy fields preserved.

    Used by create_project orchestrator before running steps so each step
    can call set_capability_state on an existing entry. Idempotent: if the
    entry already exists, return existing without mutating.
    """
    data = projects_meta.read_meta(meta_path)
    projects = data.setdefault("projects", {})
    if slug in projects:
        return {"meta_path": str(meta_path), "entry": projects[slug],
                "already_existed": True}
    entry = {
        "name": name,
        "description": description,
        "domain": domain,
        "github_url": github_url,
        "bot_id": None,
        "bot_username": None,
        "bot_port": None,
        "created_at": date_iso,
        "source": "user_created",
        "capabilities_schema_version": projects_meta.CAPABILITY_SCHEMA_VERSION,
        "capabilities": projects_meta.empty_capability_set(),
    }
    projects[slug] = entry
    projects_meta.write_meta(meta_path, data)
    return {"meta_path": str(meta_path), "entry": entry,
            "already_existed": False}


def step_5_meta_finalize(
    slug: str,
    meta_path: Path,
) -> dict:
    """No-op sentinel used by create_project step array (replaces in-loop
    step_4_meta_insert). The skeleton entry was already written upfront by
    `_register_skeleton_entry`; this step exists to preserve the 7-step JSONL
    log format consumers may rely on.

    Falls back to a register call only if the entry is missing — defensive,
    not expected in normal flow.
    """
    data = projects_meta.read_meta(meta_path)
    if slug not in (data.get("projects") or {}):
        return {"finalized": False, "reason": "entry_missing",
                "meta_path": str(meta_path)}
    return {"finalized": True, "noop": True, "meta_path": str(meta_path)}


class StepFailure(Exception):
    """Raised when an orchestrator step fails."""
    def __init__(self, step: int, code: str, message: str):
        self.step = step
        self.code = code
        super().__init__(f"step {step} ({code}): {message}")


def step_5_code_init(
    slug: str,
    name: str,
    description: str,
    code_dir: Path,
    templates_dir: Path,
    date_str: str,
    actor: str = "bernard",
) -> dict:
    """Create ${BEVOX_CODE_DIR}/<slug>/ + git init + README + initial commit on main."""
    project_path = code_dir / slug
    if project_path.exists():
        raise StepFailure(5, "code_dir_exists",
                          f"directory already exists: {project_path}")

    project_path.mkdir(parents=True)

    # Render README
    tmpl = templates_dir / "code" / "README.md.tmpl"
    readme_content = render_template(
        tmpl, slug=slug, name=name, description=description, date=date_str
    )
    (project_path / "README.md").write_text(readme_content)

    # git init + initial commit on main
    cmds = [
        ["git", "init", "--initial-branch=main"],
        ["git", "add", "README.md"],
        ["git", "commit",
         "-m", f"feat: bootstrap {slug} project",
         "--author", f"{actor} <{actor}@bevox>"],
    ]
    for cmd in cmds:
        result = subprocess.run(
            cmd, cwd=str(project_path),
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            raise StepFailure(5, "git_init_failed",
                              f"{cmd[0]} {cmd[1]}: {result.stderr}")

    return {"repo_path": str(project_path), "branch": "main"}


def step_6_github_push(
    slug: str,
    org: str,
    repo_path: Path,
) -> dict:
    """Create private GitHub repo via gh CLI + push current main branch."""
    cmd = [
        "gh", "repo", "create", f"{org}/{slug}",
        "--private",
        "--source", str(repo_path),
        "--push",
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        raise StepFailure(
            6, "gh_create_failed",
            f"gh repo create failed: {result.stderr.strip()}",
        )
    return {
        "github_url": f"https://github.com/{org}/{slug}",
        "stdout": result.stdout.strip(),
    }


import datetime as dt
import time
from dataclasses import dataclass


@dataclass
class ProjectCreateConfig:
    kb_dir: Path
    openclaw_dir: Path
    code_dir: Path
    meta_path: Path
    log_path: Path
    templates_dir: Path
    org: str = "bernardTavares"
    # NEW Phase 2 fields
    prd_file: Path | None = None  # path to PRD provided by caller (CLI --prd)
    domain: str = ""              # project domain (passed to step_3 + step_4)


def _log_event(log_path: Path, entry: dict) -> None:
    """Append one JSON line to log file. Creates parent dir if missing."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")


def _apply_capability_state_after_step(
    *,
    slug: str,
    step_name: str,
    details: dict,
    meta_path: Path,
    workspace_dir: Path,
    code_dir: Path,
    github_url: str,
) -> None:
    """Update capabilities sub-object after a step succeeds.

    Called from create_project orchestrator. Best-effort; failure here does
    not break the create flow.

    Step → capability mapping per spec W1 §Mapping:
      knowledge_folders   → knowledge_slot   (partial: 2/9 folders ADR-010)
      kanban_bootstrap    → kanban_sprints   (provisioned)
      openclaw_workspace  → workspace        (provisioned)
      persona_llm         → persona          (depends on persona_status)
      meta_insert         → no-op (entry already registered)
      code_init           → code_repo        (partial — local only)
      github_push         → code_repo        (provisioned — full)
    """
    if step_name == "knowledge_folders":
        # W2: details now comes from step_1_provision_knowledge with the
        # full 9/9 layout pushed to a draft branch.
        d = details if isinstance(details, dict) else {}
        last_bootstrap_at = (
            dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        )
        kwargs: dict[str, Any] = {
            "slot": d.get("slot", slug),
            "folders_present": 9,
            "folders_total": 9,
            "last_bootstrap_at": last_bootstrap_at,
        }
        branch = d.get("branch")
        if branch:
            kwargs["branch_at_bootstrap"] = branch
        commit_hash = d.get("commit_hash")
        if commit_hash:
            kwargs["commit_hash_at_bootstrap"] = commit_hash
        branch_url = d.get("branch_url")
        if branch_url:
            kwargs["branch_url"] = branch_url
        projects_meta.set_capability_state(
            meta_path, slug, "knowledge_slot",
            "provisioned", **kwargs,
        )
        return
    if step_name == "kanban_bootstrap":
        sprints_created = (
            details.get("sprints_created") if isinstance(details, dict) else None
        )
        projects_meta.set_capability_state(
            meta_path, slug, "kanban_sprints",
            "provisioned", sprints_created=sprints_created,
        )
        return
    if step_name == "openclaw_workspace":
        projects_meta.set_capability_state(
            meta_path, slug, "workspace",
            "provisioned", path=str(workspace_dir),
        )
        return
    if step_name == "persona_llm":
        status = (
            details.get("persona_status") if isinstance(details, dict) else None
        )
        if status in ("generated", "already_generated"):
            cap_state = "provisioned"
        elif status == "pending":
            cap_state = "partial"
        elif status == "skipped_flag":
            cap_state = "absent"
        else:
            cap_state = "partial"
        projects_meta.set_capability_state(
            meta_path, slug, "persona",
            cap_state, persona_status=status,
        )
        return
    if step_name == "meta_insert":
        # No-op: skeleton entry was already registered before the loop.
        return
    if step_name == "code_init":
        projects_meta.set_capability_state(
            meta_path, slug, "code_repo",
            "partial", path=str(code_dir / slug), github=None,
        )
        return
    if step_name == "github_push":
        projects_meta.set_capability_state(
            meta_path, slug, "code_repo",
            "provisioned", path=str(code_dir / slug), github=github_url,
        )
        return


def create_project(
    name: str,
    slug: str,
    description: str,
    config: ProjectCreateConfig,
    actor: str = "bernard",
) -> dict:
    """Orchestrate 6-step project creation with pre-flight + JSONL logging."""
    date_str = dt.date.today().isoformat()
    date_iso = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    projects_yml = config.openclaw_dir / "kanban-tasks" / "projects.yml"

    # Pre-flight
    try:
        run_preflight(
            slug=slug,
            org=config.org,
            kb_dir=config.kb_dir,
            openclaw_dir=config.openclaw_dir,
            code_dir=config.code_dir,
            projects_yml=projects_yml,
            meta_json=config.meta_path,
            prd_provided=bool(config.prd_file),
        )
    except PreflightFailure as e:
        return {
            "success": False,
            "failed_at": 0,
            "steps_completed": 0,
            "error_code": e.code,
            "error_message": str(e),
        }

    # Read PRD text (used by step_1 to inline real content + step_4 for persona LLM)
    prd_text = ""
    if config.prd_file and config.prd_file.is_file():
        prd_text = config.prd_file.read_text(encoding="utf-8")

    # Register skeleton entry upfront so steps can update capability state
    # as they progress (vs. the legacy flow where meta entry was created
    # mid-loop at step 5).
    github_url = f"https://github.com/{config.org}/{slug}"
    _register_skeleton_entry(
        slug=slug, name=name, description=description,
        github_url=github_url, meta_path=config.meta_path,
        date_iso=date_iso, domain=config.domain,
    )

    # Define steps. step_5 stays named "meta_insert" in the JSONL log to
    # preserve format compat with consumers; the implementation became
    # finalize-or-noop since the skeleton already exists.
    workspace_dir = config.openclaw_dir / f"workspace-{slug}"
    steps = [
        (1, "knowledge_folders", lambda: step_1_provision_knowledge(
            slug,
            bk_dir=config.kb_dir,
            date_str=date_str,
            project_name=name,
            description=description,
            prd_text=prd_text,
        )),
        (2, "kanban_bootstrap", lambda: step_2_kanban_bootstrap(slug, actor)),
        (3, "openclaw_workspace", lambda: step_3_create_workspace(
            slug, name, config.openclaw_dir,
            config.templates_dir, date_str,
            domain=config.domain)),
        (4, "persona_llm", lambda: step_4_persona_llm(
            slug=slug, name=name, domain=config.domain,
            date_str=date_str, prd_text=prd_text,
            workspace_dir=workspace_dir)),
        (5, "meta_insert", lambda: step_5_meta_finalize(
            slug, config.meta_path)),
        (6, "code_init", lambda: step_5_code_init(
            slug, name, description, config.code_dir,
            config.templates_dir, date_str, actor)),
        (7, "github_push", lambda: step_6_github_push(
            slug, config.org, config.code_dir / slug)),
    ]

    completed = 0
    for step_num, step_name, step_fn in steps:
        start = time.time()
        try:
            details = step_fn()
            duration_ms = int((time.time() - start) * 1000)
            # Map step result to capability state on the meta entry.
            try:
                _apply_capability_state_after_step(
                    slug=slug, step_name=step_name, details=details,
                    meta_path=config.meta_path,
                    workspace_dir=workspace_dir,
                    code_dir=config.code_dir,
                    github_url=github_url,
                )
            except Exception:
                # Capability state tracking is best-effort — never break create.
                pass
            if isinstance(details, dict):
                serial_details = {k: v for k, v in details.items() if isinstance(v, (str, int, list))}
            else:
                serial_details = {"result": details if isinstance(details, (str, int, list)) else str(details)}
            _log_event(config.log_path, {
                "ts": dt.datetime.utcnow().isoformat() + "Z",
                "slug": slug,
                "step": step_num,
                "name": step_name,
                "status": "ok",
                "duration_ms": duration_ms,
                "details": serial_details,
            })
            completed = step_num
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            _log_event(config.log_path, {
                "ts": dt.datetime.utcnow().isoformat() + "Z",
                "slug": slug,
                "step": step_num,
                "name": step_name,
                "status": "failed",
                "duration_ms": duration_ms,
                "error": str(e),
            })
            # Skeleton rollback (W1 review fix #1): the orchestrator now writes
            # the projects-meta entry up-front (vs. legacy mid-loop at step 5),
            # which broke retry semantics — a failure in steps 1-4 used to
            # leave no entry, so `openclaw project create <slug>` could be
            # retried trivially. Without rollback, the second attempt is
            # rejected with error_code=collision.
            #
            # Threshold: rollback when failed_at <= 4 (knowledge_folders,
            # kanban_bootstrap, openclaw_workspace, persona_llm). Steps 5+
            # are at-or-after the legacy meta-write point and should keep
            # capability state visible (matches pre-W1 behavior + existing
            # `test_capabilities_partial_on_step_6_failure` expectation).
            # Step 7 (github_push) is the only externally-irreversible step;
            # it remains above the threshold and is never auto-rolled-back.
            if step_num <= 4:
                try:
                    projects_meta.delete_project(config.meta_path, slug)
                    rollback_status = "rolled_back"
                except Exception as rollback_err:  # pragma: no cover
                    rollback_status = f"rollback_failed: {rollback_err}"
                _log_event(config.log_path, {
                    "ts": dt.datetime.utcnow().isoformat() + "Z",
                    "slug": slug,
                    "step": step_num,
                    "name": "skeleton_rollback",
                    "status": rollback_status,
                })
            return {
                "success": False,
                "failed_at": step_num,
                "steps_completed": completed,
                "error_code": getattr(e, "code", "unknown"),
                "error_message": str(e),
            }

    return {
        "success": True,
        "id": slug,
        "steps_completed": 7,
        "github_url": f"https://github.com/{config.org}/{slug}",
    }


def step_remove_code_dir(slug: str, code_dir: Path) -> dict:
    """Step 1: rm -rf <code_dir>/<slug>. Idempotent (skip if missing)."""
    target = code_dir / slug
    if not target.exists():
        return {"removed": False, "reason": "not_found"}
    shutil.rmtree(target)
    return {"removed": True, "path": str(target)}


def step_remove_workspace(slug: str, openclaw_dir: Path) -> dict:
    """Step 2: rm -rf <openclaw>/<slug> + <openclaw>/workspace-<slug>."""
    runtime_dir = openclaw_dir / slug
    workspace_dir = openclaw_dir / f"workspace-{slug}"
    removed = 0
    for d in (runtime_dir, workspace_dir):
        if d.exists():
            shutil.rmtree(d)
            removed += 1
    return {"removed_dirs": removed}


def step_remove_bot_profile(
    slug: str, openclaw_dir: Path, meta_path: Path
) -> dict:
    """Step 3 (post-Phase-2): tear down Telegram bot profile + systemd unit + env file.

    Idempotent — no-op when the project's meta entry has no bot_id (i.e., bot
    was never connected). Soft-fails on systemctl errors (records in
    soft_failures, does not raise) — the unit may already be stopped/disabled
    or absent on a host where the bot was bootstrapped on a different machine.

    Cleans up:
      - systemctl --user stop  openclaw-gateway@<bot_id>.service
      - systemctl --user disable openclaw-gateway@<bot_id>.service
      - ~/.openclaw-<bot_id>/  (profile dir; uses HOME env so tests can mock)
      - ~/.openclaw/gateway/bots/<bot_id>.env
      - systemctl --user daemon-reload
    """
    # 1. Find bot_id in meta. Handle both list-shape (newer schema)
    #    and dict-shape (older read_meta default) defensively.
    bot_id = None
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            meta = {}
        projects = meta.get("projects")
        if isinstance(projects, list):
            for proj in projects:
                if isinstance(proj, dict) and proj.get("id") == slug:
                    bot_id = proj.get("bot_id")
                    break
        elif isinstance(projects, dict):
            entry = projects.get(slug) or {}
            if isinstance(entry, dict):
                bot_id = entry.get("bot_id")

    if not bot_id:
        return {"removed": False, "reason": "no_bot_id"}

    soft_failures: list = []
    unit = f"openclaw-gateway@{bot_id}.service"

    def _run_soft(cmd: list, step_name: str) -> bool:
        try:
            res = subprocess.run(
                cmd, capture_output=True, text=True, timeout=15
            )
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            soft_failures.append({"step": step_name, "error": str(e)})
            return False
        if res.returncode != 0:
            soft_failures.append({
                "step": step_name,
                "error": (res.stderr or res.stdout or "").strip()
                         or f"exit {res.returncode}",
            })
            return False
        return True

    # 2. systemctl stop + disable (soft-fail; record but don't raise)
    _run_soft(
        ["systemctl", "--user", "stop", unit],
        f"systemctl_stop:{unit}",
    )
    systemd_disabled = _run_soft(
        ["systemctl", "--user", "disable", unit],
        f"systemctl_disable:{unit}",
    )

    # 3. rm -rf ~/.openclaw-<bot_id>/  (HOME env-driven so tests work)
    home = Path(os.environ.get("HOME", str(Path.home())))
    profile_path = home / f".openclaw-{bot_id}"
    profile_removed = False
    if profile_path.exists():
        shutil.rmtree(profile_path)
        profile_removed = True

    # 4. rm gateway env file
    env_file = openclaw_dir / "gateway" / "bots" / f"{bot_id}.env"
    env_removed = False
    if env_file.exists():
        env_file.unlink()
        env_removed = True

    # 5. daemon-reload (soft)
    _run_soft(
        ["systemctl", "--user", "daemon-reload"],
        "systemctl_daemon_reload",
    )

    return {
        "removed": True,
        "bot_id": bot_id,
        "systemd_disabled": systemd_disabled,
        "profile_removed": profile_removed,
        "env_removed": env_removed,
        "soft_failures": soft_failures,
    }


def step_remove_kanban(
    slug: str, openclaw_dir: Path, actor: str = "bernard"
) -> dict:
    """Step 3: emit project_deleted event + remove sprints/tasks de state.json
    + remove de projects.yml. events.jsonl APPEND-ONLY (snapshot preservado).
    """
    kanban_dir = openclaw_dir / "kanban-tasks"
    state_path = kanban_dir / "state.json"
    events_path = kanban_dir / "events.jsonl"
    yml_path = kanban_dir / "projects.yml"

    if not state_path.exists():
        return {"sprints_removed": 0, "tasks_removed": 0, "noop": True}

    lock_path = state_path.with_suffix(".json.lock")
    lock_path.touch(exist_ok=True)

    sprints_removed = []
    tasks_removed = []
    new_seq = 0

    with open(lock_path, "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            state = json.loads(state_path.read_text())

            sprints_to_remove = [
                s for s in state.get("sprints", []) if s.get("project") == slug
            ]
            tasks_to_remove = [
                t for t in state.get("tasks", []) if t.get("project") == slug
            ]
            sprints_removed = [s["id"] for s in sprints_to_remove]
            tasks_removed = [t["id"] for t in tasks_to_remove]

            meta_path = openclaw_dir / "projects-meta.json"
            github_url = None
            created_at = None
            try:
                meta = projects_meta.read_meta(meta_path)
                entry = meta.get("projects", {}).get(slug, {})
                github_url = entry.get("github_url")
                created_at = entry.get("created_at")
            except Exception:
                pass

            new_seq = state.get("last_event_seq", 0) + 1
            event = {
                "seq": new_seq,
                "ts": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
                "type": "project_deleted",
                "actor": actor,
                "project": slug,
                "snapshot": {
                    "sprints_removed": sprints_removed,
                    "tasks_removed": tasks_removed,
                    "github_url": github_url,
                    "created_at": created_at,
                },
            }
            with open(events_path, "a") as ef:
                ef.write(json.dumps(event, ensure_ascii=False) + "\n")

            state["sprints"] = [
                s for s in state.get("sprints", []) if s.get("project") != slug
            ]
            state["tasks"] = [
                t for t in state.get("tasks", []) if t.get("project") != slug
            ]
            if "projects" in state and isinstance(state["projects"], list):
                state["projects"] = [p for p in state["projects"] if p != slug]
            state["last_event_seq"] = new_seq

            tmp = state_path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False))
            tmp.replace(state_path)

            if yml_path.exists():
                lines = yml_path.read_text().splitlines(keepends=True)
                filtered = [line for line in lines if line.strip() != f"- {slug}"]
                yml_path.write_text("".join(filtered))
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)

    return {
        "sprints_removed": len(sprints_removed),
        "tasks_removed": len(tasks_removed),
        "event_seq": new_seq,
    }


def step_remove_knowledge(slug: str, kb_dir: Path) -> dict:
    """Step 4: rm -rf 10_prd/<slug>/ + 40_roadmap/<slug>/."""
    removed = 0
    for folder in ("10_prd", "40_roadmap"):
        target = kb_dir / folder / slug
        if target.exists():
            shutil.rmtree(target)
            removed += 1
    return {"removed_folders": removed}


def step_remove_meta(slug: str, meta_path: Path) -> dict:
    """Step 5: projects_meta.delete_project. Atomic via flock."""
    projects_meta.delete_project(meta_path, slug)
    return {"removed": True}


def step_remove_github(
    slug: str, org: str, allow_soft_fail: bool = True
) -> dict:
    """Step 6: gh repo delete. Soft-fail on scope missing or already-gone."""
    cmd = ["gh", "repo", "delete", f"{org}/{slug}", "--yes"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode == 0:
        return {"github_deleted": True}
    if not allow_soft_fail:
        raise StepFailure(6, "gh_delete_failed", result.stderr.strip())
    stderr = result.stderr.strip()
    if "delete_repo" in stderr:
        hint = (
            "gh CLI lacks delete_repo scope. Run "
            "'gh auth refresh -h github.com -s delete_repo' or delete manually "
            f"at https://github.com/{org}/{slug}/settings"
        )
    elif "Could not resolve" in stderr or "404" in stderr:
        hint = f"Repo {org}/{slug} already deleted or never existed."
    else:
        hint = f"gh repo delete failed: {stderr}"
    return {
        "github_deleted": False,
        "github_hint": hint,
        "stderr": stderr,
    }


@dataclass
class ProjectRemoveConfig:
    kb_dir: Path
    openclaw_dir: Path
    code_dir: Path
    meta_path: Path
    log_path: Path  # ~/.openclaw/projects-delete.jsonl
    org: str = "bernardTavares"


def remove_project(
    slug: str,
    config: ProjectRemoveConfig,
    actor: str = "bernard",
    skip_github: bool = False,
) -> dict:
    """Orchestrate 6-step project deletion. Reverse-of-create order.

    Pre-flight rejects canonical / non-user_created. Failure mid-flow returns
    failed_at + steps_completed. Success returns github_deleted flag (false
    if soft-failed).
    """
    try:
        run_remove_preflight(slug, config.meta_path)
    except RemovePreflightFailure as e:
        return {
            "success": False,
            "failed_at": 0,
            "steps_completed": 0,
            "error_code": e.code,
            "error_message": str(e),
        }

    meta = projects_meta.read_meta(config.meta_path)
    pre_entry = meta.get("projects", {}).get(slug, {})
    snapshot = {
        "github_url": pre_entry.get("github_url"),
        "created_at": pre_entry.get("created_at"),
        "bot_id": pre_entry.get("bot_id"),
    }

    steps = [
        (1, "code_dir", lambda: step_remove_code_dir(slug, config.code_dir)),
        (2, "workspace", lambda: step_remove_workspace(slug, config.openclaw_dir)),
        (3, "bot_profile", lambda: step_remove_bot_profile(
            slug, config.openclaw_dir, config.meta_path)),
        (4, "kanban", lambda: step_remove_kanban(slug, config.openclaw_dir, actor)),
        (5, "knowledge", lambda: step_remove_knowledge(slug, config.kb_dir)),
        (6, "meta", lambda: step_remove_meta(slug, config.meta_path)),
    ]
    if not skip_github:
        steps.append(
            (7, "github", lambda: step_remove_github(slug, config.org))
        )

    completed = 0
    github_deleted = None
    github_hint = None
    log_entries = []

    for step_num, step_name, step_fn in steps:
        start = time.time()
        try:
            details = step_fn()
            duration_ms = int((time.time() - start) * 1000)
            log_entry = {
                "ts": dt.datetime.utcnow().isoformat() + "Z",
                "slug": slug,
                "step": step_num,
                "name": step_name,
                "status": "ok",
                "duration_ms": duration_ms,
            }
            log_entries.append(log_entry)
            _log_event(config.log_path, log_entry)
            completed = step_num
            if step_name == "kanban":
                snapshot["sprints_removed"] = details.get("sprints_removed", 0)
                snapshot["tasks_removed"] = details.get("tasks_removed", 0)
            if step_name == "bot_profile":
                snapshot["bot_id_removed"] = details.get("bot_id")
                snapshot["bot_profile_removed"] = details.get("profile_removed", False)
                snapshot["bot_env_removed"] = details.get("env_removed", False)
                snapshot["bot_systemd_disabled"] = details.get("systemd_disabled", False)
                snapshot["bot_soft_failures"] = details.get("soft_failures", [])
            if step_name == "github":
                github_deleted = details.get("github_deleted")
                github_hint = details.get("github_hint")
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            log_entry = {
                "ts": dt.datetime.utcnow().isoformat() + "Z",
                "slug": slug,
                "step": step_num,
                "name": step_name,
                "status": "failed",
                "duration_ms": duration_ms,
                "error": str(e),
            }
            log_entries.append(log_entry)
            _log_event(config.log_path, log_entry)
            return {
                "success": False,
                "failed_at": step_num,
                "steps_completed": completed,
                "error_code": getattr(e, "code", "unknown"),
                "error_message": str(e),
                "log": log_entries,
            }

    if skip_github:
        github_deleted = False
        github_hint = "Skipped via --skip-github"

    return {
        "success": True,
        "id": slug,
        "steps_completed": completed,
        "github_deleted": github_deleted,
        "github_hint": github_hint,
        "snapshot": snapshot,
        "log": log_entries,
    }
