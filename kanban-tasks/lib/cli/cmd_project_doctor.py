"""`openclaw project doctor [--fix]` — cross-project drift scan + repair.

Spec: bevox-knowledge/35_specs/openclaw/2026-05-07-project-lifecycle-w5-v1.md
ADR-013 §Drift detection contract.

Two phases:
1. Scan (always runs): iterate projects-meta, detect drifts + orphans + drafts.
2. Repair (--fix): per drift, invoke W4 provisioner idempotently. Interactive
   prompts unless --auto-confirm. Orphans are listed only (never auto-removed
   in W5).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from lib.capability_detect import DetectPaths
from lib.doctor import _render as _doctor_render
from lib.doctor.repair import repair_drift
from lib.doctor.scanner import scan_all

EXIT_OK = 0
EXIT_VALIDATION = 1
EXIT_RUNTIME = 2


def _print(payload: Any, json_mode: bool, human: Optional[str] = None) -> None:
    if json_mode:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        if human is not None:
            print(human)
        else:
            print(json.dumps(payload, ensure_ascii=False, indent=2))


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _make_prompt_fn(non_interactive: bool):
    def _prompt(message: str, default_yes: bool = True) -> bool:
        if non_interactive:
            return default_yes
        try:
            answer = input(message).strip().lower()
        except EOFError:
            return default_yes
        if not answer:
            return default_yes
        return answer in ("y", "yes", "s", "sim")
    return _prompt


def _parse_csv(value: Optional[str]) -> Optional[list]:
    if not value:
        return None
    return [s.strip() for s in value.split(",") if s.strip()]


def cmd_project_doctor(args: argparse.Namespace) -> int:
    """Doctor entry point. See module docstring."""
    fix = bool(getattr(args, "fix", False))
    auto_confirm = bool(getattr(args, "auto_confirm", False))
    json_mode = bool(getattr(args, "json", False))
    skip_orphans = bool(getattr(args, "skip_orphans", False))

    # `--auto-confirm` without `--fix` is a no-op flag combo. We accept it
    # silently rather than failing, matching how `--bot=auto` interacts.
    if fix and not auto_confirm and not sys.stdin.isatty():
        # Per spec test plan: --fix without --auto-confirm in non-interactive
        # context (no TTY) → exit 64 (per W5 §Test plan).
        _print(
            {
                "error": "fix_requires_tty_or_auto_confirm",
                "hint": "pass --auto-confirm for non-interactive repair",
            },
            json_mode,
            "erro: --fix em terminal não-interativo exige --auto-confirm",
        )
        return 64

    openclaw_dir = Path(os.environ.get(
        "OPENCLAW_DIR", f"{Path.home()}/.openclaw"))
    kb_dir = Path(os.environ.get(
        "BEVOX_KNOWLEDGE_DIR", f"{Path.home()}/bevox-knowledge"))
    code_dir = Path(os.environ.get(
        "BEVOX_CODE_DIR", f"{Path.home()}/code"))
    org = os.environ.get("GITHUB_ORG", "bernardTavares")
    meta_path = openclaw_dir / "projects-meta.json"

    paths = DetectPaths(
        kb_dir=kb_dir, openclaw_dir=openclaw_dir,
        code_dir=code_dir, org=org,
    )

    include = _parse_csv(getattr(args, "include", None))
    exclude = _parse_csv(getattr(args, "exclude", None))

    try:
        result = scan_all(
            meta_path, paths,
            skip_remote=getattr(args, "skip_remote", False),
            skip_systemctl=getattr(args, "skip_systemctl", False),
            skip_knowledge=getattr(args, "skip_knowledge", False),
            skip_orphans=skip_orphans,
            skip_drafts=skip_orphans,  # drafts share I/O cost; same gate
            include=include,
            exclude=exclude,
        )
    except Exception as e:  # noqa: BLE001
        _print(
            {"error": "scan_failed", "detail": str(e)},
            json_mode,
            f"erro: scan falhou: {e}",
        )
        return EXIT_RUNTIME

    generated_at = _now_iso()

    # Repair phase.
    repair_outcomes = []
    if fix and result.drifts:
        prompt_fn = _make_prompt_fn(auto_confirm)
        opts: Dict[str, Any] = {
            "actor": getattr(args, "actor", None) or "bernard",
            # Bot-specific opts not threaded through doctor — bot drift repair
            # in W5 only handles partial state (idempotent rerun). For absent
            # → provisioned, user must run `project adopt --bot=...`.
        }
        for drift in result.drifts:
            outcome = repair_drift(
                drift,
                paths=paths,
                meta_path=meta_path,
                opts=opts,
                auto_confirm=auto_confirm,
                prompt_fn=prompt_fn,
            )
            repair_outcomes.append(outcome)

    if json_mode:
        payload = _doctor_render.build_json_payload(
            result, generated_at=generated_at,
            repair_outcomes=repair_outcomes if fix else None,
        )
        _print(payload, json_mode=True)
        return EXIT_OK

    # Human render.
    text = _doctor_render.render_scan(result, generated_at=generated_at)
    print(text)
    if fix:
        print()
        print(_doctor_render.render_repair_outcomes(repair_outcomes))
    return EXIT_OK


def register_subcommand(pr_sub, leaf):
    """Register `project doctor` subcommand on the project subparser.

    Mirrors W4 `register_subcommand` in cmd_project_adopt.
    """
    p = leaf(pr_sub, "doctor")
    p.add_argument("--fix", action="store_true",
                   help="repair detected drifts (interactive by default)")
    p.add_argument("--auto-confirm", action="store_true", dest="auto_confirm",
                   help="non-interactive repair (skip prompts; ambiguous drifts skipped)")
    p.add_argument("--skip-orphans", action="store_true", dest="skip_orphans",
                   help="skip orphan + drafts_pending scan (faster, CI-friendly)")
    p.add_argument("--include", default=None,
                   help="comma-separated slug whitelist")
    p.add_argument("--exclude", default=None,
                   help="comma-separated slug blacklist")
    # Detection skip flags (mirror status / adopt).
    p.add_argument("--skip-remote", action="store_true", dest="skip_remote",
                   help="skip gh repo view (offline / CI)")
    p.add_argument("--skip-systemctl", action="store_true", dest="skip_systemctl",
                   help="skip systemctl is-active (CI / non-systemd hosts)")
    p.add_argument("--skip-knowledge", action="store_true", dest="skip_knowledge",
                   help="skip detect_knowledge_slot (no origin/main fetched)")
    p.set_defaults(func=cmd_project_doctor)
    return p
