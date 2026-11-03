#!/usr/bin/env python3
"""
E5 wave 1 — Delivery Agent.

Reads active specs from the operational state, parses Tarefas/Tasks/Plan
sections, and emits task.proposed events for new items.

Spec: bevox-knowledge/35_specs/2026-04-13-e5-roadmap-delivery-os-wave-1.md

Stdlib only. Single file. Runs via systemd timer or `openclaw-delivery scan`.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import logging
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

# ── Paths ──────────────────────────────────────────────────────────

HOME = Path.home()
DELIVERY_DIR = HOME / ".openclaw" / "delivery"
EVENTS_PATH = DELIVERY_DIR / "events.jsonl"
STATE_PATH = DELIVERY_DIR / "state.json"
KNOWLEDGE_DIR = HOME / "bevox-knowledge"

VERSION = "0.1.0-wave1"

# ── Event schema ───────────────────────────────────────────────────


class ActorError(ValueError):
    """Raised when an actor is not allowed to emit a given event type."""


# Allowed (actor, type) combinations. Closed enum.
ACTOR_TYPE_MATRIX: dict[str, set[str]] = {
    "cli": {
        # E5 wave 1 (5 types)
        "spec.activated",
        "spec.archived",
        "task.created",
        "task.rejected",
        "proposal.expired",
        # E6 wave 1 (3 types)
        "spec.github_repo_set",
        "task.github_linked",
        "task.github_link_failed",
        # E6/F4 wave 1 (2 types)
        "release_notes.drafted",
        "release_notes.draft_publish_failed",
    },
    "delivery-agent": {
        "scan.run",
        "task.proposed",
    },
}


def validate_actor(actor: str, type: str) -> None:
    """Raise ActorError if (actor, type) is not in the allowed matrix."""
    if actor not in ACTOR_TYPE_MATRIX:
        raise ActorError(f"unknown actor: {actor!r}")
    if type not in ACTOR_TYPE_MATRIX[actor]:
        raise ActorError(f"actor {actor!r} cannot emit event type {type!r}")


def now_iso_utc() -> str:
    """Return current UTC time as ISO 8601 string ending in Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now(timezone.utc).microsecond // 1000:03d}Z"


def make_event(*, actor: str, type: str, payload: dict) -> dict:
    """Build an event envelope. Validates actor."""
    validate_actor(actor, type)
    return {
        "ts": now_iso_utc(),
        "event_id": f"evt_{uuid.uuid4().hex}",
        "actor": actor,
        "type": type,
        "payload": payload,
    }


def emit_event_to(path: Path, *, actor: str, type: str, payload: dict) -> dict:
    """Append an event to the JSONL file at `path`. Validates actor.

    Uses fcntl.flock for advisory locking. Returns the written event.
    """
    evt = make_event(actor=actor, type=type, payload=payload)
    line = json.dumps(evt, separators=(",", ":")) + "\n"
    with open(path, "a", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(line)
            f.flush()
            try:
                import os
                os.fsync(f.fileno())
            except OSError:
                pass
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    return evt


def emit_event(actor: str, type: str, payload: dict) -> dict:
    """Convenience: emit to the default events.jsonl path."""
    return emit_event_to(EVENTS_PATH, actor=actor, type=type, payload=payload)


def iter_events(path: Path) -> Iterator[dict]:
    """Yield each event from the JSONL file in order. Skips corrupted lines."""
    if not path.exists():
        return
    with open(path, "r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                yield json.loads(raw)
            except json.JSONDecodeError:
                logging.warning("skipping corrupted event line %d in %s", lineno, path)
                continue


# ── Projection (state.json) ────────────────────────────────────────

import os

SCHEMA_VERSION = 1


def _empty_state() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_iso_utc(),
        "from_event_id": None,
        "active_specs": {},
        "proposals": {},
        "last_scan": None,
        "release_notes": {},  # NEW (E6/F4): {repo_short: [entry, ...]}, bound 20
    }


_RELEASE_NOTES_BOUND = 20


def project_state(events_path: Path) -> dict:
    """Replay all events in the JSONL into a state dict."""
    state = _empty_state()

    for evt in iter_events(events_path):
        state["from_event_id"] = evt["event_id"]
        t = evt["type"]
        p = evt["payload"]
        ts = evt["ts"]

        if t == "spec.activated":
            state["active_specs"][p["spec_path"]] = {
                "activated_at": ts,
                "activated_by_event": evt["event_id"],
                "github_repo": None,  # NEW (E6) — set by spec.github_repo_set
            }

        elif t == "spec.archived":
            state["active_specs"].pop(p["spec_path"], None)

        elif t == "task.proposed":
            state["proposals"][p["proposal_id"]] = {
                "key": p["key"],
                "spec_path": p["spec_path"],
                "section_id": p["section_id"],
                "item_text": p["item_text"],
                "state": "pending",
                "proposed_at": ts,
                "resolved_at": None,
                "resolved_reason": None,
                "task_id": None,
                "github_link": None,  # NEW (E6)
            }

        elif t == "task.created":
            pid = p["proposal_id"]
            if pid in state["proposals"]:
                state["proposals"][pid]["state"] = "accepted"
                state["proposals"][pid]["resolved_at"] = ts
                state["proposals"][pid]["task_id"] = p["task_id"]

        elif t == "task.rejected":
            pid = p["proposal_id"]
            if pid in state["proposals"]:
                state["proposals"][pid]["state"] = "rejected"
                state["proposals"][pid]["resolved_at"] = ts
                state["proposals"][pid]["resolved_reason"] = p.get("reason")

        elif t == "proposal.expired":
            pid = p["proposal_id"]
            if pid in state["proposals"]:
                state["proposals"][pid]["state"] = "expired"
                state["proposals"][pid]["resolved_at"] = ts
                state["proposals"][pid]["resolved_reason"] = p.get("reason", "spec_archived")

        elif t == "scan.run":
            state["last_scan"] = {
                "run_id": p["run_id"],
                "finished_at": p.get("finished_at"),
                "specs_scanned": len(p.get("specs_scanned", [])),
                "proposals_emitted": p.get("proposals_emitted", 0),
            }

        elif t == "spec.github_repo_set":
            spec_path = p["spec_path"]
            if spec_path in state["active_specs"]:
                state["active_specs"][spec_path]["github_repo"] = p["repo"]

        elif t == "task.github_linked":
            task_id = p["task_id"]
            # Find proposal by task_id (reverse lookup)
            for pid, pdata in state["proposals"].items():
                if pdata.get("task_id") == task_id:
                    pdata["github_link"] = {
                        "state": "linked",
                        "repo": p["repo"],
                        "issue_number": p["issue_number"],
                        "issue_url": p["issue_url"],
                        "error_kind": None,
                        "message": None,
                        "last_attempt_at": ts,
                        "last_attempt_event": evt["event_id"],
                    }
                    break

        elif t == "task.github_link_failed":
            task_id = p["task_id"]
            for pid, pdata in state["proposals"].items():
                if pdata.get("task_id") == task_id:
                    pdata["github_link"] = {
                        "state": "failed",
                        "repo": p.get("repo"),  # can be None for repo_unresolved
                        "issue_number": None,
                        "issue_url": None,
                        "error_kind": p["error_kind"],
                        "message": p.get("message", ""),
                        "last_attempt_at": ts,
                        "last_attempt_event": evt["event_id"],
                    }
                    break
        elif t == "release_notes.drafted":
            repo_short = p["repo"]
            entry = {
                "ts": ts,
                "since_ref": p["since_ref"],
                "to_ref": p["to_ref"],
                "since_sha": p["since_sha"],
                "to_sha": p["to_sha"],
                "commit_count": p["commit_count"],
                "publish_mode": p["publish"]["mode"],
                "tag": p["publish"].get("tag"),
                "draft_url": p["publish"].get("draft_url"),
            }
            bucket = state["release_notes"].setdefault(repo_short, [])
            bucket.insert(0, entry)
            del bucket[_RELEASE_NOTES_BOUND:]

        # release_notes.draft_publish_failed is intentionally NOT projected
        # (audit-only; visible in events.jsonl per spec §5.2).

        # unknown types are ignored (forward-compat)

    return state


def read_state(state_path: Optional[Path] = None) -> dict:
    """Read state.json from disk. Returns empty state if missing/empty.

    Uses module-level STATE_PATH when state_path is None. This indirection
    (instead of `state_path: Path = STATE_PATH`) is required so that
    `mock.patch.object(agent, "STATE_PATH", ...)` actually takes effect —
    otherwise Python captures the default at function definition time and
    the patch becomes a no-op.
    """
    if state_path is None:
        state_path = STATE_PATH
    if not state_path.exists() or state_path.stat().st_size == 0:
        return _empty_state()
    try:
        return json.loads(state_path.read_text())
    except json.JSONDecodeError:
        logging.warning("state.json corrupted; returning empty state")
        return _empty_state()


def write_state_atomic(state: dict, state_path: Optional[Path] = None) -> None:
    """Atomically write state.json via tempfile + rename.

    Uses module-level STATE_PATH when state_path is None (see read_state).
    """
    if state_path is None:
        state_path = STATE_PATH
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = state_path.with_suffix(state_path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    os.replace(tmp, state_path)


def rebuild_state(
    events_path: Optional[Path] = None,
    state_path: Optional[Path] = None,
) -> dict:
    """Rebuild state.json from scratch by replaying all events. Idempotent.

    Reads events.jsonl, projects to state, writes state.json atomically.
    Never mutates events.jsonl.

    Uses module-level EVENTS_PATH / STATE_PATH when args are None (see
    read_state for why indirection matters for mock.patch).
    """
    if events_path is None:
        events_path = EVENTS_PATH
    if state_path is None:
        state_path = STATE_PATH
    state = project_state(events_path)
    write_state_atomic(state, state_path)
    return state


# ── Spec parser ────────────────────────────────────────────────────

import hashlib
import re

# Headings (level 2 = `## `) whose names mark a section we want to parse.
# Match is case-insensitive against the heading text after numbering.
TASK_SECTION_NAMES: set[str] = {"tarefas", "tasks", "plan"}

# Match a bullet list item: "- text", "* text", "- [ ] text", "- [x] text"
BULLET_RE = re.compile(r"^\s*[-*]\s+(?:\[[ xX]\]\s+)?(.+?)\s*$")

# Match a level-2 heading: "## 1. Tarefas" or "## Tarefas"
H2_RE = re.compile(r"^##\s+(?:\d+(?:\.\d+)*\.?\s+)?(.+?)\s*$")

# Match higher-level headings (level 1 or 3+) that close section context
ANY_H_RE = re.compile(r"^(#+)\s+")


def normalize_text(text: str) -> str:
    """Lowercase + collapse whitespace + strip leading bullet/checkbox markup.

    Idempotent.
    """
    s = text
    # Strip leading bullet + optional checkbox
    bm = BULLET_RE.match(s)
    if bm:
        s = bm.group(1)
    # Lowercase
    s = s.lower()
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


def compute_key(spec_path: str, section_id: str, item_text: str) -> str:
    """Stable key for a work item. sha256 of normalized inputs, truncated to 16 hex chars."""
    norm = normalize_text(item_text)
    seed = f"{spec_path}::{section_id}::{norm}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def parse_spec(path: Path) -> list[dict]:
    """Parse a markdown spec and return work items from Tarefas/Tasks/Plan sections.

    Returns a list of dicts: [{spec_path, section_id, item_text}, ...]
    Returns empty list if file missing or unreadable.
    """
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []

    items: list[dict] = []
    current_section: Optional[str] = None
    spec_path_str = str(path)

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        # Detect any heading
        h_match = ANY_H_RE.match(line)
        if h_match:
            level = len(h_match.group(1))
            if level == 2:
                # Level-2 heading: check if it's a task section
                h2 = H2_RE.match(line)
                if h2:
                    name = h2.group(1).strip().lower()
                    if name in TASK_SECTION_NAMES:
                        # Preserve original casing for section_id (canonical form)
                        for canonical in ("Tarefas", "Tasks", "Plan"):
                            if canonical.lower() == name:
                                current_section = canonical
                                break
                    else:
                        current_section = None
            else:
                # Any other heading level closes section context if level <= 2
                if level <= 2:
                    current_section = None
            continue

        if current_section is None:
            continue

        # Inside a task section: look for bullet items
        bm = BULLET_RE.match(line)
        if bm:
            item_text = bm.group(1).strip()
            if item_text:
                items.append({
                    "spec_path": spec_path_str,
                    "section_id": current_section,
                    "item_text": item_text,
                })

    return items


# ── Scan / gap detection ───────────────────────────────────────────


def scan_active_specs(state: dict) -> list[dict]:
    """Pure function: given current state, return list of NEW proposals to emit.

    Each item: {key, spec_path, section_id, item_text}.
    Does NOT emit events itself; caller does that. This keeps the function
    deterministic and testable.
    """
    # Build set of keys already known in state (any state)
    known_keys: set[str] = {p["key"] for p in state.get("proposals", {}).values()}

    new_proposals: list[dict] = []

    for spec_path_str in state.get("active_specs", {}).keys():
        items = parse_spec(Path(spec_path_str))
        for item in items:
            key = compute_key(item["spec_path"], item["section_id"], item["item_text"])
            if key in known_keys:
                continue
            new_proposals.append({
                "key": key,
                "spec_path": item["spec_path"],
                "section_id": item["section_id"],
                "item_text": item["item_text"],
            })
            known_keys.add(key)  # in-scan dedupe too

    return new_proposals


def run_scan() -> dict:
    """Full scan workflow: load state, find new proposals, emit events, rebuild state.

    Returns a summary dict: {run_id, proposals_emitted, specs_scanned}.
    """
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    started_at = now_iso_utc()

    state = read_state()
    active_paths = list(state.get("active_specs", {}).keys())
    new_proposals = scan_active_specs(state)

    for p in new_proposals:
        proposal_id = f"prop_{uuid.uuid4().hex[:12]}"
        emit_event(
            actor="delivery-agent",
            type="task.proposed",
            payload={
                "proposal_id": proposal_id,
                "key": p["key"],
                "spec_path": p["spec_path"],
                "section_id": p["section_id"],
                "item_text": p["item_text"],
                "run_id": run_id,
            },
        )

    finished_at = now_iso_utc()
    emit_event(
        actor="delivery-agent",
        type="scan.run",
        payload={
            "run_id": run_id,
            "started_at": started_at,
            "finished_at": finished_at,
            "specs_scanned": active_paths,
            "proposals_emitted": len(new_proposals),
            "parser_skips": [],
        },
    )

    # Refresh projection so subsequent reads see the changes
    rebuild_state()

    return {
        "run_id": run_id,
        "proposals_emitted": len(new_proposals),
        "specs_scanned": len(active_paths),
    }


# ── GitHub integration helpers (E6 wave 1) ─────────────────────────

KNOWLEDGE_NAMESPACES: set[str] = {
    "00_inbox",
    "10_prd",
    "20_architecture",
    "30_adr",
    "35_specs",
    "40_roadmap",
    "50_releases",
    "60_customer-feedback",
    "70_metrics",
    "99_templates",
}
KNOWLEDGE_REPO: str = "bernardTavares/bevox-knowledge"

GH_TIMEOUT_SEC: int = 10
DELIVERY_LABEL_NAME: str = "delivery"
DELIVERY_LABEL_COLOR: str = "6f42c1"
DELIVERY_LABEL_DESC: str = "Auto-created by OpenClaw Delivery"


def build_issue_title(item_text: str) -> str:
    """Trunca item_text a 80 chars, adicionando '…' se > 80."""
    if len(item_text) <= 80:
        return item_text
    return item_text[:79] + "…"


def resolve_spec_link(spec_path: str) -> str:
    """Retorna markdown link se spec_path começa com namespace canônico do
    bevox-knowledge; caso contrário, retorna o spec_path raw.

    Invariante importante: o link sempre aponta para o bevox-knowledge,
    independentemente do repo alvo da issue (Q5 ajuste).
    """
    if "/" not in spec_path:
        return spec_path
    top_level = spec_path.split("/", 1)[0]
    if top_level not in KNOWLEDGE_NAMESPACES:
        return spec_path
    url = f"https://github.com/{KNOWLEDGE_REPO}/blob/main/{spec_path}"
    return f"[{spec_path}]({url})"


def build_issue_body(proposal_data: dict) -> str:
    """Monta markdown determinista do body da issue.

    Input `proposal_data` deve conter:
      spec_path, section_id, item_text,
      proposal_id, task_id, key,
      proposed_at, resolved_at
    """
    spec_link = resolve_spec_link(proposal_data["spec_path"])
    return f"""> Auto-created by OpenClaw Delivery via GitHub Operations (E6 wave 1) on {proposal_data['resolved_at']}.

**Spec:** {spec_link}
**Section:** {proposal_data['section_id']}
**Item:** {proposal_data['item_text']}

---

**Delivery metadata:**

| Field | Value |
|---|---|
| Task ID | `{proposal_data['task_id']}` |
| Proposal ID | `{proposal_data['proposal_id']}` |
| Key | `{proposal_data['key']}` |
| Proposed at | {proposal_data['proposed_at']} |
| Accepted at | {proposal_data['resolved_at']} |

<sub>Managed locally in `~/.openclaw/delivery/events.jsonl`. GitHub is operational reflex — local is source of truth.</sub>
"""


def parse_gh_error(
    returncode: Optional[int],
    stdout: str,
    stderr: str,
    exception: Optional[BaseException] = None,
) -> tuple[str, str]:
    """Mapeia resultado de subprocess.run(["gh", ...]) para (error_kind, message).

    error_kind: um dos 8 valores do enum fechado da spec §5.3.
    message: stderr (ou repr da exception) truncado a 500 chars.

    Raises ValueError se chamado em caso de sucesso (returncode == 0, sem exception).
    """
    # Success case should not call this function
    if exception is None and returncode == 0:
        raise ValueError("parse_gh_error called on successful subprocess result")

    # Map exception cases first
    if exception is not None:
        if isinstance(exception, FileNotFoundError):
            return ("gh_not_installed", str(exception)[:500])
        if isinstance(exception, subprocess.TimeoutExpired):
            return ("network_timeout", f"gh: timeout after {exception.timeout}s"[:500])
        # Any other exception type
        return ("unknown", repr(exception)[:500])

    # Map stderr content (returncode != 0)
    stderr_lower = stderr.lower()
    msg = stderr[:500] if stderr else f"gh exited with code {returncode}"

    if "http 401" in stderr_lower or "bad credentials" in stderr_lower or "http 403" in stderr_lower:
        return ("gh_auth", msg)
    if "http 404" in stderr_lower or "could not resolve to a repository" in stderr_lower:
        return ("repo_not_found", msg)
    if "http 429" in stderr_lower or "rate limit" in stderr_lower or "abuse detection" in stderr_lower:
        return ("rate_limit", msg)

    return ("gh_exit_nonzero", msg)


def ensure_delivery_label(repo: str) -> bool:
    """Best-effort: garantir que a label 'delivery' existe em `repo`.

    Contrato (spec §5.6):
    - Retorna True se a label existe depois da chamada (já existia OU foi
      criada agora).
    - Retorna False em qualquer outro caso.
    - NUNCA levanta exceção — qualquer erro vira False.
    - Não emite eventos. Não altera state.json. Helper puramente local.
    """
    # Step 1: check if label already exists
    try:
        result = subprocess.run(
            ["gh", "label", "list", "-R", repo, "--json", "name"],
            capture_output=True, text=True, timeout=GH_TIMEOUT_SEC,
        )
        if result.returncode != 0:
            return False
        labels = json.loads(result.stdout)
        if any(l.get("name") == DELIVERY_LABEL_NAME for l in labels):
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return False
    except Exception:
        return False

    # Step 2: label missing, try to create
    try:
        result = subprocess.run(
            [
                "gh", "label", "create", DELIVERY_LABEL_NAME,
                "--color", DELIVERY_LABEL_COLOR,
                "--description", DELIVERY_LABEL_DESC,
                "-R", repo,
            ],
            capture_output=True, text=True, timeout=GH_TIMEOUT_SEC,
        )
        return result.returncode == 0
    except Exception:
        return False


class GithubIssueError(Exception):
    """Raised by create_github_issue when gh invocation fails.

    Carries (error_kind, message) already mapped for task.github_link_failed event.
    """
    def __init__(self, error_kind: str, message: str):
        self.error_kind = error_kind
        self.message = message
        super().__init__(f"{error_kind}: {message}")


_ISSUE_URL_RE = re.compile(
    r"https://github\.com/[^/]+/[^/]+/issues/(\d+)"
)


def create_github_issue(
    repo: str,
    title: str,
    body: str,
    with_label: bool,
) -> dict:
    """Invoca `gh issue create` para criar uma issue no repo alvo.

    Args:
        repo: "owner/name"
        title: título já buildado (< 80 chars)
        body: body markdown já buildado
        with_label: se True, inclui --label delivery

    Returns:
        {'issue_number': int, 'issue_url': str}

    Raises:
        GithubIssueError(error_kind, message) em qualquer falha.
    """
    args = [
        "gh", "issue", "create",
        "--repo", repo,
        "--title", title,
        "--body", body,
    ]
    if with_label:
        args.extend(["--label", DELIVERY_LABEL_NAME])

    try:
        result = subprocess.run(
            args,
            capture_output=True, text=True, timeout=GH_TIMEOUT_SEC,
        )
    except Exception as e:
        error_kind, message = parse_gh_error(
            returncode=None, stdout="", stderr="", exception=e
        )
        raise GithubIssueError(error_kind, message)

    if result.returncode != 0:
        error_kind, message = parse_gh_error(
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )
        raise GithubIssueError(error_kind, message)

    # Parse issue URL from stdout
    stdout_stripped = result.stdout.strip()
    match = _ISSUE_URL_RE.search(stdout_stripped)
    if not match:
        raise GithubIssueError(
            "unknown",
            f"could not parse issue URL from gh output: {stdout_stripped[:200]}"
        )
    issue_number = int(match.group(1))
    issue_url = stdout_stripped.split("\n")[0].strip()  # first line = URL
    return {"issue_number": issue_number, "issue_url": issue_url}


def main() -> int:
    p = argparse.ArgumentParser(prog="agent.py", description="Delivery Agent scan entry-point")
    p.add_argument("--scan", action="store_true", help="Run a scan over active specs")
    p.add_argument("--version", action="store_true", help="Print version and exit")
    args = p.parse_args()

    if args.version:
        print(VERSION)
        return 0
    if args.scan:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
        log = logging.getLogger("delivery-agent")
        try:
            summary = run_scan()
            log.info("scan complete: run_id=%s specs=%d proposals=%d",
                     summary["run_id"], summary["specs_scanned"], summary["proposals_emitted"])
            return 0
        except Exception as e:
            log.exception("scan failed: %s", e)
            return 1
    p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
