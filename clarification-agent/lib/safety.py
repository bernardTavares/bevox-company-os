"""Safety: valida sources + binary confidence (safe|unsafe)."""

from typing import List, Tuple

from . import context_loader

VALID_CONFIDENCE = {"safe", "unsafe"}


class SafetyError(Exception):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def validate_confidence(value: str) -> None:
    if value not in VALID_CONFIDENCE:
        raise SafetyError(
            "INVALID_CONFIDENCE",
            f"confidence='{value}' nao e 'safe'|'unsafe'",
        )


def validate_sources(sources: List[str]) -> Tuple[List[str], List[str]]:
    """Resolve cada source path. Retorna (valid, invalid)."""
    valid, invalid = [], []
    for s in sources:
        path_part = s.split(" ")[0].split("#")[0].strip("`")
        p = context_loader.resolve_ref_path(path_part)
        if p is not None and p.exists():
            valid.append(s)
        else:
            invalid.append(s)
    return valid, invalid


def enforce_safety(
    confidence: str, sources: List[str], escalation_reason: str,
) -> Tuple[str, str]:
    """Aplica safety rules. Retorna (effective_confidence, effective_reason)."""
    validate_confidence(confidence)
    valid_sources, invalid_sources = validate_sources(sources)

    if confidence == "safe":
        if not valid_sources:
            return "unsafe", (
                "forced_unsafe: confidence=safe declarada mas zero sources "
                "validas. Drafter pode estar alucinando; escalation obrigatoria."
            )
        if invalid_sources:
            return "unsafe", (
                f"forced_unsafe: sources invalidas detectadas (hallucination guard): "
                f"{invalid_sources[:3]}. valid={valid_sources[:3]}"
            )
        return "safe", ""

    reason = escalation_reason.strip() or "unspecified: drafter did not provide escalation_reason"
    return "unsafe", reason
