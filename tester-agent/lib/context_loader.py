"""Context loader: le execution log (tail) + files_relevant + expected_outputs + spec_refs.

Read-only filesystem. Mesmo pattern do clarification-agent context_loader,
mas adicionado read do execution log do dispatcher.
"""

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

BEVOX_KNOWLEDGE = Path(f"{Path.home()}/bevox-knowledge")
OPENCLAW_PLANS = Path(f"{Path.home()}/.openclaw/docs/superpowers/plans")
KANBAN_CLI = Path(f"{Path.home()}/.openclaw/kanban-tasks/cli.sh")
DISPATCHER_EXEC_DIR = Path(f"{Path.home()}/.openclaw/dispatcher-agent/executions")

LOG_TAIL_BYTES = 8000
FILE_HEAD_BYTES = 4000
SPEC_HEAD_BYTES = 2000


class ContextError(Exception):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def load_task_via_kanban(task_id: str) -> Dict[str, Any]:
    try:
        r = subprocess.run(
            [str(KANBAN_CLI), "task", "show", task_id, "--json"],
            capture_output=True, text=True, check=False, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise ContextError("KANBAN_CLI_TIMEOUT", str(e))
    if r.returncode != 0:
        raise ContextError(
            "TASK_NOT_FOUND",
            f"{task_id}: exit={r.returncode} stderr={r.stderr.strip()[:200]}",
        )
    data = json.loads(r.stdout)
    return data.get("task") or {}


def execution_log_path(task_id: str) -> Path:
    return DISPATCHER_EXEC_DIR / f"{task_id}.log"


def read_execution_log_tail(task_id: str, max_bytes: int = LOG_TAIL_BYTES) -> str:
    """Le tail do execution log (max_bytes bytes finais)."""
    path = execution_log_path(task_id)
    if not path.exists() or not path.is_file():
        return ""
    try:
        size = path.stat().st_size
        with open(path, "rb") as f:
            if size > max_bytes:
                f.seek(size - max_bytes)
            data = f.read()
        return data.decode("utf-8", errors="replace")
    except OSError:
        return ""


def resolve_ref_path(ref: str) -> Optional[Path]:
    """Resolve path ref (absolute, ~, ou prefixed). Mesma logica clarification-agent."""
    r = ref.strip().strip("`")
    if r.startswith("~/"):
        p = Path(r).expanduser()
        return p if p.exists() else None
    if r.startswith("/"):
        p = Path(r)
        return p if p.exists() else None
    HOME = Path.home()
    if r.startswith("bevox-knowledge/"):
        p = HOME / r
        return p if p.exists() else None
    if r.startswith(".openclaw/") or r.startswith("openclaw/"):
        p = (HOME / r if r.startswith(".openclaw/")
             else HOME / ".openclaw" / r[len("openclaw/"):])
        return p if p.exists() else None
    for base in (BEVOX_KNOWLEDGE, OPENCLAW_PLANS, HOME / ".openclaw"):
        cand = base / r
        if cand.exists():
            return cand
    return None


def read_ref(ref: str, max_bytes: int = FILE_HEAD_BYTES) -> Optional[Dict[str, Any]]:
    path = resolve_ref_path(ref)
    if path is None or not path.is_file():
        return None
    try:
        content = path.read_text(encoding="utf-8", errors="replace")[:max_bytes]
    except OSError:
        return None
    return {
        "ref": ref, "path": str(path), "content": content,
        "truncated": len(content) >= max_bytes,
    }


def _resolve_project_path(project_slug: Optional[str]) -> Optional[str]:
    """Resolve local repo path for a project slug.

    Checks projects-meta.json:projects.<slug>.local_repo_path; if absent,
    falls back to ~/code/<slug> convention. Returns None if
    project_slug is None (task without project).
    """
    if not project_slug:
        return None
    meta_path = Path.home() / ".openclaw" / "projects-meta.json"
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        entry = (meta.get("projects") or {}).get(project_slug) or {}
        if isinstance(entry, dict):
            path = entry.get("local_repo_path")
            if path:
                return os.path.expanduser(path)
    except (OSError, json.JSONDecodeError):
        pass
    # Fallback convention
    return f"{Path.home()}/code/{project_slug}"


def build_test_context(task_id: str) -> Dict[str, Any]:
    """Bundle: task + execution log tail + files_relevant/expected_outputs + spec_refs."""
    task = load_task_via_kanban(task_id)
    payload = task.get("dispatch_payload") or {}

    # Load evidence via jsonl (session) or fallback to execution log
    session_id = payload.get("execution_session_id")
    project_slug = task.get("project")
    project_path = _resolve_project_path(project_slug)
    evidence = load_evidence(task_id, session_id, project_path)
    log_tail = evidence.get("execution_log_tail", "")

    files_relevant_resolved: List[Dict[str, Any]] = []
    files_relevant_unresolved: List[str] = []
    seen_paths = set()
    combined_refs = list(payload.get("files_relevant") or []) + list(payload.get("expected_outputs") or [])
    for f in combined_refs:
        result = read_ref(f, max_bytes=FILE_HEAD_BYTES)
        if result:
            path = result.get("path")
            if path in seen_paths:
                continue
            seen_paths.add(path)
            files_relevant_resolved.append(result)
        else:
            if f not in files_relevant_unresolved:
                files_relevant_unresolved.append(f)

    spec_refs_resolved: List[Dict[str, Any]] = []
    for r in (payload.get("spec_refs") or []):
        result = read_ref(r, max_bytes=SPEC_HEAD_BYTES)
        if result:
            spec_refs_resolved.append(result)

    return {
        "task": task,
        "dispatch_payload": payload,
        "acceptance_criteria": payload.get("acceptance_criteria") or [],
        "execution_log_tail": log_tail,
        "execution_log_path": str(execution_log_path(task_id)),
        "files_relevant": files_relevant_resolved,
        "files_relevant_unresolved": files_relevant_unresolved,
        "expected_outputs": payload.get("expected_outputs") or [],
        "spec_refs": spec_refs_resolved,
        "evidence_source": evidence.get("evidence_source"),
        "evidence": evidence,
    }


def claude_project_dir(project_path: str) -> str:
    """Encode local project path to Claude CLI's project dir naming.

    Example: '~/code/bevox-site' → '-home-alice-code-bevox-site' (for HOME=/home/alice)

    Claude CLI stores per-project sessions in
    ~/.claude/projects/<encoded_path>/<session_id>.jsonl, where <encoded_path>
    is the absolute path with '/' replaced by '-' and trailing slash stripped.
    """
    expanded = os.path.expanduser(project_path or "/")
    encoded = expanded.replace("/", "-").rstrip("-")
    if not encoded:
        encoded = "-"
    return encoded


def _claude_projects_root() -> Path:
    """Return ~/.claude/projects (overridable in tests via patch)."""
    return Path.home() / ".claude" / "projects"


def load_session_evidence(session_id: str,
                          project_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Load Claude session jsonl as evidence dict.

    Reads ~/.claude/projects/<encoded_project_path>/<session_id>.jsonl (full file).
    Tolerates corrupt lines by skipping them. Returns None if file missing,
    completely unparseable, or no valid jsonl entries.

    Returns dict with:
      session_id: str
      model: str | None  (from last assistant message)
      started_at: str | None (timestamp of first message)
      finished_at: str | None (timestamp of last message)
      final_assistant_text: str (concatenated text-type content of last assistant msg)
      tool_uses: list[dict] (all tool_use entries from assistant messages)
      tool_results: list[dict] (all tool_result entries)
      files_touched: list[str] (file_path from Write/Edit tool_use entries)
      raw_lines_count: int (total lines processed, including skipped corrupt)
      source: "jsonl"
    """
    if not session_id:
        return None
    project = project_path or str(Path.home())
    proj_dir = _claude_projects_root() / claude_project_dir(project)
    session_path = proj_dir / f"{session_id}.jsonl"
    if not session_path.is_file():
        return None
    try:
        with open(session_path, "r", encoding="utf-8") as f:
            raw_lines = f.readlines()
    except OSError:
        return None

    parsed = []
    raw_lines_count = len(raw_lines)
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        try:
            parsed.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if not parsed:
        return None

    final_assistant = None
    tool_uses: List[Dict[str, Any]] = []
    tool_results: List[Dict[str, Any]] = []
    files_touched: List[str] = []
    started_at = None
    finished_at = None

    for entry in parsed:
        ts = entry.get("timestamp")
        if ts and started_at is None:
            started_at = ts
        if ts:
            finished_at = ts
        msg = entry.get("message") or {}
        role = msg.get("role")
        content = msg.get("content") or []
        if not isinstance(content, list):
            continue
        for c in content:
            if not isinstance(c, dict):
                continue
            t = c.get("type")
            if t == "tool_use" and role == "assistant":
                tool_uses.append(c)
                name = c.get("name")
                if name in ("Write", "Edit", "NotebookEdit"):
                    inp = c.get("input") or {}
                    fp = inp.get("notebook_path") if name == "NotebookEdit" else inp.get("file_path")
                    if fp and fp not in files_touched:
                        files_touched.append(fp)
            elif t == "tool_result":
                tool_results.append(c)
        if role == "assistant":
            final_assistant = entry

    final_text = ""
    final_model = None
    if final_assistant:
        msg = final_assistant.get("message") or {}
        final_model = msg.get("model")
        for c in (msg.get("content") or []):
            if isinstance(c, dict) and c.get("type") == "text":
                final_text += c.get("text", "")

    return {
        "session_id": session_id,
        "model": final_model,
        "started_at": started_at,
        "finished_at": finished_at,
        "final_assistant_text": final_text,
        "tool_uses": tool_uses,
        "tool_results": tool_results,
        "files_touched": files_touched,
        "raw_lines_count": raw_lines_count,
        "source": "jsonl",
    }


def load_evidence(task_id: str,
                  session_id: Optional[str] = None,
                  project_path: Optional[str] = None) -> Dict[str, Any]:
    """Load best-available evidence for a task.

    Tries load_session_evidence first (canonical jsonl). Falls back to
    read_execution_log_tail (legacy execution.log) if jsonl missing/empty.

    Always returns a dict with field `evidence_source`:
      - "jsonl" when load_session_evidence succeeded
      - "execution_log_fallback" otherwise

    On fallback, dict carries execution_log_tail (text) instead of
    final_assistant_text/tool_uses/files_touched.
    """
    if session_id:
        evidence = load_session_evidence(session_id, project_path)
        if evidence is not None:
            evidence["evidence_source"] = "jsonl"
            evidence["task_id"] = task_id
            return evidence

    # Fallback: execution log tail (legacy fonte fraca)
    log_tail = read_execution_log_tail(task_id)
    return {
        "task_id": task_id,
        "session_id": session_id,
        "evidence_source": "execution_log_fallback",
        "execution_log_tail": log_tail,
        "execution_log_path": str(execution_log_path(task_id)),
        # legacy compat fields (empty)
        "final_assistant_text": "",
        "tool_uses": [],
        "tool_results": [],
        "files_touched": [],
    }
