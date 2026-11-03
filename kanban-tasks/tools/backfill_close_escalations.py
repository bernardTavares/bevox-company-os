#!/usr/bin/env python3
"""Backfill: aplica _auto_close_escalations em tasks já em terminal status
mas com escalation files órfãs.

Uso:
    python3 tools/backfill_close_escalations.py            # dry-run (default)
    python3 tools/backfill_close_escalations.py --apply    # mutar de fato

Spec: bevox-knowledge/35_specs/openclaw/2026-05-04-ubn-w2-loop-self-healing.md §7.1
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Mesmo path layout que kanban-tasks/cli.sh: roda do diretório kanban-tasks/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.task import (  # type: ignore
    TERMINAL_STATUSES,
    UBN_CLR_ESCALATIONS_DIR,
    TESTER_ESCALATIONS_DIR,
    _auto_close_escalations,
)
from lib import store  # type: ignore


def find_orphan_tasks(state: dict) -> list[dict]:
    """Retorna tasks em terminal status que TÊM files órfãos.
    Recebe state já carregado dentro de mutate_state lock."""
    out = []
    for t in state.get("tasks", []):
        if t.get("status") not in TERMINAL_STATUSES:
            continue
        tid = t.get("id")
        if not tid:
            continue
        has_orphan = False
        if UBN_CLR_ESCALATIONS_DIR.is_dir():
            for p in UBN_CLR_ESCALATIONS_DIR.iterdir():
                if p.name.startswith(f"{tid}-blk-") or p.name.startswith(f"{tid}-clr-"):
                    has_orphan = True
                    break
        if not has_orphan and TESTER_ESCALATIONS_DIR.is_dir():
            for p in TESTER_ESCALATIONS_DIR.iterdir():
                if p.name.startswith(f"{tid}-tr-"):
                    has_orphan = True
                    break
        if has_orphan:
            out.append({"id": tid, "status": t["status"]})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="Mutar de fato. Default: dry-run.")
    args = ap.parse_args()

    if not args.apply:
        # Dry-run: leitura simples, sem lock
        state = json.loads(store.STATE_PATH.read_text(encoding="utf-8"))
        orphans = find_orphan_tasks(state)
        print(f"Found {len(orphans)} terminal tasks with orphan escalation files:\n")
        for o in orphans:
            print(f"  {o['id']} [{o['status']}]")
        if not orphans:
            print("\nNothing to do.")
        else:
            print("\n(dry-run — re-run with --apply to actually close)")
        return 0

    # Apply: tudo dentro do mesmo lock
    print("Applying...")
    with store.mutate_state() as state:
        orphans = find_orphan_tasks(state)
        if not orphans:
            print("Nothing to do.")
            return 0
        print(f"Found {len(orphans)} terminal tasks with orphan escalation files:")
        for o in orphans:
            print(f"  {o['id']} [{o['status']}]")
        print()
        for o in orphans:
            result = _auto_close_escalations(
                state, o["id"], o["status"], "backfill-script"
            )
            print(json.dumps({
                "task_id": o["id"],
                "status": o["status"],
                "result": result,
            }, indent=2))
            # If errors, surface separately
            if result.get("errors"):
                print(f"  ⚠ errors for {o['id']}: {result['errors']}", file=sys.stderr)
    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
