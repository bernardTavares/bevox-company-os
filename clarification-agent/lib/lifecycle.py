"""Clarification lifecycle: orquestra ask->draft->resolve."""

import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from . import store
from . import drafter as drafter_lib

KANBAN_CLI = Path(f"{Path.home()}/.openclaw/kanban-tasks/cli.sh")


class LifecycleError(Exception):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _run_kanban(args: list, actor: str = "clarification") -> Dict[str, Any]:
    cmd = [str(KANBAN_CLI)] + args + ["--json", "--actor", actor]
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, check=False, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise LifecycleError("KANBAN_CLI_TIMEOUT", str(e))
    if r.returncode != 0:
        raise LifecycleError(
            "KANBAN_CLI_FAILED",
            f"exit={r.returncode} stderr={r.stderr.strip()[:200]}",
        )
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError as e:
        raise LifecycleError("KANBAN_CLI_BAD_JSON", str(e))


def block_for_clarification(task_id: str, question_summary: str) -> None:
    reason = f"clarification_required: {question_summary[:80]}"
    _run_kanban(["task", "block", task_id, "--reason", reason])


def mark_escalation(task_id: str, escalation_reason: str) -> None:
    _run_kanban(["task", "unblock", task_id])
    reason = f"clarification_escalation_required: {escalation_reason[:80]}"
    _run_kanban(["task", "block", task_id, "--reason", reason])


def unblock(task_id: str) -> None:
    _run_kanban(["task", "unblock", task_id])


def reject_task(task_id: str, reason: str) -> None:
    _run_kanban(["task", "move", task_id, "rejected", "--reason", reason])


def merge_dispatch_payload(task_id: str, fields: Dict[str, Any]) -> None:
    _run_kanban([
        "task", "set-dispatch-payload", task_id,
        "--payload", json.dumps(fields, ensure_ascii=False), "--merge",
    ])


def ask_and_draft(
    task_id: str, question_text: str, model: Optional[str] = None,
) -> Dict[str, Any]:
    """Cycle ask: register + block + draft + auto-resolve safe / escalate unsafe."""
    seq = store.next_clarification_seq(task_id)
    clarification_id = store.make_clarification_id(task_id, seq)

    question_path = store.write_question(clarification_id, question_text)
    q_summary = question_text.strip().split("\n")[0][:80]
    block_for_clarification(task_id, q_summary)
    merge_dispatch_payload(task_id, {
        "last_clarification_id": clarification_id,
        "last_clarification_question_path": str(question_path),
        "clarification_count": seq,
    })

    drafter_kwargs = {}
    if model:
        drafter_kwargs["model"] = model
    # Drafter pode falhar (LLM down, rede, quota, exception). Sem try/except,
    # ask_and_draft morre antes de write_escalation — Bernard não recebe nada.
    # Fail-safe: drafter exception vira escalation unsafe automática.
    try:
        draft_result = drafter_lib.draft_answer(task_id, question_text, **drafter_kwargs)
    except Exception as e:
        draft_result = {
            "answer": (
                f"[AUTO-FAIL-SAFE] Drafter falhou: {type(e).__name__}: {e}\n\n"
                "Sem resposta automática. Bernard precisa decidir manualmente."
            ),
            "confidence": "unsafe",
            "sources": [],
            "drafter_model": "drafter-exception",
            "escalation_reason": f"drafter_exception: {type(e).__name__}: {e}",
        }

    answer_path = store.write_answer(
        clarification_id, question_path,
        draft_result["answer"], draft_result["confidence"],
        draft_result["sources"],
        drafter=f"clarification-agent ({draft_result['drafter_model']})",
        escalation_reason=draft_result.get("escalation_reason") or None,
    )

    if draft_result["confidence"] == "safe":
        unblock(task_id)
        merge_dispatch_payload(task_id, {
            "last_clarification_answer_path": str(answer_path),
            "last_clarification_confidence": "safe",
            "last_clarification_resolved_at": store.now_iso(),
        })
        store.emit_signal(clarification_id, "safe")
        return {
            "clarification_id": clarification_id,
            "confidence": "safe",
            "answer_path": str(answer_path),
            "question_path": str(question_path),
            "outcome": "safe",
            "answer_text": draft_result["answer"],
        }
    # Unsafe -> escalation
    store.write_escalation_symlink(clarification_id)
    mark_escalation(task_id, draft_result["escalation_reason"])
    merge_dispatch_payload(task_id, {
        "last_clarification_answer_path": str(answer_path),
        "last_clarification_confidence": "unsafe",
        "last_clarification_escalated_at": store.now_iso(),
    })
    return {
        "clarification_id": clarification_id,
        "confidence": "unsafe",
        "answer_path": str(answer_path),
        "question_path": str(question_path),
        "escalation_reason": draft_result["escalation_reason"],
        "outcome": "escalated",
    }


def emit_payload_incomplete_escalation(task_id: str, missing_fields: list) -> str:
    """Cria clarification + answer unsafe 'dispatch_payload_incomplete' sem LLM.

    Retorna clarification_id.
    """
    seq = store.next_clarification_seq(task_id)
    cid = store.make_clarification_id(task_id, seq)
    q_text = (f"[AUTO-FAST-FAIL] dispatch_payload incompleto. "
              f"Campos faltando: {missing_fields}")
    qpath = store.write_question(cid, q_text)
    ans_body = (
        "Nenhuma fonte canonica disponivel. "
        f"dispatch_payload esta sem os campos: {missing_fields}. "
        "Scrum-master OR humano upstream deve popular spec_ref + "
        "acceptance_criteria antes de retry."
    )
    store.write_answer(
        cid, qpath, ans_body, "unsafe",
        sources=[],
        drafter="clarification-poller (fast-fail)",
        escalation_reason=f"dispatch_payload_incomplete: missing {missing_fields}",
    )
    store.write_escalation_symlink(cid)
    mark_escalation(task_id, f"dispatch_payload_incomplete: missing {missing_fields}")
    merge_dispatch_payload(task_id, {
        "last_clarification_id": cid,
        "last_clarification_confidence": "unsafe",
        "last_clarification_source": "poller_fast_fail",
        "last_clarification_escalated_at": store.now_iso(),
    })
    return cid


def extract_question_from_blocked(blocked_reason: str) -> str:
    """Extrai pergunta do blocked_reason (formato 'clarification_required: <pergunta>')."""
    for prefix in ("clarification_required:", "clarification_escalation_required:"):
        if blocked_reason.startswith(prefix):
            return blocked_reason[len(prefix):].strip()
    return blocked_reason.strip()


def auto_draft_for_task(
    task_id: str, question_text: str,
) -> Dict[str, Any]:
    """Pull-mode analog de ask_and_draft, com drafter local-first."""
    seq = store.next_clarification_seq(task_id)
    cid = store.make_clarification_id(task_id, seq)
    qpath = store.write_question(cid, question_text)
    merge_dispatch_payload(task_id, {
        "last_clarification_id": cid,
        "last_clarification_question_path": str(qpath),
        "clarification_count": seq,
        "last_clarification_source": "poller",
    })
    draft = drafter_lib.draft_answer_local_first(task_id, question_text)
    answer_path = store.write_answer(
        cid, qpath,
        draft["answer"], draft["confidence"], draft["sources"],
        drafter=f"clarification-agent ({draft['drafter_model']} via {draft['drafter_provider']})",
        escalation_reason=draft.get("escalation_reason") or None,
    )
    if draft["confidence"] == "safe":
        unblock(task_id)
        merge_dispatch_payload(task_id, {
            "last_clarification_answer_path": str(answer_path),
            "last_clarification_confidence": "safe",
            "last_clarification_resolved_at": store.now_iso(),
            "last_clarification_source": "poller",
        })
        store.emit_signal(cid, "safe")
        return {"clarification_id": cid, "outcome": "safe",
                "answer_path": str(answer_path),
                "fallback_used": draft.get("local_first_fallback_used", False),
                "drafter_provider": draft["drafter_provider"]}
    store.write_escalation_symlink(cid)
    mark_escalation(task_id, draft["escalation_reason"])
    merge_dispatch_payload(task_id, {
        "last_clarification_answer_path": str(answer_path),
        "last_clarification_confidence": "unsafe",
        "last_clarification_escalated_at": store.now_iso(),
    })
    return {"clarification_id": cid, "outcome": "escalated",
            "answer_path": str(answer_path),
            "escalation_reason": draft["escalation_reason"],
            "fallback_used": draft.get("local_first_fallback_used", False),
            "drafter_provider": draft["drafter_provider"]}


def acquire_clarification_lock(task_id: str, holder: str = "clarification-poller") -> bool:
    """Tenta reservar clarification_lock no dispatch_payload. Retorna True se conseguiu."""
    state_path = Path(os.path.expanduser("~/.openclaw/kanban-tasks/state.json"))
    # Best-effort check: se ja existe lock de outro holder ha < 10min, respeita
    try:
        d = json.loads(state_path.read_text())
        for t in d.get("tasks") or []:
            if t.get("id") == task_id:
                lock = (t.get("dispatch_payload") or {}).get("clarification_lock") or {}
                existing_holder = lock.get("holder")
                if existing_holder and existing_holder != holder:
                    # Assume lock valido por 10min
                    aq = lock.get("acquired_at")
                    if aq:
                        try:
                            aq_dt = datetime.fromisoformat(aq.replace("Z", "+00:00"))
                            if datetime.now(tz=timezone.utc) - aq_dt < timedelta(minutes=10):
                                return False
                        except (ValueError, TypeError):
                            pass
                break
    except (OSError, json.JSONDecodeError):
        pass
    merge_dispatch_payload(task_id, {
        "clarification_lock": {
            "holder": holder,
            "acquired_at": store.now_iso(),
        },
    })
    return True


def release_clarification_lock(task_id: str) -> None:
    merge_dispatch_payload(task_id, {"clarification_lock": None})
