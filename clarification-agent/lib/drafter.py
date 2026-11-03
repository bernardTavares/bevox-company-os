"""Drafter: invoca subprocess claude -p com prompt estruturado + parseia.

Plano B Spike-5: zero Anthropic SDK; usa claude CLI subprocess.
Model default: claude-haiku-4-5 (barato + rapido para QA).
"""

import json
import re
import subprocess
from typing import Any, Dict, Optional

from . import context_loader
from . import safety
from . import provider as provider_lib


DRAFTER_MODEL_LOCAL = "qwen2.5-coder:14b"
DRAFTER_PROVIDER_LOCAL = "ollama"
DRAFTER_MODEL_CLOUD = "claude-haiku-4-5"
DRAFTER_PROVIDER_CLOUD = "claude_cli"
DRAFTER_TIMEOUT_LOCAL = 30
DRAFTER_TIMEOUT_CLOUD = 20


class DrafterError(Exception):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _build_prompt(
    task_id: str, question: str, ctx_bundle: Dict[str, Any],
) -> str:
    task = ctx_bundle.get("task") or {}
    payload = ctx_bundle.get("dispatch_payload") or {}
    refs = ctx_bundle.get("read_refs") or []

    refs_block = ""
    for r in refs[:10]:
        content = r["content"][:8000]
        refs_block += f"\n### {r['ref']} (path: {r['path']})\n\n```\n{content}\n```\n"

    unresolved = ctx_bundle.get("unresolved_refs") or []
    unresolved_block = ""
    if unresolved:
        unresolved_block = (
            "\n### Unresolved refs (informative)\n"
            + "\n".join(f"- {r}" for r in unresolved)
        )

    prompt = f"""Voce e um agente de clarification do OpenClaw. Responda a duvida operacional
de outra sessao Claude Code (executor) estritamente com base no contexto fornecido.

NAO invente informacao. Se nao houver base no contexto, declare unsafe.

## Task alvo

- id: {task_id}
- title: {task.get("title", "")}
- epic_id: {task.get("epic_id", "")}
- wave_ref: {task.get("wave_ref", "")}

## Dispatch payload

- goal: {payload.get("goal", "")[:300]}
- acceptance_criteria: {payload.get("acceptance_criteria", [])}
- files_relevant: {payload.get("files_relevant", [])}
- guardrails: {payload.get("guardrails", [])}
- out_of_scope: {payload.get("out_of_scope", [])}

## Contexto canonico

{refs_block}

{unresolved_block}

## Pergunta do executor

{question}

## Formato OBRIGATORIO da resposta

Responda EXATAMENTE neste formato JSON (e nada alem disso; zero prose fora do JSON):

```json
{{
  "answer": "<texto da resposta, markdown permitido>",
  "sources": ["<ref>", "<ref com linhas ou secao>"],
  "confidence": "safe" | "unsafe",
  "escalation_reason": "<motivo se unsafe; string vazia se safe>"
}}
```

Regras:
- `confidence=safe`: resposta esta ancorada em trechos concretos dos refs fornecidos.
  Lista sources minimo 1 path que EXISTE no contexto acima.
- `confidence=unsafe`: resposta exigiria decisao arquitetural nao documentada
  OU contradicao entre refs OU source insuficiente. Escreve escalation_reason claro.
- NUNCA invente paths de sources que nao estao no contexto acima.
- Se pergunta pede "qual e a decisao X", mas decisao nao esta nos refs, escreva
  unsafe + reason="no supporting source for <topic>".
"""
    return prompt


def draft_answer(
    task_id: str, question: str,
    ctx_bundle: Optional[Dict[str, Any]] = None,
    model: str = DRAFTER_MODEL_CLOUD,
    provider: str = DRAFTER_PROVIDER_CLOUD,
    timeout: int = DRAFTER_TIMEOUT_CLOUD,
) -> Dict[str, Any]:
    if ctx_bundle is None:
        ctx_bundle = context_loader.build_context_bundle(task_id)
    prompt = _build_prompt(task_id, question, ctx_bundle)
    out = provider_lib.run(
        prompt=prompt, model=model, timeout=timeout, provider=provider,
    )
    if out["error"] == "timeout":
        raise DrafterError("CLAUDE_SUBPROCESS_FAILED",
                           f"{provider} timeout after {timeout}s")
    if out["error"] and out["error"].startswith("subprocess_error"):
        raise DrafterError("CLAUDE_SUBPROCESS_FAILED", out["error"])
    if out["error"] == "parse_failed":
        raise DrafterError("PARSE_NO_JSON",
                           f"provider={provider} raw sem JSON: {out['raw'][:300]}")
    parsed = out["parsed"]
    for field in ("answer", "sources", "confidence"):
        if field not in parsed:
            raise DrafterError("PARSE_MISSING_FIELD", f"field '{field}' ausente")
    effective_confidence, effective_reason = safety.enforce_safety(
        parsed["confidence"], parsed["sources"],
        parsed.get("escalation_reason", ""),
    )
    return {
        "answer": parsed["answer"],
        "sources": parsed["sources"],
        "confidence": effective_confidence,
        "escalation_reason": effective_reason,
        "raw_response": out["raw"][:5000],
        "drafter_model": model,
        "drafter_provider": out["provider_used"],
        "drafter_latency_ms": out["latency_ms"],
    }


def draft_answer_local_first(
    task_id: str, question: str,
    ctx_bundle: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Tenta ollama local (qwen2.5-coder:14b). Em unsafe local, 1 fallback claude cloud.

    Retorna o mesmo shape de draft_answer, com campo extra:
    - `local_first_fallback_used`: bool
    - `local_first_local_confidence`: "safe"|"unsafe"|"error"
    """
    local_result = None
    try:
        local_result = draft_answer(
            task_id, question, ctx_bundle=ctx_bundle,
            model=DRAFTER_MODEL_LOCAL, provider=DRAFTER_PROVIDER_LOCAL,
            timeout=DRAFTER_TIMEOUT_LOCAL,
        )
    except DrafterError as e:
        # Local falhou (timeout, parse fail, exit nonzero) — tenta cloud
        cloud_result = draft_answer(
            task_id, question, ctx_bundle=ctx_bundle,
            model=DRAFTER_MODEL_CLOUD, provider=DRAFTER_PROVIDER_CLOUD,
            timeout=DRAFTER_TIMEOUT_CLOUD,
        )
        cloud_result["local_first_fallback_used"] = True
        cloud_result["local_first_local_confidence"] = "error"
        cloud_result["local_first_local_error"] = f"{e.code}:{e.detail[:100]}"
        return cloud_result

    if local_result["confidence"] == "safe":
        local_result["local_first_fallback_used"] = False
        local_result["local_first_local_confidence"] = "safe"
        return local_result

    # Local unsafe → fallback cloud 1x
    try:
        cloud_result = draft_answer(
            task_id, question, ctx_bundle=ctx_bundle,
            model=DRAFTER_MODEL_CLOUD, provider=DRAFTER_PROVIDER_CLOUD,
            timeout=DRAFTER_TIMEOUT_CLOUD,
        )
    except DrafterError:
        # Cloud também falhou — retorna o local unsafe
        local_result["local_first_fallback_used"] = True
        local_result["local_first_local_confidence"] = "unsafe"
        local_result["local_first_cloud_error"] = "cloud_drafter_failed"
        return local_result

    cloud_result["local_first_fallback_used"] = True
    cloud_result["local_first_local_confidence"] = "unsafe"
    cloud_result["local_first_local_escalation_reason"] = local_result["escalation_reason"]
    return cloud_result
