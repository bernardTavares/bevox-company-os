"""CLI dispatcher: parses argv, calls sprint/task/store, prints output."""

import argparse
import json
import sys
import time
from typing import Any, Dict, List, Optional

from . import migration
from . import sprint as sprint_lib
from . import store
from . import task as task_lib

EXIT_OK = 0
EXIT_INPUT = 1
EXIT_STATE = 2
EXIT_LOCK = 3
# Aliases used by project create/edit handlers (validation = input,
# runtime = state-level orchestration failure).
EXIT_VALIDATION = EXIT_INPUT
EXIT_RUNTIME = EXIT_STATE
# `project status <slug>` not-found per W3 spec (BSD sysexits EX_USAGE).
EXIT_NOT_FOUND = 64


def _print(payload: Any, json_mode: bool, human: Optional[str] = None) -> None:
    if json_mode:
        # Single-line JSON for machine consumption (MC backend parses stdout).
        print(json.dumps(payload, ensure_ascii=False))
    else:
        if human is not None:
            print(human)
        else:
            print(json.dumps(payload, ensure_ascii=False, indent=2))


def _err(msg: str, code: str, json_mode: bool) -> int:
    if json_mode:
        print(json.dumps({"ok": False, "error": msg, "code": code}))
    else:
        print(f"ERROR ({code}): {msg}", file=sys.stderr)
    if code == "invalid_input":
        return EXIT_INPUT
    if code == "PAYLOAD_INCOMPLETE":
        return EXIT_INPUT
    # Wave-5 blocked_by error codes: all map to EXIT_INPUT (exit 1).
    if code in (
        "CYCLE_DETECTED",
        "PRED_NOT_FOUND",
        "BLOCKED_BY_INVALID",
        "TASK_NOT_FOUND",
        "BLOCKED_BY_UNRESOLVED",
    ):
        return EXIT_INPUT
    if code == "lock_contention":
        return EXIT_LOCK
    return EXIT_STATE


def _format_task_row(t: Dict[str, Any]) -> str:
    badges = []
    if t.get("blocked"):
        reason = (t.get("blocked_reason") or "")[:30]
        badges.append(f"[blocked: {reason}]")
    if t.get("status") == "rejected" and t.get("rejected_reason"):
        badges.append(f"[reason: {t['rejected_reason'][:30]}]")
    if t.get("project"):
        badges.append(f"[{t['project']}]")
    if t.get("epic_id"):
        badges.append(f"[{t['epic_id']}]")
    if t.get("wave_ref"):
        badges.append(f"[{t['wave_ref']}]")
    badge_str = " ".join(badges)
    title = (t.get("title") or "")[:80]
    return f"{t['id']:7s} {t['status']:12s} {title}  {badge_str}"


# Wave-3: alias permanente. Eventos legados com to:"todo" mapeiam para ready
# na projecao. NUNCA reescrever events.jsonl.
TODO_LEGACY_ALIAS = {"todo": "ready"}


def _alias_status(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return TODO_LEGACY_ALIAS.get(value, value)


def _format_sprint(sp: Dict[str, Any], task_count: int = 0, done_count: int = 0) -> str:
    proj = sp.get("project") or "mixed"
    return (
        f"{sp['id']:10s} {sp['state']:8s} project={proj:25s} "
        f"tasks={task_count} done={done_count}  {sp.get('name','')}"
    )


# ============ Sprint handlers ============

def cmd_sprint_init(args: argparse.Namespace) -> int:
    res = sprint_lib.bootstrap(actor=args.actor)
    _print(res, args.json, "ok" if res["ok"] else "fail")
    return EXIT_OK


def cmd_sprint_show(args: argparse.Namespace) -> int:
    state = store.read_state()
    sid = args.id
    # Alias mode (no id, "current", or "next"): list ALL projects' sprints in
    # target state. Post-v4, find_sprint requires project for aliases — iterate
    # instead of raising ValueError.
    if sid in (None, "current", "next"):
        target = sid or "current"
        results = [
            sp for sp in state["sprints"]
            if sp["state"] == target and sp.get("project") is not None
        ]
        if args.json:
            _print({"target": target, "sprints": results}, True)
        else:
            print(f"sprints in state '{target}':")
            for sp in sorted(results, key=lambda s: s.get("project", "")):
                sprint_tasks = [t for t in state["tasks"] if t["sprint_id"] == sp["id"]]
                done = sum(1 for t in sprint_tasks if t["status"] == "done")
                print("  " + _format_sprint(sp, len(sprint_tasks), done))
        return EXIT_OK
    # Literal sprint id — works regardless of project
    sp = sprint_lib.find_sprint(state, sid)
    if sp is None:
        return _err(f"sprint not found: {sid}", "invalid_input", args.json)
    sprint_tasks = [t for t in state["tasks"] if t["sprint_id"] == sp["id"]]
    by_status: Dict[str, int] = {}
    for t in sprint_tasks:
        by_status[t["status"]] = by_status.get(t["status"], 0) + 1
    if args.json:
        _print({"sprint": sp, "tasks": sprint_tasks, "stats_by_status": by_status}, True)
    else:
        print(_format_sprint(sp, len(sprint_tasks), by_status.get("done", 0)))
        for t in sprint_tasks:
            print("  " + _format_task_row(t))
    return EXIT_OK


def cmd_sprint_set_project(args: argparse.Namespace) -> int:
    project = None if args.clear else args.project
    res = sprint_lib.set_project(args.sprint_id, project, actor=args.actor)
    _print(res, args.json, f"ok: {args.sprint_id} project={project}")
    return EXIT_OK


def cmd_sprint_set_name(args: argparse.Namespace) -> int:
    res = sprint_lib.set_name(args.sprint_id, args.name, actor=args.actor)
    _print(res, args.json, f"ok: {args.sprint_id} name={args.name}")
    return EXIT_OK


def cmd_sprint_set_session_id(args: argparse.Namespace) -> int:
    try:
        result = sprint_lib.set_session_id(
            sprint_id=args.sprint_id,
            session_id=args.session_id,
            actor=args.actor,
        )
    except ValueError as e:
        return _err(str(e), "SET_SESSION_FAILED", args.json)
    if args.json:
        print(json.dumps(result, default=str, indent=2))
    else:
        if result.get("noop"):
            print(f"noop: sprint {args.sprint_id} already has session_id={result['existing']}")
        else:
            print(f"set: sprint {args.sprint_id} session_id={result['session_id']}")
    return EXIT_OK


def cmd_sprint_clear_session_id(args: argparse.Namespace) -> int:
    try:
        result = sprint_lib.clear_session_id(
            sprint_id=args.sprint_id,
            actor=args.actor,
            reason=args.reason,
        )
    except ValueError as e:
        return _err(str(e), "CLEAR_SESSION_FAILED", args.json)
    if args.json:
        print(json.dumps(result, default=str, indent=2))
    else:
        if result.get("noop"):
            print(f"noop: sprint {args.sprint_id} has no session_id")
        else:
            print(f"cleared: sprint {args.sprint_id} previous_session_id={result['cleared']}")
    return EXIT_OK


def cmd_sprint_close(args: argparse.Namespace) -> int:
    state = store.read_state()
    pending = sprint_lib.list_pending_in_current(state, project=args.project)
    if args.carryover_json is not None:
        try:
            carryover = json.loads(args.carryover_json)
        except json.JSONDecodeError as e:
            return _err(f"invalid --carryover JSON: {e}", "invalid_input", args.json)
        if not isinstance(carryover, list):
            return _err("--carryover must be a JSON array", "invalid_input", args.json)
    elif args.non_interactive:
        carryover = [{"task_id": t["id"], "action": "move_current"} for t in pending]
    else:
        carryover = _interactive_carryover(pending)
        if carryover is None:
            print("aborted")
            return EXIT_INPUT
    res = sprint_lib.close_current(carryover, actor=args.actor, project=args.project)
    _print(
        res, args.json,
        f"closed {res['closed']}, current={res['promoted_to_current']}, next={res['new_next']}",
    )
    return EXIT_OK


def _interactive_carryover(pending: List[Dict[str, Any]]) -> Optional[List[Dict[str, str]]]:
    out: List[Dict[str, str]] = []
    print(f"\nFechar sprint atual com {len(pending)} task(s) pendente(s).\n")
    for t in pending:
        proj = t.get("project") or "-"
        prompt = (
            f"{t['id']} [{t['status']}] \"{t['title'][:60]}\" (project: {proj})\n"
            f"  (1) move pro novo current  (2) move pro novo next  "
            f"(3) archive  (a) abort\n  > "
        )
        while True:
            ans = input(prompt).strip().lower()
            if ans == "a":
                return None
            mapping = {"1": "move_current", "2": "move_next", "3": "archive"}
            if ans in mapping:
                out.append({"task_id": t["id"], "action": mapping[ans]})
                break
            print("  invalid; try 1/2/3/a")
    return out


def cmd_sprint_history(args: argparse.Namespace) -> int:
    state = store.read_state()
    items = sprint_lib.history(state)
    if args.json:
        _print({"closed_sprints": items}, True)
    else:
        for sp in items:
            count = len([t for t in state["tasks"] if t["sprint_id"] == sp["id"]])
            done = len([
                t for t in state["tasks"]
                if t["sprint_id"] == sp["id"] and t["status"] == "done"
            ])
            print(_format_sprint(sp, count, done))
    return EXIT_OK


def cmd_sprint_bootstrap(args: argparse.Namespace) -> int:
    projects = [args.project] if args.project else None
    try:
        result = sprint_lib.bootstrap(
            actor=args.actor, projects=projects, dry_run=args.dry_run)
    except Exception as e:
        return _err(str(e), "BOOTSTRAP_FAILED", args.json)
    if args.json:
        print(json.dumps(result, default=str, indent=2))
    else:
        if args.dry_run:
            print(f"DRY RUN — would create {len(result['would_create'])} sprints:")
            for proj, st in result['would_create']:
                print(f"  {proj}: {st}")
        else:
            created = result.get("created", [])
            print(f"created {len(created)} sprints:")
            for sp in created:
                print(f"  {sp['id']} ({sp['state']}) project={sp['project']}")
    return EXIT_OK


def cmd_sprint_migrate_to_per_project(args: argparse.Namespace) -> int:
    try:
        result = migration.migrate_to_per_project(
            actor=args.actor, dry_run=args.dry_run)
    except ValueError as e:
        return _err(str(e), "MIGRATION_FAILED", args.json)
    if args.json:
        print(json.dumps(result, default=str, indent=2))
    else:
        if result.get("noop"):
            print(f"noop: {result.get('reason', '?')}")
        elif result.get("dry_run"):
            print(f"DRY RUN — would migrate to schema v4:")
            print(f"  resprint {len(result.get('would_resprint', []))} tasks")
            print(f"  close orphan sprint {result.get('would_close', '?')}")
        else:
            print(f"migrated to schema v4:")
            print(f"  resprinted {result['resprinted_count']} tasks")
            print(f"  closed orphan {result['closed_orphan']}")
            print(f"  backup at {result['backup_path']}")
    return EXIT_OK


# ============ Task handlers ============

def cmd_task_add(args: argparse.Namespace) -> int:
    # Parse --payload JSON (wave-4 gate: obrigatorio na criacao)
    try:
        payload = json.loads(args.payload)
    except json.JSONDecodeError as e:
        return _err(
            f"invalid JSON payload: {e}", "invalid_input", args.json,
        )
    if not isinstance(payload, dict):
        return _err(
            "payload must be a JSON object", "invalid_input", args.json,
        )

    # Gate: valida completeness antes de criar (policy wave-0 §3)
    from . import payload_gate
    try:
        payload_gate.enforce_payload_gate(payload)
    except payload_gate.PayloadIncompleteError as e:
        # Emit audit event ANTES de retornar erro (truth record).
        # Usa mutate_state pra manter state.last_event_seq sincronizado
        # com events.jsonl (senao cmd_status flagga drift).
        with store.mutate_state() as state:
            seq = store.next_seq(state)
            store.append_event({
                "seq": seq,
                "ts": store.now_iso(),
                "type": "task_creation_rejected_payload_incomplete",
                "actor": args.actor or "unknown",
                "attempted_title": args.title,
                "attempted_project": args.project,
                "missing_fields": e.missing,
                "source": "cli",
            })
            state["last_event_seq"] = seq
        return _err(
            f"missing fields: {e.missing}",
            "PAYLOAD_INCOMPLETE", args.json,
        )

    # Happy path: payload valido -> forward pra task_lib.create
    res = task_lib.create(
        title=args.title, sprint=args.sprint, project=args.project,
        epic_id=args.epic, wave_ref=args.wave, description=args.description,
        payload=payload, actor=args.actor,
    )
    _print(res, args.json, f"created: {res['task']['id']}")
    return EXIT_OK


def cmd_task_show(args: argparse.Namespace) -> int:
    state = store.read_state()
    t = task_lib.find_task(state, args.task_id)
    if t is None:
        return _err(f"task not found: {args.task_id}", "invalid_input", args.json)
    if args.json:
        _print({"task": t}, True)
    else:
        print(_format_task_row(t))
        if t.get("description"):
            print("  description:", t["description"])
        print(
            f"  sprint={t['sprint_id']}  created_by={t['created_by']}  "
            f"created_at={t['created_at']}  updated_at={t['updated_at']}"
        )
    return EXIT_OK


def cmd_task_update(args: argparse.Namespace) -> int:
    fields: Dict[str, Any] = {}
    if args.title is not None:
        fields["title"] = args.title
    if args.description is not None:
        fields["description"] = args.description
    if args.project is not None:
        fields["project"] = args.project
    if args.clear_project:
        fields["clear_project"] = True
    if args.epic is not None:
        fields["epic_id"] = args.epic
    if args.wave is not None:
        fields["wave_ref"] = args.wave
    res = task_lib.update(args.task_id, actor=args.actor, **fields)
    _print(
        res, args.json,
        f"updated: {res['task']['id']}{' (noop)' if res.get('noop') else ''}",
    )
    return EXIT_OK


def cmd_task_move(args: argparse.Namespace) -> int:
    try:
        res = task_lib.move_status(
            args.task_id, args.status, actor=args.actor,
            force=getattr(args, "force", False),
            reason=getattr(args, "reason", None),
        )
    except task_lib.TaskError as e:
        return _err(str(e), e.code, args.json)
    _print(res, args.json, f"moved: {res['task']['id']} -> {res['task']['status']}")
    return EXIT_OK


def cmd_task_block(args: argparse.Namespace) -> int:
    res = task_lib.block(args.task_id, args.reason, actor=args.actor)
    _print(res, args.json, f"blocked: {res['task']['id']} ({args.reason})")
    return EXIT_OK


def cmd_task_unblock(args: argparse.Namespace) -> int:
    res = task_lib.unblock(args.task_id, actor=args.actor)
    _print(res, args.json, f"unblocked: {res['task']['id']}")
    return EXIT_OK


def cmd_task_reopen(args: argparse.Namespace) -> int:
    res = task_lib.reopen(args.task_id, args.to, args.reason, actor=args.actor)
    _print(
        res, args.json,
        f"reopened: {res['task']['id']} -> {res['task']['status']} ({args.reason})",
    )
    return EXIT_OK


def cmd_task_set_dispatch_payload(args: argparse.Namespace) -> int:
    try:
        payload = json.loads(args.payload)
    except json.JSONDecodeError as e:
        return _err(
            f"invalid JSON payload: {e}", "invalid_input", args.json,
        )
    res = task_lib.set_dispatch_payload(
        args.task_id, payload, merge=args.merge, actor=args.actor,
    )
    _print(
        res, args.json,
        f"dispatch_payload {'merged' if args.merge else 'set'}: {res['task']['id']}",
    )
    return EXIT_OK


def cmd_task_set_blocked_by(args: argparse.Namespace) -> int:
    """Seta dispatch_payload.blocked_by com validacao + cycle gate (wave-5).

    --preds "T-A,T-B" (CSV, substitui), --add "T-C" (append idempotente),
    --remove "T-D" (delete idempotente). Mutuamente exclusivos (argparse mutex).
    """
    # Fetch current preds to compute final list for --add / --remove
    current = task_lib.find_task(store.read_state(), args.task_id)
    if current is None:
        return _err(
            f"task not found: {args.task_id}",
            "TASK_NOT_FOUND", args.json,
        )

    existing_preds = list(
        (current.get("dispatch_payload") or {}).get("blocked_by") or []
    )

    if args.preds is not None:
        new_preds = [p.strip() for p in args.preds.split(",") if p.strip()]
    elif args.add is not None:
        new_preds = list(existing_preds)
        if args.add not in new_preds:
            new_preds.append(args.add)
    elif args.remove is not None:
        new_preds = [p for p in existing_preds if p != args.remove]
    else:
        # Defensive: argparse mutex(required=True) garante que nao chega aqui.
        return _err(
            "exatamente um de --preds/--add/--remove obrigatorio",
            "invalid_input", args.json,
        )

    try:
        res = task_lib.set_blocked_by(
            args.task_id, new_preds, actor=args.actor,
        )
    except task_lib.TaskError as e:
        return _err(str(e), e.code, args.json)

    _print(
        res, args.json,
        f"blocked_by set: {args.task_id} -> {new_preds}",
    )
    return EXIT_OK


def cmd_task_resprint(args: argparse.Namespace) -> int:
    res = task_lib.move_sprint(args.task_id, args.sprint, actor=args.actor)
    _print(
        res, args.json,
        f"resprinted: {res['task']['id']} -> {res['task']['sprint_id']}",
    )
    return EXIT_OK


def cmd_task_archive(args: argparse.Namespace) -> int:
    res = task_lib.archive(args.task_id, actor=args.actor)
    _print(res, args.json, f"archived: {res['task']['id']}")
    return EXIT_OK


def cmd_task_unarchive(args: argparse.Namespace) -> int:
    res = task_lib.unarchive(args.task_id, status=args.status, actor=args.actor)
    _print(
        res, args.json,
        f"unarchived: {res['task']['id']} -> {res['task']['status']}",
    )
    return EXIT_OK


def cmd_task_list(args: argparse.Namespace) -> int:
    blocked_filter = True if getattr(args, "blocked_only", False) else None
    items = task_lib.list_tasks(
        sprint=args.sprint, status=args.status, project=args.project,
        epic_id=args.epic, archived=args.archived, blocked=blocked_filter,
    )
    if args.json:
        _print({"tasks": items}, True)
    else:
        for t in items:
            print(_format_task_row(t))
    return EXIT_OK


# ============ Project handlers ============

def cmd_project_list(args: argparse.Namespace) -> int:
    state = store.read_state()
    if args.json:
        _print({"projects": state["projects"]}, True)
    else:
        for p in state["projects"]:
            print(p)
    return EXIT_OK


def cmd_project_add(args: argparse.Namespace) -> int:
    res = task_lib.add_project(args.name, actor=args.actor)
    _print(
        res, args.json,
        f"added: {res['name']}{' (noop)' if res.get('noop') else ''}",
    )
    return EXIT_OK


def cmd_project_create(args: argparse.Namespace) -> int:
    """Orchestrator: create project across 7 destinations (with persona LLM)."""
    from pathlib import Path
    import os
    from lib.project_factory import (
        create_project, slugify, ProjectCreateConfig,
    )
    slug = args.id or slugify(args.name)
    if not slug:
        _print({"error": "invalid_name"}, args.json,
               f"erro: nome inválido (id derivado vazio)")
        return EXIT_VALIDATION

    kb_dir = Path(os.environ.get(
        "BEVOX_KNOWLEDGE_DIR", f"{Path.home()}/bevox-knowledge"))
    openclaw_dir = Path(os.environ.get(
        "OPENCLAW_DIR", f"{Path.home()}/.openclaw"))
    code_dir = Path(os.environ.get(
        "BEVOX_CODE_DIR", f"{Path.home()}/code"))
    org = os.environ.get("GITHUB_ORG", "bernardTavares")
    templates_dir = openclaw_dir / "kanban-tasks" / "templates"

    prd_file = Path(args.prd) if args.prd else None
    if prd_file is not None and not prd_file.is_file():
        _print({"error": "prd_file_missing", "path": str(prd_file)},
               args.json, f"erro: --prd file não encontrado: {prd_file}")
        return EXIT_VALIDATION

    config = ProjectCreateConfig(
        kb_dir=kb_dir,
        openclaw_dir=openclaw_dir,
        code_dir=code_dir,
        meta_path=openclaw_dir / "projects-meta.json",
        log_path=openclaw_dir / "projects-create.jsonl",
        templates_dir=templates_dir,
        org=org,
        prd_file=prd_file,
        domain=args.domain or "",
    )

    result = create_project(
        name=args.name,
        slug=slug,
        description=args.description or "",
        config=config,
        actor=args.actor,
    )
    _print(result, args.json,
           f"{'ok' if result['success'] else 'failed'}: {slug}")
    return EXIT_OK if result["success"] else EXIT_RUNTIME


def cmd_project_edit(args: argparse.Namespace) -> int:
    """Light-weight: update projects-meta.json fields only (no orchestration)."""
    from pathlib import Path
    import os
    from lib import projects_meta
    openclaw_dir = Path(os.environ.get(
        "OPENCLAW_DIR", f"{Path.home()}/.openclaw"))
    meta_path = openclaw_dir / "projects-meta.json"

    partial = {}
    if args.bot_id is not None:
        partial["bot_id"] = args.bot_id if args.bot_id else None
    if args.bot_username is not None:
        partial["bot_username"] = args.bot_username if args.bot_username else None
    if args.bot_port is not None:
        if args.bot_port == "":
            partial["bot_port"] = None
        else:
            try:
                partial["bot_port"] = int(args.bot_port)
            except ValueError:
                _print({"error": "invalid_bot_port", "detail": args.bot_port},
                       args.json, f"erro: --bot-port não é int: {args.bot_port}")
                return EXIT_VALIDATION
    if args.github_url is not None:
        partial["github_url"] = args.github_url if args.github_url else None
    if args.description is not None:
        partial["description"] = args.description

    if not partial:
        _print({"error": "no_fields"}, args.json,
               "erro: pelo menos um field (--bot-id/--bot-username/--bot-port/--github-url/--description)")
        return EXIT_VALIDATION

    try:
        projects_meta.update_project(meta_path, args.id, partial)
        _print({"id": args.id, "updated": list(partial.keys())},
               args.json, f"updated: {args.id}")
        return EXIT_OK
    except projects_meta.MetaError as e:
        _print({"error": "meta_error", "detail": str(e)},
               args.json, f"erro: {e}")
        return EXIT_VALIDATION


def cmd_project_remove(args: argparse.Namespace) -> int:
    """Orchestrator: remove project across 6 destinations (reverse-of-create)."""
    from pathlib import Path
    import os
    from lib.project_factory import remove_project, ProjectRemoveConfig

    kb_dir = Path(os.environ.get(
        "BEVOX_KNOWLEDGE_DIR", f"{Path.home()}/bevox-knowledge"))
    openclaw_dir = Path(os.environ.get(
        "OPENCLAW_DIR", f"{Path.home()}/.openclaw"))
    code_dir = Path(os.environ.get(
        "BEVOX_CODE_DIR", f"{Path.home()}/code"))
    org = os.environ.get("GITHUB_ORG", "bernardTavares")

    config = ProjectRemoveConfig(
        kb_dir=kb_dir,
        openclaw_dir=openclaw_dir,
        code_dir=code_dir,
        meta_path=openclaw_dir / "projects-meta.json",
        log_path=openclaw_dir / "projects-delete.jsonl",
        org=org,
    )

    result = remove_project(
        slug=args.id,
        config=config,
        actor=args.actor,
        skip_github=args.skip_github,
    )
    _print(result, args.json,
           f"{'ok' if result['success'] else 'failed'}: {args.id}")
    if not result["success"]:
        if result.get("failed_at") == 0:
            return EXIT_VALIDATION
        return EXIT_RUNTIME
    return EXIT_OK


def cmd_project_status(args: argparse.Namespace) -> int:
    """Read-only capability matrix per project (declared vs detected).

    W3 spec: bevox-knowledge/35_specs/openclaw/2026-05-07-project-lifecycle-w3-v1.md
    ADR-013 §Drift detection contract for --json shape.

    Modes:
    - `project status <slug>` → vertical single-project table.
    - `project status` (no slug) → horizontal dispatcher matrix (all projects).
    """
    from pathlib import Path
    import datetime as _dt
    import os
    from lib import projects_meta as _pm
    from lib import render_status as _rs
    from lib.capability_detect import DetectPaths, detect_all

    openclaw_dir = Path(os.environ.get(
        "OPENCLAW_DIR", f"{Path.home()}/.openclaw"))
    kb_dir = Path(os.environ.get(
        "BEVOX_KNOWLEDGE_DIR", f"{Path.home()}/bevox-knowledge"))
    code_dir = Path(os.environ.get(
        "BEVOX_CODE_DIR", f"{Path.home()}/code"))
    org = os.environ.get("GITHUB_ORG", "bernardTavares")
    meta_path = openclaw_dir / "projects-meta.json"

    try:
        meta = _pm.read_meta(meta_path)
    except _pm.MetaError as e:
        _print({"error": "meta_read_failed", "detail": str(e)},
               args.json, f"erro: {e}")
        return EXIT_RUNTIME

    projects = meta.get("projects") or {}
    target_slug = getattr(args, "slug", None)
    no_detect = getattr(args, "no_detect", False)

    if target_slug is not None and target_slug not in projects:
        _print(
            {"error": "project_not_found", "slug": target_slug},
            args.json,
            f"error: project '{target_slug}' not found in projects-meta.json",
        )
        return EXIT_NOT_FOUND

    paths = DetectPaths(
        kb_dir=kb_dir, openclaw_dir=openclaw_dir,
        code_dir=code_dir, org=org,
    )

    target_slugs = [target_slug] if target_slug else sorted(projects.keys())
    diffs_by_slug: dict = {}
    metas_by_slug: dict = {}

    for slug in target_slugs:
        entry = projects[slug]
        declared_caps = entry.get("capabilities") or {}
        if no_detect:
            detected_caps = None
        else:
            detected_caps = detect_all(
                slug, paths, meta_entry=entry,
                skip_remote=getattr(args, "skip_remote", False),
                skip_systemctl=getattr(args, "skip_systemctl", False),
                skip_knowledge=getattr(args, "skip_knowledge", False),
            )
        diff = _rs.compute_diff(declared_caps, detected_caps)
        diffs_by_slug[slug] = diff
        metas_by_slug[slug] = entry

    if args.json:
        generated_at = _dt.datetime.now(_dt.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        payload = _rs.build_json_payload(
            generated_at,
            {s: (metas_by_slug[s], diffs_by_slug[s]) for s in target_slugs},
            detect_skipped=no_detect,
        )
        _print(payload, json_mode=True)
        return EXIT_OK

    # Human rendering.
    if target_slug:
        text = _rs.render_single_project(
            target_slug, metas_by_slug[target_slug],
            diffs_by_slug[target_slug], detect_skipped=no_detect,
        )
    else:
        text = _rs.render_dispatcher_table(diffs_by_slug)
    print(text)
    return EXIT_OK


def cmd_project_migrate_meta(args: argparse.Namespace) -> int:
    """Migrate projects-meta.json from flat schema to capabilities sub-object.

    Idempotent. Backup at projects-meta.legacy.json (1x).
    Use --dry-run to preview without writing.

    Spec: bevox-knowledge/35_specs/openclaw/2026-05-07-project-lifecycle-w1-v1.md
    ADR: bevox-knowledge/30_adr/openclaw/ADR-013-project-capability-state-machine.md
    """
    from pathlib import Path
    import os
    from lib.capability_detect import DetectPaths
    from lib.migration_capabilities import migrate_meta

    openclaw_dir = Path(os.environ.get(
        "OPENCLAW_DIR", f"{Path.home()}/.openclaw"))
    kb_dir = Path(os.environ.get(
        "BEVOX_KNOWLEDGE_DIR", f"{Path.home()}/bevox-knowledge"))
    code_dir = Path(os.environ.get(
        "BEVOX_CODE_DIR", f"{Path.home()}/code"))
    org = os.environ.get("GITHUB_ORG", "bernardTavares")
    meta_path = openclaw_dir / "projects-meta.json"

    if not meta_path.exists():
        _print({"error": "meta_missing", "path": str(meta_path)},
               args.json, f"erro: meta não encontrado em {meta_path}")
        return EXIT_VALIDATION

    paths = DetectPaths(
        kb_dir=kb_dir, openclaw_dir=openclaw_dir,
        code_dir=code_dir, org=org,
    )
    result = migrate_meta(
        meta_path,
        dry_run=args.dry_run,
        paths=paths,
        skip_remote=args.skip_remote,
        skip_systemctl=args.skip_systemctl,
        skip_knowledge=args.skip_knowledge,
    )

    if args.json:
        _print(result, json_mode=True)
        return EXIT_OK

    n_migrated = len(result["migrated"])
    n_skipped = len(result["skipped"])
    if args.dry_run:
        msg = f"dry-run: {n_migrated} entries migrariam, {n_skipped} já migradas"
    elif n_migrated == 0:
        msg = f"nada a migrar — {n_skipped} entries já migradas"
    else:
        msg = (
            f"migrou {n_migrated} entries; backup em {result['backup_path']}"
        )
    _print({"summary": msg, **result}, json_mode=False, human=msg)
    return EXIT_OK


def cmd_project_regenerate_persona(args: argparse.Namespace) -> int:
    """Re-run step_4_persona_llm for an existing project (executes step_4 only)."""
    from pathlib import Path
    import os
    import datetime as dt
    from lib.project_factory import step_4_persona_llm

    openclaw_dir = Path(os.environ.get(
        "OPENCLAW_DIR", f"{Path.home()}/.openclaw"))
    kb_dir = Path(os.environ.get(
        "BEVOX_KNOWLEDGE_DIR", f"{Path.home()}/bevox-knowledge"))

    workspace = openclaw_dir / f"workspace-{args.id}"
    if not workspace.is_dir():
        _print({"error": "workspace_missing", "id": args.id},
               args.json, f"erro: workspace-{args.id} não existe")
        return EXIT_VALIDATION

    # Locate PRD (newest matching file)
    prd_dir = kb_dir / "10_prd" / args.id
    prd_files = sorted(prd_dir.glob(f"*-{args.id}-prd.md")) \
        if prd_dir.is_dir() else []
    if not prd_files:
        _print({"error": "prd_missing", "id": args.id, "looked_in": str(prd_dir)},
               args.json, f"erro: PRD não encontrado em {prd_dir}")
        return EXIT_VALIDATION
    prd_text = prd_files[-1].read_text(encoding="utf-8")

    # Force regeneration: strip persona_status: generated marker so step_4 runs
    identity = workspace / "IDENTITY.md"
    if args.force and identity.exists():
        text = identity.read_text(encoding="utf-8")
        text = text.replace(
            "persona_status: generated", "persona_status: pending"
        )
        identity.write_text(text, encoding="utf-8")

    result = step_4_persona_llm(
        slug=args.id,
        name=args.name or args.id,
        domain=args.domain or "",
        date_str=dt.date.today().isoformat(),
        prd_text=prd_text,
        workspace_dir=workspace,
    )
    _print(result, args.json,
           f"persona: {result['persona_status']}")
    return EXIT_OK if result["persona_status"] == "generated" else EXIT_RUNTIME


# ============ Events handlers ============

def cmd_events_tail(args: argparse.Namespace) -> int:
    items = store.iter_events(
        n=args.n, since=args.since, actor=args.actor_filter,
        type_=args.type, task_id=args.task, sprint_id=args.sprint,
    )
    if args.json:
        _print({"events": items}, True)
    else:
        for ev in items:
            rest = {k: v for k, v in ev.items() if k not in ("seq", "ts", "actor", "type")}
            print(
                f"{ev.get('seq'):5d} {ev.get('ts')} "
                f"{ev.get('actor', '?'):8s} {ev.get('type'):22s} "
                f"{json.dumps(rest, ensure_ascii=False)}"
            )
    return EXIT_OK


def cmd_events_show(args: argparse.Namespace) -> int:
    ev = store.read_event_by_seq(args.seq)
    if ev is None:
        return _err(f"event not found: seq={args.seq}", "invalid_input", args.json)
    _print({"event": ev}, args.json)
    return EXIT_OK


# ============ Maintenance ============

def cmd_rebuild(args: argparse.Namespace) -> int:
    """Reconstruct state.json from events.jsonl."""
    with store.acquire_lock():
        events = store.iter_events()
        state = store._empty_state()
        state["projects"] = store.read_projects()
        for ev in events:
            _apply_event(state, ev)
        state["last_event_seq"] = events[-1]["seq"] if events else 0
        # Wave-3: backfill defaults pra tasks pre-schema_version=2
        for tk in state["tasks"]:
            tk.setdefault("blocked", False)
            tk.setdefault("blocked_reason", None)
            tk.setdefault("blocked_at", None)
            tk.setdefault("rejected_reason", None)
            tk.setdefault("dispatch_payload", None)
            tk.setdefault("test_result", None)
        # Wave-5: schema v3 migration: schema_version bump + populate blocked_by default
        state["schema_version"] = 3
        for t in state.get("tasks", []):
            dp = t.get("dispatch_payload")
            if dp is None:
                t["dispatch_payload"] = {"blocked_by": []}
            elif isinstance(dp, dict):
                if dp.get("blocked_by") is None:
                    dp["blocked_by"] = []
        store.write_state_atomic(state)
    _print(
        {"ok": True, "events_replayed": len(events)}, args.json,
        f"rebuild ok: {len(events)} events replayed",
    )
    return EXIT_OK


def _apply_event(state: Dict[str, Any], ev: Dict[str, Any]) -> None:
    t = ev.get("type")
    actor = ev.get("actor", "unknown")
    ts = ev.get("ts", store.now_iso())
    if t == "sprint_created":
        state["sprints"].append({
            "id": ev["sprint_id"], "name": ev.get("name") or ev["sprint_id"],
            "state": ev["state"], "project": ev.get("project"),
            "created_at": ts, "closed_at": None, "created_by": actor,
        })
    elif t == "sprint_project_set":
        for sp in state["sprints"]:
            if sp["id"] == ev["sprint_id"]:
                sp["project"] = ev.get("project")
    elif t == "sprint_name_set":
        for sp in state["sprints"]:
            if sp["id"] == ev["sprint_id"]:
                sp["name"] = ev.get("name") or sp["name"]
    elif t == "sprint_closed":
        for sp in state["sprints"]:
            if sp["id"] == ev["sprint_id"]:
                sp["state"] = "closed"
                sp["closed_at"] = ts
    elif t == "sprint_promoted":
        for sp in state["sprints"]:
            if sp["id"] == ev["from_id"]:
                sp["state"] = ev["to_state"]
    elif t == "task_created":
        state["tasks"].append({
            "id": ev["task_id"], "title": ev["title"], "description": "",
            "status": "backlog", "sprint_id": ev["sprint_id"],
            "project": ev.get("project"), "epic_id": ev.get("epic_id"),
            "wave_ref": ev.get("wave_ref"),
            "created_at": ts, "updated_at": ts, "created_by": actor,
            "archived_at": None,
            # Wave-3 defaults:
            "blocked": False, "blocked_reason": None, "blocked_at": None,
            "rejected_reason": None,
            "dispatch_payload": None, "test_result": None,
        })
    elif t == "task_updated":
        for tk in state["tasks"]:
            if tk["id"] == ev["task_id"]:
                for f, v in ev.get("fields_changed", {}).items():
                    tk[f] = v
                tk["updated_at"] = ts
    elif t == "task_moved":
        for tk in state["tasks"]:
            if tk["id"] == ev["task_id"]:
                tk["status"] = _alias_status(ev["to"])
                tk["updated_at"] = ts
                # Wave-3: popula rejected_reason se evento carrega reason
                if ev.get("to") == "rejected" and ev.get("reason"):
                    tk["rejected_reason"] = ev["reason"]
    elif t == "task_resprinted":
        for tk in state["tasks"]:
            if tk["id"] == ev["task_id"]:
                tk["sprint_id"] = ev["to_sprint_id"]
                tk["updated_at"] = ts
    elif t == "task_archived":
        for tk in state["tasks"]:
            if tk["id"] == ev["task_id"]:
                tk["status"] = "archived"
                tk["archived_at"] = ts
                tk["updated_at"] = ts
    elif t == "task_unarchived":
        for tk in state["tasks"]:
            if tk["id"] == ev["task_id"]:
                tk["status"] = _alias_status(ev.get("restored_to", "backlog"))
                tk["archived_at"] = None
                tk["updated_at"] = ts
    elif t == "task_blocked":
        for tk in state["tasks"]:
            if tk["id"] == ev["task_id"]:
                tk["blocked"] = True
                tk["blocked_reason"] = ev.get("reason")
                tk["blocked_at"] = ts
                tk["updated_at"] = ts
    elif t == "task_unblocked":
        for tk in state["tasks"]:
            if tk["id"] == ev["task_id"]:
                tk["blocked"] = False
                tk["blocked_reason"] = None
                tk["blocked_at"] = None
                tk["updated_at"] = ts
    elif t == "task_reopened":
        for tk in state["tasks"]:
            if tk["id"] == ev["task_id"]:
                tk["status"] = _alias_status(ev["to"])
                if ev.get("from") == "rejected":
                    tk["rejected_reason"] = None
                tk["updated_at"] = ts
    elif t == "task_dispatch_payload_set":
        # Evento carrega payload material + merge flag. Rebuild puro
        # reconstroi dispatch_payload aplicando replace ou shallow merge
        # top-level. Chave por chave; arrays/scalars substituem por
        # inteiro (sem deep merge).
        payload = ev.get("payload") or {}
        merge = bool(ev.get("merge", False))
        for tk in state["tasks"]:
            if tk["id"] == ev["task_id"]:
                existing = tk.get("dispatch_payload") or {}
                if merge:
                    tk["dispatch_payload"] = {**existing, **payload}
                else:
                    tk["dispatch_payload"] = payload
                tk["updated_at"] = ts
    elif t in ("task_entered_testing", "task_rejected_with_reason"):
        # Satellites: sem efeito de projecao (informativos pra agentes/audit).
        pass
    elif t == "project_added":
        if ev["project_name"] not in state["projects"]:
            state["projects"].append(ev["project_name"])


def cmd_status(args: argparse.Namespace) -> int:
    state = store.read_state()
    issues: List[str] = []
    # Post-v4: validate per-project (>1 current per project = corruption).
    # Legacy orphan sprints (project=None) are excluded from per-project checks.
    currents_per_proj: Dict[str, int] = {}
    nexts_per_proj: Dict[str, int] = {}
    for sp in state.get("sprints", []):
        if sp.get("project") is None:
            continue
        if sp["state"] == "current":
            currents_per_proj[sp["project"]] = currents_per_proj.get(sp["project"], 0) + 1
        elif sp["state"] == "next":
            nexts_per_proj[sp["project"]] = nexts_per_proj.get(sp["project"], 0) + 1
    projects_with_multiple_currents = sorted(
        p for p, c in currents_per_proj.items() if c > 1
    )
    if projects_with_multiple_currents:
        issues.append(f"projects with multiple currents: {projects_with_multiple_currents}")
    projects_with_multiple_nexts = sorted(
        p for p, c in nexts_per_proj.items() if c > 1
    )
    if projects_with_multiple_nexts:
        issues.append(f"projects with multiple nexts: {projects_with_multiple_nexts}")
    # Flag registered projects without a current sprint (post-v4 only)
    if state.get("schema_version") == 4:
        projects_yml = state.get("projects", [])
        projects_without_current = [p for p in projects_yml if p not in currents_per_proj]
        if projects_without_current:
            issues.append(f"projects without current sprint: {projects_without_current}")
    last_event = store.iter_events(n=1)
    if last_event:
        if state.get("last_event_seq") != last_event[0].get("seq"):
            issues.append(
                f"last_event_seq mismatch: state={state.get('last_event_seq')} "
                f"vs file={last_event[0].get('seq')}"
            )
    yml_projects = set(store.read_projects())
    state_projects = set(state.get("projects", []))
    if yml_projects and yml_projects != state_projects:
        issues.append(
            f"projects.yml diff state.json: "
            f"yml-only={sorted(yml_projects - state_projects)} "
            f"state-only={sorted(state_projects - yml_projects)}"
        )
    lock_age: Optional[float] = None
    if store.LOCK_PATH.exists():
        lock_age = round(time.time() - store.LOCK_PATH.stat().st_mtime, 1)
        if lock_age > store.LOCK_STALE_TTL_SEC:
            issues.append(f"lock stale (age={lock_age}s > {store.LOCK_STALE_TTL_SEC}s)")
    payload = {
        "ok": not issues, "issues": issues, "lock_age_sec": lock_age,
        "sprints": len(state["sprints"]), "tasks": len(state["tasks"]),
        "events": state.get("last_event_seq", 0),
    }
    _print(
        payload, args.json,
        ("ok" if not issues else "ISSUES:\n  " + "\n  ".join(issues)),
    )
    return EXIT_OK if not issues else EXIT_STATE


# ============ Parser ============

def build_parser() -> argparse.ArgumentParser:
    # Parent with common flags so they work after the subcommand too
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="JSON output")
    common.add_argument("--actor", default="bernard", help="actor identity")

    # Top-level parser does NOT include common flags; we pass them on each
    # leaf subparser via parents=[common]. If common flags were on the top
    # parser AND via parents on the leaf, the leaf's default would overwrite
    # the top-level value at parse time (argparse pitfall).
    p = argparse.ArgumentParser(prog="kanban-tasks")
    sub = p.add_subparsers(dest="cmd", required=True)

    def leaf(parser_sub, name: str) -> argparse.ArgumentParser:
        return parser_sub.add_parser(name, parents=[common])

    # sprint
    sp_p = sub.add_parser("sprint")
    sp_sub = sp_p.add_subparsers(dest="sub", required=True)
    leaf(sp_sub, "init").set_defaults(func=cmd_sprint_init)
    show = leaf(sp_sub, "show")
    show.add_argument("--id")
    show.set_defaults(func=cmd_sprint_show)
    setp = leaf(sp_sub, "set-project")
    setp.add_argument("sprint_id")
    g = setp.add_mutually_exclusive_group(required=True)
    g.add_argument("project", nargs="?")
    g.add_argument("--clear", action="store_true")
    setp.set_defaults(func=cmd_sprint_set_project)
    setn = leaf(sp_sub, "set-name")
    setn.add_argument("sprint_id")
    setn.add_argument("name")
    setn.set_defaults(func=cmd_sprint_set_name)
    setsid = leaf(sp_sub, "set-session-id")
    setsid.add_argument("--sprint-id", required=True, help="Sprint id (literal sprint-N)")
    setsid.add_argument("--session-id", required=True, help="UUID da Claude session")
    setsid.set_defaults(func=cmd_sprint_set_session_id)
    clearsid = leaf(sp_sub, "clear-session-id")
    clearsid.add_argument("--sprint-id", required=True, help="Sprint id (literal sprint-N)")
    clearsid.add_argument("--reason", default="", help="Reason for clearing (optional)")
    clearsid.set_defaults(func=cmd_sprint_clear_session_id)
    close = leaf(sp_sub, "close-current")
    close.add_argument("--project", required=True,
        help="Projeto cujo sprint fechar")
    close.add_argument("--non-interactive", action="store_true")
    close.add_argument(
        "--carryover",
        dest="carryover_json",
        default=None,
        help='JSON array: [{"task_id":"T-N","action":"move_current|move_next|archive"}, ...]',
    )
    close.set_defaults(func=cmd_sprint_close)
    leaf(sp_sub, "history").set_defaults(func=cmd_sprint_history)
    boot = leaf(sp_sub, "bootstrap")
    boot.add_argument("--project", default=None,
        help="Override: bootstrap só pra um projeto específico")
    boot.add_argument("--dry-run", action="store_true")
    boot.set_defaults(func=cmd_sprint_bootstrap)
    mig = leaf(sp_sub, "migrate-to-per-project")
    mig.add_argument("--dry-run", action="store_true")
    mig.set_defaults(func=cmd_sprint_migrate_to_per_project)

    # task
    tk_p = sub.add_parser("task")
    tk_sub = tk_p.add_subparsers(dest="sub", required=True)
    add = leaf(tk_sub, "add")
    add.add_argument("title")
    add.add_argument("--sprint", default="current")
    add.add_argument("--project")
    add.add_argument("--epic")
    add.add_argument("--wave")
    add.add_argument("--description")
    add.add_argument(
        "--payload",
        required=True,
        help="JSON dispatch_payload com spec_ref + acceptance_criteria (wave-4 gate).",
    )
    add.set_defaults(func=cmd_task_add)
    sh = leaf(tk_sub, "show")
    sh.add_argument("task_id")
    sh.set_defaults(func=cmd_task_show)
    up = leaf(tk_sub, "update")
    up.add_argument("task_id")
    up.add_argument("--title")
    up.add_argument("--description")
    up.add_argument("--project")
    up.add_argument("--clear-project", action="store_true")
    up.add_argument("--epic")
    up.add_argument("--wave")
    up.set_defaults(func=cmd_task_update)
    mv = leaf(tk_sub, "move")
    mv.add_argument("task_id")
    mv.add_argument(
        "status",
        choices=["backlog", "ready", "in_progress", "testing", "done", "rejected"],
    )
    mv.add_argument(
        "--force", action="store_true",
        help="bypass whitelist (humano so); emite forced=true no evento",
    )
    mv.add_argument(
        "--reason", default=None,
        help="motivo da transicao (obrigatorio para agentes fora da whitelist e para rejected)",
    )
    mv.set_defaults(func=cmd_task_move)
    rs = leaf(tk_sub, "resprint")
    rs.add_argument("task_id")
    rs.add_argument("sprint")
    rs.set_defaults(func=cmd_task_resprint)
    ar = leaf(tk_sub, "archive")
    ar.add_argument("task_id")
    ar.set_defaults(func=cmd_task_archive)
    un = leaf(tk_sub, "unarchive")
    un.add_argument("task_id")
    un.add_argument(
        "--status", default="backlog",
        choices=["backlog", "ready", "in_progress", "testing", "done", "rejected"],
        help="status para restaurar (default: backlog)",
    )
    un.set_defaults(func=cmd_task_unarchive)
    bl = leaf(tk_sub, "block")
    bl.add_argument("task_id")
    bl.add_argument("--reason", required=True, help="motivo do bloqueio")
    bl.set_defaults(func=cmd_task_block)
    ub = leaf(tk_sub, "unblock")
    ub.add_argument("task_id")
    ub.set_defaults(func=cmd_task_unblock)
    rp = leaf(tk_sub, "reopen")
    rp.add_argument("task_id")
    rp.add_argument(
        "--to", required=True,
        choices=["backlog", "ready", "in_progress", "testing"],
        help="destino (deve ser nao-terminal)",
    )
    rp.add_argument("--reason", required=True, help="motivo da reabertura")
    rp.set_defaults(func=cmd_task_reopen)
    sp = leaf(tk_sub, "set-dispatch-payload")
    sp.add_argument("task_id")
    sp.add_argument(
        "--payload", required=True,
        help="JSON string com o dispatch_payload",
    )
    sp.add_argument(
        "--merge", action="store_true",
        help="shallow merge (default: replace)",
    )
    sp.set_defaults(func=cmd_task_set_dispatch_payload)
    sbb = leaf(tk_sub, "set-blocked-by")
    sbb.add_argument("task_id")
    sbb_group = sbb.add_mutually_exclusive_group(required=True)
    sbb_group.add_argument("--preds", help="CSV de task_ids (substitui)")
    sbb_group.add_argument("--add", help="1 task_id a acrescentar (idempotente)")
    sbb_group.add_argument("--remove", help="1 task_id a remover")
    sbb.set_defaults(func=cmd_task_set_blocked_by)
    ls = leaf(tk_sub, "list")
    ls.add_argument("--sprint")
    ls.add_argument("--status")
    ls.add_argument("--project")
    ls.add_argument("--epic")
    ls.add_argument("--archived", action="store_true")
    ls.add_argument(
        "--blocked", dest="blocked_only", action="store_true",
        help="so tasks com blocked=true",
    )
    ls.set_defaults(func=cmd_task_list)

    # project
    pr_p = sub.add_parser("project")
    pr_sub = pr_p.add_subparsers(dest="sub", required=True)
    leaf(pr_sub, "list").set_defaults(func=cmd_project_list)
    padd = leaf(pr_sub, "add")
    padd.add_argument("name")
    padd.set_defaults(func=cmd_project_add)

    # project create
    pcreate = leaf(pr_sub, "create")
    pcreate.add_argument("name", help="Display name (e.g. 'Customer Portal')")
    pcreate.add_argument("--id", default=None,
                         help="kebab-case ID; default = slugify(name)")
    pcreate.add_argument("--description", default="")
    pcreate.add_argument("--prd", default=None,
                         help="path to PRD .md file (used by persona LLM)")
    pcreate.add_argument("--domain", default="",
                         help="project domain (Produto, Ops, Tech, Growth, ...)")
    pcreate.set_defaults(func=cmd_project_create)

    # project edit
    pedit = leaf(pr_sub, "edit")
    pedit.add_argument("id", help="project id (kebab-case)")
    pedit.add_argument("--bot-id", default=None,
                       dest="bot_id",
                       help="Telegram bot id (slug); pass empty string to clear")
    pedit.add_argument("--bot-username", default=None,
                       dest="bot_username",
                       help="Telegram @username (sem @); pass empty to clear")
    pedit.add_argument("--bot-port", default=None,
                       dest="bot_port",
                       help="Gateway port int; pass empty to clear")
    pedit.add_argument("--github-url", default=None,
                       dest="github_url")
    pedit.add_argument("--description", default=None)
    pedit.set_defaults(func=cmd_project_edit)

    # project remove
    premove = leaf(pr_sub, "remove")
    premove.add_argument("id", help="project id (kebab-case)")
    premove.add_argument("--skip-github", action="store_true", dest="skip_github",
                        help="skip step 6 GitHub delete (testes ou cleanup local-only)")
    premove.set_defaults(func=cmd_project_remove)

    # project regenerate-persona
    pregen = leaf(pr_sub, "regenerate-persona")
    pregen.add_argument("id", help="project id (kebab-case)")
    pregen.add_argument("--name", default=None,
                        help="display name (default: id)")
    pregen.add_argument("--domain", default="",
                        help="project domain")
    pregen.add_argument("--force", action="store_true",
                        help="re-generate even if persona_status: generated")
    pregen.set_defaults(func=cmd_project_regenerate_persona)

    # project migrate-meta (W1: legacy flat → capabilities schema)
    pmig = leaf(pr_sub, "migrate-meta")
    pmig.add_argument("--dry-run", action="store_true", dest="dry_run",
                      help="preview sem escrever; mandatório antes do run real")
    pmig.add_argument("--skip-remote", action="store_true", dest="skip_remote",
                      help="pular gh repo view (testes / fast-path)")
    pmig.add_argument("--skip-systemctl", action="store_true",
                      dest="skip_systemctl",
                      help="pular systemctl is-active (testes)")
    pmig.add_argument("--skip-knowledge", action="store_true",
                      dest="skip_knowledge",
                      help="pular detect_knowledge_slot (CI/host sem "
                           "origin/main fetched no bevox-knowledge)")
    pmig.set_defaults(func=cmd_project_migrate_meta)

    # project status (W3): read-only capability matrix
    # Codes: P=provisioned, p=partial, -=absent, ?=drifted/skipped, !=error
    pstatus = leaf(pr_sub, "status")
    pstatus.add_argument(
        "slug", nargs="?", default=None,
        help="project slug; omit to render dispatcher table (all projects)",
    )
    pstatus.add_argument(
        "--no-detect", action="store_true", dest="no_detect",
        help="skip runtime detect; show declared state only (fast-path)",
    )
    pstatus.add_argument(
        "--skip-remote", action="store_true", dest="skip_remote",
        help="skip gh repo view (offline / CI)",
    )
    pstatus.add_argument(
        "--skip-systemctl", action="store_true", dest="skip_systemctl",
        help="skip systemctl is-active (CI / non-systemd hosts)",
    )
    pstatus.add_argument(
        "--skip-knowledge", action="store_true", dest="skip_knowledge",
        help="skip detect_knowledge_slot (no origin/main fetched)",
    )
    pstatus.set_defaults(func=cmd_project_status)

    # project adopt (W4): brownfield entry point
    from lib.cli.cmd_project_adopt import register_subcommand as _register_adopt
    _register_adopt(pr_sub, leaf)

    # project doctor (W5): cross-project drift scan + repair
    from lib.cli.cmd_project_doctor import register_subcommand as _register_doctor
    _register_doctor(pr_sub, leaf)

    # knowledge (skill V2 W0 foundation): stubs em W0; impl em W1-W4
    knowledge = sub.add_parser("knowledge", help="bevox-knowledge governance")
    knowledge_sub = knowledge.add_subparsers(dest="knowledge_cmd", required=True)
    from lib.cli.cmd_knowledge import register_subcommand as _register_knowledge
    _register_knowledge(knowledge_sub, leaf)

    # events
    ev_p = sub.add_parser("events")
    ev_sub = ev_p.add_subparsers(dest="sub", required=True)
    et = leaf(ev_sub, "tail")
    et.add_argument("--n", type=int, default=20)
    et.add_argument("--since")
    # --actor-filter avoids collision with common --actor (identity). Plan uses
    # --actor for filtering; users pass --actor-filter here instead.
    et.add_argument("--actor-filter", dest="actor_filter")
    et.add_argument("--type")
    et.add_argument("--task")
    et.add_argument("--sprint")
    et.set_defaults(func=cmd_events_tail)
    es = leaf(ev_sub, "show")
    es.add_argument("seq", type=int)
    es.set_defaults(func=cmd_events_show)

    # maintenance
    leaf(sub, "rebuild").set_defaults(func=cmd_rebuild)
    leaf(sub, "status").set_defaults(func=cmd_status)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except store.LockContentionError as e:
        return _err(str(e), "lock_contention", args.json)
    except ValueError as e:
        return _err(str(e), "invalid_input", args.json)
    except Exception as e:
        return _err(f"{type(e).__name__}: {e}", "state_error", args.json)


if __name__ == "__main__":
    sys.exit(main())
