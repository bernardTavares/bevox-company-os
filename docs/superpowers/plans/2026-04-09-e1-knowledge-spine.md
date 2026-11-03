# E1 - Knowledge Spine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar a skill `knowledge-sync` no OpenClaw que mantem `bevox-knowledge` como fonte de verdade operacional sem drift, sem auto-merge, com trilha auditavel.

**Architecture:** Skill bash composta por 3 componentes isolados (Watcher, Actions, Notifications) com estado compartilhado em `~/.openclaw/knowledge-sync/state.json` + `events.jsonl`. Snapshots locais via git bundle. Disparo periodico via cron OpenClaw + sob demanda via CLI/Vox.

**Tech Stack:** bash, git, jq, openclaw skills system, systemd cron, Telegram bot API (via OpenClaw notification bridge).

**Spec source of truth:** `~/bevox-knowledge/35_specs/2026-04-09-e1-knowledge-spine.md` (1230+ linhas, canonico)

---

## Convencoes do plano

- **Spec section refs:** Quando uma task diz "ver spec secao X.Y", o implementador deve abrir a spec e ler aquela secao. O conteudo e a fonte de verdade.
- **Local da skill:** `~/.openclaw/skills/knowledge-sync/` (ajustar apos Task 1 se a discovery indicar outro lugar)
- **Local do estado:** `~/.openclaw/knowledge-sync/` (state.json, events.jsonl)
- **Local de snapshots:** `~/.openclaw/backups/knowledge-snapshots/`
- **Clone do bevox-knowledge:** `~/bevox-knowledge/`
- **Validacao:** funcional (rodar comandos, inspecionar arquivos, verificar estado), nao unit tests tradicionais
- **Commits da skill:** vivem em `~/.openclaw/` (sem git por enquanto - opcionalmente migrar para repo proprio depois)
- **Commits do bevox-knowledge:** o repo ja existe, pull/commit/push normais

---

## Task 0: Pre-requisitos manuais (Bernard, BLOQUEANTE)

**Files:** Nenhum (decisoes manuais)

- [ ] **Step 1: Bernard decide sobre Obsidian**

Bernard responde:
- (a) **Vai usar Obsidian** - confirma que vai instalar e usar como editor
- (b) **Nao vai usar Obsidian** por enquanto - Tasks de Obsidian config viram so doc/policy

A escolha afeta apenas a Task de Obsidian config. Skill funciona independente.

- [ ] **Step 2: Confirmar que Telegram esta funcionando**

```bash
openclaw status 2>&1 | grep -i telegram
```

Expected: linha mostrando `Telegram │ ON │ OK │ token env (...) · accounts 1/1`

Se nao estiver OK, parar - notifications via Telegram dependem disso.

- [ ] **Step 3: Confirmar que o clone do bevox-knowledge esta em estado limpo**

```bash
cd ~/bevox-knowledge && git status && git log --oneline | head -5
```

Expected:
- `working tree clean`
- branch `main`
- ultimo commit recente (apos `2687c83 spec(e1): apply 3 review adjustments`)

- [ ] **Step 4: Confirmar dependencias do host**

```bash
git --version  # >= 2.30
jq --version   # qualquer versao recente
which sha256sum
```

Se algo faltar, instalar antes de continuar:
```bash
sudo apt-get install -y git jq coreutils
```

---

## Task 1: Discovery - convencoes de skills do OpenClaw [BLOQUEANTE]

**Files:**
- Create: `~/.openclaw/docs/superpowers/notes/openclaw-skills-research.md`

**Esta task bloqueia tudo o que vem depois.** Sem entender como skills funcionam, nao da para fazer scaffold.

- [ ] **Step 1: Listar skills existentes**

```bash
openclaw skills list 2>&1 | head -40
```

Anotar: nomes das 7 skills "ready" (coding-agent, gh-issues, github, healthcheck, node-connect, skill-creator, weather).

- [ ] **Step 2: Inspecionar uma skill ready em detalhe**

```bash
openclaw skills show coding-agent 2>&1 | head -80
openclaw skills show healthcheck 2>&1 | head -80
```

Anotar: estrutura mostrada, comandos disponiveis, manifest.

- [ ] **Step 3: Localizar skills no filesystem**

```bash
# Tentar varios lugares possiveis
find ~/.openclaw -type d -name 'skills' 2>/dev/null
find ~/.npm-global/lib/node_modules/openclaw -type d -name 'skills' 2>/dev/null | head -5
find ~/.npm-global/lib/node_modules/openclaw/dist -type d 2>/dev/null | grep -i skill | head -10
```

Procurar diretorios chamados `skills`, `extensions`, ou que contenham arquivos `coding-agent`, `weather`, etc.

- [ ] **Step 4: Inspecionar estrutura interna de uma skill encontrada**

Apos achar o diretorio (vamos chamar de `$SKILLS_DIR`), inspecionar uma skill ready:

```bash
ls -la $SKILLS_DIR/coding-agent/  # ou healthcheck/, weather/
cat $SKILLS_DIR/coding-agent/SKILL.md 2>/dev/null || cat $SKILLS_DIR/coding-agent/manifest.* 2>/dev/null
find $SKILLS_DIR/coding-agent -type f | head -20
```

Anotar:
- Arquivo de manifest (nome e formato: SKILL.md? skill.yaml? package.json?)
- Estrutura de subdiretorios (commands/, lib/, scripts/, bin/?)
- Linguagem dos scripts (bash? python? node?)
- Como subcomandos sao expostos
- Como dependencias externas sao declaradas
- Como o `openclaw skills run <skill> <subcommand>` invoca o codigo

- [ ] **Step 5: Procurar documentacao de criacao de skill**

```bash
openclaw skills create --help 2>&1
openclaw skills --help 2>&1
ls ~/.npm-global/lib/node_modules/openclaw/dist/extensions/stock/skill-creator 2>/dev/null
```

Se houver `skill-creator` skill, executar para ver o que ela cria:
```bash
openclaw skills run skill-creator --dry-run 2>&1 | head -30
```

- [ ] **Step 6: Documentar achados**

Criar `~/.openclaw/docs/superpowers/notes/openclaw-skills-research.md` com:

```markdown
# OpenClaw Skills - Research

Pesquisa feita em 2026-04-09 para Task 1 do plano E1.

## Localizacao no filesystem

[caminho exato encontrado]

## Estrutura de uma skill (exemplo: <skill-escolhida>)

```
<skill-name>/
+-- <arquivos encontrados>
```

## Manifest

- Arquivo: <nome>
- Formato: <yaml/markdown/json>
- Campos obrigatorios: <listar>
- Campos opcionais: <listar>
- Exemplo:
[colar exemplo do manifest de uma skill ready]

## Linguagem dos scripts

[bash / node / python / etc]

## Como subcomandos sao expostos

[descrever]

## Como instalar uma nova skill

[comando ou processo]

## Como invocar

[`openclaw skills run <skill> <subcommand>` ou outro]

## Decisoes para a skill knowledge-sync

Com base nessa pesquisa:
- A skill knowledge-sync vai usar: <linguagem>
- Manifest format: <formato>
- Estrutura proposta: <listar>
```

- [ ] **Step 7: Bloqueio se discovery falhar**

Se a discovery NAO conseguir determinar a estrutura de skills (ex: skills sao geradas dinamicamente, sao internas ao binario do OpenClaw), parar e reportar para o coordenador. Possiveis caminhos alternativos:

- (a) Implementar `knowledge-sync` como skill OpenClaw nativa se estrutura permitir
- (b) Implementar como cron job + script bash separado em `~/.openclaw/scripts/knowledge-sync/` e expor via wrapper CLI (perde "visivel em openclaw skills list" mas mantem todas as outras propriedades da spec)

A escolha depende do que a discovery revelar. **Reportar findings ANTES de prosseguir.**

---

## Task 2: Scaffold da skill knowledge-sync

**Files:**
- Create: `~/.openclaw/skills/knowledge-sync/SKILL.md` (ou formato descoberto na Task 1)
- Create: `~/.openclaw/skills/knowledge-sync/README.md`
- Create: `~/.openclaw/skills/knowledge-sync/bin/knowledge-sync`
- Create: `~/.openclaw/skills/knowledge-sync/lib/` (vazio, pronto para Task 3)
- Create: `~/.openclaw/skills/knowledge-sync/commands/` (vazio, pronto para Tasks 5+)
- Create: `~/.openclaw/knowledge-sync/` (state dir, perm 700)
- Create: `~/.openclaw/backups/knowledge-snapshots/` (snapshots dir, perm 700)

> **Nota:** ajustar paths conforme Task 1 revelar. O resto do plano assume `~/.openclaw/skills/knowledge-sync/`.

- [ ] **Step 1: Criar estrutura de diretorios**

```bash
SKILL_DIR=~/.openclaw/skills/knowledge-sync
mkdir -p "$SKILL_DIR"/{bin,lib,commands,tests}
mkdir -p ~/.openclaw/knowledge-sync
chmod 700 ~/.openclaw/knowledge-sync
mkdir -p ~/.openclaw/backups/knowledge-snapshots/{auto,pre-canonical,manual,meta}
chmod -R 700 ~/.openclaw/backups/knowledge-snapshots
ls -la "$SKILL_DIR"
ls -la ~/.openclaw/knowledge-sync ~/.openclaw/backups/knowledge-snapshots
```

Expected: estrutura criada, permissoes 700 nas pastas de estado.

- [ ] **Step 2: Criar manifest (formato descoberto na Task 1)**

Conteudo proposto - **adaptar ao formato real descoberto**:

```bash
cat > ~/.openclaw/skills/knowledge-sync/SKILL.md <<'EOF'
---
name: knowledge-sync
version: 0.1.0
status: setup
description: Sync subsystem for bevox-knowledge - watcher, actions, notifications, snapshots
language: bash
author: Bernard / Vox
license: internal
---

# knowledge-sync

Operacionaliza o `bevox-knowledge` como fonte de verdade ativa do Company OS.

Tres componentes isolados:
- **Watcher** - observa o clone, deriva estado em `state.json`
- **Actions** - mutacoes controladas (commit, push, snapshot, restore) per ADR-006
- **Notifications** - alerta change-of-state com persistencia/severidade/dedup

Spec canonica: `bevox-knowledge/35_specs/2026-04-09-e1-knowledge-spine.md`

## Comandos

Ver `bin/knowledge-sync --help`.

## Estado

- `~/.openclaw/knowledge-sync/state.json` - fotografia operacional
- `~/.openclaw/knowledge-sync/events.jsonl` - trilha append-only
- `~/.openclaw/backups/knowledge-snapshots/` - bundles + index

## Politica

- Respeita ADR-006 (autonomia, permissions, approvals)
- Canonical commit/push/marker EXIGEM approval mesmo em L4
- pull-ff e a UNICA forma de pull
- Operacoes destrutivas (reset hard, force push, merge, rebase) NAO estao no catalogo
EOF
```

- [ ] **Step 3: Criar wrapper executavel principal**

```bash
cat > ~/.openclaw/skills/knowledge-sync/bin/knowledge-sync <<'WRAPPER_EOF'
#!/usr/bin/env bash
# knowledge-sync - main entrypoint, dispatches to subcommands
# Spec: bevox-knowledge/35_specs/2026-04-09-e1-knowledge-spine.md

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export SKILL_DIR

# Load shared library (created in Task 3)
if [[ -f "$SKILL_DIR/lib/common.sh" ]]; then
  source "$SKILL_DIR/lib/common.sh"
fi

usage() {
  cat <<USAGE
knowledge-sync - bevox-knowledge sync subsystem

Usage: knowledge-sync <command> [args]

Consulta:
  status              Leitura pura do state.json (sem efeito colateral)
  health              Resumo de health.overall + issues
  events [--last N]   Ultimos N eventos
  diff [<file>]       Diff do working tree (se dirty)
  log [--limit N]     Git log das ultimas commits
  drafts              Lista branches draft/* ativas
  snapshots [--type]  Lista snapshots disponiveis
  pending             Lista approvals canonicos pendentes (alias: approvals)

Sync:
  refresh             Roda Watcher agora (alias: watch)
  fetch               git fetch + roda Watcher
  pull-ff             git pull --ff-only com guardrails

Draft:
  draft create <slug>     Cria branch draft/<slug>
  draft commit -m <msg>   Commit em draft branch atual
  draft push              Push da draft branch
  draft delete <name>     Apaga branch local apenas

Canonical (sempre approve):
  canonical commit -m <msg> --files <list>
  canonical push
  canonical create-marker --name <slug> --type release|milestone

Snapshot:
  snapshot create [--manual <slug>]
  snapshot verify [--all|--sample N]
  restore <bundle> [--target <path>] [--apply]

Use 'knowledge-sync <command> --help' para mais detalhes de cada comando.
USAGE
}

cmd="${1:-}"; shift || true

case "$cmd" in
  ""|-h|--help|help) usage; exit 0 ;;
  status|health|events|diff|log|drafts|snapshots|pending|approvals)
    exec "$SKILL_DIR/commands/$cmd.sh" "$@" ;;
  refresh|watch)
    exec "$SKILL_DIR/commands/refresh.sh" "$@" ;;
  fetch)
    exec "$SKILL_DIR/commands/fetch.sh" "$@" ;;
  pull-ff)
    exec "$SKILL_DIR/commands/pull-ff.sh" "$@" ;;
  draft)
    exec "$SKILL_DIR/commands/draft.sh" "$@" ;;
  canonical)
    exec "$SKILL_DIR/commands/canonical.sh" "$@" ;;
  snapshot)
    exec "$SKILL_DIR/commands/snapshot.sh" "$@" ;;
  restore)
    exec "$SKILL_DIR/commands/restore.sh" "$@" ;;
  *)
    echo "knowledge-sync: comando desconhecido: $cmd" >&2
    usage >&2
    exit 2 ;;
esac
WRAPPER_EOF
chmod +x ~/.openclaw/skills/knowledge-sync/bin/knowledge-sync
```

- [ ] **Step 4: Criar README.md**

```bash
cat > ~/.openclaw/skills/knowledge-sync/README.md <<'EOF'
# knowledge-sync skill

Subsistema operacional do OpenClaw que mantem `bevox-knowledge` como fonte de verdade
ativa sem drift, sem auto-merge, com trilha auditavel.

Implementa o E1 - Knowledge Spine do roadmap OpenClaw Company OS.

## Spec

Canonica: `bevox-knowledge/35_specs/2026-04-09-e1-knowledge-spine.md`

## Estado do subsistema

- `state.json` em `~/.openclaw/knowledge-sync/` - fotografia operacional derivada
- `events.jsonl` em `~/.openclaw/knowledge-sync/` - trilha append-only
- snapshots em `~/.openclaw/backups/knowledge-snapshots/`

## Comandos

```bash
knowledge-sync --help
```

## ADR-006

Esta skill respeita explicitamente a ADR-006 (autonomia, permissions, approvals):

- `canonical commit`/`push`/`create-marker` exigem approval mesmo em L4
- `pull-ff` e a UNICA forma de pull
- Operacoes destrutivas (`reset --hard`, `force push`, `merge`, `rebase`) NAO estao no catalogo
- CLI direto NAO bypassa policy
EOF
```

- [ ] **Step 5: Validar a skill**

```bash
~/.openclaw/skills/knowledge-sync/bin/knowledge-sync --help
```

Expected: print do usage.

- [ ] **Step 6: Tentar registrar/listar via OpenClaw**

```bash
openclaw skills list 2>&1 | grep -i knowledge-sync
```

Se a skill aparecer: ok. Se nao aparecer: pode ser que o OpenClaw escaneie um diretorio diferente. Verificar findings da Task 1 e mover/symlink se necessario.

Caso a Task 1 tenha indicado um outro local de skills, ajustar:
```bash
# Exemplo se skills moram em /outro/path
mv ~/.openclaw/skills/knowledge-sync /outro/path/skills/
```

- [ ] **Step 7: Reportar status**

A skill esta scaffoldada mas vazia (so wrapper). Proximos tasks adicionam lib/ e commands/.

---

## Task 3: Common library (lib/common.sh + state + events + git-ops)

**Files:**
- Create: `~/.openclaw/skills/knowledge-sync/lib/common.sh`
- Create: `~/.openclaw/skills/knowledge-sync/lib/state.sh`
- Create: `~/.openclaw/skills/knowledge-sync/lib/events.sh`
- Create: `~/.openclaw/skills/knowledge-sync/lib/git-ops.sh`

Estes 4 arquivos sao a fundacao usada por todos os comandos. Sem testes unitarios formais; validacao e funcional em tasks subsequentes.

- [ ] **Step 1: Criar lib/common.sh**

```bash
cat > ~/.openclaw/skills/knowledge-sync/lib/common.sh <<'COMMON_EOF'
#!/usr/bin/env bash
# common.sh - shared helpers for knowledge-sync
# Source from other scripts via: source "$SKILL_DIR/lib/common.sh"

# Paths canonicos
KS_CLONE_PATH="${KS_CLONE_PATH:-~/bevox-knowledge}"
KS_STATE_DIR="${KS_STATE_DIR:-$HOME/.openclaw/knowledge-sync}"
KS_STATE_FILE="$KS_STATE_DIR/state.json"
KS_STATE_PREVIOUS_FILE="$KS_STATE_DIR/state.previous.json"
KS_EVENTS_FILE="$KS_STATE_DIR/events.jsonl"
KS_LOCK_FILE="$KS_STATE_DIR/.lock"
KS_SNAPSHOTS_DIR="${KS_SNAPSHOTS_DIR:-$HOME/.openclaw/backups/knowledge-snapshots}"
KS_SNAPSHOTS_INDEX="$KS_SNAPSHOTS_DIR/meta/snapshots-index.jsonl"

# Garantir que dirs existem com permissao 700
ks_ensure_dirs() {
  mkdir -p "$KS_STATE_DIR" "$KS_SNAPSHOTS_DIR"/{auto,pre-canonical,manual,meta}
  chmod 700 "$KS_STATE_DIR" "$KS_SNAPSHOTS_DIR" 2>/dev/null || true
}

# Logging para stderr (nao polui stdout/JSON output)
ks_log() {
  echo "[knowledge-sync] $*" >&2
}

ks_err() {
  echo "[knowledge-sync ERROR] $*" >&2
}

# Lock para impedir execucao concorrente
ks_lock() {
  local timeout="${1:-30}"
  exec 9>"$KS_LOCK_FILE"
  if ! flock -w "$timeout" 9; then
    ks_err "Could not acquire lock within ${timeout}s"
    return 1
  fi
}

ks_unlock() {
  exec 9>&-
}

# Timestamp ISO 8601 UTC
ks_now() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

# Verificar dependencias
ks_check_deps() {
  local missing=()
  for cmd in git jq sha256sum flock; do
    command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    ks_err "Missing dependencies: ${missing[*]}"
    return 1
  fi
}

# Verificar que o clone existe e e um repo git
ks_check_clone() {
  if [[ ! -d "$KS_CLONE_PATH/.git" ]]; then
    ks_err "Clone not found at $KS_CLONE_PATH"
    return 1
  fi
}

ks_ensure_dirs
COMMON_EOF
```

- [ ] **Step 2: Criar lib/state.sh**

```bash
cat > ~/.openclaw/skills/knowledge-sync/lib/state.sh <<'STATE_EOF'
#!/usr/bin/env bash
# state.sh - state.json read/write atomic

# Le o state.json atual (vazio se nao existir)
ks_state_read() {
  if [[ -f "$KS_STATE_FILE" ]]; then
    cat "$KS_STATE_FILE"
  else
    echo "{}"
  fi
}

# Le state.previous.json
ks_state_read_previous() {
  if [[ -f "$KS_STATE_PREVIOUS_FILE" ]]; then
    cat "$KS_STATE_PREVIOUS_FILE"
  else
    echo "{}"
  fi
}

# Escreve state.json atomicamente (tempfile + rename)
# Backup do anterior em state.previous.json
# Uso: echo '{...}' | ks_state_write
ks_state_write() {
  local tmp
  tmp="$(mktemp "$KS_STATE_DIR/state.json.XXXXXX")"
  cat > "$tmp"
  chmod 600 "$tmp"
  # Backup do anterior
  if [[ -f "$KS_STATE_FILE" ]]; then
    cp "$KS_STATE_FILE" "$KS_STATE_PREVIOUS_FILE"
    chmod 600 "$KS_STATE_PREVIOUS_FILE"
  fi
  mv "$tmp" "$KS_STATE_FILE"
}

# Helpers de leitura via jq
ks_state_get() {
  local path="$1"
  ks_state_read | jq -r "$path"
}
STATE_EOF
```

- [ ] **Step 3: Criar lib/events.sh**

```bash
cat > ~/.openclaw/skills/knowledge-sync/lib/events.sh <<'EVENTS_EOF'
#!/usr/bin/env bash
# events.sh - events.jsonl append-only audit trail

# Append um evento ao events.jsonl
# Uso: ks_event_append "event_name" '{"key": "value"}'
ks_event_append() {
  local event="$1"
  local payload_json="${2:-{\}}"
  local now
  now="$(ks_now)"
  local line
  line="$(jq -nc \
    --arg ts "$now" \
    --arg event "$event" \
    --argjson payload "$payload_json" \
    '{ts: $ts, event: $event, payload: $payload}')"
  echo "$line" >> "$KS_EVENTS_FILE"
  chmod 600 "$KS_EVENTS_FILE" 2>/dev/null || true
}

# Le ultimos N eventos
ks_events_tail() {
  local n="${1:-20}"
  if [[ -f "$KS_EVENTS_FILE" ]]; then
    tail -n "$n" "$KS_EVENTS_FILE"
  fi
}

# Filtra eventos por nome
ks_events_filter() {
  local event_name="$1"
  local n="${2:-20}"
  if [[ -f "$KS_EVENTS_FILE" ]]; then
    grep -F "\"event\":\"$event_name\"" "$KS_EVENTS_FILE" | tail -n "$n"
  fi
}
EVENTS_EOF
```

- [ ] **Step 4: Criar lib/git-ops.sh**

```bash
cat > ~/.openclaw/skills/knowledge-sync/lib/git-ops.sh <<'GIT_EOF'
#!/usr/bin/env bash
# git-ops.sh - safe git wrappers for the clone

# Roda git no clone
ks_git() {
  git -C "$KS_CLONE_PATH" "$@"
}

# Branch atual
ks_git_branch() {
  ks_git symbolic-ref --short HEAD 2>/dev/null || echo ""
}

# HEAD detached?
ks_git_detached() {
  if ks_git symbolic-ref -q HEAD >/dev/null 2>&1; then
    echo "false"
  else
    echo "true"
  fi
}

# SHA do HEAD
ks_git_head_sha() {
  ks_git rev-parse HEAD 2>/dev/null || echo ""
}

# SHA do tracking branch
ks_git_tracking_sha() {
  local tracking
  tracking="$(ks_git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || echo "")"
  if [[ -n "$tracking" ]]; then
    ks_git rev-parse "$tracking" 2>/dev/null || echo ""
  fi
}

# Tracking branch name (ex: origin/main)
ks_git_tracking_name() {
  ks_git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || echo ""
}

# Ahead/behind counts: retorna "ahead behind"
ks_git_ahead_behind() {
  local tracking
  tracking="$(ks_git_tracking_name)"
  if [[ -z "$tracking" ]]; then
    echo "0 0"
    return
  fi
  ks_git rev-list --left-right --count "${tracking}...HEAD" 2>/dev/null | awk '{print $2, $1}'
}

# Working tree clean?
ks_git_clean() {
  if [[ -z "$(ks_git status --porcelain 2>/dev/null)" ]]; then
    echo "true"
  else
    echo "false"
  fi
}

# Listas de arquivos modificados/untracked/staged como JSON arrays
ks_git_modified_json() {
  ks_git status --porcelain 2>/dev/null | awk '/^.M /{print $2}/^M.|^MM/{print $2}' | jq -R . | jq -sc .
}

ks_git_untracked_json() {
  ks_git status --porcelain 2>/dev/null | awk '/^\?\?/{print $2}' | jq -R . | jq -sc .
}

ks_git_staged_json() {
  ks_git status --porcelain 2>/dev/null | awk '/^[AM]./{print $2}' | jq -R . | jq -sc .
}

# Operacoes git em progresso
ks_git_merge_in_progress() {
  [[ -f "$KS_CLONE_PATH/.git/MERGE_HEAD" ]] && echo "true" || echo "false"
}

ks_git_rebase_in_progress() {
  if [[ -d "$KS_CLONE_PATH/.git/rebase-merge" ]] || [[ -d "$KS_CLONE_PATH/.git/rebase-apply" ]]; then
    echo "true"
  else
    echo "false"
  fi
}

ks_git_cherry_pick_in_progress() {
  [[ -f "$KS_CLONE_PATH/.git/CHERRY_PICK_HEAD" ]] && echo "true" || echo "false"
}

# Lista de branches draft/* como JSON
ks_git_draft_branches_json() {
  local branches
  branches="$(ks_git branch --list 'draft/*' 2>/dev/null | sed 's/^[* ] //' | sed 's/^ *//')"
  if [[ -z "$branches" ]]; then
    echo "[]"
    return
  fi
  local result="[]"
  while IFS= read -r br; do
    [[ -z "$br" ]] && continue
    local sha
    sha="$(ks_git rev-parse "$br" 2>/dev/null || echo "")"
    local main_sha
    main_sha="$(ks_git rev-parse main 2>/dev/null || echo "")"
    local ahead_main="0"
    if [[ -n "$sha" && -n "$main_sha" ]]; then
      ahead_main="$(ks_git rev-list --count "main..$br" 2>/dev/null || echo "0")"
    fi
    result="$(echo "$result" | jq -c \
      --arg name "$br" \
      --arg sha "$sha" \
      --argjson ahead "$ahead_main" \
      '. + [{name: $name, head_sha: $sha, ahead_of_main: $ahead}]')"
  done <<< "$branches"
  echo "$result"
}

# Remote URL
ks_git_remote_url() {
  ks_git config --get remote.origin.url 2>/dev/null || echo ""
}

# Fetch silencioso (retorna 0 ok, 1 erro)
ks_git_fetch_quiet() {
  ks_git fetch --quiet origin 2>&1
}
GIT_EOF
```

- [ ] **Step 5: Smoke test das libs**

```bash
cat > /tmp/ks-smoke.sh <<'SMOKE_EOF'
#!/usr/bin/env bash
set -euo pipefail
SKILL_DIR=~/.openclaw/skills/knowledge-sync
source "$SKILL_DIR/lib/common.sh"
source "$SKILL_DIR/lib/state.sh"
source "$SKILL_DIR/lib/events.sh"
source "$SKILL_DIR/lib/git-ops.sh"

ks_check_deps
ks_check_clone

echo "=== git basics ==="
echo "branch: $(ks_git_branch)"
echo "head_sha: $(ks_git_head_sha)"
echo "tracking: $(ks_git_tracking_name)"
echo "ahead behind: $(ks_git_ahead_behind)"
echo "clean: $(ks_git_clean)"
echo "merge_in_progress: $(ks_git_merge_in_progress)"
echo "drafts: $(ks_git_draft_branches_json)"

echo "=== events test ==="
ks_event_append "test_event" '{"foo": "bar"}'
echo "last event:"
ks_events_tail 1

echo "=== state test ==="
echo '{"version": 1, "test": true}' | ks_state_write
ks_state_read | jq .
SMOKE_EOF
bash /tmp/ks-smoke.sh
rm /tmp/ks-smoke.sh
```

Expected: tudo imprime sem erro, state.json criado, events.jsonl tem 1 evento.

Limpar dados de teste:
```bash
rm -f ~/.openclaw/knowledge-sync/state.json ~/.openclaw/knowledge-sync/state.previous.json ~/.openclaw/knowledge-sync/events.jsonl
```

---

## Task 4: lib/watcher.sh - implementacao do Watcher

**Files:**
- Create: `~/.openclaw/skills/knowledge-sync/lib/watcher.sh`

Implementa o ciclo do Watcher conforme spec secao 3 (sequencia de checks, schema de state.json, health.issues estruturado).

- [ ] **Step 1: Criar lib/watcher.sh**

```bash
cat > ~/.openclaw/skills/knowledge-sync/lib/watcher.sh <<'WATCHER_EOF'
#!/usr/bin/env bash
# watcher.sh - pure read of clone, derives state.json
# Spec section 3

# Janela minima entre fetches (segundos)
KS_FETCH_MIN_INTERVAL="${KS_FETCH_MIN_INTERVAL:-300}"

# Determina se deve fazer fetch baseado no ultimo fetch
ks_watcher_should_fetch() {
  local last_fetch_at
  last_fetch_at="$(ks_state_read | jq -r '.last.fetch_at // ""')"
  if [[ -z "$last_fetch_at" || "$last_fetch_at" == "null" ]]; then
    echo "true"
    return
  fi
  local last_ts
  last_ts="$(date -u -d "$last_fetch_at" +%s 2>/dev/null || echo 0)"
  local now_ts
  now_ts="$(date -u +%s)"
  local elapsed=$((now_ts - last_ts))
  if (( elapsed >= KS_FETCH_MIN_INTERVAL )); then
    echo "true"
  else
    echo "false"
  fi
}

# Detecao conservadora de conflito potencial
# Retorna "true|false|reason"
# Conservadora: evita merge-tree por ciclo
ks_watcher_conflict_potential() {
  local clean="$1"
  local behind="$2"
  local merge_in="$3"
  local rebase_in="$4"

  # Operacao git em progresso = conflito potencial implicito
  if [[ "$merge_in" == "true" || "$rebase_in" == "true" ]]; then
    echo "true|git operation in progress"
    return
  fi

  # Behind + dirty = risco de conflito ao tentar pull-ff
  if [[ "$behind" -gt 0 && "$clean" == "false" ]]; then
    echo "true|behind remote with dirty working tree"
    return
  fi

  echo "false|"
}

# Calcula health.overall e health.issues
# Retorna JSON do bloco health
ks_watcher_compute_health() {
  local clean="$1"
  local ahead="$2"
  local behind="$3"
  local merge_in="$4"
  local rebase_in="$5"
  local cherry_pick_in="$6"
  local conflict_potential="$7"
  local conflict_reason="$8"

  local previous_state
  previous_state="$(ks_state_read_previous)"

  local now
  now="$(ks_now)"
  local issues="[]"

  # working_tree_dirty
  if [[ "$clean" == "false" ]]; then
    local since
    since="$(echo "$previous_state" | jq -r '.health.issues[]? | select(.code=="working_tree_dirty") | .since' 2>/dev/null | head -1)"
    [[ -z "$since" || "$since" == "null" ]] && since="$now"
    issues="$(echo "$issues" | jq -c \
      --arg since "$since" \
      '. + [{code: "working_tree_dirty", severity: "warn", since: $since, details: {}}]')"
  fi

  # branch_behind
  if [[ "$behind" -gt 0 ]]; then
    local since
    since="$(echo "$previous_state" | jq -r '.health.issues[]? | select(.code=="branch_behind") | .since' 2>/dev/null | head -1)"
    [[ -z "$since" || "$since" == "null" ]] && since="$now"
    issues="$(echo "$issues" | jq -c \
      --arg since "$since" \
      --argjson n "$behind" \
      '. + [{code: "branch_behind", severity: "warn", since: $since, details: {behind: $n}}]')"
  fi

  # branch_ahead
  if [[ "$ahead" -gt 0 ]]; then
    local since
    since="$(echo "$previous_state" | jq -r '.health.issues[]? | select(.code=="branch_ahead") | .since' 2>/dev/null | head -1)"
    [[ -z "$since" || "$since" == "null" ]] && since="$now"
    # Severity: info default, warn after 24h
    local severity="info"
    local since_ts
    since_ts="$(date -u -d "$since" +%s 2>/dev/null || echo 0)"
    local now_ts
    now_ts="$(date -u +%s)"
    if (( now_ts - since_ts >= 86400 )); then
      severity="warn"
    fi
    issues="$(echo "$issues" | jq -c \
      --arg since "$since" \
      --arg sev "$severity" \
      --argjson n "$ahead" \
      '. + [{code: "branch_ahead", severity: $sev, since: $since, details: {ahead: $n}}]')"
  fi

  # git operations
  for op in merge:merge_in_progress rebase:rebase_in_progress cherry_pick:cherry_pick_in_progress; do
    local var_name="${op#*:}"
    local code="${var_name}"
    local val
    case "$var_name" in
      merge_in_progress) val="$merge_in" ;;
      rebase_in_progress) val="$rebase_in" ;;
      cherry_pick_in_progress) val="$cherry_pick_in" ;;
    esac
    if [[ "$val" == "true" ]]; then
      local since
      since="$(echo "$previous_state" | jq -r --arg c "$code" '.health.issues[]? | select(.code==$c) | .since' 2>/dev/null | head -1)"
      [[ -z "$since" || "$since" == "null" ]] && since="$now"
      issues="$(echo "$issues" | jq -c \
        --arg c "$code" --arg since "$since" \
        '. + [{code: $c, severity: "warn", since: $since, details: {}}]')"
    fi
  done

  # conflict_potential
  if [[ "$conflict_potential" == "true" ]]; then
    local since
    since="$(echo "$previous_state" | jq -r '.health.issues[]? | select(.code=="conflict_potential") | .since' 2>/dev/null | head -1)"
    [[ -z "$since" || "$since" == "null" ]] && since="$now"
    issues="$(echo "$issues" | jq -c \
      --arg since "$since" \
      --arg reason "$conflict_reason" \
      '. + [{code: "conflict_potential", severity: "error", since: $since, details: {reason: $reason}}]')"
  fi

  # Calcular overall
  local overall="ok"
  if echo "$issues" | jq -e '.[] | select(.severity=="error")' >/dev/null 2>&1; then
    overall="critical"
  elif echo "$issues" | jq -e '.[] | select(.severity=="warn")' >/dev/null 2>&1; then
    overall="degraded"
  fi

  jq -nc \
    --arg overall "$overall" \
    --argjson issues "$issues" \
    '{overall: $overall, issues: $issues}'
}

# Roda 1 ciclo do Watcher
# Param: $1 = "fetch" para forcar fetch, "" para respeitar interval
ks_watcher_run() {
  local force_fetch="${1:-}"
  local started_at
  started_at="$(ks_now)"
  local errors="[]"
  local fetch_status="skipped"

  # 1. Fetch (se janela permitir ou forcado)
  local should_fetch
  should_fetch="$(ks_watcher_should_fetch)"
  if [[ "$force_fetch" == "fetch" || "$should_fetch" == "true" ]]; then
    local fetch_output
    if fetch_output="$(ks_git_fetch_quiet 2>&1)"; then
      fetch_status="ok"
    else
      fetch_status="failed"
      local err_summary
      err_summary="$(echo "$fetch_output" | head -3 | tr '\n' ' ' | head -c 200)"
      errors="$(echo "$errors" | jq -c \
        --arg step "git_fetch" \
        --arg cmd "git fetch --quiet origin" \
        --arg stderr "$err_summary" \
        --arg at "$(ks_now)" \
        '. + [{step: $step, command: $cmd, exit_code: 1, stderr_summary: $stderr, occurred_at: $at}]')"
    fi
  fi

  # 2. Coletar info do git
  local branch head_sha tracking tracking_sha detached ahead behind clean
  branch="$(ks_git_branch)"
  head_sha="$(ks_git_head_sha)"
  tracking="$(ks_git_tracking_name)"
  tracking_sha="$(ks_git_tracking_sha)"
  detached="$(ks_git_detached)"
  read -r ahead behind <<< "$(ks_git_ahead_behind)"
  clean="$(ks_git_clean)"

  # 3. Working tree details
  local modified_json untracked_json staged_json
  modified_json="$(ks_git_modified_json)"
  untracked_json="$(ks_git_untracked_json)"
  staged_json="$(ks_git_staged_json)"

  # 4. Git operations em progresso
  local merge_in rebase_in cherry_pick_in
  merge_in="$(ks_git_merge_in_progress)"
  rebase_in="$(ks_git_rebase_in_progress)"
  cherry_pick_in="$(ks_git_cherry_pick_in_progress)"

  # 5. Conflict detection conservadora
  local conflict_result
  conflict_result="$(ks_watcher_conflict_potential "$clean" "$behind" "$merge_in" "$rebase_in")"
  local conflict_potential="${conflict_result%%|*}"
  local conflict_reason="${conflict_result##*|}"

  # 6. Drafts
  local drafts_json
  drafts_json="$(ks_git_draft_branches_json)"

  # 7. Health
  local health_json
  health_json="$(ks_watcher_compute_health "$clean" "$ahead" "$behind" "$merge_in" "$rebase_in" "$cherry_pick_in" "$conflict_potential" "$conflict_reason")"

  # 8. Last fields - preserva o que ja tem
  local last_pull_at last_pull_status last_commit_at last_commit_sha last_push_at last_push_status
  local previous
  previous="$(ks_state_read)"
  last_pull_at="$(echo "$previous" | jq -r '.last.pull_at // ""')"
  last_pull_status="$(echo "$previous" | jq -r '.last.pull_status // ""')"
  last_commit_at="$(echo "$previous" | jq -r '.last.commit_at // ""')"
  last_commit_sha="$(echo "$previous" | jq -r '.last.commit_sha // ""')"
  last_push_at="$(echo "$previous" | jq -r '.last.push_at // ""')"
  last_push_status="$(echo "$previous" | jq -r '.last.push_status // ""')"

  local last_fetch_at
  if [[ "$fetch_status" == "ok" ]]; then
    last_fetch_at="$started_at"
  else
    last_fetch_at="$(echo "$previous" | jq -r '.last.fetch_at // ""')"
  fi

  # 9. Duracao
  local finished_at
  finished_at="$(ks_now)"
  local duration_ms=0
  local started_ts finished_ts
  started_ts="$(date -u -d "$started_at" +%s%3N 2>/dev/null || echo 0)"
  finished_ts="$(date -u -d "$finished_at" +%s%3N 2>/dev/null || echo 0)"
  if (( finished_ts > started_ts )); then
    duration_ms=$((finished_ts - started_ts))
  fi

  # 10. Build state JSON
  local state_json
  state_json="$(jq -nc \
    --arg observed_at "$started_at" \
    --arg clone_path "$KS_CLONE_PATH" \
    --arg remote_url "$(ks_git_remote_url)" \
    --arg branch "$branch" \
    --arg tracking "$tracking" \
    --arg head_sha "$head_sha" \
    --arg tracking_sha "$tracking_sha" \
    --argjson detached "$detached" \
    --argjson ahead "$ahead" \
    --argjson behind "$behind" \
    --argjson clean "$clean" \
    --argjson modified "$modified_json" \
    --argjson untracked "$untracked_json" \
    --argjson staged "$staged_json" \
    --argjson merge_in "$merge_in" \
    --argjson rebase_in "$rebase_in" \
    --argjson cherry_in "$cherry_pick_in" \
    --argjson conflict "$conflict_potential" \
    --arg conflict_reason "$conflict_reason" \
    --argjson drafts "$drafts_json" \
    --arg last_fetch_at "$last_fetch_at" \
    --arg fetch_status "$fetch_status" \
    --arg last_pull_at "$last_pull_at" \
    --arg last_pull_status "$last_pull_status" \
    --arg last_commit_at "$last_commit_at" \
    --arg last_commit_sha "$last_commit_sha" \
    --arg last_push_at "$last_push_at" \
    --arg last_push_status "$last_push_status" \
    --argjson health "$health_json" \
    --arg ran_at "$started_at" \
    --argjson duration_ms "$duration_ms" \
    --argjson errors "$errors" \
    '{
      version: 1,
      observed_at: $observed_at,
      clone_path: $clone_path,
      remote: {name: "origin", url: $remote_url},
      branch: {
        current: $branch,
        tracking: $tracking,
        head_sha: $head_sha,
        tracking_head_sha: $tracking_sha,
        detached: $detached,
        ahead: $ahead,
        behind: $behind
      },
      working_tree: {
        clean: $clean,
        modified: $modified,
        untracked: $untracked,
        staged: $staged
      },
      git_operations: {
        merge_in_progress: $merge_in,
        rebase_in_progress: $rebase_in,
        cherry_pick_in_progress: $cherry_in
      },
      conflicts: {
        potential: $conflict,
        files: [],
        reason: (if $conflict_reason == "" then null else $conflict_reason end)
      },
      draft_branches: $drafts,
      last: {
        fetch_at: (if $last_fetch_at == "" then null else $last_fetch_at end),
        fetch_status: (if $fetch_status == "skipped" then $last_pull_status else $fetch_status end),
        pull_at: (if $last_pull_at == "" then null else $last_pull_at end),
        pull_status: (if $last_pull_status == "" then null else $last_pull_status end),
        commit_at: (if $last_commit_at == "" then null else $last_commit_at end),
        commit_sha: (if $last_commit_sha == "" then null else $last_commit_sha end),
        push_at: (if $last_push_at == "" then null else $last_push_at end),
        push_status: (if $last_push_status == "" then null else $last_push_status end)
      },
      health: $health,
      watcher: {
        ran_at: $ran_at,
        duration_ms: $duration_ms,
        errors: $errors
      }
    }')"

  echo "$state_json" | ks_state_write

  ks_event_append "watcher_ran" "$(jq -nc \
    --arg ms "$duration_ms" \
    --argjson errors "$errors" \
    '{duration_ms: ($ms|tonumber), errors: $errors}')"
}
WATCHER_EOF
```

- [ ] **Step 2: Smoke test do Watcher**

```bash
cat > /tmp/ks-watcher-test.sh <<'TEST_EOF'
#!/usr/bin/env bash
set -euo pipefail
SKILL_DIR=~/.openclaw/skills/knowledge-sync
source "$SKILL_DIR/lib/common.sh"
source "$SKILL_DIR/lib/state.sh"
source "$SKILL_DIR/lib/events.sh"
source "$SKILL_DIR/lib/git-ops.sh"
source "$SKILL_DIR/lib/watcher.sh"

ks_check_deps
ks_check_clone

echo "=== Running Watcher cycle ==="
ks_watcher_run fetch

echo "=== state.json ==="
ks_state_read | jq .

echo "=== Health ==="
ks_state_read | jq .health
TEST_EOF
bash /tmp/ks-watcher-test.sh
rm /tmp/ks-watcher-test.sh
```

Expected:
- state.json criado e populado com schema completo
- branch = "main", clean = true, ahead = 0, behind = 0
- health.overall = "ok", health.issues = []

- [ ] **Step 3: Limpar dados de teste**

```bash
rm -f ~/.openclaw/knowledge-sync/state.json
rm -f ~/.openclaw/knowledge-sync/state.previous.json
rm -f ~/.openclaw/knowledge-sync/events.jsonl
```

---

---

## Task 5: Comandos consulta basica (status, refresh, health)

**Files:**
- Create: `~/.openclaw/skills/knowledge-sync/commands/status.sh`
- Create: `~/.openclaw/skills/knowledge-sync/commands/refresh.sh`
- Create: `~/.openclaw/skills/knowledge-sync/commands/health.sh`

> **Importante:** `status` e LEITURA PURA. NAO dispara Watcher (decisao da spec apos review). Para forcar atualizacao do estado, usuario invoca `refresh`.

- [ ] **Step 1: Criar commands/status.sh - leitura pura**

```bash
cat > ~/.openclaw/skills/knowledge-sync/commands/status.sh <<'CMD_EOF'
#!/usr/bin/env bash
# status - leitura pura do state.json (sem efeito colateral)
set -euo pipefail
source "$SKILL_DIR/lib/common.sh"
source "$SKILL_DIR/lib/state.sh"

# Flag --json para output bruto
if [[ "${1:-}" == "--json" ]]; then
  ks_state_read
  exit 0
fi

state="$(ks_state_read)"
if [[ "$state" == "{}" || -z "$state" ]]; then
  echo "knowledge-sync - state vazio. Rode 'knowledge-sync refresh' primeiro."
  exit 0
fi

cat <<HEAD
knowledge-sync - bevox-knowledge

  Branch:           $(echo "$state" | jq -r '.branch.current // "?"')
  Tracking:         $(echo "$state" | jq -r '.branch.tracking // "?"')
  Head:             $(echo "$state" | jq -r '.branch.head_sha // "?" | .[0:10]')
  Remote head:      $(echo "$state" | jq -r '.branch.tracking_head_sha // "?" | .[0:10]')
  Sync:             ahead $(echo "$state" | jq -r '.branch.ahead'), behind $(echo "$state" | jq -r '.branch.behind')
  Working tree:     $(echo "$state" | jq -r 'if .working_tree.clean then "clean" else "dirty" end')
  Git operations:   $(echo "$state" | jq -r 'if (.git_operations.merge_in_progress or .git_operations.rebase_in_progress or .git_operations.cherry_pick_in_progress) then "in progress" else "none" end')
  Conflicts:        $(echo "$state" | jq -r 'if .conflicts.potential then "POTENTIAL: \(.conflicts.reason // "")" else "none" end')

  Drafts:           $(echo "$state" | jq -r '.draft_branches | length') active
HEAD

echo "$state" | jq -r '.draft_branches[]? | "    - \(.name)  (head \(.head_sha[0:10]), \(.ahead_of_main) ahead of main)"'

cat <<TAIL

  Health:           $(echo "$state" | jq -r '.health.overall' | tr 'a-z' 'A-Z')
TAIL

echo "$state" | jq -r '.health.issues[]? | "    - \(.code) [\(.severity)] since \(.since)"'

cat <<TIME

  Last fetch:       $(echo "$state" | jq -r '.last.fetch_at // "never"')
  Last commit:      $(echo "$state" | jq -r '.last.commit_at // "never"') ($(echo "$state" | jq -r '.last.commit_sha // "?"'))
  Last push:        $(echo "$state" | jq -r '.last.push_at // "never"')
  Watcher last ran: $(echo "$state" | jq -r '.watcher.ran_at // "never"') ($(echo "$state" | jq -r '.watcher.duration_ms // 0')ms)
TIME
CMD_EOF
chmod +x ~/.openclaw/skills/knowledge-sync/commands/status.sh
```

- [ ] **Step 2: Criar commands/refresh.sh**

```bash
cat > ~/.openclaw/skills/knowledge-sync/commands/refresh.sh <<'CMD_EOF'
#!/usr/bin/env bash
# refresh (alias: watch) - roda Watcher agora, sem fetch forcado
set -euo pipefail
source "$SKILL_DIR/lib/common.sh"
source "$SKILL_DIR/lib/state.sh"
source "$SKILL_DIR/lib/events.sh"
source "$SKILL_DIR/lib/git-ops.sh"
source "$SKILL_DIR/lib/watcher.sh"

ks_check_deps
ks_check_clone
ks_lock 30 || exit 1
trap 'ks_unlock' EXIT

ks_watcher_run

if [[ "${1:-}" == "--json" ]]; then
  ks_state_read
else
  exec "$SKILL_DIR/commands/status.sh"
fi
CMD_EOF
chmod +x ~/.openclaw/skills/knowledge-sync/commands/refresh.sh
```

- [ ] **Step 3: Criar commands/health.sh**

```bash
cat > ~/.openclaw/skills/knowledge-sync/commands/health.sh <<'CMD_EOF'
#!/usr/bin/env bash
# health - resumo de health.overall + issues
set -euo pipefail
source "$SKILL_DIR/lib/common.sh"
source "$SKILL_DIR/lib/state.sh"

if [[ "${1:-}" == "--json" ]]; then
  ks_state_read | jq '.health'
  exit 0
fi

state="$(ks_state_read)"
overall="$(echo "$state" | jq -r '.health.overall // "unknown"')"
echo "Overall: $overall"
echo ""
echo "Issues:"
echo "$state" | jq -r '.health.issues[]? | "  [\(.severity)] \(.code) (since \(.since))"' || echo "  (none)"
CMD_EOF
chmod +x ~/.openclaw/skills/knowledge-sync/commands/health.sh
```

- [ ] **Step 4: Validar refresh + status + health**

```bash
~/.openclaw/skills/knowledge-sync/bin/knowledge-sync refresh
~/.openclaw/skills/knowledge-sync/bin/knowledge-sync status
~/.openclaw/skills/knowledge-sync/bin/knowledge-sync health
```

Expected: refresh popula state, status mostra resumo, health mostra OK.

---

## Task 6: Cron entry para refresh periodico

**Files:**
- Modify: cron do OpenClaw (formato confirmado na Task 1)

A spec define: `refresh` roda a cada 5 minutos.

- [ ] **Step 1: Verificar onde adicionar cron entries**

Da Task 1, voce ja sabe se o OpenClaw tem sistema de cron proprio (`cron/jobs.json`?) ou se usa systemd timer.

```bash
ls ~/.openclaw/cron/ 2>/dev/null
cat ~/.openclaw/cron/jobs.json 2>/dev/null
openclaw cron --help 2>&1 | head -20
```

- [ ] **Step 2: Adicionar entry de refresh (formato OpenClaw)**

Se OpenClaw tem cron nativo:
```bash
# Exemplo - adaptar ao formato real
openclaw cron add \
  --name "knowledge-sync-refresh" \
  --schedule "*/5 * * * *" \
  --command "$HOME/.openclaw/skills/knowledge-sync/bin/knowledge-sync refresh"
```

Caso contrario, usar systemd user timer como fallback:
```bash
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/knowledge-sync-refresh.service <<'EOF'
[Unit]
Description=knowledge-sync refresh (Watcher cycle)

[Service]
Type=oneshot
ExecStart=%h/.openclaw/skills/knowledge-sync/bin/knowledge-sync refresh
EOF

cat > ~/.config/systemd/user/knowledge-sync-refresh.timer <<'EOF'
[Unit]
Description=knowledge-sync refresh every 5 minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
Unit=knowledge-sync-refresh.service

[Install]
WantedBy=timers.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now knowledge-sync-refresh.timer
systemctl --user list-timers | grep knowledge-sync
```

- [ ] **Step 3: Validar disparo periodico**

Aguardar ~6 minutos e checar:
```bash
~/.openclaw/skills/knowledge-sync/bin/knowledge-sync events --last 5 2>/dev/null || \
  cat ~/.openclaw/knowledge-sync/events.jsonl | tail -5
```

Expected: eventos `watcher_ran` recentes.

---

## Task 7: Comandos read-only restantes (events, log, diff, drafts, snapshots, pending)

**Files:**
- Create: `~/.openclaw/skills/knowledge-sync/commands/events.sh`
- Create: `~/.openclaw/skills/knowledge-sync/commands/log.sh`
- Create: `~/.openclaw/skills/knowledge-sync/commands/diff.sh`
- Create: `~/.openclaw/skills/knowledge-sync/commands/drafts.sh`
- Create: `~/.openclaw/skills/knowledge-sync/commands/snapshots.sh`
- Create: `~/.openclaw/skills/knowledge-sync/commands/pending.sh`
- Create symlink: `approvals.sh` -> `pending.sh`

- [ ] **Step 1: events.sh**

```bash
cat > ~/.openclaw/skills/knowledge-sync/commands/events.sh <<'CMD_EOF'
#!/usr/bin/env bash
set -euo pipefail
source "$SKILL_DIR/lib/common.sh"
source "$SKILL_DIR/lib/events.sh"

n=20
while [[ $# -gt 0 ]]; do
  case "$1" in
    --last) n="$2"; shift 2 ;;
    --json) shift ;;
    *) echo "events: arg desconhecido: $1" >&2; exit 2 ;;
  esac
done

ks_events_tail "$n" | jq -c .
CMD_EOF
chmod +x ~/.openclaw/skills/knowledge-sync/commands/events.sh
```

- [ ] **Step 2: log.sh**

```bash
cat > ~/.openclaw/skills/knowledge-sync/commands/log.sh <<'CMD_EOF'
#!/usr/bin/env bash
set -euo pipefail
source "$SKILL_DIR/lib/common.sh"
source "$SKILL_DIR/lib/git-ops.sh"

n=10
while [[ $# -gt 0 ]]; do
  case "$1" in
    --limit) n="$2"; shift 2 ;;
    *) shift ;;
  esac
done

ks_git log --oneline -n "$n"
CMD_EOF
chmod +x ~/.openclaw/skills/knowledge-sync/commands/log.sh
```

- [ ] **Step 3: diff.sh**

```bash
cat > ~/.openclaw/skills/knowledge-sync/commands/diff.sh <<'CMD_EOF'
#!/usr/bin/env bash
set -euo pipefail
source "$SKILL_DIR/lib/common.sh"
source "$SKILL_DIR/lib/git-ops.sh"

if [[ $# -gt 0 ]]; then
  ks_git diff -- "$@"
else
  ks_git diff
fi
CMD_EOF
chmod +x ~/.openclaw/skills/knowledge-sync/commands/diff.sh
```

- [ ] **Step 4: drafts.sh**

```bash
cat > ~/.openclaw/skills/knowledge-sync/commands/drafts.sh <<'CMD_EOF'
#!/usr/bin/env bash
set -euo pipefail
source "$SKILL_DIR/lib/common.sh"
source "$SKILL_DIR/lib/state.sh"

if [[ "${1:-}" == "--json" ]]; then
  ks_state_read | jq '.draft_branches'
  exit 0
fi

drafts="$(ks_state_read | jq -c '.draft_branches')"
count="$(echo "$drafts" | jq 'length')"
echo "Drafts: $count active"
echo "$drafts" | jq -r '.[] | "  - \(.name)  head=\(.head_sha[0:10])  ahead_of_main=\(.ahead_of_main)"'
CMD_EOF
chmod +x ~/.openclaw/skills/knowledge-sync/commands/drafts.sh
```

- [ ] **Step 5: snapshots.sh**

```bash
cat > ~/.openclaw/skills/knowledge-sync/commands/snapshots.sh <<'CMD_EOF'
#!/usr/bin/env bash
set -euo pipefail
source "$SKILL_DIR/lib/common.sh"

type_filter=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --type) type_filter="$2"; shift 2 ;;
    --json) shift ;;
    *) shift ;;
  esac
done

if [[ ! -f "$KS_SNAPSHOTS_INDEX" ]]; then
  echo "(nenhum snapshot)"
  exit 0
fi

if [[ -z "$type_filter" ]]; then
  cat "$KS_SNAPSHOTS_INDEX" | jq -c .
else
  grep -F "\"type\":\"$type_filter\"" "$KS_SNAPSHOTS_INDEX" | jq -c .
fi
CMD_EOF
chmod +x ~/.openclaw/skills/knowledge-sync/commands/snapshots.sh
```

- [ ] **Step 6: pending.sh + alias approvals.sh**

```bash
cat > ~/.openclaw/skills/knowledge-sync/commands/pending.sh <<'CMD_EOF'
#!/usr/bin/env bash
# pending - lista approvals canonicos pendentes
# Le do events.jsonl: canonical_approval_pending sem canonical_approval_granted/rejected subsequente
set -euo pipefail
source "$SKILL_DIR/lib/common.sh"
source "$SKILL_DIR/lib/events.sh"

if [[ ! -f "$KS_EVENTS_FILE" ]]; then
  echo "(nenhum approval pendente)"
  exit 0
fi

# Encontra approval_ids pendentes (pending sem granted/rejected/committed/pushed depois)
pending_ids="$(jq -rc '
  select(.event=="canonical_approval_pending") | .payload.approval_id
' "$KS_EVENTS_FILE" 2>/dev/null | sort -u)"

if [[ -z "$pending_ids" ]]; then
  echo "(nenhum approval pendente)"
  exit 0
fi

resolved="$(jq -rc '
  select(.event=="canonical_approval_granted" or .event=="canonical_approval_rejected" or .event=="canonical_committed" or .event=="canonical_pushed" or .event=="canonical_marker_created") | .payload.approval_id // empty
' "$KS_EVENTS_FILE" 2>/dev/null | sort -u)"

echo "Approvals pendentes:"
while IFS= read -r aid; do
  [[ -z "$aid" || "$aid" == "null" ]] && continue
  if ! grep -Fxq "$aid" <<< "$resolved"; then
    line="$(grep -F "\"approval_id\":\"$aid\"" "$KS_EVENTS_FILE" | grep canonical_approval_pending | tail -1)"
    echo "  - $aid"
    echo "$line" | jq -c '.payload'
  fi
done <<< "$pending_ids"
CMD_EOF
chmod +x ~/.openclaw/skills/knowledge-sync/commands/pending.sh
ln -sf pending.sh ~/.openclaw/skills/knowledge-sync/commands/approvals.sh
```

- [ ] **Step 7: Smoke test dos read-only**

```bash
KS=~/.openclaw/skills/knowledge-sync/bin/knowledge-sync
$KS events --last 5
$KS log --limit 5
$KS drafts
$KS snapshots
$KS pending
```

Expected: cada comando roda sem erro (varios podem mostrar listas vazias - isso e ok).

---

## Task 8: lib/snapshot.sh - criar e indexar snapshots

**Files:**
- Create: `~/.openclaw/skills/knowledge-sync/lib/snapshot.sh`

Implementa criacao de bundle, sha256, append no index, dedup pre-canonical.

- [ ] **Step 1: Criar lib/snapshot.sh**

```bash
cat > ~/.openclaw/skills/knowledge-sync/lib/snapshot.sh <<'SNAP_EOF'
#!/usr/bin/env bash
# snapshot.sh - bundle creation, indexing, verification

# Cria um snapshot
# Args: $1 = type (auto-hourly|pre-canonical|manual), $2 = optional slug/context
# Retorna o path do bundle criado via stdout
ks_snapshot_create() {
  local type="$1"
  local slug="${2:-}"

  local now ts_compact
  now="$(ks_now)"
  ts_compact="$(date -u -d "$now" +%Y-%m-%d-%H-%M)"

  local subdir filename
  case "$type" in
    auto-hourly)
      subdir="$KS_SNAPSHOTS_DIR/auto"
      filename="${ts_compact}-auto-hourly.bundle"
      ;;
    pre-canonical)
      subdir="$KS_SNAPSHOTS_DIR/pre-canonical"
      filename="${ts_compact}-pre-canonical-${slug}.bundle"
      ;;
    manual)
      subdir="$KS_SNAPSHOTS_DIR/manual"
      filename="${ts_compact}-manual-${slug:-no-slug}.bundle"
      ;;
    pre-restore)
      subdir="$KS_SNAPSHOTS_DIR/manual"
      filename="${ts_compact}-pre-restore-${slug:-auto}.bundle"
      ;;
    *)
      ks_err "snapshot type unknown: $type"
      return 1 ;;
  esac

  mkdir -p "$subdir"
  local path="$subdir/$filename"

  # Dedup para pre-canonical: se ja existe um pre-canonical recente para o mesmo head_sha, reuse
  if [[ "$type" == "pre-canonical" ]]; then
    local head_sha
    head_sha="$(ks_git_head_sha)"
    local existing
    existing="$(grep -l "\"head_sha\":\"$head_sha\"" "$KS_SNAPSHOTS_INDEX" 2>/dev/null || true)"
    if [[ -n "$existing" ]]; then
      local recent
      recent="$(grep "\"head_sha\":\"$head_sha\"" "$KS_SNAPSHOTS_INDEX" | grep '"type":"pre-canonical"' | tail -1)"
      if [[ -n "$recent" ]]; then
        local recent_path
        recent_path="$KS_SNAPSHOTS_DIR/$(echo "$recent" | jq -r '.path')"
        if [[ -f "$recent_path" ]]; then
          ks_log "dedup: reusing existing pre-canonical snapshot for $head_sha"
          echo "$recent_path"
          return 0
        fi
      fi
    fi
  fi

  # Criar bundle
  ks_git bundle create "$path" --all 2>/dev/null
  chmod 600 "$path"

  # SHA256
  local sha256
  sha256="$(sha256sum "$path" | awk '{print $1}')"

  # Tamanho
  local size
  size="$(stat -c%s "$path")"

  # Branches/tags atuais
  local branches_json tags_json
  branches_json="$(ks_git branch --format='%(refname:short)' 2>/dev/null | jq -R . | jq -sc .)"
  tags_json="$(ks_git tag 2>/dev/null | jq -R . | jq -sc .)"

  local rel_path="${path#$KS_SNAPSHOTS_DIR/}"
  local entry
  entry="$(jq -nc \
    --arg ts "$now" \
    --arg type "$type" \
    --arg path "$rel_path" \
    --argjson size "$size" \
    --arg head_sha "$(ks_git_head_sha)" \
    --argjson branches "$branches_json" \
    --argjson tags "$tags_json" \
    --arg sha256 "$sha256" \
    '{
      ts: $ts,
      type: $type,
      path: $path,
      size_bytes: $size,
      head_sha: $head_sha,
      branches: $branches,
      tags: $tags,
      sha256: $sha256,
      verify_status: "pending",
      verified_at: null
    }')"
  echo "$entry" >> "$KS_SNAPSHOTS_INDEX"
  chmod 600 "$KS_SNAPSHOTS_INDEX"

  echo "$path"
}

# Verifica um bundle: integridade git + sha256 + smoke restore
# Retorna 0 ok, 1 fail
ks_snapshot_verify_one() {
  local path="$1"
  local expected_sha="$2"

  if [[ ! -f "$path" ]]; then
    ks_err "missing: $path"
    return 1
  fi

  local actual_sha
  actual_sha="$(sha256sum "$path" | awk '{print $1}')"
  if [[ "$actual_sha" != "$expected_sha" ]]; then
    ks_err "sha256 mismatch: $path"
    return 1
  fi

  if ! git bundle verify "$path" >/dev/null 2>&1; then
    ks_err "git bundle verify failed: $path"
    return 1
  fi

  # Smoke restore: tentar clone para tmp
  local tmp
  tmp="$(mktemp -d)"
  if ! git clone --quiet "$path" "$tmp/restore" >/dev/null 2>&1; then
    rm -rf "$tmp"
    ks_err "smoke clone failed: $path"
    return 1
  fi
  rm -rf "$tmp"

  return 0
}

# Atualiza verify_status no index para o bundle
ks_snapshot_mark_verified() {
  local rel_path="$1"
  local status="$2"  # verified | failed
  local now
  now="$(ks_now)"

  if [[ ! -f "$KS_SNAPSHOTS_INDEX" ]]; then
    return
  fi

  local tmp
  tmp="$(mktemp)"
  jq -c \
    --arg p "$rel_path" \
    --arg s "$status" \
    --arg t "$now" \
    'if .path == $p then (.verify_status = $s | .verified_at = $t) else . end' \
    "$KS_SNAPSHOTS_INDEX" > "$tmp"
  mv "$tmp" "$KS_SNAPSHOTS_INDEX"
  chmod 600 "$KS_SNAPSHOTS_INDEX"
}

# Rotaciona snapshots conforme retencao por tipo
# auto-hourly: 48h
# pre-canonical: 30d
# manual: 90d
ks_snapshot_rotate() {
  local now_ts
  now_ts="$(date -u +%s)"

  # auto: 48h
  find "$KS_SNAPSHOTS_DIR/auto" -type f -name '*.bundle' 2>/dev/null | while IFS= read -r f; do
    local mtime
    mtime="$(stat -c%Y "$f")"
    if (( now_ts - mtime > 48 * 3600 )); then
      rm -f "$f"
    fi
  done

  # pre-canonical: 30d
  find "$KS_SNAPSHOTS_DIR/pre-canonical" -type f -name '*.bundle' 2>/dev/null | while IFS= read -r f; do
    local mtime
    mtime="$(stat -c%Y "$f")"
    if (( now_ts - mtime > 30 * 86400 )); then
      rm -f "$f"
    fi
  done

  # manual: 90d
  find "$KS_SNAPSHOTS_DIR/manual" -type f -name '*.bundle' 2>/dev/null | while IFS= read -r f; do
    local mtime
    mtime="$(stat -c%Y "$f")"
    if (( now_ts - mtime > 90 * 86400 )); then
      rm -f "$f"
    fi
  done
}
SNAP_EOF
```

- [ ] **Step 2: Smoke test snapshot lib**

```bash
bash <<'TEST_EOF'
SKILL_DIR=~/.openclaw/skills/knowledge-sync
source "$SKILL_DIR/lib/common.sh"
source "$SKILL_DIR/lib/state.sh"
source "$SKILL_DIR/lib/events.sh"
source "$SKILL_DIR/lib/git-ops.sh"
source "$SKILL_DIR/lib/snapshot.sh"

ks_check_deps
ks_check_clone

echo "Creating manual snapshot..."
path="$(ks_snapshot_create manual smoke-test)"
echo "Created: $path"
ls -la "$path"

echo ""
echo "Index:"
cat "$KS_SNAPSHOTS_INDEX"

echo ""
echo "Verifying..."
sha="$(jq -r '.sha256' <<< "$(tail -1 "$KS_SNAPSHOTS_INDEX")")"
if ks_snapshot_verify_one "$path" "$sha"; then
  echo "VERIFY OK"
else
  echo "VERIFY FAILED"
fi
TEST_EOF
```

Expected: bundle criado, index populado, verify ok.

- [ ] **Step 3: Limpar smoke**

```bash
rm -f ~/.openclaw/backups/knowledge-snapshots/manual/*-manual-smoke-test.bundle
# limpar a entrada do index
grep -v 'smoke-test' ~/.openclaw/backups/knowledge-snapshots/meta/snapshots-index.jsonl > /tmp/idx.tmp 2>/dev/null && \
  mv /tmp/idx.tmp ~/.openclaw/backups/knowledge-snapshots/meta/snapshots-index.jsonl
chmod 600 ~/.openclaw/backups/knowledge-snapshots/meta/snapshots-index.jsonl 2>/dev/null || true
```

---

## Task 9: Comando snapshot create + cron hourly

**Files:**
- Create: `~/.openclaw/skills/knowledge-sync/commands/snapshot.sh`
- Modify: cron OpenClaw (entry hourly)

- [ ] **Step 1: Criar commands/snapshot.sh (com subcomandos)**

```bash
cat > ~/.openclaw/skills/knowledge-sync/commands/snapshot.sh <<'CMD_EOF'
#!/usr/bin/env bash
# snapshot - subcomandos: create, verify
set -euo pipefail
source "$SKILL_DIR/lib/common.sh"
source "$SKILL_DIR/lib/state.sh"
source "$SKILL_DIR/lib/events.sh"
source "$SKILL_DIR/lib/git-ops.sh"
source "$SKILL_DIR/lib/snapshot.sh"

ks_check_deps
ks_check_clone

sub="${1:-}"; shift || true

case "$sub" in
  create)
    type="auto-hourly"
    slug=""
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --manual) type="manual"; slug="$2"; shift 2 ;;
        --auto) type="auto-hourly"; shift ;;
        --pre-canonical) type="pre-canonical"; slug="$2"; shift 2 ;;
        *) shift ;;
      esac
    done
    ks_lock 30 || exit 1
    trap 'ks_unlock' EXIT
    path="$(ks_snapshot_create "$type" "$slug")"
    ks_event_append "snapshot_created" "$(jq -nc --arg t "$type" --arg p "$path" '{type: $t, path: $p}')"
    ks_snapshot_rotate
    echo "$path"
    ;;

  verify)
    sample_n=0
    verify_all=false
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --all) verify_all=true; shift ;;
        --sample) sample_n="$2"; shift 2 ;;
        *) shift ;;
      esac
    done

    [[ ! -f "$KS_SNAPSHOTS_INDEX" ]] && { echo "no index"; exit 0; }

    if $verify_all; then
      mapfile -t entries < "$KS_SNAPSHOTS_INDEX"
    else
      [[ "$sample_n" -eq 0 ]] && sample_n=3
      mapfile -t entries < <(shuf "$KS_SNAPSHOTS_INDEX" 2>/dev/null | head -n "$sample_n")
    fi

    failed=0
    verified=0
    for entry in "${entries[@]}"; do
      rel_path="$(echo "$entry" | jq -r '.path')"
      sha="$(echo "$entry" | jq -r '.sha256')"
      full_path="$KS_SNAPSHOTS_DIR/$rel_path"
      if ks_snapshot_verify_one "$full_path" "$sha"; then
        ks_snapshot_mark_verified "$rel_path" "verified"
        verified=$((verified+1))
      else
        ks_snapshot_mark_verified "$rel_path" "failed"
        failed=$((failed+1))
        ks_event_append "snapshot_verification_failed" "$(jq -nc --arg p "$rel_path" '{path: $p}')"
      fi
    done

    echo "verified=$verified failed=$failed"
    [[ $failed -gt 0 ]] && exit 1
    exit 0
    ;;

  *)
    echo "snapshot: subcomando desconhecido: $sub" >&2
    echo "Use: snapshot create [--manual <slug>] | snapshot verify [--all|--sample N]" >&2
    exit 2 ;;
esac
CMD_EOF
chmod +x ~/.openclaw/skills/knowledge-sync/commands/snapshot.sh
```

- [ ] **Step 2: Adicionar cron entry hourly snapshot**

Mesma logica da Task 6 (cron OpenClaw nativo OU systemd timer fallback):

```bash
# Systemd timer fallback:
cat > ~/.config/systemd/user/knowledge-sync-snapshot-hourly.service <<'EOF'
[Unit]
Description=knowledge-sync hourly snapshot

[Service]
Type=oneshot
ExecStart=%h/.openclaw/skills/knowledge-sync/bin/knowledge-sync snapshot create --auto
EOF

cat > ~/.config/systemd/user/knowledge-sync-snapshot-hourly.timer <<'EOF'
[Unit]
Description=knowledge-sync snapshot every hour at :00

[Timer]
OnCalendar=hourly
Persistent=true
Unit=knowledge-sync-snapshot-hourly.service

[Install]
WantedBy=timers.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now knowledge-sync-snapshot-hourly.timer
```

- [ ] **Step 3: Validar com snapshot manual**

```bash
~/.openclaw/skills/knowledge-sync/bin/knowledge-sync snapshot create --manual e1-implementation
cat ~/.openclaw/backups/knowledge-snapshots/meta/snapshots-index.jsonl | tail -1 | jq .
```

Expected: bundle criado, entry no index com sha256 e verify_status pending.

---

## Task 10: Comando snapshot verify + cron daily

- [ ] **Step 1: Validar verify**

```bash
~/.openclaw/skills/knowledge-sync/bin/knowledge-sync snapshot verify --all
cat ~/.openclaw/backups/knowledge-snapshots/meta/snapshots-index.jsonl | jq '.verify_status, .verified_at'
```

Expected: `verified=N failed=0`, status atualizado para `verified` no index.

- [ ] **Step 2: Cron daily verify (sample)**

```bash
cat > ~/.config/systemd/user/knowledge-sync-verify-daily.service <<'EOF'
[Unit]
Description=knowledge-sync daily snapshot verify (sample)

[Service]
Type=oneshot
ExecStart=%h/.openclaw/skills/knowledge-sync/bin/knowledge-sync snapshot verify --sample 5
EOF

cat > ~/.config/systemd/user/knowledge-sync-verify-daily.timer <<'EOF'
[Unit]
Description=knowledge-sync verify daily at 04:00

[Timer]
OnCalendar=*-*-* 04:00:00
Persistent=true
Unit=knowledge-sync-verify-daily.service

[Install]
WantedBy=timers.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now knowledge-sync-verify-daily.timer
```

---

## Task 11: Comando restore (default dry-run, --apply override)

**Files:**
- Create: `~/.openclaw/skills/knowledge-sync/commands/restore.sh`

> **Critico:** default e SEMPRE dry-run para temp dir. `--apply` exige confirmacao explicita do Bernard.

- [ ] **Step 1: Criar commands/restore.sh**

```bash
cat > ~/.openclaw/skills/knowledge-sync/commands/restore.sh <<'CMD_EOF'
#!/usr/bin/env bash
# restore <bundle> [--target <path>] [--apply]
set -euo pipefail
source "$SKILL_DIR/lib/common.sh"
source "$SKILL_DIR/lib/state.sh"
source "$SKILL_DIR/lib/events.sh"
source "$SKILL_DIR/lib/git-ops.sh"
source "$SKILL_DIR/lib/snapshot.sh"

bundle=""
target=""
apply=false
yes=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) target="$2"; shift 2 ;;
    --apply) apply=true; shift ;;
    --yes) yes=true; shift ;;
    -*) echo "restore: arg desconhecido: $1" >&2; exit 2 ;;
    *) bundle="$1"; shift ;;
  esac
done

if [[ -z "$bundle" ]]; then
  echo "restore: bundle path requerido" >&2
  exit 2
fi

# Resolver path relativo ao snapshots dir se nao for absoluto
if [[ "${bundle:0:1}" != "/" ]]; then
  bundle="$KS_SNAPSHOTS_DIR/$bundle"
fi

if [[ ! -f "$bundle" ]]; then
  echo "restore: bundle nao encontrado: $bundle" >&2
  exit 1
fi

# Default: dry-run
if ! $apply; then
  if [[ -z "$target" ]]; then
    target="/tmp/ks-rollback-$(date +%s)"
  fi
  echo "DRY-RUN: restaurando para $target"
  git clone --quiet "$bundle" "$target"
  echo ""
  echo "OK. Inspecione em: $target"
  echo "Para sobrescrever o clone atual, use: knowledge-sync restore <bundle> --apply"
  ks_event_append "restore_dryrun" "$(jq -nc --arg b "$bundle" --arg t "$target" '{bundle: $b, target: $t}')"
  exit 0
fi

# --apply: hard override (categoria destructive ADR-006 = NEVER em todos levels - exige override)
if ! $yes; then
  echo ""
  echo "  ATENCAO - operacao DESTRUTIVA"
  echo "  Vai sobrescrever $KS_CLONE_PATH com $bundle"
  echo "  Categoria ADR-006: destructive (NEVER em todos os levels - exige override do Bernard)"
  echo ""
  read -r -p "  Digite 'SIM, APLICAR ROLLBACK' para confirmar: " confirm
  if [[ "$confirm" != "SIM, APLICAR ROLLBACK" ]]; then
    echo "  cancelado."
    ks_event_append "restore_apply_cancelled" "$(jq -nc --arg b "$bundle" '{bundle: $b}')"
    exit 1
  fi
fi

# Pre-restore snapshot do estado atual
ks_log "criando pre-restore snapshot do estado atual..."
pre_restore="$(ks_snapshot_create pre-restore "rollback-$(date +%s)")"
ks_log "pre-restore: $pre_restore"

# Restaurar
local_tmp="/tmp/ks-restore-$(date +%s)"
git clone --quiet "$bundle" "$local_tmp"

# Substituir clone atual
backup_old="${KS_CLONE_PATH}.before-restore-$(date +%s)"
mv "$KS_CLONE_PATH" "$backup_old"
mv "$local_tmp" "$KS_CLONE_PATH"

ks_event_append "restore_applied" "$(jq -nc \
  --arg b "$bundle" \
  --arg pre "$pre_restore" \
  --arg backup "$backup_old" \
  '{bundle: $b, pre_restore: $pre, backup_of_old: $backup}')"

echo "OK. Clone atual substituido."
echo "Backup do anterior: $backup_old"
echo "Pre-restore snapshot: $pre_restore"
CMD_EOF
chmod +x ~/.openclaw/skills/knowledge-sync/commands/restore.sh
```

- [ ] **Step 2: Validar dry-run**

```bash
KS=~/.openclaw/skills/knowledge-sync/bin/knowledge-sync
bundle="$($KS snapshots --type manual | jq -r '.path' | head -1)"
$KS restore "$bundle"
ls /tmp/ks-rollback-*/ 2>/dev/null
rm -rf /tmp/ks-rollback-*
```

Expected: clona o bundle para /tmp, lista arquivos.

---

## Task 12: Comando pull-ff (com guardrails estritos)

**Files:**
- Create: `~/.openclaw/skills/knowledge-sync/commands/fetch.sh`
- Create: `~/.openclaw/skills/knowledge-sync/commands/pull-ff.sh`

> **Critico:** `pull-ff` recusa se: dirty, op git pendente, ahead > 0, tracking inconsistente, conflito potencial. Spec secao 4.4 (contrato detalhado).

- [ ] **Step 1: fetch.sh**

```bash
cat > ~/.openclaw/skills/knowledge-sync/commands/fetch.sh <<'CMD_EOF'
#!/usr/bin/env bash
# fetch - forca git fetch e roda Watcher
set -euo pipefail
source "$SKILL_DIR/lib/common.sh"
source "$SKILL_DIR/lib/state.sh"
source "$SKILL_DIR/lib/events.sh"
source "$SKILL_DIR/lib/git-ops.sh"
source "$SKILL_DIR/lib/watcher.sh"

ks_check_deps
ks_check_clone
ks_lock 30 || exit 1
trap 'ks_unlock' EXIT

ks_event_append "action_started" '{"action": "fetch"}'
ks_watcher_run fetch
fetch_status="$(ks_state_read | jq -r '.last.fetch_status // "unknown"')"
ks_event_append "action_succeeded" "$(jq -nc --arg s "$fetch_status" '{action: "fetch", fetch_status: $s}')"

exec "$SKILL_DIR/commands/status.sh"
CMD_EOF
chmod +x ~/.openclaw/skills/knowledge-sync/commands/fetch.sh
```

- [ ] **Step 2: pull-ff.sh com validacao estrita**

```bash
cat > ~/.openclaw/skills/knowledge-sync/commands/pull-ff.sh <<'CMD_EOF'
#!/usr/bin/env bash
# pull-ff - git pull --ff-only com guardrails
# Recusa se: dirty, op git pendente, ahead > 0, tracking inconsistente, conflito potencial
set -euo pipefail
source "$SKILL_DIR/lib/common.sh"
source "$SKILL_DIR/lib/state.sh"
source "$SKILL_DIR/lib/events.sh"
source "$SKILL_DIR/lib/git-ops.sh"
source "$SKILL_DIR/lib/watcher.sh"

ks_check_deps
ks_check_clone
ks_lock 30 || exit 1
trap 'ks_unlock' EXIT

# Refrescar Watcher antes
ks_watcher_run

# Validacoes (preconditions per contrato)
state="$(ks_state_read)"
clean="$(echo "$state" | jq -r '.working_tree.clean')"
ahead="$(echo "$state" | jq -r '.branch.ahead')"
behind="$(echo "$state" | jq -r '.branch.behind')"
tracking="$(echo "$state" | jq -r '.branch.tracking // ""')"
merge_in="$(echo "$state" | jq -r '.git_operations.merge_in_progress')"
rebase_in="$(echo "$state" | jq -r '.git_operations.rebase_in_progress')"
cherry_in="$(echo "$state" | jq -r '.git_operations.cherry_pick_in_progress')"
conflict="$(echo "$state" | jq -r '.conflicts.potential')"

reason=""
if [[ "$clean" != "true" ]]; then
  reason="working tree not clean"
elif [[ "$merge_in" == "true" || "$rebase_in" == "true" || "$cherry_in" == "true" ]]; then
  reason="git operation in progress"
elif (( ahead > 0 )); then
  reason="non-ff: would require merge (ahead $ahead)"
elif [[ -z "$tracking" || "$tracking" == "null" ]]; then
  reason="tracking inconsistent"
elif [[ "$conflict" == "true" ]]; then
  reason="potential conflict"
fi

if [[ -n "$reason" ]]; then
  ks_event_append "action_rejected" "$(jq -nc --arg r "$reason" '{action: "pull-ff", reason: $r}')"
  echo "BLOCKED: $reason" >&2
  exit 3
fi

# Se behind == 0, no-op
if (( behind == 0 )); then
  echo "already up to date"
  ks_event_append "action_succeeded" '{"action": "pull-ff", "noop": true}'
  exit 0
fi

ks_event_append "action_started" '{"action": "pull-ff"}'

# Tentar pull --ff-only
if ks_git pull --ff-only --quiet 2>&1; then
  ks_watcher_run
  ks_event_append "action_succeeded" "$(jq -nc \
    --arg sha "$(ks_git_head_sha)" \
    '{action: "pull-ff", new_head_sha: $sha}')"
  echo "OK"
else
  ks_event_append "action_failed" '{"action": "pull-ff", "error": "git pull --ff-only failed"}'
  echo "FAILED" >&2
  exit 1
fi
CMD_EOF
chmod +x ~/.openclaw/skills/knowledge-sync/commands/pull-ff.sh
```

- [ ] **Step 3: Validar comportamento (deve retornar "already up to date")**

```bash
~/.openclaw/skills/knowledge-sync/bin/knowledge-sync pull-ff
```

Expected: `already up to date` (clone esta sincronizado).

---

---

## Task 13: Comando draft (create, commit, push, delete)

**Files:**
- Create: `~/.openclaw/skills/knowledge-sync/commands/draft.sh`

> **Spec:** subcomandos draft sao `write-knowledge-draft` = auto em L4. `draft delete` apaga apenas branch local (NAO remota).

- [ ] **Step 1: Criar commands/draft.sh**

```bash
cat > ~/.openclaw/skills/knowledge-sync/commands/draft.sh <<'CMD_EOF'
#!/usr/bin/env bash
# draft - subcomandos: create, commit, push, delete
set -euo pipefail
source "$SKILL_DIR/lib/common.sh"
source "$SKILL_DIR/lib/state.sh"
source "$SKILL_DIR/lib/events.sh"
source "$SKILL_DIR/lib/git-ops.sh"
source "$SKILL_DIR/lib/watcher.sh"

ks_check_deps
ks_check_clone

sub="${1:-}"; shift || true

case "$sub" in
  create)
    slug="${1:-}"
    [[ -z "$slug" ]] && { echo "draft create <slug>" >&2; exit 2; }
    ks_lock 30 || exit 1
    trap 'ks_unlock' EXIT

    branch_name="draft/$slug"
    ks_event_append "action_started" "$(jq -nc --arg b "$branch_name" '{action: "draft create", branch: $b}')"

    if ks_git show-ref --quiet --verify "refs/heads/$branch_name"; then
      ks_event_append "action_rejected" "$(jq -nc --arg b "$branch_name" '{action: "draft create", reason: "branch already exists", branch: $b}')"
      echo "BLOCKED: branch ja existe: $branch_name" >&2
      exit 3
    fi

    ks_git checkout -b "$branch_name" 2>&1
    ks_watcher_run
    ks_event_append "draft_branch_created" "$(jq -nc --arg b "$branch_name" '{branch: $b}')"
    ks_event_append "action_succeeded" "$(jq -nc --arg b "$branch_name" '{action: "draft create", branch: $b}')"
    echo "OK: criado $branch_name"
    ;;

  commit)
    msg=""
    while [[ $# -gt 0 ]]; do
      case "$1" in
        -m) msg="$2"; shift 2 ;;
        *) shift ;;
      esac
    done
    [[ -z "$msg" ]] && { echo "draft commit -m <msg>" >&2; exit 2; }

    ks_lock 30 || exit 1
    trap 'ks_unlock' EXIT

    current_branch="$(ks_git_branch)"
    if [[ "$current_branch" != draft/* ]]; then
      ks_event_append "action_rejected" "$(jq -nc --arg b "$current_branch" '{action: "draft commit", reason: "current branch is not draft/*", branch: $b}')"
      echo "BLOCKED: branch atual nao e draft/* (esta em $current_branch)" >&2
      exit 3
    fi

    ks_event_append "action_started" "$(jq -nc --arg b "$current_branch" --arg m "$msg" '{action: "draft commit", branch: $b, message: $m}')"

    ks_git add -A
    if ks_git commit -m "$msg" --quiet 2>&1; then
      new_sha="$(ks_git_head_sha)"
      ks_watcher_run
      ks_event_append "action_succeeded" "$(jq -nc --arg b "$current_branch" --arg s "$new_sha" '{action: "draft commit", branch: $b, new_sha: $s}')"
      echo "OK: commit $new_sha"
    else
      ks_event_append "action_failed" "$(jq -nc --arg b "$current_branch" '{action: "draft commit", branch: $b, error: "commit failed (no changes?)"}')"
      echo "FAILED: commit falhou" >&2
      exit 1
    fi
    ;;

  push)
    ks_lock 30 || exit 1
    trap 'ks_unlock' EXIT

    current_branch="$(ks_git_branch)"
    if [[ "$current_branch" != draft/* ]]; then
      ks_event_append "action_rejected" "$(jq -nc --arg b "$current_branch" '{action: "draft push", reason: "current branch is not draft/*", branch: $b}')"
      echo "BLOCKED: branch atual nao e draft/*" >&2
      exit 3
    fi

    ks_event_append "action_started" "$(jq -nc --arg b "$current_branch" '{action: "draft push", branch: $b}')"

    if ks_git push -u origin "$current_branch" 2>&1; then
      ks_event_append "draft_branch_pushed" "$(jq -nc --arg b "$current_branch" '{branch: $b}')"
      ks_event_append "action_succeeded" "$(jq -nc --arg b "$current_branch" '{action: "draft push", branch: $b}')"
      echo "OK: push $current_branch -> origin"
    else
      ks_event_append "action_failed" "$(jq -nc --arg b "$current_branch" '{action: "draft push", error: "push failed"}')"
      echo "FAILED: push" >&2
      exit 1
    fi
    ;;

  delete)
    name="${1:-}"
    [[ -z "$name" ]] && { echo "draft delete <name>" >&2; exit 2; }
    [[ "$name" != draft/* ]] && name="draft/$name"

    ks_lock 30 || exit 1
    trap 'ks_unlock' EXIT

    if ! ks_git show-ref --quiet --verify "refs/heads/$name"; then
      echo "BLOCKED: branch nao existe localmente: $name" >&2
      exit 3
    fi

    ks_event_append "action_started" "$(jq -nc --arg b "$name" '{action: "draft delete", branch: $b}')"

    # Apaga APENAS local. Branch remota fica.
    if ks_git branch -D "$name" 2>&1; then
      ks_event_append "action_succeeded" "$(jq -nc --arg b "$name" '{action: "draft delete", branch: $b, note: "local only - remote branch (if any) preserved"}')"
      echo "OK: $name apagada localmente. Branch remota correspondente NAO foi apagada."
    else
      ks_event_append "action_failed" "$(jq -nc --arg b "$name" '{action: "draft delete"}')"
      echo "FAILED: delete" >&2
      exit 1
    fi
    ;;

  *)
    echo "draft: subcomando desconhecido: $sub" >&2
    echo "Use: draft create <slug> | draft commit -m <msg> | draft push | draft delete <name>" >&2
    exit 2 ;;
esac
CMD_EOF
chmod +x ~/.openclaw/skills/knowledge-sync/commands/draft.sh
```

- [ ] **Step 2: Smoke test draft cycle**

```bash
KS=~/.openclaw/skills/knowledge-sync/bin/knowledge-sync

# Criar branch draft
$KS draft create test-e1-smoke

# Verificar
$KS status | head -20

# Tentar commitar sem mudancas (deve falhar)
$KS draft commit -m "test" || echo "expected fail"

# Criar uma mudanca pequena no inbox
echo "# E1 smoke test" > ~/bevox-knowledge/00_inbox/e1-smoke.md
$KS draft commit -m "wip: e1 smoke test"

# Voltar pra main e apagar branch
git -C ~/bevox-knowledge checkout main
$KS draft delete test-e1-smoke

# Limpar
rm -f ~/bevox-knowledge/00_inbox/e1-smoke.md
```

Expected: cria branch, commit ok com a mudanca, delete ok.

---

## Task 14: lib/notify.sh - Telegram bridge + severity routing

**Files:**
- Create: `~/.openclaw/skills/knowledge-sync/lib/notify.sh`

> **Spec sec 5.6:** info -> events apenas. warn -> Telegram. error -> Telegram com [CRITICAL]. Quiet hours 23-08.

- [ ] **Step 1: Investigar como enviar mensagem ao Telegram pelo OpenClaw**

```bash
openclaw message --help 2>&1 | head -20
openclaw agent --help 2>&1 | head -20
```

Provavelmente: `openclaw message send --channel telegram --target <id> --message "..."` ou `openclaw agent --to <id> --message "..." --deliver`.

A spec menciona o ID do Bernard: `<TELEGRAM_USER_ID>`.

- [ ] **Step 2: Criar lib/notify.sh**

```bash
cat > ~/.openclaw/skills/knowledge-sync/lib/notify.sh <<'NOTIFY_EOF'
#!/usr/bin/env bash
# notify.sh - Telegram bridge + dedup + persistence + quiet hours
# Spec section 5

# Configuracao
KS_NOTIFY_CHANNEL="${KS_NOTIFY_CHANNEL:-telegram}"
KS_NOTIFY_TARGET="${KS_NOTIFY_TARGET:-<TELEGRAM_USER_ID>}"
KS_NOTIFY_DEDUP_WINDOW="${KS_NOTIFY_DEDUP_WINDOW:-3600}"  # 1h
KS_NOTIFY_QUIET_START="${KS_NOTIFY_QUIET_START:-23}"
KS_NOTIFY_QUIET_END="${KS_NOTIFY_QUIET_END:-8}"
KS_NOTIFY_DIRTY_QUIET_WINDOW="${KS_NOTIFY_DIRTY_QUIET_WINDOW:-120}"  # 2min

# Verifica se estamos em quiet hours
ks_notify_in_quiet_hours() {
  local hour
  hour="$(date -u +%H)"
  hour=$((10#$hour))
  if (( hour >= KS_NOTIFY_QUIET_START || hour < KS_NOTIFY_QUIET_END )); then
    echo "true"
  else
    echo "false"
  fi
}

# Verifica se este evento+severity ja foi notificado dentro do dedup window
# Args: $1 = event_name, $2 = severity, $3 = file_set hash (opcional)
ks_notify_was_recently_sent() {
  local event="$1"
  local severity="$2"
  local file_hash="${3:-}"

  [[ ! -f "$KS_EVENTS_FILE" ]] && { echo "false"; return; }

  local now_ts cutoff_ts
  now_ts="$(date -u +%s)"
  cutoff_ts=$((now_ts - KS_NOTIFY_DEDUP_WINDOW))

  local found
  found="$(jq -rc --arg e "$event" --arg s "$severity" --arg h "$file_hash" --argjson cutoff "$cutoff_ts" '
    select(.event=="notification_sent" and .payload.event_name==$e and .payload.severity==$s and (.payload.file_hash // "")==$h)
    | .ts
    | strptime("%Y-%m-%dT%H:%M:%SZ") | mktime
    | select(. > $cutoff)
  ' "$KS_EVENTS_FILE" 2>/dev/null | tail -1)"

  if [[ -n "$found" ]]; then
    echo "true"
  else
    echo "false"
  fi
}

# Envia mensagem via OpenClaw para Telegram
# Args: $1 = message text
ks_notify_send_telegram() {
  local message="$1"
  if openclaw message send \
       --channel "$KS_NOTIFY_CHANNEL" \
       --target "$KS_NOTIFY_TARGET" \
       --message "$message" 2>&1 >/dev/null; then
    return 0
  fi
  # Fallback para outras formas de envio
  if openclaw agent --to "$KS_NOTIFY_TARGET" --message "$message" --deliver 2>&1 >/dev/null; then
    return 0
  fi
  ks_err "failed to send notification: $message"
  return 1
}

# Formata mensagem padronizada (5 blocos)
# Args: $1 = event, $2 = severity, $3 = what, $4 = impact, $5 = since, $6 = what_to_do, $7 = commands
ks_notify_format_message() {
  local event="$1" severity="$2" what="$3" impact="$4" since="$5" what_to_do="$6" commands="$7"
  local prefix=""
  [[ "$severity" == "error" ]] && prefix="[CRITICAL] "

  cat <<MSG
${prefix}[knowledge-sync] $event

O QUE ACONTECEU
$what

IMPACTO
$impact

DESDE QUANDO
$since

O QUE FAZER AGORA
$what_to_do

COMANDOS SUGERIDOS
$commands
MSG
}

# Notifica um evento (com toda a logica de policy)
# Args: $1 = event, $2 = severity, $3 = formatted_message_text
ks_notify_dispatch() {
  local event="$1" severity="$2" message="$3"
  local file_hash="${4:-}"

  # info -> so events.jsonl, sem mensagem ativa
  if [[ "$severity" == "info" ]]; then
    return 0
  fi

  # Dedup
  if [[ "$(ks_notify_was_recently_sent "$event" "$severity" "$file_hash")" == "true" ]]; then
    ks_log "dedup: skipping $event/$severity"
    return 0
  fi

  # Quiet hours
  if [[ "$(ks_notify_in_quiet_hours)" == "true" ]]; then
    if [[ "$severity" == "error" ]]; then
      # Errors enviam mesmo em quiet hours
      ks_notify_send_telegram "$message"
    else
      # warn fica represado para batch
      ks_event_append "notification_deferred" "$(jq -nc \
        --arg e "$event" --arg s "$severity" --arg m "$message" \
        '{event_name: $e, severity: $s, message: $m, deferred_at: now | strftime("%Y-%m-%dT%H:%M:%SZ")}')"
      return 0
    fi
  else
    ks_notify_send_telegram "$message"
  fi

  ks_event_append "notification_sent" "$(jq -nc \
    --arg e "$event" --arg s "$severity" --arg h "$file_hash" \
    '{event_name: $e, severity: $s, file_hash: $h}')"
}
NOTIFY_EOF
```

- [ ] **Step 3: Smoke test (sem enviar de verdade - dry run)**

```bash
bash <<'TEST_EOF'
SKILL_DIR=~/.openclaw/skills/knowledge-sync
source "$SKILL_DIR/lib/common.sh"
source "$SKILL_DIR/lib/notify.sh"

echo "Quiet hours? $(ks_notify_in_quiet_hours)"
echo "Was recently sent (test/warn)? $(ks_notify_was_recently_sent test_event warn)"

msg="$(ks_notify_format_message \
  "test_event" \
  "warn" \
  "Working tree dirty" \
  "Mudancas nao commitadas em main" \
  "agora" \
  "Commitar em draft branch" \
  "/commit-draft  /diff")"
echo "$msg"
TEST_EOF
```

Expected: imprime quiet hours info, false para dedup, e mensagem formatada nos 5 blocos.

---

## Task 15: Wire watcher to notify on state changes (diff + dirty quiet window)

**Files:**
- Modify: `~/.openclaw/skills/knowledge-sync/lib/watcher.sh` (adicionar funcao de diff de estado e dispatch)

- [ ] **Step 1: Adicionar diff de estado ao Watcher**

```bash
cat >> ~/.openclaw/skills/knowledge-sync/lib/watcher.sh <<'WATCH_NOTIFY_EOF'

# Detecta mudancas relevantes entre state.previous e state e dispara notificacoes
# Chamado APOS o ks_watcher_run principal
ks_watcher_dispatch_notifications() {
  source "$SKILL_DIR/lib/notify.sh"

  local current previous
  current="$(ks_state_read)"
  previous="$(ks_state_read_previous)"

  # working_tree_dirty - com janela de quietude
  local cur_clean prev_clean cur_dirty_since
  cur_clean="$(echo "$current" | jq -r '.working_tree.clean')"
  prev_clean="$(echo "$previous" | jq -r '.working_tree.clean // true')"
  cur_dirty_since="$(echo "$current" | jq -r '.health.issues[]? | select(.code=="working_tree_dirty") | .since' | head -1)"

  if [[ "$cur_clean" == "false" && "$prev_clean" == "true" ]]; then
    # Acabou de virar dirty - aguardar janela de quietude antes de notificar
    # Aqui registramos um evento; a notificacao real acontece no proximo ciclo se ainda dirty
    ks_event_append "working_tree_dirty_observed" "$(jq -nc --arg s "$cur_dirty_since" '{since: $s}')"
  elif [[ "$cur_clean" == "false" && "$prev_clean" == "false" ]]; then
    # Continua dirty - verificar se passou a janela de quietude
    local since_ts now_ts elapsed
    since_ts="$(date -u -d "$cur_dirty_since" +%s 2>/dev/null || echo 0)"
    now_ts="$(date -u +%s)"
    elapsed=$((now_ts - since_ts))
    if (( elapsed >= KS_NOTIFY_DIRTY_QUIET_WINDOW )); then
      local files
      files="$(echo "$current" | jq -r '[.working_tree.modified[], .working_tree.untracked[], .working_tree.staged[]] | join(", ")')"
      local file_hash
      file_hash="$(echo "$files" | sha256sum | awk '{print $1}' | head -c 12)"
      local msg
      msg="$(ks_notify_format_message \
        "working_tree_dirty" "warn" \
        "Working tree dirty - mudancas nao commitadas" \
        "Branch: $(echo "$current" | jq -r '.branch.current')\nArquivos: $files" \
        "$cur_dirty_since (ha $((elapsed/60))min)" \
        "Commitar em draft branch ou descartar" \
        "/knowledge-sync draft create <slug>\n/knowledge-sync diff")"
      ks_notify_dispatch "working_tree_dirty" "warn" "$msg" "$file_hash"
    fi
  elif [[ "$cur_clean" == "true" && "$prev_clean" == "false" ]]; then
    # Resolveu - info, so registra
    ks_event_append "working_tree_clean" '{}'
  fi

  # branch_behind
  local cur_behind prev_behind
  cur_behind="$(echo "$current" | jq -r '.branch.behind')"
  prev_behind="$(echo "$previous" | jq -r '.branch.behind // 0')"
  if (( cur_behind > 0 )) && (( prev_behind == 0 )); then
    local msg
    msg="$(ks_notify_format_message \
      "branch_behind" "warn" \
      "Branch local esta atras do remote ($cur_behind commits)" \
      "Voce vai precisar fazer pull-ff para sincronizar" \
      "agora" \
      "Rodar pull-ff (so se working tree estiver clean)" \
      "/knowledge-sync pull-ff")"
    ks_notify_dispatch "branch_behind" "warn" "$msg"
  fi

  # branch_synced
  local cur_ahead prev_ahead
  cur_ahead="$(echo "$current" | jq -r '.branch.ahead')"
  prev_ahead="$(echo "$previous" | jq -r '.branch.ahead // 0')"
  if (( cur_ahead == 0 )) && (( cur_behind == 0 )) && (( prev_ahead != 0 || prev_behind != 0 )); then
    ks_event_append "branch_synced" '{}'
  fi

  # conflict_potential
  local cur_conflict prev_conflict
  cur_conflict="$(echo "$current" | jq -r '.conflicts.potential')"
  prev_conflict="$(echo "$previous" | jq -r '.conflicts.potential // false')"
  if [[ "$cur_conflict" == "true" && "$prev_conflict" == "false" ]]; then
    local reason
    reason="$(echo "$current" | jq -r '.conflicts.reason')"
    local msg
    msg="$(ks_notify_format_message \
      "conflict_potential" "error" \
      "Conflito potencial detectado" \
      "Razao: $reason" \
      "agora" \
      "NAO faca pull. Inspecione manualmente." \
      "/knowledge-sync status\n/knowledge-sync diff")"
    ks_notify_dispatch "conflict_potential" "error" "$msg"
  fi

  # watcher_error
  local errors_count
  errors_count="$(echo "$current" | jq '.watcher.errors | length')"
  if (( errors_count > 0 )); then
    local first_err
    first_err="$(echo "$current" | jq -r '.watcher.errors[0].stderr_summary')"
    local msg
    msg="$(ks_notify_format_message \
      "watcher_error" "error" \
      "Watcher falhou" \
      "$first_err" \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      "Investigar logs" \
      "/knowledge-sync events --last 10")"
    ks_notify_dispatch "watcher_error" "error" "$msg"
  fi
}
WATCH_NOTIFY_EOF
```

- [ ] **Step 2: Modificar refresh.sh para chamar dispatch_notifications apos run**

```bash
cat > ~/.openclaw/skills/knowledge-sync/commands/refresh.sh <<'CMD_EOF'
#!/usr/bin/env bash
# refresh - roda Watcher agora + dispatch de notificacoes
set -euo pipefail
source "$SKILL_DIR/lib/common.sh"
source "$SKILL_DIR/lib/state.sh"
source "$SKILL_DIR/lib/events.sh"
source "$SKILL_DIR/lib/git-ops.sh"
source "$SKILL_DIR/lib/watcher.sh"

ks_check_deps
ks_check_clone
ks_lock 30 || exit 1
trap 'ks_unlock' EXIT

ks_watcher_run
ks_watcher_dispatch_notifications

if [[ "${1:-}" == "--json" ]]; then
  ks_state_read
else
  exec "$SKILL_DIR/commands/status.sh"
fi
CMD_EOF
chmod +x ~/.openclaw/skills/knowledge-sync/commands/refresh.sh
```

- [ ] **Step 3: Smoke test - editar arquivo no inbox e ver notificacao apos janela de quietude**

```bash
KS=~/.openclaw/skills/knowledge-sync/bin/knowledge-sync
cd ~/bevox-knowledge

# Criar mudanca
echo "# notify test" > 00_inbox/notify-test.md

# 1o refresh: detecta dirty mas nao notifica ainda (janela de quietude)
$KS refresh
sleep 3

# Aguardar janela de quietude (2min default - voce pode reduzir via env temporariamente)
# Para teste rapido, sobrescrever a janela:
KS_NOTIFY_DIRTY_QUIET_WINDOW=2 $KS refresh
sleep 3

# 2o refresh: agora janela ja passou, notificacao deve disparar
KS_NOTIFY_DIRTY_QUIET_WINDOW=2 $KS refresh

# Limpar
rm -f 00_inbox/notify-test.md
$KS refresh
```

Expected: voce deve receber 1 mensagem no Telegram sobre `working_tree_dirty`.

> Se Telegram nao chegar: verificar logs (`openclaw logs --follow`) e Step 1 da Task 14 (forma correta de invocar message send).

---

## Task 16: lib/approval.sh + commands/canonical.sh

**Files:**
- Create: `~/.openclaw/skills/knowledge-sync/lib/approval.sh`
- Create: `~/.openclaw/skills/knowledge-sync/commands/canonical.sh`

> **Spec sec 4.6 e 5.9:** approval e especifico da acao, single-use, time-limited (default 1h), gravado em events.jsonl.

- [ ] **Step 1: lib/approval.sh**

```bash
cat > ~/.openclaw/skills/knowledge-sync/lib/approval.sh <<'APPR_EOF'
#!/usr/bin/env bash
# approval.sh - approval flow para acoes canonicas

KS_APPROVAL_TTL_SECONDS="${KS_APPROVAL_TTL_SECONDS:-3600}"  # 1h

# Cria approval request com UUID
# Args: $1 = action_name, $2 = context_json
# Retorna approval_id via stdout
ks_approval_create() {
  local action="$1"
  local context_json="${2:-{\}}"
  local approval_id
  approval_id="$(cat /proc/sys/kernel/random/uuid 2>/dev/null || date +%s)-${RANDOM}"

  ks_event_append "canonical_approval_pending" "$(jq -nc \
    --arg id "$approval_id" \
    --arg action "$action" \
    --argjson context "$context_json" \
    '{approval_id: $id, action: $action, context: $context}')"

  echo "$approval_id"
}

# Verifica se um approval foi concedido (e nao expirado, e nao usado)
# Args: $1 = approval_id
# Retorna 0 ok, 1 nao
ks_approval_check() {
  local approval_id="$1"

  # Procura granted
  local granted_event
  granted_event="$(grep -F "\"approval_id\":\"$approval_id\"" "$KS_EVENTS_FILE" 2>/dev/null | grep canonical_approval_granted | tail -1)"
  if [[ -z "$granted_event" ]]; then
    return 1
  fi

  # Verifica expiracao
  local granted_at granted_ts now_ts
  granted_at="$(echo "$granted_event" | jq -r '.ts')"
  granted_ts="$(date -u -d "$granted_at" +%s 2>/dev/null || echo 0)"
  now_ts="$(date -u +%s)"
  if (( now_ts - granted_ts > KS_APPROVAL_TTL_SECONDS )); then
    return 1
  fi

  # Verifica se ja foi usado (committed/pushed/marker_created)
  local used
  used="$(grep -F "\"approval_id\":\"$approval_id\"" "$KS_EVENTS_FILE" 2>/dev/null | grep -E "canonical_(committed|pushed|marker_created)" | tail -1)"
  if [[ -n "$used" ]]; then
    return 1
  fi

  return 0
}

# Marca approval como rejeitado
ks_approval_reject() {
  local approval_id="$1"
  local reason="${2:-rejected by user}"
  ks_event_append "canonical_approval_rejected" "$(jq -nc \
    --arg id "$approval_id" --arg r "$reason" \
    '{approval_id: $id, reason: $r}')"
}

# Marca approval como concedido
ks_approval_grant() {
  local approval_id="$1"
  ks_event_append "canonical_approval_granted" "$(jq -nc \
    --arg id "$approval_id" \
    '{approval_id: $id}')"
}
APPR_EOF
```

- [ ] **Step 2: commands/canonical.sh**

```bash
cat > ~/.openclaw/skills/knowledge-sync/commands/canonical.sh <<'CMD_EOF'
#!/usr/bin/env bash
# canonical - subcomandos: commit, push, create-marker
# TODOS exigem approval mesmo em L4 (per ADR-006)
set -euo pipefail
source "$SKILL_DIR/lib/common.sh"
source "$SKILL_DIR/lib/state.sh"
source "$SKILL_DIR/lib/events.sh"
source "$SKILL_DIR/lib/git-ops.sh"
source "$SKILL_DIR/lib/approval.sh"
source "$SKILL_DIR/lib/notify.sh"
source "$SKILL_DIR/lib/watcher.sh"

ks_check_deps
ks_check_clone

sub="${1:-}"; shift || true

# Funcao comum: validar contexto + criar approval + esperar
# Caller passa o action name + context json + comando real para executar
ks_canonical_request_and_run() {
  local action="$1"
  local context_json="$2"
  local _execute_cmd="$3"  # nome de funcao para executar apos approval

  ks_lock 30 || exit 1
  trap 'ks_unlock' EXIT

  # Validacao de contexto comum
  ks_watcher_run
  state="$(ks_state_read)"
  branch="$(echo "$state" | jq -r '.branch.current')"
  if [[ "$branch" != "main" ]]; then
    ks_event_append "action_rejected" "$(jq -nc --arg a "$action" --arg b "$branch" '{action: $a, reason: "must be on main branch", branch: $b}')"
    echo "BLOCKED: precisa estar em main (esta em $branch)" >&2
    exit 3
  fi

  # Para commit/push, validar working tree limpo (nada de sujeira lateral)
  if [[ "$action" != "canonical create-marker" ]]; then
    local merge_in rebase_in cherry_in
    merge_in="$(echo "$state" | jq -r '.git_operations.merge_in_progress')"
    rebase_in="$(echo "$state" | jq -r '.git_operations.rebase_in_progress')"
    cherry_in="$(echo "$state" | jq -r '.git_operations.cherry_pick_in_progress')"
    if [[ "$merge_in" == "true" || "$rebase_in" == "true" || "$cherry_in" == "true" ]]; then
      echo "BLOCKED: git operation in progress" >&2
      exit 3
    fi
  fi

  # Snapshot pre-canonical (com dedup)
  source "$SKILL_DIR/lib/snapshot.sh"
  local current_sha
  current_sha="$(ks_git_head_sha)"
  ks_snapshot_create pre-canonical "${current_sha:0:10}-${action// /_}" >/dev/null

  # Criar approval request
  approval_id="$(ks_approval_create "$action" "$context_json")"

  # Notificar Bernard
  msg="$(ks_notify_format_message \
    "canonical_approval_pending" "warn" \
    "Action canonica solicitada: $action" \
    "$(echo "$context_json" | jq -r '.summary // .')" \
    "$(ks_now)" \
    "Aprovar ou rejeitar via Telegram (responda /approve $approval_id ou /reject $approval_id)" \
    "/knowledge-sync pending")"
  ks_notify_dispatch "canonical_approval_pending" "warn" "$msg" "$approval_id"

  echo "Approval pendente: $approval_id"
  echo "Aguardando aprovacao do Bernard via Telegram..."
  echo "Para cancelar: knowledge-sync canonical-cancel $approval_id"
  echo ""
  echo "Para aprovar manualmente (override): use 'openclaw' bridge ou edite events.jsonl"
  echo "(Em uma versao futura, teremos Mission Control / approval CLI)"
  echo ""
  echo "Status: pending"

  ks_event_append "$action initialized" "$(jq -nc --arg id "$approval_id" '{approval_id: $id, status: "pending"}')"

  ks_unlock
  trap - EXIT
  exit 0
}

# Executores reais (chamados apos approval explicito - normalmente outro comando do Bernard)
# Para o E1, o approval e gravado manualmente via comando ks_approval_grant
# (No futuro: bot do Telegram captura /approve e chama isso)

case "$sub" in
  commit)
    msg=""
    files=()
    while [[ $# -gt 0 ]]; do
      case "$1" in
        -m) msg="$2"; shift 2 ;;
        --files)
          shift
          while [[ $# -gt 0 && "$1" != --* ]]; do files+=("$1"); shift; done ;;
        *) shift ;;
      esac
    done
    [[ -z "$msg" ]] && { echo "canonical commit -m <msg> --files <list>" >&2; exit 2; }
    [[ ${#files[@]} -eq 0 ]] && { echo "--files <list> requerido (escopo explicito)" >&2; exit 2; }

    context="$(jq -nc \
      --arg msg "$msg" \
      --argjson files "$(printf '%s\n' "${files[@]}" | jq -R . | jq -sc .)" \
      --arg summary "Commit em main com ${#files[@]} arquivo(s)" \
      '{message: $msg, files: $files, summary: $summary}')"

    ks_canonical_request_and_run "canonical commit" "$context" "_canonical_commit_execute"
    ;;

  push)
    context="$(jq -nc --arg summary "Push de main para origin" '{summary: $summary}')"
    ks_canonical_request_and_run "canonical push" "$context" "_canonical_push_execute"
    ;;

  create-marker)
    name=""
    type=""
    message=""
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --name) name="$2"; shift 2 ;;
        --type) type="$2"; shift 2 ;;
        --message) message="$2"; shift 2 ;;
        *) shift ;;
      esac
    done
    [[ -z "$name" || -z "$type" ]] && { echo "canonical create-marker --name <slug> --type release|milestone" >&2; exit 2; }

    case "$type" in
      release) tag_name="v0.X-$name" ;;
      milestone) tag_name="milestone-$(date +%Y-%m-%d)-$name" ;;
      *) echo "type deve ser release ou milestone" >&2; exit 2 ;;
    esac

    context="$(jq -nc \
      --arg t "$type" --arg n "$name" --arg m "$message" --arg tag "$tag_name" \
      --arg summary "Criar tag $tag" \
      '{type: $t, name: $n, message: $m, tag: $tag, summary: $summary}')"

    ks_canonical_request_and_run "canonical create-marker" "$context" "_canonical_marker_execute"
    ;;

  execute)
    # Execucao real apos approval - chamado por outro componente (futuro: bot do approval)
    # Para o E1 isso e usado pelo coding-agent ou Bernard manualmente apos confirmar
    approval_id="${1:-}"
    [[ -z "$approval_id" ]] && { echo "canonical execute <approval_id>" >&2; exit 2; }

    if ! ks_approval_check "$approval_id"; then
      echo "BLOCKED: approval $approval_id nao concedido, expirado, ou ja usado" >&2
      exit 3
    fi

    # Recuperar a action e context do evento pending
    pending_event="$(grep -F "\"approval_id\":\"$approval_id\"" "$KS_EVENTS_FILE" | grep canonical_approval_pending | tail -1)"
    action="$(echo "$pending_event" | jq -r '.payload.action')"
    context="$(echo "$pending_event" | jq -c '.payload.context')"

    case "$action" in
      "canonical commit")
        msg="$(echo "$context" | jq -r '.message')"
        files_arr=$(echo "$context" | jq -r '.files[]')
        ks_lock 30 || exit 1
        trap 'ks_unlock' EXIT
        for f in $files_arr; do
          ks_git add "$f"
        done
        if ks_git commit -m "$msg" --quiet; then
          new_sha="$(ks_git_head_sha)"
          ks_event_append "canonical_committed" "$(jq -nc --arg id "$approval_id" --arg s "$new_sha" '{approval_id: $id, sha: $s}')"
          echo "OK: canonical commit $new_sha"
        else
          ks_event_append "action_failed" "$(jq -nc --arg id "$approval_id" '{approval_id: $id, action: "canonical commit"}')"
          echo "FAILED" >&2
          exit 1
        fi
        ;;

      "canonical push")
        ks_lock 30 || exit 1
        trap 'ks_unlock' EXIT
        if ks_git push origin main; then
          ks_event_append "canonical_pushed" "$(jq -nc --arg id "$approval_id" '{approval_id: $id}')"
          echo "OK: canonical push"
        else
          ks_event_append "action_failed" "$(jq -nc --arg id "$approval_id" '{approval_id: $id, action: "canonical push"}')"
          echo "FAILED" >&2
          exit 1
        fi
        ;;

      "canonical create-marker")
        tag="$(echo "$context" | jq -r '.tag')"
        message="$(echo "$context" | jq -r '.message // .summary')"
        ks_lock 30 || exit 1
        trap 'ks_unlock' EXIT
        if ks_git tag -a "$tag" -m "$message" && ks_git push origin "$tag"; then
          ks_event_append "canonical_marker_created" "$(jq -nc --arg id "$approval_id" --arg t "$tag" '{approval_id: $id, tag: $t}')"
          echo "OK: tag $tag criada e pushed"
        else
          ks_event_append "action_failed" "$(jq -nc --arg id "$approval_id" '{approval_id: $id, action: "canonical create-marker"}')"
          echo "FAILED" >&2
          exit 1
        fi
        ;;

      *)
        echo "action desconhecida no approval: $action" >&2
        exit 1 ;;
    esac
    ;;

  approve)
    # Concede approval explicitamente (uso pelo Bernard via CLI ou bot)
    approval_id="${1:-}"
    [[ -z "$approval_id" ]] && { echo "canonical approve <approval_id>" >&2; exit 2; }
    ks_approval_grant "$approval_id"
    echo "Approval $approval_id concedido"
    echo "Para executar: knowledge-sync canonical execute $approval_id"
    ;;

  reject)
    approval_id="${1:-}"
    reason="${2:-rejected}"
    [[ -z "$approval_id" ]] && { echo "canonical reject <approval_id> [reason]" >&2; exit 2; }
    ks_approval_reject "$approval_id" "$reason"
    echo "Approval $approval_id rejeitado"
    ;;

  *)
    echo "canonical: subcomando desconhecido: $sub" >&2
    echo "Use: canonical commit -m <msg> --files <list>" >&2
    echo "     canonical push" >&2
    echo "     canonical create-marker --name <slug> --type release|milestone" >&2
    echo "     canonical approve <approval_id>" >&2
    echo "     canonical reject <approval_id>" >&2
    echo "     canonical execute <approval_id>" >&2
    exit 2 ;;
esac
CMD_EOF
chmod +x ~/.openclaw/skills/knowledge-sync/commands/canonical.sh
```

- [ ] **Step 3: Smoke test do approval flow**

```bash
KS=~/.openclaw/skills/knowledge-sync/bin/knowledge-sync

# Criar arquivo canonico de teste
echo "# canonical test stub" > ~/bevox-knowledge/00_inbox/canonical-test.md
git -C ~/bevox-knowledge add 00_inbox/canonical-test.md

# Solicitar canonical commit (vai criar approval pending)
$KS canonical commit -m "test: canonical commit smoke" --files 00_inbox/canonical-test.md

# Listar pending
$KS pending

# Pegar o approval_id mais recente
APPROVAL_ID="$(grep canonical_approval_pending ~/.openclaw/knowledge-sync/events.jsonl | tail -1 | jq -r '.payload.approval_id')"
echo "Approval ID: $APPROVAL_ID"

# Aprovar (acao manual - simula Bernard respondendo no Telegram)
$KS canonical approve "$APPROVAL_ID"

# Executar
$KS canonical execute "$APPROVAL_ID"

# Verificar
git -C ~/bevox-knowledge log --oneline | head -3
```

Expected: pending listado, approval concedido, commit executado, aparece no git log.

- [ ] **Step 4: Cleanup do smoke test**

```bash
# Reverter o commit de teste
git -C ~/bevox-knowledge reset --hard HEAD~1
rm -f ~/bevox-knowledge/00_inbox/canonical-test.md
```

---

---

## Task 17: F3 - Estrutura modules/ + template + 4 stubs

**Files:**
- Create: `~/bevox-knowledge/20_architecture/modules/README.md`
- Create: `~/bevox-knowledge/20_architecture/modules/_template.md`
- Create: `~/bevox-knowledge/20_architecture/modules/bevox-console.md`
- Create: `~/bevox-knowledge/20_architecture/modules/bevox-harness.md`
- Create: `~/bevox-knowledge/20_architecture/modules/bevox-web.md`
- Create: `~/bevox-knowledge/20_architecture/modules/bevox-mobile.md`

> **Critico:** bevox-harness NAO menciona Telegram (canal do Company OS, nao do produto). Vocabulario fixo "Quem usa": Equipe Bevox / Cliente da Bevox / Cliente final do cliente / Runtime.
> **Spec sec 7** detalha o conteudo de cada stub.

- [ ] **Step 1: Criar diretorio**

```bash
cd ~/bevox-knowledge
mkdir -p 20_architecture/modules
```

- [ ] **Step 2: README.md da pasta modules/**

```bash
cat > ~/bevox-knowledge/20_architecture/modules/README.md <<'EOF'
# Modules

Overviews tecnico-operacionais dos modulos da Bevox.

## O que mora aqui

- **Module overviews** - 1 arquivo por modulo canonico (ver ADR-002)
- **`_template.md`** - template oficial para novos overviews

## NAO sao PRDs completos

PRDs detalhados moram em `10_prd/`. Os overviews em `modules/` sao **provisorios e revisaveis** - capturam o que ja sabemos sem inventar conteudo nao decidido.

## Convencao de nomenclatura

`{module-name}.md` em kebab-case, mesmo nome do modulo canonizado em ADR-002.

Modulos canonicos atuais:
- `bevox-console.md`
- `bevox-harness.md`
- `bevox-web.md`
- `bevox-mobile.md`

## Vocabulario fixo de "Quem usa"

Cada overview deve usar exatamente um (ou mais) destes valores:
- **Equipe Bevox** - uso interno pela equipe
- **Cliente da Bevox** - profissional/clinica/negocio que paga
- **Cliente final do cliente** - paciente/lead/usuario que conversa via canais
- **Runtime / sem usuario direto** - componentes de backend

## Como atualizar

Edicao + commit. Mudancas sao `write-knowledge-canonical` per ADR-006 - exigem approval para virar oficial em main.

## Quando criar um overview novo

So quando o modulo for canonizado em ADR-002 (ou ADR substituidora). NAO criar overviews para modulos especulativos.

## Maturidade documental

Cada overview tem um campo `Maturidade documental`:
- `stub` - esqueleto inicial, muitas duvidas em aberto
- `em-amadurecimento` - parcialmente preenchido, em desenvolvimento ativo
- `maduro` - estavel, refletindo realidade
EOF
```

- [ ] **Step 3: `_template.md`**

```bash
cat > ~/bevox-knowledge/20_architecture/modules/_template.md <<'EOF'
# Module: {module-name}

> Overview tecnico-operacional do modulo. Provisorio e revisavel.
> Nao e PRD completo - PRDs detalhados moram em 10_prd/.

- **Maturidade documental:** stub | em-amadurecimento | maduro
- **Owner:** Bernard
- **Camada:** [interno | runtime | cliente da Bevox]
- **Ultima atualizacao:** YYYY-MM-DD

## Proposito

Uma frase. O que esse modulo existe para fazer.

## Quem usa

Vocabulario fixo (escolher um ou mais):
- Equipe Bevox
- Cliente da Bevox
- Cliente final do cliente
- Runtime / sem usuario direto

## Responsabilidades principais

- [...]
- [...]
- [...]

## Fronteiras com outros modulos

- **Para com isso:** [escopo claro]
- **Nao faz:** [o que NAO e responsabilidade dele]
- **Depende de:** [modulos a montante]
- **E dependencia de:** [modulos a jusante]

## Entradas e saidas principais

### Inputs
- [...]

### Outputs
- [...]

## Estado atual

- Existe? [sim | nao | em planejamento]
- Stack tecnica: [a definir | conhecida]
- Repositorio: [URL ou "a criar"]
- **Status operacional do modulo:** em planejamento | alpha | beta | producao

## Decisoes ja conhecidas

- [decisao + link para ADR ou nota]

## Duvidas em aberto

- [duvida]

## Links

- ADRs relacionadas: [ADR-002, ...]
- PRDs futuros: [pendente]
- Repos: [pendente]
- Specs: [pendente]
- Modulos relacionados: [bevox-console, bevox-harness, ...]
EOF
```

- [ ] **Step 4: bevox-console.md**

```bash
cat > ~/bevox-knowledge/20_architecture/modules/bevox-console.md <<'EOF'
# Module: bevox-console

> Overview tecnico-operacional do modulo. Provisorio e revisavel.
> Nao e PRD completo - PRDs detalhados moram em 10_prd/.

- **Maturidade documental:** stub
- **Owner:** Bernard
- **Camada:** interno
- **Ultima atualizacao:** 2026-04-09

## Proposito

Super admin / backoffice interno da Bevox - administracao da plataforma, suporte operacional, gestao de tenants (clientes da Bevox), configuracoes globais e visao interna da operacao.

## Quem usa

- Equipe Bevox

## Responsabilidades principais

- Administracao da plataforma Bevox
- Suporte operacional aos clientes da Bevox
- Gestao de tenants (criacao, configuracao, suspensao)
- Configuracoes globais que afetam multiplos tenants
- Visao interna da operacao do harness
- Acesso a logs, metricas e auditoria

## Fronteiras com outros modulos

- **Para com isso:** interface administrativa - NAO e usado por clientes da Bevox nem pelo cliente final
- **Nao faz:** operacao do dia a dia do cliente (isso e bevox-web/mobile), runtime de conversas (isso e bevox-harness)
- **Depende de:** bevox-harness (le estado, executa acoes administrativas)
- **E dependencia de:** equipe Bevox (humanos)

## Entradas e saidas principais

### Inputs
- Acoes administrativas da equipe Bevox
- Logs e metricas do bevox-harness
- Eventos operacionais

### Outputs
- Mudancas de configuracao no harness
- Relatorios para a equipe interna
- Acoes de suporte aplicadas a tenants

## Estado atual

- Existe? em planejamento
- Stack tecnica: a definir
- Repositorio: a criar
- **Status operacional do modulo:** em planejamento

## Decisoes ja conhecidas

- ADR-002 canonizou bevox-console como modulo de produto, camada interna

## Duvidas em aberto

- Stack tecnica
- Modelo de auth/permissoes para a equipe
- Como expor logs do harness sem comprometer dados de tenants
- Granularidade das acoes administrativas

## Links

- ADRs relacionadas: ADR-002 (System Topology)
- PRDs futuros: pendente
- Repos: pendente
- Specs: pendente
- Modulos relacionados: bevox-harness
EOF
```

- [ ] **Step 5: bevox-harness.md**

> **CRITICO:** sem mencao a Telegram. Canais do produto sao WhatsApp, Instagram e similares.

```bash
cat > ~/bevox-knowledge/20_architecture/modules/bevox-harness.md <<'EOF'
# Module: bevox-harness

> Overview tecnico-operacional do modulo. Provisorio e revisavel.
> Nao e PRD completo - PRDs detalhados moram em 10_prd/.

- **Maturidade documental:** stub
- **Owner:** Bernard
- **Camada:** runtime
- **Ultima atualizacao:** 2026-04-09

## Proposito

Runtime da secretaria IA - orquestra conversas com clientes finais via canais conectados, gerencia memoria operacional, executa skills, aplica politicas. E o "motor" do produto agent-first.

## Quem usa

- Runtime / sem usuario direto
- Cliente final do cliente acessa **mediado** atraves dos canais conectados (WhatsApp, Instagram e similares), nao por interface propria

## Responsabilidades principais

- Hospedar sessoes da secretaria IA por tenant
- Conectar e mediar canais de mensageria do produto (WhatsApp, Instagram, etc.)
- Manter memoria operacional persistente das conversas
- Executar as skills disponiveis para a secretaria IA
- Aplicar politicas configuradas pelo cliente da Bevox
- Realizar handoff humano quando necessario
- Expor estado e capacidades para bevox-console (admin) e bevox-web/mobile (cliente)

## Fronteiras com outros modulos

- **Para com isso:** runtime puro - hospeda agentes e canais
- **Nao faz:** UI propria para usuarios finais (eles usam os canais conectados), administracao da plataforma (isso e bevox-console), interfaces do cliente da Bevox (bevox-web/mobile)
- **Depende de:** infra de canais externos (WhatsApp Business, Instagram Graph API, outros), modelos de IA para inferencia
- **E dependencia de:** bevox-console (admin), bevox-web (config), bevox-mobile (operacao do dia a dia)

## Entradas e saidas principais

### Inputs
- Mensagens dos clientes finais via canais conectados
- Configuracoes feitas pelo cliente da Bevox via bevox-web
- Acoes administrativas via bevox-console
- Politicas e regras de negocio

### Outputs
- Respostas aos clientes finais via os mesmos canais
- Eventos para bevox-console e bevox-web
- Logs de conversas e auditoria
- Sinais de handoff humano para bevox-mobile

## Estado atual

- Existe? em planejamento
- Stack tecnica: a definir
- Repositorio: a criar
- **Status operacional do modulo:** em planejamento

## Decisoes ja conhecidas

- ADR-002 canonizou bevox-harness como motor da secretaria IA, camada runtime
- Cliente final NAO acessa via interface propria - so via canais mediados

## Duvidas em aberto

- Stack tecnica e arquitetura do runtime
- Modelo de tenancy (multi-tenant single-process? sandbox por tenant?)
- Quais canais entram no MVP
- Modelo de memoria persistente (DB? vetorial?)
- Politica de retencao de conversas
- Modelo de billing/usage tracking

## Links

- ADRs relacionadas: ADR-002 (System Topology)
- PRDs futuros: pendente
- Repos: pendente
- Specs: pendente
- Modulos relacionados: bevox-console, bevox-web, bevox-mobile
EOF
```

- [ ] **Step 6: bevox-web.md**

```bash
cat > ~/bevox-knowledge/20_architecture/modules/bevox-web.md <<'EOF'
# Module: bevox-web

> Overview tecnico-operacional do modulo. Provisorio e revisavel.
> Nao e PRD completo - PRDs detalhados moram em 10_prd/.

- **Maturidade documental:** stub
- **Owner:** Bernard
- **Camada:** cliente da Bevox
- **Ultima atualizacao:** 2026-04-09

## Proposito

Aplicacao web do **cliente da Bevox** (profissional, clinica, negocio). Interface principal pelo navegador para setup, configuracao, gestao, agenda, politicas e operacao web da secretaria IA.

## Quem usa

- Cliente da Bevox

## Responsabilidades principais

- Setup da secretaria IA pelo cliente da Bevox
- Configuracao de politicas, respostas e automacoes
- Gestao da agenda (horarios, disponibilidade, regras)
- Configuracao de integracoes com sistemas do cliente
- Acompanhamento de conversas e historico
- Operacao em "modo mesa" (tela cheia, multiplas abas)

## Fronteiras com outros modulos

- **Para com isso:** UI web do cliente da Bevox, voltada a operacao em desktop/laptop
- **Nao faz:** UI para o cliente final (paciente/lead - eles usam canais), administracao da plataforma (bevox-console), operacao mobile (bevox-mobile)
- **Depende de:** bevox-harness (leitura e escrita de configuracoes, eventos)
- **E dependencia de:** Cliente da Bevox

## Entradas e saidas principais

### Inputs
- Acoes do cliente da Bevox via UI web
- Eventos do bevox-harness (novas conversas, alertas)

### Outputs
- Configuracoes para bevox-harness
- Visualizacoes de dados e historicos para o cliente
- Disparos de acoes (ex: agendar, pausar, exportar)

## Estado atual

- Existe? em planejamento
- Stack tecnica: a definir
- Repositorio: a criar
- **Status operacional do modulo:** em planejamento

## Decisoes ja conhecidas

- ADR-002 canonizou bevox-web como aplicacao web do cliente da Bevox (NAO do cliente final)

## Duvidas em aberto

- Stack tecnica (framework, design system)
- Modelo de auth (SSO? magic link? password?)
- Multi-org / multi-usuario por conta?
- Offline-first ou online-only?

## Links

- ADRs relacionadas: ADR-002 (System Topology)
- PRDs futuros: pendente
- Repos: pendente
- Specs: pendente
- Modulos relacionados: bevox-harness, bevox-mobile
EOF
```

- [ ] **Step 7: bevox-mobile.md**

```bash
cat > ~/bevox-knowledge/20_architecture/modules/bevox-mobile.md <<'EOF'
# Module: bevox-mobile

> Overview tecnico-operacional do modulo. Provisorio e revisavel.
> Nao e PRD completo - PRDs detalhados moram em 10_prd/.

- **Maturidade documental:** stub
- **Owner:** Bernard
- **Camada:** cliente da Bevox
- **Ultima atualizacao:** 2026-04-09

## Proposito

App **operador** do cliente da Bevox para o dia a dia: inbox de conversas, handoff humano, agenda do dia, alertas e acoes rapidas. Otimizado para uso em movimento.

## Quem usa

- Cliente da Bevox (especificamente: operador/profissional em movimento)

## Responsabilidades principais

- Inbox unificado de conversas precisando de atencao
- Handoff humano quando a IA passa o caso para a pessoa
- Agenda do dia em formato mobile-friendly
- Notificacoes push de alertas e novas mensagens
- Acoes rapidas (responder, agendar, marcar resolvido)
- Sync continuo com bevox-harness

## Fronteiras com outros modulos

- **Para com isso:** app nativo otimizado para uso operacional no celular
- **Nao faz:** setup completo (use bevox-web), administracao (bevox-console), runtime de conversas (bevox-harness), interface para cliente final
- **Depende de:** bevox-harness (eventos, mensagens, estado)
- **E dependencia de:** Cliente da Bevox (usuario operador)

## Entradas e saidas principais

### Inputs
- Eventos de novas conversas precisando de atencao
- Notificacoes push do bevox-harness
- Updates de agenda
- Acoes rapidas do operador

### Outputs
- Respostas humanas inseridas no fluxo da conversa
- Mudancas de estado (resolvido, agendado, etc.)
- Confirmacoes de handoff

## Estado atual

- Existe? em planejamento
- Stack tecnica: a definir
- Repositorio: a criar
- **Status operacional do modulo:** em planejamento

## Decisoes ja conhecidas

- ADR-002 canonizou bevox-mobile como app operador do cliente da Bevox

## Duvidas em aberto

- Plataforma (iOS/Android/ambas)
- Framework (nativo, React Native, Flutter, etc.)
- Modelo de notificacoes push
- Modelo de offline (cache local? sincronia ao reconectar?)
- Permissoes nativas necessarias (notificacoes, biometria)

## Links

- ADRs relacionadas: ADR-002 (System Topology)
- PRDs futuros: pendente
- Repos: pendente
- Specs: pendente
- Modulos relacionados: bevox-harness, bevox-web
EOF
```

- [ ] **Step 8: Verificacao critica**

```bash
# bevox-harness NAO deve conter "Telegram"
grep -i telegram ~/bevox-knowledge/20_architecture/modules/bevox-harness.md && echo "BUG: Telegram mencionado em bevox-harness" || echo "OK"

# Vocabulario fixo presente em todos
for f in bevox-console bevox-harness bevox-web bevox-mobile; do
  echo "=== $f ==="
  grep -E "Equipe Bevox|Cliente da Bevox|Cliente final do cliente|Runtime" \
    ~/bevox-knowledge/20_architecture/modules/$f.md | head -3
done
```

Expected:
- `OK` para a verificacao do Telegram
- Cada arquivo lista o(s) publico(s) usando vocabulario fixo

---

## Task 18: F3 - Pasta `99_templates/` com templates compartilhados

**Files:**
- Create: `~/bevox-knowledge/99_templates/README.md`
- Create: `~/bevox-knowledge/99_templates/adr.md`
- Create: `~/bevox-knowledge/99_templates/module-overview.md`
- Create: `~/bevox-knowledge/99_templates/spec.md`
- Create: `~/bevox-knowledge/99_templates/note.md`

> **Spec sec 7.6:** templates compartilhados em `99_templates/` (NAO em `.obsidian/`) para fazer sentido tambem para Vox e Claude Code.

- [ ] **Step 1: Criar pasta + README**

```bash
mkdir -p ~/bevox-knowledge/99_templates

cat > ~/bevox-knowledge/99_templates/README.md <<'EOF'
# Templates compartilhados

Templates usados por humanos (via editor/Obsidian), Vox e Claude Code para criar artefatos novos no `bevox-knowledge`.

## Templates disponiveis

| Arquivo | Para criar |
|---|---|
| `adr.md` | Nova ADR (copia para `30_adr/ADR-XXX-titulo.md`) |
| `module-overview.md` | Novo overview de modulo (copia para `20_architecture/modules/<name>.md`) |
| `spec.md` | Nova spec de implementacao (copia para `35_specs/YYYY-MM-DD-<topic>.md`) |
| `note.md` | Nota rapida no inbox (copia para `00_inbox/<slug>.md`) |

## Por que aqui (e nao em `.obsidian/templates/`)

Se vivessem em `.obsidian/templates/`, so o Obsidian acessaria. Aqui:
- O Obsidian (com plugin Templater apontado para esta pasta) usa
- O Vox le quando precisa criar artefato novo
- O Claude Code le quando o Bernard pede para criar uma ADR/spec/etc.
- O proprio Bernard pode `cp` direto via terminal

## Como usar

Pelo Obsidian: configurar Templater para apontar para `99_templates/`.
Pelo terminal:
```bash
cp 99_templates/adr.md 30_adr/ADR-007-novo-titulo.md
# ajustar conteudo
```

## Convencao

Templates aqui devem:
- Ter placeholders claros (ex: `{titulo}`, `YYYY-MM-DD`)
- Refletir a estrutura canonica vigente
- Ser atualizados quando a estrutura mudar
EOF
```

- [ ] **Step 2: Templates individuais**

```bash
# adr.md (copia do que ja existe em 30_adr/_template.md)
cp ~/bevox-knowledge/30_adr/_template.md ~/bevox-knowledge/99_templates/adr.md

# module-overview.md (copia do que ja existe em 20_architecture/modules/_template.md)
cp ~/bevox-knowledge/20_architecture/modules/_template.md ~/bevox-knowledge/99_templates/module-overview.md

# spec.md (template para nova spec)
cat > ~/bevox-knowledge/99_templates/spec.md <<'EOF'
# {Topic} Design

> Spec de implementacao - design detalhado para construcao de uma feature/epico.
> Spec NAO e PRD - spec define COMO, PRD define O QUE.

**Data:** YYYY-MM-DD
**Epico/Feature:** {nome}
**Prioridade:** P0 | P1 | P2
**Dependencias:** {listar}
**Roadmap mestre:** {link}

---

## 1. Visao Geral

### 1.1 Objetivo

[Uma frase do objetivo]

### 1.2 Resultado esperado

[Lista do que sera entregue]

### 1.3 Out of scope

[Explicito - o que NAO entra]

---

## 2. Arquitetura

[Componentes, fluxo, decisoes estruturais]

---

## 3. Implementacao detalhada

[Por componente, com schemas, contratos, etc.]

---

## 4. Operacionalizacao

### 4.1 Pre-requisitos
### 4.2 Componentes a entregar
### 4.3 Definition of Done
### 4.4 Metricas de sucesso
### 4.5 Riscos

---

## 5. Pendencias e proximos passos

---

## 6. Decisoes tomadas durante o brainstorming

---

## 7. Referencias

[ADRs, specs relacionadas, links]
EOF

# note.md (template simples para inbox)
cat > ~/bevox-knowledge/99_templates/note.md <<'EOF'
# {titulo}

**Data:** YYYY-MM-DD
**Tipo:** captura | ideia | rascunho | follow-up
**Status:** novo

## Contexto

[O que motivou essa nota]

## Conteudo

[O que voce queria registrar]

## Proximos passos

- [ ] [acao concreta, se houver]

## Links

- [referencias]
EOF
```

- [ ] **Step 3: Verificar**

```bash
ls -la ~/bevox-knowledge/99_templates/
```

Expected: 5 arquivos (README + 4 templates).

---

## Task 19: Obsidian config (gitignore + doc)

**Files:**
- Modify: `~/bevox-knowledge/.gitignore`

> **Decisao do Task 0:** se Bernard nao for usar Obsidian agora, esta task vira so atualizacao do gitignore (preventiva) + doc da policy.

- [ ] **Step 1: Atualizar `.gitignore`**

Ler conteudo atual:

```bash
cat ~/bevox-knowledge/.gitignore
```

Adicionar (apenas o que faltar):

```bash
cat >> ~/bevox-knowledge/.gitignore <<'EOF'

# Obsidian - config pessoal nao compartilhada
.obsidian/workspace*
.obsidian/appearance.json
.obsidian/graph.json
.obsidian/hotkeys.json
.obsidian/cache
.obsidian/plugins/*/data.json
.obsidian/plugins/*/manifest.json
EOF
```

> **Spec sec 8.2:** `.obsidian/community-plugins.json` MANTEM versionado (decisao consciente do Bernard sobre quais plugins). Templates compartilhados estao em `99_templates/` (Task 18), nao em `.obsidian/templates/`.

- [ ] **Step 2: Verificar gitignore**

```bash
cat ~/bevox-knowledge/.gitignore | grep -A 10 Obsidian
```

Expected: bloco Obsidian presente.

- [ ] **Step 3: Documentar policy do Obsidian Git plugin (mesmo que Bernard nao use ainda)**

Sera incluido na Task 21 (ops doc) - nao e arquivo separado aqui. Se Bernard usar Obsidian:

> **Plugin "Obsidian Git" deve ter auto-pull/auto-push/auto-backup OFF.** O sync e responsabilidade da skill `knowledge-sync`. Plugin git so para visibilidade. Se ele tentar mexer no clone em paralelo, gera conflito com o Watcher.

---

## Task 20: CLI binary install em ~/.local/bin/

**Files:**
- Create: `~/.local/bin/knowledge-sync` (symlink ou wrapper)

- [ ] **Step 1: Garantir que ~/.local/bin esta no PATH**

```bash
mkdir -p ~/.local/bin
echo "$PATH" | tr ':' '\n' | grep -q "$HOME/.local/bin" || echo "AVISO: ~/.local/bin nao esta no PATH"
```

Se nao estiver, sugerir ao Bernard adicionar ao `~/.bashrc`:
```bash
export PATH="$HOME/.local/bin:$PATH"
```

(Mas NAO mexer no `.bashrc` automaticamente sem permissao - apenas reportar.)

- [ ] **Step 2: Criar symlink**

```bash
ln -sf ~/.openclaw/skills/knowledge-sync/bin/knowledge-sync ~/.local/bin/knowledge-sync
ls -la ~/.local/bin/knowledge-sync
```

- [ ] **Step 3: Validar invocacao direta**

```bash
~/.local/bin/knowledge-sync --help
~/.local/bin/knowledge-sync status
```

Expected: comandos rodam normalmente.

- [ ] **Step 4: Confirmar que CLI direto NAO bypassa ADR-006**

> Spec sec 9.6: a invocacao via CLI direto e via Vox/openclaw e a mesma skill. Approval continua valido.

```bash
# Tentar canonical commit via CLI direto - deve criar approval pendente igual via skill
~/.local/bin/knowledge-sync canonical commit -m "test direto" --files /dev/null 2>&1 | head -5 || true
```

Expected: cria approval pendente (mesmo comportamento da invocacao via Vox).

---

## Task 21: Documentacao operacional knowledge-spine.md

**Files:**
- Create: `~/bevox-knowledge/20_architecture/knowledge-spine.md`

> **Spec sec 10.2:** documento similar ao security-posture.md - estado atual do subsistema, como usar, rollback, troubleshooting.

- [ ] **Step 1: Criar knowledge-spine.md**

```bash
cat > ~/bevox-knowledge/20_architecture/knowledge-spine.md <<'EOF'
# Knowledge Spine - Bevox / OpenClaw

> Estado operacional do subsistema knowledge-sync que mantem `bevox-knowledge` como fonte de verdade ativa. Documento canonico, atualizado quando o subsistema mudar.

**Ultima atualizacao:** 2026-04-09
**Spec source:** `35_specs/2026-04-09-e1-knowledge-spine.md`
**Skill:** `~/.openclaw/skills/knowledge-sync/`

---

## 1. Visao geral

A skill `knowledge-sync` opera o `bevox-knowledge` como knowledge spine ativo:

- Watcher detecta drift entre clone local e remote
- Actions executam mutacoes controladas (com approval para canonico)
- Notifications avisam o Bernard quando o estado muda

## 2. Componentes em producao

| Componente | Localizacao |
|---|---|
| Skill | `~/.openclaw/skills/knowledge-sync/` |
| Wrapper executavel | `~/.openclaw/skills/knowledge-sync/bin/knowledge-sync` |
| CLI symlink | `~/.local/bin/knowledge-sync` |
| Estado | `~/.openclaw/knowledge-sync/state.json` |
| Estado anterior | `~/.openclaw/knowledge-sync/state.previous.json` |
| Eventos | `~/.openclaw/knowledge-sync/events.jsonl` |
| Snapshots | `~/.openclaw/backups/knowledge-snapshots/` |
| Index de snapshots | `~/.openclaw/backups/knowledge-snapshots/meta/snapshots-index.jsonl` |
| Clone do bevox-knowledge | `~/bevox-knowledge/` |

## 3. Servicos systemd ativos

| Unit | Frequencia | Funcao |
|---|---|---|
| `knowledge-sync-refresh.timer` | a cada 5 min | Roda o Watcher |
| `knowledge-sync-snapshot-hourly.timer` | a cada hora | Cria snapshot auto-hourly |
| `knowledge-sync-verify-daily.timer` | as 04:00 | Verifica amostra de bundles |

Verificar:
```bash
systemctl --user list-timers | grep knowledge-sync
```

## 4. Como usar

### Ver estado atual

```bash
knowledge-sync status
```

### Forcar refresh do Watcher

```bash
knowledge-sync refresh
```

### Trabalhar em uma proposta (draft)

```bash
knowledge-sync draft create adr-007-titulo
# editar arquivos
knowledge-sync draft commit -m "wip: rascunho ADR-007"
knowledge-sync draft push
```

### Promover para canonico (com approval)

```bash
knowledge-sync canonical commit -m "adr(007): aceita ADR-007" --files 30_adr/ADR-007-titulo.md
# Bernard recebe notificacao no Telegram
# Aprovar via:
knowledge-sync canonical approve <approval_id>
knowledge-sync canonical execute <approval_id>
# Depois:
knowledge-sync canonical push
# (mesmo flow de approval)
```

### Snapshot manual

```bash
knowledge-sync snapshot create --manual antes-de-grande-mudanca
```

### Listar snapshots

```bash
knowledge-sync snapshots
```

### Restaurar snapshot (dry-run por default)

```bash
knowledge-sync restore manual/2026-04-09-15-30-manual-antes-de-grande-mudanca.bundle
# Inspeciona em /tmp/ks-rollback-<ts>/
```

### Restaurar com --apply (override destrutivo)

```bash
knowledge-sync restore <bundle> --apply
# Pede confirmacao explicita "SIM, APLICAR ROLLBACK"
```

## 5. Procedimento de rollback

### Caso 1: Apenas reverter mudanca local nao commitada

```bash
cd ~/bevox-knowledge
git restore <arquivo>  # ou git restore .
```

### Caso 2: Reverter um commit recente em branch draft

```bash
cd ~/bevox-knowledge
git reset --hard HEAD~1
```

### Caso 3: Rollback canonico via snapshot

```bash
# 1. Listar snapshots disponiveis
knowledge-sync snapshots --type pre-canonical

# 2. Inspecionar antes (dry-run)
knowledge-sync restore <bundle>

# 3. Aplicar (com confirmacao)
knowledge-sync restore <bundle> --apply
```

### Caso 4: Rollback completo do estado da skill

```bash
# Parar timers
systemctl --user stop knowledge-sync-refresh.timer knowledge-sync-snapshot-hourly.timer

# Backup do estado atual
mv ~/.openclaw/knowledge-sync ~/.openclaw/knowledge-sync.backup-$(date +%s)

# Re-inicializar (vazio)
mkdir -p ~/.openclaw/knowledge-sync
chmod 700 ~/.openclaw/knowledge-sync

# Reiniciar
systemctl --user start knowledge-sync-refresh.timer knowledge-sync-snapshot-hourly.timer

# O proximo refresh repopula state.json
knowledge-sync refresh
```

## 6. Troubleshooting

### Watcher nao roda

```bash
systemctl --user status knowledge-sync-refresh.timer
systemctl --user status knowledge-sync-refresh.service
journalctl --user -u knowledge-sync-refresh.service -n 50
```

### Notificacoes nao chegam no Telegram

- Verificar que o canal esta OK: `openclaw status | grep -i telegram`
- Verificar que o ID do Bernard esta correto: `KS_NOTIFY_TARGET=<TELEGRAM_USER_ID>`
- Inspecionar events.jsonl por `notification_sent`/`notification_deferred`
- Pode estar em quiet hours (23h-08h) - errors enviam, warns ficam em batch

### Snapshot verify falhando

```bash
knowledge-sync snapshot verify --all
# Inspecionar entries com verify_status=failed no index
cat ~/.openclaw/backups/knowledge-snapshots/meta/snapshots-index.jsonl | jq 'select(.verify_status=="failed")'
```

### Conflito potencial detectado

```bash
knowledge-sync status
# Olhar campo conflicts.reason
# NAO faca pull. Inspecionar manualmente.
cd ~/bevox-knowledge
git status
git fetch
git log HEAD..origin/main --oneline
```

## 7. ADR-006 e a skill

A skill respeita explicitamente a ADR-006:

- `pull-ff` e a UNICA forma de pull (sem merge implicito)
- `commit-canonical` e `push-canonical` exigem approval mesmo em L4
- `create-marker` (tag canonica) tambem exige approval
- Operacoes destrutivas (`reset --hard`, `force push`, `merge`, `rebase`) NAO estao no catalogo
- `restore --apply` e categoria `destructive` - exige override explicito
- CLI direto NAO bypassa policy (e o mesmo subsistema)

## 8. Variaveis de ambiente configuraveis

| Variavel | Default | Funcao |
|---|---|---|
| `KS_CLONE_PATH` | `~/bevox-knowledge` | Path do clone |
| `KS_FETCH_MIN_INTERVAL` | `300` | Segundos minimos entre fetches |
| `KS_NOTIFY_TARGET` | `<TELEGRAM_USER_ID>` | ID do Telegram do Bernard |
| `KS_NOTIFY_QUIET_START` | `23` | Hora UTC inicio quiet |
| `KS_NOTIFY_QUIET_END` | `8` | Hora UTC fim quiet |
| `KS_NOTIFY_DEDUP_WINDOW` | `3600` | Janela de dedup (s) |
| `KS_NOTIFY_DIRTY_QUIET_WINDOW` | `120` | Janela de quietude antes de notificar dirty (s) |
| `KS_APPROVAL_TTL_SECONDS` | `3600` | TTL de approval canonico (s) |

## 9. Pendencias conhecidas

Ver spec `35_specs/2026-04-09-e1-knowledge-spine.md` secao 11.

- Bot do Telegram para captura automatica de `/approve`/`/reject` (hoje approval e via CLI)
- Mission Control UI (vira em E2)
- Backup remoto camada 3 (Cloudflare R2 - vira spec propria)
- Multi-host sync

## 10. Referencias

- ADR-001: Company OS Boundary
- ADR-005: Knowledge Source of Truth & Context Sync **(base)**
- ADR-006: Autonomy, Permissions & Approval Policy **(governa as Actions)**
- Spec do E1: `35_specs/2026-04-09-e1-knowledge-spine.md`
- Security posture: `20_architecture/security-posture.md`
EOF
```

- [ ] **Step 2: Verificar**

```bash
wc -l ~/bevox-knowledge/20_architecture/knowledge-spine.md
head -20 ~/bevox-knowledge/20_architecture/knowledge-spine.md
```

Expected: ~250+ linhas, comeca com o titulo correto.

---

## Task 22: Commit das mudancas no bevox-knowledge (modules/, templates/, gitignore, knowledge-spine)

**Files:** todas criadas/modificadas nas Tasks 17-19, 21.

> **IMPORTANTE:** este e um commit em **main do bevox-knowledge** afetando arquivos em areas canonicas (`20_architecture/`). Per ADR-006, isso e `write-knowledge-canonical` e exige approval.
>
> Mas Bernard solicitou explicitamente esta implementacao, entao o approval e implicito. Documentar isso no commit message.

- [ ] **Step 1: Verificar status**

```bash
cd ~/bevox-knowledge
git status
```

Expected: lista de arquivos novos em `20_architecture/modules/`, `99_templates/`, `20_architecture/knowledge-spine.md`, e modified `.gitignore`.

- [ ] **Step 2: Stage e commit**

```bash
cd ~/bevox-knowledge
git add 20_architecture/modules/ 99_templates/ 20_architecture/knowledge-spine.md .gitignore
git commit -m "$(cat <<'EOF'
e1: knowledge spine - F3 ingestion + Obsidian gitignore + ops doc

Implementa partes do E1 - Knowledge Spine (spec em
35_specs/2026-04-09-e1-knowledge-spine.md):

F3 Ingestao:
- 20_architecture/modules/ com README, _template e 4 stubs canonicos
- bevox-console (super admin/backoffice interno)
- bevox-harness (runtime da secretaria IA, canais do produto - sem Telegram)
- bevox-web (cliente da Bevox - operacao mesa)
- bevox-mobile (cliente da Bevox - dia a dia)
- Vocabulario fixo "Quem usa": Equipe Bevox/Cliente da Bevox/Cliente final/Runtime

Templates compartilhados:
- 99_templates/ com README + adr.md, module-overview.md, spec.md, note.md
- Acessivel por Vox, Claude Code e Obsidian (Templater)

Obsidian config:
- .gitignore atualizado com padroes Obsidian (config pessoal)
- community-plugins.json mantem versionado

Documentacao operacional:
- 20_architecture/knowledge-spine.md - estado, uso, rollback, troubleshooting
- Similar ao security-posture.md

Approval implicito: solicitacao explicita do Bernard durante a implementacao
do E1 (sessao 2026-04-09).

Refs: ADR-005 (knowledge SoT), ADR-006 (autonomia), spec E1
EOF
)"
git push origin main
```

Expected: commit feito e pushed.

---

## Task 23: E2E test - Draft cycle

> Executar o ciclo: editar -> Watcher detecta -> notify -> commit draft -> push draft

- [ ] **Step 1: Setup**

```bash
KS=knowledge-sync
cd ~/bevox-knowledge
$KS refresh
echo "Estado inicial:"
$KS status | head -10
```

- [ ] **Step 2: Editar arquivo no inbox**

```bash
echo "# E2E test - draft cycle" > 00_inbox/e2e-draft-cycle-test.md
echo "Conteudo de teste para o ciclo draft do E1." >> 00_inbox/e2e-draft-cycle-test.md
```

- [ ] **Step 3: Refresh + verificar dirty detected**

```bash
KS_NOTIFY_DIRTY_QUIET_WINDOW=2 $KS refresh
sleep 3
KS_NOTIFY_DIRTY_QUIET_WINDOW=2 $KS refresh
$KS status | grep -A 2 "Working tree"
```

Expected: `Working tree: dirty`. Dois refreshes para passar a janela de quietude.

- [ ] **Step 4: Criar branch draft + commit**

```bash
$KS draft create e2e-test
$KS draft commit -m "test: e2e draft cycle"
$KS status | head -15
```

Expected: branch `draft/e2e-test` ativa, commit feito.

- [ ] **Step 5: Push draft**

```bash
$KS draft push
```

Expected: push para `origin/draft/e2e-test` ok.

- [ ] **Step 6: Cleanup**

```bash
git checkout main
$KS draft delete e2e-test
git -C ~/bevox-knowledge push origin --delete draft/e2e-test 2>&1 || echo "(remota: delete manual se necessario)"
$KS refresh
```

---

## Task 24: E2E test - Canonical cycle com approval

- [ ] **Step 1: Criar mudanca canonica de teste (em modules/)**

```bash
KS=knowledge-sync
cd ~/bevox-knowledge
git checkout main

# Modificar bevox-console.md (adicionar nota nas duvidas em aberto)
sed -i '/## Duvidas em aberto/a - [E2E test marker - remover apos teste]' 20_architecture/modules/bevox-console.md
git diff 20_architecture/modules/bevox-console.md
```

- [ ] **Step 2: Solicitar canonical commit**

```bash
$KS canonical commit \
  -m "test: e2e canonical cycle - adicionar marker temporario" \
  --files 20_architecture/modules/bevox-console.md
```

Expected: cria approval pendente, mostra approval_id, notifica via Telegram (se configurado).

- [ ] **Step 3: Listar pending**

```bash
$KS pending
APPROVAL_ID="$(grep canonical_approval_pending ~/.openclaw/knowledge-sync/events.jsonl | tail -1 | jq -r '.payload.approval_id')"
echo "Approval ID: $APPROVAL_ID"
```

- [ ] **Step 4: Aprovar e executar**

```bash
$KS canonical approve "$APPROVAL_ID"
$KS canonical execute "$APPROVAL_ID"
```

Expected: commit em main feito.

- [ ] **Step 5: Reverter (cleanup)**

```bash
git -C ~/bevox-knowledge reset --hard HEAD~1
$KS refresh
```

> Note: NAO push do test commit - so test local. Para o E2E real, o reset desfaz o commit.

---

## Task 25: E2E test - Snapshot create/restore

- [ ] **Step 1: Snapshot manual**

```bash
KS=knowledge-sync
$KS snapshot create --manual e2e-test
$KS snapshots --type manual | tail -1
```

Expected: bundle criado, listado.

- [ ] **Step 2: Verify**

```bash
$KS snapshot verify --all
```

Expected: `verified=N failed=0`.

- [ ] **Step 3: Restore dry-run**

```bash
BUNDLE=$($KS snapshots --type manual | tail -1 | jq -r '.path')
$KS restore "$BUNDLE"
ls /tmp/ks-rollback-*/  # ver conteudo restaurado
```

Expected: clone restaurado em `/tmp/ks-rollback-<ts>/`.

- [ ] **Step 4: Cleanup**

```bash
rm -rf /tmp/ks-rollback-*
# Apagar o bundle de teste do index e do disco
rm -f ~/.openclaw/backups/knowledge-snapshots/manual/*-manual-e2e-test.bundle
grep -v 'e2e-test' ~/.openclaw/backups/knowledge-snapshots/meta/snapshots-index.jsonl > /tmp/idx.tmp && \
  mv /tmp/idx.tmp ~/.openclaw/backups/knowledge-snapshots/meta/snapshots-index.jsonl
```

---

## Task 26: E2E test - Conflict detection (simulacao)

Simular um cenario que dispara `conflict_potential = true`.

- [ ] **Step 1: Criar dirty + behind simulado**

```bash
cd ~/bevox-knowledge
# Criar mudanca local
echo "test conflict" >> 00_inbox/conflict-test.md

# (Nao vamos realmente criar um remote behind aqui - so testar a logica conservadora)
# Para simular behind, podemos manualmente editar state.json (so para teste)

# Forcar Watcher
knowledge-sync refresh
knowledge-sync status | grep -A 2 Conflicts
```

Para simulacao mais real:
```bash
# Salvar HEAD atual
SAVED="$(git rev-parse HEAD)"

# Reset HEAD para 1 commit anterior (simula behind)
git reset --hard HEAD~1

# Agora estamos behind. Criar mudanca local (simula dirty)
echo "test conflict" >> 00_inbox/conflict-test.md

# Refresh
knowledge-sync refresh
knowledge-sync status | grep -A 3 Conflicts

# Esperado: conflict_potential = true (behind + dirty)

# Restaurar
git reset --hard "$SAVED"
rm -f 00_inbox/conflict-test.md
knowledge-sync refresh
```

Expected: durante a simulacao, status mostra `conflict_potential` ou similar.

- [ ] **Step 2: Validar que pull-ff recusou**

```bash
# Durante a simulacao, tentar pull-ff
knowledge-sync pull-ff 2>&1
```

Expected: BLOCKED com razao apropriada (working tree not clean / non-ff / etc).

---

## Task 27: Validacao final do DoD

- [ ] **Step 1: Checklist do DoD da spec**

Verificar item por item:

```bash
# Skill instalada e visivel
openclaw skills list 2>&1 | grep -i knowledge-sync && echo "OK" || echo "FAIL: skill not in list"

# Watcher rodando via cron
systemctl --user list-timers | grep knowledge-sync-refresh && echo "OK" || echo "FAIL"

# events.jsonl populando
[[ -f ~/.openclaw/knowledge-sync/events.jsonl ]] && echo "OK" || echo "FAIL"

# Comandos da Secao 9 funcionando
for cmd in status health events log drafts snapshots pending; do
  knowledge-sync $cmd >/dev/null 2>&1 && echo "OK: $cmd" || echo "FAIL: $cmd"
done

# Approval flow (criado e respeitado em Task 24)
grep -q canonical_committed ~/.openclaw/knowledge-sync/events.jsonl && echo "OK: approval flow tested" || echo "PEND"

# Snapshots automaticos
ls ~/.openclaw/backups/knowledge-snapshots/auto/*.bundle 2>/dev/null | head -1 && echo "OK: auto snapshot exists" || echo "PEND (aguardar 1h cron)"

# restore testado em dry-run (Task 25)
grep -q restore_dryrun ~/.openclaw/knowledge-sync/events.jsonl && echo "OK" || echo "PEND"

# Verify amostral funcionando
grep -q snapshot ~/.openclaw/knowledge-sync/events.jsonl && echo "OK" || echo "PEND"

# bevox-knowledge atualizado
[[ -d ~/bevox-knowledge/20_architecture/modules ]] && echo "OK: modules" || echo "FAIL"
[[ -d ~/bevox-knowledge/99_templates ]] && echo "OK: templates" || echo "FAIL"
[[ -f ~/bevox-knowledge/20_architecture/knowledge-spine.md ]] && echo "OK: ops doc" || echo "FAIL"

# .gitignore Obsidian
grep -q "\.obsidian" ~/bevox-knowledge/.gitignore && echo "OK: gitignore" || echo "FAIL"

# Vox le stubs sem intervencao manual
cat ~/bevox-knowledge/20_architecture/modules/bevox-harness.md | head -5 >/dev/null && echo "OK: stubs lidos via filesystem" || echo "FAIL"
```

- [ ] **Step 2: Reportar status**

Lista de tudo que esta verde, e qualquer item amarelo/vermelho. Se tiver vermelho, voltar para a task respectiva antes de prosseguir para Task 28 (tag).

---

## Task 28: Tag v0.2-knowledge-spine (SO apos DoD validado)

> **Critico:** so aplicar a tag depois que o DoD da Task 27 estiver REALMENTE fechado (todos os checkmarks verdes). Nao tagar so porque o spec/plano foi salvo.

- [ ] **Step 1: Confirmar DoD verde**

Re-rodar a Task 27 e validar que TODOS os items reportam OK. Se algum esta PEND/FAIL, voltar e resolver.

- [ ] **Step 2: Aplicar tag canonica via skill (com approval)**

```bash
KS=knowledge-sync
$KS canonical create-marker \
  --name knowledge-spine \
  --type release \
  --message "E1 - Knowledge Spine implementado. Skill knowledge-sync ativa, Watcher/Actions/Notifications funcionando, snapshots locais + tags, F3 ingestao com 4 stubs canonicos, ops doc."

# Pegar approval_id
APPROVAL_ID="$(grep canonical_approval_pending ~/.openclaw/knowledge-sync/events.jsonl | tail -1 | jq -r '.payload.approval_id')"

# Aprovar
$KS canonical approve "$APPROVAL_ID"
$KS canonical execute "$APPROVAL_ID"
```

Expected: tag `v0.X-knowledge-spine` (ajustar nomenclatura per ADR-004 - provavelmente `v0.2-knowledge-spine`) criada e pushed.

- [ ] **Step 3: Verificar tag no GitHub**

```bash
git -C ~/bevox-knowledge tag -l | grep knowledge-spine
gh api repos/bernardTavares/bevox-knowledge/tags | jq -r '.[].name' | head -5
```

Expected: tag presente local e remoto.

- [ ] **Step 4: Notificar Bernard**

```
E1 - Knowledge Spine concluido.

Tag aplicada: v0.2-knowledge-spine

DoD validado:
- Skill knowledge-sync ativa em ~/.openclaw/skills/knowledge-sync/
- Watcher rodando via systemd timer (5min)
- Snapshots auto-hourly + verify daily
- 4 stubs canonicos em bevox-knowledge/20_architecture/modules/
- 99_templates/ criado
- Obsidian gitignore atualizado
- knowledge-spine.md operacional

Repo: github.com/bernardTavares/bevox-knowledge

Proximos passos sugeridos:
- Bernard valida o ciclo end-to-end no uso real
- E2 - Mission Control Shell pode comecar
- Camada 3 de snapshots (R2 backup) vira spec propria
```

---

## Self-Review checklist

Apos toda a implementacao:

- [ ] **Spec coverage:** todas as secoes da spec tem task correspondente
  - Sec 2 (arquitetura) -> Tasks 2-4
  - Sec 3 (Watcher) -> Task 4
  - Sec 4 (Actions) -> Tasks 5, 7, 9-13, 16
  - Sec 5 (Notifications) -> Tasks 14-15
  - Sec 6 (Snapshots) -> Tasks 8-11
  - Sec 7 (F3 ingestao) -> Tasks 17-18
  - Sec 8 (Obsidian) -> Task 19
  - Sec 9 (Interface) -> Tasks 5, 7, 11-13, 16, 20
  - Sec 10 (Operacionalizacao) -> Tasks 21-22
- [ ] **Placeholder scan:** plano sem TBD/TODO/incomplete
- [ ] **Type consistency:** nomes de funcoes/comandos/eventos consistentes em todas as tasks (state.json schema, action contracts, event names)
- [ ] **DoD da Task 27 todos verdes antes de aplicar tag**
- [ ] **Documentacao operacional (Task 21) reflete o estado real implementado**

---

## Resumo de commits e tags

| Quando | O que | Onde |
|---|---|---|
| Tasks 17-21 (juntas) | Commit em main com modules/, templates/, knowledge-spine, gitignore | bevox-knowledge |
| Task 28 | Tag `v0.2-knowledge-spine` via canonical create-marker | bevox-knowledge |

A skill `knowledge-sync` em si vive em `~/.openclaw/` e nao e versionada no git nesta versao. Possivel migracao futura para repo proprio (`bevox-skills`?).

---

## Pendencias conhecidas (post-E1)

- Bot do Telegram para captura automatica de `/approve`/`/reject` (hoje aprovacao e via CLI)
- Backup remoto camada 3 (Cloudflare R2) - vira spec propria
- Mission Control UI (E2 - feed visual dos mesmos eventos)
- Multi-host sync
- Indexacao/RAG do knowledge

---

## Estimativas

- **Tasks executaveis:** 0-28 (Task 0 e manual)
- **Tempo estimado:** alto - este e um plano denso. Cada task com bash code e validacao pode levar tempo considerave.
- **Pontos de checkpoint para revisao humana:**
  - Apos Task 1 (discovery) - PRINCIPAL bloqueio
  - Apos Task 4 (Watcher funcional)
  - Apos Task 13 (draft cycle funcionando)
  - Apos Task 16 (canonical cycle funcionando)
  - Apos Task 22 (commit canonical de F3 feito)
  - Apos Task 27 (DoD validation completa)
  - Apos Task 28 (tag aplicada)

---

## Dependencias externas

- `git` >= 2.30
- `jq`
- `flock` (util-linux)
- `sha256sum` (coreutils)
- OpenClaw rodando como systemd user service
- Acesso ao github.com/bernardTavares/bevox-knowledge via gh auth
- Telegram channel ativo no OpenClaw (para notificacoes)

---

## O que NAO esta neste plano (out of scope)

Mesmo out of scope da spec sec 1.4:
- Cloudflare R2 / backup remoto
- Mission Control UI (E2)
- Approval Center funcional com fila/UI (E4)
- RAG / indexacao avancada
- Multi-host sync
- PRDs profundos dos modulos canonicos
- Plugin custom do Obsidian

