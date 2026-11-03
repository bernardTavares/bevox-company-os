"""`openclaw project adopt <slug>` — brownfield entry point.

Spec: bevox-knowledge/35_specs/openclaw/2026-05-07-project-lifecycle-w4-v1.md
ADR-013 §CLI canônicos · ADR-014 §Amendment 3 (skill as provider).

Detects existing capabilities via capability_detect.detect_all → diffs vs
declared meta → provisions missing capabilities idempotently in fixed order
(per spec §Sequência de adopt). Resulting projects-meta entry has
`source: adopted`.

Idempotent: rerun in fully-provisioned project is no-op (zero mutations,
exit 0 with summary line). Drift is logged + skipped in non-interactive mode
(W5 doctor is the canonical repair entry).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from lib import projects_meta as _pm
from lib.capability_detect import DetectPaths, detect_all
from lib.provisioners._registry import ADOPT_ORDER

# Exit codes mirroring api.py.
EXIT_OK = 0
EXIT_VALIDATION = 1
EXIT_RUNTIME = 2

# Allowed --bot values.
BOT_FLAG_VALUES = ("yes", "no", "auto")


def _print(payload: Any, json_mode: bool, human: Optional[str] = None) -> None:
    if json_mode:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        if human is not None:
            print(human)
        else:
            print(json.dumps(payload, ensure_ascii=False, indent=2))


def _now_iso() -> str:
    return _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _decide_action(
    capability: str,
    detected_state: str,
    *,
    interactive: bool,
    bot_flag: str,
    skip: List[str],
    prompt_fn,
) -> Tuple[str, str]:
    """Decide action for one capability based on detected state + flags.

    Returns (action, reason). action ∈ {skip, repair, provision, prompt-yes,
    prompt-no, skip-flag, skip-already}.
    """
    if capability in skip:
        return ("skip-flag", f"--skip={capability}")
    if detected_state == "provisioned":
        return ("skip-already", "already provisioned")
    if detected_state == "drifted":
        # Drift is W5 doctor territory — log + skip in non-interactive,
        # prompt in interactive (Y = re-provision over drift).
        if not interactive:
            return ("skip", "drifted (use W5 doctor or rerun --bot=yes etc.)")
        if prompt_fn(f"capability '{capability}' drifted; reprovisionar? (Y/n) "):
            return ("provision", "user confirmed reprovision over drift")
        return ("skip", "user declined reprovision")
    if detected_state == "partial":
        # Partial → repair (idempotent rerun of provisioner).
        return ("repair", "partial state — rerun provisioner")

    # absent
    if capability == "bot":
        if bot_flag == "yes":
            return ("provision", "--bot=yes")
        if bot_flag == "no":
            return ("skip-flag", "--bot=no")
        if bot_flag == "auto":
            # auto: provisioned only if profile dir exists (handled by
            # detect; if we reach here state==absent → skip).
            return ("skip", "--bot=auto and no profile detected")
        # interactive default for bot: prompt
        if prompt_fn("criar bot Telegram? (y/N) ", default_yes=False):
            return ("prompt-yes", "user confirmed")
        return ("prompt-no", "user declined")
    # other capabilities: default Y in interactive
    if not interactive:
        return ("skip", "non-interactive default skip for absent")
    if prompt_fn(f"criar {capability}? (Y/n) "):
        return ("prompt-yes", "user confirmed")
    return ("prompt-no", "user declined")


def _make_prompt_fn(non_interactive: bool):
    """Return a callable that returns bool, respecting non-interactive."""
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


def _ensure_meta_entry(
    *,
    meta_path: Path,
    slug: str,
    description: str,
    domain: str,
) -> Dict:
    """Ensure projects-meta entry exists for slug. Create skeleton if missing.

    Returns the entry dict. If created fresh, source=adopted. If exists,
    leaves source untouched (don't reclassify user_created → adopted on rerun).
    """
    data = _pm.read_meta(meta_path)
    projects = data.setdefault("projects", {})
    if slug in projects:
        return projects[slug]
    entry = {
        "name": slug,
        "description": description or "",
        "domain": domain or "",
        "github_url": f"https://github.com/bernardTavares/{slug}",
        "bot_id": None,
        "bot_username": None,
        "bot_port": None,
        "adopted_at": _now_iso(),
        "source": "adopted",
        "capabilities_schema_version": _pm.CAPABILITY_SCHEMA_VERSION,
        "capabilities": _pm.empty_capability_set(),
        "knowledge_watcher": dict(_pm.DEFAULT_KNOWLEDGE_WATCHER),
    }
    projects[slug] = entry
    _pm.write_meta(meta_path, data)
    return entry


def _record_capability(
    meta_path: Path,
    slug: str,
    capability: str,
    state: str,
    fields: dict,
) -> None:
    """Persist capability state via projects_meta helper. Best-effort."""
    try:
        _pm.set_capability_state(meta_path, slug, capability, state, **fields)
    except _pm.MetaError as e:
        # Surface but don't crash the whole adopt run.
        print(f"warn: failed to record {capability}: {e}", file=sys.stderr)


def _run_provisioner(
    capability: str,
    *,
    slug: str,
    paths: DetectPaths,
    meta_path: Path,
    meta_entry: Dict,
    opts: Dict,
) -> Dict:
    """Dispatch to the right provisioner module. Returns serializable dict."""
    if capability == "knowledge_slot":
        from lib.provisioners.knowledge import provision_knowledge
        try:
            res = provision_knowledge(
                slug,
                bk_path=paths.kb_dir,
                prd_text=opts.get("prd_text"),
                project_name=meta_entry.get("name") or slug,
                description=meta_entry.get("description") or "",
            )
            return {
                "state": res.state,
                "fields": {
                    "slot": res.slot,
                    "branch_at_bootstrap": res.branch,
                    "folders_present": 9,
                    "folders_total": 9,
                },
            }
        except Exception as e:
            return {"state": "partial", "fields": {}, "error": str(e)}

    if capability == "workspace":
        from lib.provisioners.workspace import provision_workspace
        res = provision_workspace(
            slug,
            openclaw_dir=paths.openclaw_dir,
            name=meta_entry.get("name") or slug,
            domain=meta_entry.get("domain") or "",
        )
        return {
            "state": res.state,
            "fields": {"path": res.path} if res.path else {},
            "error": res.error,
        }

    if capability == "persona":
        from lib.provisioners.persona import provision_persona
        res = provision_persona(
            slug,
            openclaw_dir=paths.openclaw_dir,
            name=meta_entry.get("name") or slug,
            domain=meta_entry.get("domain") or "",
            prd_text=opts.get("prd_text"),
        )
        return {
            "state": res.state,
            "fields": {"persona_status": res.persona_status}
                      if res.persona_status else {},
            "error": res.error,
        }

    if capability == "bot":
        from lib.provisioners.bot import provision_bot
        res = provision_bot(
            slug,
            openclaw_dir=paths.openclaw_dir,
            bot_id=opts.get("bot_id") or slug,
            bot_port=opts.get("bot_port"),
            token=opts.get("bot_token"),
            chat_id=opts.get("bot_chat_id"),
            allow_from=opts.get("bot_allow_from"),
            skills=opts.get("bot_skills"),
            project_slug=slug,
        )
        fields: Dict[str, Any] = {}
        if res.bot_id:
            fields["area"] = res.bot_id
        if res.bot_port:
            fields["port"] = res.bot_port
        if res.profile_dir:
            fields["profile"] = res.profile_dir
        return {
            "state": res.state,
            "fields": fields,
            "error": res.error,
        }

    if capability == "telegram_topics":
        from lib.provisioners.telegram_topics import provision_telegram_topics
        res = provision_telegram_topics(
            slug,
            openclaw_dir=paths.openclaw_dir,
            meta_path=meta_path,
        )
        return {
            "state": res.state,
            "fields": {
                "created": res.created,
                "existing": res.existing,
            },
            "error": res.error,
        }

    if capability == "kanban_sprints":
        from lib.provisioners.kanban_sprints import provision_kanban_sprints
        res = provision_kanban_sprints(slug, actor=opts.get("actor", "bernard"))
        return {
            "state": res.state,
            "fields": {"sprints_created": res.sprints_created},
            "error": res.error,
        }

    if capability == "code_repo":
        from lib.provisioners.code_repo import provision_code_repo
        res = provision_code_repo(
            slug, code_dir=paths.code_dir, org=paths.org,
        )
        fields = {}
        if res.path:
            fields["path"] = res.path
        if res.github:
            fields["github"] = res.github
        return {
            "state": res.state,
            "fields": fields,
            "error": res.error,
        }

    if capability == "mission_control":
        from lib.provisioners.mission_control import provision_mission_control
        res = provision_mission_control(slug)
        fields = {}
        if res.note:
            fields["note"] = res.note
        return {
            "state": res.state,
            "fields": fields,
            "error": res.error,
        }

    return {"state": "absent", "fields": {}, "error": f"no provisioner for {capability}"}


def cmd_project_adopt(args: argparse.Namespace) -> int:
    """Brownfield adopt entry point. See module docstring."""
    slug = args.slug
    if not slug or not isinstance(slug, str):
        _print({"error": "missing_slug"}, args.json, "erro: slug obrigatório")
        return EXIT_VALIDATION

    bot_flag = (args.bot or "").lower() if args.bot else ""
    if bot_flag and bot_flag not in BOT_FLAG_VALUES:
        _print(
            {"error": "invalid_bot_flag", "value": bot_flag,
             "allowed": list(BOT_FLAG_VALUES)},
            args.json,
            f"erro: --bot deve ser yes|no|auto (got '{bot_flag}')",
        )
        return EXIT_VALIDATION

    if args.non_interactive and not bot_flag:
        _print(
            {"error": "non_interactive_requires_bot_flag",
             "hint": "pass --bot=yes|no|auto"},
            args.json,
            "erro: --non-interactive exige --bot=<yes|no|auto>",
        )
        return EXIT_VALIDATION

    skip = [s.strip() for s in (args.skip or "").split(",") if s.strip()]
    bad_skip = [s for s in skip if s not in ADOPT_ORDER]
    if bad_skip:
        _print(
            {"error": "invalid_skip", "unknown": bad_skip,
             "allowed": list(ADOPT_ORDER)},
            args.json,
            f"erro: --skip valores inválidos: {bad_skip}",
        )
        return EXIT_VALIDATION

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

    # Validate slot is canonical (skill helper) — non-fatal: if skill lib
    # absent, fall through with warning. Real validation happens inside
    # provision_knowledge anyway.
    if not getattr(args, "skip_slot_check", False):
        slot_resolve = (
            kb_dir / "99_templates"
            / "skill-bevox-knowledge-contribute" / "lib" / "slot_resolve.sh"
        )
        if slot_resolve.is_file():
            import subprocess
            try:
                rc = subprocess.run(
                    ["bash", str(slot_resolve), slug],
                    capture_output=True, text=True, timeout=10,
                ).returncode
            except (subprocess.TimeoutExpired, FileNotFoundError):
                rc = 0  # soft-fail
            if rc != 0:
                _print(
                    {"error": "slot_non_canonical", "slug": slug},
                    args.json,
                    f"erro: slug '{slug}' não é canônico (slot_resolve)",
                )
                return EXIT_VALIDATION

    # Load PRD text if --prd provided.
    prd_text: Optional[str] = None
    if args.prd:
        prd_path = Path(args.prd)
        if not prd_path.is_file():
            _print(
                {"error": "prd_file_missing", "path": str(prd_path)},
                args.json,
                f"erro: --prd não encontrado: {prd_path}",
            )
            return EXIT_VALIDATION
        prd_text = prd_path.read_text(encoding="utf-8")

    # Ensure meta entry (skeleton with source=adopted if missing).
    if not args.dry_run:
        entry = _ensure_meta_entry(
            meta_path=meta_path,
            slug=slug,
            description=args.description or "",
            domain=args.domain or "",
        )
    else:
        # In dry-run, don't touch meta. Build a virtual entry for detect.
        meta = _pm.read_meta(meta_path)
        entry = (meta.get("projects") or {}).get(slug) or {
            "name": slug, "description": args.description or "",
            "domain": args.domain or "",
            "capabilities": _pm.empty_capability_set(),
            "source": "adopted",
        }

    # Detect all capabilities.
    detected = detect_all(
        slug, paths, meta_entry=entry,
        skip_remote=getattr(args, "skip_remote", False),
        skip_systemctl=getattr(args, "skip_systemctl", False),
        skip_knowledge=getattr(args, "skip_knowledge", False),
    )

    interactive = not args.non_interactive
    prompt_fn = _make_prompt_fn(args.non_interactive)

    plan: List[Dict] = []
    for capability in ADOPT_ORDER:
        det = detected.get(capability) or {"state": "absent"}
        det_state = det.get("state", "absent")
        action, reason = _decide_action(
            capability, det_state,
            interactive=interactive,
            bot_flag=bot_flag,
            skip=skip,
            prompt_fn=prompt_fn,
        )
        plan.append({
            "capability": capability,
            "detected": det_state,
            "action": action,
            "reason": reason,
        })

    # Validate bot args early when bot will actually be provisioned. Avoids
    # discovering at provisioner runtime that --bot-port/token/chat-id/allow-from
    # are missing (which previously surfaced as a per-capability error in the
    # adopt result table).
    will_provision_bot = any(
        r["capability"] == "bot"
        and r["action"] in ("provision", "prompt-yes", "repair")
        for r in plan
    )
    if will_provision_bot and not args.dry_run:
        missing = [
            name for name, val in (
                ("--bot-port", args.bot_port),
                ("--bot-token", args.bot_token),
                ("--bot-chat-id", args.bot_chat_id),
                ("--bot-allow-from", args.bot_allow_from),
            ) if not val
        ]
        if missing:
            _print(
                {"error": "bot_args_missing", "missing": missing,
                 "hint": "all 4 are required when adopt will provision the bot"},
                args.json,
                f"erro: provisão de bot exige {', '.join(missing)}",
            )
            return EXIT_VALIDATION

    # Dry-run: render plan + exit.
    if args.dry_run:
        if args.json:
            payload = {
                "slug": slug,
                "dry_run": True,
                "source": entry.get("source", "adopted"),
                "plan": plan,
            }
            _print(payload, json_mode=True)
        else:
            print(f"Adopt plan for {slug}:")
            print()
            print(f"  {'Capability':<18} | {'Detected':<13} | Action")
            print(f"  {'-' * 18}-+-{'-' * 13}-+-{'-' * 30}")
            for row in plan:
                print(
                    f"  {row['capability']:<18} | "
                    f"{row['detected']:<13} | "
                    f"{row['action']} ({row['reason']})"
                )
            print()
            print(f"Total: {len(plan)} capabilities planned. "
                  f"Run without --dry-run to execute.")
        return EXIT_OK

    # Execute provisioners per plan.
    opts: Dict[str, Any] = {
        "prd_text": prd_text,
        "actor": getattr(args, "actor", None) or "bernard",
        "bot_id": args.bot_id,
        "bot_port": args.bot_port,
        "bot_token": args.bot_token,
        "bot_chat_id": args.bot_chat_id,
        "bot_allow_from": args.bot_allow_from,
        "bot_skills": args.bot_skills,
    }

    results: List[Dict] = []
    any_run = False
    for row in plan:
        capability = row["capability"]
        action = row["action"]
        if action in ("skip", "skip-flag", "skip-already", "prompt-no"):
            # Sync meta to detected state when reality says provisioned —
            # closes drift bug where declared stayed stale (e.g. absent)
            # despite detector confirming the capability is present.
            if action == "skip-already":
                det = detected.get(capability) or {}
                fields = {k: v for k, v in det.items() if k != "state"}
                _record_capability(
                    meta_path, slug, capability, "provisioned", fields,
                )
            results.append({**row, "executed": False})
            continue
        # repair / provision / prompt-yes → run provisioner
        any_run = True
        prov_result = _run_provisioner(
            capability,
            slug=slug, paths=paths, meta_path=meta_path,
            meta_entry=entry, opts=opts,
        )
        new_state = prov_result.get("state", "partial")
        fields = prov_result.get("fields") or {}

        # Map state→capability_state for projects-meta.
        if new_state in _pm.CAPABILITY_STATES:
            _record_capability(
                meta_path, slug, capability, new_state, fields,
            )
        else:
            # Unknown state — record as partial.
            _record_capability(
                meta_path, slug, capability, "partial", fields,
            )

        results.append({
            **row,
            "executed": True,
            "result_state": new_state,
            "fields": fields,
            "error": prov_result.get("error"),
        })

    # Update last_adopt_at audit timestamp.
    try:
        _pm.update_project(meta_path, slug, {"last_adopt_at": _now_iso()})
    except _pm.MetaError:
        pass  # entry should always exist at this point

    # Final detect for summary.
    final_meta = _pm.read_meta(meta_path)
    final_entry = (final_meta.get("projects") or {}).get(slug) or {}
    final_caps = final_entry.get("capabilities") or {}

    if args.json:
        payload = {
            "slug": slug,
            "source": final_entry.get("source"),
            "noop": not any_run,
            "results": results,
            "capabilities": final_caps,
        }
        _print(payload, json_mode=True)
        return EXIT_OK

    # Human render.
    print(f"Adopt result for {slug}:")
    for row in results:
        suffix = ""
        if row.get("executed"):
            suffix = f" → {row.get('result_state')}"
            if row.get("error"):
                suffix += f"  [error: {row['error']}]"
        print(
            f"  {row['capability']:<18} {row['action']:<14}"
            f" ({row['reason']}){suffix}"
        )
    if not any_run:
        print()
        print("All capabilities already provisioned. No-op.")

    # Optional F3 bootstrap-docs hook (opt-in via --bootstrap-docs).
    # Skipped on dry-run + on adopt errors (any row with error field set).
    if (
        getattr(args, "bootstrap_docs", False)
        and not args.dry_run
        and not any(r.get("error") for r in results)
    ):
        print()
        print(f"🌱 [bootstrap-docs {slug}] running F3 greenfield generator…")
        try:
            from lib.knowledge_watcher.greenfield.workflow import bootstrap_project
            result = bootstrap_project(
                slug, kb_dir, code_dir,
                dry_run=False,
                no_adr=getattr(args, "bootstrap_no_adr", False),
                push_draft=True,  # adopt always pushes draft (governance)
            )
            if result.skipped_reason:
                print(f"  ⏭  {result.skipped_reason}")
            else:
                for d in result.docs_generated:
                    cost_str = f"${d.cost_usd:.2f}"
                    already = any("already exists" in w for w in d.warnings)
                    marker = "⏭ " if already else "✅"
                    print(f"  {marker} {d.tier.value}/{d.doc_type}: "
                          f"{d.relative_path} ({cost_str})")
                print(f"  Total: ${result.total_cost_usd:.2f}")
                if result.draft_branch:
                    print(f"  📤 Draft branch: {result.draft_branch} (pushed)")
        except Exception as e:
            print(f"  ⚠️  bootstrap-docs failed: {e}")

    return EXIT_OK


def register_subcommand(pr_sub, leaf):
    """Register `project adopt` subcommand on the project subparser.

    Called from api.build_parser(). `leaf` is the helper used to add a
    subparser with shared common args.
    """
    p = leaf(pr_sub, "adopt")
    p.add_argument("slug", help="project id (kebab-case canonical slot)")
    p.add_argument("--prd", default=None,
                   help="PRD .md file (used by knowledge + persona provisioners)")
    p.add_argument("--description", default="",
                   help="project description (when entry doesn't yet exist)")
    p.add_argument("--domain", default="",
                   help="project domain (when entry doesn't yet exist)")
    p.add_argument("--bot", default=None,
                   help="bot strategy: yes|no|auto (required with --non-interactive)")
    p.add_argument("--non-interactive", action="store_true",
                   dest="non_interactive",
                   help="no prompts; default-skip absent (except via flags)")
    p.add_argument("--dry-run", action="store_true", dest="dry_run",
                   help="preview action plan without executing")
    p.add_argument("--skip", default=None,
                   help="comma-separated capabilities to skip "
                        "(e.g. --skip=bot,mission_control)")
    # Detection skip flags (mirror status / migrate-meta).
    p.add_argument("--skip-remote", action="store_true", dest="skip_remote",
                   help="skip gh repo view in code_repo detect")
    p.add_argument("--skip-systemctl", action="store_true", dest="skip_systemctl",
                   help="skip systemctl is-active in bot detect")
    p.add_argument("--skip-knowledge", action="store_true", dest="skip_knowledge",
                   help="skip knowledge_slot detect (no origin/main)")
    p.add_argument("--skip-slot-check", action="store_true",
                   dest="skip_slot_check",
                   help="skip slot_resolve.sh canonical validation (tests)")
    # Bot-specific args (only used when bot provisioner runs).
    p.add_argument("--bot-id", default=None, dest="bot_id",
                   help="bot area name (defaults to slug)")
    p.add_argument("--bot-port", type=int, default=None, dest="bot_port",
                   help="gateway port int (required for bot provisioner)")
    p.add_argument("--bot-token", default=None, dest="bot_token",
                   help="Telegram bot token (required for bot provisioner)")
    p.add_argument("--bot-chat-id", default=None, dest="bot_chat_id",
                   help="Telegram chat id (required for bot provisioner)")
    p.add_argument("--bot-allow-from", default=None, dest="bot_allow_from",
                   help="comma-separated allowed users (required for bot)")
    p.add_argument("--bot-skills", default=None, dest="bot_skills",
                   help="comma-separated skills override")
    p.add_argument("--bootstrap-docs", action="store_true",
                   dest="bootstrap_docs",
                   help="after adopt, run F3 greenfield generator to "
                        "auto-create canonical doc suite (PRD/roadmap/ADRs/"
                        "architecture/release-notes); LLM cost ~$2.50/project")
    p.add_argument("--bootstrap-no-adr", action="store_true",
                   dest="bootstrap_no_adr",
                   help="when --bootstrap-docs, skip Tier JUDGMENT (Sonnet "
                        "ADR proposes); reduces cost to ~$0.30")
    p.set_defaults(func=cmd_project_adopt)
    return p
