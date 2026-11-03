"""Context loader: le dispatch_payload + spec_refs + plan_ref + ADRs."""

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

BEVOX_KNOWLEDGE = Path(f"{Path.home()}/bevox-knowledge")
OPENCLAW_PLANS = Path(f"{Path.home()}/.openclaw/docs/superpowers/plans")
KANBAN_CLI = Path(f"{Path.home()}/.openclaw/kanban-tasks/cli.sh")


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
        raise ContextError("KANBAN_CLI_TIMEOUT", f"{e}")
    if r.returncode != 0:
        raise ContextError(
            "TASK_NOT_FOUND",
            f"{task_id}: exit={r.returncode} stderr={r.stderr.strip()[:200]}",
        )
    data = json.loads(r.stdout)
    return data.get("task") or {}


def resolve_ref_path(ref: str) -> Optional[Path]:
    r = ref.strip().strip("`")
    if r.startswith("~/"):
        p = Path(r).expanduser()
        return p if p.exists() else None
    if r.startswith("/"):
        p = Path(r)
        return p if p.exists() else None
    # Refs prefixadas (relative): resolve em ~
    HOME = Path.home()
    if r.startswith("bevox-knowledge/"):
        p = HOME / r
        return p if p.exists() else None
    if r.startswith(".openclaw/") or r.startswith("openclaw/"):
        p = HOME / r if r.startswith(".openclaw/") else HOME / ".openclaw" / r[len("openclaw/"):]
        return p if p.exists() else None
    # Fallback: tenta as bases conhecidas
    for base in (BEVOX_KNOWLEDGE, OPENCLAW_PLANS, HOME / ".openclaw"):
        cand = base / r
        if cand.exists():
            return cand
    return None


def read_ref(ref: str, max_bytes: int = 20_000) -> Optional[Dict[str, Any]]:
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


def extract_adrs_from_content(content: str) -> List[str]:
    # ADRs vivem em subpastas (ADR-010 wave-4): 30_adr/<_shared|bevox-*|company-os|openclaw>/ADR-N-*.md
    # Regex aceita opcionalmente 1 nível de subpasta antes de ADR-N-*.md (preserva backwards-compat
    # com refs históricas que apontam para o layout flat pré-wave-4).
    pat = re.compile(r"(bevox-knowledge/30_adr/(?:[\w-]+/)?ADR-\d+-[\w-]+\.md)")
    return list(dict.fromkeys(pat.findall(content)))


def build_context_bundle(task_id: str) -> Dict[str, Any]:
    task = load_task_via_kanban(task_id)
    payload = task.get("dispatch_payload") or {}
    spec_refs = payload.get("spec_refs") or []
    plan_ref = payload.get("plan_ref")

    read_refs: List[Dict[str, Any]] = []
    for r in spec_refs:
        result = read_ref(r)
        if result:
            read_refs.append(result)
    if plan_ref:
        result = read_ref(plan_ref)
        if result:
            read_refs.append(result)

    adr_refs_seen: List[str] = []
    for r in read_refs:
        for adr in extract_adrs_from_content(r["content"]):
            if adr not in adr_refs_seen:
                adr_refs_seen.append(adr)
    for adr_ref in adr_refs_seen:
        result = read_ref(adr_ref)
        if result:
            read_refs.append(result)

    return {
        "task": task,
        "dispatch_payload": payload,
        "read_refs": read_refs,
        "resolved_count": len(read_refs),
        "unresolved_refs": [
            r for r in spec_refs + ([plan_ref] if plan_ref else [])
            if resolve_ref_path(r) is None
        ],
    }
