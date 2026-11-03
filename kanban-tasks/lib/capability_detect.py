"""Capability detect helpers (pure, runtime introspection).

Each detect function takes a slug + paths/config + optional meta_entry and
returns a dict with at least {"state": one_of(absent|partial|provisioned|drifted)}
plus optional fields per capability. No side-effects on disk or remote services.

Spec: bevox-knowledge/35_specs/openclaw/2026-05-07-project-lifecycle-w1-v1.md §Detect helpers
ADR: bevox-knowledge/30_adr/openclaw/ADR-013-project-capability-state-machine.md
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


# 9 canonical folders per ADR-010.
KNOWLEDGE_FOLDERS = (
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
class DetectPaths:
    """Bundle of filesystem roots needed by detect helpers."""
    kb_dir: Path
    openclaw_dir: Path
    code_dir: Path
    org: str = "bernardTavares"


def _run_cmd(cmd: list, timeout: int = 10) -> tuple[int, str, str]:
    """Soft subprocess.run wrapper — never raises. Returns (rc, stdout, stderr).

    rc=-1 means binary missing or timeout (treat as soft-fail).
    """
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return -1, "", ""
    return result.returncode, (result.stdout or "").strip(), (result.stderr or "").strip()


# ============ 1. code_repo ============

def detect_code_repo(
    slug: str,
    paths: DetectPaths,
    *,
    skip_remote: bool = False,
) -> dict:
    """is_dir(code_dir/slug) + gh repo view org/slug.

    States:
    - absent: nem local nem remote.
    - partial: só local (sem github) ou só remote (sem local — drifted variant).
    - provisioned: ambos OK.
    - drifted: github existe e local não (registered mas dir removido manualmente).

    skip_remote=True: assume github match local (pra tests / fast-path).
    """
    local_path = paths.code_dir / slug
    has_local = local_path.is_dir()
    github_full = f"{paths.org}/{slug}"
    github_url = f"https://github.com/{github_full}"

    if skip_remote:
        if has_local:
            return {
                "state": "provisioned",
                "path": str(local_path),
                "github": github_url,
            }
        return {"state": "absent"}

    rc, _, _ = _run_cmd(["gh", "repo", "view", github_full])
    has_remote = rc == 0

    if has_local and has_remote:
        return {
            "state": "provisioned",
            "path": str(local_path),
            "github": github_url,
        }
    if has_local and not has_remote:
        return {
            "state": "partial",
            "path": str(local_path),
            "github": None,
        }
    if not has_local and has_remote:
        return {
            "state": "drifted",
            "path": None,
            "github": github_url,
            "drift_reason": "github exists, local repo missing",
        }
    return {"state": "absent"}


# ============ 2. knowledge_slot ============

def detect_knowledge_slot(slug: str, paths: DetectPaths) -> dict:
    """Conta quantos dos 9 folders ADR-010 têm subdir <slug> committed em
    origin/main de bevox-knowledge.

    States:
    - 0/9: absent
    - 1-8/9: partial
    - 9/9: provisioned
    - partial + drift_reason: when `git ls-tree origin/main` fails (CI/fresh
      clone without origin/main fetched). Returns partial (not absent) so
      callers see "could not verify" rather than a silent false-negative.
    """
    if not paths.kb_dir.is_dir():
        return {"state": "absent", "folders_present": 0, "folders_total": 9}

    rc, stdout, stderr = _run_cmd(
        ["git", "-C", str(paths.kb_dir), "ls-tree", "-d", "--name-only", "origin/main"],
    )
    if rc != 0:
        # W1 review fix #2: surface "cannot verify" instead of silent absent.
        # Common cause is fresh clone without `git fetch` (no origin/main ref)
        # — populating absent in a migration would mask real state.
        first_stderr_line = (stderr.splitlines()[0] if stderr else "").strip()
        return {
            "state": "partial",
            "folders_present": 0,
            "folders_total": 9,
            "drift_reason": (
                f"git ls-tree origin/main failed (rc={rc}); "
                f"cannot verify slot. stderr: {first_stderr_line}"
            ),
        }

    top_level = set(stdout.splitlines())
    present = []
    for folder in KNOWLEDGE_FOLDERS:
        if folder not in top_level:
            continue
        rc2, sub_out, _ = _run_cmd(
            ["git", "-C", str(paths.kb_dir), "ls-tree", "-d", "--name-only",
             f"origin/main:{folder}"],
        )
        if rc2 == 0 and slug in sub_out.splitlines():
            present.append(folder)

    count = len(present)
    if count == 0:
        state = "absent"
    elif count >= 9:
        state = "provisioned"
    else:
        state = "partial"

    return {
        "state": state,
        "slot": slug,
        "folders_present": count,
        "folders_total": 9,
        "folders": present,
    }


# ============ 3. kanban_sprints ============

def detect_kanban_sprints(slug: str, paths: DetectPaths) -> dict:
    """Lookup em kanban-tasks/state.json por current+next sprint do projeto.

    States:
    - absent: nenhum sprint do projeto.
    - partial: só current OU só next.
    - provisioned: ambos.
    """
    state_path = paths.openclaw_dir / "kanban-tasks" / "state.json"
    if not state_path.is_file():
        return {"state": "absent"}
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"state": "absent", "drift_reason": "state.json unreadable"}

    sprints = data.get("sprints") or []
    project_sprints = [
        s for s in sprints
        if isinstance(s, dict) and s.get("project") == slug
    ]
    current = next(
        (s for s in project_sprints if s.get("status") == "current"), None
    )
    nxt = next(
        (s for s in project_sprints if s.get("status") == "next"), None
    )

    if current and nxt:
        return {
            "state": "provisioned",
            "current_sprint": current.get("id"),
            "next_sprint": nxt.get("id"),
        }
    if current or nxt:
        return {
            "state": "partial",
            "current_sprint": current.get("id") if current else None,
            "next_sprint": nxt.get("id") if nxt else None,
        }
    return {"state": "absent"}


# ============ 4. workspace ============

def detect_workspace(slug: str, paths: DetectPaths) -> dict:
    """is_dir(workspace-<slug>/) + IDENTITY.md presente.

    States:
    - absent: dir não existe.
    - partial: dir existe mas IDENTITY.md ausente.
    - provisioned: ambos OK.
    """
    workspace_dir = paths.openclaw_dir / f"workspace-{slug}"
    if not workspace_dir.is_dir():
        return {"state": "absent"}
    identity = workspace_dir / "IDENTITY.md"
    if not identity.is_file():
        return {
            "state": "partial",
            "path": str(workspace_dir),
            "drift_reason": "IDENTITY.md missing",
        }
    return {"state": "provisioned", "path": str(workspace_dir)}


# ============ 5. persona ============

_PERSONA_RE = re.compile(r"^persona_status:\s*(\S+)\s*$", re.MULTILINE)


def detect_persona(slug: str, paths: DetectPaths) -> dict:
    """Frontmatter persona_status em IDENTITY.md.

    States:
    - generated → provisioned
    - pending → partial
    - missing/no IDENTITY → absent
    """
    identity = paths.openclaw_dir / f"workspace-{slug}" / "IDENTITY.md"
    if not identity.is_file():
        return {"state": "absent"}
    try:
        text = identity.read_text(encoding="utf-8")
    except OSError:
        return {"state": "absent", "drift_reason": "IDENTITY.md unreadable"}
    m = _PERSONA_RE.search(text)
    if not m:
        return {"state": "absent"}
    status = m.group(1)
    if status == "generated":
        return {"state": "provisioned", "persona_status": "generated"}
    if status == "pending":
        return {"state": "partial", "persona_status": "pending"}
    return {"state": "absent", "persona_status": status}


# ============ 6. bot ============

def detect_bot(
    slug: str,
    paths: DetectPaths,
    meta_entry: Optional[dict] = None,
    *,
    skip_systemctl: bool = False,
) -> dict:
    """bot_id em meta + ~/.openclaw-<bot_id>/ dir + systemctl unit active.

    Considera dois nomes de unit per memory `project_factory_bot_lifecycle_gaps_w3`:
    - openclaw-gateway@<bot_id>.service (template — preferido)
    - openclaw-gateway-<bot_id>.service (custom-named legacy)

    States:
    - absent: bot_id null/missing.
    - partial: bot_id declarado mas profile dir ausente OU systemd inactive.
    - provisioned: tudo OK.
    - drifted: bot_id declarado mas tudo abaixo missing.
    """
    if not isinstance(meta_entry, dict):
        return {"state": "absent"}
    bot_id = meta_entry.get("bot_id")
    if not bot_id:
        return {"state": "absent"}

    home = Path(os.environ.get("HOME", str(Path.home())))
    profile = home / f".openclaw-{bot_id}"
    has_profile = profile.is_dir()

    if skip_systemctl:
        # Pra tests — assume systemd active se profile existe.
        systemd_active = has_profile
    else:
        units = (
            f"openclaw-gateway@{bot_id}.service",
            f"openclaw-gateway-{bot_id}.service",
        )
        systemd_active = False
        for unit in units:
            rc, _, _ = _run_cmd(
                ["systemctl", "--user", "is-active", "--quiet", unit],
            )
            if rc == 0:
                systemd_active = True
                break

    fields = {
        "area": bot_id,
        "port": meta_entry.get("bot_port"),
        "profile": str(profile),
    }
    if has_profile and systemd_active:
        return {"state": "provisioned", **fields}
    if has_profile or systemd_active:
        return {
            "state": "partial",
            **fields,
            "drift_reason": (
                "profile missing" if not has_profile else "systemd inactive"
            ),
        }
    return {
        "state": "drifted",
        **fields,
        "drift_reason": "bot_id declared but profile + systemd missing",
    }


# ============ 7. telegram_topics ============

def detect_telegram_topics(
    slug: str,
    paths: DetectPaths,
    meta_entry: Optional[dict] = None,
) -> dict:
    """telegram.topics.{clarifications, dispatcher, blocks, knowledge} non-null em meta.

    States:
    - absent: telegram.topics ausente ou todos null.
    - partial: 1-3/4 thread_ids non-null.
    - provisioned: 4/4.
    """
    if not isinstance(meta_entry, dict):
        return {"state": "absent"}
    telegram = meta_entry.get("telegram") or {}
    topics = telegram.get("topics") or {} if isinstance(telegram, dict) else {}
    if not isinstance(topics, dict):
        return {"state": "absent"}

    # ADR-015 (formalizes ADR-013 §canonical topics) lists 4 canonical:
    # clarifications + dispatcher + blocks + knowledge.
    # 'blocks' added in UBN delivery (2026-05-04). 'knowledge' added in
    # skill V2 W0 (2026-05-08) for knowledge watcher Telegram routing.
    expected = ("clarifications", "dispatcher", "blocks", "knowledge")
    present = {k: topics.get(k) for k in expected if topics.get(k) is not None}
    count = len(present)

    if count == 0:
        return {"state": "absent"}
    if count >= 4:
        return {"state": "provisioned", **present}
    return {"state": "partial", **present}


# ============ 8. mission_control ============

def detect_mission_control(
    slug: str,
    paths: DetectPaths,
    meta_entry: Optional[dict] = None,
) -> dict:
    """Always returns absent until a real MC sync API exists.

    MC currently reads `~/.openclaw/projects-meta.json` directly (see
    mission-control/src/lib/projects/meta.ts), so visibility is implicit
    once the entry is written by adopt — but absent here remains the
    honest detector result until a true `/api/projects/<slug>` probe
    (with auth) is wired in.

    See `provision_mission_control` for the matching no-op success path
    so adopt does not surface an error on this capability.
    """
    return {"state": "absent"}


# ============ Aggregator ============

def detect_all(
    slug: str,
    paths: DetectPaths,
    meta_entry: Optional[dict] = None,
    *,
    skip_remote: bool = False,
    skip_systemctl: bool = False,
    skip_knowledge: bool = False,
) -> dict:
    """Run all 8 detect helpers, return {<capability>: {state, ...}}.

    skip_knowledge=True bypasses `detect_knowledge_slot` entirely, returning
    state=skipped + drift_reason. Use on hosts/CI where bevox-knowledge has
    no `origin/main` fetched (e.g., fresh `migrate-meta` runs) so the migration
    does not lock in an inaccurate slot state. Mirrors `skip_remote` /
    `skip_systemctl` ergonomics.
    """
    if skip_knowledge:
        knowledge_result = {
            "state": "skipped",
            "drift_reason": "knowledge_slot detection skipped via flag",
        }
    else:
        knowledge_result = detect_knowledge_slot(slug, paths)
    return {
        "code_repo": detect_code_repo(
            slug, paths, skip_remote=skip_remote
        ),
        "knowledge_slot": knowledge_result,
        "kanban_sprints": detect_kanban_sprints(slug, paths),
        "workspace": detect_workspace(slug, paths),
        "persona": detect_persona(slug, paths),
        "bot": detect_bot(
            slug, paths, meta_entry, skip_systemctl=skip_systemctl,
        ),
        "telegram_topics": detect_telegram_topics(slug, paths, meta_entry),
        "mission_control": detect_mission_control(slug, paths, meta_entry),
    }
