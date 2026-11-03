# Integration: tester-agent

> O **tester-agent** valida tasks no estado `testing` operacionalmente.
> Gate de validação determinística (5 invariantes + 1 LLM check por AC),
> NÃO juiz de produto. Auto-invocado pelo dispatcher só em modo foreground.

## Decisões possíveis

| Resultado | Transição | Quando |
|---|---|---|
| All AC pass + invariantes OK | `testing → done` (auto) | sucesso completo |
| ≥1 AC fail (reparable) | `testing → in_progress` blocked `test_failed: <ac>` | falha clara, agente pode corrigir |
| ≥1 AC inconclusive | `testing → in_progress` blocked `test_inconclusive: <reason>` | falta evidência |
| Structural concern detectado | exit code 3 + escalation file (Bernard `--commit` apenas) | propõe rejeição; nunca auto-rejeita |

## CLI cheatsheet

```bash
TESTER=~/.openclaw/tester-agent/cli.sh

# Validar uma task agora (aplica decisão)
$TESTER check <task-id>

# Dry-run: gera test_run JSON, NÃO move kanban
$TESTER check <task-id> --no-act

# Re-validar após edit manual (gera novo seq)
$TESTER recheck <task-id>

# Listar resultados
$TESTER results [--all|--failed|--inconclusive|--proposed-rejection]
$TESTER show <task-id>

# Aceitar uma rejeição proposta (Bernard apenas)
$TESTER reject-task <task-id> --reason "<categoria>: ..." --commit
```

## Quando o tester é invocado

```bash
# Dispatcher foreground: AUTO-invoca tester após auto-move pra testing
~/.openclaw/dispatcher-agent/cli.sh next --launch --foreground

# Dispatcher detached (default): NÃO invoca tester; reaper move pra testing
~/.openclaw/dispatcher-agent/cli.sh next --launch
```

Em modo detached, eu (Voz dedicado) ou Bernard invoca o tester manualmente
quando a task chega em `testing`.

## Exit codes

- `0`: done auto OR devolveu in_progress (blocked test_failed/inconclusive)
- `1`: input inválido (TASK_NOT_FOUND, INVALID_REJECT_CATEGORY)
- `2`: precheck infraestrutural falhou (sem log, sem AC)
- `3`: TESTER_PROPOSES_REJECTION (estrutural; precisa Bernard `--commit`)

## Princípios

- Tester valida AC explícita determinanticamente
- Nunca opina sobre qualidade subjetiva
- Nunca auto-rejeita; rejeição estrutural precisa de Bernard
- LLM check usa `claude -p` com `allowedTools=Read,Grep` (read-only)
