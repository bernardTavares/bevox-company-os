"""Gera briefing.md estruturado a partir de dispatch_payload.

Shape segue convention §10.1 da spec. Embute instruction forte pra
Claude Code cooperar com `vox clarification ask --and-wait`.
"""

from pathlib import Path
from typing import Any, Dict, List

VOX_CLARIFICATION_CLI = f"{Path.home()}/.openclaw/clarification-agent/cli.sh"


def _fmt_bullets(items: List[str], empty_msg: str = "(nenhum)") -> str:
    if not items:
        return empty_msg
    return "\n".join(f"- {i}" for i in items)


def _fmt_specs(refs: List[str]) -> str:
    if not refs:
        return "(nenhuma spec referenciada)"
    return "\n".join(f"- `{r}`" for r in refs)


def _fmt_capabilities(caps: List[str]) -> str:
    """Bloco de capabilities requeridas + protocolo CAPABILITY_MISSING.

    Renderiza apenas se a task declarou requires_capability. Default vazio.
    """
    if not caps:
        return ""
    cap_list = ", ".join(f"`{c}`" for c in caps)
    return f"""

## Capabilities requeridas

Esta task pode requerer: {cap_list}

Se voce tentar usar uma destas capabilities e o ambiente bloquear (permission
denied, comando ausente, sock inacessivel, etc.), NAO finja cumprimento e NAO
invente evidencia. Escreva na saida (stdout) a linha canonica:

```
CAPABILITY_MISSING: <nome_da_capability>
```

E continue avaliando os outros ACs. O tester-agent detecta este marker e
emite `inconclusive` em vez de `fail`, abrindo clarification pra Bernard
decidir manualmente.
"""


def render_briefing(task: Dict[str, Any], allowed_tools: str) -> str:
    """Renderiza briefing.md a partir de task + flag allowed_tools literal."""
    task_id = task["id"]
    title = task.get("title", "")
    payload = task.get("dispatch_payload") or {}
    goal = payload.get("goal") or task.get("description") or title
    spec_refs = payload.get("spec_refs") or []
    plan_ref = payload.get("plan_ref") or ""
    plan_anchor = payload.get("plan_anchor") or ""
    ac = payload.get("acceptance_criteria") or []
    files_relevant = payload.get("files_relevant") or []
    out_of_scope = payload.get("out_of_scope") or []
    guardrails = payload.get("guardrails") or []
    requires_capability = payload.get("requires_capability") or []

    if ac:
        ac_block = "\n".join(f"- [ ] {c}" for c in ac)
    else:
        ac_block = "(nenhum AC explicito; infira dos spec_refs)"
    files_block = _fmt_bullets(
        files_relevant,
        "(nenhum file explicito; explore conforme necessario)",
    )
    oos_block = _fmt_bullets(out_of_scope, "(nada declarado fora de escopo)")
    guards_block = _fmt_bullets(
        guardrails, "(nenhum guardrail explicito; siga ADRs padrao)",
    )

    plan_line = f"**Plan:** `{plan_ref}`" + (
        f" (anchor: {plan_anchor})" if plan_anchor else ""
    )

    return f"""# Task {task_id} — {title}

{goal}

## Contexto canonico

**Spec(s):**
{_fmt_specs(spec_refs)}

{plan_line}

**Epic/Wave:** {task.get("epic_id", "?")} / {task.get("wave_ref", "?")}

## Objetivo

{goal}

## Acceptance criteria

{ac_block}

## Files relevantes

{files_block}

## Out of scope

{oos_block}

## Guardrails

{guards_block}{_fmt_capabilities(requires_capability)}

---

## INSTRUCOES OPERACIONAIS — LEIA ANTES DE EXECUTAR

Voce esta sendo invocado pelo dispatcher-agent do OpenClaw como executor
de uma task operacional. Convention OBRIGATORIA:

### Se encontrar duvida bloqueante

Se durante a execucao voce precisar de informacao que NAO esta neste
briefing nem nos spec_refs/plan_ref citados, e que NAO consegue inferir
com seguranca a partir do codigo existente, NAO INVENTE. Execute via
Bash:

```
{VOX_CLARIFICATION_CLI} ask {task_id} \\
    --question "<sua pergunta especifica>" \\
    --and-wait
```

O comando vai bloquear ate a resposta chegar. A resposta vira no stdout.
Use ela e continue.

### Se a resposta retornar com exit code 4 (CLARIFICATION_REJECTED_TASK)

Significa que Bernard decidiu rejeitar esta task. Encerre execucao
imediatamente; NAO commite mudancas parciais.

### Se concluir com sucesso

Encerre limpamente (exit 0). O dispatcher detecta seu exit code e move
a task pra `testing` automaticamente. NAO tente mover a task voce mesmo.

### Como reportar fechamento (IMPORTANTE — afeta o tester)

O tester-agent valida cada AC lendo SO o seu output (este log). Drafter
e conservador: se voce nao enumerar evidencia explicita, AC fica
`inconclusive` e a task vira `blocked`, exigindo intervencao manual.

Para cada AC do briefing acima, no resumo final, voce DEVE:

- **Tipos/enums:** listar valores literais (ex: `LayoutPosition = 'top-left' | 'top-center' | ... | 'bottom-right'` (9 valores)). Nao escrever "9 typed positions" — drafter nao consegue verificar.
- **Funcoes/constantes/refs:** citar `path:line` ou `path:start-end`. Ex: `lib/overlay.ts:12-30`.
- **Code changes:** listar paths exatos modificados/criados.
- **Commands rodados:** citar comando + resultado curto. Ex: `pnpm typecheck → 0 errors` ou `pytest tests/ → 47 passed, 0 failed`.
- **AC numerado:** referencie cada AC por seu texto (ou prefixo). Ex:
  ```
  AC1 (LayoutPosition 9 posicoes): types/scene.ts:5-15, enum literal:
       'top-left' | 'top-center' | 'top-right' | 'middle-left' |
       'center' | 'middle-right' | 'bottom-left' | 'bottom-center' |
       'bottom-right'
  AC2 (CopyCard mapping unico): components/overlay/CopyCard.tsx:42-55
       consome OVERLAY_POSITION_CLASSES de lib/overlay-position.ts:8-26
  AC3 (typecheck limpo): pnpm typecheck → exit 0, 0 errors
  ```

Resumos genericos ("done", "implemented X", "tests pass") fazem o
tester escalar como inconclusive. Evidencia explicita = AC pass.

### Tools permitidas nesta sessao

{allowed_tools}
"""
