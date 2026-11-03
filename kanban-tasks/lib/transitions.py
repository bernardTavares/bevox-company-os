"""Status transitions: whitelist canonica + validacao soft.

Whitelist (transicoes nao-forcadas):
    backlog     -> ready, in_progress, rejected
    ready       -> backlog, in_progress, rejected
    in_progress -> ready, testing, rejected
    testing     -> in_progress, done, rejected
    done        -> nada (terminal -- exige reopen)
    rejected    -> nada (terminal -- exige reopen)

Soft policy: fora da whitelist exige force=True (humano) ou
reason nao-vazio (agente).
"""

from typing import Optional

# Status enum canonico (excluindo `archived`, que e ortogonal).
STATUS_ENUM = ("backlog", "ready", "in_progress", "testing", "done", "rejected")

# Status terminais -- so saem via cmd `reopen`.
TERMINAL = frozenset({"done", "rejected"})

# Status onde flag `blocked` e permitida.
BLOCKABLE = frozenset({"backlog", "ready", "in_progress", "testing"})

# Whitelist soft. Cada chave -> tuple de destinos validos sem force.
WHITELIST = {
    "backlog":     ("ready", "in_progress", "rejected"),
    "ready":       ("backlog", "in_progress", "rejected"),
    "in_progress": ("ready", "testing", "rejected"),
    "testing":     ("in_progress", "done", "rejected"),
    "done":        (),
    "rejected":    (),
}


def is_valid_transition(from_status: str, to_status: str) -> bool:
    """True se transicao esta na whitelist (sem force)."""
    return to_status in WHITELIST.get(from_status, ())


def is_terminal(status: str) -> bool:
    return status in TERMINAL


def is_blockable(status: str) -> bool:
    return status in BLOCKABLE


def validate_or_raise(
    from_status: str,
    to_status: str,
    force: bool,
    reason: Optional[str],
    actor: str,
) -> None:
    """Valida transicao. Levanta ValueError em politica violada.

    - Transicao na whitelist: aceita sempre.
    - Fora da whitelist + actor=='bernard' + force=False: erro INVALID_TRANSITION.
    - Fora da whitelist + actor!='bernard' + reason vazio: erro
      INVALID_TRANSITION_AGENT_NEEDS_REASON.
    - Fora da whitelist + reason ou force: aceita.
    """
    if to_status not in STATUS_ENUM:
        raise ValueError(f"invalid status: {to_status}")
    if is_valid_transition(from_status, to_status):
        return  # OK, dentro da whitelist
    # fora da whitelist
    is_agent = actor != "bernard"
    if is_agent:
        if not reason or not reason.strip():
            raise ValueError(
                f"INVALID_TRANSITION_AGENT_NEEDS_REASON: "
                f"agent '{actor}' must pass --reason to move {from_status}->{to_status}; "
                f"valid destinations from {from_status}: {WHITELIST.get(from_status, ())}"
            )
        return  # agente com reason: OK
    # humano (bernard) sem force
    if not force:
        raise ValueError(
            f"INVALID_TRANSITION: cannot move {from_status}->{to_status} without --force; "
            f"valid destinations from {from_status}: {WHITELIST.get(from_status, ())}"
        )
    return  # humano com --force: OK


# ================= Wave-5 helpers: blocked_by =================

def validate_blocked_by_field(value):
    """Valida o formato do campo dispatch_payload.blocked_by.

    Aceita:
    - None (ausente — valido)
    - list de strings com prefixo T-

    Retorna (valid: bool, errors: list[str]).
    """
    if value is None:
        return (True, [])
    if not isinstance(value, list):
        return (False, ["blocked_by_must_be_list"])
    errors = []
    for i, item in enumerate(value):
        if not isinstance(item, str) or not item.startswith("T-"):
            errors.append(f"blocked_by[{i}]_invalid")
    return (len(errors) == 0, errors)


def _blocked_by_of(task):
    """Extrai blocked_by de task (navegando dispatch_payload). Retorna lista."""
    dp = task.get("dispatch_payload") or {}
    return dp.get("blocked_by") or []


def detect_cycle(state, proposed_task_id, proposed_preds):
    """DFS topologica sobre o grafo blocked_by. Retorna path do ciclo (lista)
    ou [] se nao ha ciclo.

    proposed_task_id + proposed_preds representam uma proposta de mutacao
    (simula o grafo apos set-blocked-by). Sem side effect no state.

    Preds inexistentes no state sao tratados como folha (nao-cycle); gate
    de pred-not-found eh responsabilidade separada.
    """
    # Constroi grafo atual + substitui proposta
    graph = {}
    for t in state.get("tasks", []):
        graph[t["id"]] = list(_blocked_by_of(t))
    graph[proposed_task_id] = list(proposed_preds)

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {}

    def dfs(node, path):
        if color.get(node) == GRAY:
            # ciclo encontrado; retorna slice do path ate este node + ele
            start = path.index(node) if node in path else 0
            return path[start:] + [node]
        if color.get(node) == BLACK:
            return None
        color[node] = GRAY
        new_path = path + [node]
        for neighbor in graph.get(node, []):
            if neighbor not in graph:
                # pred nao existe no state -> trata como folha (sem cycle)
                continue
            found = dfs(neighbor, new_path)
            if found:
                return found
        color[node] = BLACK
        return None

    return dfs(proposed_task_id, []) or []


def can_move_to_ready(task, state):
    """Retorna (ok: bool, missing_preds: list[str]).

    AND semantics: ok=True apenas se TODOS os preds do task estao status=done.
    Preds com status != done ou pred nao-existente contam como missing.
    """
    preds = _blocked_by_of(task)
    if not preds:
        return (True, [])
    missing = []
    by_id = {t["id"]: t for t in state.get("tasks", [])}
    for pred_id in preds:
        pred = by_id.get(pred_id)
        if pred is None:
            missing.append(f"{pred_id}:not_found")
            continue
        status = pred.get("status")
        if status != "done":
            missing.append(f"{pred_id}:{status}")
    return (len(missing) == 0, missing)
