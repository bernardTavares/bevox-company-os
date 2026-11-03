# Integration: dispatcher-agent

> O **dispatcher-agent** seleciona a próxima task `ready` do meu projeto e
> dispara um Claude Code em background detached para executá-la.

## Como ele decide a próxima task

1. Lê `~/.openclaw/kanban-tasks/state.json`
2. Filtra tasks com `status=ready` e `project={{SLUG}}`
3. Respeita `WORK_IN_PROGRESS_LIMIT` (default 1 in_progress por projeto)
4. Ordena por `priority` desc, `created_at` asc
5. Dispara a primeira

## CLI cheatsheet

```bash
# Ver próxima task que seria escolhida (sem disparar)
~/.openclaw/dispatcher-agent/cli.sh next --project {{SLUG}} --dry-run

# Disparar próxima ready
~/.openclaw/dispatcher-agent/cli.sh next --launch --project {{SLUG}}

# Listar dispatches em andamento
~/.openclaw/dispatcher-agent/cli.sh list-active --project {{SLUG}}

# Marcar manualmente uma task como done (escape hatch)
~/.openclaw/dispatcher-agent/cli.sh complete <task-id> --actor {{SLUG}}
```

## Briefing format

Briefings ficam em `~/.openclaw/dispatcher-agent/briefings/<task-id>.md`.
Contêm: task title, description, payload (acceptance criteria, spec_ref),
project context, and operational instructions.

## Lifecycle

```
ready → in_progress → testing → done
                  ↓
               blocked (clarification opened)
```

Quando a task é dispatched, o dispatcher escreve `dispatcher_session_id`
no payload e move pra `in_progress`. O reaper periódico verifica se a
sessão Claude Code terminou e move pra `testing`. O tester-agent valida
e move pra `done` ou volta pra `ready` com feedback.

## Notificação

Em caso de `task_done` ou `task_failed`, o dispatcher posta no tópico
Telegram `dispatcher` (se `telegram.topics.dispatcher` presente em
`projects-meta.json` para este projeto). Senão, posta no general.
