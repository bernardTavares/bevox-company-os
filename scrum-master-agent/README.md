# scrum-master-agent

> HOST-LOCAL, NUNCA COMMITADO. Modulo Hub-dispatch que projeta
> implementation plans em tasks do kanban-tasks.

Spec canonica:
`bevox-knowledge/35_specs/2026-04-19-e10-scrum-master-agent.md` (commit `2ac8527`)

Playbook canonico (a ser criado na Phase 8):
`bevox-knowledge/20_architecture/agents/scrum-master-agent.md`
(copia sync'd em `./playbook.md`).

## Estrutura

```
~/.openclaw/scrum-master-agent/
├── cli.sh                 entrypoint bash
├── lib/                   logic Python stdlib
│   ├── store.py           I/O atomico + listagem de proposals
│   ├── parser.py          (Phase 3) parser do plan
│   ├── projects.py        (Phase 4) project derivation
│   ├── proposer.py        (Phase 5) build proposal JSON
│   ├── materializer.py    (Phase 7) accept -> kanban CLI
│   └── api.py             argparse dispatcher
├── proposals/             proposals JSON files (runtime)
├── playbook.md            (Phase 8) copia sync'd do canonico
└── README.md              este arquivo
```

## Operacao basica (wave-1)

```bash
# Listar propostas
./cli.sh list                      # pending por default
./cli.sh list --status all
./cli.sh list --status accepted
./cli.sh list --status rejected

# Inspecionar uma proposta
./cli.sh show <proposal-id>
./cli.sh show <proposal-id> --json

# Propor a partir de um plan (Phase 5+)
./cli.sh propose --plan <slug-ou-path>

# Aceitar (all-or-nothing, Phase 7+)
./cli.sh accept <proposal-id>
./cli.sh accept <proposal-id> --ready

# Rejeitar (Phase 6)
./cli.sh reject <proposal-id> --reason "..."
```

## Escopo wave-1

- 1 plan por invocacao -> 1 proposal JSON.
- Projecao 1:1 — cada plan Task vira 1 kanban task.
- Phases viram `wave_ref` suffix (`<plan.epic>/<plan.wave>/Phase-N`).
- Accept all-or-nothing (sem partial).
- Status default das tasks materializadas: `backlog`. Flag `--ready`
  materializa ja como `ready`.

Dispatcher (wave-2 PRD), tester (wave-3), cron (wave-4) ficam fora
desta wave.

## Troubleshooting

**`PROPOSAL_NOT_FOUND`:** `./cli.sh list --status all` pra ver IDs reais.

**`PLAN_MISSING_EPIC`:** (Phase 5+) adicione `**Epico:** <ep>/<wave>`
no header do plan.

**`AMBIGUOUS_PROJECT`:** (Phase 5+) adicione `**Project:** <nome>` no
header OU passe `--project-override <nome>`.

## Spec canonica

- `bevox-knowledge/35_specs/2026-04-19-e10-scrum-master-agent.md`
- Plan wave-1: `~/.openclaw/docs/superpowers/plans/2026-04-19-e10-scrum-master-agent-plan.md`
