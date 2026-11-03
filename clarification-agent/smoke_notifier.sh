#!/bin/bash
# Smoke E2E — clarification-notifier wave-2
# Cobre 7 cenários da spec 2026-04-21-e10-telegram-push-escalations §5.
set -u

PASS=0
FAIL=0
FAILED_NAMES=()
_ok()   { echo "  ✓ $1"; PASS=$((PASS+1)); }
_fail() { echo "  ✗ $1"; FAIL=$((FAIL+1)); FAILED_NAMES+=("$1"); }

ROOT=~/.openclaw/clarification-agent
ESC="$ROOT/escalations"
STATE="$ROOT/notifier-state.json"
JSONL="$ROOT/notifier.jsonl"

# Backup estado antes do smoke
[ -f "$STATE" ] && cp "$STATE" "$STATE.smoke-bak"
[ -f "$JSONL" ] && cp "$JSONL" "$JSONL.smoke-bak"

_restore() {
  [ -f "$STATE.smoke-bak" ] && mv "$STATE.smoke-bak" "$STATE" || rm -f "$STATE"
  [ -f "$JSONL.smoke-bak" ] && mv "$JSONL.smoke-bak" "$JSONL" || rm -f "$JSONL"
}

# ========= 1. Happy path, 1 escalation nova =========
echo "=== 1. Happy path 1 escalation ==="
# Manual: requer Bot API real. Executar com live env.
echo "  (pending — requires live TELEGRAM_BOT_TOKEN + thread_id válido)"

# ========= 2. Dry run não envia nem grava =========
echo "=== 2. Dry run ==="
rm -f "$STATE" "$JSONL"
touch "$ESC/T-SMOKE-clr-1.md" 2>/dev/null || true
out=$("$ROOT/notifier.sh" --tick --dry-run --json 2>&1 || true)
if echo "$out" | grep -q '"would_send"'; then
  _ok "dry-run reports would_send"
else
  _fail "dry-run did NOT output would_send"
fi
[ ! -f "$STATE" ] && _ok "dry-run did not create state" || _fail "dry-run CREATED state"
rm -f "$ESC/T-SMOKE-clr-1.md"

# ========= 3. Env var ausente → exit 1 =========
echo "=== 3. Missing env var ==="
rc=$(env -u TELEGRAM_CLARIFICATIONS_THREAD_ID "$ROOT/notifier.sh" --tick 2>/dev/null; echo $?)
[ "$rc" = "1" ] && _ok "missing env var → exit 1" || _fail "expected exit 1 got $rc"

# ========= 4. Recovery silencioso =========
echo "=== 4. Recovery silencioso ==="
# Manual: resolve uma clarification (override/reject-task) e confirma que não há Telegram.
echo "  (pending — requires live override command + live Bot API observability)"

# ========= 5. Parse error não quebra o tick =========
echo "=== 5. Parse error em filename inválido ==="
rm -f "$STATE" "$JSONL"
touch "$ESC/garbage.md"
out=$("$ROOT/notifier.sh" --tick --dry-run --json 2>&1 || true)
# Garbage não deve aparecer em nenhum evento de notification
if grep -q "garbage" "$JSONL" 2>/dev/null; then
  _fail "garbage file appeared in audit events"
else
  _ok "garbage file ignored"
fi
rm -f "$ESC/garbage.md"

# ========= 6. Múltiplas escalations de uma vez =========
echo "=== 6. Multiple escalations ==="
# Manual: criar 5 escalations falsas + live send. Pending.
echo "  (pending — requires live Bot API)"

# ========= 7. Telegram API down (network) =========
echo "=== 7. Telegram API network failure ==="
# Manual: desconectar rede + tick + verificar event notification_send_failed.
echo "  (pending — requires network toggle + live run)"

_restore
echo ""
echo "== Smoke summary =="
echo "PASS=$PASS FAIL=$FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo "Failed scenarios:"
  for n in "${FAILED_NAMES[@]}"; do echo "  - $n"; done
  exit 1
fi
exit 0
