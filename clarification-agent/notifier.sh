#!/bin/bash
# Wrapper para lib.notifier — invocado pelo systemd oneshot.
# Carrega .env (tolerante a linhas comentadas) + passa args pro python.
set -eu

ROOT="$HOME/.openclaw/clarification-agent"
ENV_FILE="$HOME/.openclaw/.env"

if [[ -f "$ENV_FILE" ]]; then
  # Carrega apenas linhas KEY=VALUE (ignora # e linhas vazias).
  set -a
  # shellcheck disable=SC1090
  source <(grep -E '^[A-Z_][A-Z0-9_]*=' "$ENV_FILE" || true)
  set +a
fi

cd "$ROOT"
exec /usr/bin/python3 -m lib.notifier "$@"
