#!/usr/bin/env python3
"""backfill_gaps_w3.5 — re-run F1 audit + F4 scan registrando gaps em state v2.

Idempotent (re-run não duplica via gap_registry.add_gap idempotency).
Use --dry-run pra preview sem mutate state.json.

Usage:
    python3 backfill_gaps_w3.5.py [--dry-run]

Após W3.5 deploy normal, F1/F2/F4 runs já registram gaps automaticamente —
este script é one-shot pra fazer catch-up dos gaps surfaced em smoke runs
prévios (W2 retirement + W3 audit) que ainda não estão em state v2.

Spec: bevox-knowledge/35_specs/_shared/plans/2026-05-09-skill-v2-W3.5-telegram-commands-plan.md §Phase 1 Task 1.8
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib.knowledge_watcher.state import (
    read_state, write_state, default_state, SCHEMA_VERSION,
)
from lib.knowledge_watcher.commit_watcher.runner import run_audit
from lib.knowledge_watcher.retirement.scanner import scan_retirement_candidates


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill knowledge-watcher gaps em state v2 (one-shot)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", dest="dry_run",
        help="preview gap counts sem mutate state.json",
    )
    args = parser.parse_args()

    openclaw_dir = Path(os.path.expanduser("~/.openclaw"))
    kb_dir = Path(os.environ.get("BEVOX_KNOWLEDGE_DIR", os.path.expanduser("~/bevox-knowledge")))
    code_dir = Path(os.environ.get("BEVOX_CODE_DIR", os.path.expanduser("~/code")))
    state_path = openclaw_dir / "knowledge-watcher" / "state.json"
    meta_path = openclaw_dir / "projects-meta.json"

    print("📥 [W3.5 backfill]")
    print()

    state = read_state(state_path)
    if state.get("version") != SCHEMA_VERSION:
        print(f"⚠️  state.json schema mismatch — got {state.get('version')}, expected {SCHEMA_VERSION}")
        print("Migration in progress: starting from default v2 state")
        state = default_state()

    # F1 audit (re-run; registers via run_audit)
    print("F1 commit watcher:")
    try:
        results = run_audit(
            meta_path, kb_dir, code_dir,
            project=None, since=None,
            dry_run=args.dry_run,
            state_path=state_path,
        )
    except Exception as e:
        print(f"  ⚠️  F1 audit failed: {e}")
        results = []

    for r in results:
        if r.skipped_reason:
            print(f"  ⏭  {r.repo_slug}: {r.skipped_reason}")
            continue
        sha = r.last_commit_processed[:7] if r.last_commit_processed else "(none)"
        print(f"  ✅ {r.repo_slug}: {r.gaps_detected} gap(s) — last_sha={sha}")

    # Reload state após F1 (run_audit persiste no state_path internamente)
    if not args.dry_run:
        state = read_state(state_path)

    # F4 retirement scan
    print()
    print("F4 retirement scan:")
    try:
        candidates = scan_retirement_candidates(kb_dir, code_dir, state=state)
    except Exception as e:
        print(f"  ⚠️  F4 scan failed: {e}")
        candidates = []

    if candidates:
        per_repo: dict[str, int] = {}
        for c in candidates:
            slug = c.project_slug or "_shared"
            per_repo[slug] = per_repo.get(slug, 0) + 1
        for slug, count in sorted(per_repo.items()):
            print(f"  📋 {slug}: {count} retirement candidate(s)")
    else:
        print("  ✅ no retirement candidates")

    # Sumário
    total_gaps = sum(
        len(rs.get("gaps", {})) for rs in state.get("repos", {}).values()
    )
    print()
    print(f"Total gaps registered in state: {total_gaps}")

    if args.dry_run:
        print("[dry-run] state NOT written")
        return 0

    write_state(state_path, state)
    print(f"✅ state.json updated: {state_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
