"""Storage para proposal files: atomic write, glob, load.

Responsabilidade unica desta wave: I/O puro dos proposals em
~/.openclaw/scrum-master-agent/proposals/. NAO fala com plan, NAO
fala com kanban, NAO parseia conteudo. Parser/proposer/materializer
vivem em lib/ proprios (Phases 3/5/7).
"""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(os.path.expanduser("~/.openclaw/scrum-master-agent"))
PROPOSALS_DIR = ROOT / "proposals"


def now_iso() -> str:
    """UTC ISO8601 com Z suffix, segundos precision (match kanban convention)."""
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _atomic_write(path: Path, content: str) -> None:
    """tmpfile + os.rename (atomic em POSIX)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.rename(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write_proposal(proposal: Dict[str, Any]) -> Path:
    """Escreve proposal JSON atomic. Retorna path absoluto."""
    pid = proposal["proposal_id"]
    path = PROPOSALS_DIR / f"{pid}.json"
    content = json.dumps(proposal, ensure_ascii=False, indent=2)
    _atomic_write(path, content)
    return path


def read_proposal(proposal_id: str) -> Dict[str, Any]:
    """Le proposal JSON. Raises FileNotFoundError com code PROPOSAL_NOT_FOUND."""
    path = PROPOSALS_DIR / f"{proposal_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"PROPOSAL_NOT_FOUND: {proposal_id}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def update_proposal(proposal: Dict[str, Any]) -> Path:
    """Reescreve proposal (atomic). Proposal_id inalterado."""
    return write_proposal(proposal)


def list_proposals(
    status_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Lista proposals. status_filter: pending|accepted|rejected|all|None.

    None ou 'all' retorna todas. Cada item ganha key `_computed_status`
    derivada de `state.accepted_at` / `state.rejected_at`.
    """
    if not PROPOSALS_DIR.exists():
        return []
    out: List[Dict[str, Any]] = []
    for path in sorted(PROPOSALS_DIR.glob("*.json")):
        try:
            with open(path, "r", encoding="utf-8") as f:
                p = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        state = p.get("state", {})
        if state.get("accepted_at"):
            p_status = "accepted"
        elif state.get("rejected_at"):
            p_status = "rejected"
        else:
            p_status = "pending"
        if status_filter and status_filter != "all" and p_status != status_filter:
            continue
        p["_computed_status"] = p_status
        out.append(p)
    return out


def proposal_exists(proposal_id: str) -> bool:
    return (PROPOSALS_DIR / f"{proposal_id}.json").exists()
