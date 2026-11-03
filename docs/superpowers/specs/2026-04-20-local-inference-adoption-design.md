# Local Inference Adoption — Design Spec

> **Status:** Draft (aguardando review do Bernard)
> **Data:** 2026-04-20
> **Autor:** Claude Code (sessão com Bernard)
> **Escopo:** OpenClaw (Company OS) — migração seletiva de inferência LLM para modelos locais em RTX 3060 12 GB, preservando gpt-5.4 como primário para Vox premium.
> **Relação com bevox-knowledge:** esta spec pode ser promovida para `bevox-knowledge/35_specs/` após aprovação e virar ADR em `bevox-knowledge/30_adr/ADR-XXX-local-inference-adoption.md`.

---

## 1. Contexto e motivação

### 1.1 Dados de consumo (últimos 12 dias, 2026-04-08 → 2026-04-20)

Medido via `cost/usage-tracking.db` e agregação das sessões em `agents/main/sessions/*.jsonl`:

- **Total:** 26.1M tokens · **$47.82** · ~$4/dia médio · projeção linear **~$120/mês**
- **99.6%** em `openai-codex/gpt-5.4` (primary). 0.4% em fallback deepseek-v3.2 (configurado hoje).
- **89% concentrado em 1 sessão:** `bdd60e4e...` = `agent:main:telegram:direct:7593...` — é o Vox rodando em DM Telegram + todos os crons firing nessa mesma sessionKey.

### 1.2 Breakdown dos crons (subset de Vox)

| Cron | Runs/12d | In/run | Out/run | Total/12d | Perfil |
|---|---:|---:|---:|---:|---|
| `healthcheck:operational-check` (4h) | 55 | ~44k | ~290 | 2.44M | 99% input, quase sempre `NO_REPLY` |
| `memory:daily-consolidation` (20h) | 9 | ~52k | ~1.3k | 468k | Síntese sobre memory/ |
| `watchdog:cron-health` (8h) | 8 | ~31k | ~360 | 251k | Check rápido |
| `review:weekly-system-health` (dom 18h) | 2 | ~49k | ~410 | 99k | Revisão semanal |
| **Total crons** | 74 | | | **3.26M** (~12%) | |

**Assinatura comum:** contexto enorme, output minúsculo — tarefas de triagem/síntese que não precisam de raciocínio de fronteira.

### 1.3 Hardware disponível (instalado em 2026-04-20)

- NVIDIA GeForce RTX 3060 12 GB VRAM (CUDA 12.4, compute 8.6, driver 550.163.01)
- CPU i5-10600K 6c/12t, 32 GB RAM, 185 GB livre em `/`
- Ollama 0.21.0 com `qwen2.5-coder:14b` e `qwen2.5-coder:7b` já puxados (smoke test: 65 tok/s em 7B, 33 tok/s em 14B, modelo inteiro na GPU)

### 1.4 Por que agora

1. **Privacidade:** `memory:daily-consolidation` hoje envia toda sua memória operacional (people.md, decisions.md, sessions) para OpenAI a cada 20h. Local elimina vazamento sem perda funcional.
2. **Economia:** ~$15–60/mês dependendo de escopo. Pagável pela simples realocação do hardware que já existe.
3. **Resiliência:** 3º braço independente de internet. Quando OpenAI + OpenRouter caem (já aconteceu: 2026-04-19 rate limit 50h), crons continuam.
4. **Stack técnica validada:** driver, CUDA, Ollama, plugin `ollama` do OpenClaw (já loaded stock) — zero bloqueios.

---

## 2. Objetivos e não-objetivos

### Objetivos
- **O1.** Rotear crons batch para modelo local quando qualidade for suficiente.
- **O2.** Eliminar vazamento de `memory/*` para providers externos (privacy gate absoluto).
- **O3.** Introduzir camada de triagem por turno humano no Telegram, reservando gpt-5.4 para quando for genuinamente necessário.
- **O4.** Manter Vox premium (gpt-5.4) intacto para reasoning de fronteira, tool-heavy, conversa complexa.
- **O5.** Toda mudança reversível em ≤60s por componente; emergência total em ≤10s.

### Não-objetivos
- **N1.** Embeddings / RAG / busca semântica em memory (avaliado em spec futura).
- **N2.** Substituir qwen2.5-coder quando houver demanda coder específica.
- **N3.** Benchmark formal (lm-eval, MT-Bench) — usamos observação + spot-check.
- **N4.** Multi-agente concorrente (hoje só `main`).
- **N5.** Migração do workflow Claude Code (fora de escopo; Claude Code é ambiente de coding, OpenClaw é Company OS).

---

## 3. Arquitetura

### 3.1 Visão topológica

```
PROVIDERS (ordem de preferência por camada)
┌────────────────────────────────────────────────────────────┐
│  Cloud premium:   openai-codex/gpt-5.4                     │
│  Cloud fallback:  openrouter/deepseek/deepseek-v3.2        │
│                   openrouter/qwen/qwen3.6-plus             │
│  Local (NOVO):    ollama/qwen3:14b                         │
│                   ollama/qwen3:4b                          │
│                   ollama/deepseek-r1:14b (opcional)        │
│                   ollama/qwen2.5-coder:14b (já instalado)  │
└────────────────────────────────────────────────────────────┘

FLUXO HUMANO (Telegram DM)
  msg → sessionKey main:telegram:direct:7593...
      → TRIAGE AGENT (qwen3:4b local) — NOVO
      → classifica {route: local|premium, confidence, reason}
      ↓                              ↓
    local                         premium
      ↓                              ↓
    Vox-local (qwen3:14b)         Vox (gpt-5.4)
    [fallback: gpt-5.4]           [fallback: openrouter chain]

FLUXO CRON (batch, sem humano)
  Cron fires → payload.model EXPLÍCITO (não herda do Vox)
            → local primary → local fallback → cloud fallback
            → log usage + decisão em model-routing.jsonl
```

### 3.2 Componentes novos

| Componente | Tipo | Onde vive | Função |
|---|---|---|---|
| **Ollama provider** | config | `openclaw.json` → `plugins.entries.ollama.enabled=true`, models entries | Expõe modelos Ollama ao runtime |
| **Triage agent** | agent (L1) | `bevox-knowledge/20_architecture/agents/triage-agent.md` + `registry.yml` | Router de turno humano |
| **Vox-local variant** | agent config | `openclaw.json` → agente `vox-local` ou rota condicional no Vox | Variante do Vox usando qwen3:14b |
| **Per-cron model override** | config | `cron/jobs.json` (cada job com `payload.model` próprio) | Cada cron aponta modelo-alvo explícito |
| **Circuit breaker** | runtime | Hook/plugin no OpenClaw runtime **OU** state local em `logs/circuit-breaker.json` | 3 erros consecutivos num primary → força fallback por 1h |
| **Model routing audit** | log | `logs/model-routing.jsonl` (append-only) | Cada decisão de routing + fallback |
| **`/escalate` command** | Telegram command | skill em `~/.openclaw/skills/escalate` | Força próximo turn humano para premium (bypass triage) |

### 3.3 Componentes existentes tocados

| Componente | Mudança |
|---|---|
| `bevox-knowledge/20_architecture/agents/registry.yml` | Novos agentes `triage-agent` e `vox-local` (se usar agente separado); atualização de fallbacks se necessário |
| `bevox-knowledge/20_architecture/agents/{triage-agent,vox-local}.md` | Páginas novas derivadas (via render ou manual) |
| `bevox-knowledge/30_adr/ADR-XXX-local-inference-adoption.md` | ADR nova: política "quando usar local, quando não, privacy gates" |
| `~/.openclaw/openclaw.json` | `plugins.entries.ollama.enabled=true`; nova entrada em `agents.defaults.models`; rotas de roteamento no canal telegram |
| `~/.openclaw/cron/jobs.json` | Cada job ganha `payload.model` + `payload.fallbacks` explícitos; `timeoutSeconds` escalonado |
| `~/.openclaw/workspace/memory/pending.md` | Remover items resolvidos, registrar follow-ups |

---

## 4. Mapa de modelos por tarefa

### 4.1 Modelos a manter/adicionar

| Modelo | Tamanho | Papel | Status |
|---|---:|---|---|
| `qwen2.5-coder:14b` | 9.0 GB | Código | ✅ já instalado |
| `qwen2.5-coder:7b` | 4.7 GB | Código leve | ✅ já instalado |
| `qwen3:14b` | ~9 GB | **Generalista forte**; Vox-local, memory, review | ➕ W1 |
| `qwen3:4b` | ~2.5 GB | **Triage rápido**; healthcheck, watchdog, router | ➕ W1 |
| `deepseek-r1:14b` | ~9 GB | Reasoning batch (opcional) | ➕ W1 se couber tempo |

**Total disco:** ~34 GB (dos 185 GB livres). **VRAM simultânea:** 1 modelo por vez via `OLLAMA_MAX_LOADED_MODELS=1`; keep-alive `15m` para evitar reload em horários agrupados de cron.

### 4.2 Decisão por consumidor

| Consumidor | Primary | Fallback 1 | Fallback 2 | Privacy gate |
|---|---|---|---|---|
| **Vox premium** (humano complexo) | `openai-codex/gpt-5.4` | `openrouter/deepseek-v3.2` | `openrouter/qwen3.6-plus` | — |
| **Vox-local** (humano trivial) | `ollama/qwen3:14b` | `openai-codex/gpt-5.4` | `openrouter/deepseek-v3.2` | — |
| **triage-agent** (router) | `ollama/qwen3:4b` | `ollama/qwen3:14b` | `openai-codex/gpt-5.4` | — |
| **healthcheck** | `ollama/qwen3:4b` | `ollama/qwen3:14b` | `openai-codex/gpt-5.4` | — |
| **watchdog** | `ollama/qwen3:4b` | `ollama/qwen3:14b` | `openai-codex/gpt-5.4` | — |
| **memory:daily-consolidation** | `ollama/qwen3:14b` | `openai-codex/gpt-5.4` | — | **SIM — sem OpenRouter** |
| **review:weekly-system-health** | `ollama/qwen3:14b` | `ollama/deepseek-r1:14b` | `openai-codex/gpt-5.4` | — |

### 4.3 Regras transversais

1. **Privacy gate absoluto (`memory:daily-consolidation`):** se todos os fallbacks locais falharem E o fallback for openrouter, o cron **falha explicitamente** com alerta em vez de vazar memory. Cai para `openai-codex` só porque você já tem conta lá e decidiu aceitar esse custo de privacidade; openrouter fica fora dessa cadeia.
2. **Circuit breaker por (consumidor, primary):** 3 erros consecutivos → força fallback por 60min, retry automático depois.
3. **Timeout escalonado por modelo:**
   - qwen3:4b batch: 60s
   - qwen3:14b batch: 180s
   - gpt-5.4 batch: 120s (atual)
4. **`OLLAMA_KEEP_ALIVE=15m`** via env na systemd unit.
5. **`OLLAMA_MAX_LOADED_MODELS=1`** explícito — evita OOM de VRAM.

---

## 5. Rollout em 4 ondas

### W1 — Infraestrutura local (30 min)
- Puxar modelos: `qwen3:14b`, `qwen3:4b`, `deepseek-r1:14b` (opcional)
- Habilitar plugin `ollama` em `openclaw.json`:
  - `plugins.entries.ollama.enabled=true`
  - Adicionar models em `agents.defaults.models`: `ollama/qwen3:14b`, `ollama/qwen3:4b`
- Configurar systemd override com `OLLAMA_KEEP_ALIVE=15m` e `OLLAMA_MAX_LOADED_MODELS=1`
- Smoke test: `openclaw capability infer --model ollama/qwen3:14b --prompt "ping"` → retorna "pong" equivalente
- **Gate:** todos os modelos respondem OK

### W2 — Crons batch (1h)
Migrar em ordem de risco crescente:
1. `watchdog:cron-health` (menor volume, menor risco)
2. `healthcheck:operational-check` (maior volume, mesmo perfil)
3. `memory:daily-consolidation` (privacy-critical; ativar gate)
4. `review:weekly-system-health` (roda só domingo; baixa urgência)

Para cada: edit `cron/jobs.json` via `openclaw cron edit <id>` aplicando primary/fallbacks/timeout novos. Backup antes.

- **Gate:** cada cron executado manualmente 1x (`openclaw cron run <id>`) com sucesso local
- **Observação:** 48h de monitoramento antes de avançar para W3

### W3 — Observabilidade (1h)
- Circuit breaker implementado (hook OpenClaw ou wrapper)
- Log `logs/model-routing.jsonl` com shape `{ts, consumer, primary_tried, fallback_used, reason, usage}`
- Integração com `watchdog:cron-health` para alertar "3 erros consecutivos em local"
- Dashboard leve (opcional, MVP = `jq` one-liner no log)

- **Gate:** circuit breaker testado via indisponibilidade forçada (ex: parar Ollama daemon → verificar fallback)

### W4 — Triage + Vox-local (2–3h)
- Criar agente `triage-agent` em `bevox-knowledge/20_architecture/agents/`
  - Shape: L1, primary `ollama/qwen3:4b`, prompt system para devolver JSON `{route, confidence, reason}`
- Criar `vox-local` (variant do Vox com primary qwen3:14b)
- Rota condicional no canal Telegram:
  - msg → triage → switch on route
- Implementar comando `/escalate` (skill `~/.openclaw/skills/escalate`) que:
  - Seta flag na sessionKey para "próximo turn = premium"
  - Triage lê a flag e força route=premium
- Comparação paralela opcional: primeiros 20 turns rodam em ambos (local + premium) para comparar outputs (log only, respondem com premium para não quebrar UX)

- **Gate:** 1 semana rodando com `/escalate` disponível; se taxa de escalate > 30%, triage está ruim e precisa retune

### Entre ondas
- Cada onda = 1 draft branch em `bevox-knowledge` (`draft/local-inference-w1`, ..., `-w4`)
- Branch mergeada para `main` só após gate passar
- `pending.md` atualizado ao fim de cada onda

---

## 6. Riscos e mitigações

| # | Risco | Prob | Impact | Mitigação |
|---|---|---|---|---|
| R1 | qwen3:14b degrada `memory:daily-consolidation` | Média | Alto | Rodar em paralelo 3 dias (dual output: local + cloud). Só promove quando qualidade OK via spot-check manual. |
| R2 | qwen3:4b classifica errado triage → Vox-local quando merecia premium | Média | Médio | `/escalate`; log completo; threshold baixo → default premium; retune via prompt engineering |
| R3 | Ollama daemon crash (OOM, panic) | Baixa | Baixo | systemd `Restart=always`; fallback cloud imediato via circuit breaker |
| R4 | GPU OOM ao tentar carregar 2 modelos | Baixa | Baixo | `OLLAMA_MAX_LOADED_MODELS=1` explícito |
| R5 | Contexto estoura `num_ctx` do modelo local (32k default) | Média (memory-consolidation) | Médio | `num_ctx=65536` via Modelfile custom; truncar priorizando recência se ainda não couber |
| R6 | Divergência silenciosa: local responde sintaticamente OK mas semanticamente errado | Média | Alto | Log `model-routing.jsonl` + spot-check semanal por 2 semanas; comparação paralela em W4 primeiros dias |
| R7 | Config errada em `openclaw.json` quebra fluxo atual | Baixa | Alto | Backup por onda; draft branch; apt-like rollback por componente |
| R8 | Privacy gate de memory falha silenciosamente (cai pra openrouter sem aviso) | Baixa | **Crítico** | Teste explícito em W2: simular falha do local → confirmar que cron aborta em vez de cair para openrouter |

---

## 7. Rollback

### Por onda
- **W1:** `openclaw plugins disable ollama` + `ollama rm qwen3:14b qwen3:4b deepseek-r1:14b`. Estado pré-migração.
- **W2:** `openclaw cron edit <id> --model openai-codex/gpt-5.4` por job. ~30s por cron.
- **W3:** remover hooks do routing log + reverter watchdog. Sem impacto funcional.
- **W4:** deletar `triage-agent` + `vox-local` + remover routing rules no `openclaw.json`. Telegram volta direto ao Vox cloud.

### Emergência total
```bash
cp ~/.openclaw/openclaw.json.bak.pre-local-inference ~/.openclaw/openclaw.json
cp ~/.openclaw/cron/jobs.json.bak.pre-local-inference ~/.openclaw/cron/jobs.json
sudo systemctl restart ollama  # opcional, so para deixar limpo
```
Estado pré-W1 em <10 segundos.

---

## 8. Métricas e observabilidade

### 8.1 Métricas coletadas

| Métrica | Fonte | Frequência | Uso |
|---|---|---|---|
| Tokens por consumidor × model | `usage-tracking.db` (já existe) | A cada chamada | Validar economia |
| Decisões de routing | `logs/model-routing.jsonl` (novo) | A cada chamada | Auditoria + debug |
| Erros por primary | Circuit breaker state | Contínuo | Disparar fallback/alert |
| Latency por modelo | Log Ollama + `total_duration` | A cada chamada | Validar timeouts |
| Taxa de `/escalate` | Comando no Telegram | Contínuo | Retune triage |

### 8.2 Spot-check semanal (2 primeiras semanas)
- 5 samples aleatórios de `memory:daily-consolidation`: manual review da qualidade
- 5 samples aleatórios de triage decisions (W4+): conferir se classificação faz sentido

### 8.3 Economia projetada (a validar)

| Cenário (volume atual) | Tokens migrados | Economia/mês |
|---|---|---|
| **Só W2** (crons) | ~3.26M/12d = ~8M/mês | **~$15–20/mês** |
| **W2 + W4** (crons + triage human) | ~20M/mês (estimativa) | **~$40–60/mês** |

Números finais saem da comparação pré/pós-migração na `usage-tracking.db`.

---

## 9. Scope-out (reiterado)

- Embeddings / RAG sobre memory (spec futura)
- Qwen2.5-coder workflow (sem demanda atual)
- Benchmark formal
- Multi-agente concorrente
- Web UI / Mission Control para configurar roteamento
- Substituir Claude Code (fora de escopo; CLAUDE.md §1)

---

## 10. Dependências externas

- Ollama 0.21.0 (instalado 2026-04-20)
- Plugin `ollama` do OpenClaw 2026.4.8 (stock, já loaded)
- NVIDIA driver 550.163.01 + CUDA 12.4 (instalado 2026-04-20)
- `OPENROUTER_API_KEY` válida (hoje em `~/.openclaw/.env`)
- OAuth `openai-codex:you@example.com` válido (hoje ativo, rate limit até ~22/04)

---

## 11. Aceitação (done criteria)

- [ ] W1: todos os modelos puxados e respondendo a `capability infer`
- [ ] W2: 4 crons migrados, cada um com 1 execução manual OK + 48h sem regressão
- [ ] W2.gate: privacy gate testado explicitamente em `memory:daily-consolidation`
- [ ] W3: circuit breaker testado (derrubar Ollama → verificar fallback + log)
- [ ] W4: triage rodando por 1 semana; `/escalate` funcionando; taxa escalate ≤ 30%
- [ ] `bevox-knowledge/30_adr/ADR-XXX-local-inference-adoption.md` mergeada para `main`
- [ ] `usage-tracking.db` mostra queda mensurável de tokens gpt-5.4 (meta ≥ 30% do volume cron)
- [ ] `pending.md` atualizado após cada onda

---

## 12. Referências

- `~/.openclaw/cost/usage-tracking.db` — dados de consumo (origem da análise de §1)
- `~/.openclaw/cron/jobs.json` — crons alvos (healthcheck, watchdog, memory, review)
- `~/.openclaw/openclaw.json` — config runtime (fallbacks atuais, providers)
- `bevox-knowledge/20_architecture/agents/registry.yml` — SoT canônica dos agentes
- `bevox-knowledge/20_architecture/agents/vox.md` — agente principal hoje impactado
- `bevox-knowledge/30_adr/ADR-001-boundary.md` — boundary OpenClaw vs Produto
- `bevox-knowledge/30_adr/ADR-005-source-of-truth.md` — SoT em bevox-knowledge
- `bevox-knowledge/30_adr/ADR-006-autonomy-permissions-approval.md` — política de autonomia/approval
- Commit `f0daaa7` em `draft/fallback-hardening-2026-04-20` — fix dos fallbacks stealth que motivou este trabalho

---

## 13. Perguntas abertas (a fechar antes de implementação)

1. **Implementação do circuit breaker:** o runtime OpenClaw já tem hook nativo para isso, ou precisamos de um wrapper/plugin próprio? (Resposta define complexidade de W3.)
2. **Triage em W4:** agente separado (`triage-agent`) ou routing rule no próprio canal Telegram sem agente intermediário? (Arquitetura mais simples vs granularidade de controle.)
3. **Modelfile custom para qwen3:14b em `memory:daily-consolidation`:** precisa `num_ctx=65536` ou o default 32k é suficiente? (Depende do tamanho real do memory/ no dia da consolidação.)
4. **Promoção desta spec para canônica:** após aprovação, mover para `bevox-knowledge/35_specs/` e abrir ADR correspondente, ou manter em `docs/superpowers/specs/` como documento de trabalho do OpenClaw?

---

*Fim da spec.*
