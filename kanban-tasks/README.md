# kanban-tasks

> HOST-LOCAL, NUNCA COMMITADO. Pode conter informacao sensivel em
> titles/descriptions de tasks. Conforme ADR-007.

Modulo de kanban operacional para dev tasks da Bevox. 2 sprints sempre
abertos (current + next). Tasks vinculadas opcionalmente a epic/wave do
delivery-tracker. CLI host-local + HTTP API no MC + UI `/kanban`.

## Estrutura

```
~/.openclaw/kanban-tasks/
├── cli.sh                 entrypoint bash
├── lib/                   logic Python stdlib
│   ├── store.py           I/O atomico, lock, append events
│   ├── sprint.py          bootstrap, close, promote
│   ├── task.py            CRUD, move, block/unblock/reopen, archive
│   ├── transitions.py     whitelist soft + helpers (wave-3)
│   └── api.py             argparse dispatcher
├── projects.yml           lista de projetos (editavel)
├── state.json             projecao atual (schema_version=2)
├── events.jsonl           SoT canonica append-only
├── state.json.lock        fcntl lock
└── README.md              este arquivo
```

## Status canonico (wave-3)

`backlog | ready | in_progress | testing | done | rejected`

+ `archived` (ortogonal -- task fora do board, preservada).
+ `blocked` (flag ortogonal -- task pausada por dep externa).

### Whitelist soft de transicoes

```
backlog     -> ready, in_progress, rejected
ready       -> backlog, in_progress, rejected
in_progress -> ready, testing, rejected
testing     -> in_progress, done, rejected
done        -> nada (terminal -- `task reopen` cmd)
rejected    -> nada (terminal -- `task reopen` cmd)
```

Fora da whitelist:
- Humano (`--actor bernard`): exige `--force`. Evento ganha `forced=true`.
- Agente (`--actor X`): exige `--reason "..."`. Sem reason, erro.

`blocked` task NAO pode ser movida pra terminal (`done`/`rejected`),
mesmo com `--force`. Faca `unblock` primeiro.

### Alias legado `todo` -> `ready`

Eventos antigos com `to:"todo"` ficam **intactos** em `events.jsonl`
(SoT imutavel). A projecao `apply_event` mapeia `todo` -> `ready` no
rebuild. Tasks com `status:"todo"` no `state.json` antigo viram `ready`
no proximo rebuild -- sem migration script.

## Operacao basica

```bash
# Bootstrap (uma vez)
~/.openclaw/kanban-tasks/cli.sh sprint init

# Criar task
cli.sh task add "implementar latest.json atomic write" \
  --sprint current --project openclaw \
  --epic E8 --wave E8/F3-snapshot-cron

# Listar current sprint
cli.sh sprint show
cli.sh task list --sprint current

# Mover entre colunas (ver whitelist abaixo)
cli.sh task move T-0001 ready
cli.sh task move T-0001 in_progress
cli.sh task move T-0001 testing
cli.sh task move T-0001 done

# Editar
cli.sh task update T-0001 --description "detalhes adicionais"

# Arquivar / desarquivar
cli.sh task archive T-0001
cli.sh task unarchive T-0001 --status backlog

# Fechar sprint (interativo: decide carry-over individual)
cli.sh sprint close

# Historico
cli.sh sprint history

# Eventos recentes
cli.sh events tail --n 20
cli.sh events tail --actor vox
cli.sh events show 42

# Health check
cli.sh status
```

## Vox usage

Vox invoca via Bash passando `--actor vox`:

```bash
cli.sh task add "..." --actor vox --project openclaw --epic E5
cli.sh task move T-NNN done --actor vox
cli.sh sprint close --non-interactive --actor vox
```

Auditoria: `cli.sh events tail --actor vox --n 50`.

## Guardrails de criacao manual de task

Se a task vai participar do fluxo `ready -> dispatcher -> testing -> done`,
**nao basta** criar um card "parecendo certo". Ela precisa nascer com
metadata operacional minima consistente.

### Minimo obrigatorio

- `project` valido em `projects.yml`
- `epic` preenchido
- `wave` ou `wave_ref` coerente com o trabalho
- `dispatch_payload.acceptance_criteria` nao-vazio
- `dispatch_payload.spec_ref` ou `dispatch_payload.spec_refs`
- `dispatch_payload.plan_ref`
- `dispatch_payload.plan_anchor`

### Anti-pattern proibido

Nao criar task manual com apenas:
- `title`
- `description`
- `acceptance_criteria` top-level

Esse formato pode parecer utilizavel no board, mas quebra a automacao:
- tester nao olha `task.acceptance_criteria`
- dispatcher/tester perdem rastreabilidade de plan/spec
- task pode entrar em `testing` e voltar blocked por precheck

### Regra pratica

Se a origem da task for plan/roadmap, prefira sempre o fluxo do
`scrum-master-agent` (`propose` + `accept`) em vez de `task.created`
manual. Criacao manual so deve ser usada para excecoes pequenas ou
housekeeping, nunca para bootstrap de sprint de implementacao.

## Troubleshooting

**Lock orfao** (`ERROR (lock_contention)` apos crash):

```bash
# Aguarde 30s (TTL stale auto-clean) OU force:
rm ~/.openclaw/kanban-tasks/state.json.lock
```

**state.json corrompido / dessincronizado**:

```bash
cli.sh rebuild   # reconstroi de events.jsonl
```

**Validar invariantes**:

```bash
cli.sh status    # 1 current + 1 next, seq casa, lock freshness
```

**Reset completo** (apaga tudo, recomeca do zero):

```bash
rm ~/.openclaw/kanban-tasks/state.json \
   ~/.openclaw/kanban-tasks/events.jsonl
cli.sh sprint init
```

## API HTTP (MC)

A UI MC `/kanban` consome `/api/kanban/*`. Vox prefere CLI direto via
Bash mas tambem pode bater HTTP com header:

```
X-Agent-Identity: vox
```

## Status canonico (wave-3)

`backlog | ready | in_progress | testing | done | rejected`

+ `archived` (ortogonal -- task fora do board, preservada).
+ `blocked` (flag ortogonal -- task pausada por dep externa).

### Whitelist soft de transicoes

```
backlog     -> ready, in_progress, rejected
ready       -> backlog, in_progress, rejected
in_progress -> ready, testing, rejected
testing     -> in_progress, done, rejected
done        -> nada (terminal -- usar `task reopen`)
rejected    -> nada (terminal -- usar `task reopen`)
```

Fora da whitelist:
- Humano (`--actor bernard`): exige `--force`. Evento ganha `forced=true`.
- Agente (`--actor X`): exige `--reason "..."`. Sem reason, erro.

Mover task `blocked=true` para terminal (`done`/`rejected`) sempre falha
com `MUST_UNBLOCK_BEFORE_TERMINAL` -- mesmo com `--force`.

### Alias legado `todo` -> `ready`

Eventos antigos com `to:"todo"` ficam **intactos** em `events.jsonl` (SoT
imutavel). A projecao `apply_event` mapeia `todo -> ready` no rebuild.
Tasks com `status:"todo"` no `state.json` antigo viram `ready` no
proximo rebuild -- sem migration script.

## Cmds wave-3

```bash
# Block / unblock (flag ortogonal)
cli.sh task block T-0042 --reason "esperando spec"
cli.sh task unblock T-0042
cli.sh task list --blocked        # filtra so blocked=true

# Reopen task terminal (cmd dedicado, `--to` deve ser nao-terminal)
cli.sh task reopen T-0042 --to in_progress --reason "regression flagged"

# Move forcado (humano so, audit explicito via forced=true)
cli.sh task move T-0042 done --force --reason "skip testing"

# Move com reason (agente fora da whitelist)
cli.sh task move T-0042 done --actor vox --reason "passed by tester-agent"

# Set dispatch_payload (contrato operacional pra scrum-master/dispatcher/tester)
# Modos: replace (default) ou --merge (shallow merge top-level).
# Shallow merge: chave por chave, novo valor substitui antigo inteiro.
# Arrays e scalars NAO sao combinados (sem deep merge, sem array concat).
# Evento task_dispatch_payload_set carrega payload completo -> replay
# via `cli.sh rebuild` reconstroi dispatch_payload deterministicamente.
# IMPORTANTE: o tester/precheck olha `dispatch_payload.acceptance_criteria`,
# nao o campo top-level `task.acceptance_criteria`. Se a task for criada ou
# atualizada sem AC dentro do dispatch_payload, ela pode ser auto-blocked em
# testing com `precheck_failed: acceptance_criteria_non_empty`.
cli.sh task set-dispatch-payload T-0042 --payload '{"goal": "x", "spec_refs": ["a.md"], "acceptance_criteria": ["y"]}'
cli.sh task set-dispatch-payload T-0042 --payload '{"dispatched_at": "..."}' --merge

# Rejected sempre exige --reason (mesmo dentro da whitelist)
cli.sh task move T-0042 rejected --reason "scope cut"
```

## Spec canonica

- `bevox-knowledge/35_specs/2026-04-17-e5-f4-sprint-planning-wave-1.md`
- `bevox-knowledge/35_specs/2026-04-17-e5-f4-kanban-rich-ui-wave-2.md`
- `bevox-knowledge/35_specs/2026-04-19-e5-f4-kanban-dev-lifecycle.md` (wave-3)
- Plan wave-1+2: `bevox-knowledge/35_specs/2026-04-17-e5-f4-kanban-tasks-implementation-plan.md`
- Plan wave-3: `~/.openclaw/docs/superpowers/plans/2026-04-19-e5-f4-kanban-dev-lifecycle-plan.md`

## Sprint per-project (schema v4)

Desde 2026-04-25 (wave `sprint-per-project`), cada projeto canônico em
`projects.yml` tem seu próprio par `current` + `next` independente.

### Bootstrap

```bash
# Cria current+next pra cada projeto em projects.yml que ainda não tem
./cli.sh sprint bootstrap

# Override: só para um projeto específico
./cli.sh sprint bootstrap --project bevox-mobile

# Plan-only (sem mutação)
./cli.sh sprint bootstrap --dry-run
```

Idempotente: projetos que já têm current+next são skipados.

### Close per-project

```bash
./cli.sh sprint close-current --project bevox-mobile --actor bernard \
  --carryover '[{"task_id":"T-50","action":"move_current"},{"task_id":"T-51","action":"archive"}]'
```

Fecha current de bevox-mobile, promove next→current, nasce novo next.
Outros projetos intocados.

### Migração v3→v4

Comando one-shot rodado pós-deploy do schema v4:

```bash
./cli.sh sprint migrate-to-per-project --dry-run   # inspeciona plano
./cli.sh sprint migrate-to-per-project              # aplica
```

Backup defensivo automático em `state.json.pre-schema-v4.bak`.
Idempotente (re-rodar = noop "already_migrated").

## Sprint session_id helpers (wave dispatcher-same-session-per-sprint)

Sprints ganham field `execution_session_id` (UUID) populado lazy quando primeira task da sprint dispatcha. Tasks subsequentes da mesma sprint reusam via `claude --resume`.

### Set (chamado primariamente pelo dispatcher; manual override possível)

```bash
./cli.sh sprint set-session-id --sprint-id sprint-22 --session-id <uuid> --actor dispatcher
```

Idempotente: se sprint já tem session_id, retorna noop com o existing. Closed sprint: rejeita.

### Clear (recovery operacional)

```bash
./cli.sh sprint clear-session-id --sprint-id sprint-22 --actor bernard --reason "context contamination"
```

Limpa session_id (próxima task gera fresh). Idempotente. Closed sprint: rejeita.
