#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

case "${1:-}" in
    ubn)
        shift
        exec python3 -m lib.ubn_actions "$@"
        ;;
    *)
        exec python3 -m lib.api "$@"
        ;;
esac
