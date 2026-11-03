"""CLI dispatcher.

Wave-1 Phase 2 skeleton: apenas `list` e `show` funcionais (usam somente
lib/store.py). `propose`, `accept`, `reject`, `diff` sao stubs que
retornam NOT_IMPLEMENTED ate as Phases 5/6/7 do plan.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

from . import materializer as materializer_lib
from . import parser as parser_lib
from . import projects as projects_lib
from . import proposer as proposer_lib
from . import store

PLANS_DIR = Path(f"{Path.home()}/.openclaw/docs/superpowers/plans")

EXIT_OK = 0
EXIT_INPUT = 1
EXIT_STATE = 2

# Exit codes pra erros de codigo:
_EXIT_BY_CODE = {
    "invalid_input": EXIT_INPUT,
    "PROPOSAL_NOT_FOUND": EXIT_INPUT,
    "NOT_IMPLEMENTED": EXIT_STATE,
    "PLAN_NOT_FOUND": EXIT_INPUT,
    "PLAN_MISSING_EPIC": EXIT_INPUT,
    "NO_PHASES_FOUND": EXIT_INPUT,
    "NO_TASKS_FOUND": EXIT_INPUT,
    "AMBIGUOUS_PROJECT": EXIT_INPUT,
    "UNKNOWN_PROJECT": EXIT_INPUT,
    "PROPOSAL_ALREADY_ACCEPTED": EXIT_INPUT,
    "PROPOSAL_ALREADY_REJECTED": EXIT_INPUT,
    "PROPOSAL_PARTIALLY_MATERIALIZED": EXIT_INPUT,
    "PLAN_DRIFT": EXIT_INPUT,
    "TARGET_SPRINT_NOT_FOUND": EXIT_INPUT,
    "INVALID_TITLE": EXIT_INPUT,
    "INVALID_PAYLOAD": EXIT_INPUT,
    "PARTIAL_MATERIALIZATION": EXIT_STATE,
}


def _resolve_plan_path(plan_arg: str) -> Path:
    """Slug ou path absoluto -> Path.

    Slug: tenta PLANS_DIR/<slug>.md ou PLANS_DIR/<slug>.
    Path absoluto: usa direto se existe.
    Raises ParseError PLAN_NOT_FOUND se nao resolve.
    """
    p = Path(plan_arg).expanduser()
    if p.is_absolute() and p.exists():
        return p
    candidate = PLANS_DIR / f"{plan_arg}.md"
    if candidate.exists():
        return candidate
    candidate2 = PLANS_DIR / plan_arg
    if candidate2.exists():
        return candidate2
    raise parser_lib.ParseError(
        "PLAN_NOT_FOUND",
        f"plan '{plan_arg}' nao resolve. Tente path absoluto ou slug "
        f"existente em {PLANS_DIR}",
    )


def _print(payload: Any, json_mode: bool, human: Optional[str] = None) -> None:
    if json_mode:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
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
    return _EXIT_BY_CODE.get(code, EXIT_STATE)


# ============ Implementados nesta phase ============

def cmd_list(args: argparse.Namespace) -> int:
    proposals = store.list_proposals(status_filter=args.status)
    if args.json:
        _print({"proposals": proposals}, True)
        return EXIT_OK
    if not proposals:
        print("(nenhum proposal)")
        return EXIT_OK
    print(f"{'ID':60s} {'STATUS':10s} TASKS EPIC/WAVE")
    for p in proposals:
        pid = p.get("proposal_id", "?")
        status = p.get("_computed_status", "?")
        total = p.get("total_tasks", 0)
        wave = p.get("wave_ref_root", "?")
        print(f"{pid[:60]:60s} {status:10s} {total:5d} {wave}")
    return EXIT_OK


def cmd_show(args: argparse.Namespace) -> int:
    try:
        proposal = store.read_proposal(args.proposal_id)
    except FileNotFoundError as e:
        return _err(str(e), "PROPOSAL_NOT_FOUND", args.json)
    if args.json:
        _print(proposal, True)
        return EXIT_OK

    # Human format
    state = proposal.get("state", {})
    if state.get("accepted_at"):
        computed_status = "accepted"
    elif state.get("rejected_at"):
        computed_status = "rejected"
    else:
        computed_status = "pending"
    print(f"proposal:      {proposal['proposal_id']}")
    print(f"status:        {computed_status}")
    print(f"plan_ref:      {proposal['plan_ref']}")
    print(f"plan_sha:      {proposal['plan_sha'] or '(not under git)'}")
    print(f"sprint_goal:   {proposal['sprint_goal'][:80]}")
    print(f"target_sprint: {proposal['target_sprint']}")
    print(f"target_project:{proposal.get('target_project') or '(per-task)'}")
    print(f"epic_id:       {proposal['epic_id']}")
    print(f"wave_ref_root: {proposal['wave_ref_root']}")
    print(f"totals:        {proposal['total_tasks']} tasks across "
          f"{proposal['total_phases']} phases")
    print(f"proposed_at:   {state.get('proposed_at')}")
    if state.get("accepted_at"):
        print(f"accepted_at:   {state['accepted_at']} by {state.get('accepted_by')}")
        mats = state.get("materialized_task_ids") or []
        print(f"materialized:  {len(mats)} tasks ({', '.join(mats[:5])}"
              f"{'...' if len(mats) > 5 else ''})")
    if state.get("rejected_at"):
        print(f"rejected_at:   {state['rejected_at']} by {state.get('rejected_by')}")
        print(f"reject_reason: {state.get('reject_reason')}")
    warnings = proposal.get("_warnings") or []
    if warnings:
        print(f"warnings ({len(warnings)}):")
        for w in warnings:
            print(f"  ! {w}")
    print("")
    print("tasks:")
    for t in proposal["tasks"]:
        print(f"  {t['provisional_id']:6s} [{t['project']:16s}] "
              f"{t['wave_ref']}  {t['title'][:50]}")
    return EXIT_OK


# ============ inspect (Phase 3 — preview estrutural, sem proposal) ============

def cmd_inspect(args: argparse.Namespace) -> int:
    """Parse o plan e mostra estrutura (header, phases, tasks, project resolution).

    NAO gera proposal. Inclui project resolution per-task (rule 1/2/3).
    """
    try:
        plan_path = _resolve_plan_path(args.plan)
        text = parser_lib.load_plan(plan_path)
        summary = parser_lib.parse_plan_summary(text)
    except parser_lib.ParseError as e:
        return _err(e.detail, e.code, args.json)

    # Project resolution (Phase 4): opt-in para inspect; flag do CLI
    proj_map: dict = {}
    proj_warnings: list = []
    proj_error_msg = None
    try:
        proj_map, proj_warnings = projects_lib.resolve_all_tasks(
            summary["tasks"], summary["header"],
            cli_override=args.project_override,
            validate_against_canonical=True,
        )
    except projects_lib.AmbiguousProjectError as e:
        proj_error_msg = ("AMBIGUOUS_PROJECT", str(e))
    except projects_lib.UnknownProjectError as e:
        proj_error_msg = ("UNKNOWN_PROJECT", str(e))

    if args.json:
        summary["project_resolution"] = {
            "map": proj_map,
            "warnings": proj_warnings,
            "error": (
                {"code": proj_error_msg[0], "detail": proj_error_msg[1]}
                if proj_error_msg else None
            ),
        }
        _print(summary, True)
        return EXIT_OK

    # Human output
    h = summary["header"]
    print(f"plan: {plan_path}")
    print("")
    print("== HEADER ==")
    print(f"  Goal:        {h.get('goal') or '(missing)'}")
    print(f"  Epico:       {h['wave_ref_root']}")
    print(f"               epic_id={h['epic_id']} wave_slug={h['wave_slug']}")
    if h["project"]:
        print(f"  Project:     {h['project']}  (plan-level explicit)")
    elif h["projects"]:
        print(f"  Projects:    {', '.join(h['projects'])}  (multi; per-task path resolution)")
    else:
        print("  Project(s):  (none; per-task path resolution)")
    if h["tech_stack"]:
        print(f"  Tech stack:  {len(h['tech_stack'])} entries")
    if h["specs_canonicas"]:
        print(f"  Refs ({len(h['specs_canonicas'])}):")
        for r in h["specs_canonicas"]:
            print(f"    - {r}")
    print("")
    print(f"== PHASES ({summary['total_phases']}) ==")
    for ph in summary["phases"]:
        print(f"  Phase {ph['phase_num']}: {ph['phase_name']}"
              f"  ({ph['task_count']} tasks)")
    print("")
    print(f"== TASKS ({summary['total_tasks']}) ==")
    for t in summary["tasks"]:
        proj = proj_map.get(t["task_num"], "?")
        print(f"  Task {t['task_num']:6s} (Phase {t['phase_num']}) "
              f"files={t['files_count']} steps={t['steps_count']} "
              f"expected={t['expected_count']}  project={proj:16s}  "
              f"{t['task_subject'][:50]}")
    print("")
    print("== PROJECT RESOLUTION ==")
    if proj_warnings:
        print(f"  warnings ({len(proj_warnings)}):")
        for w in proj_warnings:
            print(f"    ! {w}")
    else:
        print("  warnings: (none)")
    if proj_error_msg:
        code, detail = proj_error_msg
        print(f"  ERROR: {code}")
        for line in detail.splitlines():
            print(f"    {line}")
        return EXIT_INPUT
    print(f"  resolved: {len(proj_map)}/{summary['total_tasks']} tasks")
    return EXIT_OK


# ============ propose (Phase 5 — gera proposal; zero materializacao) ============

def cmd_propose(args: argparse.Namespace) -> int:
    """Parse plan + resolve projects + escreve proposal JSON. Zero side-effect
    no kanban. Output: proposal_id + summary.
    """
    from . import dependency_resolver, gate_check

    try:
        plan_path = _resolve_plan_path(args.plan)
        proposal = proposer_lib.build_proposal(
            plan_path=plan_path,
            cli_project_override=args.project_override,
            cli_target_sprint=args.target_sprint,
            actor=args.actor,
            dependency_mode=args.dependency_mode,
        )
    except parser_lib.ParseError as e:
        return _err(e.detail, e.code, args.json)
    except projects_lib.AmbiguousProjectError as e:
        return _err(str(e), "AMBIGUOUS_PROJECT", args.json)
    except projects_lib.UnknownProjectError as e:
        return _err(str(e), "UNKNOWN_PROJECT", args.json)
    except dependency_resolver.CycleDetectedError as e:
        return _err(f"cycle: {' -> '.join(e.cycle)}", "CYCLE_DETECTED", args.json)
    except ValueError as e:
        msg = str(e)
        if "explicit mode" in msg:
            return _err(msg, "EXPLICIT_MODE_MISSING_OVERRIDE", args.json)
        raise
    except gate_check.GateCheckFailedError as e:
        detail = "; ".join(e.failures)
        return _err(detail, "GATE_CHECK_FAILED", args.json)

    path = store.write_proposal(proposal)
    warnings_count = len(proposal.get("_warnings", []))

    if args.json:
        _print({
            "ok": True,
            "proposal_id": proposal["proposal_id"],
            "path": str(path),
            "total_tasks": proposal["total_tasks"],
            "total_phases": proposal["total_phases"],
            "epic_id": proposal["epic_id"],
            "wave_ref_root": proposal["wave_ref_root"],
            "plan_sha": proposal["plan_sha"],
            "warnings_count": warnings_count,
        }, True)
        return EXIT_OK

    display_path = str(path).replace(f"{Path.home()}/", "~/")
    print(f"proposal created: {proposal['proposal_id']}")
    print(f"  path:           {display_path}")
    print(f"  plan_ref:       {proposal['plan_ref']}")
    print(f"  plan_sha:       {proposal['plan_sha'] or '(not under git)'}")
    print(f"  sprint_goal:    {proposal['sprint_goal'][:80]}")
    print(f"  target_sprint:  {proposal['target_sprint']}")
    print(f"  epic_id:        {proposal['epic_id']}")
    print(f"  wave_ref_root:  {proposal['wave_ref_root']}")
    print(f"  tasks:          {proposal['total_tasks']} across "
          f"{proposal['total_phases']} phases")
    print(f"  warnings:       {warnings_count}")
    if warnings_count:
        for w in proposal["_warnings"]:
            print(f"    ! {w}")
    return EXIT_OK


def cmd_diff(args: argparse.Namespace) -> int:
    """Preview 100% local: lista invocacoes `cli.sh task add` + set-dispatch-payload
    que o accept materializaria. NAO toca kanban.
    """
    try:
        proposal = store.read_proposal(args.proposal_id)
    except FileNotFoundError as e:
        return _err(str(e), "PROPOSAL_NOT_FOUND", args.json)

    state = proposal.get("state", {})
    if state.get("accepted_at"):
        status_note = (
            f"(proposal ja aceita em {state['accepted_at']} — diff e historico, "
            f"nao preview)"
        )
    elif state.get("rejected_at"):
        status_note = (
            f"(proposal ja rejeitada em {state['rejected_at']} — diff e historico, "
            f"accept bloqueado)"
        )
    else:
        status_note = "(preview de materializacao — nenhum side effect agora)"

    if args.json:
        import json as _json
        preview = []
        for t in proposal["tasks"]:
            # Wave-4: add_cmd agora inclui --payload minimo (spec_ref + ac)
            # com fallback spec_refs (plural) -> spec_ref (gate key)
            dp = t.get("dispatch_payload") or {}
            spec_ref_val = dp.get("spec_ref")
            if spec_ref_val is None:
                spec_ref_val = dp.get("spec_refs")
            minimal_payload = {
                "spec_ref": spec_ref_val,
                "acceptance_criteria": dp.get("acceptance_criteria"),
            }
            preview.append({
                "provisional_id": t["provisional_id"],
                "add_cmd": [
                    "task", "add", t["title"],
                    "--sprint", t["sprint_target"],
                    "--project", t["project"],
                    "--epic", t["epic_id"],
                    "--wave", t["wave_ref"],
                    "--payload", _json.dumps(minimal_payload, ensure_ascii=False),
                ],
                "set_payload_keys": sorted(t["dispatch_payload"].keys()),
            })
        _print({
            "proposal_id": proposal["proposal_id"],
            "status_note": status_note,
            "preview": preview,
        }, True)
        return EXIT_OK

    print(f"proposal: {proposal['proposal_id']}")
    print(f"  {status_note}")
    print(f"  target_sprint: {proposal['target_sprint']}")
    print(f"  total:         {proposal['total_tasks']} tasks")
    print("")
    print("Preview (cli.sh invocations that accept would run):")
    for t in proposal["tasks"]:
        title_esc = t["title"].replace('"', '\\"')[:60]
        # Wave-4: preview inclui --payload minimo no task add
        print(f'  kanban-tasks: task add "{title_esc}" '
              f'--sprint {t["sprint_target"]} '
              f'--project {t["project"]} '
              f'--epic {t["epic_id"]} '
              f'--wave {t["wave_ref"]} '
              f"--payload '<minimal: spec_ref + acceptance_criteria>' "
              f'({t["provisional_id"]})')
        dp_keys = sorted(t["dispatch_payload"].keys())
        print(f'    then: task set-dispatch-payload <T-NNNN> --payload '
              f'<json with keys: {", ".join(dp_keys)}>')
    return EXIT_OK


def cmd_reject(args: argparse.Namespace) -> int:
    """Marca proposal como rejeitada. Idempotente (proposal ja rejeitada
    erra claro; aceita nao pode ser rejeitada).

    100% proposal-local: escreve so no arquivo da proposal. Zero side
    effect em kanban, tracker, ou qualquer outra surface.
    """
    try:
        proposal = store.read_proposal(args.proposal_id)
    except FileNotFoundError as e:
        return _err(str(e), "PROPOSAL_NOT_FOUND", args.json)

    state = proposal.setdefault("state", {})
    if state.get("accepted_at"):
        return _err(
            f"proposal ja aceita em {state['accepted_at']} por "
            f"{state.get('accepted_by', '?')}; accept eh terminal, nao "
            f"pode rejeitar",
            "PROPOSAL_ALREADY_ACCEPTED", args.json,
        )
    if state.get("rejected_at"):
        return _err(
            f"proposal ja rejeitada em {state['rejected_at']} por "
            f"{state.get('rejected_by', '?')} (reason: "
            f"{state.get('reject_reason', '?')})",
            "PROPOSAL_ALREADY_REJECTED", args.json,
        )

    state["rejected_at"] = store.now_iso()
    state["rejected_by"] = args.actor
    state["reject_reason"] = args.reason
    store.update_proposal(proposal)

    _print(
        {"ok": True, "proposal_id": args.proposal_id,
         "rejected_at": state["rejected_at"],
         "rejected_by": state["rejected_by"],
         "reject_reason": state["reject_reason"]},
        args.json,
        f"rejected: {args.proposal_id}\n"
        f"  rejected_at:   {state['rejected_at']}\n"
        f"  rejected_by:   {state['rejected_by']}\n"
        f"  reject_reason: {state['reject_reason']}",
    )
    return EXIT_OK


def cmd_accept(args: argparse.Namespace) -> int:
    """Accept all-or-nothing. Preflight completo ANTES de mutar kanban;
    em caso de falha no meio, proposal vira partial (accept bloqueado).
    """
    try:
        proposal = store.read_proposal(args.proposal_id)
    except FileNotFoundError as e:
        return _err(str(e), "PROPOSAL_NOT_FOUND", args.json)
    try:
        result = materializer_lib.materialize(
            proposal,
            make_ready=args.ready,
            force_plan_drift=args.force_plan_drift,
            actor=args.actor,
        )
    except materializer_lib.MaterializerError as e:
        return _err(e.detail, e.code, args.json)

    _print(
        result, args.json,
        f"accepted: {args.proposal_id}\n"
        f"  resolved_sprint: {result['resolved_sprint']}\n"
        f"  materialized:    {result['total_materialized']} tasks\n"
        f"  ids:             {', '.join(result['materialized_task_ids'][:8])}"
        f"{'...' if result['total_materialized'] > 8 else ''}\n"
        f"  warnings:        {len(result['warnings'])}",
    )
    return EXIT_OK


# ============ Parser ============

def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="JSON output")
    common.add_argument("--actor", default="bernard", help="actor identity")

    p = argparse.ArgumentParser(prog="scrum-master-agent")
    sub = p.add_subparsers(dest="cmd", required=True)

    def leaf(psub, name):
        return psub.add_parser(name, parents=[common])

    # inspect (Phase 3+4 — parseia plan, mostra estrutura + project resolution)
    insp = leaf(sub, "inspect")
    insp.add_argument("--plan", required=True, help="plan slug ou path absoluto")
    insp.add_argument("--project-override", default=None,
                      help="escape pra AMBIGUOUS_PROJECT (mesmo shape do propose)")
    insp.set_defaults(func=cmd_inspect)

    # propose (stub)
    prop = leaf(sub, "propose")
    prop.add_argument("--plan", required=True, help="plan slug ou path absoluto")
    prop.add_argument("--target-sprint", default="next",
                      help="sprint alvo (current|next|<sprint-id>); default next")
    prop.add_argument("--project-override", default=None,
                      help="escape pra AMBIGUOUS_PROJECT")
    prop.add_argument("--dependency-mode", choices=["phase-sequence", "explicit", "hybrid"],
                      default="hybrid",
                      help="como deduzir blocked_by entre tasks (default: hybrid)")
    prop.set_defaults(func=cmd_propose)

    # list (implementado)
    ls = leaf(sub, "list")
    ls.add_argument("--status", default="pending",
                    choices=["pending", "accepted", "rejected", "all"])
    ls.set_defaults(func=cmd_list)

    # show (implementado)
    sh = leaf(sub, "show")
    sh.add_argument("proposal_id")
    sh.set_defaults(func=cmd_show)

    # diff
    df = leaf(sub, "diff")
    df.add_argument("proposal_id")
    df.set_defaults(func=cmd_diff)

    # reject
    rj = leaf(sub, "reject")
    rj.add_argument("proposal_id")
    rj.add_argument("--reason", required=True, help="motivo da rejeicao")
    rj.set_defaults(func=cmd_reject)

    # accept (Phase 7 materializer vira; state guards ja ativos)
    acc = leaf(sub, "accept")
    acc.add_argument("proposal_id")
    acc.add_argument("--ready", action="store_true",
                     help="cria tasks diretamente como ready (default backlog)")
    acc.add_argument("--force-plan-drift", action="store_true")
    acc.set_defaults(func=cmd_accept)

    return p


def main(argv=None) -> int:
    p = build_parser()
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
