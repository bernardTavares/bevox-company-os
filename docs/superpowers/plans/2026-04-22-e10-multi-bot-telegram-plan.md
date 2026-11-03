# E10 Multi-bot Telegram Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Habilitar N Telegram bots em paralelo ao Vox (1 bot por área da empresa) usando `openclaw --profile <name>` built-in, cada bot com workspace isolado + shared core via absolute symlinks, + bootstrap script canônico pra criar novos bots em 10-15min.

**Architecture:** 5 phases. Phase 0 valida openclaw `--profile` funcional. Phase 1 cria `workspace-shared/memory/` + instala systemd template `openclaw-gateway@.service`. Phase 2 escreve bootstrap script idempotent. Phase 3+4 executam 2 pilot bots (bevox-mobile reuse de sessions + financeiro greenfield). Phase 5 fecha com release note + tracker + push condicional. Zero modificação em código externo (openclaw npm package) ou em knowledge-sync plugins repo.

**Tech Stack:** Bash + systemd user units + openclaw CLI (`openclaw@2026.4.8` built-in `--profile`) + Telegram Bot API via openclaw channel. Zero dependências pip/npm novas.

**Spec canônica:** `bevox-knowledge/35_specs/2026-04-22-e10-telegram-multi-bot.md` (commit 775f4c4)
**Branch draft:** `draft/e10-multi-bot-telegram` (bevox-knowledge)
**Epic:** E10 — Functional Agents Pack / wave multi-bot-telegram

---

## File Structure

**Runtime (NÃO git-tracked):**
- `~/.config/systemd/user/openclaw-gateway@.service` — template unit (NEW)
- `~/.openclaw/workspace-shared/memory/{user_profile,feedback_universal,reference_bevox_knowledge}.md` — shared core (NEW)
- `~/.openclaw/workspace-shared/memory/MEMORY.md` — index (NEW)
- `~/.openclaw/gateway/bots/README.md` — template + checklist (NEW)
- `~/.openclaw/gateway/bots/bevox-mobile.env` — pilot 1 (NEW, via script)
- `~/.openclaw/gateway/bots/financeiro.env` — pilot 2 (NEW, via script)
- `~/.openclaw/scripts/bootstrap-telegram-agent.sh` — canonical pattern (NEW)
- `~/.openclaw-bevox-mobile/` — pilot 1 profile (NEW, via script)
- `~/.openclaw-financeiro/` — pilot 2 profile (NEW, via script)

**Canonical (bevox-knowledge, branch draft/e10-multi-bot-telegram → merge main):**
- `35_specs/2026-04-22-e10-telegram-multi-bot.md` — spec (JÁ criada, commit 775f4c4)
- `20_architecture/agents/telegram-bot-agent-pattern.md` — cross-ref (NEW)
- `40_roadmap/delivery-tracker.yml` — wave entry (MODIFY, pós-PASS)
- `40_roadmap/2026-04-09-openclaw-company-os-roadmap.md` — E10 status note (MODIFY, pós-PASS)
- `50_releases/2026-04-22-e10-multi-bot-telegram-delivered.md` — release note (NEW, pós-PASS)

**ZERO mudanças em:** openclaw npm package, knowledge-sync repo, Vox runtime (`openclaw-gateway.service` intacto).

---

## Phase 0 — Baseline

### Task 0.1: Validate openclaw `--profile` feature

**Files:** (nenhum modificado; verificação runtime)

- [ ] **Step 1: Confirm openclaw version ≥ 2026.4.8**

```bash
openclaw --version
```

Expected: `2026.4.8` ou maior.

- [ ] **Step 2: Test `--profile` isolation (5s trial run)**

```bash
timeout 5 openclaw --profile test-verify gateway --port 19099 2>&1 | head -10
echo "EXIT=$?"
```

Expected: log line mostrando `[gateway] loading configuration…` + `Missing config. Run 'openclaw --profile test-verify setup' or set gateway.mode=local (or pass --allow-unconfigured).` Confirma que profile isolation funciona (olhou pra `~/.openclaw-test-verify/` que não existe). Exit code será 124 (timeout) OU 1 (missing config).

- [ ] **Step 3: Verify Vox runtime funcional (baseline)**

```bash
systemctl --user is-active openclaw-gateway.service
journalctl --user -u openclaw-gateway.service --since '5 minutes ago' --no-pager 2>&1 | tail -5
```

Expected: `active` + logs recentes do Vox gateway.

- [ ] **Step 4: Nenhum commit.**

---

## Phase 1 — Infra shared core + systemd template

### Task 1.1: Create `workspace-shared/memory/` com 3 core files

**Files:**
- Create: `~/.openclaw/workspace-shared/memory/user_profile.md`
- Create: `~/.openclaw/workspace-shared/memory/feedback_universal.md`
- Create: `~/.openclaw/workspace-shared/memory/reference_bevox_knowledge.md`
- Create: `~/.openclaw/workspace-shared/memory/MEMORY.md`

- [ ] **Step 1: mkdir structure**

```bash
mkdir -p ~/.openclaw/workspace-shared/memory
ls -la ~/.openclaw/workspace-shared/
```

Expected: dir criado vazio.

- [ ] **Step 2: Create `user_profile.md`**

```bash
cat > ~/.openclaw/workspace-shared/memory/user_profile.md <<'EOF'
---
name: Bernard user profile
description: Founder Bevox; operação Company OS; comunicação PT-BR direta
type: user
---

# Bernard — founder Bevox

Founder da Bevox. Opera o Company OS interno (OpenClaw) em paralelo a desenvolvimento do produto principal. Experiência técnica solida (engineering + produto + operacional).

## Preferências de comunicação

- **Idioma primário:** Português brasileiro (PT-BR).
- **Tom:** direto, sem enrolação, sem elogios vazios.
- **Formato:** curto e operacional. Recomendação clara com impacto + risco + próximo passo.
- **Discordância:** esperada quando houver risco real, drift arquitetural, mistura de boundary, automação prematura, segurança fraca, complexidade desnecessária.

## Responsabilidades

- Decisões canônicas de boundary Company OS ↔ produto Bevox
- Approvals pra operações sensíveis (push canônico, mudança de policy, systemd, etc)
- Roadmap estratégico + prioridades
- Commit final em specs/ADRs

## Stack técnico que usa

- Claude Code como ambiente principal de dev
- OpenClaw + bevox-knowledge (SoT) + Mission Control
- Telegram como canal operacional (grupo principal + grupos áreas-específicas multi-bot)
EOF
wc -l ~/.openclaw/workspace-shared/memory/user_profile.md
```

Expected: ~30 linhas gravadas.

- [ ] **Step 3: Create `feedback_universal.md`**

```bash
cat > ~/.openclaw/workspace-shared/memory/feedback_universal.md <<'EOF'
---
name: Universal response style feedback
description: Estilo de resposta aplicável a qualquer bot/área
type: feedback
---

# Feedback universal de estilo (cross-área)

## Resposta default

- Curta, sem header/footer decorativos.
- Sem "ótima pergunta!" ou elogios vazios.
- Sem trailing summary resumindo o que foi feito — Bernard lê o diff/output.
- Usar markdown quando agrega clareza (tabelas, listas); evitar quando só polui.
- Recomendação explícita quando há decisão a tomar. Formato "A/B/C" preferido.

## Quando discordar

- Flag explicitamente riscos, drift ou complexidade desnecessária.
- Propor alternativa com tradeoffs.
- Não ceder pra "agradar" — confronto técnico é produtivo.

## Quando faltar contexto

- Não inventar. Procurar em bevox-knowledge primeiro. Se ambíguo, fazer proposta marcada como hipótese.
- Melhor "isso não está decidido" do que improvisar como se fosse canônico.

**Why:** Bernard valoriza velocidade + clareza + segurança operacional. Respostas longas/genéricas custam tempo sem agregar.

**How to apply:** Aplicar em toda resposta, qualquer bot, qualquer área. Se feedback específico de área conflitar, feedback de área vence.
EOF
wc -l ~/.openclaw/workspace-shared/memory/feedback_universal.md
```

Expected: ~30 linhas.

- [ ] **Step 4: Create `reference_bevox_knowledge.md`**

```bash
cat > ~/.openclaw/workspace-shared/memory/reference_bevox_knowledge.md <<'EOF'
---
name: bevox-knowledge SoT repository
description: Source of Truth canônico — hierarquia + locations
type: reference
---

# bevox-knowledge (SoT)

**Path local:** `~/bevox-knowledge/`
**Repo:** `github.com/bernardTavares/bevox-knowledge`

## Hierarquia canônica

- `30_adr/` — ADRs (Architecture Decision Records) aceitas
- `35_specs/` — specs por epic/wave/feature (implementation truth)
- `40_roadmap/`:
  - `2026-04-09-openclaw-company-os-roadmap.md` — narrativa estratégica
  - `delivery-tracker.yml` — state de execução por epic/feature/wave
- `50_releases/` — release notes pós-delivery
- `20_architecture/` — padrões arquiteturais + cross-refs curtos
- `00_inbox/` — logs factuais + notas operacionais

## Regras de branch

- `main` = conteúdo aceito/canônico
- `draft/*` = propostas/rascunhos em revisão
- Mudança canônica exige merge explícito com go-ahead Bernard

## Conflict resolution

Se conflito entre narrativa (roadmap) e spec/tracker: **spec mais recente vence**.

**How to apply:** Ao responder qualquer query que envolva decisão, arquitetura, roadmap, status de entrega — consultar bevox-knowledge primeiro. Citar path + linha quando relevante. Nunca inventar estado sem checar.
EOF
```

Expected: arquivo criado.

- [ ] **Step 5: Create `MEMORY.md` index**

```bash
cat > ~/.openclaw/workspace-shared/memory/MEMORY.md <<'EOF'
# Memory index — workspace-shared (cross-profile core)

Compartilhado via absolute symlinks pelos workspaces de cada bot profile:
- `~/.openclaw/workspace/memory/` (Vox default)
- `~/.openclaw-bevox-mobile/workspace/memory/`
- `~/.openclaw-financeiro/workspace/memory/`
- `~/.openclaw-<area>/workspace/memory/` (futuros)

## Core files

- [User profile](user_profile.md) — Bernard founder perfil (role + comunicação + responsabilidades + stack)
- [Feedback universal](feedback_universal.md) — estilo de resposta cross-área
- [Reference bevox-knowledge](reference_bevox_knowledge.md) — SoT path + hierarquia + branch rules
EOF
ls -la ~/.openclaw/workspace-shared/memory/
```

Expected: 4 arquivos `.md` listados.

- [ ] **Step 6: Nenhum commit (runtime NÃO git-tracked).**

### Task 1.2: Install systemd template `openclaw-gateway@.service`

**Files:**
- Create: `~/.config/systemd/user/openclaw-gateway@.service`

- [ ] **Step 1: Write template unit file**

```bash
cat > ~/.config/systemd/user/openclaw-gateway@.service <<'EOF'
[Unit]
Description=OpenClaw Gateway — profile %i
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=%h/.openclaw/gateway/bots/%i.env
ExecStart=/usr/bin/openclaw --profile %i gateway --port ${OPENCLAW_GATEWAY_PORT}
Restart=on-failure
RestartSec=10
TimeoutStopSec=30
SuccessExitStatus=0 143
KillMode=control-group
Environment=HOME=~
Environment=PATH=/usr/bin:~/.local/bin:~/.npm-global/bin:~/bin:~/.volta/bin:~/.asdf/shims:~/.bun/bin:~/.nvm/current/bin:~/.fnm/current/bin:~/.local/share/pnpm:/usr/local/bin:/bin

[Install]
WantedBy=default.target
EOF
cat ~/.config/systemd/user/openclaw-gateway@.service
```

Expected: arquivo criado com content correto.

- [ ] **Step 2: Verify openclaw binary path**

```bash
which openclaw
```

Expected: `~/.npm-global/bin/openclaw` ou similar. Se diferente de `/usr/bin/openclaw`, corrigir `ExecStart=` no template para path real.

- [ ] **Step 3: Corrigir ExecStart se necessário**

Se `which openclaw` retornar path diferente de `/usr/bin/openclaw`, editar o template:

```bash
OPENCLAW_BIN=$(which openclaw)
sed -i "s|ExecStart=/usr/bin/openclaw|ExecStart=$OPENCLAW_BIN|" ~/.config/systemd/user/openclaw-gateway@.service
cat ~/.config/systemd/user/openclaw-gateway@.service | grep ExecStart
```

Expected: ExecStart usa path absoluto correto do binary.

- [ ] **Step 4: Reload systemd daemon**

```bash
systemctl --user daemon-reload
systemctl --user list-unit-files 'openclaw-gateway@*' --no-pager
```

Expected: unit listado (template).

- [ ] **Step 5: Nenhum commit.**

### Task 1.3: Create `gateway/bots/` dir + README template

**Files:**
- Create: `~/.openclaw/gateway/bots/README.md`

- [ ] **Step 1: mkdir + README**

```bash
mkdir -p ~/.openclaw/gateway/bots
cat > ~/.openclaw/gateway/bots/README.md <<'EOF'
# gateway/bots/ — Multi-bot Telegram instance env files

Cada arquivo `<area>.env` corresponde a uma instância
`openclaw-gateway@<area>.service` rodando um profile openclaw isolado.

## Estrutura esperada de cada `<area>.env`

```
OPENCLAW_GATEWAY_PORT=<port-exclusivo>
# Profile: <area>. Config completa em ~/.openclaw-<area>/openclaw.json.
# Token, chat_ids, plugins, agents ficam em openclaw.json (convenção
# openclaw native, não em env file).
```

## Port allocation convention

- 18789 → Vox default (openclaw-gateway.service, sem template)
- 18790 → bevox-mobile
- 18791 → financeiro
- 18792+ → bots adicionais (marketing, bevox-backend, etc)

## Criar novo bot

```bash
~/.openclaw/scripts/bootstrap-telegram-agent.sh <area> <port>
```

Depois seguir checklist impresso pelo script.

## Audit

```bash
systemctl --user list-units 'openclaw-gateway@*' --no-pager
ls ~/.openclaw/gateway/bots/*.env
```
EOF
ls ~/.openclaw/gateway/bots/
```

Expected: `README.md` único arquivo.

- [ ] **Step 2: Nenhum commit.**

---

## Phase 2 — Bootstrap script + pattern doc

### Task 2.1: Write `bootstrap-telegram-agent.sh`

**Files:**
- Create: `~/.openclaw/scripts/bootstrap-telegram-agent.sh`

- [ ] **Step 1: Write script**

```bash
mkdir -p ~/.openclaw/scripts
cat > ~/.openclaw/scripts/bootstrap-telegram-agent.sh <<'EOFSCRIPT'
#!/bin/bash
# Bootstrap de novo bot Telegram por área usando openclaw --profile.
# Uso: ~/.openclaw/scripts/bootstrap-telegram-agent.sh <area> <port>
# Idempotente: safe re-run; NÃO sobrescreve area_context.md populado.

set -euo pipefail

AREA="${1:-}"
PORT="${2:-}"
if [[ -z "$AREA" || ! "$AREA" =~ ^[a-z][a-z0-9-]*$ ]]; then
  echo "usage: $0 <area> <port>  (area: lowercase+alphanumeric+hyphens; port: int)"
  exit 2
fi
if [[ "$AREA" == "dev" ]]; then
  echo "error: 'dev' é reservado pelo openclaw (--dev profile)"
  exit 2
fi
if [[ -z "$PORT" || ! "$PORT" =~ ^[0-9]+$ ]]; then
  echo "usage: $0 <area> <port>  (port integer; convenção 18790+)"
  exit 2
fi

SHARED="$HOME/.openclaw/workspace-shared/memory"
PROFILE_DIR="$HOME/.openclaw-$AREA"
WS="$PROFILE_DIR/workspace/memory"
ENV_FILE="$HOME/.openclaw/gateway/bots/$AREA.env"
TEMPLATE_CONFIG="$HOME/.openclaw/openclaw.json"

# Preflight
[[ -d "$SHARED" ]] || { echo "FAIL: $SHARED missing; run phase-1 first"; exit 1; }
[[ -f "$SHARED/user_profile.md" ]] || { echo "FAIL: $SHARED/user_profile.md missing"; exit 1; }
[[ -f "$TEMPLATE_CONFIG" ]] || { echo "FAIL: $TEMPLATE_CONFIG missing (Vox config necessária como template)"; exit 1; }

# Profile dir + workspace structure
mkdir -p "$WS"/{context,feedback,projects,sessions}
mkdir -p "$(dirname "$ENV_FILE")"

# 3 absolute symlinks pro shared core
cd "$WS"
for f in user_profile.md feedback_universal.md reference_bevox_knowledge.md; do
  if [[ ! -L "$f" ]]; then
    ln -s "$SHARED/$f" "$f"
  fi
done

# MEMORY.md index (cria se ausente)
if [[ ! -f "$WS/MEMORY.md" ]]; then
  cat > "$WS/MEMORY.md" <<EOF2
# Memory index — $AREA

## Shared (absolute symlinks para workspace-shared/memory/)
- [User profile](user_profile.md) — Bernard founder perfil (shared)
- [Feedback universal](feedback_universal.md) — estilo de resposta (shared)
- [Reference bevox-knowledge](reference_bevox_knowledge.md) — SoT path (shared)

## Local $AREA

(adicionar projects/feedback/reference específicos aqui conforme bot acumula memory)
EOF2
fi

# area_context.md (cria APENAS se ausente; não sobrescreve populado)
if [[ ! -f "$WS/area_context.md" ]]; then
  cat > "$WS/area_context.md" <<EOF2
# Contexto $AREA

<!-- Contexto específico da área $AREA. Complementa instructions Vox base. -->
<!-- Exemplos (remova esse bloco ao popular):                               -->
<!-- - Vocabulário domínio: [termos técnicos da área]                       -->
<!-- - Tools/platforms: [ex: YNAB, Linear, Notion]                          -->
<!-- - Referencias canônicas: [pastas bevox-knowledge relevantes]           -->
<!-- - Comportamento default: [formatos, tom adaptado à área]               -->
EOF2
fi

# openclaw.json do profile: clona do Vox + ajusta workspace + placeholder channels
if [[ ! -f "$PROFILE_DIR/openclaw.json" ]]; then
  cp "$TEMPLATE_CONFIG" "$PROFILE_DIR/openclaw.json"
  python3 - <<PYEOF
import json
p = "$PROFILE_DIR/openclaw.json"
c = json.load(open(p))
c["agents"]["defaults"]["workspace"] = "$PROFILE_DIR/workspace"
c["agents"]["list"] = [{"id": "main", "workspace": "$PROFILE_DIR/workspace"}]
# Placeholder channels.telegram — Bernard popula post-bootstrap
if "channels" not in c:
    c["channels"] = {}
c["channels"]["telegram"] = {
    "enabled": True,
    "groups": {"<POPULATE_CHAT_ID>": {"requireMention": False}},
    "dmPolicy": "allowlist",
    "allowFrom": ["<POPULATE_BERNARD_USER_ID>"],
}
# Plugins: core only por default
if "plugins" not in c:
    c["plugins"] = {}
c["plugins"]["allow"] = ["knowledge-sync-commands"]
json.dump(c, open(p, "w"), indent=2)
PYEOF
  chmod 0600 "$PROFILE_DIR/openclaw.json"
fi

# Env file pro systemd (port + boot vars)
if [[ ! -f "$ENV_FILE" ]]; then
  cat > "$ENV_FILE" <<EOF2
OPENCLAW_GATEWAY_PORT=$PORT
# Profile: $AREA. Config completa em $PROFILE_DIR/openclaw.json.
# Token Telegram vai direto na config do profile (channels.telegram),
# NÃO neste env file (convenção openclaw native).
EOF2
  chmod 0600 "$ENV_FILE"
fi

echo ""
echo "✓ Bootstrap $AREA complete (port $PORT)."
echo ""
echo "Checklist manual Bernard:"
echo "  1. @BotFather → /newbot → nome + username → guardar TOKEN"
echo "  2. Telegram → criar grupo novo → add bot → guardar CHAT_ID"
echo "  3. Editar $PROFILE_DIR/openclaw.json:"
echo "     - channels.telegram.groups: substitua '<POPULATE_CHAT_ID>' pelo CHAT_ID real"
echo "     - channels.telegram.allowFrom: substitua '<POPULATE_BERNARD_USER_ID>' pelo seu user_id"
echo "     - Token via: openclaw --profile $AREA auth telegram set <TOKEN>"
echo "       (OU editar openclaw.json direto se preferir)"
echo "     - plugins.allow: adicionar opcionais (ex: clarification-commands) se desejar"
echo "  4. Editar $WS/area_context.md (remover placeholder + adicionar contexto real)"
echo "  5. systemctl --user enable --now openclaw-gateway@$AREA.service"
echo "  6. Test: mensagem no grupo mencionando o bot → expect resposta contextual"
EOFSCRIPT
chmod +x ~/.openclaw/scripts/bootstrap-telegram-agent.sh
ls -la ~/.openclaw/scripts/bootstrap-telegram-agent.sh
```

Expected: arquivo criado executável (`-rwxr-xr-x`).

- [ ] **Step 2: Test bash syntax**

```bash
bash -n ~/.openclaw/scripts/bootstrap-telegram-agent.sh && echo "OK syntax"
```

Expected: `OK syntax`.

- [ ] **Step 3: Test validation (should reject bad input)**

```bash
~/.openclaw/scripts/bootstrap-telegram-agent.sh 2>&1 | head -2
~/.openclaw/scripts/bootstrap-telegram-agent.sh Foo 18792 2>&1 | head -2
~/.openclaw/scripts/bootstrap-telegram-agent.sh dev 18792 2>&1 | head -2
~/.openclaw/scripts/bootstrap-telegram-agent.sh valid-area abc 2>&1 | head -2
```

Expected:
- Linha 1: `usage: ... <area> <port>` + exit 2
- Linha 2: `usage: ...` (Foo tem uppercase) + exit 2
- Linha 3: `error: 'dev' é reservado pelo openclaw (--dev profile)` + exit 2
- Linha 4: `usage: ...` (port não é int) + exit 2

- [ ] **Step 4: Nenhum commit.**

### Task 2.2: Test script idempotent com area fake

**Files:** (teste transient; cleanup ao final)

- [ ] **Step 1: Run script com area de teste**

```bash
~/.openclaw/scripts/bootstrap-telegram-agent.sh wave8-test-bot 19999 2>&1 | tail -20
```

Expected: `✓ Bootstrap wave8-test-bot complete (port 19999)` + checklist impresso.

- [ ] **Step 2: Verify filesystem criado**

```bash
echo '=== Profile dir ==='
ls -la ~/.openclaw-wave8-test-bot/ 2>&1
echo ''
echo '=== Workspace memory ==='
ls -la ~/.openclaw-wave8-test-bot/workspace/memory/ 2>&1
echo ''
echo '=== Symlinks point to shared ==='
for f in ~/.openclaw-wave8-test-bot/workspace/memory/{user_profile,feedback_universal,reference_bevox_knowledge}.md; do
  readlink "$f"
done
echo ''
echo '=== openclaw.json shape ==='
python3 -c "
import json
c = json.load(open('~/.openclaw-wave8-test-bot/openclaw.json'))
print('workspace default:', c['agents']['defaults']['workspace'])
print('agents list:', c['agents']['list'])
print('telegram groups:', c['channels']['telegram']['groups'])
print('plugins.allow:', c['plugins']['allow'])
"
echo ''
echo '=== Env file ==='
cat ~/.openclaw/gateway/bots/wave8-test-bot.env
```

Expected:
- Profile dir tem `openclaw.json` + `workspace/memory/`
- 3 symlinks apontam pra `~/.openclaw/workspace-shared/memory/*`
- `workspace default`: `~/.openclaw-wave8-test-bot/workspace`
- `telegram groups`: `{'<POPULATE_CHAT_ID>': {'requireMention': False}}`
- `plugins.allow`: `['knowledge-sync-commands']`
- Env file tem `OPENCLAW_GATEWAY_PORT=19999`

- [ ] **Step 3: Run script segunda vez (test idempotência)**

```bash
# Popula area_context.md pra verificar que não é sobrescrito
echo "# Test content preserved" > ~/.openclaw-wave8-test-bot/workspace/memory/area_context.md

~/.openclaw/scripts/bootstrap-telegram-agent.sh wave8-test-bot 19999 2>&1 | tail -5

# Verify area_context NOT overwritten
cat ~/.openclaw-wave8-test-bot/workspace/memory/area_context.md
```

Expected: `# Test content preserved` (nao sobrescrito; script é idempotent).

- [ ] **Step 4: Cleanup test profile**

```bash
rm -rf ~/.openclaw-wave8-test-bot/
rm -f ~/.openclaw/gateway/bots/wave8-test-bot.env
ls ~/.openclaw-wave8-test-bot/ 2>&1 || echo "✓ profile removed"
ls ~/.openclaw/gateway/bots/ | grep -v README
```

Expected: profile removed; bots/ dir só tem README.md.

- [ ] **Step 5: Nenhum commit.**

---

## Phase 3 — Pilot 1: bot-bevox-mobile

### Task 3.1: Bernard cria bot + grupo Telegram

**Files:** (ação externa Bernard)

- [ ] **Step 1: @BotFather → /newbot**

No Telegram:
1. Abrir `@BotFather`
2. `/newbot`
3. Nome display: `Bevox Mobile Bot`
4. Username: `<ProjectBot>` (ou variação se disponível)
5. Guardar o TOKEN retornado (formato `<digits>:<chars>`)

- [ ] **Step 2: Criar grupo Telegram**

1. Criar grupo novo "bevox — mobile" (ou nome similar)
2. Add o bot criado acima como member do grupo
3. Promover bot a admin (necessário pra ler msgs)
4. Pegar CHAT_ID: enviar `/ping` no grupo (bot ignora, mas logs mostram chat_id). OU usar `curl https://api.telegram.org/bot<TOKEN>/getUpdates | jq '.result[-1].message.chat.id'`. CHAT_ID começa com `-100` (supergroup).

- [ ] **Step 3: Guardar TOKEN + CHAT_ID pra Task 3.3**

### Task 3.2: Run bootstrap script

**Files:** (script execution)

- [ ] **Step 1: Bootstrap `bevox-mobile` profile**

```bash
~/.openclaw/scripts/bootstrap-telegram-agent.sh bevox-mobile 18790 2>&1 | tail -20
```

Expected: `✓ Bootstrap bevox-mobile complete (port 18790)` + checklist impresso.

- [ ] **Step 2: Verify profile criado**

```bash
ls ~/.openclaw-bevox-mobile/
ls ~/.openclaw-bevox-mobile/workspace/memory/
cat ~/.openclaw/gateway/bots/bevox-mobile.env
```

Expected:
- Profile dir criado com `openclaw.json` + `workspace/`
- Workspace memory tem 3 symlinks + area_context.md + MEMORY.md + subdirs
- Env file tem `OPENCLAW_GATEWAY_PORT=18790`

### Task 3.3: Edit `openclaw.json` com TOKEN + CHAT_ID + plugins

**Files:**
- Modify: `~/.openclaw-bevox-mobile/openclaw.json`

- [ ] **Step 1: Setup token via openclaw CLI**

```bash
# Substituir <TOKEN> pelo token real do BotFather
openclaw --profile bevox-mobile auth telegram set <TOKEN>
```

Expected: output confirma token saved. Alternativa: editar openclaw.json direto em `channels.telegram.token` (campo específico) OU via env file openclaw-conventional.

Note: Se `auth telegram set` não existir como subcmd, editar openclaw.json direto:
```bash
python3 - <<'PYEOF'
import json
p = "~/.openclaw-bevox-mobile/openclaw.json"
c = json.load(open(p))
c["channels"]["telegram"]["botToken"] = "<TOKEN-REAL>"
json.dump(c, open(p, "w"), indent=2)
PYEOF
```

- [ ] **Step 2: Substituir CHAT_ID + Bernard user_id**

```bash
# Discover Bernard user_id: message the bot in private, see getUpdates output
# OR use value já conhecido do Vox openclaw.json allowFrom
BERNARD_UID=$(python3 -c "import json; c=json.load(open('~/.openclaw/openclaw.json')); print(c['channels']['telegram']['allowFrom'][0])")
echo "Bernard UID (from Vox): $BERNARD_UID"

# Substituir placeholders (usar CHAT_ID real do Task 3.1 step 2)
python3 - <<PYEOF
import json
p = "~/.openclaw-bevox-mobile/openclaw.json"
c = json.load(open(p))
BERNARD_UID = "$BERNARD_UID"
CHAT_ID = "<POPULATE_CHAT_ID_REAL>"  # Substituir pelo valor real (-100...)
# Substitui placeholders
c["channels"]["telegram"]["allowFrom"] = [BERNARD_UID]
c["channels"]["telegram"]["groups"] = {CHAT_ID: {"requireMention": False}}
json.dump(c, open(p, "w"), indent=2)
print("allowFrom:", c["channels"]["telegram"]["allowFrom"])
print("groups:", list(c["channels"]["telegram"]["groups"].keys()))
PYEOF
```

Expected: allowFrom contém Bernard user_id + groups tem CHAT_ID real.

- [ ] **Step 3: Adicionar clarification-commands plugin à allow list**

```bash
python3 - <<'PYEOF'
import json
p = "~/.openclaw-bevox-mobile/openclaw.json"
c = json.load(open(p))
allowed = set(c.get("plugins", {}).get("allow", []))
allowed.add("clarification-commands")
c["plugins"]["allow"] = sorted(allowed)
# Verificar que plugins.installs já herdado tem entry pro clarification-commands (do template Vox)
print("allow:", c["plugins"]["allow"])
print("installs count:", len(c["plugins"].get("installs", [])))
json.dump(c, open(p, "w"), indent=2)
PYEOF
```

Expected: `allow` contém `['clarification-commands', 'knowledge-sync-commands']` sorted.

### Task 3.4: Popular `area_context.md` com bevox-mobile domain

**Files:**
- Modify: `~/.openclaw-bevox-mobile/workspace/memory/area_context.md`

- [ ] **Step 1: Overwrite placeholder com contexto real**

```bash
cat > ~/.openclaw-bevox-mobile/workspace/memory/area_context.md <<'EOF'
# Contexto bevox-mobile

## Vocabulário de domínio

- iOS, Android, React Native, Expo
- App lifecycle: dev → staging → TestFlight/Internal Testing → Production
- CI: GitHub Actions + Fastlane
- Crash reporting: Firebase Crashlytics
- Analytics: Firebase Analytics / Mixpanel

## Tools & platforms

- Xcode (iOS), Android Studio (Android), Expo Go (dev)
- Firebase Console (crash + analytics)
- App Store Connect / Google Play Console (release)

## Referencias canônicas

- `bevox-knowledge/20_architecture/agents/bevox-mobile-*.md` — specs bevox-mobile agent
- `bevox-knowledge/35_specs/` — specs ativas de features mobile
- `bevox-knowledge/40_roadmap/delivery-tracker.yml` — E10 entries relevantes
- `~/code/bevox-mobile/` — source repo (não SoT, é trabalho)

## Comportamento default

- Decisões sobre build/release exigem evidência de CI green + crash baseline validation.
- Não prometer release sem approval explícito + checklist pre-release.
- Links canônicos sempre que referenciar decisão ou spec.
- Flag se mudança arquitetural sem spec — não implementar "no escuro".

## Loop operacional

- Clarifications escaladas deste bot via wave-2/3 OH → daemon resolve OR Bernard responde `/clr_*`.
- Tasks ready em kanban `bevox-mobile` project → cron-dispatcher pega em 5min.
- Testes via tester-agent com AC validation.
EOF
wc -l ~/.openclaw-bevox-mobile/workspace/memory/area_context.md
```

Expected: ~30-35 linhas.

### Task 3.5: systemctl enable + smoke

**Files:** (runtime activation)

- [ ] **Step 1: Enable + start**

```bash
systemctl --user enable --now openclaw-gateway@bevox-mobile.service
sleep 3
systemctl --user is-active openclaw-gateway@bevox-mobile.service
systemctl --user status openclaw-gateway@bevox-mobile.service --no-pager 2>&1 | head -15
```

Expected: status = `active (running)`. Logs mostram gateway loading + Telegram channel ativo.

- [ ] **Step 2: Verify Vox NÃO foi afetado**

```bash
systemctl --user is-active openclaw-gateway.service
```

Expected: `active` (Vox continua intacto).

- [ ] **Step 3: Smoke test — mandar mensagem no grupo Telegram bevox-mobile**

Enviar mensagem no grupo Telegram "bevox — mobile" (criado Task 3.1):
> @<project_bot> resumo do que foi feito no bloco OH

Expected: bot responde com resumo do bloco OH 8 waves. Se não responder, verificar logs: `journalctl --user -u openclaw-gateway@bevox-mobile.service --since '5m ago' --no-pager | tail -20`.

- [ ] **Step 4: Nenhum commit (runtime NÃO git).**

---

## Phase 4 — Pilot 2: bot-financeiro

### Task 4.1: Bernard cria bot + grupo Telegram

**Files:** (ação externa Bernard)

- [ ] **Step 1: @BotFather → /newbot**

No Telegram:
1. Abrir `@BotFather`
2. `/newbot`
3. Nome display: `Bevox Finance Bot`
4. Username: `<FinanceBot>` (ou variação)
5. Guardar o TOKEN

- [ ] **Step 2: Criar grupo Telegram**

1. Criar grupo novo "bevox — financeiro"
2. Add bot como member + admin
3. Pegar CHAT_ID (mesmo método Task 3.1)

- [ ] **Step 3: Guardar TOKEN + CHAT_ID pra Task 4.3**

### Task 4.2: Run bootstrap script

**Files:** (script execution)

- [ ] **Step 1: Bootstrap `financeiro` profile (greenfield)**

```bash
~/.openclaw/scripts/bootstrap-telegram-agent.sh financeiro 18791 2>&1 | tail -20
```

Expected: `✓ Bootstrap financeiro complete (port 18791)` + checklist impresso.

- [ ] **Step 2: Verify greenfield profile criado**

```bash
ls ~/.openclaw-financeiro/
ls ~/.openclaw-financeiro/workspace/memory/
```

Expected: profile completo + workspace memory com placeholders.

### Task 4.3: Edit `openclaw.json` com TOKEN + CHAT_ID (plugins = core only)

**Files:**
- Modify: `~/.openclaw-financeiro/openclaw.json`

- [ ] **Step 1: Setup token + chat_ids**

```bash
BERNARD_UID=$(python3 -c "import json; c=json.load(open('~/.openclaw/openclaw.json')); print(c['channels']['telegram']['allowFrom'][0])")

python3 - <<PYEOF
import json
p = "~/.openclaw-financeiro/openclaw.json"
c = json.load(open(p))
BERNARD_UID = "$BERNARD_UID"
CHAT_ID = "<POPULATE_CHAT_ID_FINANCEIRO_REAL>"  # Substituir pelo CHAT_ID real
c["channels"]["telegram"]["allowFrom"] = [BERNARD_UID]
c["channels"]["telegram"]["groups"] = {CHAT_ID: {"requireMention": False}}
c["channels"]["telegram"]["botToken"] = "<TOKEN-REAL-BEVOX-FINANCE>"  # substitui
json.dump(c, open(p, "w"), indent=2)
PYEOF
```

Expected: arquivo salvo com valores reais populados (allowFrom + groups + botToken).

Note: plugins.allow fica em `['knowledge-sync-commands']` apenas — finance-commands é futuro.

### Task 4.4: Popular `area_context.md` com finance domain

**Files:**
- Modify: `~/.openclaw-financeiro/workspace/memory/area_context.md`

- [ ] **Step 1: Overwrite com contexto finance**

```bash
cat > ~/.openclaw-financeiro/workspace/memory/area_context.md <<'EOF'
# Contexto financeiro

## Vocabulário de domínio

- MRR (Monthly Recurring Revenue), ARR (Annual Recurring Revenue)
- CAC (Customer Acquisition Cost), LTV (Lifetime Value)
- Runway (caixa disponível / burn rate mensal)
- Burn rate (gastos mensais)
- Churn rate (% clientes que saem por período)
- Conversion rate (% leads que viram customers)

## Tools & platforms

- **YNAB** (You Need A Budget) — ferramenta primária de tracking financeiro pessoal + empresarial
- `~/.openclaw/finance/runway.yml` — snapshot gerado pelo finance-snapshot timer (OpenClaw)
- `~/.openclaw/finance/override.yml` — host-local overrides (valores reais, não committados; ADR-007)
- Mission Control page `/finance` — projeção runway UI

## Referencias canônicas

- E11 epic: `bevox-knowledge/40_roadmap/delivery-tracker.yml` §E11
- Spec runway wave-1: `bevox-knowledge/35_specs/2026-04-14-e11-finance-runway-wave-1.md`
- Spec receitas/despesas F1: `bevox-knowledge/35_specs/2026-04-17-e11-f1-receitas-despesas.md`
- ADR sensitive data: `bevox-knowledge/30_adr/ADR-007-*.md`

## Comportamento default

- Formato runway: "X meses @ burn atual Y/mês" (contexto, não apenas número bruto).
- Links canônicos sempre que referenciar decisão ou spec.
- Valores reais vivem em override local (não committar em bevox-knowledge nem mencionar em logs públicos).
- Não prometer executar transferência/pagamento sem approval explícito.

## Comportamento crítico

- Runway < 6 meses → flag como urgent.
- Burn rate mudança > 20% mês-a-mês → flag pra review.
- Nunca inventar números. Se dado não está em snapshot ou spec, dizer "não tenho este dado; preciso popular em override local".
EOF
wc -l ~/.openclaw-financeiro/workspace/memory/area_context.md
```

Expected: ~35-40 linhas.

### Task 4.5: systemctl enable + smoke

**Files:** (runtime activation)

- [ ] **Step 1: Enable + start**

```bash
systemctl --user enable --now openclaw-gateway@financeiro.service
sleep 3
systemctl --user is-active openclaw-gateway@financeiro.service
systemctl --user status openclaw-gateway@financeiro.service --no-pager 2>&1 | head -15
```

Expected: `active (running)`.

- [ ] **Step 2: Verify todos 3 gateways ativos em paralelo**

```bash
systemctl --user list-units 'openclaw-gateway*' --no-pager
```

Expected:
- `openclaw-gateway.service` (Vox) — active
- `openclaw-gateway@bevox-mobile.service` — active
- `openclaw-gateway@financeiro.service` — active

- [ ] **Step 3: Smoke greenfield**

Enviar no grupo "bevox — financeiro":
> @<finance_bot> qual nossa runway atual?

Expected: bot consulta area_context.md (referencia `~/.openclaw/finance/runway.yml`) + opcionalmente navega bevox-knowledge E11 spec + responde com runway em formato "X meses @ burn Y/mês" OU diz "dado não populado em override local" se snapshot vazio.

- [ ] **Step 4: Nenhum commit.**

---

## Phase 5 — Validação + closure

### Task 5.1: Validate PASS criteria (§10 do spec)

**Files:** (verificação runtime)

- [ ] **Step 1: PASS criteria 1 — Vox intacto**

```bash
systemctl --user is-active openclaw-gateway.service
# Smoke Vox (original grupo Telegram)
echo "Bernard: manda '/clr_pending' no grupo Vox original → verifica resposta correta"
```

Expected: Vox gateway active + /clr_pending responde.

- [ ] **Step 2: PASS criteria 2 — bot-bevox-mobile ativo**

Já validado em Task 3.5 Step 3. Confirmar que persiste:

```bash
systemctl --user is-active openclaw-gateway@bevox-mobile.service
```

Expected: active.

- [ ] **Step 3: PASS criteria 3 — bot-financeiro ativo**

Já validado em Task 4.5 Step 3. Confirmar que persiste:

```bash
systemctl --user is-active openclaw-gateway@financeiro.service
```

Expected: active.

- [ ] **Step 4: PASS criteria 4 — bootstrap script idempotent**

Re-run script com mesmos args:

```bash
~/.openclaw/scripts/bootstrap-telegram-agent.sh bevox-mobile 18790 2>&1 | tail -5
# Verify area_context.md NÃO foi sobrescrito (tem conteúdo real)
head -3 ~/.openclaw-bevox-mobile/workspace/memory/area_context.md
```

Expected: "Bootstrap complete" sem erro; area_context.md começa com "# Contexto bevox-mobile" (não placeholder).

- [ ] **Step 5: PASS criteria 5 — Plugin scoping enforced**

Enviar no grupo bevox-mobile: `/clr_` (incomplete) → verificar se bot autocompleta com /clr_* commands.
Enviar no grupo financeiro: `/clr_` → verificar se bot NÃO mostra /clr_* (plugin não carregado).

Expected:
- bevox-mobile: sugestões incluem `/clr_pending`, `/clr_show`, etc
- financeiro: sem /clr_*. Apenas /knowledge_* se `knowledge-sync-commands` expõe comandos.

- [ ] **Step 6: PASS criteria 7 — Zero toque em OH waves runtime**

```bash
# OH runtime ainda funciona (re-executa smoke wave-7 subset)
systemctl --user list-timers 'openclaw-*' --no-pager | head -10
tail -5 ~/.openclaw/clarification-agent/poll.jsonl
tail -5 ~/.openclaw/kanban-tasks/events.jsonl
```

Expected: timers ativos (cron-dispatcher, reaper, clarification-daemon, clarification-notifier); logs recentes sem erros.

### Task 5.2: Criar cross-ref em `20_architecture/agents/`

**Files:**
- Create: `bevox-knowledge/20_architecture/agents/telegram-bot-agent-pattern.md`

- [ ] **Step 1: Verify branch state**

```bash
cd ~/bevox-knowledge && git branch --show-current
```

Expected: `draft/e10-multi-bot-telegram`.

- [ ] **Step 2: Create cross-ref doc**

```bash
mkdir -p ~/bevox-knowledge/20_architecture/agents
cat > ~/bevox-knowledge/20_architecture/agents/telegram-bot-agent-pattern.md <<'EOF'
# Telegram bot agent pattern (cross-ref)

**Spec canônica:** [35_specs/2026-04-22-e10-telegram-multi-bot.md](../../35_specs/2026-04-22-e10-telegram-multi-bot.md)

## Pattern em 10 linhas

Cada área da empresa tem seu próprio Telegram bot + grupo + profile openclaw isolado:

1. **1 bot Telegram por área** (financeiro, marketing, bevox-mobile, bevox-backend, etc)
2. **1 profile openclaw** por bot: `~/.openclaw-<area>/` (via `openclaw --profile <area>`)
3. **1 systemd instance** por bot: `openclaw-gateway@<area>.service` (template unit)
4. **1 env file** por bot: `~/.openclaw/gateway/bots/<area>.env` (port + boot vars)
5. **Workspace isolado:** `~/.openclaw-<area>/workspace/memory/` por profile
6. **Shared core via absolute symlinks:** user_profile + feedback_universal + reference_bevox_knowledge → `~/.openclaw/workspace-shared/memory/`
7. **Area context file:** `~/.openclaw-<area>/workspace/memory/area_context.md` complementa Vox base
8. **Plugins per profile:** declarados em `~/.openclaw-<area>/openclaw.json` `plugins.allow`
9. **Vox legacy (default profile):** permanece intacto em `openclaw-gateway.service` + `~/.openclaw/`
10. **Criar novo bot:** `~/.openclaw/scripts/bootstrap-telegram-agent.sh <area> <port>` (10-15min total)

## Criar novo bot (quick reference)

```bash
~/.openclaw/scripts/bootstrap-telegram-agent.sh <area> <port>
# Seguir checklist impresso pelo script (7 passos ~15min)
```

Detalhes completos: spec canônica.
EOF
ls -la ~/bevox-knowledge/20_architecture/agents/
```

Expected: arquivo criado.

### Task 5.3: Release note + tracker + roadmap update

**Files:**
- Create: `bevox-knowledge/50_releases/2026-04-22-e10-multi-bot-telegram-delivered.md`
- Modify: `bevox-knowledge/40_roadmap/delivery-tracker.yml`
- Modify: `bevox-knowledge/40_roadmap/2026-04-09-openclaw-company-os-roadmap.md`
- Modify: `bevox-knowledge/35_specs/2026-04-22-e10-telegram-multi-bot.md` (status delivered)

- [ ] **Step 1: Release note**

```bash
cat > ~/bevox-knowledge/50_releases/2026-04-22-e10-multi-bot-telegram-delivered.md <<'EOF'
# Release — E10 Multi-bot Telegram (Epico B retomada) delivered (2026-04-22)

**Wave:** E10 multi-bot-telegram
**Spec:** `35_specs/2026-04-22-e10-telegram-multi-bot.md` (commit 775f4c4)
**Branch draft:** `draft/e10-multi-bot-telegram`

## Entregue

Infra multi-bot Telegram habilitada via `openclaw --profile <area>` built-in. Zero modificação em código externo (openclaw npm package) ou knowledge-sync plugins repo. Tudo é filesystem + systemd + config.

### 2 pilots em produção

- **bot-bevox-mobile** (`openclaw-gateway@bevox-mobile.service`, port 18790, profile `~/.openclaw-bevox-mobile/`) — reuse de contexto histórico bevox-mobile; plugins: knowledge-sync-commands + clarification-commands.
- **bot-financeiro** (`openclaw-gateway@financeiro.service`, port 18791, profile `~/.openclaw-financeiro/`, greenfield) — plugins: knowledge-sync-commands only (finance-commands futuro).

### Infraestrutura

- `~/.openclaw/workspace-shared/memory/` — shared core cross-profile (user_profile + feedback_universal + reference_bevox_knowledge + MEMORY.md)
- `~/.config/systemd/user/openclaw-gateway@.service` — systemd template unit
- `~/.openclaw/scripts/bootstrap-telegram-agent.sh` — bootstrap script canônico (idempotent, ~15min por bot novo)
- `~/.openclaw/gateway/bots/*.env` — port config por bot

### Vox intacto

`openclaw-gateway.service` (default profile `~/.openclaw/`) permanece LIVE sem mudanças. Zero downtime.

## Pattern pra novos bots

```bash
~/.openclaw/scripts/bootstrap-telegram-agent.sh <area> <port>
# Segue checklist: BotFather → grupo Telegram → edit openclaw.json → enable systemd
```

Cross-ref: `20_architecture/agents/telegram-bot-agent-pattern.md`.

## Follow-ups registrados

- Rollout bots adicionais (marketing, bevox-backend, CRM, suporte) — trabalho operacional via script.
- Mission Control UI `/bots` page — wave futura se 4+ bots virarem dor de gestão.
- Per-bot analytics + recovery alerts — futuras.
EOF
```

Expected: arquivo criado.

- [ ] **Step 2: Tracker entry**

Edit `40_roadmap/delivery-tracker.yml` adicionando entry em E10.waves, depois de `oh-closure`:

```bash
python3 - <<'PYEOF'
# Leitura + append manual (sem yaml module). Adiciona linha antes de finance-agent
p = "~/bevox-knowledge/40_roadmap/delivery-tracker.yml"
content = open(p).read()

entry = """      - id: multi-bot-telegram
        status: delivered
        delivered_at: 2026-04-22
        spec: 35_specs/2026-04-22-e10-telegram-multi-bot.md
        narrative: "Epico B retomada — 1 bot Telegram por area via openclaw --profile"
        features:
          - "Infra multi-bot via openclaw --profile <area> built-in (zero mod gateway source)"
          - "2 pilot bots: bevox-mobile + financeiro em systemd instances openclaw-gateway@<area>.service"
          - "Shared core workspace-shared/memory/ + absolute symlinks nos profiles"
          - "Bootstrap script idempotent ~/.openclaw/scripts/bootstrap-telegram-agent.sh (15min por bot novo)"
          - "Plugin scoping via plugins.allow em openclaw.json do profile (native mechanism)"
          - "Vox (openclaw-gateway.service) intacto — zero touch runtime LIVE"
"""

# Insere antes de '- id: finance-agent'
marker = "      - id: finance-agent"
idx = content.find(marker)
if idx < 0:
    raise SystemExit("marker finance-agent not found")
new = content[:idx] + entry + content[idx:]
open(p, "w").write(new)
print("inserted multi-bot-telegram entry")
PYEOF
grep -A 2 'multi-bot-telegram' ~/bevox-knowledge/40_roadmap/delivery-tracker.yml | head -5
```

Expected: entry inserted, grep retorna match.

- [ ] **Step 3: Roadmap narrative**

Add linha em E10 status (`40_roadmap/2026-04-09-openclaw-company-os-roadmap.md` section §E10):

```bash
python3 - <<'PYEOF'
p = "~/bevox-knowledge/40_roadmap/2026-04-09-openclaw-company-os-roadmap.md"
content = open(p).read()
# Localiza a linha do OH CLOSED (adicionada pela wave anterior)
marker = "Finance Agent parked"
addition = "**Multi-bot Telegram entregue 2026-04-22** (retomada Epico B, `35_specs/2026-04-22-e10-telegram-multi-bot.md`): 2 pilot bots (bot-bevox-mobile + bot-financeiro) via `openclaw --profile <area>` built-in; bootstrap script canônico habilita N bots adicionais em 15min operacional; release `50_releases/2026-04-22-e10-multi-bot-telegram-delivered.md`. "
idx = content.find(marker)
if idx < 0:
    raise SystemExit("marker 'Finance Agent parked' not found")
new = content[:idx] + addition + content[idx:]
open(p, "w").write(new)
print("roadmap narrative updated")
PYEOF
grep 'Multi-bot Telegram entregue' ~/bevox-knowledge/40_roadmap/2026-04-09-openclaw-company-os-roadmap.md | head -1
```

Expected: grep match.

- [ ] **Step 4: Update spec status draft → delivered**

```bash
sed -i 's/\*\*Status:\*\* draft → em execução (2026-04-22)/**Status:** delivered (2026-04-22)/' ~/bevox-knowledge/35_specs/2026-04-22-e10-telegram-multi-bot.md
grep -E '^\*\*Status:' ~/bevox-knowledge/35_specs/2026-04-22-e10-telegram-multi-bot.md
```

Expected: `**Status:** delivered (2026-04-22)`.

### Task 5.4: Commit closure em draft branch

**Files:** (git)

- [ ] **Step 1: Git add + commit**

```bash
cd ~/bevox-knowledge
git status -s
git add 50_releases/2026-04-22-e10-multi-bot-telegram-delivered.md \
        40_roadmap/delivery-tracker.yml \
        40_roadmap/2026-04-09-openclaw-company-os-roadmap.md \
        35_specs/2026-04-22-e10-telegram-multi-bot.md \
        20_architecture/agents/telegram-bot-agent-pattern.md
git commit -m "$(cat <<'EOF'
delivery(E10): multi-bot Telegram delivered (Epico B retomada)

2 pilot bots entregues (bevox-mobile + financeiro) via openclaw
--profile built-in. Zero modificação em código externo. Bootstrap
script canônico habilita bots adicionais em 15min operacional.

Artefatos:
- 50_releases/2026-04-22-e10-multi-bot-telegram-delivered.md (NEW)
- 20_architecture/agents/telegram-bot-agent-pattern.md (NEW cross-ref)
- 40_roadmap/delivery-tracker.yml: +multi-bot-telegram entry em E10
- 40_roadmap narrative: E10 status atualizado
- 35_specs/2026-04-22-e10-telegram-multi-bot.md: draft → delivered

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git log --oneline -3
```

Expected: commit criado.

### Task 5.5: Push condicional (Bernard go-ahead explícito)

**Files:** (git push — CLAUDE.md §8 sensitive)

- [ ] **Step 1: Bernard confirma push autorizado**

Antes de push, Bernard precisa confirmar explicitamente. Claude NÃO push sem OK verbal.

- [ ] **Step 2: Merge draft → main + push**

```bash
cd ~/bevox-knowledge
git checkout main
git pull --ff-only origin main
git merge --no-ff draft/e10-multi-bot-telegram -m "merge(E10): multi-bot Telegram (Epico B retomada)"
git log --oneline -5
git push origin main
```

Expected: fast-forward merge + push successful.

- [ ] **Step 3: Verify remote**

```bash
git fetch origin
git log --oneline origin/main | head -3
```

Expected: merge commit no topo.

---

## Rollback procedures

**Full rollback (runtime):**

```bash
# Disable + remove pilot gateways
systemctl --user disable --now openclaw-gateway@bevox-mobile.service 2>/dev/null
systemctl --user disable --now openclaw-gateway@financeiro.service 2>/dev/null

# Remove template unit
rm -f ~/.config/systemd/user/openclaw-gateway@.service
systemctl --user daemon-reload

# Remove infra dirs (profiles + shared + scripts + env files)
rm -rf ~/.openclaw-bevox-mobile/ ~/.openclaw-financeiro/
rm -rf ~/.openclaw/workspace-shared/
rm -rf ~/.openclaw/gateway/ ~/.openclaw/scripts/bootstrap-telegram-agent.sh

echo "✓ Multi-bot rollback complete."
echo "  Vox (openclaw-gateway.service) continua intacto."
systemctl --user is-active openclaw-gateway.service
```

**Rollback git (se commit draft ou merge main foi feito mas quer reverter):**

```bash
cd ~/bevox-knowledge
# Se NÃO pushou ainda:
git reset --hard <commit-antes-do-merge>

# Se pushou: NÃO force push. Cria commit de revert:
git revert <merge-commit-sha>
git push origin main
```

---

## Self-review checklist (antes de executar)

- [ ] Cada Phase tem entregável independente testável
- [ ] Phase 0 Task 0.1 Step 2 (`--profile` trial run) é safe — cria dir em /tmp mentalmente OU não cria (verificado: apenas erros sem criar dir, 5s timeout)
- [ ] Bootstrap script tem validations (regex area, reject 'dev', port int)
- [ ] Script é idempotent (Task 2.2 Step 3 testa)
- [ ] Vox NUNCA é tocado (zero risco pro runtime OH LIVE)
- [ ] PASS criteria §10 tem 7 items; Task 5.1 cobre todos
- [ ] Rollback documented; Vox sempre preservado

---

## Model selection (subagent-driven-development)

| Task | Complexity | Recommended model |
|---|---|---|
| Task 0.1 | trivial (3 shell commands) | haiku |
| Task 1.1 | mechanical (mkdir + cat files) | haiku |
| Task 1.2 | mechanical (cat + systemctl reload) | haiku |
| Task 1.3 | mechanical | haiku |
| Task 2.1 | mechanical (write script) | haiku |
| Task 2.2 | integration (test script idempotent) | opus (verify logic) |
| Task 3.1 + 4.1 | ação externa Bernard | N/A (inline) |
| Task 3.2-3.5 | integration (setup + smoke) | opus (json parsing + systemctl) |
| Task 4.2-4.5 | integration (greenfield setup) | opus |
| Task 5.1 | validation (PASS criteria) | opus (judgement) |
| Task 5.2 | mechanical (markdown) | haiku |
| Task 5.3 | integration (tracker + roadmap + release note) | opus (context-aware edits) |
| Task 5.4 | mechanical (git commit) | inline Claude (sensitive) |
| Task 5.5 | sensitive (git push) | inline Claude (Bernard go-ahead) |
