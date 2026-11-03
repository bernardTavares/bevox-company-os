"""Lifecycle: orquestra check completo de uma task.

Fluxo:
1. Carrega context (task + log + files + specs)
2. Prechecks (5 invariantes)
   - Se algum falha: precheck-failure path (block test_failed: precheck_X)
3. Per AC: check_ac via LLM + safety.enforce_safety
4. Aggregate overall status:
   - All pass + zero structural_concern -> done
   - Any structural_concern detectado -> propose_rejection (exit 3, NAO move kanban)
   - Any fail (sem structural) -> in_progress + block test_failed
   - Any inconclusive (sem fail/structural) -> in_progress + block test_inconclusive
5. Apply decisao no kanban + merge test_result
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from . import checker as checker_lib
from . import context_loader
from . import prechecks
from . import safety
from . import store

KANBAN_CLI = Path(f"{Path.home()}/.openclaw/kanban-tasks/cli.sh")

# Reuse dispatcher Telegram notifier — same Telegram triple, same thread.
# Tester-agent já tem seu próprio package "lib"; carregamos o módulo do
# dispatcher por path absoluto via importlib pra evitar colisão de namespace.
def _load_dispatcher_notifier():
    import importlib.util
    notifier_path = Path(
        f"{Path.home()}/.openclaw/dispatcher-agent/lib/notifier.py")
    if not notifier_path.is_file():
        return None
    # telegram_meta sit em scripts/lib/ e é importado pelo notifier
    _TM_LIB = f"{Path.home()}/.openclaw/scripts/lib"
    if _TM_LIB not in sys.path:
        sys.path.insert(0, _TM_LIB)
    spec = importlib.util.spec_from_file_location(
        "openclaw_dispatcher_notifier", notifier_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        return None
    return module


dispatcher_notifier = _load_dispatcher_notifier()


class LifecycleError(Exception):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _run_kanban(args: list, actor: str = "tester") -> Dict[str, Any]:
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


def move_to_done(task_id: str) -> None:
    _run_kanban(["task", "move", task_id, "done"])


def move_to_in_progress(task_id: str) -> None:
    _run_kanban(["task", "move", task_id, "in_progress"])


def block(task_id: str, reason: str) -> None:
    _run_kanban(["task", "block", task_id, "--reason", reason])


def reject_task(task_id: str, reason: str) -> None:
    """Bernard --commit only. Unblock se necessario antes de move terminal.

    F4 wave-3 enforce MUST_UNBLOCK_BEFORE_TERMINAL: task blocked nao pode
    mover pra rejected. Tester normalmente bloqueia com test_failed antes
    do Bernard rodar reject-task, entao precisamos unblock idempotente.
    """
    try:
        _run_kanban(["task", "unblock", task_id])
    except LifecycleError:
        pass  # task may already be unblocked; ignore
    _run_kanban(["task", "move", task_id, "rejected", "--reason", reason])


def merge_test_result(task_id: str, fields: Dict[str, Any]) -> None:
    """Shallow merge top-level em dispatch_payload."""
    _run_kanban([
        "task", "set-dispatch-payload", task_id,
        "--payload", json.dumps(fields, ensure_ascii=False), "--merge",
    ])


def _aggregate(checks: List[Dict[str, Any]]) -> Dict[str, str]:
    """Decide overall + decision baseado nos per-AC effective_status + structural_concern."""
    has_structural = any(c.get("effective_structural_concern") for c in checks)
    if has_structural:
        return {"overall": "structural_reject_proposed",
                "decision": "proposed_rejected"}
    statuses = [c.get("effective_status") for c in checks]
    if any(s == "fail" for s in statuses):
        return {"overall": "fail", "decision": "in_progress_test_failed"}
    if any(s == "inconclusive" for s in statuses):
        return {"overall": "inconclusive",
                "decision": "in_progress_test_inconclusive"}
    if all(s == "pass" for s in statuses) and statuses:
        return {"overall": "pass", "decision": "done"}
    # Fallback (zero AC checks impossivel pos-precheck mas defensivo)
    return {"overall": "inconclusive", "decision": "in_progress_test_inconclusive"}


def _short_reason(text: str, limit: int = 80) -> str:
    return (text or "").replace("\n", " ").strip()[:limit]


def _write_escalation_md(test_run_id: str, task_id: str,
                         checks: List[Dict[str, Any]]) -> None:
    structural_checks = [c for c in checks if c.get("effective_structural_concern")]
    # Prefer first structural concern; fallback to "manual" if none detected
    suggested = (structural_checks[0].get("effective_structural_concern")
                 if structural_checks else "manual")
    frontmatter = (
        f"---\n"
        f"test_run_id: {test_run_id}\n"
        f"task_id: {task_id}\n"
        f"decision: proposed_rejected\n"
        f"structural_concern: {suggested}\n"
        f"generated_at: {store.now_iso()}\n"
        f"---\n\n"
    )
    body = f"""# Tester escalation — {test_run_id}

**Task:** {task_id}
**Generated at:** {store.now_iso()}
**Suggested category:** {suggested}

---

## Structural concerns detectadas

"""
    for c in structural_checks:
        body += (f"### AC: {c.get('ac', '')[:200]}\n\n"
                 f"- structural_concern: {c.get('effective_structural_concern')}\n"
                 f"- evidence: {c.get('evidence', '')[:300]}\n"
                 f"- sources: {c.get('valid_sources') or c.get('sources')}\n\n")
    body += """---

## Acoes possiveis (Bernard)

- `vox tester reject-task <task-id> --reason "<categoria>: <detail>" --commit`
- `vox tester recheck <task-id>` (apos editar AC/spec)
- Override manual: `~/.openclaw/kanban-tasks/cli.sh task move <task-id> done --actor bernard`
- UBN: respond no Telegram com `/ubn_done <task-id> <reason>` ou `/ubn_reject <task-id> <reason>`
"""
    store.write_escalation(test_run_id, frontmatter + body)


def _build_merge_fields(test_run: Dict[str, Any], path: Path,
                        seq: int) -> Dict[str, Any]:
    """Campos isolados em dispatch_payload (decisao #9 da spec)."""
    return {
        "test_result": {
            "last_test_run_id": test_run["test_run_id"],
            "last_test_run_path": str(path),
            "last_test_overall": test_run["overall"],
            "last_test_decision": test_run["decision"],
            "last_test_finished_at": test_run.get("finished_at"),
            "test_run_count": seq,
            "tester_actor": "tester",
        },
    }


def _build_decision_reason(agg: Dict[str, str],
                           checks: List[Dict[str, Any]]) -> str:
    decision = agg["decision"]
    if decision == "done":
        return f"all {len(checks)} AC pass"
    if decision == "in_progress_test_failed":
        fails = [c for c in checks if c["effective_status"] == "fail"]
        return f"{len(fails)}/{len(checks)} AC fail: {_short_reason(fails[0].get('ac', ''))}"
    if decision == "in_progress_test_inconclusive":
        inc = [c for c in checks if c["effective_status"] == "inconclusive"]
        return f"{len(inc)}/{len(checks)} AC inconclusive: {_short_reason(inc[0].get('downgrade_reason') or inc[0].get('evidence', ''))}"
    if decision == "proposed_rejected":
        sc = [c for c in checks if c.get("effective_structural_concern")]
        return f"structural concern detected: {sc[0].get('effective_structural_concern')}"
    return "unknown"


def run_check(
    task_id: str,
    no_act: bool = False,
    model: Optional[str] = None,
    trigger: str = "manual",
    escalation_check: Optional[Callable[[str], bool]] = None,
) -> Dict[str, Any]:
    """Executa check completo: prechecks -> LLM checks -> decisao -> kanban (se !no_act).

    Retorna test_run dict completo.
    """
    if escalation_check is None:
        escalation_check = prechecks.default_escalation_check

    seq = store.next_test_run_seq(task_id)
    test_run_id = store.make_test_run_id(task_id, seq)
    started_at = store.now_iso()

    # Load context
    ctx = context_loader.build_test_context(task_id)
    task = ctx["task"]
    log_path = context_loader.execution_log_path(task_id)

    # Prechecks
    pc = prechecks.run_prechecks(task, log_path, escalation_check)
    test_run: Dict[str, Any] = {
        "test_run_id": test_run_id,
        "task_id": task_id,
        "started_at": started_at,
        "trigger": trigger,
        "prechecks": pc,
        "checks": [],
        "overall": None,
        "decision": None,
        "decision_reason": "",
        "kanban_actions_applied": [],
    }

    if not pc["passed"]:
        # Precheck failure path: nao roda LLM, devolve in_progress blocked
        test_run["overall"] = "fail"
        test_run["decision"] = "in_progress_test_failed_precheck"
        test_run["decision_reason"] = pc["failure_reason"]
        test_run["finished_at"] = store.now_iso()
        path = store.write_test_run(test_run_id, test_run)
        if not no_act:
            try:
                # Skip move if task not in testing (already in another state)
                if pc["details"].get("task_in_testing"):
                    move_to_in_progress(task_id)
                    block(task_id, f"test_failed: {_short_reason(pc['failure_reason'])}")
                    test_run["kanban_actions_applied"] = [
                        "task_move:in_progress", "task_block:test_failed"]
                merge_test_result(task_id, _build_merge_fields(test_run, path, seq))
                test_run["kanban_actions_applied"].append("set-dispatch-payload:test_result")
                store.write_test_run(test_run_id, test_run)
            except LifecycleError:
                raise
        return test_run

    # Per AC checks
    ac_list = ctx["acceptance_criteria"]
    model_kw = {"model": model} if model else {}
    raw_checks: List[Dict[str, Any]] = []
    for ac in ac_list:
        try:
            raw = checker_lib.check_ac(ac, ctx, **model_kw)
        except checker_lib.CheckerError as e:
            # Treat checker failure as inconclusive (operator inspect)
            raw = {"status": "inconclusive", "evidence": "", "sources": [],
                   "structural_concern": "",
                   "raw_response": f"CHECKER_ERROR: {e}",
                   "drafter_model": model or checker_lib.CHECKER_MODEL,
                   "checker_error": str(e)}
        safety_result = safety.enforce_safety(
            raw["status"], raw["sources"], raw.get("structural_concern", ""), ctx,
        )
        raw_checks.append({
            "ac": ac,
            "status": raw["status"],
            "effective_status": safety_result["effective_status"],
            "downgrade_reason": safety_result["downgrade_reason"],
            "structural_concern": raw.get("structural_concern", ""),
            "effective_structural_concern": safety_result["effective_structural_concern"],
            "evidence": raw.get("evidence", ""),
            "sources": raw.get("sources", []),
            "valid_sources": safety_result["valid_sources"],
            "invalid_sources": safety_result["invalid_sources"],
            "drafter_model": raw.get("drafter_model"),
            "raw_response": raw.get("raw_response", ""),
            "checker_error": raw.get("checker_error"),
        })

    test_run["checks"] = raw_checks

    # Aggregate decision
    agg = _aggregate(raw_checks)
    test_run["overall"] = agg["overall"]
    test_run["decision"] = agg["decision"]
    test_run["decision_reason"] = _build_decision_reason(agg, raw_checks)
    test_run["finished_at"] = store.now_iso()
    path = store.write_test_run(test_run_id, test_run)

    if no_act:
        return test_run

    # Apply kanban
    actions: List[str] = []
    decision = agg["decision"]
    notif_outcome: Optional[str] = None
    notif_extra: Dict[str, Any] = {}
    if decision == "done":
        move_to_done(task_id)
        actions += ["task_move:done"]
        notif_outcome = "passed"
        notif_extra = {"test_run_id": test_run_id}
    elif decision == "in_progress_test_failed":
        first_fail = next((c for c in raw_checks
                           if c["effective_status"] == "fail"), None)
        ac_excerpt = _short_reason(first_fail.get("ac", "") if first_fail else "")
        move_to_in_progress(task_id)
        block(task_id, f"test_failed: {ac_excerpt}")
        actions += ["task_move:in_progress", "task_block:test_failed"]
        notif_outcome = "failed_test"
        notif_extra = {
            "first_failed_ac": first_fail.get("ac", "?") if first_fail else "?",
            "test_run_path": str(path),
        }
    elif decision == "in_progress_test_inconclusive":
        first_inc = next((c for c in raw_checks
                          if c["effective_status"] == "inconclusive"), None)
        reason_excerpt = _short_reason(
            (first_inc.get("downgrade_reason") or first_inc.get("evidence") or "")
            if first_inc else "",
        )
        move_to_in_progress(task_id)
        block(task_id, f"test_inconclusive: {reason_excerpt}")
        actions += ["task_move:in_progress", "task_block:test_inconclusive"]
        notif_outcome = "inconclusive"
        notif_extra = {
            "decision_reason": test_run["decision_reason"],
            "test_run_path": str(path),
        }
    elif decision == "proposed_rejected":
        # NAO move kanban; escreve escalation file. Bernard --commit decide.
        _write_escalation_md(test_run_id, task_id, raw_checks)
        actions += ["escalation_written"]
    merge_test_result(task_id, _build_merge_fields(test_run, path, seq))
    actions += ["set-dispatch-payload:test_result"]

    # Telegram notify (graceful — falhas swallow)
    if notif_outcome and dispatcher_notifier is not None:
        try:
            notif_ctx = _build_notifier_context(task, log_path)
            notif_ctx.update(notif_extra)
            dispatcher_notifier.send_task_event(
                task_id, notif_outcome, context=notif_ctx,
            )
        except Exception as e:  # double-safety; notifier já é graceful
            print(f"tester notifier raised (swallowed): {e}", file=sys.stderr)

    test_run["kanban_actions_applied"] = actions
    store.write_test_run(test_run_id, test_run)
    return test_run


def _build_notifier_context(task: Dict[str, Any], log_path: Path) -> Dict[str, Any]:
    """Mirror dispatcher's notifier context shape."""
    return {
        "project": task.get("project") or "?",
        "title": task.get("title") or "?",
        "log_path": str(log_path),
    }
