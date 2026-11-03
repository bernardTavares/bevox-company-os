# Local Inference Adoption — Status Report (pausa em W2)

> **Data:** 2026-04-20, ~18h  
> **Sessão:** iniciada ~07h, pausada ~18h (~11h de trabalho real)  
> **Estado:** W1 completo, W2 arquitetural completo, W2 tuning pendente, W3/W4 não iniciados  
> **Próxima ação:** aguardar decisão do Bernard sobre caminho de tuning  
>
> Documento complementa:
> - `docs/superpowers/specs/2026-04-20-local-inference-adoption-design.md` (design original)
> - `docs/superpowers/plans/2026-04-20-local-inference-adoption-plan.md` (plano original, 39 tasks)

---

## 1. O que foi feito

### 1.1 W1 — Infraestrutura local (DONE)

| Componente | Estado | Como |
|---|---|---|
| NVIDIA driver proprietário | 550.163.01 | Substituiu nouveau; reboot aplicado |
| CUDA | 12.4 via libcuda.so | Instalado junto do driver |
| Ollama daemon | 0.21.0, systemd | user `ollama`, service `openclaw-gateway` indiretamente |
| systemd override | `OLLAMA_KEEP_ALIVE=15m`, `OLLAMA_MAX_LOADED_MODELS=1` | `/etc/systemd/system/ollama.service.d/override.conf` |
| `qwen3:14b` | 9.3 GB | Generalista forte |
| `qwen3:14b-64k` | 9.3 GB (shared blobs) | Modelfile custom `num_ctx=65536` |
| `qwen3:4b` | 2.5 GB | Triage leve |
| `deepseek-r1:14b` | 9.0 GB | Reasoning batch |
| `qwen2.5-coder:{7b,14b}` | 4.7+9.0 GB | Coder (preservado) |
| Plugin `ollama` | enabled em `openclaw.json` | Auto-loaded stock |
| `OLLAMA_API_KEY=local-ollama-placeholder` | em `~/.openclaw/.env` | Destravou auth do provider |
| Smoke test | 65 tok/s (qwen3:4b @ 1k ctx), 33 tok/s (qwen3:14b @ 1k ctx) | via Ollama API direto |

**Por quê:** precondição para qualquer inferência local. Valida hardware + stack. Entrega valor imediato (modelos disponíveis para uso manual fora do OpenClaw via `ollama run` ou API direto).

### 1.2 W2 — Multi-agent runtime (arquitetural DONE, tuning PENDENTE)

#### Arquitetural entregue

| Componente | Estado | Onde |
|---|---|---|
| `agents.list` com 7 agentes | ativo | `openclaw.json` |
| Per-agent `model` field | validado | cada entry em `agents.list` |
| Per-agent workspace isolado | auto-criado pelo bootstrap | `~/.openclaw/workspace-<id>/` |
| Per-agent `agent/auth-profiles.json` | copiado de `main` | manual |
| `agents.defaults.llm.idleTimeoutSeconds: 600` | aplicado | destrava timeout para modelos lentos |
| `models.providers.ollama.models[].contextWindow` | 32k/16k/65k por modelo | override do default 262144 hardcoded |
| 4 crons repointed | via `openclaw cron edit --model ... --session isolated --light-context --timeout-seconds 600` | healthcheck→healthcheck-agent, watchdog→watchdog-agent, memory→memory-consolidation-agent, weekly→weekly-review-agent |
| 6 páginas de agente em bevox-knowledge | criadas | `20_architecture/agents/{healthcheck,watchdog,memory-consolidation,weekly-review,triage,vox-local}-agent.md` |
| `registry.yml` canônico | atualizado + regenerado | `20_architecture/agents/registry.yml` + `registry.md` |

**Shape canônico descoberto:**
```json5
"agents": {
  "defaults": { ...existente... },
  "list": [
    { "id": "<name>", "model": "provider/model", "workspace": "~/.openclaw/workspace-<name>" },
    ...
  ]
}
```

**Per-cron override via CLI:**
```bash
openclaw cron edit <id> \
  --agent <agent-id> \
  --session-key "agent:<agent-id>:telegram:direct:<peer>" \
  --model "ollama/<model>" \
  --session isolated \
  --light-context \
  --timeout-seconds 600
```

#### Correções importantes ao longo do caminho

1. `agents.list` (array) é o shape correto, não `agents.entries` (map) como eu presumi inicialmente — validado em github.com/openclaw/openclaw (plataforma é ativamente mantida, 19k issues).
2. `openclaw cron run <id>` direto funciona, mas editar `cron/jobs.json` manualmente tem race condition — o gateway sobrescreve com visão in-memory. **Usar sempre `openclaw cron edit`**.
3. Quando `agents.list` é populado, o implícito `main` some — precisa declarar `main` explicitamente na lista para preservar a sessão Telegram DM existente (sessionId `1a6ff138-...`).
4. Session locks órfãos (`agents/main/sessions/<id>.jsonl.lock`) causam loops de retry infinito em sessões com `overflow-retry`. Solução: `systemctl --user restart openclaw-gateway` (session locks são liberados no restart).
5. `auth-profiles.json` de cada novo agent precisa ter o profile `ollama` explícito **E** o env `OLLAMA_API_KEY` precisa estar set (mesmo com valor placeholder — Ollama local não valida, mas OpenClaw exige a presença).

**Por quê:**
- Destrava per-cron model override (objetivo original do plano)
- Cada cron vira session isolada → sessão do Vox não mais inflada com crons (separação limpa)
- Privacy gate implementado em `memory-consolidation-agent` (fallback só para `openai-codex/gpt-5.4` OAuth, nunca para openrouter)
- Fundação para W4 (triage + vox-local usarão mesma primitiva)

---

## 2. O que não foi feito — e por quê

### 2.1 W2 tuning (BLOCKED — precisa decisão estratégica)

**Status operacional atual:** os 4 crons migrados **funcionam mas caem para fallback cloud** (openrouter/deepseek-v3.2) na prática. O modelo local é tentado e falha por timeout. **Não quebra produção** (crons continuam recebendo resposta), mas a economia prometida é zero.

**Por que falhou:** 3 causas em camadas (todas identificadas, nenhuma resolvida).

### 2.2 Causa-raiz #1: `num_ctx: 262144` default do OpenClaw

**O que é:** OpenClaw deriva `num_ctx` do Ollama a partir de `provider-catalog.contextWindow` hardcoded. Para `qwen3`, o catalog tem `contextWindow: 262144` (256k).

**Impacto:** Ollama pré-aloca **KV cache proporcional ao num_ctx**, independente do tamanho real do prompt. Para 256k num_ctx + qwen3:4b:
- 40 GB de memória total estimada pelo Ollama
- RTX 3060 tem 12 GB VRAM → offload parcial para CPU (só 8/37 layers na GPU)
- Inferência cai de 65 tok/s para <1 tok/s
- Prompt de 3k tokens leva 10 min em vez de 10 s

**Solução COMPROVADA (aplicada):** override em `models.providers.ollama.models[].contextWindow`. Shape exigido pelo schema:
```json
{
  "id": "qwen3:4b",
  "name": "qwen3:4b",
  "contextWindow": 32768,
  "maxTokens": 2048
}
```
**Mas schema exige `id` + `name`** (ambos), e usar essa config **desativa auto-discovery** — precisa declarar TODOS os modelos manualmente.

### 2.3 Causa-raiz #2: system prompt OpenClaw é grande

**O que é:** mesmo com `--session isolated` + `--light-context`, o OpenClaw injeta:
- System prompt ~11k chars (~3k tokens): instruções sobre tools, reactions, runtime, channel, agentId, model
- Tools schema (JSON das ferramentas disponíveis)
- User message do cron: ~500-1000 chars

Total por turn mínimo: **~4-5k tokens**.

**Impacto:** com contextWindow=16k, alguns runs dão "Context overflow". Com 32k, cabe mas deixa pouca margem para resposta do modelo + thinking tokens.

**Soluções candidatas (não testadas):**
- `agents.defaults.contextInjection: "continuation-skip"` — pula re-injeção de bootstrap em turns de continuação (docs mencionam).
- `agents.defaults.skipBootstrap: true` — desabilita os 5 arquivos de bootstrap (AGENTS.md, IDENTITY.md etc.). **Mas** é global, afeta `main` (Vox) também — inaceitável porque quebra identidade do Vox.
- System prompt custom por agent via IDENTITY.md/SOUL.md minimais (~500 chars cada).
- Reduzir tools expostas via `--tools "exec,read"` (já aplicado em novos crons, mas schema das tools remanescentes ainda é pesado).

### 2.4 Causa-raiz #3: qwen3:4b com contexto 32k ainda é lento em 12 GB

**Benchmark (sem OpenClaw no meio, direto Ollama API):**

| Modelo | 1k ctx | 10k ctx | 50k ctx | 164k ctx |
|---|---:|---:|---:|---:|
| qwen3:4b | 11s | 16s | 100s | ~600s |
| qwen3:14b / 14b-64k | 27s | 69s | 211s | >500s |
| deepseek-r1:14b | 47s | 176s | >600s (timeout) | — |
| qwen2.5-coder:14b | 30s | 121s | 209s | — |

**Impacto:** mesmo com prompt reduzido para 3-5k tokens (possível via causa #2), qwen3:4b em 32k ctx **KV cache** precisa de ~11 GB de VRAM (confirmado: `nvidia-smi` mostrou 11078 MiB). Isso deixa a GPU "travada" em qwen3:4b e impede outros modelos coexistirem.

**Soluções candidatas (patterns de AI engineering):**

#### Pattern 1: Hybrid triage (recomendação para healthcheck/watchdog)
```
state_atual_hash = hash(pending.md + últimos_cron_runs + agenda_files)
se state_atual_hash == último_hash_salvo:
    retorna NO_REPLY                    # 0 LLM calls, 0s
senão:
    LLM com diff mínimo (2k tokens)     # qwen3:4b, ~10s
    salva state_atual_hash
```
- **Aplicável a:** `healthcheck-agent`, `watchdog-agent` (ambos retornam NO_REPLY em ~90% dos casos)
- **Economia:** ~95% dos runs evitam LLM totalmente
- **Implementação:** script Python wrapper ao redor do cron, estado em `~/.openclaw/state/cron-hashes.json`
- **Custo:** ~2-3h de implementação

#### Pattern 2: Distillation (compact-then-decide)
```
grande_ctx (32k) → qwen3:4b: "comprima em 2k tokens" → 2k → qwen3:4b: "decide" → resposta
```
- **Aplicável a:** `weekly-review-agent` (roda 1x/semana, tolera latência)
- **Trade-off:** ~40s total; perde nuance na compressão

#### Pattern 3: Map-Reduce
```
ctx_grande → split em N chunks de 10k → N× qwen3:4b (map, 10s cada) → N summaries → qwen3:14b (reduce, 10s) → final
```
- **Aplicável a:** `memory-consolidation-agent`
- **Tempo total:** ~2-3 min (vs 5-10 min direto)
- **Cobertura:** completa

#### Pattern 4: RAG / pre-filter
```
query → embeddings (nomic-embed-text) → top-5 chunks de memory/ → contexto 2-4k → qwen3:4b → resposta
```
- **Aplicável a:** consolidação, search via Telegram
- **Pré-requisito:** configurar `agents.defaults.memorySearch` com embedding provider

#### Pattern 5: Script paralelo (bypass OpenClaw)
```
systemd timer → Python direto → Ollama /api/generate → Telegram bot API → done
```
- **Bypassa OpenClaw inteiro** para esses crons
- **Tempo por run:** 30-60s
- **Trade-off:** perde framework de session/delivery/logging do OpenClaw
- **Uso:** transição temporária até contextWindow/prompt tuning estar resolvido

### 2.5 W3 — Observability (NÃO INICIADO)

Conteúdo: `logs/model-routing.jsonl` + `check-primary-health.py` detect-and-alert + `routing-log-watcher.sh` systemd timer + integração ao watchdog.

**Por que não:** depende de W2 estar em estado estável para medir. Rodá-lo agora mediria um fluxo que cai para fallback cloud — dados não representativos.

### 2.6 W4 — Triage + Vox-local (NÃO INICIADO)

Conteúdo: fluxo no Telegram que rotea turn humano via `triage-agent` para `vox-local` (trivial) ou Vox main (complexo); skill `/escalate`.

**Por que não:** depende de W2 e requer investigação adicional de routing rules no canal Telegram (`channels.telegram.routing` shape).

### 2.7 Wrap-up (NÃO INICIADO)

Conteúdo: ADR canônica, commit bevox-knowledge, promoção da spec, pending.md final.

---

## 3. Estado técnico atual (snapshot)

### 3.1 Config mutações aplicadas

| Arquivo | Mudança | Backup |
|---|---|---|
| `~/.openclaw/openclaw.json` | plugin ollama, agents.list (7 agents), ollama provider config (baseUrl + models), idleTimeoutSeconds=600, models.list expandida | `.bak.pre-local-inference` |
| `~/.openclaw/cron/jobs.json` | 4 crons repointed (agent+sessionKey+model+timeout+session=isolated) | `.bak.pre-local-inference` |
| `~/.openclaw/.env` | `OLLAMA_API_KEY=local-ollama-placeholder` adicionado | (append) |
| `/etc/systemd/system/ollama.service.d/override.conf` | OLLAMA_KEEP_ALIVE=15m, OLLAMA_MAX_LOADED_MODELS=1 | (novo arquivo) |
| `/etc/apt/sources.list` | `contrib non-free` adicionado | `.bak.pre-nvidia-2026-04-20` |
| `~/.openclaw/agents/*/agent/auth-profiles.json` | copiado de main + adicionado `ollama:default` profile | (novo por agent) |
| `~/.openclaw/modelfiles/qwen3-14b-64k.Modelfile` | Modelfile custom com num_ctx=65536 | (novo) |

### 3.2 bevox-knowledge — branch `draft/local-inference-adoption-2026-04-20`

Uncommitted:
- `20_architecture/agents/registry.yml` (+6 agentes)
- `20_architecture/agents/registry.md` (regenerado)
- 6 arquivos novos: `20_architecture/agents/{healthcheck,watchdog,memory-consolidation,weekly-review,triage,vox-local}-agent.md`

**Commit pendente** (Task 25 do plano). Será feito como parte desta consolidação.

### 3.3 Comportamento operacional

- Crons: rodam, mas caem para fallback cloud (deepseek via openrouter). **Não quebram.**
- Telegram DM Vox: intocado. Rate limit da OpenAI até ~22/04 (~40h mais).
- Ollama daemon: ativo, modelos disponíveis via API direto em `127.0.0.1:11434`.
- Gateway OpenClaw: ativo, health probe OK, 7 agents reconhecidos.
- Nenhum processo órfão (proxy de debug desligado).

### 3.4 Rollback emergencial (se algo quebrar)

```bash
# Restaurar estado pré-W1:
cp ~/.openclaw/openclaw.json.bak.pre-local-inference ~/.openclaw/openclaw.json
cp ~/.openclaw/cron/jobs.json.bak.pre-local-inference ~/.openclaw/cron/jobs.json
systemctl --user restart openclaw-gateway

# Opcional: remover modelos locais (recuperar 30 GB disco):
ollama rm qwen3:14b qwen3:14b-64k qwen3:4b deepseek-r1:14b
# (mantendo qwen2.5-coder:{7b,14b} — esses eram pré-existentes)

# Desabilitar plugin ollama:
# editar openclaw.json removendo "ollama" de plugins.allow e plugins.entries.ollama
```

---

## 4. Decisões pendentes (bloqueio para retomar)

Estas são as decisões que o Bernard precisa tomar antes de qualquer ação executável:

### 4.1 Estratégia de tuning para completar W2

Qual caminho seguir para destravar Ollama local como primary real?

**(A) Pattern 1 (Hybrid triage)** — aplicar em healthcheck/watchdog. 2-3h de código. Economia máxima (~95% dos runs sem LLM). Requer estado persistente.

**(B) Pattern 5 (Script paralelo)** — bypass OpenClaw para os 4 crons. 3-6h. Infra temporária que convive com OpenClaw. Descartável quando tuning estiver pronto.

**(C) Deep tuning do OpenClaw** — investigar `contextInjection`, `skipBootstrap` per-agent (workaround), reduzir tools schema, system prompt custom. 4-6h. Resolve definitivo se funcionar.

**(D) Pausar W2 indefinidamente** — aceitar fallback cloud como estado estável; partir para W3 (observability) que entrega valor independente.

### 4.2 `contextWindow` definitivo para qwen3:4b

- 16k → "Context overflow" (OpenClaw system prompt + tools já passa disso em alguns turns)
- 32k → cabe mas ocupa 11 GB VRAM (quase todo); inferência ainda marginal em prompts realistas
- Opção alternativa: **não usar qwen3:4b** para esses crons; usar qwen3:14b com ctx 32k e aceitar latência de 60-120s

### 4.3 Prioridade entre W3 e W2 tuning

- W3 entrega visibilidade agora sem depender de W2 completar
- W2 tuning pode deixar crons 100% local (zero custo)
- Caminho conservador: W3 primeiro, W2 tuning como iteração de fundo
- Caminho ambicioso: fecha W2 antes, depois W3/W4

### 4.4 Promoção canônica

- Esta spec + plano de implementação + status virar artefato canônico em `bevox-knowledge/35_specs/`?
- Abrir ADR em `bevox-knowledge/30_adr/` sobre "Local Inference Patterns for Cron Agents" (independente de qual pattern escolher)?
- Ou manter tudo em `~/.openclaw/docs/superpowers/` como doc de trabalho?

---

## 5. Recomendação (não-blocante)

Se você quisesse minha opinião sem pedir:

**Agora (curto prazo, 1-2 dias):**
1. Escolher **(A) Pattern 1 Hybrid triage** — maior ROI, alinhado com arquitetura agent-first da Bevox
2. Executar W3 em paralelo (observability independente)
3. Deixar W4 para quando Pattern 1 estiver validado

**Médio prazo (1-2 semanas):**
1. Pattern 3 (Map-Reduce) para memory-consolidation — privacy gate real ganha valor quando rodando local
2. Abrir issue upstream em `openclaw/openclaw` sobre default `contextWindow=262144` ser antagônico a Ollama local em hardware comum (constituir caso real)
3. ADR canônica em bevox-knowledge

**Mas você conhece seu projeto melhor que eu.** Decisão é sua.

---

## 6. Histórico de decisões ao longo desta sessão

Para contexto futuro:
- **Início da sessão (07h):** fix fallback stealth → deepseek/qwen via openrouter (commit `f0daaa7` em `draft/fallback-hardening-2026-04-20`)
- **08h:** instalação do stack local (NVIDIA + CUDA + Ollama + modelos coder)
- **10h:** brainstorm + spec de local inference adoption (design aprovado)
- **12h:** plan escrito (39 tasks, 4 waves)
- **13h:** início execução W1+W2
- **14h:** debug multi-agent (false negativo: presumi que não era suportado)
- **15h:** descoberta de `agents.list` é shape correto (Bernard me fez verificar nas docs — correto)
- **16h:** tuning loop: auth → contextWindow → timeout → proxy instrumentation
- **17h:** causa-raiz num_ctx=262144 identificada via proxy HTTP loopback
- **18h:** pausa — Bernard pediu consolidação antes de decidir próximo passo

Duração total: **~11h**. Trabalho entregue: ~80% da infra W1+W2, 0% de W3+W4. Tempo em debug: ~40% do total. Valor durável: muito (infra + descobertas sobre OpenClaw nunca documentadas no repo).

---

*Fim do status. Aguardando decisão do Bernard para retomar.*
