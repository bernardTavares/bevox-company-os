# dispatcher-agent

> HOST-LOCAL, NUNCA COMMITADO. Hub-dispatch L1 que seleciona proxima task
> ready, gera briefing, invoca Claude Code em background detached,
> auto-move in_progress -> testing no exit 0.

Spec: `bevox-knowledge/35_specs/2026-04-19-e10-dispatcher-and-clarification-agents.md`
Playbook: `bevox-knowledge/20_architecture/agents/dispatcher-agent.md`

## Operacao basica

```bash
vox dispatcher next [--project X]            # dry-run
vox dispatcher next --launch [--project X]   # default detach; cmd retorna imediato
vox dispatcher next --launch --foreground    # debug: bloqueia ate Claude Code terminar
vox dispatcher status                        # lista sessions ativas
vox dispatcher show <task-id>                # detail + log path
vox dispatcher tail <task-id>                # tail -f no log
vox dispatcher relaunch <task-id>            # apos fix de execution_failed
vox dispatcher kill <task-id>                # SIGTERM session
```

## Troubleshooting

**`NO_READY_TASK`**: scrum-master precisa ter produzido tasks ready
OU mover manual via `kanban-tasks/cli.sh task move <id> ready`.

**`WORK_IN_PROGRESS_LIMIT`**: ja existe task do projeto em in_progress.
Conclui ela primeiro, ou rode `vox dispatcher kill <id>`.

**`execution_failed`**: Claude Code terminou exit != 0. Chequa log:
`vox dispatcher tail <task-id>`. Decide `relaunch` ou rejection manual.

## Spec canonica

- `bevox-knowledge/35_specs/2026-04-19-e10-dispatcher-and-clarification-agents.md`

---

## Reaper (wave-3.5)

Subcomando `reap-detached` fecha o loop **detached** que para em
`testing` (limitacao §10.2 spec do tester-agent). Reusa
`runner.reap_finished` + `lifecycle.process_finished_session` +
`_invoke_tester` (zero refactor).

```bash
vox dispatcher reap-detached --once          # roda uma passada
vox dispatcher reap-detached --once --json   # output estruturado
vox dispatcher reap-detached --dry-run       # lista o que faria, sem agir
```

### Limitacao explicita (NAO eh otimismo)

Detached + reaper **so fecha ate `done` automaticamente quando
`dispatch_flags.no_tester == false`** (default).

- `vox dispatcher next --launch` (default) → reaper invoca tester →
  decisao final auto (done | blocked | proposed_rejected).
- `vox dispatcher next --launch --no-tester` → flag persistido em
  `dispatch_payload.dispatch_flags.no_tester=true`. Reaper aplica
  reap + lifecycle (move pra testing) mas **NAO invoca tester por
  design**. Task fica em `testing` ate Bernard rodar
  `vox tester check <id>` manual. O touch extra continua existindo.

### Garantias (§2 da spec detached-reaper)

- Sequencial + ordem deterministica (`started_at` asc, tie-break filename)
- Lock global do lote (fcntl 1x por tick — segunda instancia exit 0
  com `lock_skipped=true`)
- Idempotente (`post_action_applied=true` skipa)
- Reaper transparente: zero campo "reaped_by_reaper" no payload;
  audit em `reaper.jsonl`

### Habilitacao systemd (manual pos-push)

Templates shipped em `~/.openclaw/dispatcher-agent/systemd/`.
Bernard copia + habilita explicit:

```bash
mkdir -p ~/.config/systemd/user
cp ~/.openclaw/dispatcher-agent/systemd/openclaw-reaper.{service,timer} \
   ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now openclaw-reaper.timer
systemctl --user list-timers | grep reaper
journalctl --user -u openclaw-reaper -f       # tail logs
```

Desabilitar:

```bash
systemctl --user disable --now openclaw-reaper.timer
```

### NAO eh cron-dispatcher

Reaper SO age sobre executions ja lancadas via
`dispatcher next --launch`. Auto-dispatch de novas tasks `ready`
continua fora desta wave (cron-dispatcher = wave-4 PRD original,
separada).

**Audit:** `~/.openclaw/dispatcher-agent/reaper.jsonl` (append-only;
uma linha por tick).

**Spec canonica:**
- `bevox-knowledge/35_specs/2026-04-19-e10-detached-reaper.md`

---

## Cron-dispatcher (wave-4)

Subcomando `cron-tick` automatiza o kick off de novas tasks `ready`
para projetos **explicit opted-in** via `cron-projects.txt`. Combinado
com o reaper (wave-3.5), fecha o pipeline em **0 touches happy path
CONDICIONAL** (8 pre-condicoes simultaneas; ver §10 spec).

```bash
vox dispatcher cron-tick --once          # uma passada (usado pelo systemd timer)
vox dispatcher cron-tick --once --json   # output estruturado
vox dispatcher cron-tick --dry-run       # lista o que faria, sem agir
```

### Limitacao explicita (NAO eh otimismo)

"0 touches happy path" eh **CONDICIONAL**. Vale APENAS quando TODAS
as pre-condicoes sao verdadeiras simultaneamente:

1. Projeto listado em `~/.openclaw/dispatcher-agent/cron-projects.txt`
2. systemd timer `openclaw-cron-dispatcher.timer` habilitado
3. systemd timer `openclaw-reaper.timer` habilitado (wave-3.5)
4. `dispatch_flags.no_tester=false` (default)
5. Kill-switch ausente (`cron.disabled` nao existe)
6. Zero escalation aberta no projeto (clarification + tester)
7. Zero task em `in_progress` / `testing` / `blocked`
8. Tester decide `done` no LLM check (heritage wave-3)

Qualquer pre-condicao falha → degrade graceful pra path manual.

### Opt-in default deny

Edite `~/.openclaw/dispatcher-agent/cron-projects.txt` (1 project/linha;
`#` no inicio = comment). File ausente OR vazio → cron-tick exit 0
sem fazer nada. Ordem alfabetica deterministica dentro do tick.

### Kill-switch global

```bash
touch ~/.openclaw/dispatcher-agent/cron.disabled    # para tudo proximo tick
rm    ~/.openclaw/dispatcher-agent/cron.disabled    # retoma proximo tick
```

### Garantias (§2 spec)

- **Sequencial + ordem alfabetica deterministica** dos opted-in
- **Testing TAMBEM bloqueia** (invariante forte §2.5): in_progress +
  testing + blocked + escalation aberta (clarification OR tester)
  skipam projeto
- **Falha per-project NAO aborta tick**: exception capturada + auditada
  como `outcome=dispatch_error` em `cron.jsonl`; tick continua proximo
  projeto. Unico caso que aborta: lock global no inicio.
- **Lock global do tick** (`cron.lock` SEPARADO de `reaper.lock`);
  segunda instancia exit 0 com `lock_skipped=true`
- **1 task/projeto/tick**; sempre detached; `dispatch_flags.no_tester=false`
- `dispatcher_actor="cron-dispatcher"` (distingue do "dispatcher" manual)

### Habilitacao systemd (manual pos-push)

Templates shipped em `~/.openclaw/dispatcher-agent/systemd/` (300s default).
Bernard copia + habilita explicit:

```bash
cp ~/.openclaw/dispatcher-agent/systemd/openclaw-cron-dispatcher.{service,timer} \
   ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now openclaw-cron-dispatcher.timer
systemctl --user list-timers | grep cron-dispatcher
journalctl --user -u openclaw-cron-dispatcher -f
```

Override de cadencia (sem editar template):

```bash
systemctl --user edit openclaw-cron-dispatcher.timer
# editor abre overlay; escreva:
# [Timer]
# OnUnitActiveSec=600s   # 10min em vez de 5min
```

Desabilitar:

```bash
systemctl --user disable --now openclaw-cron-dispatcher.timer
```

### NAO eh redesign

Cron-dispatcher SO automatiza o kick off. Tudo o resto reusa intacto:
selector + briefing + runner detached + lifecycle + reaper + tester.

**Audit:** `~/.openclaw/dispatcher-agent/cron.jsonl` (append-only;
SEPARADO do `reaper.jsonl`).

**Spec canonica:**
- `bevox-knowledge/35_specs/2026-04-19-e10-cron-dispatcher.md`

## Notificações Telegram (opcional)

O dispatcher pode emitir mensagens Telegram em transições terminais
(`task_done` após exit 0, `task_failed` após exit != 0 / reaper timeout).

Para ativar, exportar no environment do serviço systemd:

```bash
TELEGRAM_BOT_TOKEN=<token>                     # reusa bot existente
OPENCLAW_DISPATCHER_TELEGRAM_CHAT_ID=<chat_id> # mesmo chat dos outros tópicos
OPENCLAW_DISPATCHER_TELEGRAM_THREAD_ID=<int>   # thread_id do tópico "dispatcher"
```

Se qualquer uma faltar: função vira no-op silencioso (log em
`dispatcher-agent/notifier.jsonl` com event `skipped:env_missing`).

Audit trail append-only em `dispatcher-agent/notifier.jsonl`:
- `task_event_sent` — Telegram respondeu OK
- `skipped:env_missing` — uma das env vars não presente
- `skipped:env_invalid` — `THREAD_ID` não-numérico
- `failed:telegram_api_<code>` — HTTP falhou (swallow, audit only)

Opcional: `OPENCLAW_DEBUG_NOTIFIER=1` imprime um log em stderr quando o
notifier pular um evento (útil em dev; nunca loga credenciais).

---

## Sprint filter (schema v4)

Desde 2026-04-25, dispatcher só dispatcha tasks que estão na **current
sprint do projeto da task**. Tasks em `next` sprint (ou outras) são
ignoradas até `close-current` promover next→current.

### Kill-switch

Se houver bug no filtro, restaurar comportamento legado em <30s:

```bash
systemctl --user edit openclaw-cron-dispatcher.service
# adiciona:
[Service]
Environment="OPENCLAW_DISPATCHER_IGNORE_SPRINT=1"

systemctl --user daemon-reload
systemctl --user restart openclaw-cron-dispatcher.timer
```

Filtro vira no-op, dispatcher volta a aceitar qualquer task ready.
Schema continua per-project (sprints intactos), só o filtro é desabilitado.

### Audit

`cron.jsonl` captura por tick:
- `current_sprint_id` pra cada projeto considerado
- Outcome novo `skipped_no_current_sprint` se projeto não tem current

---

## Session reuse per sprint (wave dispatcher-same-session-per-sprint)

Tasks da mesma current sprint do projeto compartilham 1 session Claude Code via `claude --resume`. Primeira task gera UUID e grava em `sprint.execution_session_id`; subsequentes reusam.

### Kill-switch

Se houver bug com `--resume` ou suspeita de context contamination, restaurar comportamento legado em <30s:

```bash
systemctl --user edit openclaw-cron-dispatcher.service
# adiciona:
[Service]
Environment="OPENCLAW_DISPATCHER_DISABLE_SESSION_REUSE=1"

systemctl --user daemon-reload
systemctl --user restart openclaw-cron-dispatcher.timer
```

Comportamento com kill-switch ativo:
- Cada task spawna `claude --session-id <novo-uuid>` (fresh)
- Kanban estado de sprint NÃO muda (sprint mantém session_id existing read-only)
- Cron audit registra `kill_switch_active: true` + `session_was_fresh: true`

Desativar kill-switch volta automaticamente ao reuse.

### Recovery cirúrgico (sprint específica)

Sem kill-switch global, limpar só uma sprint problemática:

```bash
~/.openclaw/kanban-tasks/cli.sh sprint clear-session-id --sprint-id sprint-22 \
  --actor bernard --reason "context bloat after Task 1.3"
```

Próxima task da sprint gera UUID novo. Outras sprints intocadas.

### Audit

`cron.jsonl` por tick captura em ações `dispatched`:
- `execution_session_id`: UUID usado (resume ou fresh)
- `session_was_fresh`: `true` se primeira task da sprint, `false` se resume

`executions/<task>.log` ganha header pré-spawn com metadata:
```
# DISPATCHER METADATA
# task_id: T-0099
# sprint_id: sprint-22
# execution_session_id: abc-uuid
# session_was_fresh: true
# kill_switch_active: false
# ----- claude output below -----
```
