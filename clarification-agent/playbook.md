<!-- Agent file do Clarification Agent — wave-2 do PRD orchestration.
     Invocado pelo Claude Code (via Bash tool) durante execucao do
     dispatcher. Gera answer com confidence; auto-resolve safe; escala
     unsafe.
     Spec canonica: 35_specs/2026-04-19-e10-dispatcher-and-clarification-agents.md
     Pareado com dispatcher-agent na mesma wave canonica.
-->

# Agent: clarification-agent

> Runbook canonico. Spec:
> `35_specs/2026-04-19-e10-dispatcher-and-clarification-agents.md`.

- **Owner:** <!-- DERIVED --> Bernard
- **Status:** <!-- DERIVED --> ativo
- **Level:** <!-- DERIVED --> L1
- **Modelo padrao:** <!-- DERIVED --> stdlib-python/no-model (invoca claude -p subprocess)
- **Modelo fallback:** <!-- DERIVED --> none
- **Criado em:** <!-- DERIVED --> 2026-04-19

## Missao

Responder duvidas operacionais levantadas pelo executor (Claude Code
invocado via dispatcher) **estritamente com base em contexto canonico**
(spec_refs, plan_ref, ADRs citadas). Confidence binary:

- **safe**: auto-unblock + retorna answer pelo stdout do `ask` (Claude
  Code continua execucao sem intervencao humana intermediaria).
- **unsafe**: escalation file escrito; task permanece blocked com reason
  `clarification_escalation_required`; aguarda Bernard.

## Inputs

- Invocacao tipica: `vox clarification ask <task-id> --question "..."
  --and-wait` executado pelo Claude Code via Bash tool.
- Invocacao manual (Bernard): `escalations`, `show`, `override --commit`,
  `reject-task --commit`, `redraft`.
- Task em `in_progress`, blocked=false (estado valido pra receber pergunta).

## Outputs

- `~/.openclaw/clarification-agent/questions/<task-id>-clr-<seq>.md`
- `~/.openclaw/clarification-agent/answers/<task-id>-clr-<seq>.md`
  (header com confidence + sources + escalation_reason se unsafe)
- `~/.openclaw/clarification-agent/escalations/<task-id>-clr-<seq>.md`
  (symlink → answer; existe apenas pra escalations pending)
- `~/.openclaw/clarification-agent/signals/<clarification-id>.signal`
  (file vazio quando answer ready + unblock feito; usado pelo
  `--and-wait` pra detectar conclusao)
- Kanban mutations:
  - `task block <id> --reason "clarification_required: <q-resumo>"` (ask)
  - `task unblock <id> --actor clarification` (auto-resolve safe ou
    override Bernard)
  - `task block <id> --reason "clarification_escalation_required: <reason>"`
    (escalation; re-block apos unblock momentaneo)
  - `task move <id> rejected --reason "<categoria>: ..."` (Bernard
    `reject-task --commit`)
  - `task set-dispatch-payload <id> --merge --payload {last_clarification_*}`

## Skills

- Subprocess `claude -p` (drafter, Plano B Spike-5 - zero pip install).
- Read filesystem em `bevox-knowledge/` e
  `~/.openclaw/docs/superpowers/plans/`.
- Subprocess `~/.openclaw/kanban-tasks/cli.sh task block/unblock/
  move/set-dispatch-payload`.

## Limites

1. **NUNCA inventa source.** Safety enforcement valida cada path
   citado existe no filesystem. Hallucination guard: confidence=safe
   forced→unsafe se sources invalidas.
2. **Safe → auto-unblock permitido.** Gate humano dispensado pq source
   guard validou. **Unsafe → sempre Bernard decide** (override |
   reject-task | redraft | edit+relaunch).
3. **Reject-task SEMPRE exige `--commit` humano.** Agent NUNCA muta
   `task.status = rejected` autonomamente; apenas propoe via exit code 3
   (`CLARIFICATION_PROPOSES_REJECTION`).
4. **Categorias rejection fechadas**: `task_malformed`,
   `spec_inconsistent`, `requires_re_decomposition`, `inexecutable`,
   `manual`. Outras strings rejeitadas com `INVALID_REJECT_CATEGORY`.
5. **NAO modifica dispatch_payload autoral do scrum-master.**

## Approvals

- **Auto-resolve safe**: sem approval card (gate dispensado pelo source
  guard).
- **Override / reject-task**: EXIGE flag `--commit` humano explicit.
- Hard limits gerais (ADR-006) aplicam.

## KPIs

- Clarifications/semana.
- Taxa auto-resolve safe / total clarifications.
- Taxa escalation (unsafe) / total — alto = sinal de spec_refs ralo OR
  perguntas mal escopadas pelo executor OR drafter prompt-tuning fraco.
- Tempo medio question→answer (proxy de latencia).
- `--project-override`-equivalent NAO existe aqui (clarification nao
  decide project; herda da task).

## Playbook operacional

### 1. Registrar dispatch

Append em `~/.openclaw/workspace/shared/outputs/agent-dispatch.jsonl`.

### 2. Ask cycle

- Gera seq + clarification_id.
- Escreve `questions/<id>.md`.
- `task block --reason "clarification_required: <q-summary-80c>"`.
- Merge metadata: last_clarification_id, question_path, count.

### 3. Draft

- `context_loader.build_context_bundle`: task + dispatch_payload +
  spec_refs + plan_ref + ADRs citadas (read-only filesystem).
- `drafter.draft_answer`: subprocess `claude -p` com prompt
  estruturado (model default: claude-haiku-4-5).
- Parse JSON response (answer, sources, confidence, escalation_reason).
- `safety.enforce_safety`: valida sources existem; downgrade safe→unsafe
  se hallucination.

### 4. Resolve

- **Safe**: unblock; merge resolved_at + confidence; emit signal `safe`;
  return answer no stdout (se `--and-wait`).
- **Unsafe**: write escalation symlink; `task block` com reason
  `clarification_escalation_required`; merge escalated_at + unsafe; se
  `--and-wait`: poll loop ate signal humano (`override` | `rejected`).

### 5. Human intervention (escalation)

- `override --commit`: write override answer (`*-override.md`); unblock;
  emit signal `override`; clear escalation symlink.
- `reject-task --reason "<cat>: ..." --commit`: valida categoria;
  `task move rejected`; emit signal `rejected`.
- `redraft`: re-invoca draft com mesma pergunta + novo clarification_id.

## Boundary com outros agents

Ver §9 + §13 da spec. Clarification **NAO**:
- Seleciona task (responsabilidade do dispatcher).
- Gera briefing inicial (responsabilidade do dispatcher).
- Move pra `testing/done` (gate humano OR dispatcher auto-testing).
- Multi-round chain numa mesma pergunta (cada clarification isolada;
  Claude Code pode fazer sequenciais via novo `ask`).

## Volume minimo

- Manter L1: pelo menos 1 clarification/mes.
- Promocao L2 (ADR-003): pelo menos 5/sem por 4 sem consecutivas, taxa
  auto-resolve safe ≥ 70%, zero rejection autonoma (sempre via Bernard
  `--commit`).

## Historico de levels

- L1 desde 2026-04-19.

---

## Pull mode (daemon) — ADR-009 + E10 wave-1 operational-loop-hardening

Desde 2026-04-22 o clarification-agent opera em 2 modos:

- **Push** (CLI `ask` invocada por Claude Code): intocada.
- **Pull** (subcomando `poll-tick` via systemd timer 10min): novo.

### Comando novo

- `vox clarification poll-tick [--once] [--dry-run] [--json]`
- `vox clarification poll-status [--json]`

### Pipeline do tick

1. Kill-switch check (`poll.disabled`) + fcntl lock global (`poll.lock`).
2. Lista tasks `blocked=true` do kanban state.json.
3. Pre-filter determinístico (skip non-clarification reason, already-pending, budget, dedup-hash, lock).
4. Fast-fail em payload incompleto → escalation `dispatch_payload_incomplete` zero-LLM.
5. LLM path local-first (ollama/qwen2.5-coder:14b) → fallback cloud 1x em unsafe.
6. Resolve: safe→auto-unblock; unsafe→escalation + hook `unsafe_escalation_emitted`.
7. Audit append-only em `poll.jsonl`.

### Observabilidade

- Events de interesse no `poll.jsonl`: `tick_started`, `drafter_used_local`, `drafter_escalated_to_cloud`, `fast_fail_payload_incomplete`, `clarification_auto_unblock`, `unsafe_escalation_emitted`, `tick_finished`.
- Health: service `openclaw-clarification-daemon` registrado em `bevox-knowledge/20_architecture/health-registry.yml`.

### Rollback

- Desabilitar timer: `systemctl --user disable --now openclaw-clarification-daemon.timer`.
- Killswitch temporário: `touch ~/.openclaw/clarification-agent/poll.disabled`.
- Rollback total do refactor: `cp lib/drafter.py.pre-provider.bak lib/drafter.py` + `cp lib/api.py.pre-poll.bak lib/api.py` + `cp lib/store.py.pre-poll.bak lib/store.py` + `cp lib/lifecycle.py.pre-poll.bak lib/lifecycle.py`.

---

## Push mode (Telegram notifier) — E10/OH wave-2

Serviço standalone que notifica Bernard via Telegram quando
nova escalation unsafe aparece em `escalations/`. Desacoplado do daemon
pull — não depende do clarification-daemon rodar.

**Ativar:**

```bash
cp ~/.openclaw/clarification-agent/systemd/openclaw-clarification-notifier.{service,timer} \
   ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now openclaw-clarification-notifier.timer
```

**Desativar (rollback):**

```bash
systemctl --user disable --now openclaw-clarification-notifier.timer
```

Escalations continuam sendo escritas normalmente; apenas o push Telegram
para. Zero dado perdido.

**Forçar re-envio de todas as escalations pendentes:**

```bash
rm ~/.openclaw/clarification-agent/notifier-state.json
# próximo tick vai disparar uma msg por escalation ainda em escalations/
```

**Observabilidade:**

- Audit append-only: `~/.openclaw/clarification-agent/notifier.jsonl`
- State idempotência: `~/.openclaw/clarification-agent/notifier-state.json`
- Health: entrada `openclaw-clarification-notifier` em `bevox-knowledge/20_architecture/health-registry.yml`
