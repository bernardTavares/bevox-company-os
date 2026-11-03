#!/usr/bin/env bash
# scrum-master-agent CLI entrypoint.
# Invoca lib.api via python3 stdlib.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
exec python3 -m lib.api "$@"
