"""Proposer: monta proposal JSON a partir do plan parseado.

Guardrails Phase 5:
- ZERO materializacao. Zero chamada ao kanban. Zero side effect alem
  de escrever o arquivo em ~/.openclaw/scrum-master-agent/proposals/.
- `dispatch_payload` com shape fixo e minimo (§spec 5.4). Campos
  opcionais sao OMITIDOS quando source vazio (nao inventa conteudo).

Composicao:
- 1 proposal por plan.
- 1 plan Task -> 1 provisional task entry (P-001, P-002, ...).
- `wave_ref` = `<plan.epic>/<plan.wave>/Phase-<N>` (AJUSTE #1).
- `project` via projects_lib.resolve_all_tasks (raises AmbiguousProjectError
  / UnknownProjectError sem fallback silencioso).
"""

import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import parser as parser_lib
from . import projects as projects_lib
from . import store
from . import dependency_resolver, gate_check


def _plan_sha(plan_path: Path) -> Optional[str]:
    """Retorna git SHA do plan se o arquivo esta tracked; None caso contrario.

    Timeout 5s pra evitar travar em repos grandes.
    """
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--", str(plan_path)],
            capture_output=True, text=True, check=False,
            cwd=str(plan_path.parent), timeout=5,
        )
        if result.returncode != 0:
            return None
        sha = result.stdout.strip()
        return sha if sha else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def _make_proposal_id(plan_path: Path) -> str:
    """<timestamp_compact>-<plan_stem>."""
    ts = store.now_iso().replace(":", "").replace("-", "")
    slug = plan_path.stem.replace(".", "-")
    return f"{ts}-{slug}"


def _first_paragraph(body: str, max_lines: int = 3) -> str:
    """Pega a primeira paragraph apos o heading da task.

    Pula linhas vazias e `**Files:**` block. Retorna ate `max_lines`
    linhas colapsadas em single-string.
    """
    lines = body.splitlines()
    # Skip first line (heading) se presente
    start = 1 if lines and lines[0].lstrip().startswith("###") else 0
    collected: List[str] = []
    for raw in lines[start:]:
        stripped = raw.strip()
        if not stripped:
            if collected:
                break
            continue
        if stripped.startswith("**Files:**") or stripped.startswith("- [ ]"):
            if collected:
                break
            continue
        collected.append(stripped)
        if len(collected) >= max_lines:
            break
    return " ".join(collected).strip()


def _task_anchor(task_num: str) -> str:
    """Github-style slug do task heading.

    Ex: '1.1' -> 'task-1-1'
    """
    return f"task-{task_num.replace('.', '-')}"


def _build_dispatch_payload(
    parsed_task: Dict[str, Any],
    spec_refs: List[str],
    plan_ref_display: str,
) -> Dict[str, Any]:
    """Monta dispatch_payload com shape fixo. Omite campos com source vazio.

    Campos (spec §5.4):
    - goal:                 str (first paragraph OR task_subject)
    - spec_refs:            [str]   (plan-level)
    - plan_ref:             str     (path display-friendly)
    - plan_anchor:          str     (task-N-M)
    - acceptance_criteria:  [str]   (Expected: lines); omit se vazio
    - out_of_scope:         [str]   (not extracted; source em plans atuais e
                                     top-level, nao per-task — omitted)
    - files_relevant:       [str]   (Files block paths); omit se vazio
    - expected_outputs:     [str]   (Create paths do Files block); omit se vazio
    - guardrails:           [str]   (not extracted; omitted — Bernard
                                     adiciona via task set-dispatch-payload
                                     merge quando necessario)
    - depends_on:           [str]   (not auto-inferred; omitted — plans
                                     nao declaram deps explicitas; Bernard
                                     adiciona manual se quiser enforcement
                                     informal)

    Guardrail Phase 5 #2: sem inventar campos novos. Ordem/shape estavel.
    """
    files = parsed_task.get("files") or []
    ac = parsed_task.get("expected") or []
    goal = _first_paragraph(parsed_task["body"]) or parsed_task["task_subject"]
    files_relevant = [f["path"] for f in files]
    expected_outputs = [f["path"] for f in files if f.get("op") == "Create"]

    payload: Dict[str, Any] = {
        "goal": goal,
        "spec_refs": list(spec_refs),
        "spec_ref": spec_refs[0] if spec_refs else None,
        "plan_ref": plan_ref_display,
        "plan_anchor": _task_anchor(parsed_task["task_num"]),
    }
    if ac:
        payload["acceptance_criteria"] = ac
    if files_relevant:
        payload["files_relevant"] = files_relevant
    if expected_outputs:
        payload["expected_outputs"] = expected_outputs
    # out_of_scope, guardrails, depends_on: omitidos (source vazio ou nao
    # parseado). Schema aceita ausencia. Agents consumidores devem tratar
    # key-missing como "no info", nao como lista vazia implicita.
    return payload


def _build_task_entry(
    parsed_task: Dict[str, Any],
    provisional_id: str,
    header: Dict[str, Any],
    resolved_project: str,
    target_sprint: str,
    spec_refs: List[str],
    plan_ref_display: str,
    blocked_by_labels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    wave_ref = f"{header['wave_ref_root']}/Phase-{parsed_task['phase_num']}"
    dispatch_payload = _build_dispatch_payload(
        parsed_task, spec_refs, plan_ref_display,
    )
    # Wave-6: include blocked_by_labels (may be empty list)
    dispatch_payload["blocked_by_labels"] = list(blocked_by_labels or [])
    return {
        "provisional_id": provisional_id,
        "label": f"Task {parsed_task['task_num']}",
        "title": parsed_task["task_subject"],
        "description": _first_paragraph(parsed_task["body"])
                       or parsed_task["task_subject"],
        "status_on_create": "backlog",
        "project": resolved_project,
        "epic_id": header["epic_id"],
        "wave_ref": wave_ref,
        "sprint_target": target_sprint,
        "dispatch_payload": dispatch_payload,
    }


def build_proposal(
    plan_path: Path,
    cli_project_override: Optional[str],
    cli_target_sprint: str,
    actor: str = "bernard",
    dependency_mode: str = "hybrid",
) -> Dict[str, Any]:
    """Entry-point: le plan, parseia, resolve projects + deps, monta proposal.

    Wave-6 (scrum-master-v2):
    - `dependency_mode` (phase-sequence | explicit | hybrid; default hybrid)
      feeds dependency_resolver.resolve().
    - Each task entry gets `label` ("Task N.M") + dispatch_payload
      gains `blocked_by_labels`.
    - Proposal top-level gains `dependency_mode` + `computed_deps`.
    - schema_version bumped 1 -> 2.
    - gate_check.check_proposal() runs after build; raises
      GateCheckFailedError if any task is missing spec_ref/spec_refs
      or acceptance_criteria.

    Raises: parser_lib.ParseError, projects_lib.AmbiguousProjectError,
            projects_lib.UnknownProjectError,
            dependency_resolver.CycleDetectedError, ValueError,
            gate_check.GateCheckFailedError.
    """
    text = parser_lib.load_plan(plan_path)
    summary = parser_lib.parse_plan_summary(text)

    # Project resolution (raises se ambiguo/unknown sem override)
    proj_map, proj_warnings = projects_lib.resolve_all_tasks(
        summary["tasks"], summary["header"],
        cli_override=cli_project_override,
        validate_against_canonical=True,
    )

    # Wave-6: resolve deps before building entries.
    resolver_tasks = [
        {
            "label": f"Task {pt['task_num']}",
            "phase_num": pt["phase_num"],
            "depends": parser_lib.extract_depends(pt["body"]),
        }
        for pt in summary["tasks"]
    ]
    computed_deps = dependency_resolver.resolve(
        resolver_tasks, mode=dependency_mode,
    )

    spec_refs = list(summary["header"].get("specs_canonicas") or [])
    # Inclui o proprio plan como ref (display-friendly)
    plan_ref_display = str(plan_path).replace(f"{Path.home()}/", "~/")

    tasks_out: List[Dict[str, Any]] = []
    for i, pt in enumerate(summary["tasks"], start=1):
        provisional = f"P-{i:03d}"
        resolved = proj_map[pt["task_num"]]
        label = f"Task {pt['task_num']}"
        tasks_out.append(_build_task_entry(
            pt, provisional, summary["header"], resolved,
            cli_target_sprint, spec_refs, plan_ref_display,
            blocked_by_labels=computed_deps.get(label, []),
        ))

    proposal: Dict[str, Any] = {
        "schema_version": 2,
        "proposal_id": _make_proposal_id(plan_path),
        "plan_ref": plan_ref_display,
        "plan_sha": _plan_sha(plan_path),
        "sprint_goal": summary["header"].get("goal") or "",
        "target_sprint": cli_target_sprint,
        "target_project": summary["header"].get("project"),
        "epic_id": summary["header"]["epic_id"],
        "wave_ref_root": summary["header"]["wave_ref_root"],
        "total_tasks": len(tasks_out),
        "total_phases": summary["total_phases"],
        "dependency_mode": dependency_mode,
        "computed_deps": computed_deps,
        "tasks": tasks_out,
        "state": {
            "proposed_at": store.now_iso(),
            "proposed_by": actor,
            "accepted_at": None,
            "accepted_by": None,
            "rejected_at": None,
            "rejected_reason": None,
            "materialized_task_ids": None,
        },
    }
    if proj_warnings:
        proposal["_warnings"] = list(proj_warnings)

    # Wave-6 gate self-check (fail-fast antes de submit).
    gate_check.check_proposal(proposal)

    return proposal
