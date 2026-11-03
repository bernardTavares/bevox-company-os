# Integration: kanban-tasks

> O **kanban-tasks** é o sistema de tasks per-project (schema v4). Cada
> projeto tem seus próprios sprints (`current` + `next`).

## CLI cheatsheet

```bash
KANBAN=~/.openclaw/kanban-tasks/cli.sh

# Listar tasks deste projeto
$KANBAN task list --project {{SLUG}}

# Filtrar por status
$KANBAN task list --project {{SLUG}} --status ready

# Adicionar task ao sprint `next`
$KANBAN task add "Título da task" \
    --project {{SLUG}} \
    --sprint sprint-next \
    --description "Descrição" \
    --payload '{"spec_ref": "...", "acceptance_criteria": [...]}'

# Mover task entre states (idempotent)
$KANBAN task move <task-id> ready --actor {{SLUG}}
$KANBAN task move <task-id> in_progress --actor dispatcher
$KANBAN task move <task-id> testing --actor reaper
$KANBAN task move <task-id> done --actor tester

# Bloquear/desbloquear
$KANBAN task block <task-id> --reason "..."
$KANBAN task unblock <task-id>

# Listar sprints
$KANBAN sprint list --project {{SLUG}}

# Fechar sprint atual
$KANBAN sprint close-current --project {{SLUG}} --carryover
```

## Estados válidos

```
draft → next → ready → in_progress → testing → done
                 ↓
              blocked  (via clarification ou tester reject)
```

## Payload format

```json
{
  "spec_ref": "35_specs/openclaw/2026-04-NN-...md",
  "acceptance_criteria": [
    "Criterio 1",
    "Criterio 2"
  ],
  "branch": "feat/...",
  "dispatcher_session_id": null
}
```

## Eventos

`events.jsonl` é append-only. Cada transição emite um event com `seq`,
`ts`, `type`, `actor`, `task_id`/`project`, `snapshot`. Snapshot pre-delete
é preservado mesmo após `project remove`.
