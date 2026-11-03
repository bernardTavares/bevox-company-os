#!/bin/bash
# Bootstrap de novo bot Telegram por área usando openclaw --profile.
#
# Modo interactive (default):
#   ~/.openclaw/scripts/bootstrap-telegram-agent.sh <area> <port>
#   Cria estrutura + placeholders. Imprime checklist manual final.
#
# Modo non-interactive (MC backend, ou automação):
#   ~/.openclaw/scripts/bootstrap-telegram-agent.sh \
#     --token TOKEN --chat-id CHAT_ID --allow-from u1,u2 \
#     --skills knowledge-sync-commands,clarification-commands \
#     --non-interactive --json [--dry-run] <area> <port>
#   Escreve config completa + (opcional) habilita systemd. Output: 1 linha JSON.
#
# Idempotente: safe re-run; NÃO sobrescreve area_context.md populado.

set -euo pipefail

# ---------- Flag parsing ----------
TOKEN=""
CHAT_ID=""
ALLOW_FROM=""
SKILLS="knowledge-sync-commands,clarification-commands"
PROJECT_SLUG=""
NON_INTERACTIVE=0
JSON_OUTPUT=0
DRY_RUN=0

POSITIONAL=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --token) TOKEN="$2"; shift 2 ;;
    --chat-id) CHAT_ID="$2"; shift 2 ;;
    --allow-from) ALLOW_FROM="$2"; shift 2 ;;
    --skills) SKILLS="$2"; shift 2 ;;
    --project-slug) PROJECT_SLUG="$2"; shift 2 ;;
    --non-interactive) NON_INTERACTIVE=1; shift ;;
    --json) JSON_OUTPUT=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --) shift; while [[ $# -gt 0 ]]; do POSITIONAL+=("$1"); shift; done ;;
    -*) echo "unknown flag: $1" >&2; exit 2 ;;
    *) POSITIONAL+=("$1"); shift ;;
  esac
done
set -- "${POSITIONAL[@]}"

AREA="${1:-}"
PORT="${2:-}"
if [[ -z "$AREA" || ! "$AREA" =~ ^[a-z][a-z0-9-]*$ ]]; then
  echo "usage: $0 [flags] <area> <port>  (area: lowercase+alphanumeric+hyphens; port: int)" >&2
  exit 2
fi
if [[ "$AREA" == "dev" ]]; then
  echo "error: 'dev' é reservado pelo openclaw (--dev profile)" >&2
  exit 2
fi
if [[ -z "$PORT" || ! "$PORT" =~ ^[0-9]+$ ]]; then
  echo "usage: $0 [flags] <area> <port>  (port integer; convenção 18790+)" >&2
  exit 2
fi

if [[ "$NON_INTERACTIVE" -eq 1 ]]; then
  if [[ -z "$TOKEN" || -z "$CHAT_ID" || -z "$ALLOW_FROM" ]]; then
    echo "FAIL: --non-interactive requires --token --chat-id --allow-from" >&2
    exit 2
  fi
fi

SHARED="$HOME/.openclaw/workspace-shared/memory"
PROFILE_DIR="$HOME/.openclaw-$AREA"
WS="$PROFILE_DIR/workspace/memory"
ENV_FILE="$HOME/.openclaw/gateway/bots/$AREA.env"
TEMPLATE_CONFIG="$HOME/.openclaw/openclaw.json"

# Preflight
[[ -d "$SHARED" ]] || { echo "FAIL: $SHARED missing; run phase-1 first" >&2; exit 1; }
[[ -f "$SHARED/user_profile.md" ]] || { echo "FAIL: $SHARED/user_profile.md missing" >&2; exit 1; }
[[ -f "$TEMPLATE_CONFIG" ]] || { echo "FAIL: $TEMPLATE_CONFIG missing (Vox config necessária como template)" >&2; exit 1; }

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

# openclaw.json do profile: clona do Vox + ajusta workspace + channels (placeholders OU populated)
# Em modo non-interactive, REESCREVE config mesmo se já existe (idempotência permite reconnect com creds novas).
if [[ ! -f "$PROFILE_DIR/openclaw.json" || "$NON_INTERACTIVE" -eq 1 ]]; then
  if [[ ! -f "$PROFILE_DIR/openclaw.json" ]]; then
    cp "$TEMPLATE_CONFIG" "$PROFILE_DIR/openclaw.json"
  fi
  TOKEN="$TOKEN" CHAT_ID="$CHAT_ID" ALLOW_FROM="$ALLOW_FROM" SKILLS="$SKILLS" \
    NON_INTERACTIVE="$NON_INTERACTIVE" PROFILE_DIR="$PROFILE_DIR" \
  python3 <<'PYEOF'
import json, os
p = os.path.join(os.environ["PROFILE_DIR"], "openclaw.json")
c = json.load(open(p))
c["agents"]["defaults"]["workspace"] = os.path.join(os.environ["PROFILE_DIR"], "workspace")
c["agents"]["list"] = [{"id": "main", "workspace": os.path.join(os.environ["PROFILE_DIR"], "workspace")}]
c.setdefault("channels", {})
if os.environ["NON_INTERACTIVE"] == "1":
    chat_id = os.environ["CHAT_ID"]
    allow_from = [u for u in os.environ["ALLOW_FROM"].split(",") if u]
    c["channels"]["telegram"] = {
        "enabled": True,
        "groups": {chat_id: {"requireMention": False}},
        "dmPolicy": "allowlist",
        "allowFrom": allow_from,
        "botToken": os.environ["TOKEN"],
    }
else:
    c["channels"]["telegram"] = {
        "enabled": True,
        "groups": {"<POPULATE_CHAT_ID>": {"requireMention": False}},
        "dmPolicy": "allowlist",
        "allowFrom": ["<POPULATE_BERNARD_USER_ID>"],
    }
c.setdefault("plugins", {})
skills = [s for s in os.environ["SKILLS"].split(",") if s]
for required in ("knowledge-sync-commands", "clarification-commands"):
    if required not in skills:
        skills.insert(0, required)
c["plugins"]["allow"] = skills
json.dump(c, open(p, "w"), indent=2)
PYEOF
  chmod 0600 "$PROFILE_DIR/openclaw.json"
fi

# Env file pro systemd (port + boot vars). Sempre atualiza port em non-interactive (reconnect).
if [[ ! -f "$ENV_FILE" || "$NON_INTERACTIVE" -eq 1 ]]; then
  cat > "$ENV_FILE" <<EOF2
OPENCLAW_GATEWAY_PORT=$PORT
# Profile: $AREA. Config completa em $PROFILE_DIR/openclaw.json.
# Token Telegram vai direto na config do profile (channels.telegram),
# NÃO neste env file (convenção openclaw native).
EOF2
  chmod 0600 "$ENV_FILE"
fi

# ---------- Modo non-interactive: enable systemd + meta sync + JSON output ----------
if [[ "$NON_INTERACTIVE" -eq 1 ]]; then
  if [[ "$DRY_RUN" -eq 0 ]]; then
    systemctl --user daemon-reload
    systemctl --user enable --now "openclaw-gateway@$AREA.service"
    sleep 2
    if ! systemctl --user is-active --quiet "openclaw-gateway@$AREA.service"; then
      echo "FAIL: systemd unit not active after enable" >&2
      journalctl --user -u "openclaw-gateway@$AREA.service" -n 20 --no-pager >&2 || true
      exit 1
    fi
  fi

  # Validate clarification-commands plugin is wired in profile config
  if ! python3 -c "
import json, sys
with open('$PROFILE_DIR/openclaw.json') as f:
    cfg = json.load(f)
allow = cfg.get('plugins', {}).get('allow', [])
sys.exit(0 if 'clarification-commands' in allow else 1)
"; then
    echo "FAIL: clarification-commands not in plugins.allow after bootstrap" >&2
    exit 1
  fi

  # ---- Meta sync (Phase 4 hardening): garantir bot_id em projects-meta.json ----
  # Sem isso, telegram_meta.resolve_telegram_target retorna None (bot_id ausente)
  # e os notifiers caem no fallback do Vox principal — quebrando o roteamento
  # per-project. MC route /api/projects/<id>/bot/connect já chama project edit
  # após este script; este bloco é defesa em profundidade pra invocações fora
  # do MC flow (CLI direto).
  META_SYNC_STATUS="skipped_no_slug"
  if [[ -n "$PROJECT_SLUG" && "$DRY_RUN" -eq 0 ]]; then
    KANBAN_CLI="$HOME/.openclaw/kanban-tasks/cli.sh"
    BOT_USERNAME=""
    if [[ -n "$TOKEN" ]]; then
      BOT_USERNAME=$(curl -s --max-time 8 \
        "https://api.telegram.org/bot$TOKEN/getMe" \
        | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('result',{}).get('username',''))" 2>/dev/null || echo "")
    fi
    if [[ -x "$KANBAN_CLI" ]]; then
      EDIT_ARGS=("project" "edit" "$PROJECT_SLUG" "--bot-id" "$AREA" "--bot-port" "$PORT")
      if [[ -n "$BOT_USERNAME" ]]; then
        EDIT_ARGS+=("--bot-username" "$BOT_USERNAME")
      fi
      if "$KANBAN_CLI" "${EDIT_ARGS[@]}" --json >/dev/null 2>&1; then
        META_SYNC_STATUS="ok"
      else
        META_SYNC_STATUS="failed"
        echo "WARN: project edit failed for $PROJECT_SLUG (bot_id=$AREA) — meta may be stale" >&2
      fi
    else
      META_SYNC_STATUS="kanban_cli_missing"
    fi
  fi

  if [[ "$JSON_OUTPUT" -eq 1 ]]; then
    printf '{"success":true,"area":"%s","port":%s,"profile_dir":"%s","systemd_unit":"openclaw-gateway@%s.service","dry_run":%s,"project_slug":"%s","meta_sync":"%s"}\n' \
      "$AREA" "$PORT" "$PROFILE_DIR" "$AREA" "$([[ "$DRY_RUN" -eq 1 ]] && echo true || echo false)" "$PROJECT_SLUG" "$META_SYNC_STATUS"
  fi
  exit 0
fi

# ---------- Modo interactive: checklist manual ----------
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
echo "     - plugins.allow: knowledge-sync-commands + clarification-commands são forçados por construção; para remover algum, edite openclaw.json após bootstrap"
echo "  4. Editar $WS/area_context.md (remover placeholder + adicionar contexto real)"
echo "  5. systemctl --user enable --now openclaw-gateway@$AREA.service"
echo "  6. Test: mensagem no grupo mencionando o bot → expect resposta contextual"
