# Integration: scrum-master-agent

> O **scrum-master-agent** converte plans (`docs/superpowers/plans/`) em
> tasks no kanban-tasks via proposal/accept loop.

## Fluxo

1. Eu (ou Bernard) escrevo um plan em `~/.openclaw/docs/superpowers/plans/`
2. `scrum-master propose --plan <plan.md> --project {{SLUG}}` lê o plan e gera
   uma proposal JSON em `~/.openclaw/scrum-master-agent/proposals/`
3. Bernard revisa: `scrum-master review <proposal-id>` (mostra diff)
4. Bernard aceita: `scrum-master accept <proposal-id> [--ready]`
5. Tasks são materializadas no kanban; com `--ready` vão pra `ready`

## CLI cheatsheet

```bash
# Propor tasks a partir de um plan
~/.openclaw/scrum-master-agent/cli.sh propose \
    --plan ~/.openclaw/docs/superpowers/plans/<plan>.md \
    --project {{SLUG}}

# Listar proposals abertos
~/.openclaw/scrum-master-agent/cli.sh list-proposals --project {{SLUG}}

# Aceitar (move pra `next` por default; --ready pra `ready`)
~/.openclaw/scrum-master-agent/cli.sh accept <proposal-id> --ready

# Rejeitar (com motivo)
~/.openclaw/scrum-master-agent/cli.sh reject <proposal-id> --reason "..."
```

## Plan → task extraction

Scrum-master parseia headers `## Phase N: <title>` (sprint) e `### Task N.M:
<title>` (task). Cada `### Task` vira uma entry no kanban com:

- `title`: o título da task
- `description`: corpo até o próximo `### Task` ou `##`
- `payload.spec_ref`: referência da spec (extraída do header do plan)
- `payload.acceptance_criteria`: array de checkboxes encontrados na task
- `project`: passado via `--project`

## Lifecycle de proposal

```
draft → reviewed → accepted (tasks no kanban)
              ↓
           rejected
```
