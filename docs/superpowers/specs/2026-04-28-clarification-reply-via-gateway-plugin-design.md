# Design — Clarification Reply via Gateway Plugin

> **Status:** design aprovado (pendente review do escrito)
> **Data:** 2026-04-28
> **Decisor:** Bernard
> **Escopo:** OpenClaw runtime + workspace-template + bevox-knowledge
> **Origem:** audit operacional do caminho de poll-replies do `clarification-agent`
> **Próximo passo:** writing-plans skill cria plano de implementação executável

---

## 1. Contexto

Auditoria operacional em 2026-04-28 do caminho de ingestão de respostas de clarifications do `clarification-agent` revelou **5 defeitos auditáveis** rodando em produção:

1. **Race com OpenClaw notifier** — `reply_handler.poll_telegram_replies` (legacy) consome `getUpdates` no mesmo `TELEGRAM_BOT_TOKEN` que o gateway central. Cursor `last_update_id` ficou nulo (consumer mais lento perde os updates).
2. **Persistência incompleta** — `notifier-state.json` grava `telegram_message_id` mas `chat_id`, `thread_id`, `project`, `sent_at` ficam `None`. Viola §"Requisitos de implementação" do `CLARIFICATION_FLOW_CONTRACT.md`.
3. **Redescoberta tardia** — `dynamic_reply_handler` recompõe destino de cada clarification em poll-time via 3 estratégias em cadeia (`_find_project_slug` → kanban state.json → projects-meta.json). Cada estratégia é ponto de falha.
4. **Drift do bot de confirmação** — `send_confirmation_message` envia pelo `TELEGRAM_BOT_TOKEN` (operacional) mesmo quando a clarification original foi enviada em bot de projeto.
5. **Dois handlers paralelos coexistindo** — `reply_handler.poll_telegram_replies` (single-bot legacy) + `dynamic_reply_handler.poll_dynamic_replies` (multi-bot). `cmd_poll_replies` tenta o dynamic; cai no legacy se falhar. Ambos competem pelo mesmo update stream.

Em paralelo, o plugin de gateway `clarification-commands` (delivered wave-3 OH 2026-04-22) **já roda em produção** em todos os 4 gateways (`openclaw-gateway` + `openclaw-gateway-bevox-site` + `openclaw-gateway@bevox-mobile` + `openclaw-gateway@financeiro`), expondo 5 comandos `/clr_*` + reply-to-message inference via SDK.

**Pergunta canônica que este design responde**: qual é o caminho único de ingestão de reply de clarification, e como tornar a infra fisicamente livre dos defeitos auditados?

## 2. Decisões travadas no brainstorming (2026-04-28)

| # | Decisão | Justificativa |
|---|---|---|
| 1 | **Roteamento per-projeto + fallback central** | Bot do projeto já tem gateway com plugin instalado; central serve projetos sem mapping em `projects-meta.json` |
| 2 | **`notifier-state.json` é a SoT — schema v2 com tupla canônica completa** | Elimina redescoberta tardia; alinha com §"Requisitos de implementação" do contrato |
| 3 | **Matching exclusivo via `reply_to_message.message_id` (Strat 3)** | Lookup O(1) no notifier-state; imune a mudanças no formato da mensagem; UX limpa (swipe-reply nativo) |
| 4 | **Token discipline hard rule: 1 token = 1 consumer** | Race fisicamente impossível por construção, não por convenção |
| 5 | **Consolidar no plugin do gateway, deletar daemon paralelo** | Plugin já delivered e cobre 3 caminhos (swipe-reply, /clr_*, CLI manual); daemon não acrescenta cobertura, só competição |

## 3. Arquitetura

```
┌──────────────────────┐    ┌──────────────────────┐
│ clarification-agent  │    │ ~/.openclaw/         │
│ (Python)             │    │   extensions/        │
│ ─ notifier.py        │───▶│   clarification-     │
│   escreve state v2   │    │   commands/ (Node)   │
│ ─ reply_handler.py   │    │   plugin in 4        │
│   handle_reply()     │◀───│   gateways           │
│ ─ cli.sh answer ...  │    │     (subprocess)     │
└──────────────────────┘    └──────────────────────┘
            ▲                          ▲
            │                          │
       fallback                    swipe-reply OR
       manual CLI                  /clr_* commands
                                       │
                                       ▼
                              ┌──────────────────┐
                              │  Telegram        │
                              │  (1 gateway =    │
                              │   1 consumer     │
                              │   por bot/token) │
                              └──────────────────┘
```

- **1 SoT compartilhada**: `notifier-state.json` schema v2. Python notifier escreve, Node plugin lê.
- **2 caminhos de ingestão automatizados**: swipe-reply nativo (lookup via `reply_to_message.message_id`) e `/clr_override <task> "<texto>"`. Ambos dentro do plugin.
- **1 fallback manual**: `cli.sh answer <cid> --answer "..."`.
- **0 caminhos de polling externos**: poll-replies daemon é deletado.

## 4. Componentes

### 4.1 Mudanças em `clarification-agent/`

| Caminho | Mudança | Tamanho |
|---|---|---|
| `lib/notifier.py` | Schema v2: tupla completa por entry; valida `topics.clarifications` antes de enviar; fallback central + warning estruturado | ~30 linhas modificadas |
| `lib/store.py` | `load_state_v2()`, `migrate_v1_to_v2()`, schema bump; backup automático antes de migrar | ~60 linhas adicionadas |
| `lib/api.py` | Remove `cmd_poll_replies` + parser; mantém `cmd_answer` e `cmd_poll_tick` (drafter pull, não confundir) | ~50 removidas |
| `lib/reply_handler.py` | Reduz a `handle_reply()` + `unblock_task()` + `send_confirmation_message()`. Confirmation usa `entry.token_alias` (não `TELEGRAM_BOT_TOKEN`) | ~250 removidas, ~20 modificadas |
| `notifier-state.json` | Schema v1 → v2 (file format change, migrado in-place no primeiro start) | format change |

### 4.2 Componentes deletados

| Caminho | Ação |
|---|---|
| `lib/poller.py` | DELETAR |
| `lib/dynamic_reply_handler.py` | DELETAR |
| `lib/*.pre-poll.bak` (3 arquivos) | DELETAR |
| `cli.sh poll-replies` (subcommand) | REMOVIDO via api.py |
| `bot-states/` (diretório) | DELETAR |
| `telegram-reply-state.json` | DELETAR |
| `systemd/openclaw-clarification-daemon.service` | DELETAR (após `disable + stop`) |
| `systemd/openclaw-clarification-daemon.timer` | DELETAR (após `disable + stop`) |

`openclaw-clarification-notifier.service/.timer` **permanece** — notifier de envio é independente.

### 4.3 Plugin `clarification-commands` — extensão (Node.js)

1. **Schema v2 awareness** — ler entries com `{token_alias, chat_id, thread_id, telegram_message_id, status, project, sent_at}`. Construir `Map<message_id, entry>` em memória ao receber update.
2. **Cross-validation no swipe-reply path** — quando update tem `reply_to_message.message_id`, lookup encontra entry; validar `update.chat.id == entry.chat_id` && `update.message_thread_id == entry.thread_id` && `entry.status == "pending"`. Falha em qualquer check → log warning, no-op.
3. **Cross-validation no `/clr_override <task>` path** — lookup todas entries `pending` com `task_id == arg`; escolher mais recente por `sent_at`. Se nenhuma: responder no chat "nenhuma clarification pendente para `<task>`".
4. **Idempotência** — após CLI retornar sucesso, plugin **não** atualiza notifier-state diretamente; `cmd_answer` faz isso (write `status="resolved"`, `resolved_at`, `resolved_via`). Plugin só relê na próxima invocação.
5. **CLI subprocess** — continua chamando `clarification-agent answer` via `execFile` com `--actor telegram:<sender_id>`.

### 4.4 Schema v2 do `notifier-state.json`

```json
{
  "schema_version": 2,
  "heartbeat_at": "2026-04-28T14:00:00Z",
  "notifications": {
    "T-0105-clr-1": {
      "task_id": "T-0105",
      "project": "bevox-site",
      "token_alias": "project-bevox-site",
      "chat_id": "-100xxxxxxxxxx",
      "thread_id": 18,
      "telegram_message_id": 273,
      "sent_at": "2026-04-28T11:36:01Z",
      "status": "pending",
      "resolved_at": null,
      "resolved_via": null
    }
  }
}
```

- `status`: `pending` | `resolved` | `failed` | `orphan`
- `resolved_via`: `telegram_reply` | `slash_command` | `manual_cli` | `null`
- `orphan`: entries pré-migração que não conseguiram backfill

### 4.5 Migração v1 → v2

Primeiro start do notifier após deploy:
1. `store.load_state()` detecta `schema_version != 2`.
2. Backup automático: copia para `notifier-state.v1.bak`.
3. Para cada entry existente:
   - Tenta resolver `project` via `kanban-tasks/state.json` (lookup por `task_id`).
   - Tenta resolver `(token_alias, chat_id, thread_id)` via `projects-meta.json` para esse projeto.
   - Sucesso → `status="pending"` (assume que ainda pode ser respondida).
   - Falha em qualquer resolução → `status="orphan"`, fields parciais.
4. `schema_version: 2` escrito atomicamente (`os.rename`).

Orphans observados hoje (T-0024-clr-4, T-0105-clr-2 com fields nulos) provavelmente vão para `status="orphan"`. Bernard pode resolver via `cli.sh answer <cid> --answer "..."`.

### 4.6 Token alias registry — função pura

Sem arquivo separado. Resolução determinística:

```python
def resolve_token_alias(project_slug: str | None) -> tuple[str, str]:
    if project_slug is None:
        return ("openclaw-central", env["TELEGRAM_BOT_TOKEN"])
    meta = load_projects_meta()
    entry = meta.get(project_slug, {})
    bot_token_env_key = entry.get("bot_token_env")  # ex: "BOT_TOKEN_VOZ_BEVOX_SITE"
    if bot_token_env_key and env.get(bot_token_env_key):
        return (f"project-{project_slug}", env[bot_token_env_key])
    return ("openclaw-central", env["TELEGRAM_BOT_TOKEN"])  # fallback
```

Plugin (Node) tem implementação espelhada — mesma fonte (`projects-meta.json` + env).

### 4.7 Pré-condição operacional do projeto (notifier valida no envio)

```python
def send_clarification(cid, task_id, project):
    if project:
        meta_entry = projects_meta.get(project)
        thread_id = meta_entry.get("telegram", {}).get("topics", {}).get("clarifications")
        if not thread_id:
            log_event("clarification_fallback_to_central",
                      cid=cid, project=project, reason="topics.clarifications missing")
            token_alias, token, chat_id, thread_id = resolve_central()
            send_proactive_warning_to_central(project, cid)
        else:
            token_alias, token, chat_id = resolve_project(project)
    else:
        token_alias, token, chat_id, thread_id = resolve_central()
    # ... send + persist schema v2 entry ...
```

### 4.8 Bootstrap garante plugin de clarifications por default

`scripts/bootstrap-telegram-agent.sh`:

```diff
- SKILLS="knowledge-sync-commands"
+ SKILLS="knowledge-sync-commands,clarification-commands"
```

E force-inject de ambos no Python heredoc:

```python
for required in ("knowledge-sync-commands", "clarification-commands"):
    if required not in skills:
        skills.insert(0, required)
```

Mais validação pós-`systemctl enable`:

```bash
if ! python3 -c "import json,sys; c=json.load(open('$PROFILE_DIR/openclaw.json')); a=c.get('plugins',{}).get('allow',[]); sys.exit(0 if 'clarification-commands' in a else 1)"; then
    echo "FAIL: clarification-commands not in plugins.allow" >&2
    exit 1
fi
```

Opt-out continua possível com `--skills knowledge-sync-commands` explícito.

## 5. Data flow

```
1. Executor de task precisa input → cli.sh ask <task> --question "..." --and-wait
2. Drafter retorna unsafe → lifecycle escreve question/<cid>.md, escalation/<cid>.md
3. Notifier:
   - resolve target (project ou central; fallback se topics.clarifications ausente)
   - sendMessage Telegram
   - persist notifier-state[cid] = {schema v2 tuple, status=pending}
4. Bernard vê mensagem
5. Bernard responde via 1 dos 3 caminhos:
   (a) swipe-reply nativo
   (b) /clr_override <task> "<texto>"
   (c) cli.sh answer <cid> --answer "..."
6. Plugin (a, b) ou cmd_answer (c) lookup notifier-state, cross-validate, chama cmd_answer
7. cmd_answer:
   - process_reply_file
   - clear_escalation_symlink
   - merge_dispatch_payload
   - emit_signal
   - kanban: task unblock + move ready
   - notifier-state[cid].status=resolved
   - send_confirmation_message via entry.token_alias
8. cron-dispatcher detecta task ready → re-dispatcha
```

## 6. Error handling

| Falha | Onde | Resposta | Recovery |
|---|---|---|---|
| `sendMessage` 4xx | notifier | log error; retry next tick (max 3) | operador corrige `projects-meta.json` |
| `sendMessage` 5xx | notifier | retry com backoff exponencial | self-heals |
| `topics.clarifications` ausente | notifier | fallback central + warning estruturado + msg proativa no central | operador roda `init_telegram_topics.py --slug X` |
| Plugin lookup miss (`reply_to.message_id` desconhecido) | plugin | log info DEBUG; no-op | esperado: reply a outra mensagem |
| Plugin cross-validation fail | plugin | log warning; no-op | provável: cid copiado para chat errado |
| Plugin: `status != pending` | plugin | log info; no-op idempotente | esperado em race |
| Plugin: CLI subprocess timeout (>30s) | plugin | log error; mensagem no chat | manual retry |
| Plugin: CLI exit != 0 | plugin | log error com exit code; mensagem no chat | depende do exit code |
| `cmd_answer`: kanban unblock fail | cmd_answer | log error; exit 2; **NÃO** atualiza status | manual via `vox kanban task unblock` |
| `cmd_answer`: notifier-state write fail | cmd_answer | log error; tarefa já desbloqueada; status fica pending | self-recovers |
| `cmd_answer`: confirmation send fail | cmd_answer | log warning; **não falha** o comando | best-effort |
| Notifier-state corrupto (JSON parse error) | store | retorna empty; log error crítico; restaura backup `.v1.bak` se disponível | manual review |
| Plugin: schema v1 detectado | plugin | log warning "migration not yet run"; trata como orphan | notifier migra no próximo write |

## 7. Observabilidade

### 7.1 Eventos novos em `clarification-agent/notifier.jsonl`

```json
{"ts":"...","event":"clarification_sent","cid":"T-0105-clr-1","task_id":"T-0105","project":"bevox-site","token_alias":"project-bevox-site","chat_id":"-100...","thread_id":18,"message_id":273}
{"ts":"...","event":"clarification_fallback_to_central","cid":"T-0105-clr-1","project":"bevox-site","reason":"topics.clarifications missing"}
{"ts":"...","event":"clarification_send_failed","cid":"...","attempt":1,"error_class":"TelegramHTTP4xx","error_detail":"..."}
{"ts":"...","event":"clarification_orphan","cid":"T-0024-clr-4","reason":"schema v1 migration could not resolve project"}
```

### 7.2 Eventos novos em `clarification-agent/reply.jsonl` (novo arquivo)

```json
{"ts":"...","event":"reply_received","cid":"T-0105-clr-1","source":"telegram_reply","actor":"telegram:7593...","matched_via":"reply_to_message_id"}
{"ts":"...","event":"reply_validation_failed","cid":"T-0105-clr-1","reason":"thread_id mismatch","expected":18,"got":22}
{"ts":"...","event":"reply_resolved","cid":"T-0105-clr-1","task_id":"T-0105","resolved_via":"telegram_reply","elapsed_ms_since_sent":432100}
```

### 7.3 Métricas derivadas

| Métrica | Definição | Sinal de alerta |
|---|---|---|
| `clarification_pending_count` | entries com `status=pending` | >5 = backlog operacional |
| `clarification_pending_age_max_h` | idade da pending mais antiga | >24h = Bernard ofuscado |
| `clarification_orphan_count` | entries com `status=orphan` | >0 = drift documental |
| `clarification_resolved_via_ratio` | telegram_reply vs slash_command vs manual_cli (rolling 7d) | observa UX |
| `clarification_send_failure_rate` | (failed / sent) últimas 24h | >5% = problema infra |
| `clarification_fallback_to_central_rate` | (fallback / sent) últimas 24h | >0% = projeto sem topics inicializados |

### 7.4 Visualização hierárquica na MC (out of scope desta wave; spec aqui declara o contrato)

Drill-down esperado: `Projeto → Sprint → Task → Clarifications da task`.

- **Painel da task** lista entries de `notifier-state.json` filtradas por `task_id`. Cada entry mostra estado, bot, tópico (link `https://t.me/c/<chat>/<message_id>`), timeline, validações falhadas, botão "answer manually".
- **Painel da sprint**: agregação `count by status` das tasks da sprint.
- **Painel do projeto**: rolagem das sprints; `fallback_to_central_rate` por projeto.

Razão: clarification é **atributo de uma task**, não objeto solto. Lista global é difícil de operar.

Dependências satisfeitas: E2 mc-sprints-page (delivered 2026-04-25), E2 mc-projects-redesign (delivered 2026-04-26), E10 sprint-per-project (delivered 2026-04-25).

Pendências (fora desta wave): endpoint HTTP `GET /api/notifier-state?task_id=X` (depende E5/F4 wave-MC-HTTP-API), componente UI `<TaskClarificationsPanel taskId=...>`, modal de answer manual.

Esta wave **só garante que `notifier-state.json` schema v2 tem todos os campos necessários para essa UI futura**.

### 7.5 Resilience properties

1. Idempotência ponta a ponta: `cmd_answer` pode ser chamado N vezes para mesmo cid → primeira resolve, demais são no-op.
2. At-least-once delivery sem duplicate side-effect: lookup `status=resolved` → skip.
3. Crash do gateway durante reply: update fica no buffer SDK; ao retomar, reprocessa.
4. Notifier-state corrupto: pior caso → todas viram orphan; CLI manual continua resolvendo.
5. Sem race com OpenClaw notifier: token discipline garante por construção.

## 8. Plano de docs em `workspace-template/`

### 8.1 Arquivos com mudança

| Arquivo | Mudança |
|---|---|
| `shared/CLARIFICATION_FLOW_CONTRACT.md` | Reescrever inteiro (esqueleto novo: §"Caminhos de ingestão canônicos" com 3 caminhos, §"Pré-condições do canal Telegram", §"SoT da clarification" com schema v2) |
| `AGENTS.md` (L226-264) | Substituir §"Telegram Poll-Replies Dinâmico" por bloco curto: "Reply é responsabilidade do plugin do gateway. Agente nunca implementa polling Telegram." |
| `memory/integrations/clarification.md` | Reescrever §"Notificação Telegram" + §"Como Bernard responde" (3 caminhos equivalentes; agente não precisa saber qual foi usado) |
| `memory/integrations/telegram-bot.md` | Atualizar §"Bootstrap automatizado" (`--skills` default inclui `clarification-commands`); adicionar §"Pré-condições para clarification reply" (3 itens); §"Anti-patterns" ganha "NÃO implementar polling Telegram em código de agente" |
| `TOOLS.md` (L18, L46-49) | Remover qualquer menção a `poll-replies` no CLI cheatsheet; manter `ask`, `answer`, `list`, `poll-tick` |
| `HEARTBEAT.md` (L11-12) | Verificar se `cli.sh list --open` continua válido (provavelmente sim — leitura) |
| `memory/MEMORY.md` (L24) | Atualizar one-line hook do link para `clarification.md` |

### 8.2 OK — sem mudança

`shared/OPERATING_RULES.md` (L255-258), `memory/integrations/dispatcher.md`, `memory/integrations/kanban.md`, `USER.md`, `BOOT.md`, `SOUL.md`, `IDENTITY.md`, `TEAM.md`, `PRODUCT_DELIVERY_PIPELINE.md`, `KNOWLEDGE_INTEGRATION_CONTRACT.md`.

### 8.3 Estratégia de propagação para os 11 workspaces materializados

11 workspaces materializados existem (`workspace-bevox-mobile`, `-bevox-site`, `-healthcheck-agent`, `-healthcheck-light`, `-memory-consolidation-light`, `-memory-consolidation-ultralight`, `-shared`, `-watchdog-agent`, `-watchdog-light`, `-weekly-review-agent`, `-template`). Cada um carrega cópia parcial do template — sem mecanismo automático de re-render.

Recomendação: **opção C — marcar como dívida e tratar fora desta wave** (workspaces materializados ficam stale; novos materializados após deploy ficam corretos). Capturado no PRD `knowledge-as-living-system` §5.4 questão 13 e no inbox `2026-04-28-workspace-template-structure-investigation.md`.

### 8.4 Out of scope desta wave

- Reescrever a estrutura do `workspace-template/` (folders, hierarquia AGENTS.md vs SOUL.md vs IDENTITY.md). Capturado em `bevox-knowledge/00_inbox/openclaw/2026-04-28-workspace-template-structure-investigation.md`.
- Adicionar checklist documental novo aos agentes (depende do PRD investigativo).

## 9. Plano de docs em `bevox-knowledge/`

### 9.1 Sumário consolidado

| # | Arquivo | Padrão | Ação |
|---|---|---|---|
| 1 | `30_adr/company-os/ADR-011-clarification-reply-via-gateway-plugin.md` | criar | nova ADR |
| 2 | `30_adr/company-os/ADR-009-clarification-loop-unified-local-first.md` | B (in-place) | status: `parcialmente superseded por ADR-011`; §Consequências ganha bloco 2026-04-28 |
| 3 | `35_specs/openclaw/2026-04-28-clarification-reply-via-gateway-plugin.md` | criar | nova spec (mirror desta seção 1-7 + delivery plan) |
| 4 | `35_specs/openclaw/2026-04-21-e10-telegram-reply-handler.md` (delivered) | annotation | header "Extended by 2026-04-28-..." |
| 5 | `35_specs/openclaw/2026-04-21-e10-clarification-daemon-local-first.md` | B (in-place) | status: `parcialmente superseded`; nota topo: drafter local-first e push-mode permanecem |
| 6 | `35_specs/openclaw/2026-04-23-clarification-telegram-enhancement.md` | **A (mover)** | mover para `_retired/` + §Aposentadoria |
| 7 | `35_specs/openclaw/2026-04-19-e10-dispatcher-and-clarification-agents.md` | annotation | header de evolução |
| 8 | `20_architecture/openclaw/clarification-agent.md` | edição | §"Reply ingestion" reescrita; remove referências ao daemon |
| 9 | `20_architecture/_shared/health-registry.yml` | edição | DELETAR linhas 219-227 (entrada `openclaw-clarification-daemon`) |
| 10 | `40_roadmap/_shared/delivery-tracker.yml` | edição | adicionar wave `clarification-reply-via-gateway-plugin` ao bloco E10 OH-followup |
| 11 | `40_roadmap/company-os/2026-04-09-openclaw-company-os-roadmap.md` | edição | linha narrativa curta |
| 12 | `decision-log.md` | **não tocar** | escopo do PRD knowledge-as-living-system |
| 13 | `_retired/README.md` | **não tocar** | escopo do PRD knowledge-as-living-system |
| 14 | `00_inbox/openclaw/2026-04-28-workspace-template-structure-investigation.md` | **já criado** nesta sessão | — |
| 15 | `10_prd/_shared/2026-04-28-knowledge-as-living-system-investigation-prd.md` | **já criado** nesta sessão | — |

### 9.2 Padrões de aposentadoria aplicados

- **Padrão A** (move para `_retired/` + §Aposentadoria): item 6 — descreve estado com bugs.
- **Padrão B** (status field in-place): itens 2 e 5 — capability sobrevive, só implementação evoluiu.
- **Annotation** (header "Extended by"): itens 4 e 7 — não são deprecated, evolução.
- ADRs nunca movem (item 1 = nova; item 2 = status muda).

### 9.3 Skeletons relevantes

#### ADR-011 (item 1)

```markdown
# ADR-011: Clarification Reply via Gateway Plugin (deprecation of poll-replies daemon)

- **Status:** proposta
- **Data:** 2026-04-28
- **Decisor:** Bernard
- **Tags:** agents, clarification, telegram, gateway-plugin, e10
- **Supersedes:** parts of ADR-009 §Recomendação Opção C (coexistência daemon+plugin)

## Contexto e Problema
Audit 2026-04-28 revelou 5 defeitos concretos no daemon poll-replies
(race com TELEGRAM_BOT_TOKEN, persistência incompleta da triple,
redescoberta tardia, drift do bot de confirmação, dois handlers
paralelos). Plugin já cobre os 3 caminhos canônicos. Coexistência
ADR-009 §Opção C é redundante.

## Opções
- A. Manter daemon + plugin (status quo): race confirmado.
- B. Manter só daemon: regride; perde UX swipe-reply + /clr_*.
- C. Manter só plugin (recomendada): token discipline por construção.

## Recomendação
Opção C. Plugin já delivered; não acrescenta cobertura adicional ter
daemon paralelo, apenas competição.

## Consequências
Positivas: race fisicamente impossível; ~800 LOC removidos.
Negativas: spec wave-3 ganha multi-bot awareness; contrato reescrito.
ADR-009 §Opção C parcialmente superseded.

## Notas
Spec: 35_specs/openclaw/2026-04-28-clarification-reply-via-gateway-plugin.md
Pré-condições: init_telegram_topics.py + plugin instalado + gateway ativo.
Gaps correlatos: 00_inbox/openclaw/2026-04-28-workspace-template-...,
                  10_prd/_shared/2026-04-28-knowledge-as-living-system-...
```

#### Spec canônica (item 3)

Mirror das §§1-7 deste design + §"Plano de delivery" em phases (ver §10 abaixo) + §"Critérios de aceitação" + §"Out of scope" + §"Dependências de UI futura" + §"Referências".

#### Health-registry edit (item 9)

```diff
-  openclaw-clarification-daemon:
-    name: "OpenClaw Clarification Daemon (pull)"
-    owner: Bernard
-    epic: E10
-    ...
-      unit: openclaw-clarification-daemon.timer
-    since: 2026-04-21
```

`openclaw-clarification-notifier` permanece — serviço diferente.

#### Delivery-tracker edit (item 10)

```yaml
- id: clarification-reply-via-gateway-plugin
  wave: E10/clarification-reply-via-gateway-plugin
  spec: 35_specs/openclaw/2026-04-28-clarification-reply-via-gateway-plugin.md
  adr: 30_adr/company-os/ADR-011-clarification-reply-via-gateway-plugin.md
  status: proposed
  prerequisites: [clarification-daemon-local-first, telegram-reply-handler]
  deliverables:
    - "notifier-state.json schema v2"
    - "plugin clarification-commands estendido (multi-bot + cross-validation)"
    - "daemon openclaw-clarification-daemon aposentado (units + state files removidos)"
    - "bootstrap-telegram-agent.sh força clarification-commands no default"
```

## 10. Plano de delivery (sumário; detalhe via writing-plans)

| Phase | Conteúdo | Risco |
|---|---|---|
| 0 | `disable + stop` daemon `openclaw-clarification-daemon.timer/.service`; backup `notifier-state.json` para `.v1.bak` | baixo (timer fica inativo; envio continua via notifier) |
| 1 | Schema v2 helpers em `store.py` + migração v1→v2 | baixo (idempotente) |
| 2 | `notifier.py` valida pré-condição `topics.clarifications` + escreve schema v2 | médio (mudança de write path) |
| 3 | `reply_handler.py` reduzido; confirmation usa `entry.token_alias` | baixo |
| 4 | Plugin (Node) ganha schema v2 awareness + cross-validation + idempotência | médio (Node, fora do escopo Python) |
| 5 | `bootstrap-telegram-agent.sh` força plugin no default + validação pós | baixo |
| 6 | Deletar legacy: `lib/{poller,dynamic_reply_handler}.py`, `*.pre-poll.bak`, `bot-states/`, `telegram-reply-state.json`, `systemd/openclaw-clarification-daemon.*`; `cmd_poll_replies` removido de api.py | baixo (já apagado de runtime na phase 0) |
| 7 | Smoke test: 3 caminhos × 2 bots (central + bevox-site); cada um resolvendo 1 cid pendente | médio (depende de ter cid pendente disponível) |
| 8 | Atualizar workspace-template (7 arquivos com mudança em §8.1) | baixo |
| 9 | Atualizar bevox-knowledge (15 itens em §9.1) — branch `draft/adr-011-clarification-reply-via-gateway-plugin` | médio (canônico, exige approval) |

Cada phase é um commit separado. Phase 9 vai em branch `draft/*` e é mergeada para `main` só com approval explícito.

## 11. Critérios de aceitação

- [ ] `notifier-state.json` schema v2 ativo; orphans pré-migração marcados como `status="orphan"`
- [ ] swipe-reply nativo desbloqueia task em bot central + bot bevox-site
- [ ] `/clr_override <task> "<texto>"` funciona em ambos
- [ ] `cli.sh answer <cid> --answer "..."` continua funcionando
- [ ] confirmação chega no MESMO bot que enviou a clarification original
- [ ] daemon deletado: `systemctl --user list-units` não mostra `openclaw-clarification-daemon`
- [ ] `notifier.jsonl` + `reply.jsonl` populados com eventos do schema novo
- [ ] `bootstrap-telegram-agent.sh` em dry-run com flags default produz `openclaw.json:plugins.allow` contendo `clarification-commands`
- [ ] reply em chat/thread errado (cross-validation fail) é log-only, não atualiza task
- [ ] reply para cid já resolvido é no-op idempotente
- [ ] ADR-011, spec nova e mudanças nos 11 outros artefatos de bevox-knowledge em branch `draft/adr-011-...`

## 12. Out of scope (consolidado)

- Dashboard Mission Control com drill-down hierárquico (depende E5/F4 MC HTTP API).
- Alerta automático `pending_age > 24h` (depende E10 alert-notifier).
- Replay forense de eventos.
- Reescrita estrutural do `workspace-template/` (capturado em `00_inbox/openclaw/2026-04-28-workspace-template-structure-investigation.md`).
- Investigação documental de bevox-knowledge (capturada em `10_prd/_shared/2026-04-28-knowledge-as-living-system-investigation-prd.md`).
- Estender `decision-log.md` ou criar índice ativo no README do bevox-knowledge.
- Criar tabela cronológica em `_retired/README.md`.
- Skill nova ou refactor de skills existentes além das 7 mudanças listadas em §8.1.

## 13. Referências

### 13.1 Artefatos criados nesta sessão de brainstorming

- `~/.openclaw/docs/superpowers/specs/2026-04-28-clarification-reply-via-gateway-plugin-design.md` (este documento)
- `bevox-knowledge/10_prd/_shared/2026-04-28-knowledge-as-living-system-investigation-prd.md`
- `bevox-knowledge/00_inbox/openclaw/2026-04-28-workspace-template-structure-investigation.md`

### 13.2 Artefatos canônicos referenciados

- ADR-001 boundary, ADR-002 topology, ADR-005 SoT, ADR-006 autonomy, ADR-009 clarification loop unified (parcialmente superseded), ADR-010 knowledge project separation
- Spec `2026-04-21-e10-telegram-reply-handler.md` (delivered, ganha extension annotation)
- Spec `2026-04-21-e10-clarification-daemon-local-first.md` (parcialmente superseded)
- Spec `2026-04-23-clarification-telegram-enhancement.md` (movida para `_retired/`)
- Spec `2026-04-19-e10-dispatcher-and-clarification-agents.md` (annotation)
- Architecture `20_architecture/openclaw/clarification-agent.md` (reescreve §)
- `40_roadmap/_shared/delivery-tracker.yml` (nova wave)
- `~/.openclaw/workspace-template/shared/CLARIFICATION_FLOW_CONTRACT.md` (reescrito)

### 13.3 Runtime confirmado em produção (2026-04-28)

- Plugin instalado: `~/.openclaw/extensions/clarification-commands/` (Node.js, ESM)
- Gateways carregando plugin: `openclaw-gateway`, `openclaw-gateway-bevox-site`, `openclaw-gateway@bevox-mobile`, `openclaw-gateway@financeiro`
- Daemon paralelo ativo (a deletar): `openclaw-clarification-daemon.timer` (enabled + active)
- Cursor de update do gateway (canônico): `~/.openclaw-<profile>/telegram/update-offset-default.json`

### 13.4 CLAUDE.md (OpenClaw)

Aderência verificada com:
- §3 (bevox-knowledge como SoT) — todos artefatos canônicos atualizados em branch `draft/*`
- §6 (regras de trabalho) — boundary respeitada (OpenClaw + Company OS)
- §8 (autonomia) — mudança canônica em branch draft, não em main silencioso
- §11 (faltar contexto) — gaps capturados em PRD investigativo + inbox
- §13 (anti-patterns) — automação proposta tem governança, observabilidade, rollback
