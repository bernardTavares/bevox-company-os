# Local Inference Adoption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrar cron batch workloads e triagem de turno humano do OpenClaw para inferência local em Ollama (qwen3:14b, qwen3:4b), preservando gpt-5.4 como primário para Vox premium. Eliminar vazamento de `memory/*` para providers externos via privacy gate absoluto em `memory:daily-consolidation`.

**Architecture:** 4 ondas (W1 infra → W2 crons → W3 observabilidade → W4 triage+vox-local). Cada cron vira agente dedicado no `bevox-knowledge/registry.yml` com primary/fallback próprios (OpenClaw não suporta per-cron model override nativo). Circuit breaker em W3 é **detect-and-alert** (auto-swap fica como W3.5 futuro, requer plugin).

**Tech Stack:** Ollama 0.21.0 (instalado), OpenClaw 2026.4.8, plugin `ollama` stock, Debian 13 trixie, NVIDIA 550.163.01 + CUDA 12.4, RTX 3060 12 GB, systemd, bash, Python 3.13, SQLite (`usage-tracking.db`), JSONL (cron runs, routing audit), git (apenas em `bevox-knowledge`).

**Spec de origem:** `~/.openclaw/docs/superpowers/specs/2026-04-20-local-inference-adoption-design.md`

**Desvios documentados da spec:**
- **Per-cron agents** (em vez de per-cron model override): OpenClaw não expõe `payload.model` hoje; caminho canônico é criar agentes dedicados. Adiciona 4 agentes no registry além dos 2 previstos (triage + vox-local).
- **Circuit breaker MVP = detect-and-alert**: sem hook runtime, auto-swap é hack. Bernard recebe alerta no Telegram quando 3 falhas consecutivas detectadas; swap manual via `openclaw cron edit` ou via próximo sprint W3.5 quando plugin custom estiver pronto.

---

## Preflight — Setup (15 min)

### Task 0: Backup de arquivos críticos

**Files:**
- Create: `~/.openclaw/openclaw.json.bak.pre-local-inference`
- Create: `~/.openclaw/cron/jobs.json.bak.pre-local-inference`

- [ ] **Step 1: Backup `openclaw.json`**

```bash
cp ~/.openclaw/openclaw.json ~/.openclaw/openclaw.json.bak.pre-local-inference
ls -la ~/.openclaw/openclaw.json.bak.pre-local-inference
```
Expected: arquivo existe com mesmo tamanho que original.

- [ ] **Step 2: Backup `cron/jobs.json`**

```bash
cp ~/.openclaw/cron/jobs.json ~/.openclaw/cron/jobs.json.bak.pre-local-inference
ls -la ~/.openclaw/cron/jobs.json.bak.pre-local-inference
```
Expected: arquivo existe, mesmo tamanho.

- [ ] **Step 3: Verificar integridade JSON dos backups**

```bash
python3 -c "import json; json.load(open('~/.openclaw/openclaw.json.bak.pre-local-inference')); json.load(open('~/.openclaw/cron/jobs.json.bak.pre-local-inference')); print('backups válidos')"
```
Expected: `backups válidos`

### Task 1: Criar branch draft em bevox-knowledge

**Files:**
- Branch: `bevox-knowledge@draft/local-inference-adoption-2026-04-20`

- [ ] **Step 1: Verificar estado atual**

```bash
cd ~/bevox-knowledge && git status --short && git branch --show-current
```
Expected: branch atual mostrada (pode estar em `draft/fallback-hardening-2026-04-20` do trabalho anterior); uncommitted changes são pre-existing do Bernard (não tocar).

- [ ] **Step 2: Voltar para main antes de criar branch nova**

```bash
cd ~/bevox-knowledge && git checkout main
```
Expected: Switched to branch 'main'. Se rejeitar por uncommitted changes, investigar ANTES de prosseguir; as mudanças READMEs podem ser trabalho em andamento do Bernard.

- [ ] **Step 3: Criar branch draft**

```bash
cd ~/bevox-knowledge && git checkout -b draft/local-inference-adoption-2026-04-20
```
Expected: `Switched to a new branch 'draft/local-inference-adoption-2026-04-20'`

---

## W1 — Infraestrutura Local (30 min)

### Task 2: Pull `qwen3:14b`

**Files:**
- Create: `~/.ollama/models/...` (gerenciado pelo Ollama)

- [ ] **Step 1: Confirmar estado pré**

```bash
ollama list | grep -E "qwen3:14b" || echo "qwen3:14b ausente, ok para pull"
```
Expected: `qwen3:14b ausente, ok para pull`

- [ ] **Step 2: Pull em foreground (~9 GB, 3-15min)**

```bash
ollama pull qwen3:14b
```
Expected: progresso de download, ao fim `success`.

- [ ] **Step 3: Confirmar instalação**

```bash
ollama list | grep -E "^qwen3:14b"
```
Expected: linha com `qwen3:14b` e tamanho ~9 GB.

### Task 3: Pull `qwen3:4b`

**Files:**
- Create: `~/.ollama/models/...`

- [ ] **Step 1: Pull (~2.5 GB, 1-3min)**

```bash
ollama pull qwen3:4b
```
Expected: progresso, `success`.

- [ ] **Step 2: Confirmar**

```bash
ollama list | grep -E "^qwen3:4b"
```
Expected: linha com `qwen3:4b`.

### Task 4: Pull `deepseek-r1:14b` (opcional fallback reasoning)

**Files:**
- Create: `~/.ollama/models/...`

- [ ] **Step 1: Pull (~9 GB, 3-15min)**

```bash
ollama pull deepseek-r1:14b
```
Expected: `success`.

- [ ] **Step 2: Confirmar**

```bash
ollama list | grep -E "^deepseek-r1:14b"
```
Expected: linha presente.

- [ ] **Step 3: Skip se banda/tempo limitado**

Se o download falhar ou quiser pular, remover `deepseek-r1:14b` do fallback de `review:weekly-system-health` (Task 15) e prosseguir com qwen3:14b como único.

### Task 5: Systemd override para Ollama

**Files:**
- Create: `/etc/systemd/system/ollama.service.d/override.conf`

- [ ] **Step 1: Verificar estado atual**

```bash
sudo systemctl show ollama -p Environment
```
Expected: sem `OLLAMA_KEEP_ALIVE` ou `OLLAMA_MAX_LOADED_MODELS` configurados (ou defaults).

- [ ] **Step 2: Criar override dir**

```bash
sudo mkdir -p /etc/systemd/system/ollama.service.d
```

- [ ] **Step 3: Escrever override**

```bash
sudo tee /etc/systemd/system/ollama.service.d/override.conf > /dev/null <<'EOF'
[Service]
Environment="OLLAMA_KEEP_ALIVE=15m"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
EOF
```

- [ ] **Step 4: Daemon-reload + restart**

```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama
sleep 3
systemctl is-active ollama
```
Expected: `active`.

- [ ] **Step 5: Verificar env aplicado**

```bash
sudo journalctl -u ollama --since "30 seconds ago" --no-pager | grep -iE "keep_alive|max_loaded" | head
```
Expected: saída mostra `OLLAMA_KEEP_ALIVE:15m0s` e `OLLAMA_MAX_LOADED_MODELS:1` no server config.

### Task 6: Habilitar plugin `ollama` e adicionar models em `openclaw.json`

**Files:**
- Modify: `~/.openclaw/openclaw.json`

- [ ] **Step 1: Verificar estado atual do plugin**

```bash
openclaw config get plugins.entries.ollama 2>&1 | head
```
Expected: provavelmente vazio ou não presente (plugin é `loaded` mas não configurado como `enabled`).

- [ ] **Step 2: Editar `openclaw.json` — adicionar ollama em plugins**

Ler `openclaw.json` e aplicar mudança JSON: adicionar `"ollama"` em `plugins.allow`, adicionar `"ollama": {"enabled": true}` em `plugins.entries`, adicionar os 5 modelos em `agents.defaults.models`.

Estado esperado da seção `plugins.allow`:
```json
"allow": [
  "knowledge-sync-commands",
  "openai",
  "openrouter",
  "qwen",
  "deepseek",
  "google",
  "arcee",
  "ollama"
]
```

Estado esperado da seção `plugins.entries` (adicionar):
```json
"ollama": { "enabled": true }
```

Estado esperado da seção `agents.defaults.models` (adicionar aos existentes):
```json
"ollama/qwen3:14b": {},
"ollama/qwen3:4b": {},
"ollama/qwen2.5-coder:14b": {},
"ollama/qwen2.5-coder:7b": {},
"ollama/deepseek-r1:14b": {}
```

- [ ] **Step 3: Validar JSON**

```bash
python3 -c "import json; d=json.load(open('~/.openclaw/openclaw.json')); print('plugins.allow ollama in?', 'ollama' in d['plugins']['allow']); print('plugins.entries.ollama enabled?', d['plugins']['entries'].get('ollama',{}).get('enabled')); print('models count:', len(d['agents']['defaults']['models']))"
```
Expected:
```
plugins.allow ollama in? True
plugins.entries.ollama enabled? True
models count: 10  (5 originais já limpos + 5 ollama)
```

- [ ] **Step 4: Verificar plugin carregou**

```bash
openclaw plugins list 2>&1 | grep -i ollama
```
Expected: linha mostrando `ollama` com status `loaded` e algum indicador de `enabled`.

### Task 7: Smoke test de inferência via OpenClaw

**Files:** N/A (runtime test)

- [ ] **Step 1: Test direto via Ollama API**

```bash
curl -s http://127.0.0.1:11434/api/generate -d '{"model":"qwen3:14b","prompt":"Em uma palavra em portugues: ok?","stream":false,"options":{"num_predict":10}}' | python3 -c "import json,sys; d=json.load(sys.stdin); print('resp:', d.get('response','').strip()[:60])"
```
Expected: resposta curta em português contendo algo próximo de "OK", "Sim" ou similar.

- [ ] **Step 2: Test via OpenClaw `capability infer`**

```bash
openclaw capability infer --model ollama/qwen3:4b --prompt "responda em uma palavra: ping" 2>&1 | tail -10
```
Expected: saída contendo uma resposta (ex: "pong" ou similar). Se falhar com "unknown model" ou "provider not found", significa que plugin não está roteando os slugs `ollama/...` → debug:
```bash
openclaw plugins list 2>&1 | grep ollama
openclaw config get plugins.entries.ollama
```

- [ ] **Step 3: Registrar timing**

```bash
time openclaw capability infer --model ollama/qwen3:14b --prompt "diga OK" 2>&1 | tail -5
```
Expected: `real ~3-10s` (primeiro request pode ser mais longo por model load).

### Task 8: Gate W1 — checkpoint humano

- [ ] **Step 1: Bernard confirma que W1 está OK**

Pergunta a Bernard antes de seguir para W2: "W1 concluída — plugin habilitado, 3 modelos locais respondendo via OpenClaw capability. Posso avançar para W2 (migração dos 4 crons)?"

Expected: Bernard responde "sim". Se não, investigar o que está pendente.

---

## W2 — Migração de Crons Batch (1h)

### Task 9: Discovery — confirmar que per-cron agent é o caminho

**Files:** N/A (research)

- [ ] **Step 1: Confirmar que `payload.model` não é respeitado pelo runtime**

```bash
# Inspecionar todos os campos aceitos no payload atual
python3 -c "import json; d=json.load(open('~/.openclaw/cron/jobs.json')); [print(j['name'], '→ payload keys:', list(j['payload'].keys())) for j in d['jobs']]"
```
Expected: apenas `kind`, `message`, `timeoutSeconds`, `lightContext`. Nenhum `model` presente.

- [ ] **Step 2: Tentar adicionar `model` via edit manual em 1 cron para teste**

```bash
# Editar temporariamente
python3 <<'PY'
import json, pathlib
p = pathlib.Path('~/.openclaw/cron/jobs.json')
d = json.loads(p.read_text())
for j in d['jobs']:
    if j['name'] == 'watchdog:cron-health':
        j['payload']['model'] = 'ollama/qwen3:4b'  # test
        break
p.write_text(json.dumps(d, indent=2))
PY

openclaw cron run b2f711f3-1173-44dc-be90-eaac9268cb4e 2>&1 | tail -5
sleep 30
# Ver qual modelo foi realmente usado
sudo journalctl -u openclaw* --since "1 minute ago" --no-pager 2>/dev/null | grep -iE "model|provider" | tail -10
# Alternativa: inspecionar cron runs
tail -1 ~/.openclaw/cron/runs/b2f711f3-1173-44dc-be90-eaac9268cb4e.jsonl | python3 -m json.tool | grep model
```
Expected: campo `model` no run log mostra `gpt-5.4` (ignorando `payload.model`), confirmando que `payload.model` não é honrado.

- [ ] **Step 3: Reverter o test e confirmar Path A**

```bash
cp ~/.openclaw/cron/jobs.json.bak.pre-local-inference ~/.openclaw/cron/jobs.json
python3 -c "import json; d=json.load(open('~/.openclaw/cron/jobs.json')); [print(j['name'], 'payload:', j['payload']) for j in d['jobs'] if j['name']=='watchdog:cron-health']"
```
Expected: payload sem `model` — volta ao estado original.

- [ ] **Step 4: Se `payload.model` FOI respeitado (cenário alternativo)**

Se Step 2 mostrou o modelo sendo trocado: skip todas as tasks de criação de agente (tasks 11-14). Em vez disso, adicionar tasks de edit do `payload.model` + `payload.fallbacks` em cada cron. Atualizar plano.

- [ ] **Step 5: Path confirmado — seguir com per-cron agents**

Se Step 2 confirmou comportamento esperado (Path A): avançar para Task 10.

### Task 10: Criar Modelfile custom `qwen3:14b-64k` para contextos grandes

**Files:**
- Create: `~/.openclaw/modelfiles/qwen3-14b-64k.Modelfile`

- [ ] **Step 1: Criar diretório e Modelfile**

```bash
mkdir -p ~/.openclaw/modelfiles
cat > ~/.openclaw/modelfiles/qwen3-14b-64k.Modelfile <<'EOF'
FROM qwen3:14b
PARAMETER num_ctx 65536
EOF
```

- [ ] **Step 2: Criar model custom via Ollama**

```bash
ollama create qwen3:14b-64k -f ~/.openclaw/modelfiles/qwen3-14b-64k.Modelfile
ollama list | grep qwen3
```
Expected: nova linha `qwen3:14b-64k` presente.

- [ ] **Step 3: Test de contexto estendido**

```bash
# Teste rápido: prompt gigante deve funcionar sem truncar
python3 <<'PY'
import requests, json
prompt = "Conte até 10 e depois resuma este texto: " + ("abc " * 10000)  # ~30k tokens
r = requests.post("http://127.0.0.1:11434/api/generate",
                  json={"model":"qwen3:14b-64k","prompt":prompt,"stream":False,
                        "options":{"num_predict":30}})
d = r.json()
print("ctx used:", d.get("prompt_eval_count"), "response:", d.get("response","")[:100])
PY
```
Expected: prompt_eval_count > 10k (modelo aceitou o contexto grande sem error).

- [ ] **Step 4: Adicionar model em `openclaw.json`**

Adicionar `"ollama/qwen3:14b-64k": {}` em `agents.defaults.models`, validar JSON.

### Task 11: Criar agente `watchdog-agent` no bevox-knowledge

**Files:**
- Modify: `bevox-knowledge/20_architecture/agents/registry.yml`
- Create: `bevox-knowledge/20_architecture/agents/watchdog-agent.md`
- Modify: `bevox-knowledge/20_architecture/agents/registry.md` (regenerado)

- [ ] **Step 1: Adicionar entry em registry.yml (inserir alfabeticamente antes de `vox`)**

No arquivo `bevox-knowledge/20_architecture/agents/registry.yml`, inserir:

```yaml
  watchdog-agent:
    status: ativo
    level: L1
    owner: Bernard
    model:
      primary: ollama/qwen3:4b
      fallback: openai-codex/gpt-5.4
    since: 2026-04-20
    file: watchdog-agent.md
```

- [ ] **Step 2: Criar página do agente**

Arquivo: `bevox-knowledge/20_architecture/agents/watchdog-agent.md`:

```markdown
# watchdog-agent

## Identidade
- **Status:** <!-- DERIVED: registry.yml -> agents.watchdog-agent.status --> ativo
- **Level:** <!-- DERIVED: registry.yml -> agents.watchdog-agent.level --> L1
- **Owner:** <!-- DERIVED: registry.yml -> agents.watchdog-agent.owner --> Bernard
- **Modelo primário:** <!-- DERIVED: registry.yml -> agents.watchdog-agent.model.primary --> ollama/qwen3:4b
- **Modelo fallback:** <!-- DERIVED: registry.yml -> agents.watchdog-agent.model.fallback --> openai-codex/gpt-5.4
- **Ativo desde:** <!-- DERIVED: registry.yml -> agents.watchdog-agent.since --> 2026-04-20

## Responsabilidade
Monitorar saúde dos crons ativos. Detectar falhas repetidas, ausência de runs recentes anormais, circuit breaker trips. Alertar Bernard quando necessário; caso contrário silêncio.

## Entradas
- `~/.openclaw/cron/runs/*.jsonl` (últimos runs)
- `~/.openclaw/logs/model-routing.jsonl` (routing decisions — W3)
- `~/.openclaw/logs/circuit-breaker.json` (breaker state — W3)

## Saídas
- Mensagem Telegram para Bernard em caso de anomalia
- `NO_REPLY` em caso normal

## Modelo local
Usa `qwen3:4b` por ser tarefa simples (parse de JSON, threshold check, decisão sim/não sobre alertar). Raciocínio pesado não é necessário. Fallback para `gpt-5.4` se local indisponível.

## Referência cruzada
- Cron job: `b2f711f3-1173-44dc-be90-eaac9268cb4e` (watchdog:cron-health, 0 8 * * *)
```

- [ ] **Step 3: Regenerar `registry.md`**

```bash
cd ~/bevox-knowledge && ./20_architecture/agents/_tools/render-registry.py
git diff --stat 20_architecture/agents/registry.md
```
Expected: `registry.md` atualizado com nova linha de `watchdog-agent`.

- [ ] **Step 4: Verificar cobertura no registry.md**

```bash
grep -E "^\| watchdog-agent" ~/bevox-knowledge/20_architecture/agents/registry.md
```
Expected: linha presente com primary/fallback corretos.

### Task 12: Criar agente `healthcheck-agent`

**Files:**
- Modify: `bevox-knowledge/20_architecture/agents/registry.yml`
- Create: `bevox-knowledge/20_architecture/agents/healthcheck-agent.md`
- Modify: `bevox-knowledge/20_architecture/agents/registry.md` (regen)

- [ ] **Step 1: Adicionar entry em registry.yml**

```yaml
  healthcheck-agent:
    status: ativo
    level: L1
    owner: Bernard
    model:
      primary: ollama/qwen3:4b
      fallback: openai-codex/gpt-5.4
    since: 2026-04-20
    file: healthcheck-agent.md
```

- [ ] **Step 2: Criar página** (usar mesmo template da Task 11, ajustando nome e responsabilidade)

Arquivo: `bevox-knowledge/20_architecture/agents/healthcheck-agent.md`.
Responsabilidade: "Checagem operacional leve a cada 4h — agenda 24-48h, pendências abertas, follow-ups atrasados, saúde básica dos crons. `NO_REPLY` quando nada relevante; alerta curto e acionável quando há algo importante."
Referência cruzada: cron `900940c2-8350-456e-9d2e-e862267a1a21`.

- [ ] **Step 3: Regenerar `registry.md`**

```bash
cd ~/bevox-knowledge && ./20_architecture/agents/_tools/render-registry.py
grep -E "^\| healthcheck-agent" 20_architecture/agents/registry.md
```
Expected: linha presente.

### Task 13: Criar agente `memory-consolidation-agent`

**Files:**
- Modify: `bevox-knowledge/20_architecture/agents/registry.yml`
- Create: `bevox-knowledge/20_architecture/agents/memory-consolidation-agent.md`
- Modify: `bevox-knowledge/20_architecture/agents/registry.md` (regen)

- [ ] **Step 1: Adicionar entry em registry.yml**

**NOTE:** este agente tem privacy gate. Usa `qwen3:14b-64k` (custom com contexto 64k) como primary e `openai-codex/gpt-5.4` como único fallback. **NÃO** fallback para openrouter.

```yaml
  memory-consolidation-agent:
    status: ativo
    level: L1
    owner: Bernard
    model:
      primary: ollama/qwen3:14b-64k
      fallback: openai-codex/gpt-5.4
    since: 2026-04-20
    file: memory-consolidation-agent.md
    privacy_gate: true  # custom field: sinaliza que NÃO pode cair para openrouter
```

**Importante:** o campo `privacy_gate` é custom e pode não ser reconhecido pelo `render-registry.py`. Verificar no próximo step.

- [ ] **Step 2: Verificar que o render não quebra com campo extra**

```bash
cd ~/bevox-knowledge && ./20_architecture/agents/_tools/render-registry.py 2>&1 | tail -5
```
Expected: sucesso ou warning ignorável. Se falhar com "campo inválido", **remover** `privacy_gate` do YAML e documentar a restrição APENAS na página MD (Step 3). Privacy enforcement se dará via ausência de fallback para openrouter nas regras transversais.

- [ ] **Step 3: Criar página com seção de privacy gate explícita**

Arquivo: `bevox-knowledge/20_architecture/agents/memory-consolidation-agent.md`:

Incluir seção especial:
```markdown
## ⚠️ Privacy Gate

Este agente processa memory/* (dados pessoais, contatos, decisões, históricos). 
**REGRA INVIOLÁVEL:** se o primary local falhar e o fallback `openai-codex/gpt-5.4` também falhar, 
o cron **aborta com erro** em vez de cair para OpenRouter.

Motivação: memory/* **não pode sair para provider externo sem OAuth** (Anthropic/OpenAI 
aceitos via termos específicos; OpenRouter é roteador agregador de providers variados sem 
garantia equivalente).
```

Responsabilidade: "Consolidação diária da memória operacional — revisa sessions recentes, extrai decisões/lições/pendências, atualiza memory/context/* e memory/MEMORY.md."
Referência cruzada: cron `482e37d6-7a4d-467c-a99b-0e46b60dd3e6`.

### Task 14: Criar agente `weekly-review-agent`

**Files:**
- Modify: `bevox-knowledge/20_architecture/agents/registry.yml`
- Create: `bevox-knowledge/20_architecture/agents/weekly-review-agent.md`
- Modify: `bevox-knowledge/20_architecture/agents/registry.md` (regen)

- [ ] **Step 1: Adicionar entry em registry.yml**

Este agente pode usar `deepseek-r1:14b` como secondary local (reasoning) se Task 4 instalou. Se não, único local é qwen3:14b.

```yaml
  weekly-review-agent:
    status: ativo
    level: L1
    owner: Bernard
    model:
      primary: ollama/qwen3:14b
      fallback: ollama/deepseek-r1:14b  # ou openai-codex/gpt-5.4 se deepseek-r1 não instalado
    since: 2026-04-20
    file: weekly-review-agent.md
```

**Importante:** schema de `registry.yml` aceita só 1 fallback. Se quiser chain de 3 (qwen → deepseek-r1 → gpt-5.4), o 3º nível vira implícito — sistema default do OpenClaw usa `agents.defaults.model.fallbacks` como safety net adicional. Ou: omitir 2º local se quiser simplicidade.

- [ ] **Step 2: Criar página**

Arquivo: `bevox-knowledge/20_architecture/agents/weekly-review-agent.md`.
Responsabilidade: "Revisão sistêmica semanal (dom 18h) — examina últimas 7 dias de sessions, crons, decisions, gera resumo operacional + flags anomalias."
Referência cruzada: cron `68885b74-eedf-4baa-8e94-6284f317283b`.

- [ ] **Step 3: Regenerar registry.md**

```bash
cd ~/bevox-knowledge && ./20_architecture/agents/_tools/render-registry.py
grep -E "^\| (watchdog|healthcheck|memory-consolidation|weekly-review)-agent" 20_architecture/agents/registry.md
```
Expected: 4 linhas, uma para cada agente novo.

### Task 15: Declarar agentes novos em `~/.openclaw/openclaw.json`

**Files:**
- Modify: `~/.openclaw/openclaw.json`

- [ ] **Step 1: Verificar que existe seção `agents` para declarar múltiplos**

```bash
python3 -c "import json; d=json.load(open('~/.openclaw/openclaw.json')); print(json.dumps(d.get('agents',{}), indent=2)[:500])"
```
Expected: seção atual tem `defaults` — preciso adicionar `entries` com cada agente novo, OU confirmar como OpenClaw espera a declaração per-agent via `agents.entries.<name>.model`.

- [ ] **Step 2: Teste via `openclaw agents`**

```bash
openclaw agents 2>&1 | tail -30
openclaw config get agents 2>&1 | head -30
```
Expected: identificar campos aceitos. Se OpenClaw só aceita 1 agente default + `entries`, adicionar entries.

- [ ] **Step 3: Propor shape de config**

Adicionar em `openclaw.json` seção:

```json
"agents": {
  "defaults": { ...existente... },
  "entries": {
    "watchdog-agent": {
      "model": {
        "primary": "ollama/qwen3:4b",
        "fallbacks": ["openai-codex/gpt-5.4"]
      }
    },
    "healthcheck-agent": {
      "model": {
        "primary": "ollama/qwen3:4b",
        "fallbacks": ["openai-codex/gpt-5.4"]
      }
    },
    "memory-consolidation-agent": {
      "model": {
        "primary": "ollama/qwen3:14b-64k",
        "fallbacks": ["openai-codex/gpt-5.4"]
      },
      "privacy_gate": true
    },
    "weekly-review-agent": {
      "model": {
        "primary": "ollama/qwen3:14b",
        "fallbacks": ["ollama/deepseek-r1:14b", "openai-codex/gpt-5.4"]
      }
    }
  }
}
```

**Se OpenClaw não suportar `agents.entries`:** criar via `openclaw agents create <name>` se existir, ou documentar limitação e colocar config por cron no `cron/jobs.json` na próxima task (task 17) via workaround.

- [ ] **Step 4: Validar JSON e testar listagem**

```bash
python3 -c "import json; d=json.load(open('~/.openclaw/openclaw.json')); print('agents.entries keys:', list(d.get('agents',{}).get('entries',{}).keys()))"
openclaw agents 2>&1 | tail -15
```
Expected: 4 agentes novos listados se OpenClaw suporta; senão, revisar Step 3.

### Task 16: Apontar cada cron para seu agente

**Files:**
- Modify: `~/.openclaw/cron/jobs.json`

- [ ] **Step 1: Backup adicional antes de mexer em jobs.json**

```bash
cp ~/.openclaw/cron/jobs.json ~/.openclaw/cron/jobs.json.bak.w2-start
```

- [ ] **Step 2: Editar `agentId` em cada cron via script Python**

```bash
python3 <<'PY'
import json, pathlib
p = pathlib.Path('~/.openclaw/cron/jobs.json')
d = json.loads(p.read_text())
mapping = {
  'watchdog:cron-health': 'watchdog-agent',
  'healthcheck:operational-check': 'healthcheck-agent',
  'memory:daily-consolidation': 'memory-consolidation-agent',
  'review:weekly-system-health': 'weekly-review-agent',
}
timeouts = {
  'watchdog-agent': 60,
  'healthcheck-agent': 60,
  'memory-consolidation-agent': 180,
  'weekly-review-agent': 180,
}
for j in d['jobs']:
    if j['name'] in mapping:
        j['agentId'] = mapping[j['name']]
        j['payload']['timeoutSeconds'] = timeouts[mapping[j['name']]]
        print(f"migrated {j['name']} -> agentId={j['agentId']} timeout={j['payload']['timeoutSeconds']}")
p.write_text(json.dumps(d, indent=2))
PY
```
Expected: 4 linhas de output mostrando migração.

- [ ] **Step 3: Validar JSON**

```bash
python3 -c "import json; d=json.load(open('~/.openclaw/cron/jobs.json')); [print(j['name'], '→', j['agentId'], 'timeout:', j['payload']['timeoutSeconds']) for j in d['jobs']]"
```
Expected: 4 jobs com agents novos; demais inalterados.

### Task 17: Privacy gate test — `memory-consolidation-agent`

**Files:** N/A (runtime test)

- [ ] **Step 1: Confirmar que fallback chain NÃO tem openrouter**

```bash
python3 -c "import json; d=json.load(open('~/.openclaw/openclaw.json')); e=d.get('agents',{}).get('entries',{}).get('memory-consolidation-agent',{}); print(json.dumps(e, indent=2))"
```
Expected: `model.fallbacks` contém apenas `openai-codex/gpt-5.4`. **Se contém qualquer `openrouter/*`, aborta** — privacy gate violado na configuração.

- [ ] **Step 2: Simular falha do local temporariamente**

```bash
sudo systemctl stop ollama
sleep 2
systemctl is-active ollama
```
Expected: `inactive`.

- [ ] **Step 3: Rodar cron manualmente**

```bash
openclaw cron run 482e37d6-7a4d-467c-a99b-0e46b60dd3e6 2>&1 | tail -5
# Aguardar ~30s e verificar qual modelo foi usado
sleep 30
tail -1 ~/.openclaw/cron/runs/482e37d6-7a4d-467c-a99b-0e46b60dd3e6.jsonl | python3 -c "import json,sys; d=json.load(sys.stdin); print('status:', d.get('status'), 'model:', d.get('model'))"
```
Expected: ou `status: ok` com `model: gpt-5.4` (fallback legítimo) OU `status: error` (local e gpt-5.4 ambos falharam).

**Crítico:** se o `model` no log for `openrouter/*`, PRIVACY GATE QUEBROU. Abortar tudo e debugar.

- [ ] **Step 4: Restaurar Ollama**

```bash
sudo systemctl start ollama
sleep 3
systemctl is-active ollama
```
Expected: `active`.

- [ ] **Step 5: Registrar resultado**

Anotar em `~/.openclaw/workspace/memory/pending.md` (seção Resolvidos): "Privacy gate de memory-consolidation-agent validado em 2026-04-20 — confirmou queda apenas para openai-codex em falha do local."

### Task 18: Rodar cada cron manualmente e validar

**Files:** N/A (runtime test)

- [ ] **Step 1: `watchdog-agent`**

```bash
openclaw cron run b2f711f3-1173-44dc-be90-eaac9268cb4e 2>&1 | tail -5
sleep 30
tail -1 ~/.openclaw/cron/runs/b2f711f3-1173-44dc-be90-eaac9268cb4e.jsonl | python3 -c "import json,sys; d=json.load(sys.stdin); print('status:', d.get('status'), 'model:', d.get('model'), 'duration:', d.get('durationMs'))"
```
Expected: `status: ok`, `model: qwen3:4b`, `duration < 60000ms`.

- [ ] **Step 2: `healthcheck-agent`**

```bash
openclaw cron run 900940c2-8350-456e-9d2e-e862267a1a21 2>&1 | tail -5
sleep 60
tail -1 ~/.openclaw/cron/runs/900940c2-8350-456e-9d2e-e862267a1a21.jsonl | python3 -c "import json,sys; d=json.load(sys.stdin); print('status:', d.get('status'), 'model:', d.get('model'), 'duration:', d.get('durationMs'))"
```
Expected: `status: ok`, `model: qwen3:4b`, `duration < 60000ms`.

- [ ] **Step 3: `weekly-review-agent`**

```bash
openclaw cron run 68885b74-eedf-4baa-8e94-6284f317283b 2>&1 | tail -5
sleep 120
tail -1 ~/.openclaw/cron/runs/68885b74-eedf-4baa-8e94-6284f317283b.jsonl | python3 -c "import json,sys; d=json.load(sys.stdin); print('status:', d.get('status'), 'model:', d.get('model'), 'duration:', d.get('durationMs'))"
```
Expected: `status: ok`, `model: qwen3:14b`, `duration < 180000ms`.

- [ ] **Step 4: `memory-consolidation-agent`**

```bash
openclaw cron run 482e37d6-7a4d-467c-a99b-0e46b60dd3e6 2>&1 | tail -5
sleep 180
tail -1 ~/.openclaw/cron/runs/482e37d6-7a4d-467c-a99b-0e46b60dd3e6.jsonl | python3 -c "import json,sys; d=json.load(sys.stdin); print('status:', d.get('status'), 'model:', d.get('model'), 'duration:', d.get('durationMs'))"
```
Expected: `status: ok`, `model: qwen3:14b-64k`, `duration < 180000ms`.

- [ ] **Step 5: Se algum falhar**

Investigar log detalhado:
```bash
sudo journalctl -u ollama --since "5 minutes ago" --no-pager | tail -20
```
Considerar rollback individual daquele cron via:
```bash
python3 <<'PY'
import json, pathlib
p = pathlib.Path('~/.openclaw/cron/jobs.json')
d = json.loads(p.read_text())
for j in d['jobs']:
    if j['name'] == 'NOME_DO_QUE_FALHOU':
        j['agentId'] = 'main'  # rollback
        j['payload']['timeoutSeconds'] = 120
p.write_text(json.dumps(d, indent=2))
PY
```

### Task 19: Commit W2 no bevox-knowledge

**Files:**
- Modify: `bevox-knowledge/20_architecture/agents/registry.yml`
- Modify: `bevox-knowledge/20_architecture/agents/registry.md`
- Create: `bevox-knowledge/20_architecture/agents/{watchdog,healthcheck,memory-consolidation,weekly-review}-agent.md`

- [ ] **Step 1: Stage apenas arquivos do W2**

```bash
cd ~/bevox-knowledge && git add 20_architecture/agents/registry.yml 20_architecture/agents/registry.md 20_architecture/agents/watchdog-agent.md 20_architecture/agents/healthcheck-agent.md 20_architecture/agents/memory-consolidation-agent.md 20_architecture/agents/weekly-review-agent.md
git diff --cached --stat
```
Expected: ~6 arquivos staged.

- [ ] **Step 2: Commit**

```bash
cd ~/bevox-knowledge && git commit -m "$(cat <<'EOF'
feat(agents): add 4 per-cron agents for local inference migration

Creates dedicated agents (watchdog, healthcheck, memory-consolidation,
weekly-review) to route each cron to its optimal model. OpenClaw runtime
doesn't honor payload.model, so per-agent is the canonical path.

Privacy gate on memory-consolidation-agent: no openrouter fallback.

Companion to ~/.openclaw/docs/superpowers/specs/2026-04-20-local-inference-adoption-design.md

Draft branch, awaiting Bernard review.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 20: Gate W2 — checkpoint humano

- [ ] **Step 1: Bernard aprova W2**

Pergunta: "W2 concluída — 4 crons rodando em modelos locais, privacy gate de memory-consolidation validado. Posso avançar para W3 (observabilidade) ou prefere 48h de observação primeiro?"

Expected: Bernard decide. Se preferir observação, pause do plano aqui por 48h e retoma em Task 21.

---

## W3 — Observabilidade (1h)

### Task 21: Criar estrutura de `logs/model-routing.jsonl`

**Files:**
- Create: `~/.openclaw/logs/model-routing.jsonl`
- Create: `~/.openclaw/docs/model-routing-schema.md`

- [ ] **Step 1: Criar arquivo de log vazio com permissão correta**

```bash
touch ~/.openclaw/logs/model-routing.jsonl
chmod 600 ~/.openclaw/logs/model-routing.jsonl
```

- [ ] **Step 2: Documentar schema**

Criar `~/.openclaw/docs/model-routing-schema.md`:

```markdown
# model-routing.jsonl schema

Event per line:

```json
{
  "ts": 1776680039499,
  "consumer": "healthcheck-agent",
  "cron_job_id": "900940c2-...",
  "primary_tried": "ollama/qwen3:4b",
  "primary_ok": true,
  "fallback_used": null,
  "fallback_reason": null,
  "duration_ms": 4521,
  "tokens": {"input": 42310, "output": 287},
  "error": null
}
```

Produzido por `~/.openclaw/scripts/log-routing-decision.py` chamado após cada cron run.
Consumido por `~/.openclaw/scripts/check-primary-health.py` (detect 3-consecutive-fail).
```

### Task 22: Script `log-routing-decision.py` que popula o audit log

**Files:**
- Create: `~/.openclaw/scripts/log-routing-decision.py`
- Create: `~/.openclaw/scripts/tests/test_log_routing.py`

- [ ] **Step 1: Escrever teste primeiro**

Arquivo: `~/.openclaw/scripts/tests/test_log_routing.py`:

```python
import json, tempfile, subprocess, pathlib

def test_appends_entry_from_run_log():
    """Given a cron runs JSONL with a finished event, the script appends structured entry to routing log."""
    with tempfile.TemporaryDirectory() as d:
        runs = pathlib.Path(d) / "900940c2.jsonl"
        runs.write_text(json.dumps({
            "ts": 1776680039499,
            "jobId": "900940c2-8350-456e-9d2e-e862267a1a21",
            "action": "finished",
            "status": "ok",
            "durationMs": 4521,
            "model": "qwen3:4b",
            "provider": "ollama",
            "usage": {"input_tokens": 42310, "output_tokens": 287}
        }) + "\n")
        routing = pathlib.Path(d) / "routing.jsonl"
        result = subprocess.run(
            ["python3", "~/.openclaw/scripts/log-routing-decision.py",
             "--runs", str(runs), "--routing", str(routing), "--consumer", "healthcheck-agent"],
            capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        entry = json.loads(routing.read_text().strip())
        assert entry["consumer"] == "healthcheck-agent"
        assert entry["primary_tried"] == "ollama/qwen3:4b"
        assert entry["primary_ok"] is True
        assert entry["duration_ms"] == 4521

def test_flags_fallback_when_error_then_success():
    """When run has an error entry followed by success from different model, fallback_used is set."""
    # ... (espelha o cenário do run do 2026-04-20 retry)
    pass  # implementar após o happy path passar
```

- [ ] **Step 2: Rodar teste, confirmar que falha**

```bash
cd ~/.openclaw/scripts && python3 -m pytest tests/test_log_routing.py::test_appends_entry_from_run_log -v
```
Expected: FAIL (script não existe).

- [ ] **Step 3: Implementar script**

Arquivo: `~/.openclaw/scripts/log-routing-decision.py`:

```python
#!/usr/bin/env python3
"""Reads latest 'finished' event from cron runs JSONL and appends structured entry to routing log."""
import argparse, json, pathlib, sys

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--runs", required=True, help="Cron runs JSONL path")
    p.add_argument("--routing", required=True, help="Routing audit JSONL path")
    p.add_argument("--consumer", required=True, help="Agent name (e.g., healthcheck-agent)")
    args = p.parse_args()

    runs = pathlib.Path(args.runs)
    if not runs.exists():
        sys.exit("runs file not found")
    
    last_finished = None
    for line in runs.read_text().splitlines():
        try: d = json.loads(line)
        except: continue
        if d.get("action") == "finished":
            last_finished = d
    
    if not last_finished:
        sys.exit("no finished event found")
    
    provider = last_finished.get("provider", "unknown")
    model = last_finished.get("model", "unknown")
    entry = {
        "ts": last_finished.get("ts"),
        "consumer": args.consumer,
        "cron_job_id": last_finished.get("jobId"),
        "primary_tried": f"{provider}/{model}",
        "primary_ok": last_finished.get("status") == "ok",
        "fallback_used": None,  # stays null in MVP; populated by W3.5 when auto-breaker plugin lands
        "fallback_reason": None,
        "duration_ms": last_finished.get("durationMs"),
        "tokens": last_finished.get("usage") or {},
        "error": last_finished.get("error"),
    }
    
    with open(args.routing, "a") as f:
        f.write(json.dumps(entry) + "\n")

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Rodar teste, confirmar que passa**

```bash
cd ~/.openclaw/scripts && python3 -m pytest tests/test_log_routing.py::test_appends_entry_from_run_log -v
```
Expected: PASS.

- [ ] **Step 5: Chmod executável**

```bash
chmod +x ~/.openclaw/scripts/log-routing-decision.py
```

- [ ] **Step 6: Integrar ao fluxo** 

Opção canônica: chamar esse script automaticamente após cada cron. Como OpenClaw não expõe post-run hook, solução MVP: rodar via cron dedicado (timer systemd ou OpenClaw cron adicional) a cada 5min lendo todos os cron runs novos.

Criar `~/.openclaw/scripts/routing-log-watcher.sh`:

```bash
#!/bin/bash
# Runs every 5 min; scans cron runs for new finished events since last scan; calls log-routing-decision.py for each.
LAST_SCAN_FILE=~/.openclaw/scripts/.last-routing-scan
LAST=$(cat "$LAST_SCAN_FILE" 2>/dev/null || echo 0)
NOW=$(date +%s)

declare -A JOB_TO_AGENT=(
  ["900940c2-8350-456e-9d2e-e862267a1a21"]="healthcheck-agent"
  ["b2f711f3-1173-44dc-be90-eaac9268cb4e"]="watchdog-agent"
  ["482e37d6-7a4d-467c-a99b-0e46b60dd3e6"]="memory-consolidation-agent"
  ["68885b74-eedf-4baa-8e94-6284f317283b"]="weekly-review-agent"
)

for job in "${!JOB_TO_AGENT[@]}"; do
  RUNS="~/.openclaw/cron/runs/${job}.jsonl"
  [ -f "$RUNS" ] || continue
  # Check if file modified since last scan
  MTIME=$(stat -c %Y "$RUNS")
  if [ "$MTIME" -gt "$LAST" ]; then
    python3 ~/.openclaw/scripts/log-routing-decision.py \
      --runs "$RUNS" \
      --routing ~/.openclaw/logs/model-routing.jsonl \
      --consumer "${JOB_TO_AGENT[$job]}"
  fi
done
echo "$NOW" > "$LAST_SCAN_FILE"
```

```bash
chmod +x ~/.openclaw/scripts/routing-log-watcher.sh
```

- [ ] **Step 7: Configurar via systemd timer**

```bash
sudo tee /etc/systemd/system/openclaw-routing-watcher.service > /dev/null <<'EOF'
[Unit]
Description=OpenClaw routing-log watcher

[Service]
Type=oneshot
ExecStart=~/.openclaw/scripts/routing-log-watcher.sh
User=bernard
EOF

sudo tee /etc/systemd/system/openclaw-routing-watcher.timer > /dev/null <<'EOF'
[Unit]
Description=Run openclaw-routing-watcher every 5 min

[Timer]
OnBootSec=1min
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now openclaw-routing-watcher.timer
```

- [ ] **Step 8: Verificar**

```bash
systemctl list-timers | grep openclaw-routing-watcher
sleep 90  # aguarda primeira execução
cat ~/.openclaw/logs/model-routing.jsonl | tail -5
```
Expected: linhas JSON estruturadas dos crons recentes.

### Task 23: Script `check-primary-health.py` — detect 3-consecutive-fail

**Files:**
- Create: `~/.openclaw/scripts/check-primary-health.py`
- Create: `~/.openclaw/scripts/tests/test_check_health.py`

- [ ] **Step 1: Escrever teste**

Arquivo: `~/.openclaw/scripts/tests/test_check_health.py`:

```python
import json, tempfile, subprocess, pathlib, sys

def test_flags_3_consecutive_failures():
    """Given 3 consecutive error entries for same consumer+primary, script prints alert JSON."""
    with tempfile.TemporaryDirectory() as d:
        routing = pathlib.Path(d) / "routing.jsonl"
        for i in range(3):
            routing.write_text((routing.read_text() if routing.exists() else "") + json.dumps({
                "ts": 1776680000000 + i*3600000,
                "consumer": "healthcheck-agent",
                "primary_tried": "ollama/qwen3:4b",
                "primary_ok": False,
                "error": "timeout"
            }) + "\n")
        result = subprocess.run(
            ["python3", "~/.openclaw/scripts/check-primary-health.py",
             "--routing", str(routing), "--window", "3"],
            capture_output=True, text=True)
        assert result.returncode == 1, "should exit 1 on alert"
        alert = json.loads(result.stdout)
        assert alert["consumer"] == "healthcheck-agent"
        assert alert["primary"] == "ollama/qwen3:4b"
        assert alert["consecutive_fails"] == 3

def test_no_alert_when_success_resets_counter():
    """Given fail-fail-success-fail, no alert fires."""
    with tempfile.TemporaryDirectory() as d:
        routing = pathlib.Path(d) / "routing.jsonl"
        seq = [False, False, True, False]  # last 3 include a success
        with open(routing, "w") as f:
            for i, ok in enumerate(seq):
                f.write(json.dumps({
                    "ts": 1776680000000 + i*3600000,
                    "consumer": "healthcheck-agent",
                    "primary_tried": "ollama/qwen3:4b",
                    "primary_ok": ok,
                    "error": None if ok else "timeout"
                }) + "\n")
        result = subprocess.run(
            ["python3", "~/.openclaw/scripts/check-primary-health.py",
             "--routing", str(routing), "--window", "3"],
            capture_output=True, text=True)
        assert result.returncode == 0, "should exit 0 when counter reset"
```

- [ ] **Step 2: Rodar teste, confirmar falha**

```bash
cd ~/.openclaw/scripts && python3 -m pytest tests/test_check_health.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implementar**

Arquivo: `~/.openclaw/scripts/check-primary-health.py`:

```python
#!/usr/bin/env python3
"""Detect 3 consecutive failures per (consumer, primary) and emit alert JSON."""
import argparse, json, pathlib, sys
from collections import defaultdict, deque

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--routing", required=True)
    p.add_argument("--window", type=int, default=3, help="N consecutive fails to trigger alert")
    args = p.parse_args()

    routing = pathlib.Path(args.routing)
    if not routing.exists():
        sys.exit(0)

    # Per (consumer, primary), keep rolling window of last N
    windows = defaultdict(lambda: deque(maxlen=args.window))
    
    for line in routing.read_text().splitlines():
        try: d = json.loads(line)
        except: continue
        key = (d.get("consumer"), d.get("primary_tried"))
        windows[key].append(d.get("primary_ok"))
    
    for (consumer, primary), w in windows.items():
        if len(w) == args.window and all(not ok for ok in w):
            alert = {
                "consumer": consumer,
                "primary": primary,
                "consecutive_fails": args.window,
                "action_suggested": f"openclaw cron edit <id> (force fallback for 60min) OR investigate {primary} health"
            }
            print(json.dumps(alert))
            sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Rodar testes**

```bash
cd ~/.openclaw/scripts && python3 -m pytest tests/test_check_health.py -v
```
Expected: 2 PASS.

- [ ] **Step 5: Chmod executável**

```bash
chmod +x ~/.openclaw/scripts/check-primary-health.py
```

### Task 24: Integrar alerta ao `watchdog-agent`

**Files:**
- Modify: `bevox-knowledge/20_architecture/agents/watchdog-agent.md`
- Modify: `~/.openclaw/cron/jobs.json` (prompt do watchdog)

- [ ] **Step 1: Atualizar prompt do watchdog cron**

```bash
python3 <<'PY'
import json, pathlib
p = pathlib.Path('~/.openclaw/cron/jobs.json')
d = json.loads(p.read_text())
for j in d['jobs']:
    if j['name'] == 'watchdog:cron-health':
        j['payload']['message'] = """Faça um watchdog simples dos crons ativos. Siga esta ordem:
1. Rode `~/.openclaw/scripts/check-primary-health.py --routing ~/.openclaw/logs/model-routing.jsonl --window 3` via tool `exec`.
2. Se exit code != 0: leia o JSON de alerta em stdout e envie mensagem curta a Bernard com recomendação de ação.
3. Verifique crons recentes em ~/.openclaw/cron/runs/*.jsonl para anomalias adicionais (status=error).
4. Se falha transitória, tente 1 retry seguro via `openclaw cron run <id>`.
5. Se tudo saudável e sem alerta: responda NO_REPLY."""
        break
p.write_text(json.dumps(d, indent=2))
PY

# Validar
python3 -c "import json; d=json.load(open('~/.openclaw/cron/jobs.json')); [print(j['name'], 'len:', len(j['payload']['message'])) for j in d['jobs'] if j['name']=='watchdog:cron-health']"
```
Expected: tamanho novo > original (prompt mais detalhado).

- [ ] **Step 2: Test end-to-end**

```bash
# Simular estado de 3 fails forçando entries
python3 <<'PY'
import json, pathlib
f = pathlib.Path('~/.openclaw/logs/model-routing.jsonl')
for i in range(3):
    entry = {
        "ts": 1776700000000 + i,
        "consumer": "healthcheck-agent",
        "primary_tried": "ollama/qwen3:4b",
        "primary_ok": False,
        "error": "simulated"
    }
    f.open('a').write(json.dumps(entry) + "\n")
PY

openclaw cron run b2f711f3-1173-44dc-be90-eaac9268cb4e 2>&1 | tail -5
sleep 60
# Verificar se Bernard recebeu alerta (via Telegram)
```
Expected: watchdog executa, detecta alerta, envia notificação a Bernard. Se Telegram não chegar, verificar logs.

- [ ] **Step 3: Limpar simulação**

```bash
# Truncar as 3 entries simuladas (últimas 3 linhas) do log
head -n -3 ~/.openclaw/logs/model-routing.jsonl > /tmp/routing-cleaned.jsonl && mv /tmp/routing-cleaned.jsonl ~/.openclaw/logs/model-routing.jsonl
```

### Task 25: Commit W3 no bevox-knowledge

**Files:** watchdog-agent.md updated

- [ ] **Step 1: Stage e commit**

```bash
cd ~/bevox-knowledge && git add 20_architecture/agents/watchdog-agent.md
git commit -m "$(cat <<'EOF'
feat(observability): watchdog-agent integrates routing-health alert

watchdog:cron-health now runs check-primary-health.py before its usual
sweep. 3 consecutive failures per (consumer, primary) → Bernard alerta.

Auto-swap (W3.5) remains future work — requires plugin or OpenClaw hook.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 26: Gate W3 — checkpoint humano

- [ ] **Step 1: Aprovação**

"W3 concluída — routing audit log + alerta detectado rodando. Posso avançar para W4 (triage + vox-local, risco mais alto)?"

---

## W4 — Triage Humano + Vox-local (2-3h)

### Task 27: Discovery — routing agent em canal Telegram

**Files:** N/A (research)

- [ ] **Step 1: Examinar channel config atual**

```bash
python3 -c "import json; d=json.load(open('~/.openclaw/openclaw.json')); print(json.dumps(d.get('channels',{}), indent=2))"
```
Expected: seção `channels.telegram` com `dmPolicy`, `allowFrom`, `groups`. **Provável que não tenha routing rule por mensagem** hoje.

- [ ] **Step 2: Verificar `openclaw agents` para routing bindings**

```bash
openclaw agents --bindings 2>&1 | head -20
```
Expected: mostra rotas channel→agente. Provavelmente só `main` como default.

- [ ] **Step 3: Decidir arquitetura do triage**

Dois caminhos, escolher baseado no Step 2:

**Path A (OpenClaw suporta routing rule por conteúdo):** configurar `channels.telegram.routing` para: "se primeiro turn de uma thread → triage-agent; senão → agente persistido da sessão (vox-local ou vox-premium)".

**Path B (OpenClaw não suporta content-based routing):** implementar triage como **pre-hook** antes do agent turn. Precisa de plugin custom ou workaround:
- Opção B1: triage-agent é o agente default; ele decide e usa tool `escalate(level)` para encaminhar.
- Opção B2: não introduzir triage real no fluxo; economia vem APENAS dos crons (W2). W4 fica em "agente local disponível via `/local` comando" — não automático.

Path B1 é a recomendação se B for inevitável. Documentar escolha.

### Task 28: Criar `triage-agent` no bevox-knowledge

**Files:**
- Modify: `bevox-knowledge/20_architecture/agents/registry.yml`
- Create: `bevox-knowledge/20_architecture/agents/triage-agent.md`
- Modify: `bevox-knowledge/20_architecture/agents/registry.md` (regen)

- [ ] **Step 1: Adicionar entry em registry.yml**

```yaml
  triage-agent:
    status: ativo
    level: L1
    owner: Bernard
    model:
      primary: ollama/qwen3:4b
      fallback: openai-codex/gpt-5.4
    since: 2026-04-20
    file: triage-agent.md
```

- [ ] **Step 2: Criar página**

Arquivo: `bevox-knowledge/20_architecture/agents/triage-agent.md`:

Incluir:
- Responsabilidade: "Receber 1º turn humano no Telegram DM; classificar como `trivial` (→ vox-local) ou `complex` (→ vox premium gpt-5.4); emitir JSON estruturado com rota, confidence, reason."
- Prompt system:
  ```
  Você é um classificador. Receba uma mensagem de usuário e devolva APENAS um objeto JSON com:
  {"route": "local" | "premium", "confidence": 0.0-1.0, "reason": "string curta"}
  
  Rotear para "local" quando: pergunta operacional simples, pedido de lookup, saudação, status check, comando direto.
  Rotear para "premium" quando: planejamento, debugging complexo, raciocínio arquitetural, ambiguidade alta, código difícil, decisão multi-step.
  Se incerto: preferir "premium".
  ```
- Regra de confidence: se confidence < 0.6, default premium.

- [ ] **Step 3: Regenerar registry.md**

```bash
cd ~/bevox-knowledge && ./20_architecture/agents/_tools/render-registry.py
grep -E "^\| triage-agent" 20_architecture/agents/registry.md
```

### Task 29: Criar `vox-local` no bevox-knowledge

**Files:**
- Modify: `bevox-knowledge/20_architecture/agents/registry.yml`
- Create: `bevox-knowledge/20_architecture/agents/vox-local.md`
- Modify: `bevox-knowledge/20_architecture/agents/registry.md` (regen)

- [ ] **Step 1: Adicionar entry em registry.yml**

```yaml
  vox-local:
    status: ativo
    level: L4
    owner: Bernard
    model:
      primary: ollama/qwen3:14b
      fallback: openai-codex/gpt-5.4
    since: 2026-04-20
    file: vox-local.md
```

- [ ] **Step 2: Criar página — reutilizar identidade de vox com nota sobre modelo**

Arquivo: `bevox-knowledge/20_architecture/agents/vox-local.md`:

Incluir:
- "Variante do Vox executando em modelo local para turns triviais. Mesma persona, identidade e políticas do Vox principal, porém com reasoning reduzido. Para turns que excedem sua capacidade, responde sugerindo `/escalate` ou o triage reencaminha automaticamente em turns subsequentes."
- Link para `vox.md` como canônico de identidade.

- [ ] **Step 3: Regenerar registry.md**

### Task 30: Configurar routing em `openclaw.json`

**Files:**
- Modify: `~/.openclaw/openclaw.json`

- [ ] **Step 1: Aplicar Path A ou B baseado na decisão de Task 27**

**Se Path A:** adicionar em `channels.telegram.routing`:
```json
"routing": {
  "default_agent": "main",
  "rules": [
    {
      "match": { "first_turn_in_session": true, "peer_in": ["<TELEGRAM_USER_ID>"] },
      "agent": "triage-agent"
    }
  ]
}
```

**Se Path B1:** trocar default do canal:
```json
"channels": {
  "telegram": {
    ...
    "defaultAgent": "triage-agent"
  }
}
```

E triage-agent terá tool `escalate(level)` que chama o agente correto. Precisa ser implementado como skill do triage agent.

- [ ] **Step 2: Validar JSON**

```bash
python3 -c "import json; d=json.load(open('~/.openclaw/openclaw.json')); print(json.dumps(d.get('channels',{}).get('telegram',{}).get('routing') or d.get('channels',{}).get('telegram',{}).get('defaultAgent'), indent=2))"
```

### Task 31: Implementar comando `/escalate` como skill

**Files:**
- Create: `~/.openclaw/skills/escalate/SKILL.md`
- Create: `~/.openclaw/skills/escalate/command.sh` (ou equivalente)
- Create: `~/.openclaw/skills/escalate/tests/test_escalate.sh`

- [ ] **Step 1: Estudar estrutura de skills existentes**

```bash
ls ~/.openclaw/skills/ 2>/dev/null | head -10
find ~/.openclaw/skills -name "SKILL.md" 2>/dev/null | head -5
```
Expected: entender convenção local antes de inventar.

- [ ] **Step 2: Definir comportamento**

Quando Bernard digita `/escalate` no Telegram:
1. Skill marca flag `next_turn_force_premium: true` em arquivo de state por sessionKey (ex: `~/.openclaw/workspace/session-state/escalate-flags.json`)
2. Triage-agent lê esse arquivo antes de classificar; se flag set, retorna `{"route": "premium", "reason": "user_escalated", ...}` e limpa flag.

- [ ] **Step 3: Escrever teste**

Arquivo `tests/test_escalate.sh`:

```bash
#!/bin/bash
# Test: /escalate sets flag file
STATE=/tmp/test-escalate-flags.json
rm -f $STATE
bash ~/.openclaw/skills/escalate/command.sh --session "test-sess" --state-file "$STATE"
if [ "$(jq -r '."test-sess"' < $STATE)" != "true" ]; then
  echo "FAIL: flag not set"; exit 1
fi
echo "PASS"
```

- [ ] **Step 4: Rodar teste (deve falhar)**

```bash
bash ~/.openclaw/skills/escalate/tests/test_escalate.sh
```
Expected: FAIL.

- [ ] **Step 5: Implementar**

Arquivo `command.sh`:

```bash
#!/bin/bash
set -e
SESSION=""
STATE="~/.openclaw/workspace/session-state/escalate-flags.json"
while [[ $# -gt 0 ]]; do
  case $1 in
    --session) SESSION="$2"; shift 2;;
    --state-file) STATE="$2"; shift 2;;
    *) shift;;
  esac
done
[ -n "$SESSION" ] || { echo "missing --session"; exit 1; }
mkdir -p "$(dirname "$STATE")"
[ -f "$STATE" ] || echo "{}" > "$STATE"
tmp=$(mktemp)
jq --arg s "$SESSION" '.[$s] = true' "$STATE" > "$tmp" && mv "$tmp" "$STATE"
```

```bash
chmod +x ~/.openclaw/skills/escalate/command.sh
```

SKILL.md:

```markdown
---
name: escalate
description: Force next turn to premium model (gpt-5.4), bypassing triage classification. Use when triage routed to local but you need premium reasoning.
---

# /escalate

Marks a flag in session state. Triage-agent reads this flag and routes next turn to vox premium.

Flag is auto-cleared after use.
```

- [ ] **Step 6: Rodar teste (deve passar)**

```bash
bash ~/.openclaw/skills/escalate/tests/test_escalate.sh
```
Expected: PASS.

- [ ] **Step 7: Registrar skill no openclaw.json**

```bash
python3 <<'PY'
import json, pathlib
p = pathlib.Path('~/.openclaw/openclaw.json')
d = json.loads(p.read_text())
d.setdefault('skills',{}).setdefault('entries',{})['escalate'] = {'enabled': True, 'path': '~/.openclaw/skills/escalate'}
p.write_text(json.dumps(d, indent=2))
PY
```

### Task 32: Ajustar triage-agent para ler flag escalate

**Files:**
- Modify: `bevox-knowledge/20_architecture/agents/triage-agent.md`

- [ ] **Step 1: Adicionar seção "pre-check" no prompt system**

Antes de classificar, triage deve:

```
1. Ler ~/.openclaw/workspace/session-state/escalate-flags.json via tool read.
2. Se sua sessionKey tem flag=true, retornar imediatamente {"route":"premium","confidence":1.0,"reason":"user_escalated"} e chamar tool exec para limpar flag.
3. Senão, classificar normalmente conforme regras.
```

### Task 33: Test E2E — Telegram com triage

**Files:** N/A (runtime test)

- [ ] **Step 1: Mandar mensagem simples via Telegram**

Você (Bernard) manda ao bot: "oi"

Expected: triage classifica como `local`, vox-local responde rapidamente com saudação curta usando qwen3:14b.

Verificar via log:
```bash
tail -1 ~/.openclaw/logs/model-routing.jsonl | python3 -m json.tool
```

- [ ] **Step 2: Mandar mensagem complexa**

Você manda ao bot: "planeja pra mim como refatorar o módulo X assumindo que preciso manter backward compat com 3 clientes"

Expected: triage classifica como `premium`, vox (gpt-5.4) responde.

- [ ] **Step 3: Test `/escalate`**

Você manda: `/escalate` seguido de "oi"

Expected: mesmo que "oi" seria classificado como local, o próximo turn vai forçado para premium (gpt-5.4). Flag é consumida.

- [ ] **Step 4: Documentar resultados em `pending.md`**

Anotar: taxa de classificação correta nos primeiros 10 turns (spot check manual).

### Task 34: Commit W4 no bevox-knowledge

**Files:** triage-agent.md, vox-local.md, registry.yml, registry.md

- [ ] **Step 1: Stage + commit**

```bash
cd ~/bevox-knowledge && git add 20_architecture/agents/registry.yml 20_architecture/agents/registry.md 20_architecture/agents/triage-agent.md 20_architecture/agents/vox-local.md
git commit -m "$(cat <<'EOF'
feat(agents): add triage-agent + vox-local for human turn routing

Triage classifies Telegram DM first-turn as trivial/complex.
Trivial -> vox-local (qwen3:14b). Complex -> Vox premium (gpt-5.4).
/escalate command overrides: forces next turn to premium.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 35: Gate W4 — 1 semana de observação

- [ ] **Step 1: Setup observação**

Bernard usa o bot normalmente por 7 dias. Ao fim:
- Conferir quantos turns foram `local` vs `premium` em `logs/model-routing.jsonl`
- Conferir frequência de `/escalate` (taxa alvo ≤ 30%)
- Spot-check manual: pegar 5 turns classificados como `local` — foram realmente triviais?

- [ ] **Step 2: Spot-check manual semanal (spec §8.2)**

Pegar 5 samples aleatórios de cada um:
```bash
# Samples de memory-consolidation
tail -20 ~/.openclaw/agents/memory-consolidation-agent/sessions/*.jsonl 2>/dev/null | shuf | head -5
# Samples de triage decisions
grep '"consumer":"triage-agent"' ~/.openclaw/logs/model-routing.jsonl | tail -100 | shuf | head -5 | python3 -m json.tool
```

Revisar manualmente:
- Consolidação de memory faz sentido? Capturou decisões importantes? Nada hallucinado?
- Triage classificou corretamente? Algum turn complexo foi para local por engano?

Registrar achados em `~/.openclaw/workspace/memory/pending.md` seção "Observações W4".

- [ ] **Step 3: Decisão pós-semana**

Se:
- Taxa escalate > 30% → retune prompt do triage-agent
- Qualidade vox-local ruim em turns locais → recalibrar threshold (elevar para premium em duplicidade)
- Consolidação de memory degradou → reverter `memory-consolidation-agent` para gpt-5.4 primary e ficar em privacy trade-off
- Tudo OK → prosseguir para wrap-up

---

## Wrap-up (30 min)

### Task 36: Escrever ADR canônica

**Files:**
- Create: `bevox-knowledge/30_adr/ADR-XXX-local-inference-adoption.md`

- [ ] **Step 1: Descobrir próximo número de ADR**

```bash
ls ~/bevox-knowledge/30_adr/ | sort -V | tail -5
```
Expected: ver último ADR-NNN; usar NNN+1 ou o número reservado para esta iniciativa.

- [ ] **Step 2: Escrever ADR**

Arquivo `30_adr/ADR-NNN-local-inference-adoption.md` com seções canônicas: Título, Status (Aceita), Contexto, Decisão, Consequências, Alternativas consideradas, Referências.

- [ ] **Step 3: Conteúdo resumido**

- **Decisão 1:** OpenClaw adota Ollama como 4º provider; qwen3:14b + qwen3:4b como inferência local primária para crons batch e triage humano.
- **Decisão 2:** Privacy gate absoluto em `memory-consolidation-agent`: nenhuma queda para provider fora do host além de openai-codex OAuth.
- **Decisão 3:** Modelos stealth (healer-alpha, hunter-alpha) proibidos em config canônica; só slugs estáveis do OpenRouter.
- **Decisão 4:** Circuit breaker MVP = detect-and-alert; auto-swap vira W3.5 requer plugin custom.

Referência: `docs/superpowers/specs/2026-04-20-local-inference-adoption-design.md`; commit `f0daaa7` (fallback-hardening precursor).

### Task 37: Promover spec para `bevox-knowledge/35_specs/` (opcional)

**Files:**
- Copy: `docs/superpowers/specs/2026-04-20-local-inference-adoption-design.md` → `bevox-knowledge/35_specs/2026-04-20-local-inference-adoption.md`

- [ ] **Step 1: Confirmar com Bernard se quer promover**

- [ ] **Step 2: Se sim, copiar com ajustes de metadata**

```bash
cp ~/.openclaw/docs/superpowers/specs/2026-04-20-local-inference-adoption-design.md ~/bevox-knowledge/35_specs/2026-04-20-local-inference-adoption.md
# Editar header: Status=Aceita (não Draft), adicionar link para ADR
```

### Task 38: Atualizar `pending.md` + commit final

**Files:**
- Modify: `~/.openclaw/workspace/memory/pending.md`
- Commit final em `draft/local-inference-adoption-2026-04-20`

- [ ] **Step 1: Atualizar pending.md**

Seção "Resolvidos recentemente" acrescentar:
```markdown
- [x] 2026-04-20 — Local inference adoption implementada (W1-W4). 
      Stack: Ollama 0.21.0 + qwen3:14b + qwen3:4b + qwen3:14b-64k + deepseek-r1:14b. 
      4 crons migrados, privacy gate de memory-consolidation validado, 
      triage + vox-local ativos no Telegram. ADR-NNN mergeada.
```

Seção "Aguardando Bernard" remover ou marcar itens relacionados.

- [ ] **Step 2: Stage + commit final em bevox-knowledge**

```bash
cd ~/bevox-knowledge && git add 30_adr/ADR-NNN-local-inference-adoption.md 35_specs/2026-04-20-local-inference-adoption.md 2>/dev/null || true
git commit -m "$(cat <<'EOF'
docs(adr): ADR-NNN local inference adoption

Codifica decisões das waves W1-W4 executadas em draft/local-inference-adoption-2026-04-20.

- Ollama como 4º provider canônico
- Privacy gate absoluto em memory-consolidation-agent
- Slugs OpenRouter estáveis apenas
- Circuit breaker MVP = detect-and-alert

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"

git log --oneline -5
```

### Task 39: Handoff — draft para merge

- [ ] **Step 1: Resumo final para Bernard**

"Plano executado. Draft branch `draft/local-inference-adoption-2026-04-20` em bevox-knowledge com X commits. Quer revisar antes de merge para main, ou merge imediato?"

- [ ] **Step 2: Se autorizar merge**

```bash
cd ~/bevox-knowledge && git checkout main && git merge --no-ff draft/local-inference-adoption-2026-04-20
# Não push automático — aguardar autorização explícita do Bernard para push canônico (CLAUDE.md §8)
```

- [ ] **Step 3: Verificar economia real**

```bash
sqlite3 ~/.openclaw/cost/usage-tracking.db "SELECT date, COUNT(*), SUM(total_tokens), ROUND(SUM(cost),2) FROM usage_snapshots WHERE date >= date('now','-7 days') GROUP BY date ORDER BY date;"
```
Expected: tendência decrescente de custo em relação aos 7 dias pré-migração.

---

## Resumo de rollback por componente

| Componente | Rollback | Tempo |
|---|---|---|
| Ollama modelos | `ollama rm qwen3:14b qwen3:4b qwen3:14b-64k deepseek-r1:14b` | 10s |
| Systemd override | `sudo rm /etc/systemd/system/ollama.service.d/override.conf && sudo systemctl daemon-reload` | 5s |
| Plugin ollama | Remover `ollama` de `plugins.allow` e `plugins.entries` em openclaw.json | 10s |
| Crons migrados | Restaurar `jobs.json` de `jobs.json.bak.pre-local-inference` | 5s |
| Routing watcher | `sudo systemctl disable --now openclaw-routing-watcher.timer` | 5s |
| bevox-knowledge | `git checkout main` no bevox-knowledge (branch draft não impactou main) | 1s |
| Emergência total | `cp ~/.openclaw/openclaw.json.bak.pre-local-inference ~/.openclaw/openclaw.json && cp ~/.openclaw/cron/jobs.json.bak.pre-local-inference ~/.openclaw/cron/jobs.json` | 10s |

---

## Fim do plano.
