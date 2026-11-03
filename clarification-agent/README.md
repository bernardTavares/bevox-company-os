# clarification-agent

> HOST-LOCAL. Hub-dispatch L1 invocado pelo Claude Code (via Bash tool)
> quando ha duvida bloqueante. Le contexto canonico, gera answer com
> confidence flag. Safe -> auto-unblock + retorna answer. Unsafe -> escala.

Spec: `bevox-knowledge/35_specs/2026-04-19-e10-dispatcher-and-clarification-agents.md`

## Invocado pelo Claude Code

```bash
~/.openclaw/clarification-agent/cli.sh ask T-0042 --question "..." --and-wait
```

## Operacao manual (Bernard)

```bash
~/.openclaw/clarification-agent/cli.sh escalations
~/.openclaw/clarification-agent/cli.sh show <task-id>
~/.openclaw/clarification-agent/cli.sh override <task-id> --answer "..." --commit
~/.openclaw/clarification-agent/cli.sh reject-task <task-id> --reason "<cat>: ..." --commit
~/.openclaw/clarification-agent/cli.sh redraft <task-id>
```

## Categorias validas de rejection

- `task_malformed`
- `spec_inconsistent`
- `requires_re_decomposition`
- `inexecutable`
- `manual`

## Exit codes

- 0: safe auto-resolve OK
- 2: cancelado durante --and-wait (SIGTERM)
- 3: CLARIFICATION_PROPOSES_REJECTION
- 4: CLARIFICATION_REJECTED_TASK

---

## 2026-04-22 — Wave-1 delivered

Daemon pull mode + local-first drafter em coexistência com push mode.

- Spec canônica: `bevox-knowledge/35_specs/2026-04-21-e10-clarification-daemon-local-first.md`
- ADR: `bevox-knowledge/30_adr/ADR-009-clarification-loop-unified-local-first.md`
- Plan: `~/.openclaw/docs/superpowers/plans/2026-04-21-e10-clarification-daemon-local-first-plan.md`

### Artefatos entregues

- `lib/provider.py` (90 lines) — ollama + claude_cli abstraction
- `lib/poller.py` (~320 lines) — run_tick + pre-filter + fast-fail + dedup + lock + LLM path
- `lib/drafter.py` refactored (199 lines) — delegates to provider + draft_answer_local_first wrapper
- `lib/store.py` extended (157 lines) — POLL_JSONL + append_poll_event
- `lib/lifecycle.py` extended (~252 lines) — auto_draft_for_task + emit_payload_incomplete_escalation + clarification_lock
- `lib/api.py` extended (403 lines) — cmd_poll_tick + cmd_poll_status + subparsers
- `tests/test_provider.py` (104 lines, 6 tests)
- `tests/test_store_poll_append.py` (29 lines, 1 test)
- `tests/test_poller.py` (~210 lines, 17 tests)
- `systemd/openclaw-clarification-daemon.{service,timer}` (templates)
- `smoke_e2e.sh` (~173 lines, 14 cenários)
- `bevox-mobile/scripts/request-clarification.sh` patched (coexistência Fase A)

### Verificação

- **24/24 unit tests PASS** (6 provider + 1 store_poll_append + 17 poller).
- CLI `poll-tick --dry-run --json` retorna estrutura esperada.
- CLI `poll-tick --json` escreve tick_started/tasks_blocked_scanned/tick_finished em `poll.jsonl`.
- CLI `poll-status --json` agrega events das últimas 24h.
- Push mode preservado (`cli.sh ask <task>` retorna TASK_NOT_FOUND estrutural).
- Smoke E2E: 4 automáticos PASS (lock contention, killswitch, dry-run, push regression).

### Próximos passos (Bernard)

1. Instalar systemd units:
   ```
   cp ~/.openclaw/clarification-agent/systemd/*.{service,timer} ~/.config/systemd/user/
   systemctl --user daemon-reload
   systemctl --user enable --now openclaw-clarification-daemon.timer
   ```
2. Opcional: rodar smoke E2E manual scenarios (1, 2, 13, 14) quando ollama up + task real.
3. Merge do `draft/adr-009-clarification-daemon` para main quando bloco Operational Loop Hardening completo.

### Backups `.bak` (rollback)

- `lib/drafter.py.pre-provider.bak`
- `lib/api.py.pre-poll.bak`
- `lib/store.py.pre-poll.bak`
- `lib/lifecycle.py.pre-poll.bak`

---

## 2026-04-22 — Wave-2 delivered

Telegram push notifier standalone para escalations unsafe.

- Spec canônica: `bevox-knowledge/35_specs/2026-04-21-e10-telegram-push-escalations.md`
- Plan: `~/.openclaw/docs/superpowers/plans/2026-04-22-e10-telegram-push-escalations-plan.md`

### Artefatos entregues

- `lib/notifier.py` (~280 lines) — orchestração + tick + dedup + Telegram API
- `tests/test_notifier.py` (35/35 passing) — cenários happy path + error + edge
- `notifier.sh` wrapper — CLI entry point com argparse
- `systemd/openclaw-clarification-notifier.{service,timer}` — templates
- `smoke_notifier.sh` (~120 lines, 7 cenários) — automated + manual validation

### Verificação

- **35/35 unit tests PASS** (load_state, save_state, validate_env, parse_filename, send_telegram, build_message, tick logic, GC).
- CLI `--tick --dry-run --json` retorna estrutura esperada.
- CLI `--tick --json` escreve eventos em `notifier.jsonl`.
- Smoke E2E: 3 automáticos PASS (dry-run, missing env var, garbage file ignored); 4 manuais pending (live Bot API).

### Próximos passos (Bernard)

1. Popular `.env` com `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CLARIFICATIONS_CHAT_ID`/`TELEGRAM_CLARIFICATIONS_THREAD_ID`.
2. Instalar systemd units:
   ```
   cp ~/.openclaw/clarification-agent/systemd/openclaw-clarification-notifier.{service,timer} ~/.config/systemd/user/
   systemctl --user daemon-reload
   systemctl --user enable --now openclaw-clarification-notifier.timer
   ```
3. Validar: rodar smoke E2E cenários 1, 4, 6, 7 com live env.
4. Merge `draft/adr-009-...` para main quando bloco Operational Loop Hardening completo.
