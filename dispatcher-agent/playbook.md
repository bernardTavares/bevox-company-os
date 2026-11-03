<!-- Agent file do Dispatcher Agent — wave-2 do PRD orchestration.
     Modo: Hub-dispatch L1 supervisionado. Invoca Claude Code em
     background detached como executor.
     Spec canonica: 35_specs/2026-04-19-e10-dispatcher-and-clarification-agents.md
     Pareado com clarification-agent na mesma wave canonica.
-->

# Agent: dispatcher-agent

> Runbook canonico. Spec:
> `35_specs/2026-04-19-e10-dispatcher-and-clarification-agents.md`.
> Design: `30_adr/ADR-003-agent-governance.md`. Policy:
> `30_adr/ADR-006-autonomy-permissions-approval.md`. Metadata:
> `20_architecture/agents/registry.yml`.

- **Owner:** <!-- DERIVED --> Bernard
- **Status:** <!-- DERIVED --> ativo
- **Level:** <!-- DERIVED --> L1
- **Modelo padrao:** <!-- DERIVED --> stdlib-python/no-model (invoca claude CLI subprocess)
- **Modelo fallback:** <!-- DERIVED --> none
- **Criado em:** <!-- DERIVED --> 2026-04-19

## Missao

Selecionar proxima task `ready` no kanban-tasks, gerar briefing
estruturado a partir de `dispatch_payload`, invocar Claude Code como
subprocess detached (foreground disponivel pra debug), capturar output
em log persistente, detectar exit code, **auto-mover** `in_progress →
testing` em exit 0, marcar `blocked` com `execution_failed: <stderr>`
em exit != 0.

Agente coordena; **NAO escreve codigo**. Claude Code continua sendo
executor unico de codigo.

## Inputs

- Invocacao manual: `vox dispatcher next [--launch] [--project X]`
  OU `~/.openclaw/dispatcher-agent/cli.sh next ...`.
- Task `ready` nao-blocked no kanban-tasks (via scrum-master ou manual).
- `dispatch_payload` com `goal` no minimo (campos demais sao opcionais).
- Flag opcional `--foreground` (debug; auto-invoca tester apos
  `auto_move_to_testing` se sem `--no-tester`). Em detached default
  (`--launch` sem `--foreground`), tester **NAO** eh auto-invocado
  nesta wave (limitacao MVP wave-3 §10.2 do spec tester-agent).

## Outputs

- `~/.openclaw/dispatcher-agent/briefings/<task-id>.md`
- `~/.openclaw/dispatcher-agent/executions/<task-id>.log` +
  `<task-id>.status.json`
- Kanban mutations:
  - `task move <id> in_progress --actor dispatcher` (no `--launch`)
  - `task set-dispatch-payload <id> --merge --payload {dispatched_at,
    dispatcher_actor, briefing_path, dispatch_mode, execution_*}`
  - Pos-execucao automatico: `task move <id> testing --actor dispatcher`
    (exit 0) OR `task block <id> --reason "execution_failed: ..."` (exit != 0)
- Linha de dispatch em `~/.openclaw/workspace/shared/outputs/
  agent-dispatch.jsonl` (pattern herdado de outros E10 agents).
- Em foreground + tester auto-invocado: o status JSON retornado tambem
  carrega `tester_invoked=true` + `tester_result_summary`
  (test_run_id, overall, decision do tester). Em detached default:
  `tester_invoked=false` + `tester_skipped_reason` explicito.

## Skills

- Subprocess `claude -p` (executor real do codigo).
- Subprocess `~/.openclaw/kanban-tasks/cli.sh task` (state machine).
- `setsid + nohup` via Python `start_new_session=True` (detached).

## Limites

1. **UMA task por invocacao.** `--project` enforce: zero in_progress
   no projeto alvo (`WORK_IN_PROGRESS_LIMIT`).
2. **Auto-move APENAS** `in_progress → testing`. Nunca `→ done` nem
   `→ rejected`.
3. **`--allowed-tools` restritivo por default** (baseline em §10.2 da
   spec). Bernard pode override via flag.
4. **NAO invoca clarification-agent diretamente.** Claude Code (executor)
   invoca via Bash tool quando precisar (convention enforce-strong no
   briefing).
5. **NAO mexe em campos autorais do scrum-master** no `dispatch_payload`
   (goal, spec_refs, acceptance_criteria, files_relevant, guardrails,
   out_of_scope, plan_ref, plan_anchor, depends_on). Apenas merge de
   metadata runtime.
6. **Auto-invoke do tester-agent** apos `auto_move_to_testing`:
   APENAS em modo foreground (`--launch --foreground`). Default
   detached **NAO** invoca tester (limitacao MVP wave-3; ver §10.2
   do spec `35_specs/2026-04-19-e10-tester-agent.md`). Bernard usa
   `vox tester check <id>` manual depois. Flag `--no-tester`
   desativa auto-invoke mesmo em foreground (debug). Detached default
   preserva touch model atual (zero-touch ate `testing`; +1 touch
   pra `done`).
7. Hard limits gerais (ADR-006) aplicam.

## Approvals

Modo Hub-dispatch supervisionado. Gate unico: `vox dispatcher next
--launch` (CLI explicit Bernard). Dispatcher NAO requer approval card
(operacao confined a host-local + dispatch_payload merge auditavel).

## KPIs

- Dispatches/semana = invocacoes `--launch`.
- Taxa happy-path (exit 0 + auto-move testing) / total dispatches.
- Taxa execution_failed (exit != 0) / total — alto = sinal de briefing
  pobre OR Claude Code travando em permission OR task complexa demais.
- Tempo medio do dispatch ate testing (proxy de velocidade).

## Playbook operacional

### 1. Registrar dispatch

Append em `~/.openclaw/workspace/shared/outputs/agent-dispatch.jsonl`.

### 2. Select next ready

Le `~/.openclaw/kanban-tasks/state.json` direto (mesmo pattern do
scrum-master materializer — MC eh projecao).
Guard: `check_one_task_per_project_guard`.

### 3. Gerar briefing

Template §10.1 da spec. Embute convention strong pra Claude Code rodar
`vox clarification ask --and-wait` em duvida.

### 4. Move kanban + metadata

`cli.sh task move ready→in_progress --actor dispatcher`.
Merge dispatch_payload: dispatched_at, dispatcher_actor, briefing_path,
dispatch_mode (detach|foreground).

### 5. Spawn subprocess

- **Detach (default)**: `subprocess.Popen(... start_new_session=True ...)`
  com stdout/stderr redirect pro log.
- **Foreground (debug)**: blocking com output streamed pro TTY E pro log.

### 6. Lifecycle (auto-applied)

- Exit 0: `task move <id> testing --actor dispatcher` + merge
  execution_finished_at + execution_exit_code + auto_moved_to_testing_at.
- Exit != 0: `task block <id> --reason "execution_failed: <stderr-tail-150c>"`
  + merge execution_failed_marked_at.

## Boundary com outros agents

Ver §9 + §13 da spec. Dispatcher **NAO**:
- Registra perguntas (responsabilidade do clarification-agent).
- Move pra `testing → done` (gate humano).
- Move pra `rejected` (sempre via Bernard `--commit`).
- Auto-relaunch em failure (Bernard `dispatcher relaunch <id>`).

## Reaper (wave-3.5)

Subcomando `reap-detached` fecha o loop **detached** que parava em
`testing` (limitacao §10.2 spec do tester-agent). NAO eh
cron-dispatcher (auto-dispatch de novas tasks `ready`). Reaper SO age
sobre executions ja lancadas pelo Bernard via `dispatcher next
--launch`.

Spec: `35_specs/2026-04-19-e10-detached-reaper.md`.

### Operacao

```bash
vox dispatcher reap-detached --once          # uma passada (default; usado pelo systemd timer)
vox dispatcher reap-detached --once --json   # output estruturado
vox dispatcher reap-detached --dry-run       # lista o que faria, sem agir
```

### Garantias (§2 spec detached-reaper)

- **Sequencial**: dentro do tick, executions processadas uma a uma.
- **Ordem deterministica**: lote ordenado por `started_at` ascendente
  com tie-break por filename.
- **Lock global do lote**: fcntl 1x por tick (NAO per-execution).
  Segunda instancia exit 0 com `lock_skipped=true` (sem falha).
- **Idempotente**: `post_action_applied=true` skipa reprocessamento
  (triplo-check: lifecycle early-return + reaper checa antes + tester
  nao re-invocado se `test_result` presente).
- **Carve-out `dispatch_flags.no_tester`**:
  - `false` (default) → reaper invoca tester via `_invoke_tester`
    (decisao final auto: done | blocked | proposed_rejected)
  - `true` → reaper para em `testing`, NAO invoca tester (touch extra
    manual de `vox tester check` continua existindo por design)
- **Transparente**: zero campo "reaped_by_reaper" no `dispatch_payload`;
  audit so em `~/.openclaw/dispatcher-agent/reaper.jsonl` + `status.json`
  herdado.

### Habilitacao systemd (manual pos-push)

Templates shipped em `~/.openclaw/dispatcher-agent/systemd/`. Bernard
copia + habilita explicit:

```bash
cp ~/.openclaw/dispatcher-agent/systemd/openclaw-reaper.{service,timer} \
   ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now openclaw-reaper.timer
systemctl --user list-timers | grep reaper
journalctl --user -u openclaw-reaper -f
```

### Touch model atualizado pos-wave-3.5

| Modo dispatcher | `dispatch_flags.no_tester` | Touches happy path |
|---|---|---|
| `--launch --foreground` | false (default) | **1** (kick off) |
| `--launch` (detached) **+ reaper habilitado** | **false** (default) | **1** (kick off; reaper fecha em ~60-120s) |
| `--launch --no-tester` (detached) + reaper habilitado | **true** | **2** (kick + `vox tester check` manual) |
| `--launch` (detached) **com reaper desabilitado** | qualquer | igual pre-wave-3.5 |

## Cron-dispatcher (wave-4)

Subcomando `cron-tick` automatiza o kick off de novas tasks `ready`
para projetos **explicit opted-in** via `cron-projects.txt`. Combinado
com o reaper (wave-3.5), fecha o pipeline em **0 touches happy path
CONDICIONAL** (8 pre-condicoes simultaneas; ver §10 da spec
`35_specs/2026-04-19-e10-cron-dispatcher.md`). NAO eh redesign do
pipeline — SO automatiza o kick off.

Spec: `35_specs/2026-04-19-e10-cron-dispatcher.md`.

### Operacao

```bash
vox dispatcher cron-tick --once          # uma passada (usado pelo systemd timer)
vox dispatcher cron-tick --once --json   # output estruturado
vox dispatcher cron-tick --dry-run       # lista o que faria, sem agir
```

### Opt-in default deny

Edite `~/.openclaw/dispatcher-agent/cron-projects.txt` (1 project/linha;
`#` no inicio = comment). File ausente OR vazio = cron-tick exit 0
sem fazer nada.

### Kill-switch global

```bash
touch ~/.openclaw/dispatcher-agent/cron.disabled    # para tudo proximo tick
rm    ~/.openclaw/dispatcher-agent/cron.disabled    # retoma
```

### Garantias (§2 spec)

- **Sequencial + ordem alfabetica deterministica** dos opted-in
- **Testing TAMBEM bloqueia** (invariante forte §2.5): `in_progress`
  + `testing` + `blocked` + escalation aberta (clarification OR
  tester) skipam projeto
- **Falha per-project NAO aborta tick**: exception capturada +
  auditada como `outcome=dispatch_error` em `cron.jsonl`; tick
  continua proximo projeto. Unico caso que aborta: lock global no
  inicio OR erro infrastrutural pre-loop.
- **Lock global do tick** (`cron.lock` SEPARADO de `reaper.lock`);
  segunda instancia exit 0 com `lock_skipped=true` (sem falha)
- **1 task/projeto/tick**; sempre detached; `dispatch_flags.no_tester=false`
- `dispatcher_actor="cron-dispatcher"` (distingue do "dispatcher" manual)

### "0 touches happy path" eh CONDICIONAL

NAO eh wording incondicional. Vale APENAS quando TODAS as
pre-condicoes simultaneamente sao verdadeiras (§10 da spec):

1. Projeto listado em `cron-projects.txt`
2. Timer `openclaw-cron-dispatcher.timer` habilitado
3. Timer `openclaw-reaper.timer` habilitado (wave-3.5)
4. `dispatch_flags.no_tester=false` (default)
5. Kill-switch ausente (`cron.disabled` nao existe)
6. Zero escalation aberta no projeto (clarification OR tester)
7. Zero task em `in_progress` / `testing` / `blocked` (invariante
   forte §2.5)
8. Tester decide `done` no LLM check (heritage wave-3)

Qualquer pre-condicao falha → degrade graceful pra path manual.

### Habilitacao systemd (manual pos-push)

Templates shipped em `~/.openclaw/dispatcher-agent/systemd/openclaw-cron-dispatcher.{service,timer}`
(300s default). Bernard copia + habilita explicit:

```bash
cp ~/.openclaw/dispatcher-agent/systemd/openclaw-cron-dispatcher.{service,timer} \
   ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now openclaw-cron-dispatcher.timer
```

Override de cadencia: `systemctl --user edit openclaw-cron-dispatcher.timer`.

### Audit

`~/.openclaw/dispatcher-agent/cron.jsonl` (append-only; SEPARADO do
`reaper.jsonl`). Schema fechado: tick_id + tick_started_at +
tick_finished_at + trigger + kill_switch_active + opted_in_projects +
projects_considered + projects_skipped_no_ready/busy/escalation +
dispatched_count + actions_per_project[] + lock_acquired/skipped +
dry_run.

### Touch model atualizado pos-wave-4

| Modo + cron-dispatcher | `dispatch_flags.no_tester` | Touches happy path |
|---|---|---|
| Foreground manual | false | 1 (kick off) |
| Detached manual + reaper habilitado | false | 1 (kick off; reaper fecha) |
| **Cron habilitado pra projeto X + reaper habilitado, todas pre-cond OK** | **false** | **0\*** (CONDICIONAL; 8 pre-cond simultaneas) |
| Cron habilitado + `--no-tester` ou tester decide blocked | qualquer | 1 (Bernard inspeciona pos-fato) |
| Projeto NAO opted-in | n/a | igual pre-wave-4 |

\* "0 touches" eh **CONDICIONAL** (8 pre-cond simultaneas; ver §10
spec da wave-4). Sem wording incondicional.

## Volume minimo

- Manter L1: pelo menos 1 invocacao/mes.
- Promocao L2 (ADR-003): pelo menos 5/sem por 4 sem consecutivas, taxa
  execution_failed < 20%, zero rejection autonoma.

## Historico de levels

- L1 desde 2026-04-19.
