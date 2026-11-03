"""Payload completeness gate — E10/OH wave-4.

Enforce policy wave-0 §3: criacao de task no kanban exige dispatch_payload
com spec_ref + acceptance_criteria preenchidos. Modulo puro (sem side
effects); callers (CLI + HTTP) invocam enforce_payload_gate antes de criar.

Aceita formas flexiveis de spec_ref:
- string nao-vazia
- lista nao-vazia de strings

Acceptance_criteria deve ser lista nao-vazia. Conteudo de cada item nao
eh validado nesta wave (apenas presenca/tipo).
"""
from typing import Any, Dict, List, Tuple


class PayloadIncompleteError(Exception):
    """Raised quando payload falha gate. Carrega lista de campos faltantes."""

    def __init__(self, missing: List[str]):
        self.missing = list(missing)
        self.code = "PAYLOAD_INCOMPLETE"
        super().__init__(f"payload incomplete: missing {self.missing}")


def validate_payload(payload: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Retorna (valid, missing_fields).

    Campos avaliados:
    - spec_ref: string nao-vazia OU lista nao-vazia. Falso se ausente, vazio,
      ou tipo invalido.
    - acceptance_criteria: lista com >=1 item. Falso se ausente, nao-lista,
      ou lista vazia.

    Nao raise. Callers decidem politica.
    """
    missing: List[str] = []

    spec = payload.get("spec_ref") if isinstance(payload, dict) else None
    if isinstance(spec, str):
        if not spec.strip():
            missing.append("spec_ref")
    elif isinstance(spec, list):
        if len(spec) == 0:
            missing.append("spec_ref")
    else:
        missing.append("spec_ref")

    ac = payload.get("acceptance_criteria") if isinstance(payload, dict) else None
    if not isinstance(ac, list) or len(ac) == 0:
        missing.append("acceptance_criteria")

    return (len(missing) == 0, missing)


def enforce_payload_gate(payload: Dict[str, Any]) -> None:
    """Raise PayloadIncompleteError se invalido. No-op se valido."""
    valid, missing = validate_payload(payload)
    if not valid:
        raise PayloadIncompleteError(missing)
