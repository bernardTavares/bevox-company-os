"""Checker: invoca claude -p com prompt estruturado per AC.

Plano B Spike-5: zero Anthropic SDK; usa claude CLI subprocess.
allowedTools="Read,Grep" restritivo (decisao #6 da spec).
Model default: claude-haiku-4-5 (barato + rapido).
"""

import json
import re
import subprocess
from typing import Any, Dict, List, Optional

CHECKER_MODEL = "claude-haiku-4-5"
CHECKER_TIMEOUT_SECONDS = 120
ALLOWED_TOOLS = "Read,Grep"


class CheckerError(Exception):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _build_prompt(ac: str, ctx: Dict[str, Any]) -> str:
    task = ctx.get("task") or {}
    payload = ctx.get("dispatch_payload") or {}
    log_tail = ctx.get("execution_log_tail") or ""
    log_path = ctx.get("execution_log_path") or ""

    # Lista enumerada dos paths exatos disponiveis pra source citation.
    # Drafter DEVE escolher destes (hallucination guard valida).
    valid_paths: list = []
    if log_path:
        valid_paths.append(log_path)
    files_block = ""
    for f in (ctx.get("files_relevant") or [])[:10]:
        valid_paths.append(f["path"])
        files_block += f"\n### {f['ref']} (path: {f['path']})\n\n```\n{f['content'][:4000]}\n```\n"
    if not files_block:
        files_block = "(nenhum file_relevant resolvido)"

    spec_block = ""
    for r in (ctx.get("spec_refs") or [])[:5]:
        valid_paths.append(r["path"])
        spec_block += f"\n### {r['ref']} (path: {r['path']})\n\n```\n{r['content'][:2000]}\n```\n"
    if not spec_block:
        spec_block = "(sem spec_refs)"

    valid_paths_block = "\n".join(f"- `{p}`" for p in valid_paths) or "(nenhum)"

    prompt = f"""Voce eh tester-agent do OpenClaw. Valide se a Acceptance Criterion (AC) abaixo
foi cumprida pela execucao do dispatcher. Use APENAS evidencia do execution log,
files_relevant e spec_refs (read-only).

NAO opine sobre qualidade, elegancia, ou design. Apenas valida cumprimento
objetivo da AC.

## Task

- id: {task.get("id", "")}
- title: {task.get("title", "")}
- goal: {payload.get("goal", "")[:300]}

## AC sob avaliacao

{ac}

## Execution log (path: {log_path})

```
{log_tail[:8000]}
```

## Files relevant

{files_block}

## Spec refs (resumo)

{spec_block}

## Paths VALIDOS pra source citation (escolha destes)

{valid_paths_block}

## Formato OBRIGATORIO da resposta

Responda EXATAMENTE neste formato JSON (e nada alem disso; zero prose fora do JSON):

```json
{{
  "status": "pass" | "fail" | "inconclusive",
  "evidence": "<excerpt curto do log/file que justifica>",
  "sources": ["<path>", "<path with line>"],
  "structural_concern": "<motivo se detectar task_malformed/spec_inconsistent/inexecutable/requires_re_decomposition; vazio se nao>"
}}
```

Regras:
- `pass`: evidencia clara no log/files que AC foi cumprida.
- `fail`: evidencia clara que AC NAO foi cumprida (ex: arquivo nao criado, exit nao-zero no log).
- `inconclusive`: log/files nao tem evidencia explicita pro AC. NAO chute.
- `structural_concern`: preencha SE perceber que AC contradiz spec_refs OR eh ambigua a ponto de
  inviabilizar checagem. Caller usara pra propor rejected.
- **Sources OBRIGATORIO formato**: cada source deve ser um path EXATO da lista
  "Paths VALIDOS" acima. Pode adicionar `:N` pra apontar linha (ex: `{log_path}:42`).
  NAO escreva descricoes naturais como "execution log line 4" ou "log".
  Use o path completo como mostrado acima.
"""
    return prompt


def _parse_response(raw: str) -> Dict[str, Any]:
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if m:
        block = m.group(1)
    else:
        start = raw.find("{")
        if start == -1:
            raise CheckerError("PARSE_NO_JSON", f"output sem JSON: {raw[:300]}")
        end = raw.rfind("}")
        if end == -1 or end <= start:
            raise CheckerError("PARSE_NO_JSON", f"JSON malformado: {raw[:300]}")
        block = raw[start : end + 1]
    try:
        parsed = json.loads(block)
    except json.JSONDecodeError as e:
        raise CheckerError("PARSE_JSON_INVALID", f"{e}: {block[:300]}")
    for field in ("status", "evidence", "sources"):
        if field not in parsed:
            raise CheckerError("PARSE_MISSING_FIELD", f"field '{field}' ausente")
    if not isinstance(parsed["sources"], list):
        parsed["sources"] = [str(parsed["sources"])]
    parsed.setdefault("structural_concern", "")
    return parsed


def _scan_capability_missing(execution_log: str) -> Optional[str]:
    """Retorna primeiro capability marker no log (ou None).

    Convention canonica: agente escreve `CAPABILITY_MISSING: <name>` no
    stdout quando bate em capability fora do env (e.g., docker daemon
    inacessivel). Tester-agent detecta e emite inconclusive em vez de
    fail.
    """
    if not execution_log:
        return None
    for line in execution_log.splitlines():
        stripped = line.strip()
        if stripped.startswith("CAPABILITY_MISSING:"):
            name = stripped.split(":", 1)[1].strip()
            if name:
                return name
    return None


def check_ac(
    ac: str, ctx: Dict[str, Any], model: str = CHECKER_MODEL,
) -> Dict[str, Any]:
    """Invoca claude -p pro AC. Retorna dict raw (status, evidence, sources, structural_concern).

    Pre-scan CAPABILITY_MISSING:
    Se o execution log declarou capability ausente, short-circuit pra
    inconclusive + structural_concern, sem chamar drafter LLM.
    """
    cap_missing = _scan_capability_missing(ctx.get("execution_log_tail", ""))
    if cap_missing is not None:
        return {
            "status": "inconclusive",
            "evidence": f"executor declarou CAPABILITY_MISSING: {cap_missing}",
            "sources": [],
            "structural_concern": f"capability_required:{cap_missing}",
            "raw_response": "",
            "drafter_model": model,
        }
    prompt = _build_prompt(ac, ctx)
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--model", model,
             "--allowedTools", ALLOWED_TOOLS],
            capture_output=True, text=True, check=False,
            timeout=CHECKER_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise CheckerError("CLAUDE_SUBPROCESS_FAILED",
                          f"{type(e).__name__}: {e}")
    if result.returncode != 0:
        raise CheckerError(
            "CLAUDE_EXIT_NONZERO",
            f"exit={result.returncode} stderr={result.stderr[:200]}",
        )
    parsed = _parse_response(result.stdout)
    parsed["raw_response"] = result.stdout[:5000]
    parsed["drafter_model"] = model
    return parsed
