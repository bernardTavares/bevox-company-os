"""`openclaw knowledge` — top-level subcommand dispatcher (skill V2).

W0 foundation: registra 4 sub-subcommands (audit, gap-report,
bootstrap-docs, retirement-scan). Implementação por wave:
- audit       → implementado em W3 (F1 commit watcher)
- gap-report  → W1 (F2 cross-project audit) — implementado
- bootstrap-docs → implementado em W4 (F3 greenfield generator)
- retirement-scan → W2 (F4 retirement detector) — implementado

Spec: bevox-knowledge/35_specs/_shared/2026-05-08-bevox-knowledge-contribute-skill-v2.md
"""
from __future__ import annotations

import argparse
from typing import Any

from lib.knowledge_watcher.telegram import dispatch_to_telegram


EXIT_OK = 0
EXIT_NOT_IMPLEMENTED = 64
EXIT_RUNTIME_ERROR = 2


def cmd_audit(args: argparse.Namespace) -> int:
    """F1 commit watcher — implementação W3.

    Cross-project audit: scans new commits since state.last_commit_processed
    per opted-in repo, classifies via heuristic+LLM, applies strategy per
    doc-type, dispatches Telegram digest. Idempotent.
    """
    import os
    from pathlib import Path

    from lib.knowledge_watcher.commit_watcher.runner import run_audit

    openclaw_dir = Path(os.environ.get("OPENCLAW_DIR", f"{Path.home()}/.openclaw"))
    kb_dir = Path(os.environ.get("BEVOX_KNOWLEDGE_DIR", f"{Path.home()}/bevox-knowledge"))
    code_dir = Path(os.environ.get("BEVOX_CODE_DIR", f"{Path.home()}/code"))
    meta_path = openclaw_dir / "projects-meta.json"

    try:
        results = run_audit(
            meta_path, kb_dir, code_dir,
            project=getattr(args, "repo", None),
            since=getattr(args, "since", None),
            dry_run=getattr(args, "dry_run", False),
        )
    except Exception as e:
        print(f"erro: audit failed: {e}")
        return EXIT_RUNTIME_ERROR

    if getattr(args, "json", False):
        import json as _json
        payload = [
            {"slug": r.repo_slug,
             "new_commits": r.new_commits_processed,
             "gaps_detected": r.gaps_detected,
             "last_commit_processed": r.last_commit_processed,
             "skipped_reason": r.skipped_reason}
            for r in results
        ]
        print(_json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        if not results:
            print("📥 [knowledge-watcher audit]")
            print()
            print("No opted-in projects found in projects-meta.json.")
            return EXIT_OK
        print("📥 [knowledge-watcher audit]")
        print()
        for r in results:
            if r.skipped_reason:
                print(f"  ⏭  {r.repo_slug}: {r.skipped_reason}")
                continue
            sha_short = r.last_commit_processed[:7] if r.last_commit_processed else "(none)"
            print(f"  ✅ {r.repo_slug}: {r.gaps_detected} gap(s) — last_sha={sha_short}")

    return EXIT_OK


def cmd_gap_report(args: argparse.Namespace) -> int:
    """F2 gap-report — implementação W1.

    Audits cross-project canonical state vs expectation rules.
    Outputs human markdown OR JSON.
    """
    import os
    from pathlib import Path

    from lib import projects_meta as _pm
    from lib.knowledge_watcher.gap_report import run_gap_report
    from lib.knowledge_watcher.expectations import Severity
    from lib.knowledge_watcher.formatters import format_human, format_json

    openclaw_dir = Path(os.environ.get("OPENCLAW_DIR", f"{Path.home()}/.openclaw"))
    kb_dir = Path(os.environ.get("BEVOX_KNOWLEDGE_DIR", f"{Path.home()}/bevox-knowledge"))
    code_dir = Path(os.environ.get("BEVOX_CODE_DIR", f"{Path.home()}/code"))
    meta_path = openclaw_dir / "projects-meta.json"

    try:
        meta = _pm.read_meta(meta_path)
    except Exception as e:
        print(f"erro: cannot read projects-meta.json: {e}")
        return EXIT_RUNTIME_ERROR

    severity_filter = None
    sev_arg = getattr(args, "severity", None)
    if sev_arg:
        try:
            severity_filter = Severity(sev_arg)
        except ValueError:
            print(f"erro: invalid --severity '{sev_arg}'")
            return EXIT_RUNTIME_ERROR

    reports = run_gap_report(
        kb_dir, code_dir, meta,
        project=getattr(args, "project", None),
        severity=severity_filter,
    )

    human_text = format_human(reports)
    if getattr(args, "json", False):
        print(format_json(reports))
    else:
        print(human_text)

    if getattr(args, "dispatch_telegram", False) or getattr(args, "dispatch_dry_run", False):
        any_gaps = any(getattr(r, "gaps", []) for r in reports)
        if any_gaps:
            from pathlib import Path
            import os
            from lib.knowledge_watcher.digest_header import format_summary_header
            openclaw_dir = Path(os.environ.get(
                "OPENCLAW_DIR", f"{Path.home()}/.openclaw"))
            kw_state_path = openclaw_dir / "knowledge-watcher" / "state.json"
            flat = [
                type("_FlatGap", (), {
                    "project_slug": r.slug,
                    "relative_path": g.folder,
                    "score": None,
                })()
                for r in reports for g in (getattr(r, "gaps", []) or [])
            ]
            header = format_summary_header(
                flat, title="📊 [knowledge gap-report cross-project]",
                score_attr=None,
            )
            _dispatch_with_guards(
                header + "\n\n" + human_text,
                kind="gap-report",
                state_path=kw_state_path,
                dry_run=getattr(args, "dispatch_dry_run", False),
                force=getattr(args, "force_dispatch", False),
            )

    return EXIT_OK


def cmd_bootstrap_docs(args: argparse.Namespace) -> int:
    """F3 greenfield doc generator — implementação W4.

    Bootstrap completo de documentação canonical para um project. Tiered
    strategy: MECÂNICO (factual, $0) → SEMI-AUTO (Haiku) → JUDGMENT (Sonnet
    paralelo via claude -p). 4 hallucination guardrails. Idempotente.
    """
    import os
    from pathlib import Path
    from lib.knowledge_watcher.greenfield.workflow import bootstrap_project

    kb_dir = Path(os.environ.get("BEVOX_KNOWLEDGE_DIR", f"{Path.home()}/bevox-knowledge"))
    code_dir = Path(os.environ.get("BEVOX_CODE_DIR", f"{Path.home()}/code"))

    slug = args.slug
    try:
        result = bootstrap_project(
            slug, kb_dir, code_dir,
            dry_run=getattr(args, "dry_run", False),
            no_adr=getattr(args, "no_adr", False),
            force_topics=getattr(args, "force_topics", None),  # NEW W5
            push_draft=getattr(args, "push_draft", False),  # NEW W7-extras
        )
    except Exception as e:
        print(f"erro: bootstrap failed: {e}")
        return EXIT_RUNTIME_ERROR

    if getattr(args, "json", False):
        import json as _json
        payload = {
            "slug": result.slug,
            "skipped_reason": result.skipped_reason,
            "docs_generated": [
                {
                    "tier": d.tier.value,
                    "doc_type": d.doc_type,
                    "path": d.relative_path,
                    "cost_usd": d.cost_usd,
                    "warnings": d.warnings,
                }
                for d in result.docs_generated
            ],
            "total_cost_usd": result.total_cost_usd,
            "duration_seconds": result.duration_seconds,
        }
        print(_json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        if result.skipped_reason:
            print(f"📥 [knowledge bootstrap-docs {slug}]")
            print()
            print(f"  ⏭  {result.skipped_reason}")
            return EXIT_OK

        print(f"📥 [knowledge bootstrap-docs {slug}]")
        print()
        for d in result.docs_generated:
            warn_count = len(d.warnings)
            warn_str = f" ⚠️  {warn_count} warning(s)" if warn_count else ""
            cost_str = f"${d.cost_usd:.2f}"
            already_exists = any("already exists" in w for w in d.warnings)
            marker = "⏭ " if already_exists else "✅"
            print(f"  {marker} {d.tier.value}/{d.doc_type}: {d.relative_path} ({cost_str}){warn_str}")
            for w in d.warnings:
                print(f"       └─ {w}")
        print()
        print(f"Total: ${result.total_cost_usd:.2f} em {result.duration_seconds:.1f}s")
        if result.draft_branch:
            print(f"📤 Draft branch: {result.draft_branch} (pushed)")

    return EXIT_OK


def cmd_retirement_scan(args: argparse.Namespace) -> int:
    """F4 retirement scan — implementação W2 + W3.5.

    Walks canonical bevox-knowledge folders, runs 5 detectors per doc,
    flags candidates with compound score >= 0.7. Never auto-retires
    (per spec §10.4 — sempre review humano via Telegram digest).

    W3.5: each flagged candidate is registered in state.json via add_gap
    (idempotent). _shared docs (no project_slug) are skipped.
    """
    import os
    from pathlib import Path

    from lib.knowledge_watcher.retirement.scanner import scan_retirement_candidates
    from lib.knowledge_watcher.formatters import (
        format_retirement_human, format_retirement_json,
    )
    from lib.knowledge_watcher.state import read_state, write_state

    kb_dir = Path(os.environ.get("BEVOX_KNOWLEDGE_DIR", f"{Path.home()}/bevox-knowledge"))
    code_dir = Path(os.environ.get("BEVOX_CODE_DIR", f"{Path.home()}/code"))
    openclaw_dir = Path(os.environ.get("OPENCLAW_DIR", f"{Path.home()}/.openclaw"))
    state_path = openclaw_dir / "knowledge-watcher" / "state.json"

    state = read_state(state_path)

    candidates = scan_retirement_candidates(
        kb_dir, code_dir,
        project=getattr(args, "project", None),
        state=state,
    )

    if candidates:
        write_state(state_path, state)

    human_text = format_retirement_human(candidates)
    if getattr(args, "json", False):
        print(format_retirement_json(candidates))
    else:
        print(human_text)

    if (getattr(args, "dispatch_telegram", False) or
            getattr(args, "dispatch_dry_run", False)) and candidates:
        from lib.knowledge_watcher.digest_header import format_summary_header
        header = format_summary_header(
            candidates, title="🗑️ [knowledge retirement-scan]",
        )
        _dispatch_with_guards(
            header + "\n\n" + human_text,
            kind="retirement-scan",
            state_path=state_path,
            dry_run=getattr(args, "dispatch_dry_run", False),
            force=getattr(args, "force_dispatch", False),
        )

    return EXIT_OK


def cmd_review_cli(args: argparse.Namespace) -> int:
    """CLI wrapper for cmd_review (W3.5)."""
    import os
    from pathlib import Path
    from lib.knowledge_watcher.state import read_state
    from lib.knowledge_watcher.commands import cmd_review

    openclaw_dir = Path(os.environ.get("OPENCLAW_DIR", f"{Path.home()}/.openclaw"))
    state_path = openclaw_dir / "knowledge-watcher" / "state.json"
    kb_remote = os.environ.get(
        "BEVOX_KNOWLEDGE_REMOTE_URL",
        "https://github.com/bernardTavares/bevox-knowledge",
    )
    state = read_state(state_path)
    r = cmd_review(state, args.gap_id, kb_remote_url=kb_remote)
    if getattr(args, "json", False):
        import json as _json
        print(_json.dumps({"ok": r.ok, "reply": r.reply, "exit_code": r.exit_code}))
    else:
        print(r.reply)
    return r.exit_code


def cmd_dismiss_cli(args: argparse.Namespace) -> int:
    """CLI wrapper for cmd_dismiss (W3.5)."""
    import os
    from pathlib import Path
    from lib.knowledge_watcher.state import read_state, write_state
    from lib.knowledge_watcher.commands import cmd_dismiss

    state_path = Path(os.environ.get("OPENCLAW_DIR", f"{Path.home()}/.openclaw")) / "knowledge-watcher" / "state.json"
    state = read_state(state_path)
    r = cmd_dismiss(state, args.gap_id)
    if r.ok and r.exit_code == 0:
        write_state(state_path, state)
    if getattr(args, "json", False):
        import json as _json
        print(_json.dumps({"ok": r.ok, "reply": r.reply, "exit_code": r.exit_code}))
    else:
        print(r.reply)
    return r.exit_code


def cmd_postpone_cli(args: argparse.Namespace) -> int:
    """CLI wrapper for cmd_postpone (W3.5)."""
    import os
    from pathlib import Path
    from lib.knowledge_watcher.state import read_state, write_state
    from lib.knowledge_watcher.commands import cmd_postpone

    state_path = Path(os.environ.get("OPENCLAW_DIR", f"{Path.home()}/.openclaw")) / "knowledge-watcher" / "state.json"
    state = read_state(state_path)
    r = cmd_postpone(state, args.gap_id, days=args.days)
    if r.ok and r.exit_code == 0:
        write_state(state_path, state)
    if getattr(args, "json", False):
        import json as _json
        print(_json.dumps({"ok": r.ok, "reply": r.reply, "exit_code": r.exit_code}))
    else:
        print(r.reply)
    return r.exit_code


def cmd_keep_cli(args: argparse.Namespace) -> int:
    """CLI wrapper for cmd_keep (W3.5)."""
    import os
    from pathlib import Path
    from lib.knowledge_watcher.state import read_state, write_state
    from lib.knowledge_watcher.commands import cmd_keep

    state_path = Path(os.environ.get("OPENCLAW_DIR", f"{Path.home()}/.openclaw")) / "knowledge-watcher" / "state.json"
    state = read_state(state_path)
    r = cmd_keep(state, args.gap_id)
    if r.ok and r.exit_code == 0:
        write_state(state_path, state)
    if getattr(args, "json", False):
        import json as _json
        print(_json.dumps({"ok": r.ok, "reply": r.reply, "exit_code": r.exit_code}))
    else:
        print(r.reply)
    return r.exit_code


def cmd_keep_permanent_cli(args: argparse.Namespace) -> int:
    """CLI wrapper for cmd_keep_permanent (W3.5)."""
    import os
    from pathlib import Path
    from lib.knowledge_watcher.state import read_state, write_state
    from lib.knowledge_watcher.commands import cmd_keep_permanent

    state_path = Path(os.environ.get("OPENCLAW_DIR", f"{Path.home()}/.openclaw")) / "knowledge-watcher" / "state.json"
    kb_dir = Path(os.environ.get("BEVOX_KNOWLEDGE_DIR", f"{Path.home()}/bevox-knowledge"))
    state = read_state(state_path)
    r = cmd_keep_permanent(
        state, args.gap_id, kb_dir=kb_dir,
        dry_run=getattr(args, "dry_run", False),
        push=getattr(args, "push", True),
    )
    if r.ok and r.exit_code == 0:
        write_state(state_path, state)
    if getattr(args, "json", False):
        import json as _json
        print(_json.dumps({"ok": r.ok, "reply": r.reply, "exit_code": r.exit_code}))
    else:
        print(r.reply)
    return r.exit_code


def cmd_retire_cli(args: argparse.Namespace) -> int:
    """CLI wrapper for cmd_retire (W3.5)."""
    import os
    from pathlib import Path
    from lib.knowledge_watcher.state import read_state, write_state
    from lib.knowledge_watcher.commands import cmd_retire

    state_path = Path(os.environ.get("OPENCLAW_DIR", f"{Path.home()}/.openclaw")) / "knowledge-watcher" / "state.json"
    kb_dir = Path(os.environ.get("BEVOX_KNOWLEDGE_DIR", f"{Path.home()}/bevox-knowledge"))
    state = read_state(state_path)
    r = cmd_retire(state, args.gap_id, kb_dir=kb_dir, push=getattr(args, "push", True))
    if r.ok and r.exit_code == 0:
        write_state(state_path, state)
    if getattr(args, "json", False):
        import json as _json
        print(_json.dumps({"ok": r.ok, "reply": r.reply, "exit_code": r.exit_code}))
    else:
        print(r.reply)
    return r.exit_code


def cmd_accept_cli(args: argparse.Namespace) -> int:
    """CLI wrapper for cmd_accept (W3.5). Always writes state (2-step token flow)."""
    import os
    from pathlib import Path
    from lib.knowledge_watcher.state import read_state, write_state
    from lib.knowledge_watcher.commands import cmd_accept

    state_path = Path(os.environ.get("OPENCLAW_DIR", f"{Path.home()}/.openclaw")) / "knowledge-watcher" / "state.json"
    kb_dir = Path(os.environ.get("BEVOX_KNOWLEDGE_DIR", f"{Path.home()}/bevox-knowledge"))
    state = read_state(state_path)
    r = cmd_accept(
        state, args.gap_id,
        confirm_token=getattr(args, "token", None),
        kb_dir=kb_dir,
        push=getattr(args, "push", True),
    )
    # accept writes state in both steps (step 1: stores token; step 2: stores ACCEPTED)
    write_state(state_path, state)
    if getattr(args, "json", False):
        import json as _json
        print(_json.dumps({"ok": r.ok, "reply": r.reply, "exit_code": r.exit_code}))
    else:
        print(r.reply)
    return r.exit_code


def _dispatch_with_guards(
    text: str,
    kind: str,
    state_path,
    *,
    dry_run: bool = False,
    force: bool = False,
) -> bool:
    """Wrap dispatch_to_telegram with --dispatch-dry-run + throttle.

    - dry_run=True: print payload chunks instead of sending HTTP
    - throttle: skip if last dispatch for `kind` < 30min ago (state.json
      `global.last_dispatch_at[<kind>]`)
    - force=True bypasses throttle

    Returns True on actual send OR dry-run; False if throttled.
    """
    if dry_run:
        from lib.knowledge_watcher.telegram import _chunk_text, _TELEGRAM_CHUNK_CHARS
        chunks = _chunk_text(text, _TELEGRAM_CHUNK_CHARS)
        print(f"\n[DRY-RUN dispatch '{kind}'] would send "
              f"{len(chunks)} chunk(s):")
        for i, c in enumerate(chunks, 1):
            print(f"--- chunk {i}/{len(chunks)} ({len(c)} chars) ---")
            print(c)
        print(f"--- end of dry-run payload ---\n")
        return True

    from lib.knowledge_watcher.dispatch_throttle import (
        is_throttled, record_dispatch,
    )
    if not force and is_throttled(kind, state_path):
        print(f"⏭ dispatch '{kind}' throttled (last sent < 30min ago); "
              f"use --force-dispatch to override")
        return False

    from pathlib import Path as _P
    ok = dispatch_to_telegram(None, text)
    if ok:
        record_dispatch(kind, _P(state_path))
    return ok


def cmd_feedback_stats(args: argparse.Namespace) -> int:
    """Show aggregated F1/F4 decision stats + F3 edit-distance trends.

    Defaults to last 30 days. JSON via --json. Surfaces tuning candidates
    (signal combos with keep_ratio > 90%) with ⚠️ marker.
    """
    from lib.knowledge_watcher.feedback_stats import (
        stats_by_doc_type, stats_f3_edit_distance, stats_by_signal_combo,
    )

    days = getattr(args, "days", 30)
    by_dt = stats_by_doc_type(days)
    by_combo = stats_by_signal_combo(days)
    f3 = stats_f3_edit_distance(days)

    if getattr(args, "json", False):
        import json as _json
        print(_json.dumps({
            "days": days,
            "by_doc_type": by_dt,
            "by_signal_combo": by_combo,
            "f3_edit_distance": f3,
        }, indent=2))
        return EXIT_OK

    print(f"📊 Feedback stats — last {days} days\n")

    if not by_dt and not f3:
        print("(empty — no decisions or F3 outputs recorded yet)")
        return EXIT_OK

    if by_dt:
        print("By doc-type:")
        for r in by_dt:
            print(
                f"  {r['doc_type']:14} (n={r['n']:3}): "
                f"keep {r['keep_ratio']*100:>3.0f}% · "
                f"retire {r['retire_ratio']*100:>3.0f}% · "
                f"keep_perm {r['keep_permanent_ratio']*100:>3.0f}% · "
                f"dismiss {r['dismiss_ratio']*100:>3.0f}%"
            )
        print()

    if by_combo:
        print("By signal combo (top 10):")
        for r in by_combo[:10]:
            warn = "⚠️ tuning candidate" if r["keep_ratio"] > 0.9 else ""
            print(
                f"  {r['doc_type']:8} + {r['signal_combo']:12} "
                f"(n={r['n']:3}): keep {r['keep_ratio']*100:>3.0f}% "
                f"{warn}"
            )
        print()

    if f3:
        print("F3 edit distance:")
        for r in f3:
            print(
                f"  {r['generator']:14} (n={r['n']:3}): "
                f"p50={r['p50']:.2f} p90={r['p90']:.2f} mean={r['mean']:.2f}"
            )

    return EXIT_OK


def cmd_tune_suggest(args: argparse.Namespace) -> int:
    """Run tune-suggest analyzer; optionally dispatch Telegram (cron mode)."""
    from lib.knowledge_watcher.tune_suggest import (
        analyze_tuning_candidates, format_suggestions_for_telegram,
    )
    days = getattr(args, "days", 28)
    suggestions = analyze_tuning_candidates(days)
    text = format_suggestions_for_telegram(suggestions)
    print(text)
    if (getattr(args, "dispatch_telegram", False) or
            getattr(args, "dispatch_dry_run", False)) and suggestions:
        from pathlib import Path
        import os
        openclaw_dir = Path(os.environ.get(
            "OPENCLAW_DIR", f"{Path.home()}/.openclaw"))
        kw_state_path = openclaw_dir / "knowledge-watcher" / "state.json"
        _dispatch_with_guards(
            text,
            kind="tune-suggest",
            state_path=kw_state_path,
            dry_run=getattr(args, "dispatch_dry_run", False),
            force=getattr(args, "force_dispatch", False),
        )
    return EXIT_OK


def cmd_tune(args: argparse.Namespace) -> int:
    """Apply runtime override to skill_config.json.

    Currently supports `tune <doc_type> threshold <value>` only. Idempotent.
    """
    from lib.knowledge_watcher.skill_config import set_doc_type_threshold
    field = getattr(args, "field", "")
    if field != "threshold":
        print(f"❌ /tune: only 'threshold' field supported (got '{field}')")
        return EXIT_RUNTIME_ERROR
    try:
        value = float(args.value)
    except (TypeError, ValueError):
        print(f"❌ /tune: value must be numeric (got '{args.value}')")
        return EXIT_RUNTIME_ERROR
    if not (0.0 <= value <= 1.0):
        print(f"❌ /tune: value must be in [0.0, 1.0] (got {value})")
        return EXIT_RUNTIME_ERROR
    set_doc_type_threshold(args.doc_type, value)
    print(f"✅ Override aplicado: {args.doc_type} threshold = {value}")
    return EXIT_OK


def cmd_cron_alert(args: argparse.Namespace) -> int:
    """Dispatch a Telegram alert for a failed systemd unit.

    Triggered by `OnFailure=openclaw-cron-alerter@%n.service` wired in
    F1/F2/F4 service files. Pulls last 10 journal lines for the unit and
    formats a digestible alert that lands in bot-knowledge General topic.
    """
    import datetime as _dt
    import subprocess as _sp

    target = getattr(args, "target", "") or ""
    if not target:
        return EXIT_RUNTIME_ERROR

    try:
        proc = _sp.run(
            ["journalctl", "--user", "-u", target, "-n", "10",
             "--no-pager", "-o", "short"],
            capture_output=True, text=True, timeout=10,
        )
        log_excerpt = (proc.stdout or "").strip() or "(no log lines available)"
    except Exception:
        log_excerpt = "(could not read journal)"

    now = _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat() + "Z"
    text = (
        f"🚨 [knowledge-watcher] cron failure\n"
        f"Unit: {target}\n"
        f"Time: {now}\n\n"
        f"Last 10 log lines:\n{log_excerpt[:2000]}\n\n"
        f"Run: journalctl --user -u {target} --since=today"
    )
    ok = dispatch_to_telegram(None, text)
    return EXIT_OK if ok else EXIT_RUNTIME_ERROR


def register_subcommand(knowledge_sub, leaf) -> None:
    """Register 12 subcommands under `knowledge` (4 scan + 7 action + cron-alert).

    Args:
        knowledge_sub: argparse subparsers from parent `knowledge` parser.
        leaf: helper from api.py that adds subparser with shared common args.
    """
    audit = leaf(knowledge_sub, "audit")
    audit.add_argument("--repo", default=None,
                       help="filter to single repo (slug)")
    audit.add_argument("--since", default=None,
                       help="ISO-8601 datetime; process commits after this")
    audit.add_argument("--dry-run", action="store_true", dest="dry_run",
                       help="preview without state mutations")
    audit.set_defaults(func=cmd_audit)

    gap_report = leaf(knowledge_sub, "gap-report")
    gap_report.add_argument("--all", action="store_true",
                            help="audit all opted-in projects")
    gap_report.add_argument("--project", default=None,
                            help="single project slug")
    gap_report.add_argument("--severity", default=None,
                            choices=["always-required", "conditional"],
                            help="filter by gap severity")
    gap_report.add_argument("--dispatch-telegram", action="store_true",
                            dest="dispatch_telegram",
                            help="also send digest to bot-knowledge "
                                 "(topic `knowledge`); cron mode")
    gap_report.add_argument("--dispatch-dry-run", action="store_true",
                            dest="dispatch_dry_run",
                            help="print payload chunks but skip HTTP send "
                                 "(for testing format/chunking without spam)")
    gap_report.add_argument("--force-dispatch", action="store_true",
                            dest="force_dispatch",
                            help="bypass 30min throttle for this kind")
    gap_report.set_defaults(func=cmd_gap_report)

    bootstrap = leaf(knowledge_sub, "bootstrap-docs")
    bootstrap.add_argument("slug", help="project slug to bootstrap")
    bootstrap.add_argument("--no-adr", action="store_true", dest="no_adr",
                           help="skip Tier JUDGMENT (ADR proposes)")
    bootstrap.add_argument("--dry-run", action="store_true", dest="dry_run")
    bootstrap.add_argument(
        "--force-topic", action="append", dest="force_topics", default=None,
        help="bypass overlap detection for this topic slug; repeatable",
    )
    bootstrap.add_argument(
        "--push-draft", action="store_true", dest="push_draft",
        help="auto-create draft branch (draft/skill-v2-bootstrap-<slug>-<date>) "
             "+ commit + push to origin (governance per CLAUDE.md §7)",
    )
    bootstrap.set_defaults(func=cmd_bootstrap_docs)

    retirement = leaf(knowledge_sub, "retirement-scan")
    retirement.add_argument("--project", default=None,
                            help="single project slug")
    retirement.add_argument("--dispatch-telegram", action="store_true",
                            dest="dispatch_telegram",
                            help="also send digest to bot-knowledge "
                                 "(topic `knowledge`); cron mode")
    retirement.add_argument("--dispatch-dry-run", action="store_true",
                            dest="dispatch_dry_run",
                            help="print payload chunks but skip HTTP send "
                                 "(for testing format/chunking without spam)")
    retirement.add_argument("--force-dispatch", action="store_true",
                            dest="force_dispatch",
                            help="bypass 30min throttle for this kind")
    retirement.set_defaults(func=cmd_retirement_scan)

    # --- W3.5 action handlers ---

    review = leaf(knowledge_sub, "review")
    review.add_argument("gap_id")
    review.set_defaults(func=cmd_review_cli)

    dismiss = leaf(knowledge_sub, "dismiss")
    dismiss.add_argument("gap_id")
    dismiss.set_defaults(func=cmd_dismiss_cli)

    postpone = leaf(knowledge_sub, "postpone")
    postpone.add_argument("gap_id")
    postpone.add_argument("days", type=int)
    postpone.set_defaults(func=cmd_postpone_cli)

    accept = leaf(knowledge_sub, "accept")
    accept.add_argument("gap_id")
    accept.add_argument("token", nargs="?", default=None)
    accept.add_argument("--no-push", action="store_false", dest="push", default=True)
    accept.set_defaults(func=cmd_accept_cli)

    retire = leaf(knowledge_sub, "retire")
    retire.add_argument("gap_id")
    retire.add_argument("--no-push", action="store_false", dest="push", default=True)
    retire.set_defaults(func=cmd_retire_cli)

    keep = leaf(knowledge_sub, "keep")
    keep.add_argument("gap_id")
    keep.set_defaults(func=cmd_keep_cli)

    keep_perm = leaf(knowledge_sub, "keep-permanent")
    keep_perm.add_argument("gap_id")
    keep_perm.add_argument("--dry-run", action="store_true", dest="dry_run")
    keep_perm.add_argument("--no-push", action="store_false", dest="push", default=True)
    keep_perm.set_defaults(func=cmd_keep_permanent_cli)

    cron_alert = leaf(knowledge_sub, "cron-alert")
    cron_alert.add_argument("--target", required=True,
                            help="systemd unit name (e.g. "
                                 "openclaw-knowledge-watcher.service)")
    cron_alert.set_defaults(func=cmd_cron_alert)

    fb_stats = leaf(knowledge_sub, "feedback-stats")
    fb_stats.add_argument("--days", type=int, default=30,
                          help="time window (default 30)")
    fb_stats.set_defaults(func=cmd_feedback_stats)

    ts = leaf(knowledge_sub, "tune-suggest")
    ts.add_argument("--days", type=int, default=28,
                    help="lookback window for tuning analysis (default 28)")
    ts.add_argument("--dispatch-telegram", action="store_true",
                    dest="dispatch_telegram",
                    help="also send suggestions to bot-knowledge (cron mode)")
    ts.add_argument("--dispatch-dry-run", action="store_true",
                    dest="dispatch_dry_run",
                    help="print payload but skip HTTP send")
    ts.add_argument("--force-dispatch", action="store_true",
                    dest="force_dispatch",
                    help="bypass 30min throttle")
    ts.set_defaults(func=cmd_tune_suggest)

    tn = leaf(knowledge_sub, "tune")
    tn.add_argument("doc_type",
                    help="doc type to tune (adr, spec, prd, architecture, ...)")
    tn.add_argument("field", default="threshold",
                    help="field to override (only 'threshold' supported)")
    tn.add_argument("value",
                    help="new value (float in [0.0, 1.0])")
    tn.set_defaults(func=cmd_tune)
