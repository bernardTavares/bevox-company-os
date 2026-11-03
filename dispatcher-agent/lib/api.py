"""CLI dispatcher: argparse + cmd handlers."""

from pathlib import Path
import argparse
import json
import os
import subprocess
import sys
from typing import Any, Dict, Optional

from . import briefing as briefing_lib
from . import lifecycle as lifecycle_lib
from . import runner as runner_lib
from . import selector as selector_lib
from . import store

EXIT_OK = 0
EXIT_INPUT = 1
EXIT_STATE = 2

from . import allowlist

DEFAULT_ALLOWED_TOOLS = allowlist.default_tools()

# Wave-3: tester-agent CLI invocado SOMENTE em foreground mode pelo cmd_next.
# Em detached default, tester NAO eh auto-invocado (limitacao MVP wave-3
# §10.2 da spec; follow-up daemon reaper §16). Bernard usa
# `vox tester check <id>` manual.
TESTER_CLI = f"{Path.home()}/.openclaw/tester-agent/cli.sh"

_EXIT_BY_CODE = {
    "NO_READY_TASK": EXIT_INPUT,
    "WORK_IN_PROGRESS_LIMIT": EXIT_INPUT,
    "KANBAN_STATE_MISSING": EXIT_STATE,
    "KANBAN_STATE_INVALID": EXIT_STATE,
    "KANBAN_CLI_TIMEOUT": EXIT_STATE,
    "KANBAN_CLI_FAILED": EXIT_STATE,
    "KANBAN_CLI_BAD_JSON": EXIT_STATE,
    "SESSION_NOT_FOUND": EXIT_INPUT,
    "SESSION_NO_PID": EXIT_STATE,
    "SESSION_NOT_FINISHED": EXIT_STATE,
    "KILL_FAILED": EXIT_STATE,
    "FOREGROUND_TIMEOUT": EXIT_STATE,
}


def _err(msg: str, code: str, json_mode: bool) -> int:
    if json_mode:
        print(json.dumps({"ok": False, "error": msg, "code": code}))
    else:
        print(f"ERROR ({code}): {msg}", file=sys.stderr)
    return _EXIT_BY_CODE.get(code, EXIT_STATE)


def _print(payload: Any, json_mode: bool, human: Optional[str] = None) -> None:
    if json_mode:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if human is not None:
            print(human)
        else:
            print(json.dumps(payload, ensure_ascii=False, indent=2))


# ============ cmd_next: dry-run + --launch ============

def _invoke_tester(task_id: str, json_mode: bool) -> tuple:
    """Invoca tester-agent CLI sequencial. Retorna (invoked_bool, summary_dict).

    Foreground only — chamado dentro de cmd_next quando --foreground + sem
    --no-tester. Em modo detached, esta funcao NAO eh chamada (limitacao MVP
    wave-3 da spec; ver §10.2 + follow-up daemon reaper §16).
    """
    import subprocess as sp
    cmd = [TESTER_CLI, "check", task_id, "--json"]
    try:
        r = sp.run(cmd, capture_output=True, text=True, check=False, timeout=600)
    except (OSError, sp.TimeoutExpired) as e:
        if not json_mode:
            print(f"WARN: tester invoke failed: {e}", file=sys.stderr)
        return False, {"error": str(e)}
    if r.returncode not in (0, 3) and not json_mode:
        print(f"WARN: tester exit={r.returncode}; ver test_run", file=sys.stderr)
    summary: Dict[str, Any] = {"tester_exit_code": r.returncode}
    try:
        parsed = json.loads(r.stdout)
        summary["test_run_id"] = parsed.get("test_run_id")
        summary["overall"] = parsed.get("overall")
        summary["decision"] = parsed.get("decision")
    except (json.JSONDecodeError, ValueError):
        summary["raw_stdout_tail"] = r.stdout[-300:]
    return True, summary


def cmd_next(args: argparse.Namespace) -> int:
    try:
        if args.launch:
            selector_lib.check_one_task_per_project_guard(args.project)
        task = selector_lib.select_next_ready(args.project)
    except selector_lib.SelectorError as e:
        return _err(e.detail, e.code, args.json)

    allowed_tools = args.allowed_tools or DEFAULT_ALLOWED_TOOLS
    briefing_content = briefing_lib.render_briefing(task, allowed_tools)

    if args.briefing_only or not args.launch:
        bpath = store.write_briefing(task["id"], briefing_content)
        _print({
            "ok": True, "mode": "dry_run",
            "task_id": task["id"], "title": task.get("title"),
            "project": task.get("project"),
            "briefing_path": str(bpath),
        }, args.json,
            f"selected (dry-run): {task['id']} project={task.get('project')}\n"
            f"briefing: {bpath}\n"
            f"[use --launch pra mover status + invocar Claude Code]")
        return EXIT_OK

    bpath = store.write_briefing(task["id"], briefing_content)
    try:
        lifecycle_lib.move_to_in_progress(task["id"])
    except lifecycle_lib.LifecycleError as e:
        return _err(e.detail, e.code, args.json)

    ts = store.now_iso()
    metadata = {
        "dispatched_at": ts, "dispatcher_actor": "dispatcher",
        "briefing_path": str(bpath),
        "dispatch_mode": "foreground" if args.foreground else "detach",
        "dispatch_flags": {
            "no_tester": bool(args.no_tester),
        },
    }
    try:
        lifecycle_lib.merge_dispatch_payload(task["id"], metadata)
    except lifecycle_lib.LifecycleError as e:
        return _err(e.detail, e.code, args.json)

    # Lê sprint pra obter session_id (lazy create na primeira task)
    try:
        kanban_state = json.loads(
            selector_lib.KANBAN_STATE.read_text(encoding="utf-8")
        )
        sprint_obj = next(
            (sp for sp in kanban_state.get("sprints", [])
             if sp["id"] == task["sprint_id"]),
            None,
        )
        sprint_session_id_in = sprint_obj.get("execution_session_id") if sprint_obj else None
    except (OSError, json.JSONDecodeError):
        sprint_session_id_in = None

    try:
        if args.foreground:
            status = runner_lib.launch_foreground(
                task["id"], bpath, allowed_tools,
                sprint_session_id=sprint_session_id_in,
                sprint_id=task["sprint_id"],
                model=args.model,
            )
            lifecycle_lib.process_finished_session(task["id"])
            # Wave-3: auto-invoke tester (foreground only; default ON;
            # --no-tester desativa). Detached NAO chama _invoke_tester.
            tester_invoked = False
            tester_result_summary = None
            if not args.no_tester:
                tester_invoked, tester_result_summary = _invoke_tester(
                    task["id"], json_mode=args.json,
                )
            status["tester_invoked"] = tester_invoked
            if tester_result_summary:
                status["tester_result_summary"] = tester_result_summary
        else:
            status = runner_lib.launch_detached(
                task["id"], bpath, allowed_tools,
                sprint_session_id=sprint_session_id_in,
                sprint_id=task["sprint_id"],
                model=args.model,
            )
            # Wave-3: detached default NAO auto-invoca tester. Marca explicito.
            status["tester_invoked"] = False
            status["tester_skipped_reason"] = (
                "detached_mode: auto-invoke do tester so em foreground "
                "(limitacao MVP wave-3 §10.2; use 'vox tester check <id>' manual "
                "OR --foreground)"
            )
    except runner_lib.RunnerError as e:
        return _err(e.detail, e.code, args.json)

    # Se foi fresh E kill-switch off, gravar UUID na sprint via kanban CLI
    disable_reuse = os.environ.get("OPENCLAW_DISPATCHER_DISABLE_SESSION_REUSE") == "1"
    if status.get("sprint_session_was_fresh") and not disable_reuse:
        kanban_cli_path = f"{Path.home()}/.openclaw/kanban-tasks/cli.sh"
        try:
            subprocess.run(
                [kanban_cli_path, "sprint", "set-session-id",
                 "--sprint-id", task["sprint_id"],
                 "--session-id", status["sprint_session_id"],
                 "--actor", "dispatcher", "--json"],
                capture_output=True, text=True, timeout=10, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            # Não bloqueia dispatch — próxima task vai gerar fresh UUID
            pass

    lifecycle_lib.merge_dispatch_payload(task["id"], {
        "execution_session_id": status["session_id"],
        "execution_log_path": status["log_path"],
        "execution_started_at": status["started_at"],
    })

    _print(status, args.json,
           f"launched: {task['id']} ({status['run_mode']})\n"
           f"  session_id: {status['session_id']}\n"
           f"  pid:        {status['pid']}\n"
           f"  log:        {status['log_path']}\n"
           f"  briefing:   {status['briefing_path']}")
    return EXIT_OK


def cmd_status(args: argparse.Namespace) -> int:
    executions = store.list_executions()
    if args.json:
        for e in executions:
            e["alive"] = runner_lib.is_session_alive(e)
        _print({"executions": executions}, True)
        return EXIT_OK
    if not executions:
        print("(nenhuma session)")
        return EXIT_OK
    print(f"{'TASK':10s} {'MODE':10s} {'PID':6s} {'ALIVE':6s} STARTED                 FINISHED                EXIT")
    for e in executions:
        alive = "yes" if runner_lib.is_session_alive(e) else "no "
        pid = str(e.get("pid") or "?")
        started = e.get("started_at", "?")
        finished = e.get("finished_at") or "-"
        ec = e.get("exit_code")
        ec_str = str(ec) if ec is not None else "-"
        print(f"{e['task_id']:10s} {e.get('run_mode', '?'):10s} {pid:6s} {alive:6s} {started:23s} {finished:23s} {ec_str}")
    return EXIT_OK


def cmd_show(args: argparse.Namespace) -> int:
    status = store.read_execution_status(args.task_id)
    if status is None:
        return _err(
            f"{args.task_id}: sem status.json", "SESSION_NOT_FOUND", args.json,
        )
    status["alive"] = runner_lib.is_session_alive(status)
    _print(status, args.json)
    return EXIT_OK


def cmd_tail(args: argparse.Namespace) -> int:
    path = store.execution_log_path(args.task_id)
    if not path.exists():
        return _err(
            f"{args.task_id}: log nao existe", "SESSION_NOT_FOUND", args.json,
        )
    import subprocess as sp
    try:
        sp.run(["tail", "-f", str(path)], check=False)
    except KeyboardInterrupt:
        pass
    return EXIT_OK


def cmd_kill(args: argparse.Namespace) -> int:
    try:
        status = runner_lib.kill_session(args.task_id)
    except runner_lib.RunnerError as e:
        return _err(e.detail, e.code, args.json)
    _print({"ok": True, "killed": args.task_id, "status": status},
           args.json, f"killed: {args.task_id}")
    return EXIT_OK


def cmd_relaunch(args: argparse.Namespace) -> int:
    try:
        lifecycle_lib.unblock_for_relaunch(args.task_id)
    except lifecycle_lib.LifecycleError as e:
        return _err(e.detail, e.code, args.json)
    import subprocess as sp
    KANBAN_CLI = f"{Path.home()}/.openclaw/kanban-tasks/cli.sh"
    out = sp.run(
        [KANBAN_CLI, "task", "show", args.task_id, "--json"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    if out.returncode != 0:
        return _err(
            f"task show {args.task_id}: {out.stderr}",
            "KANBAN_CLI_FAILED", args.json,
        )
    task_data = json.loads(out.stdout).get("task")
    if task_data is None:
        return _err(f"{args.task_id} nao encontrada", "SESSION_NOT_FOUND", args.json)

    allowed_tools = args.allowed_tools or DEFAULT_ALLOWED_TOOLS
    content = briefing_lib.render_briefing(task_data, allowed_tools)
    bpath = store.write_briefing(args.task_id, content)

    # Lê sprint pra obter session_id (lazy create na primeira task)
    sprint_session_id_in = None
    try:
        kanban_state = json.loads(
            selector_lib.KANBAN_STATE.read_text(encoding="utf-8")
        )
        sprint_obj = next(
            (sp for sp in kanban_state.get("sprints", [])
             if sp["id"] == task_data["sprint_id"]),
            None,
        )
        if sprint_obj:
            sprint_session_id_in = sprint_obj.get("execution_session_id")
    except (OSError, json.JSONDecodeError):
        sprint_session_id_in = None

    try:
        status = runner_lib.launch_detached(
            args.task_id, bpath, allowed_tools,
            sprint_session_id=sprint_session_id_in,
            sprint_id=task_data["sprint_id"],
            model=args.model,
        )
    except runner_lib.RunnerError as e:
        return _err(e.detail, e.code, args.json)

    # Se foi fresh E kill-switch off, gravar UUID na sprint via kanban CLI
    disable_reuse = os.environ.get("OPENCLAW_DISPATCHER_DISABLE_SESSION_REUSE") == "1"
    if status.get("sprint_session_was_fresh") and not disable_reuse:
        kanban_cli_path = f"{Path.home()}/.openclaw/kanban-tasks/cli.sh"
        try:
            subprocess.run(
                [kanban_cli_path, "sprint", "set-session-id",
                 "--sprint-id", task_data["sprint_id"],
                 "--session-id", status["sprint_session_id"],
                 "--actor", "dispatcher", "--json"],
                capture_output=True, text=True, timeout=10, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            # Não bloqueia relaunch — próxima task vai gerar fresh UUID
            pass

    _print(status, args.json,
           f"relaunched: {args.task_id} (pid {status['pid']})")
    return EXIT_OK


def cmd_reap_detached(args: argparse.Namespace) -> int:
    """Wave-3.5: reap loop unico (--once). Sem daemon mode.

    Detecta trigger via env INVOCATION_ID (systemd seta) vs manual.
    """
    from . import reaper as reaper_lib
    trigger = "manual"
    if os.environ.get("INVOCATION_ID"):
        trigger = "systemd_timer"
    try:
        result = reaper_lib.run_tick(trigger=trigger, dry_run=args.dry_run)
    except reaper_lib.ReaperError as e:
        return _err(e.detail, e.code, args.json)
    if args.json:
        _print(result, True)
    else:
        if result.get("lock_skipped"):
            print(f"reap-detached: lock_skipped (other instance running) "
                  f"tick={result['tick_id'][:30]}")
        else:
            n = result["considered_executions"]
            r = result["reaped_count"]
            t = result["tester_invoked_count"]
            sa = result["skipped_already_reaped"]
            sr = result["skipped_still_running"]
            mode = "DRY-RUN" if args.dry_run else "applied"
            print(f"reap-detached [{mode}]: considered={n} reaped={r} "
                  f"tester_invoked={t} skipped_already={sa} skipped_running={sr}")
            # Quiet-log: skip already_reaped (passive idempotent skips that fire
            # every reaper tick). Operator only cares about state changes.
            for a in result.get("actions_per_task", []):
                if a.get("outcome") == "already_reaped":
                    continue
                print(f"  {a['task_id']}: {a['stage']} -> {a['outcome']}")
    return EXIT_OK


def cmd_cron_tick(args: argparse.Namespace) -> int:
    """Wave-4: cron-tick loop unico (--once). Sem daemon mode.

    Detecta trigger via env INVOCATION_ID (systemd seta) vs manual.
    """
    from . import cron as cron_lib
    trigger = "manual"
    if os.environ.get("INVOCATION_ID"):
        trigger = "systemd_timer"
    try:
        result = cron_lib.run_tick(trigger=trigger, dry_run=args.dry_run)
    except cron_lib.CronError as e:
        return _err(e.detail, e.code, args.json)
    if args.json:
        _print(result, True)
    else:
        if result.get("lock_skipped"):
            print(f"cron-tick: lock_skipped (other instance) tick={result['tick_id'][:30]}")
        elif result.get("kill_switch_active"):
            print(f"cron-tick: kill_switch_active (cron.disabled present) tick={result['tick_id'][:30]}")
        else:
            opt = result.get("opted_in_projects") or []
            n = result["projects_considered"]
            d = result["dispatched_count"]
            sb = result["projects_skipped_busy"]
            se = result["projects_skipped_escalation"]
            sn = result["projects_skipped_no_ready"]
            mode = "DRY-RUN" if args.dry_run else "applied"
            # Quiet-log: only print when a task is dispatched (real state change).
            # All skipped_* outcomes are passive (no work done) — operator queries
            # via --json or `vox kanban list` when curious.
            QUIET_OUTCOMES = ("skipped_no_ready", "skipped_busy", "skipped_escalation",
                              "skipped_no_current_sprint")
            interesting = d > 0 or any(
                a.get("outcome") not in QUIET_OUTCOMES
                for a in result.get("actions_per_project", [])
            )
            if interesting:
                print(f"cron-tick [{mode}]: opted_in={opt} dispatched={d} "
                      f"skipped_busy={sb} skipped_escalation={se} skipped_no_ready={sn} considered={n}")
                for a in result.get("actions_per_project", []):
                    if a.get("outcome") in QUIET_OUTCOMES:
                        continue
                    tid = f" ({a['task_id']})" if a.get("task_id") else ""
                    print(f"  {a['project']}: {a['outcome']}{tid}")
    return EXIT_OK


def cmd_cron_tick(args: argparse.Namespace) -> int:
    """Wave-4: cron-tick loop unico (--once). Sem daemon mode.

    Detecta trigger via env INVOCATION_ID (systemd seta) vs manual.
    """
    from . import cron as cron_lib
    trigger = "manual"
    if os.environ.get("INVOCATION_ID"):
        trigger = "systemd_timer"
    try:
        result = cron_lib.run_tick(trigger=trigger, dry_run=args.dry_run)
    except cron_lib.CronError as e:
        return _err(e.detail, e.code, args.json)
    if args.json:
        _print(result, True)
    else:
        if result.get("lock_skipped"):
            print(f"cron-tick: lock_skipped (other instance) "
                  f"tick={result['tick_id'][:30]}")
        elif result.get("kill_switch_active"):
            print(f"cron-tick: kill_switch_active (cron.disabled present) "
                  f"tick={result['tick_id'][:30]}")
        else:
            opt = result.get("opted_in_projects") or []
            n = result["projects_considered"]
            d = result["dispatched_count"]
            sb = result["projects_skipped_busy"]
            se = result["projects_skipped_escalation"]
            sn = result["projects_skipped_no_ready"]
            mode = "DRY-RUN" if args.dry_run else "applied"
            # Quiet-log: only print when something actually happened
            # (dispatched > 0 OR an unusual outcome). All skipped_* are passive.
            QUIET_OUTCOMES = ("skipped_no_ready", "skipped_busy",
                              "skipped_escalation", "skipped_no_current_sprint")
            interesting = d > 0 or any(
                a.get("outcome") not in QUIET_OUTCOMES
                for a in result.get("actions_per_project", [])
            )
            if interesting:
                print(f"cron-tick [{mode}]: opted_in={opt} dispatched={d} "
                      f"skipped_busy={sb} skipped_escalation={se} "
                      f"skipped_no_ready={sn} considered={n}")
                for a in result.get("actions_per_project", []):
                    if a.get("outcome") in QUIET_OUTCOMES:
                        continue
                    tid = f" ({a['task_id']})" if a.get("task_id") else ""
                    print(f"  {a['project']}: {a['outcome']}{tid}")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true")
    common.add_argument("--actor", default="dispatcher")

    p = argparse.ArgumentParser(prog="dispatcher-agent")
    sub = p.add_subparsers(dest="cmd", required=True)

    def leaf(psub, name):
        return psub.add_parser(name, parents=[common])

    nx = leaf(sub, "next")
    nx.add_argument("--project", default=None)
    nx.add_argument("--launch", action="store_true")
    nx.add_argument("--foreground", action="store_true")
    nx.add_argument("--no-tester", action="store_true",
                    help="Skip auto-invoke do tester apos auto-move testing. "
                         "Foreground: skip imediato. Detached: persistido em "
                         "dispatch_flags.no_tester; reaper (wave-3.5) respeita.")
    nx.add_argument("--briefing-only", action="store_true")
    nx.add_argument("--allowed-tools", default=None)
    nx.add_argument("--model", default="claude-opus-4-7")
    nx.set_defaults(func=cmd_next)

    st = leaf(sub, "status")
    st.set_defaults(func=cmd_status)

    sh = leaf(sub, "show")
    sh.add_argument("task_id")
    sh.set_defaults(func=cmd_show)

    tl = leaf(sub, "tail")
    tl.add_argument("task_id")
    tl.set_defaults(func=cmd_tail)

    kl = leaf(sub, "kill")
    kl.add_argument("task_id")
    kl.set_defaults(func=cmd_kill)

    rl = leaf(sub, "relaunch")
    rl.add_argument("task_id")
    rl.add_argument("--allowed-tools", default=None)
    rl.add_argument("--model", default="claude-opus-4-7")
    rl.set_defaults(func=cmd_relaunch)

    rp = leaf(sub, "reap-detached")
    rp.add_argument("--once", action="store_true",
                    help="Roda uma passada e sai (default; usado pelo systemd timer).")
    rp.add_argument("--dry-run", action="store_true",
                    help="Lista o que faria, sem agir.")
    rp.set_defaults(func=cmd_reap_detached)

    cr = leaf(sub, "cron-tick")
    cr.add_argument("--once", action="store_true",
                    help="Roda uma passada e sai (default; usado pelo systemd timer).")
    cr.add_argument("--dry-run", action="store_true",
                    help="Lista o que faria, sem agir.")
    cr.set_defaults(func=cmd_cron_tick)

    return p


def main(argv=None) -> int:
    p = build_parser()
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
