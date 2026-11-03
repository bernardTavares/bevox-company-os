"""Safety: valida status + sources + structural_concern.

Decisoes da spec:
- Confidence binary pass|fail|inconclusive (decisao #4 + #2c).
- Sources hallucination guard: pass exige >=1 source valida (existe no
  contexto OU no filesystem). Senao downgrade pra inconclusive.
- structural_concern: 4 categorias validas; outras dropadas.
"""

from pathlib import Path
from typing import Any, Dict, List, Tuple

VALID_STATUS = {"pass", "fail", "inconclusive"}
VALID_STRUCTURAL_CONCERNS = {
    "task_malformed", "spec_inconsistent",
    "requires_re_decomposition", "inexecutable",
}


class SafetyError(Exception):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _validate_sources(sources: List[str], ctx: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """Resolve cada source: precisa estar em files_relevant/spec_refs/execution_log path
    OU existir no filesystem absoluto."""
    valid, invalid = [], []
    known_paths = set()
    for f in (ctx.get("files_relevant") or []):
        known_paths.add(f.get("path"))
        known_paths.add(f.get("ref"))
    for r in (ctx.get("spec_refs") or []):
        known_paths.add(r.get("path"))
        known_paths.add(r.get("ref"))
    log_path = ctx.get("execution_log_path")
    if log_path:
        known_paths.add(log_path)
        known_paths.add("execution_log")

    for s in sources:
        if not s:
            invalid.append(s); continue
        # Strip line/column suffixes (path:line)
        bare = s.split(":")[0].strip("`")
        # Match exact known path OR check filesystem
        if bare in known_paths or s in known_paths:
            valid.append(s)
            continue
        if any(bare in kp for kp in known_paths if kp):
            valid.append(s)
            continue
        # Filesystem fallback
        try:
            p = Path(bare).expanduser()
            if p.exists() and p.is_file():
                valid.append(s)
                continue
        except (OSError, ValueError):
            pass
        invalid.append(s)
    return valid, invalid


def enforce_safety(
    status: str, sources: List[str], structural_concern: str,
    ctx: Dict[str, Any],
) -> Dict[str, Any]:
    """Aplica safety rules. Retorna effective_status + downgrade_reason +
    effective_structural_concern + sources_valid/invalid."""
    if status not in VALID_STATUS:
        raise SafetyError(
            "INVALID_STATUS",
            f"status='{status}' nao em {sorted(VALID_STATUS)}",
        )

    valid_sources, invalid_sources = _validate_sources(sources, ctx)

    effective_status = status
    downgrade_reason = ""

    if status == "pass":
        if invalid_sources and not valid_sources:
            effective_status = "inconclusive"
            downgrade_reason = (
                f"hallucination_guard: todas sources invalidas ({invalid_sources[:3]}); "
                f"zero validas. Downgrade pra inconclusive."
            )
        elif not valid_sources:
            effective_status = "inconclusive"
            downgrade_reason = (
                "no_sources: pass declarada mas zero sources fornecidas. "
                "Hallucination guard: downgrade pra inconclusive."
            )
        elif invalid_sources:
            effective_status = "inconclusive"
            downgrade_reason = (
                f"hallucination_guard: sources invalidas detectadas "
                f"({invalid_sources[:3]}). valid={valid_sources[:3]}"
            )

    sc = (structural_concern or "").strip()
    effective_sc = sc if sc in VALID_STRUCTURAL_CONCERNS else ""

    return {
        "effective_status": effective_status,
        "downgrade_reason": downgrade_reason,
        "effective_structural_concern": effective_sc,
        "valid_sources": valid_sources,
        "invalid_sources": invalid_sources,
    }
