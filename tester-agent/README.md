# tester-agent

> HOST-LOCAL, NUNCA COMMITADO. Hub-dispatch L1 que valida tasks em
> `testing` (5 invariantes deterministicos + LLM checks per AC) e decide:
>
> - `testing → done` (auto, todos AC pass)
> - `testing → in_progress` blocked `test_failed: <ac>` (≥1 AC fail)
> - `testing → in_progress` blocked `test_inconclusive: <reason>` (≥1 AC sem evidencia)
> - **Propõe** `testing → rejected` via exit 3 (Bernard `--commit` apenas)

Spec: `bevox-knowledge/35_specs/2026-04-19-e10-tester-agent.md`
Playbook: `bevox-knowledge/20_architecture/agents/tester-agent.md`

## Operacao basica

```bash
vox tester check <task-id>                                  # roda prechecks + LLM checks; aplica decisao
vox tester check <task-id> --no-act                         # dry-run: gera test_run JSON, NAO move kanban
vox tester recheck <task-id>                                # re-valida apos edit manual; novo seq
vox tester results [--all|--failed|--inconclusive|--proposed-rejection]
vox tester show <task-id>                                   # ou <test-run-id>
vox tester reject-task <task-id> --reason "<categoria>: ..." --commit
```

## Exit codes

- `0`: done auto OR devolveu in_progress (blocked test_failed/inconclusive)
- `1`: input invalido (TASK_NOT_FOUND, INVALID_REJECT_CATEGORY)
- `2`: precheck infrastrutural falhou (sem log, sem AC)
- `3`: TESTER_PROPOSES_REJECTION (structural fail; Bernard --commit)

## Auto-invoke

Dispatcher invoca tester automaticamente APENAS em modo foreground:

```bash
vox dispatcher next --launch --foreground             # auto-invoca tester apos auto-move testing
vox dispatcher next --launch --foreground --no-tester # foreground SEM tester (debug)
vox dispatcher next --launch                          # detached (default): NAO invoca tester
```

Bernard em detached mode usa `vox tester check <id>` manual depois.

## Troubleshooting

**`PRECHECK_FAILED: execution_log_missing`**: dispatcher nao gerou log
OR foi limpo. Verifica `~/.openclaw/dispatcher-agent/executions/<id>.log`.

**`PRECHECK_FAILED: acceptance_criteria_empty`**: scrum-master nao
populou AC no dispatch_payload. Verifica plan original.

**`PRECHECK_FAILED: clarification_escalation_open`**: clarification
pending. Resolve override/reject-task antes do tester.

**`test_inconclusive`**: AC ambigua OR log incompleto. Bernard inspeciona;
opcoes: `tester recheck` apos edit, `dispatcher relaunch`, override
manual via `kanban task move done --actor bernard`.

**`exit 3 TESTER_PROPOSES_REJECTION`**: structural fail. Le
`escalations/<test-run-id>.md`; decide `tester reject-task --commit`.

## Spec canonica

- `bevox-knowledge/35_specs/2026-04-19-e10-tester-agent.md`
