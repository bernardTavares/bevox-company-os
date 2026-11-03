"""CLI tester-agent."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

from . import checker as checker_lib
from . import context_loader as ctx_lib
from . import lifecycle as lifecycle_lib
from . import store

EXIT_OK = 0
EXIT_INPUT = 1
EXIT_PRECHECK_FAILED_INFRA = 2
EXIT_PROPOSES_REJECTION = 3

VALID_REJECT_CATEGORIES = {
    "task_malformed", "spec_inconsistent", "requires_re_decomposition",
    "inexecutable", "manual",
}

_EXIT_BY_CODE = {
    "TASK_NOT_FOUND": EXIT_INPUT,
    "KANBAN_CLI_TIMEOUT": EXIT_INPUT,
    "KANBAN_CLI_FAILED": EXIT_INPUT,
    "KANBAN_CLI_BAD_JSON": EXIT_INPUT,
    "INVALID_REJECT_CATEGORY": EXIT_INPUT,
    "TEST_RUN_NOT_FOUND": EXIT_INPUT,
}


def _err(msg: str, code: str, json_mode: bool) -> int:
    if json_mode:
        print(json.dumps({"ok": False, "error": msg, "code": code}))
    else:
        print(f"ERROR ({code}): {msg}", file=sys.stderr)
    return _EXIT_BY_CODE.get(code, 2)


def _print(payload: Any, json_mode: bool, human: Optional[str] = None) -> None:
    if json_mode:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if human is not None:
            print(human)
        else:
            print(json.dumps(payload, ensure_ascii=False, indent=2))


def _decision_exit_code(decision: str) -> int:
    if decision == "proposed_rejected":
        return EXIT_PROPOSES_REJECTION
    return EXIT_OK


def cmd_check(args: argparse.Namespace) -> int:
    try:
        result = lifecycle_lib.run_check(
            args.task_id, no_act=args.no_act, model=args.model, trigger="manual",
        )
    except ctx_lib.ContextError as e:
        return _err(e.detail, e.code, args.json)
    except lifecycle_lib.LifecycleError as e:
        return _err(e.detail, e.code, args.json)

    decision = result.get("decision") or ""
    pc_passed = result.get("prechecks", {}).get("passed", False)

    if args.json:
        _print(result, True)
    else:
        print(f"test_run: {result['test_run_id']}")
        print(f"  prechecks_passed: {pc_passed}")
        if not pc_passed:
            print(f"  failure_reason: {result['prechecks']['failure_reason']}")
        else:
            n_pass = sum(1 for c in result['checks'] if c['effective_status'] == 'pass')
            n_fail = sum(1 for c in result['checks'] if c['effective_status'] == 'fail')
            n_inc = sum(1 for c in result['checks'] if c['effective_status'] == 'inconclusive')
            n_struct = sum(1 for c in result['checks'] if c.get('effective_structural_concern'))
            print(f"  ac_results: {n_pass}p / {n_fail}f / {n_inc}i ({len(result['checks'])} total)"
                  + (f" + {n_struct} structural_concern" if n_struct else ""))
        print(f"  overall: {result['overall']}")
        print(f"  decision: {decision}")
        print(f"  reason: {result['decision_reason']}")
        if result.get("kanban_actions_applied"):
            print(f"  applied: {', '.join(result['kanban_actions_applied'])}")

    if not pc_passed and not args.no_act:
        # precheck infrastrutural fail (log missing etc) — exit 2 ate Bernard fix
        infra_fails = {"execution_log_exists", "acceptance_criteria_non_empty"}
        failed_keys = {k for k, v in result["prechecks"]["details"].items() if not v}
        if failed_keys & infra_fails:
            return EXIT_PRECHECK_FAILED_INFRA

    return _decision_exit_code(decision)


def cmd_recheck(args: argparse.Namespace) -> int:
    # Recheck = mesma logica do check; novo seq sai automatico
    return cmd_check(args)


def cmd_results(args: argparse.Namespace) -> int:
    runs = store.list_test_runs(task_id=args.task_id)
    if args.failed:
        runs = [r for r in runs if r.get("decision") == "in_progress_test_failed"
                or r.get("decision") == "in_progress_test_failed_precheck"]
    elif args.inconclusive:
        runs = [r for r in runs if r.get("decision") == "in_progress_test_inconclusive"]
    elif args.proposed_rejection:
        runs = [r for r in runs if r.get("decision") == "proposed_rejected"]
    if args.json:
        _print({"test_runs": runs}, True)
        return EXIT_OK
    if not runs:
        print("(nenhum test_run)")
        return EXIT_OK
    print(f"{'TEST_RUN_ID':30s} {'TASK':10s} {'OVERALL':30s} DECISION")
    for r in runs:
        print(f"{r.get('test_run_id', '?'):30s} "
              f"{r.get('task_id', '?'):10s} "
              f"{(r.get('overall') or '?'):30s} "
              f"{r.get('decision') or '?'}")
    return EXIT_OK


def cmd_show(args: argparse.Namespace) -> int:
    target = args.target
    if "-tr-" in target:
        # test_run_id
        tr = store.read_test_run(target)
        if tr is None:
            return _err(f"test_run {target} nao existe",
                        "TEST_RUN_NOT_FOUND", args.json)
        if args.json:
            _print(tr, True)
            return EXIT_OK
        print(f"=== {target} ===")
        print(json.dumps(tr, ensure_ascii=False, indent=2))
        return EXIT_OK
    # task_id: lista test_runs dessa task
    runs = store.list_test_runs(task_id=target)
    if not runs:
        return _err(f"nenhum test_run para {target}",
                    "TEST_RUN_NOT_FOUND", args.json)
    if args.json:
        _print({"task_id": target, "test_runs": runs}, True)
        return EXIT_OK
    print(f"test_runs for {target}:")
    for r in runs:
        print(f"  {r.get('test_run_id'):30s} {r.get('decision') or '?'}")
    return EXIT_OK


def cmd_reject_task(args: argparse.Namespace) -> int:
    parts = args.reason.split(":", 1)
    if not parts or parts[0].strip() not in VALID_REJECT_CATEGORIES:
        return _err(
            f"categoria invalida. Use '<cat>: <detail>' com cat em "
            f"{sorted(VALID_REJECT_CATEGORIES)}",
            "INVALID_REJECT_CATEGORY", args.json,
        )
    try:
        lifecycle_lib.reject_task(args.task_id, args.reason)
    except lifecycle_lib.LifecycleError as e:
        return _err(e.detail, e.code, args.json)
    # Clear escalation (latest seq)
    runs = store.list_test_runs(task_id=args.task_id)
    if runs:
        latest = max(runs, key=lambda r: r.get("test_run_id", ""))
        store.clear_escalation(latest.get("test_run_id"))
    _print({"ok": True, "task_id": args.task_id, "reason": args.reason},
           args.json,
           f"rejected: {args.task_id} (reason: {args.reason})")
    return EXIT_OK


def cmd_escalations(args: argparse.Namespace) -> int:
    escs = store.list_escalations()
    if args.json:
        _print({"escalations": escs}, True)
        return EXIT_OK
    if not escs:
        print("(nenhuma escalation pending)")
        return EXIT_OK
    print(f"{'TEST_RUN_ID':30s} ESCALATION_PATH")
    for e in escs:
        print(f"{e['test_run_id']:30s} {e['escalation_path']}")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true")
    common.add_argument("--actor", default="tester")

    p = argparse.ArgumentParser(prog="tester-agent")
    sub = p.add_subparsers(dest="cmd", required=True)

    def leaf(psub, name):
        return psub.add_parser(name, parents=[common])

    ck = leaf(sub, "check")
    ck.add_argument("task_id")
    ck.add_argument("--no-act", action="store_true",
                    help="dry-run: gera test_run JSON, NAO move kanban")
    ck.add_argument("--model", default="claude-haiku-4-5")
    ck.set_defaults(func=cmd_check)

    rc = leaf(sub, "recheck")
    rc.add_argument("task_id")
    rc.add_argument("--no-act", action="store_true")
    rc.add_argument("--model", default="claude-haiku-4-5")
    rc.set_defaults(func=cmd_recheck)

    rs = leaf(sub, "results")
    rs.add_argument("--task-id", default=None)
    rs.add_argument("--all", action="store_true")
    rs.add_argument("--failed", action="store_true")
    rs.add_argument("--inconclusive", action="store_true")
    rs.add_argument("--proposed-rejection", action="store_true")
    rs.set_defaults(func=cmd_results)

    sh = leaf(sub, "show")
    sh.add_argument("target", help="task_id ou test_run_id")
    sh.set_defaults(func=cmd_show)

    rj = leaf(sub, "reject-task")
    rj.add_argument("task_id")
    rj.add_argument("--reason", required=True)
    rj.add_argument("--commit", action="store_true")
    rj.set_defaults(func=cmd_reject_task)

    es = leaf(sub, "escalations")
    es.set_defaults(func=cmd_escalations)

    return p


def main(argv=None) -> int:
    p = build_parser()
    args = p.parse_args(argv)
    if args.cmd == "reject-task" and not getattr(args, "commit", False):
        print("ERROR: --commit obrigatorio pra aplicar (gate humano)",
              file=sys.stderr)
        return EXIT_INPUT
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
