"""Gate check local — espelha wave-4 payload_gate (E10/OH wave-6).

Propósito: scrum-master valida localmente que cada task proposta tem
spec_ref + acceptance_criteria populados ANTES de submeter ao kanban.
Sem isso, o wave-4 gate do kanban rejeitaria o materialize downstream.

Guard-rail: fail-fast upstream → feedback imediato ao dev em vez de
submissao parcial + partial_failure (que exige triagem manual).
"""
from typing import Tuple, List


class GateCheckFailedError(Exception):
    def __init__(self, failures: List[str]):
        self.failures = list(failures)
        self.code = "GATE_CHECK_FAILED"
        super().__init__(f"gate check failures: {self.failures}")


def check_task_payload(task) -> Tuple[bool, List[str]]:
    """Valida 1 task. Aceita tanto `spec_ref` (singular) quanto `spec_refs`
    (plural, list) — source shape do proposer atual usa plural.

    Returns (ok, missing_fields_list).
    """
    dp = task.get("dispatch_payload") or {}
    missing: List[str] = []

    # spec_ref: string nao-vazia OR spec_refs: lista nao-vazia
    spec = dp.get("spec_ref")
    spec_refs = dp.get("spec_refs")
    spec_ok = False
    if isinstance(spec, str) and spec.strip():
        spec_ok = True
    elif isinstance(spec, list) and len(spec) > 0:
        spec_ok = True
    elif isinstance(spec_refs, list) and len(spec_refs) > 0:
        spec_ok = True
    if not spec_ok:
        missing.append("spec_ref")

    # acceptance_criteria: lista non-vazia
    ac = dp.get("acceptance_criteria")
    if not isinstance(ac, list) or len(ac) == 0:
        missing.append("acceptance_criteria")

    return (len(missing) == 0, missing)


def check_proposal(proposal) -> None:
    """Valida todas as tasks do proposal. Raise GateCheckFailedError
    se qualquer task falhar. Message lista todas as falhas.
    """
    failures: List[str] = []
    for i, t in enumerate(proposal.get("tasks") or []):
        ok, missing = check_task_payload(t)
        if not ok:
            label = t.get("label", f"task[{i}]")
            failures.append(f"{label}: missing {missing}")
    if failures:
        raise GateCheckFailedError(failures)
