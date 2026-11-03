<!-- Agent file do Tester Agent — wave-3 do PRD orchestration.
     Hub-dispatch L1 invocado pelo dispatcher (foreground only) OR
     manualmente por Bernard (qualquer modo).
     Spec canonica: 35_specs/2026-04-19-e10-tester-agent.md
-->

# Agent: tester-agent

> Runbook canonico. Spec: `35_specs/2026-04-19-e10-tester-agent.md`.
> Design: `30_adr/ADR-003-agent-governance.md`. Policy:
> `30_adr/ADR-006-autonomy-permissions-approval.md`. Metadata:
> `20_architecture/agents/registry.yml`.

- **Owner:** <!-- DERIVED --> Bernard
- **Status:** <!-- DERIVED --> ativo
- **Level:** <!-- DERIVED --> L1
- **Modelo padrao:** <!-- DERIVED --> stdlib-python/no-model (invoca claude -p subprocess)
- **Modelo fallback:** <!-- DERIVED --> none
- **Criado em:** <!-- DERIVED --> 2026-04-19

## Missao

Validar tasks em `testing` operacionalmente: 5 invariantes
deterministicos antes de invocar LLM, depois 1 check via `claude -p`
(allowedTools=Read,Grep) por AC; aplicar decisao final no kanban
SEM auto-rejeicao (proposes only).

Decisoes:
- All AC pass + invariantes OK → `testing → done` (auto)
- ≥1 AC fail (reparable) → `testing → in_progress` blocked
  `test_failed: <ac>`
- ≥1 AC inconclusive → `testing → in_progress` blocked
  `test_inconclusive: <reason>`
- Structural concern detectado → exit 3 + escalation file (Bernard
  `--commit` com categoria valida pra mover rejected)

Tester eh **gate de validacao operacional**, NAO juiz de produto.
Valida AC explicita determinanticamente; nunca opina sobre qualidade
subjetiva.

## Inputs

- **Auto-invocacao**: pelo dispatcher SOMENTE em modo foreground
  (`vox dispatcher next --launch --foreground`) apos
  `auto_move_to_testing`. Skip via `--no-tester` (debug).
- **Detached default NAO auto-invoca tester** (limitacao MVP wave-3
  §10.2 da spec; follow-up daemon reaper §16). Em detached, a task
  para em `testing` ate Bernard rodar `vox tester check <id>` manual.
- **Manual**: `vox tester check <task-id>` (qualquer momento, qualquer
  task em testing — funciona em ambos os modos).
- **Recheck**: `vox tester recheck <task-id>` (apos edit; novo seq).

## Outputs

- `~/.openclaw/tester-agent/test_runs/<task-id>-tr-<seq>.json`
  (per-test-run audit; prechecks + per-AC checks + decision)
- `~/.openclaw/tester-agent/escalations/<task-id>-tr-<seq>.md`
  (apenas pra structural reject proposed)
- Kanban mutations:
  - Pass: `task move <id> done --actor tester`
  - Fail/inconclusive: `task move <id> in_progress --actor tester` +
    `task block <id> --reason "test_failed|test_inconclusive: ..."`
  - Reject (Bernard `--commit`): `task unblock <id>` (idempotente) +
    `task move <id> rejected --reason "<cat>: ..."` (F4 wave-3 enforce
    `MUST_UNBLOCK_BEFORE_TERMINAL`; tester unblock antes do move
    terminal)
  - Sempre: `task set-dispatch-payload <id> --merge --payload {test_result: {...}}`

### Shape do `test_result` em `dispatch_payload`

Shallow merge top-level (slot reservado F4 wave-3, write-path unico):

```jsonc
{
  "test_result": {
    "last_test_run_id": "T-NNNN-tr-N",
    "last_test_run_path": "~/.openclaw/tester-agent/test_runs/T-NNNN-tr-N.json",
    "last_test_overall": "pass" | "fail" | "inconclusive" | "structural_reject_proposed",
    "last_test_decision": "done" | "in_progress_test_failed" | "in_progress_test_inconclusive" | "proposed_rejected" | "in_progress_test_failed_precheck",
    "last_test_finished_at": "...Z",
    "test_run_count": <int>,
    "tester_actor": "tester"
  }
}
```

Zero campo autoral do scrum-master (goal, AC, files_relevant) ou
dispatcher (briefing_path, execution_*) eh tocado.

## Skills

- Subprocess `claude -p --allowedTools "Read,Grep"` (drafter, Plano B
  Spike-5, herda padrao validado wave-2).
- Read filesystem (execution log + files_relevant + spec_refs).
- Subprocess `~/.openclaw/kanban-tasks/cli.sh task` (state machine).

## Limites

1. **NUNCA auto-rejeita.** Structural fail → exit 3
   (`TESTER_PROPOSES_REJECTION`); commit terminal sempre via Bernard
   `--commit` com categoria valida.
2. **NUNCA auto-relaunch.** Dispatcher relaunch eh Bernard-only.
3. **5 invariantes obrigatorios** pra auto-promote done:
   `task.status==testing` + `task.blocked==false` + execution log
   non-empty + zero clarification escalation aberta + AC nao-vazio.
4. **`inconclusive` NUNCA promove.** Sempre vira `in_progress` blocked
   `test_inconclusive: <reason>`.
5. **`dispatch_payload.test_result` isolado** em shallow merge top-level.
   Nao toca em campos autorais do scrum-master nem do dispatcher.
6. **Auto-invoke condicional ao modo:** APENAS em foreground.
   - `vox dispatcher next --launch --foreground` → auto-invoca tester
     apos `auto_move_to_testing` (zero-touch ate `done` no happy path).
   - `vox dispatcher next --launch --foreground --no-tester` →
     foreground sem auto-tester (debug).
   - `vox dispatcher next --launch` (detached default) → **NAO** invoca
     tester nesta wave; task para em `testing` ate Bernard rodar
     `vox tester check <id>` manual. Limitacao MVP §10.2 da spec;
     follow-up daemon reaper §16.
7. **One-task-per-project**: respeitado quando invocado standalone
   (1 task por invocacao). Concorrencia so se Bernard invocar paralelo.
8. **Read-only allowedTools**: drafter usa apenas `Read,Grep`. Nunca
   `Edit/Write/Bash`.
9. **Categorias rejection fechadas**: `task_malformed`,
   `spec_inconsistent`, `requires_re_decomposition`, `inexecutable`,
   `manual`. Outras strings rejeitadas com `INVALID_REJECT_CATEGORY`.
10. Hard limits gerais (ADR-006) aplicam.

## Approvals

- **Auto-promote done**: sem approval card (gate dispensado pelos 5
  invariantes + hallucination guard de sources).
- **Auto-block fail/inconclusive**: sem approval card (operacao
  reversivel; Bernard pode override via kanban manual).
- **Reject-task**: EXIGE flag `--commit` humano explicit.
- Hard limits gerais (ADR-006) aplicam.

## KPIs

- Test_runs/semana.
- Taxa auto-promote done / total runs.
- Taxa test_failed / total runs (alto = sinal de executor pobre OR AC
  ralo do scrum-master).
- Taxa test_inconclusive / total runs (alto = sinal de AC mal escrita
  OR log incompleto OR drafter prompt fraco).
- Taxa proposed_rejected / total runs (alto = sinal de plan→spec
  drift; scrum-master pode estar produzindo tasks sem checagem com
  canonical).
- Taxa override Bernard kanban manual (apos test_inconclusive) /
  total inconclusive (alto = sinal que confidence binary ta calibrado
  conservador demais).

## Playbook operacional

### 1. Registrar dispatch
Append em `~/.openclaw/workspace/shared/outputs/agent-dispatch.jsonl`.

### 2. Prechecks (5 invariantes)
- task em testing + nao-blocked
- execution log existe e nao-vazio
- acceptance_criteria nao-vazio
- nenhuma clarification escalation aberta
Se algum falha: precheck-failure path (block test_failed: precheck_X).

### 3. Context loader
- Le task via `cli.sh task show <id> --json`
- Le execution log tail (8000 chars) de
  `~/.openclaw/dispatcher-agent/executions/<id>.log`
- Le files_relevant (head 4000 chars cada, max 10)
- Le spec_refs (head 2000 chars cada, max 5)

### 4. Per AC LLM check
- `claude -p` com prompt estruturado §10.3 da spec
- allowedTools="Read,Grep" (read-only)
- Model default: claude-haiku-4-5
- Parse JSON: `{status, evidence, sources, structural_concern}`
- **Refinamento wave-3.5 (prompt source citation)**: prompt enumera
  explicitamente os paths VALIDOS pra source citation (execution_log
  path absoluto + files_relevant + spec_refs paths) e instrui drafter
  a usar path EXATO (com sufixo opcional `:N` pra linha) em vez de
  descricoes naturais ("execution log line 4", "log"). Resolve drift
  identificado no smoke E2E da wave-3.5 cenario 1 onde drafter haiku
  citava texto descritivo, safety guard derrubava `pass` para
  `inconclusive`. Fix vive em
  `~/.openclaw/tester-agent/lib/checker.py::_build_prompt`. Safety
  guard em si NAO foi relaxado (mantido strict). Veja spec
  `35_specs/2026-04-19-e10-detached-reaper.md` §13 (loop corretivo).

### 5. Safety enforce
- Valida sources existem (no contexto OU filesystem)
- Pass + zero sources fornecidas → downgrade `no_sources` → inconclusive
- Pass + todas sources alucinadas → downgrade `hallucination_guard` → inconclusive
- Pass + algumas alucinadas → downgrade `hallucination_guard` → inconclusive
- structural_concern fora das 4 categorias validas → drop

### 6. Aggregate decision
- All pass + zero structural → `decision=done`
- Any fail (sem structural) → `decision=in_progress_test_failed`
- Any inconclusive (sem fail/structural) →
  `decision=in_progress_test_inconclusive`
- Any structural → `decision=proposed_rejected` (NAO move kanban)

### 7. Apply kanban + merge test_result
- Done: `task move done --actor tester`
- Fail/inconclusive: `task move in_progress` + `task block --reason`
- Proposed_rejected: write escalation file + exit 3
- Sempre: `task set-dispatch-payload --merge --payload {test_result}`

### 8. Human intervention (Bernard)
- `vox tester reject-task <id> --reason "<cat>: ..." --commit`:
  valida categoria + `task unblock` idempotente + `task move rejected`
  + clear escalation
- `vox tester recheck <id>`: re-roda check (novo seq)
- Override manual (override done apesar de fail/inconclusive):
  `~/.openclaw/kanban-tasks/cli.sh task unblock <id>` +
  `task move <id> done --actor bernard`

## Boundary com outros agents

Ver §9 + §13 da spec. Tester **NAO**:
- Seleciona task (responsabilidade do dispatcher).
- Gera briefing (responsabilidade do dispatcher).
- Move pra `rejected` autonomamente (sempre via Bernard `--commit`).
- Relaunch (responsabilidade do dispatcher; Bernard inicia).
- Modifica `dispatch_payload` autoral (goal, AC, files_relevant, etc.).
- Auto-invoca em modo detached (limitacao MVP wave-3; §10.2 da spec).
- Multi-round chain numa mesma testing entry (cada testing pass
  isolado; relaunch cria novo dispatcher run + novo testing).

## Touch model (resumo por modo)

| Modo dispatcher | Cenario | Touches Bernard |
|---|---|---|
| `--launch --foreground` | All pass | **1** (kick off) |
| `--launch --foreground` | Test fail/inconclusive | 2 (kick + relaunch ou reject) |
| `--launch --foreground` | Proposed rejected | 2 (kick + `reject-task --commit`) |
| `--launch` (detached default) | All pass | **2** (kick + `vox tester check`) |
| `--launch` (detached default) | Worst case | 4-5 |

Ver §11 da spec para detalhes.

## Volume minimo

- Manter L1: pelo menos 1 invocacao/mes.
- Promocao L2 (ADR-003): pelo menos 5/sem por 4 sem consecutivas, taxa
  auto-promote done ≥ 60%, zero rejection autonoma (sempre via Bernard
  `--commit`), zero overrides manuais Bernard de test_inconclusive em
  10 runs (sinal que confidence binary ta calibrado).

## Historico de levels

- L1 desde 2026-04-19.
