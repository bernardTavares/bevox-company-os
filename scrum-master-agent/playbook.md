<!-- Agent file do Scrum Master Agent — primeira wave do PRD
     "OpenClaw Task-Orchestrated Development for Claude Code".
     Criado a partir de _template.md (E3) + pattern Hub-dispatch
     estabelecido por delivery-status-agent (2026-04-17).

     Modo operacional: Hub-dispatch supervisionado (ver CREATING.md §7.3).
     Spec canonica: 35_specs/2026-04-19-e10-scrum-master-agent.md
     (canonizada em 2ac8527).
     Design canonico: 30_adr/ADR-003-agent-governance.md.
     Policy canonica: 30_adr/ADR-006-autonomy-permissions-approval.md.

     Identidade canonica: scrum-master-agent.
     Agente entrando em L1 novo (nao formalizacao retroativa).
     Zero TBDs pendentes — todos os campos preenchidos.
-->

# Agent: scrum-master-agent

> Runbook canonico do Scrum Master Agent. Spec:
> `35_specs/2026-04-19-e10-scrum-master-agent.md`. Design:
> `30_adr/ADR-003-agent-governance.md`. Policy de autonomia:
> `30_adr/ADR-006-autonomy-permissions-approval.md`. Source of truth
> dos campos de metadata: `20_architecture/agents/registry.yml`.

- **Owner:** <!-- DERIVED: registry.yml -> agents.scrum-master-agent.owner --> Bernard
- **Status:** <!-- DERIVED: registry.yml -> agents.scrum-master-agent.status --> ativo
- **Level:** <!-- DERIVED: registry.yml -> agents.scrum-master-agent.level --> L1
- **Modelo padrao:** <!-- DERIVED: registry.yml -> agents.scrum-master-agent.model.primary --> stdlib-python/no-model
- **Modelo fallback:** <!-- DERIVED: registry.yml -> agents.scrum-master-agent.model.fallback --> none
- **Criado em:** <!-- DERIVED: registry.yml -> agents.scrum-master-agent.since --> 2026-04-19

## Missao

Projetar implementation plans (produto de `superpowers:writing-plans`)
em tasks operacionais do `kanban-tasks` host-local, preservando metadata
via `dispatch_payload` estruturado. Agente eh **coordenador**; NAO
escreve codigo, NAO executa tasks.

Modo operacional: **L1, manual-invoke, supervisionado** (Hub-dispatch).
Sem scheduler proprio. Sem runtime persistente. Cada invocacao eh
explicita do Bernard via CLI ou Vox carregando o playbook.

## Inputs

- **Invocacao explicita do Bernard** (forma unica nesta wave):
  `vox scrum-master propose --plan <slug-ou-path>` OU
  `~/.openclaw/scrum-master-agent/cli.sh propose --plan <slug>`.
- **Plan file obrigatorio** em `~/.openclaw/docs/superpowers/plans/`
  (produto de `superpowers:writing-plans`). Header obrigatorio:
  `**Epico:** <epic-id>/<wave-slug>`. Sem header valido, agente
  recusa com `PLAN_MISSING_EPIC`.

## Outputs

- **Proposal JSON estruturada** em
  `~/.openclaw/scrum-master-agent/proposals/<timestamp>-<slug>.json`
  (shape conforme spec §7). Escrita atomica via `tmpfile + rename`.
- **Nenhuma mutacao direta** em bevox-knowledge, delivery-tracker,
  ou qualquer arquivo canonico.
- **Apos `accept` humano**, materializacao no kanban-tasks via CLI
  existente + subcmd `task set-dispatch-payload` (enabling delta ja
  entregue na mesma wave desta spec).
- **Linha de dispatch** em `~/.openclaw/workspace/shared/outputs/
  agent-dispatch.jsonl` (pattern herdado de `delivery-status-agent`).

## Skills

- Leitura de plan + spec canonica (referenciada no plan header) +
  `delivery-tracker.yml` + ADRs citadas (read-only).
- Shell tool pra invocar `~/.openclaw/kanban-tasks/cli.sh` via
  subprocess no accept flow.
- `git` read (log) no clone de `bevox-knowledge` pra capturar
  `plan_sha` da proposta.
- Nenhuma skill externa nova. Zero pip install.

## Limites

1. **UMA proposta por invocacao.** Cada `propose` gera `proposal_id`
   unico (timestamp + plan_slug). Reinvocacao com mesmo plan =
   proposal_id diferente.
2. **Accept all-or-nothing.** Sem partial accept. Se falhar no meio
   (erro em task N de total), proposta entra em estado `partial` e
   **retry cego fica bloqueado** (`PROPOSAL_PARTIALLY_MATERIALIZED`).
   Cleanup = operador arquiva tasks criadas + cria nova proposta.
3. **Rejeicao + reproposta** eh o caminho pra ajustar composicao.
   Sem edicao de proposal in-place.
4. **Escrita estritamente local.** Proposals em
   `~/.openclaw/scrum-master-agent/proposals/`. Tasks materializadas
   em `~/.openclaw/kanban-tasks/` via CLI existente. **NAO muta
   canonico** (bevox-knowledge inteiro read-only).
5. **Input plan obrigatorio.** `superpowers:writing-plans` skill eh
   pre-requisito. Spec canonica SEM plan = recusa `PLAN_NOT_FOUND`
   ou `PLAN_MISSING_EPIC`.
6. **NUNCA inventa acceptance_criteria.** Extrai de `Expected:` lines
   do plan. Ausencia vira AC omitida (campo dispatch_payload sem a key).
7. **NUNCA reexecuta propose idempotente.** Cada invocacao cria novo
   proposal_id. Rejeicao de proposals antigos fica com Bernard.
8. **NUNCA materializa sem preflight completo.** Se qualquer check
   falhar (proposal state, plan drift, target sprint, projects,
   titles, payload shape), zero side effect no kanban.
9. Hard limits gerais (ADR-006 §"Hard Limits") aplicam.

## Explicitamente fora desta wave

Comportamentos NAO cobertos por este agente (ficam pras proximas
waves do PRD "OpenClaw Task-Orchestrated Development", cada uma com
spec propria):

- **Scheduler/cron de propose automatico** — toda invocacao eh manual.
  `cron restrito` (wave-4 PRD) fora de escopo.
- **Dispatcher** — escolher proxima task `ready` e despachar pro
  Claude Code eh o `dispatcher-agent` (wave-2 PRD), spec separada.
- **Tester** — validar tasks em `testing` e mover pra `done`/
  `in_progress`/`rejected` eh o `tester-agent` (wave-3 PRD), spec
  separada.
- **Auto-ready** — tasks nascem `backlog` por default. Flag `--ready`
  no accept eh escape ergonomico; Bernard decide. Auto-promocao de
  `backlog -> ready` sem acao humana fora de escopo.
- **Auto-merge / auto-close de wave/spec / auto tracker flip** —
  gates humanos preservados (PRD §10 FR-10).
- **Multi-plan merge** — 1 proposta = 1 plan. Fundir N plans numa
  unica proposta fica pra wave futura se dor real aparecer.
- **Resume parcial** — proposta em estado `partial` NAO eh retryable;
  operador limpa manualmente e cria nova proposta. Cmd `resume`
  fica pra wave futura se dor real aparecer.
- **UI dedicada pra revisar proposals** — CLI-only nesta wave. UI
  MC fica pra follow-up se demanda real aparecer.
- **Enforcement de `depends_on`** — kanban wave-3 nao tem dep
  enforcement; scrum-master registra deps em
  `dispatch_payload.depends_on` como metadata advisory (quando
  presente), sem bloqueio runtime.

## Approvals

Modo Hub-dispatch supervisionado; sem sessao runtime propria, sem
entry em `exec-approvals.json`, sem listener E4.1/E4.2.

**Gate unico:** `vox scrum-master accept <id>` (CLI explicito do
Bernard). Nao usa knowledge-sync canonical flow (proposal eh
host-local, nao muta canonico; materializacao eh operacional via
`kanban-tasks/cli.sh`).

Hard limits gerais do Vox (ADR-006 §"Hard Limits") aplicam em cima
deste playbook. Playbook nao concede autonomia adicional.

Dispatch de cada invocacao registrado em
`~/.openclaw/workspace/shared/outputs/agent-dispatch.jsonl`.

## KPIs

- **Proposals geradas por semana**: arquivos em `proposals/` com
  `state.proposed_at` em janela de 7 dias.
- **Taxa de acceptance**: `state.accepted_at != null` / total proposals
  (exclui `partial`).
- **Time-to-accept**: mediana de `(accepted_at - proposed_at)`.
- **Partial rate**: `state.partial_at != null` / total accepts. Alto
  = sinal de preflight insuficiente OU plans com shape ruim. Target
  < 5%.
- **AMBIGUOUS_PROJECT rate**: fraction de `propose` que falha com esse
  codigo. Alto = plans mal formados ou path map canonico desatualizado.
- **`--project-override` usage**: > 30% sustentado = review do
  playbook ou dos plans producers.
- **Frequencia de revisao**: mensal. Primeira revisao 2026-05-19.

## Playbook operacional

### Passo 1 — Registrar dispatch

Append em `~/.openclaw/workspace/shared/outputs/agent-dispatch.jsonl`:

```json
{
  "ts": "<ISO8601 UTC>",
  "playbook": "scrum-master-agent",
  "source": "explicit",
  "request_summary": "propose from plan <slug>",
  "session_id": "<canal ou null>"
}
```

Single-writer append (bash `>>`). Este passo fica eventualmente
automatizado pela skill `scrum-master-agent`; por enquanto, invocacao
manual via CLI tambem conta como explicit dispatch (agente registra
linha no append ao receber o cmd `propose`).

### Passo 2 — Resolver plan

`cli.sh propose --plan <arg>`. Arg pode ser:
- slug sem extensao: tenta `PLANS_DIR/<slug>.md`.
- path absoluto: usa direto se existir.
- nao resolve: `PLAN_NOT_FOUND`.

### Passo 3 — Parsear plan (host-local)

`lib/parser.py` extrai (spec §4.3):
- Header: Goal (opcional), Epico (OBRIGATORIO), Project/Projects
  (opcional), Tech Stack (opcional), Specs canonicas (refs).
- Phases: `^## Phase N: Name`. Sem nenhuma, `NO_PHASES_FOUND`.
- Tasks: `^### Task N.M: Subject`. Sem, `NO_TASKS_FOUND`.
- Per-task: Files block, Steps, Expected lines.

Falhas sao explicitas (erro + codigo), nao best-effort.

### Passo 4 — Derivar project (per-task)

Rules deterministicas (spec §5.3):
1. plan-level `**Project:**` single -> todas tasks.
2. per-task path map canonico (`lib/projects.py:PATH_MAP`) -> exactly
   1 project resolvido wins.
3. `--project-override` escape com warning + audit no `_warnings`.
4. Nada resolvido -> `AMBIGUOUS_PROJECT` com listing dos ids
   afetados.

Adicional: valida que todos os projects resolvidos existem em
`~/.openclaw/kanban-tasks/projects.yml` canonico; senao
`UNKNOWN_PROJECT` com lista de nomes faltando.

### Passo 5 — Montar proposal (shape §spec 7)

`lib/proposer.py` cria proposal JSON:
- `wave_ref_root = <plan.epic>/<plan.wave>` (ex `E5/F4-kanban-dev-lifecycle`)
- `task.wave_ref = <wave_ref_root>/Phase-<N>` — aponta pra **wave do
  trabalho**, nao pra wave do agente (AJUSTE #1 da spec).
- `task.dispatch_payload` com shape fixo:
  - `goal` (obrigatorio)
  - `spec_refs` (obrigatorio; pode ser lista vazia)
  - `plan_ref` (obrigatorio)
  - `plan_anchor` (obrigatorio)
  - `acceptance_criteria` (opcional; omitido se plan nao tem Expected:)
  - `files_relevant` (opcional; omitido se Files block vazio)
  - `out_of_scope`, `guardrails`, `depends_on` (opcionais; agente nao
    auto-infere; Bernard adiciona manual via
    `kanban-tasks/cli.sh task set-dispatch-payload ... --merge`)
- `plan_sha` via `git log -1 <plan>` (null se fora de git).

### Passo 6 — Escrever proposal

`~/.openclaw/scrum-master-agent/proposals/<proposal_id>.json` atomic
(tmpfile + rename).

### Passo 7 — Retornar summary

Print `proposal_id`, total_tasks, total_phases, epic_id, warnings.

### Accept flow

Invocado por cmd separado (`cli.sh accept <id>`). Pipeline:

**Regra dura:** bootstrap de sprint de implementacao nao deve ser feito
com `task.created` manual ad-hoc fora deste fluxo. Se a intencao eh
materializar trabalho derivado de PRD/roadmap/implementation plan, o
caminho correto eh `propose` + `accept`, para preservar epic/wave_ref,
plan_ref, plan_anchor, spec_refs e acceptance_criteria no payload.

1. **Preflight** (sem tocar kanban):
   - state: accepted/rejected/partial = erro claro.
   - plan drift: `plan_sha` atual vs salvo; se mudou sem
     `--force-plan-drift`, erro.
   - `target_sprint` resolve no `state.json` do kanban.
   - projects do proposal existem em `projects.yml`.
   - titles non-empty.
   - dispatch_payload shape (required keys + no invented).
2. **Materializacao sequencial** via `kanban-tasks/cli.sh`:
   - `task add ... --payload '{spec_ref,acceptance_criteria}'` — payload
     minimo pra satisfazer gate wave-4 E10/OH; captura real `T-NNNN`.
   - `task set-dispatch-payload <T-NNNN> --payload <json-completo>` —
     full payload (com `depends_on` ja resolvido) em replace default.
   - `task move <T-NNNN> ready` se `--ready`.
   - Resolve `depends_on` provisional -> real via mapping local antes do
     set-dispatch-payload.
   - **Invariante operacional:** sempre preservar `acceptance_criteria`
     dentro de `dispatch_payload` durante materializacao e merges
     posteriores. Nao confiar no campo top-level `task.acceptance_criteria`
     para satisfazer precheck do tester.
   - **Checklist de saida obrigatorio por task materializada:**
     `project`, `epic`, `wave_ref` (ou wave equivalente adotada pelo
     fluxo), `dispatch_payload.spec_ref/spec_refs`,
     `dispatch_payload.plan_ref`, `dispatch_payload.plan_anchor` e
     `dispatch_payload.acceptance_criteria` presentes antes de marcar a
     task como pronta para dispatcher.
3. **Sucesso**: escreve `accepted_at`, `accepted_by`,
   `materialized_task_ids`. Unico ponto de gravacao `accepted_at`.
4. **Falha no meio**: grava `partial_at`, `partial_by`,
   `materialized_task_ids` (parcial), `partial_failure = {provisional_id,
   index, step, error}`. Raise `PARTIAL_MATERIALIZATION`. Retry bloqueado.

## Dependency projection (wave-6)

Scrum-master projeta `blocked_by` automaticamente via 2 fontes:

1. **Phase-sequence default (implicit)**: cada task de Phase N+1 depende
   da ULTIMA task de Phase N.
2. **`**Depends:**` override (explicit)**: linha no body da task lista
   labels de preds: `**Depends:** Task 1.1, Task 2.3`.

Flag `--dependency-mode {phase-sequence,explicit,hybrid}` default hybrid:
- `hybrid`: phase-sequence como base + override substitui por task com
  `**Depends:**` linha.
- `phase-sequence`: ignora overrides; só sequência de fases.
- `explicit`: exige `**Depends:**` em toda task non-initial; erro caso
  ausente.

Cross-phase references aceitos: `**Depends:** Task 1.1 (Phase 1)` — parser
strip parenthetical suffix antes de resolver label.

Cycle detect + gate self-check (spec_ref + acceptance_criteria) rodam
ANTES de submeter proposal. Errors: `CYCLE_DETECTED`,
`EXPLICIT_MODE_MISSING_OVERRIDE`, `GATE_CHECK_FAILED`.

Materialização 2-step:
1. `task add --payload '{spec_ref, ac}'` (wave-4 gate).
2. `task set-dispatch-payload <id> --payload '{full com blocked_by
   resolved}'` — wave-5 gate em set_dispatch_payload valida ciclo +
   pred existence.

**Guardrail anti-regressao:** se o payload completo for reescrito, ele
precisa continuar carregando `acceptance_criteria` em
`dispatch_payload.acceptance_criteria`. Se essa chave sumir, o tester
pode marcar a task como blocked em testing com
`precheck_failed: acceptance_criteria_non_empty`.

## Boundary com outros agentes

| Identidade | Dominio | Modo | Fonte |
|---|---|---|---|
| `delivery-agent` (E5) | propor work items derivados de specs | runtime proprio (systemd timer, L1 python stdlib) | spec E5 wave 1 |
| `delivery-status-agent` (E10) | flip status no `delivery-tracker.yml` | Hub-dispatch, single-gate via knowledge-sync | spec E10 delivery-status |
| `scrum-master-agent` (E10) | projetar plan -> tasks do kanban | Hub-dispatch, single-gate via `cli.sh accept` | esta spec |

**Tres identidades distintas, zero acoplamento.**

- `scrum-master-agent` NAO consome outputs do `delivery-agent` ou
  `delivery-status-agent`.
- `scrum-master-agent` NAO modifica `delivery-tracker.yml` (leitura
  read-only).
- Eventual reconciliacao entre dominios vira spec propria.

## Volume minimo

Volume minimo para manter L1: **pelo menos 1 proposal por mes**
(natural ou sintetico). Abaixo disso, Bernard reavalia (aposentar,
shadow mode, ou migrar behavior pra outro agente).

Promocao L1→L2 (ADR-003 §Fase 4): **pelo menos 2 proposals por
semana por 4 semanas consecutivas**, taxa accept ≥ 75%, zero
`PARTIAL_MATERIALIZATION` em 10 accepts consecutivos.

## Historico de levels

- L1 desde 2026-04-19.
