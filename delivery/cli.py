#!/usr/bin/env python3
"""
E5 wave 1 — Delivery CLI.

Subcommand dispatch for openclaw-delivery. Imports primitives from agent.py.

Spec: bevox-knowledge/35_specs/2026-04-13-e5-roadmap-delivery-os-wave-1.md
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Optional

import agent  # local import; same directory


# ── Helpers ────────────────────────────────────────────────────────


def _resolve_spec_path(arg: str) -> Path:
    """Resolve a spec path arg. Accepts absolute, relative to bevox-knowledge, or cwd."""
    p = Path(arg).expanduser()
    if p.is_absolute() and p.exists():
        return p
    # Try as relative to bevox-knowledge
    in_kb = agent.KNOWLEDGE_DIR / arg
    if in_kb.exists():
        return in_kb
    # Try cwd-relative
    if p.exists():
        return p.resolve()
    raise FileNotFoundError(f"spec not found: {arg}")


def _normalize_spec_path_for_storage(p: Path) -> str:
    """Store the spec path canonically.

    If under bevox-knowledge, store as relative path (e.g. '35_specs/foo.md').
    Otherwise, store absolute.
    """
    try:
        rel = p.resolve().relative_to(agent.KNOWLEDGE_DIR.resolve())
        return str(rel)
    except (ValueError, RuntimeError):
        return str(p.resolve())


def _find_proposal_by_prefix(state: dict, prefix: str) -> str:
    """Find a proposal_id by short prefix. Raises if ambiguous or not found."""
    matches = [pid for pid in state["proposals"].keys() if pid.startswith(prefix) or pid.startswith(f"prop_{prefix}")]
    if len(matches) == 0:
        raise LookupError(f"no proposal found matching {prefix!r}")
    if len(matches) > 1:
        raise LookupError(f"ambiguous prefix {prefix!r} matches: {matches}")
    return matches[0]


# ── Subcommands ────────────────────────────────────────────────────


def cmd_activate_spec(args) -> int:
    p = _resolve_spec_path(args.path)
    stored = _normalize_spec_path_for_storage(p)
    state = agent.read_state()
    if stored in state.get("active_specs", {}):
        print(f"error: spec already active: {stored}", file=sys.stderr)
        return 2
    evt = agent.emit_event(actor="cli", type="spec.activated", payload={"spec_path": stored})
    agent.rebuild_state()
    print(f"activated: {stored}")
    print(f"event_id: {evt['event_id']}")
    return 0


def cmd_archive_spec(args) -> int:
    p = _resolve_spec_path(args.path)
    stored = _normalize_spec_path_for_storage(p)
    state = agent.read_state()
    if stored not in state.get("active_specs", {}):
        print(f"error: spec not active: {stored}", file=sys.stderr)
        return 2
    archive_evt = agent.emit_event(
        actor="cli",
        type="spec.archived",
        payload={"spec_path": stored, "reason": args.reason},
    )
    # Cascade: expire all pending proposals from this spec
    expired_count = 0
    for pid, pdata in state["proposals"].items():
        if pdata["spec_path"] == stored and pdata["state"] == "pending":
            agent.emit_event(
                actor="cli",
                type="proposal.expired",
                payload={
                    "proposal_id": pid,
                    "key": pdata["key"],
                    "reason": "spec_archived",
                    "triggered_by": archive_evt["event_id"],
                },
            )
            expired_count += 1
    agent.rebuild_state()
    print(f"archived: {stored} (reason={args.reason})")
    print(f"expired pending proposals: {expired_count}")
    return 0


def cmd_scan(args) -> int:
    summary = agent.run_scan()
    print(f"scan {summary['run_id']}: {summary['proposals_emitted']} new proposal(s) from {summary['specs_scanned']} spec(s)")
    return 0


def cmd_proposals(args) -> int:
    state = agent.read_state()
    if args.all:
        items = list(state["proposals"].items())
    else:
        target_state = args.state or "pending"
        items = [(pid, p) for pid, p in state["proposals"].items() if p["state"] == target_state]
    if not items:
        print("No proposals." if args.all else f"No {args.state or 'pending'} proposals.")
        return 0
    if args.json:
        print(json.dumps([{**p, "proposal_id": pid} for pid, p in items], indent=2))
        return 0
    print(f"{'PROPOSAL_ID':<12}  {'STATE':<9}  {'SECTION':<10}  {'ITEM'}")
    for pid, p in items:
        short = pid[:12]
        item = p["item_text"][:60]
        print(f"{short:<12}  {p['state']:<9}  {p['section_id']:<10}  {item}")
    return 0


def cmd_accept(args) -> int:
    state = agent.read_state()
    try:
        pid = _find_proposal_by_prefix(state, args.proposal_id)
    except LookupError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    pdata = state["proposals"][pid]
    if pdata["state"] != "pending":
        print(f"error: proposal {pid} is not pending (state={pdata['state']})", file=sys.stderr)
        return 2

    # E5 wave 1: emit task.created (local-first invariant)
    task_id = f"task_{uuid.uuid4().hex[:12]}"
    agent.emit_event(
        actor="cli",
        type="task.created",
        payload={"proposal_id": pid, "key": pdata["key"], "task_id": task_id},
    )
    agent.rebuild_state()
    print(f"accepted: {pid} -> {task_id}")

    # E6 wave 1: linkage subflow
    state_refreshed = agent.read_state()
    pdata_refreshed = state_refreshed["proposals"][pid]
    proposal_data = _build_proposal_data_for_linkage(state_refreshed, pid)

    repo = _resolve_target_repo(
        state_refreshed,
        pdata_refreshed["spec_path"],
        args.repo,
    )

    _run_linkage_subflow(
        task_id=task_id,
        key=pdata["key"],
        proposal_data=proposal_data,
        repo=repo,
    )
    return 0


def cmd_reject(args) -> int:
    state = agent.read_state()
    try:
        pid = _find_proposal_by_prefix(state, args.proposal_id)
    except LookupError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    pdata = state["proposals"][pid]
    if pdata["state"] != "pending":
        print(f"error: proposal {pid} is not pending (state={pdata['state']})", file=sys.stderr)
        return 2
    agent.emit_event(
        actor="cli",
        type="task.rejected",
        payload={"proposal_id": pid, "key": pdata["key"], "reason": args.reason},
    )
    agent.rebuild_state()
    print(f"rejected: {pid} (reason: {args.reason})")
    return 0


def cmd_status(args) -> int:
    state = agent.read_state()
    n_active = len(state.get("active_specs", {}))
    proposals = state.get("proposals", {})
    n_pending = sum(1 for p in proposals.values() if p["state"] == "pending")
    n_accepted = sum(1 for p in proposals.values() if p["state"] == "accepted")
    n_rejected = sum(1 for p in proposals.values() if p["state"] == "rejected")
    n_expired = sum(1 for p in proposals.values() if p["state"] == "expired")
    last_scan = state.get("last_scan") or {}
    print(f"openclaw-delivery status (wave 1)")
    print(f"  active specs:       {n_active}")
    print(f"  proposals pending:  {n_pending}")
    print(f"  proposals accepted: {n_accepted}")
    print(f"  proposals rejected: {n_rejected}")
    print(f"  proposals expired:  {n_expired}")
    if last_scan:
        print(f"  last scan:          {last_scan.get('finished_at', '?')} (run_id={last_scan.get('run_id', '?')})")
        print(f"                      specs={last_scan.get('specs_scanned', '?')} proposals={last_scan.get('proposals_emitted', '?')}")
    else:
        print(f"  last scan:          (never)")
    return 0


def cmd_rebuild_state(args) -> int:
    state = agent.rebuild_state()
    print(f"state.json rebuilt: {len(state['active_specs'])} active spec(s), {len(state['proposals'])} proposal(s)")
    return 0


# ── E6 wave 1 helpers ──────────────────────────────────────────────

_REPO_RE = re.compile(r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$")


def _validate_repo_format(repo: str) -> None:
    """Raises SystemExit(2) if repo does not match regex."""
    if not _REPO_RE.match(repo):
        print(f"error: invalid repo format: {repo!r} (expected 'owner/name')", file=sys.stderr)
        sys.exit(2)


def cmd_set_spec_repo(args) -> int:
    _validate_repo_format(args.repo)

    # Resolve spec path (allows bare filename or path relative to bevox-knowledge)
    try:
        p = _resolve_spec_path(args.spec_path)
        stored = _normalize_spec_path_for_storage(p)
    except FileNotFoundError:
        # If path can't be resolved, try to check if it's in active_specs anyway
        # (for specs that were activated but file is now missing)
        stored = args.spec_path

    state = agent.read_state()
    if stored not in state.get("active_specs", {}):
        print(f"error: spec not active: {stored}", file=sys.stderr)
        return 2

    evt = agent.emit_event(
        actor="cli",
        type="spec.github_repo_set",
        payload={"spec_path": stored, "repo": args.repo},
    )
    agent.rebuild_state()
    print(f"spec repo set: {stored} -> {args.repo}")
    print(f"event_id: {evt['event_id']}")
    return 0


def _build_proposal_data_for_linkage(state: dict, proposal_id: str) -> dict:
    """Constrói o dict passado a build_issue_body a partir do state atual."""
    p = state["proposals"][proposal_id]
    return {
        "spec_path": p["spec_path"],
        "section_id": p["section_id"],
        "item_text": p["item_text"],
        "proposal_id": proposal_id,
        "task_id": p["task_id"],
        "key": p["key"],
        "proposed_at": p["proposed_at"],
        "resolved_at": p["resolved_at"],
    }


def _resolve_target_repo(
    state: dict,
    spec_path: str,
    cli_flag_repo: Optional[str],
) -> Optional[str]:
    """Cascata de resolução do repo alvo (spec §3.4 step 3).

    1. --repo CLI flag
    2. state.active_specs[spec_path].github_repo
    3. None (caller trata como repo_unresolved)
    """
    if cli_flag_repo is not None:
        return cli_flag_repo
    spec_entry = state.get("active_specs", {}).get(spec_path)
    if spec_entry and spec_entry.get("github_repo"):
        return spec_entry["github_repo"]
    return None


def _run_linkage_subflow(
    task_id: str,
    key: str,
    proposal_data: dict,
    repo: Optional[str],
) -> None:
    """Linkage subflow compartilhado entre cmd_accept e cmd_github_link.

    Preconditions: task.created JÁ foi emitido pelo caller (para accept)
    ou task_id JÁ é accepted (para github-link).

    - Se repo is None: emit task.github_link_failed com repo_unresolved.
    - Senão: tenta gh via create_github_issue; emit success ou failed.
    - Sempre rebuild_state ao final.
    - Sempre retorna (não raises).
    """
    if repo is None:
        agent.emit_event(
            actor="cli",
            type="task.github_link_failed",
            payload={
                "task_id": task_id,
                "key": key,
                "repo": None,
                "error_kind": "repo_unresolved",
                "message": "pass --repo or run set-spec-repo",
            },
        )
        agent.rebuild_state()
        print(
            f"WARN: github link failed (repo_unresolved): no target repo.\n"
            f"Retry after setting repo:\n"
            f"  openclaw-delivery set-spec-repo {proposal_data['spec_path']} --repo <owner/name>",
            file=sys.stderr,
        )
        return

    # Try gh subprocess path
    with_label = agent.ensure_delivery_label(repo)
    title = agent.build_issue_title(proposal_data["item_text"])
    body = agent.build_issue_body(proposal_data)

    try:
        issue = agent.create_github_issue(
            repo=repo, title=title, body=body, with_label=with_label,
        )
    except agent.GithubIssueError as e:
        agent.emit_event(
            actor="cli",
            type="task.github_link_failed",
            payload={
                "task_id": task_id,
                "key": key,
                "repo": repo,
                "error_kind": e.error_kind,
                "message": e.message,
            },
        )
        agent.rebuild_state()
        print(
            f"WARN: github link failed ({e.error_kind}): {e.message[:200]}\n"
            f"Retry: openclaw-delivery github-link {task_id}",
            file=sys.stderr,
        )
        return

    # Success
    agent.emit_event(
        actor="cli",
        type="task.github_linked",
        payload={
            "task_id": task_id,
            "key": key,
            "repo": repo,
            "issue_number": issue["issue_number"],
            "issue_url": issue["issue_url"],
        },
    )
    agent.rebuild_state()
    print(f"  -> {issue['issue_url']}")


def _find_proposal_by_task_id(state: dict, task_id: str) -> Optional[str]:
    """Reverse lookup: task_id -> proposal_id."""
    for pid, pdata in state.get("proposals", {}).items():
        if pdata.get("task_id") == task_id:
            return pid
    return None


def cmd_github_link(args) -> int:
    state = agent.read_state(agent.STATE_PATH)
    pid = _find_proposal_by_task_id(state, args.task_id)
    if pid is None:
        print(f"error: task {args.task_id!r} not found in state", file=sys.stderr)
        return 2

    pdata = state["proposals"][pid]
    if pdata["state"] != "accepted":
        print(
            f"error: task {args.task_id} proposal is in state {pdata['state']!r}, expected 'accepted'",
            file=sys.stderr,
        )
        return 2

    github_link = pdata.get("github_link")
    if github_link is not None and github_link.get("state") == "linked":
        print(
            f"error: task {args.task_id} already linked to {github_link.get('issue_url')}",
            file=sys.stderr,
        )
        return 2

    # Resolve repo
    repo = _resolve_target_repo(state, pdata["spec_path"], args.repo)

    proposal_data = _build_proposal_data_for_linkage(state, pid)

    # Run linkage subflow (no task.created emission — already exists)
    _run_linkage_subflow(
        task_id=args.task_id,
        key=pdata["key"],
        proposal_data=proposal_data,
        repo=repo,
    )
    return 0


# ── E6/F4 wave 1 — Release notes assistidas ────────────────────────
#
# Spec: bevox-knowledge/35_specs/2026-04-18-e6-f4-release-notes-wave-1.md


_CONV_PREFIX_RE = re.compile(r"^(feat|fix|docs|refactor|chore|test)(\([^)]+\))?:")
_RN_GROUPS = ("feat", "fix", "docs", "refactor", "chore", "test", "other")
_ISSUE_REF_RE = re.compile(r"(?:^|\s)#(\d+)\b")

_RN_SECTION_TITLES = {
    "feat": "Features",
    "fix": "Bug Fixes",
    "docs": "Documentation",
    "refactor": "Refactoring",
    "chore": "Chores",
    "test": "Tests",
    "other": "Other",
}

SUPPORTED_REPOS = {
    "bevox-knowledge": {
        "github": "bernardTavares/bevox-knowledge",
        "clone": f"{Path.home()}/bevox-knowledge",
    },
    "knowledge-sync": {
        "github": "bernardTavares/knowledge-sync",
        "clone": f"{Path.home()}/code/knowledge-sync",
    },
}


def _group_commits(commits: list[dict]) -> dict[str, list[dict]]:
    """Classify commits by conventional-commit prefix.

    Input: list of {sha, subject, body} dicts (order = git log order).
    Output: dict with keys feat/fix/docs/refactor/chore/test/other,
    each a list of matched commits in input order. Unmatched → "other".
    """
    groups: dict[str, list[dict]] = {k: [] for k in _RN_GROUPS}
    for c in commits:
        match = _CONV_PREFIX_RE.match(c.get("subject", ""))
        groups[match.group(1) if match else "other"].append(c)
    return groups


def _parse_issue_refs(commits: list[dict]) -> list[int]:
    """Extract unique #N issue references from commit subjects+bodies.

    Returns sorted ascending list of int issue numbers (deduplicated).
    Matches only standalone `#NNN` (not `abc#123`, not `#abc`).
    """
    refs: set[int] = set()
    for c in commits:
        text = f"{c.get('subject', '')}\n{c.get('body', '')}"
        for m in _ISSUE_REF_RE.finditer(text):
            refs.add(int(m.group(1)))
    return sorted(refs)


def _strip_conv_prefix(subject: str) -> str:
    """Strip `feat:`, `fix(scope):`, etc. from start of subject."""
    return _CONV_PREFIX_RE.sub("", subject, count=1).lstrip()


def _render_markdown(
    repo_short: str,
    since_sha_short: str,
    to_sha_short: str,
    commit_count: int,
    generated_at: str,
    groups: dict[str, list[dict]],
    issue_refs: list[int],
) -> str:
    """Build the spec §5.5 markdown shape.

    Sections with empty groups are omitted. "Referenced issues" omitted
    if issue_refs empty. Subject prefix stripped for grouped sections;
    "Other" keeps full subject.
    """
    plural = "commits" if commit_count != 1 else "commit"
    lines: list[str] = [
        f"# Release notes — {repo_short}",
        "",
        f"**Range:** `{since_sha_short}..{to_sha_short}` "
        f"({commit_count} {plural}, merges excluidos)",
        f"**Generated:** {generated_at}",
        "",
    ]
    for key in _RN_GROUPS:
        bucket = groups.get(key, [])
        if not bucket:
            continue
        lines.append(f"## {_RN_SECTION_TITLES[key]}")
        lines.append("")
        for c in bucket:
            subject = c.get("subject", "")
            display = subject if key == "other" else _strip_conv_prefix(subject)
            lines.append(f"- {display} ({c.get('sha', '')[:7]})")
        lines.append("")
    if issue_refs:
        lines.append("## Referenced issues")
        lines.append("")
        for n in issue_refs:
            lines.append(f"- #{n}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _resolve_range(
    clone_path: str,
    since: Optional[str],
    to: Optional[str],
) -> tuple[str, str, str, str]:
    """Resolve (since_label, to_label, since_sha, to_sha) for git range.

    - If since is None, uses `git describe --tags --abbrev=0`.
    - If to is None, uses "HEAD".
    - Raises FileNotFoundError if clone_path missing.
    - Raises ValueError("no tags...") if since=None and no tags.
    - Raises ValueError("ref not found: X") if any ref invalid.
    """
    import subprocess as _sp
    clone = Path(clone_path)
    if not clone.exists() or not (clone / ".git").exists():
        raise FileNotFoundError(f"local clone not found: {clone_path}")

    def _git(*args):
        return _sp.run(
            ["git", "-C", str(clone), *args],
            capture_output=True, text=True, timeout=10,
        )

    if since is None:
        r = _git("describe", "--tags", "--abbrev=0")
        if r.returncode != 0:
            raise ValueError(
                f"no tags found in {clone_path}; pass --since explicitly"
            )
        since_label = r.stdout.strip()
    else:
        since_label = since

    to_label = to if to is not None else "HEAD"

    r_since = _git("rev-parse", "--verify", f"{since_label}^{{commit}}")
    if r_since.returncode != 0:
        raise ValueError(f"ref not found: {since_label}")
    since_sha = r_since.stdout.strip()

    r_to = _git("rev-parse", "--verify", f"{to_label}^{{commit}}")
    if r_to.returncode != 0:
        raise ValueError(f"ref not found: {to_label}")
    to_sha = r_to.stdout.strip()

    return since_label, to_label, since_sha, to_sha


def _read_git_log(clone_path: str, since: str, to: str) -> list[dict]:
    """Read commits in (since..to] EXCLUDING merges (spec §2.11).

    Returns list of {sha, subject, body} dicts in git log order
    (newest first). Raises RuntimeError on git failure.
    """
    import subprocess as _sp
    # NUL between fields, ASCII RS (0x1e) between records
    fmt = "%H%x00%s%x00%b%x1e"
    r = _sp.run(
        ["git", "-C", clone_path, "log", "--no-merges",
         f"--pretty=format:{fmt}", f"{since}..{to}"],
        capture_output=True, text=True, timeout=30,
    )
    if r.returncode != 0:
        raise RuntimeError(f"git log failed: {r.stderr.strip()[:500]}")
    raw = r.stdout
    if not raw:
        return []
    commits: list[dict] = []
    for record in raw.split("\x1e"):
        record = record.strip("\n")
        if not record:
            continue
        parts = record.split("\x00")
        if len(parts) < 3:
            continue
        commits.append({
            "sha": parts[0],
            "subject": parts[1],
            "body": parts[2].strip(),
        })
    return commits


_GH_RELEASE_URL_RE = re.compile(
    r"^https://github\.com/[^/]+/[^/]+/releases/(?:tag/[^/\s]+|untagged-[a-f0-9]+)\s*$",
    re.MULTILINE,
)


def _publish_draft(
    github_repo: str,
    tag: str,
    title: str,
    markdown: str,
) -> dict:
    """Publish a GitHub Release draft via gh CLI.

    Pre-checks tag existence (`gh release view`) before creating.
    Returns:
        {"ok": True,  "url": "https://..."}
        {"ok": False, "error_kind": "tag_exists"|"network_timeout"|...,
                      "message": "<truncated stderr>"}
    """
    # Pre-check: does the tag already have a release?
    try:
        view = subprocess.run(
            ["gh", "release", "view", tag, "--repo", github_repo],
            capture_output=True, text=True, timeout=10,
        )
    except FileNotFoundError as e:
        return {"ok": False, "error_kind": "gh_not_installed",
                "message": str(e)[:500]}
    except subprocess.TimeoutExpired as e:
        return {"ok": False, "error_kind": "network_timeout",
                "message": f"gh: timeout after {e.timeout}s"[:500]}

    if view.returncode == 0:
        return {"ok": False, "error_kind": "tag_exists",
                "message": f"draft already exists for tag {tag}; "
                           f"use different --tag or delete via "
                           f"'gh release delete {tag} --repo {github_repo}'"}

    # Pre-check failed-not-found is OK; any other pre-check error → propagate
    stderr_l = view.stderr.lower()
    if ("not found" not in stderr_l and "release not found" not in stderr_l
            and view.returncode != 1):
        kind, msg = agent.parse_gh_error(view.returncode, view.stdout,
                                          view.stderr)
        return {"ok": False, "error_kind": kind, "message": msg}

    # Create the draft
    try:
        create = subprocess.run(
            ["gh", "release", "create", tag,
             "--draft", "--notes-file", "-",
             "--title", title, "--repo", github_repo],
            input=markdown, capture_output=True, text=True, timeout=10,
        )
    except FileNotFoundError as e:
        return {"ok": False, "error_kind": "gh_not_installed",
                "message": str(e)[:500]}
    except subprocess.TimeoutExpired as e:
        return {"ok": False, "error_kind": "network_timeout",
                "message": f"gh: timeout after {e.timeout}s"[:500]}

    if create.returncode != 0:
        kind, msg = agent.parse_gh_error(create.returncode, create.stdout,
                                          create.stderr)
        return {"ok": False, "error_kind": kind, "message": msg}

    # Parse URL from stdout
    m = _GH_RELEASE_URL_RE.search(create.stdout)
    if not m:
        return {"ok": False, "error_kind": "unknown",
                "message": f"could not parse release URL from gh stdout: "
                           f"{create.stdout[:300]}"}
    return {"ok": True, "url": m.group(0).strip()}


def _resolve_repo(name: str) -> dict:
    """Look up SUPPORTED_REPOS by short name (`knowledge-sync`) or full
    GitHub path (`bernardTavares/knowledge-sync`).

    Returns the repo info dict ({github, clone}). Raises ValueError on
    unknown repo, with message listing supported names.
    """
    if name in SUPPORTED_REPOS:
        return SUPPORTED_REPOS[name]
    for short, info in SUPPORTED_REPOS.items():
        if info["github"] == name:
            return info
    supported = sorted(SUPPORTED_REPOS.keys())
    raise ValueError(f"unknown repo: {name}; supported: {supported}")


def cmd_release_notes(args) -> int:
    """E6/F4 wave 1 — generate release notes for a repo.

    Default: prints markdown to stdout (zero side-effect). With
    --publish-draft, additionally creates a GitHub Release draft.
    Always emits release_notes.drafted on success (even commit_count=0).
    Failure of publish emits release_notes.draft_publish_failed instead.

    Spec: bevox-knowledge/35_specs/2026-04-18-e6-f4-release-notes-wave-1.md
    """
    from datetime import datetime as _dt

    # 1. Resolve repo
    try:
        repo_info = _resolve_repo(args.repo)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    repo_short = next((s for s, info in SUPPORTED_REPOS.items()
                       if info is repo_info), args.repo)

    # 2. Resolve range
    try:
        since_ref, to_ref, since_sha, to_sha = _resolve_range(
            repo_info["clone"], args.since, args.to)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    # 3. Read git log (--no-merges per spec §2.11)
    try:
        commits = _read_git_log(repo_info["clone"], since_sha, to_sha)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    # 4. Group + parse refs + render
    groups = _group_commits(commits)
    issue_refs = _parse_issue_refs(commits)
    generated_at = _dt.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    markdown = _render_markdown(
        repo_short=repo_short,
        since_sha_short=since_sha[:7],
        to_sha_short=to_sha[:7],
        commit_count=len(commits),
        generated_at=generated_at,
        groups=groups,
        issue_refs=issue_refs,
    )

    # 5. Print markdown to stdout (always)
    print(markdown)

    # 6. Optionally publish draft
    if args.publish_draft:
        tag = args.tag or _dt.utcnow().strftime("draft-%Y-%m-%d-%H%M")
        title = f"Release notes — {repo_short} ({since_sha[:7]}..{to_sha[:7]})"
        result = _publish_draft(repo_info["github"], tag, title, markdown)
        groups_count = {k: len(v) for k, v in groups.items()}
        if result["ok"]:
            agent.emit_event(
                actor="cli", type="release_notes.drafted",
                payload={
                    "repo": repo_short,
                    "github_repo": repo_info["github"],
                    "since_ref": since_ref, "to_ref": to_ref,
                    "since_sha": since_sha, "to_sha": to_sha,
                    "commit_count": len(commits),
                    "groups": groups_count,
                    "publish": {"mode": "draft", "tag": tag,
                                "draft_url": result["url"]},
                })
            agent.rebuild_state()
            print(f"==> draft created: {result['url']}")
            print(f"==> reverter: gh release delete {tag} --yes "
                  f"--repo {repo_info['github']}")
            return 0
        else:
            agent.emit_event(
                actor="cli", type="release_notes.draft_publish_failed",
                payload={
                    "repo": repo_short,
                    "github_repo": repo_info["github"],
                    "since_ref": since_ref, "to_ref": to_ref,
                    "since_sha": since_sha, "to_sha": to_sha,
                    "commit_count": len(commits),
                    "tag": tag,
                    "error_kind": result["error_kind"],
                    "message": result["message"],
                })
            print(f"error: publish failed ({result['error_kind']}): "
                  f"{result['message']}", file=sys.stderr)
            return 1

    # 7. Stdout-only path: emit drafted with publish.mode=stdout
    groups_count = {k: len(v) for k, v in groups.items()}
    agent.emit_event(
        actor="cli", type="release_notes.drafted",
        payload={
            "repo": repo_short,
            "github_repo": repo_info["github"],
            "since_ref": since_ref, "to_ref": to_ref,
            "since_sha": since_sha, "to_sha": to_sha,
            "commit_count": len(commits),
            "groups": groups_count,
            "publish": {"mode": "stdout", "tag": None, "draft_url": None},
        })
    agent.rebuild_state()
    return 0


# ── Main dispatch ──────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="openclaw-delivery", description="Delivery operator CLI (E5 wave 1)")
    sub = p.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("activate-spec", help="Activate a spec for scanning")
    pa.add_argument("path", help="Path to spec markdown (relative to bevox-knowledge or absolute)")
    pa.set_defaults(func=cmd_activate_spec)

    par = sub.add_parser("archive-spec", help="Archive a spec; cascade expire pending proposals")
    par.add_argument("path")
    par.add_argument("--reason", required=True, choices=["delivered", "paused", "superseded", "discarded"])
    par.set_defaults(func=cmd_archive_spec)

    pssr = sub.add_parser("set-spec-repo", help="Set GitHub target repo for an active spec")
    pssr.add_argument("spec_path", help="Path to active spec (relative to bevox-knowledge or absolute)")
    pssr.add_argument("--repo", required=True, help="GitHub repo in 'owner/name' format")
    pssr.set_defaults(func=cmd_set_spec_repo)

    ps = sub.add_parser("scan", help="Run an immediate scan over active specs")
    ps.set_defaults(func=cmd_scan)

    pp = sub.add_parser("proposals", help="List proposals (default: pending)")
    pp.add_argument("--all", action="store_true", help="List all proposals regardless of state")
    pp.add_argument("--state", choices=["pending", "accepted", "rejected", "expired"], help="Filter by state")
    pp.add_argument("--json", action="store_true", help="JSON output")
    pp.set_defaults(func=cmd_proposals)

    pac = sub.add_parser("accept", help="Accept a pending proposal")
    pac.add_argument("proposal_id", help="Full or short proposal id")
    pac.add_argument("--repo", help="Override GitHub target repo (owner/name)")
    pac.set_defaults(func=cmd_accept)

    prej = sub.add_parser("reject", help="Reject a pending proposal")
    prej.add_argument("proposal_id")
    prej.add_argument("--reason", required=True)
    prej.set_defaults(func=cmd_reject)

    # E6 wave 1: github-link retry
    pgl = sub.add_parser("github-link", help="Retry GitHub linkage for an accepted task")
    pgl.add_argument("task_id", help="Full task_id (e.g. task_abc123456789)")
    pgl.add_argument("--repo", help="Override GitHub target repo (owner/name)")
    pgl.set_defaults(func=cmd_github_link)

    pst = sub.add_parser("status", help="Show summary status")
    pst.set_defaults(func=cmd_status)

    prb = sub.add_parser("rebuild-state", help="Regenerate state.json from events.jsonl (idempotent)")
    prb.set_defaults(func=cmd_rebuild_state)

    prn = sub.add_parser("release-notes",
                         help="Generate release notes for a repo "
                              "(stdout default; --publish-draft to create GH Release draft)")
    prn.add_argument("repo", help="Repo name (short or owner/name); see SUPPORTED_REPOS")
    prn.add_argument("--since", default=None,
                     help="Git ref start of range (exclusive); default: last tag")
    prn.add_argument("--to", default=None,
                     help="Git ref end of range (inclusive); default: HEAD")
    prn.add_argument("--publish-draft", dest="publish_draft", action="store_true",
                     help="Create GitHub Release draft (always draft, never published)")
    prn.add_argument("--tag", default=None,
                     help="Tag name for draft (default: draft-YYYY-MM-DD-HHMM)")
    prn.set_defaults(func=cmd_release_notes)

    pv = sub.add_parser("version", help="Print version")
    pv.set_defaults(func=lambda a: (print(agent.VERSION) or 0))

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
