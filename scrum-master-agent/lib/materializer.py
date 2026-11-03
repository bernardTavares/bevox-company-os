"""Materializer: accept -> cria tasks reais no kanban-tasks.

Guardrails Phase 7:

1. Preflight completo ANTES de mutar qualquer task. Se QUALQUER check
   falhar, zero side effect no kanban. Checks:
   - proposal pending (not accepted, rejected, partial)
   - plan drift (plan_sha atual vs salvo)
   - target_sprint resolve no kanban state
   - todos os projects em projects.yml canonico
   - todos os titles non-empty
   - todos os dispatch_payloads com shape valido (keys permitidas)

2. accepted_at SO no fim do caminho feliz. Durante a materializacao,
   nao escrevemos nada na proposal. Se tudo passar, no final escrevemos
   accepted_at + accepted_by + materialized_task_ids.

3. Falha no meio = estado PARTIAL explicito. Proposal recebe:
   - partial_at, partial_by
   - materialized_task_ids (ids ja criados ate falhar)
   - partial_failure: {provisional_id, step, error}
   Estado partial BLOQUEIA accept subsequente (PROPOSAL_PARTIALLY_MATERIALIZED).
   Bernard decide: arquiva tasks criadas + re-propoe, OU manual cleanup.

4. Test hook pra simular falha parcial: env `SCRUM_MASTER_FAIL_AT=<idx>`
   (0-based) raises MaterializerError antes de criar a task de indice N.
   Nao usado em producao real; documentado aqui pra auditoria.
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import parser as parser_lib
from . import projects as projects_lib
from . import proposer as proposer_lib
from . import store


KANBAN_CLI = Path(f"{Path.home()}/.openclaw/kanban-tasks/cli.sh")
KANBAN_STATE = Path(f"{Path.home()}/.openclaw/kanban-tasks/state.json")

# Shape fixo do dispatch_payload (mesmo set usado no proposer)
_DISPATCH_PAYLOAD_REQUIRED = {"goal", "spec_refs", "plan_ref", "plan_anchor"}
_DISPATCH_PAYLOAD_ALLOWED = _DISPATCH_PAYLOAD_REQUIRED | {
    "spec_ref", "acceptance_criteria", "out_of_scope", "files_relevant",
    "expected_outputs", "guardrails", "depends_on", "blocked_by_labels",
}


class MaterializerError(Exception):
    def __init__(self, code: str, detail: str, partial: bool = False):
        self.code = code
        self.detail = detail
        self.partial = partial
        super().__init__(f"{code}: {detail}")


# =================== Preflight ===================

def _check_proposal_state(proposal: Dict[str, Any]) -> None:
    state = proposal.get("state") or {}
    if state.get("accepted_at"):
        raise MaterializerError(
            "PROPOSAL_ALREADY_ACCEPTED",
            f"ja aceita em {state['accepted_at']} por "
            f"{state.get('accepted_by', '?')}",
        )
    if state.get("rejected_at"):
        raise MaterializerError(
            "PROPOSAL_ALREADY_REJECTED",
            f"rejeitada em {state['rejected_at']} por "
            f"{state.get('rejected_by', '?')} (reason: "
            f"{state.get('reject_reason', '?')})",
        )
    if state.get("partial_at"):
        pf = state.get("partial_failure") or {}
        mats = state.get("materialized_task_ids") or []
        raise MaterializerError(
            "PROPOSAL_PARTIALLY_MATERIALIZED",
            f"materializacao interrompida em {state['partial_at']} por "
            f"{state.get('partial_by', '?')}: falha em "
            f"{pf.get('provisional_id', '?')}/{pf.get('step', '?')} "
            f"({pf.get('error', '?')[:80]}). "
            f"Tasks criadas: {mats}. "
            f"Accept retry bloqueado pra evitar duplicacao. "
            f"Arquive manualmente ({', '.join(mats)}) e crie nova proposal.",
        )


def _check_plan_drift(proposal: Dict[str, Any], force: bool) -> List[str]:
    """Retorna warnings; raises PLAN_DRIFT se mudou e sem force."""
    warnings: List[str] = []
    plan_ref = proposal.get("plan_ref", "").replace("~/", f"{Path.home()}/")
    plan_path = Path(plan_ref).expanduser()
    saved = proposal.get("plan_sha")
    if saved is None:
        warnings.append(
            "plan_sha=null (plan nao esta sob git); drift check skipped"
        )
        return warnings
    if not plan_path.exists():
        raise MaterializerError(
            "PLAN_NOT_FOUND",
            f"plan_ref '{plan_ref}' no proposal nao existe mais",
        )
    current = proposer_lib._plan_sha(plan_path)
    if current != saved:
        if not force:
            raise MaterializerError(
                "PLAN_DRIFT",
                f"plan_sha mudou: saved={saved} atual={current}. "
                f"Use --force-plan-drift ou re-proponha.",
            )
        warnings.append(
            f"plan_drift_forced: saved={saved} atual={current}"
        )
    return warnings


def _resolve_target_sprint(state: dict, target: str, project: str) -> str:
    """Resolve sprint_target ('current'|'next'|literal) per-project.

    Aliases requerem project. Raise ValueError com NO_SPRINT_FOR_PROJECT
    se projeto nao tem o sprint pedido.
    """
    if target in ("current", "next"):
        for sp in state["sprints"]:
            if sp["state"] == target and sp.get("project") == project:
                return sp["id"]
        raise ValueError(
            f"NO_SPRINT_FOR_PROJECT: project={project} target={target}; "
            f"rode `kanban-tasks/cli.sh sprint bootstrap`"
        )
    # literal id: lookup direto
    for sp in state["sprints"]:
        if sp["id"] == target:
            return target
    raise ValueError(f"sprint not found: {target}")


def _check_target_sprint(target: str, project: str, state: dict) -> str:
    """Resolve target_sprint no kanban state per-project. Retorna sprint_id real."""
    try:
        return _resolve_target_sprint(state, target, project)
    except ValueError as e:
        raise MaterializerError("TARGET_SPRINT_NOT_FOUND", str(e))


def _check_projects(tasks: List[Dict[str, Any]]) -> None:
    known = projects_lib.known_projects()
    if not known:
        raise MaterializerError(
            "PROJECTS_YML_MISSING",
            "kanban-tasks/projects.yml ausente ou vazio. Nao da pra validar.",
        )
    required = {t["project"] for t in tasks}
    missing = required - known
    if missing:
        raise MaterializerError(
            "UNKNOWN_PROJECT",
            f"projects do proposal nao estao em projects.yml: "
            f"{sorted(missing)}. Rode `kanban-tasks/cli.sh project add "
            f"<nome>` pra cada um.",
        )


def _check_payload_shape(tasks: List[Dict[str, Any]]) -> None:
    for t in tasks:
        dp = t.get("dispatch_payload") or {}
        if not isinstance(dp, dict):
            raise MaterializerError(
                "INVALID_PAYLOAD",
                f"task {t.get('provisional_id')}: dispatch_payload nao "
                f"eh dict (got {type(dp).__name__})",
            )
        keys = set(dp.keys())
        missing = _DISPATCH_PAYLOAD_REQUIRED - keys
        invented = keys - _DISPATCH_PAYLOAD_ALLOWED
        if missing:
            raise MaterializerError(
                "INVALID_PAYLOAD",
                f"task {t.get('provisional_id')}: dispatch_payload missing "
                f"required keys {sorted(missing)}",
            )
        if invented:
            raise MaterializerError(
                "INVALID_PAYLOAD",
                f"task {t.get('provisional_id')}: dispatch_payload has "
                f"unknown keys {sorted(invented)} (allowed: "
                f"{sorted(_DISPATCH_PAYLOAD_ALLOWED)})",
            )


def _check_titles(tasks: List[Dict[str, Any]]) -> None:
    for t in tasks:
        title = (t.get("title") or "").strip()
        if not title:
            raise MaterializerError(
                "INVALID_TITLE",
                f"task {t.get('provisional_id')}: title vazio ou so whitespace",
            )


def _load_kanban_state() -> dict:
    """Le kanban state do disco. Levanta MaterializerError em falha."""
    if not KANBAN_STATE.exists():
        raise MaterializerError(
            "KANBAN_STATE_MISSING",
            f"{KANBAN_STATE} nao existe. Rode `kanban-tasks/cli.sh "
            f"sprint init` primeiro.",
        )
    try:
        return json.loads(KANBAN_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise MaterializerError(
            "KANBAN_STATE_INVALID", f"falha lendo {KANBAN_STATE}: {e}",
        )


def preflight(
    proposal: Dict[str, Any], force_plan_drift: bool,
) -> Dict[str, Any]:
    """Roda todos os checks. Retorna {'warnings': [...], 'resolved_sprint': str,
    'resolved_sprint_by_project': Dict[str, str]}.

    Levanta MaterializerError na primeira falha. Zero mutacao no kanban
    ou proposal. Sprint resolve e per-project (schema v4): cada projeto
    resolve seu proprio 'current'/'next'.
    """
    _check_proposal_state(proposal)
    warnings = _check_plan_drift(proposal, force_plan_drift)
    tasks = proposal.get("tasks") or []
    _check_projects(tasks)
    _check_titles(tasks)
    _check_payload_shape(tasks)

    target = proposal["target_sprint"]
    state = _load_kanban_state()
    projects_in_proposal = {t["project"] for t in tasks} if tasks else set()

    resolved_sprint_by_project: Dict[str, str] = {}
    for proj in sorted(projects_in_proposal):
        resolved_sprint_by_project[proj] = _check_target_sprint(target, proj, state)

    # resolved_sprint: primeiro projeto resolvido (compat) ou target literal
    if resolved_sprint_by_project:
        first_proj = sorted(projects_in_proposal)[0]
        resolved_sprint = resolved_sprint_by_project[first_proj]
    else:
        # proposal sem tasks: fallback ao comportamento antigo
        resolved_sprint = target

    return {
        "warnings": warnings,
        "resolved_sprint": resolved_sprint,
        "resolved_sprint_by_project": resolved_sprint_by_project,
    }


# =================== Kanban CLI wrappers ===================

def _run_kanban(args: List[str], actor: str) -> Dict[str, Any]:
    """Invoca cli.sh kanban com --json + --actor. Retorna payload parseado.

    Raises MaterializerError em non-zero exit ou JSON invalido.
    """
    cmd = [str(KANBAN_CLI)] + args + ["--json", "--actor", actor]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=False, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise MaterializerError(
            "KANBAN_CLI_TIMEOUT",
            f"subprocess {' '.join(cmd[:4])} falhou: {e}",
        )
    if result.returncode != 0:
        raise MaterializerError(
            "KANBAN_CLI_FAILED",
            f"{' '.join(cmd)} exit={result.returncode}; "
            f"stderr={result.stderr.strip()[:200]}; "
            f"stdout={result.stdout.strip()[:200]}",
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise MaterializerError(
            "KANBAN_CLI_BAD_JSON",
            f"stdout nao eh JSON: err={e}, stdout={result.stdout[:200]}",
        )


def _materialize_one(
    task: Dict[str, Any],
    prov_to_real: Dict[str, str],
    target_sprint: str,
    make_ready: bool,
    actor: str,
    label_to_real: Optional[Dict[str, str]] = None,
) -> str:
    """Cria task real + set-payload + opcional move ready. Retorna task_id real.

    Wave-4 gate (E10/OH wave-4, 2026-04-22): `kanban-tasks task add` agora
    exige `--payload` com `spec_ref` + `acceptance_criteria`. Passamos um
    payload minimo no add (suficiente pra satisfazer o gate) + full payload
    com `depends_on` resolvido no set-dispatch-payload subsequente.

    Wave-8 fix (2026-04-22): resolve `blocked_by_labels` via label_to_real
    incremental map + chama `task set-blocked-by` pra popular wave-5
    task-record blocked_by (source of truth pra move-to-ready gate +
    auto-release hooks). Requer caller (materialize) manter label_to_real.
    """
    if label_to_real is None:
        label_to_real = {}
    full_payload = dict(task.get("dispatch_payload") or {})

    # Wave-4: payload minimo pra satisfazer gate no task add.
    # Scrum-master usa chave `spec_refs` (plural, list; ver lib/proposer.py)
    # enquanto o gate wave-4 checa `spec_ref` (singular — aceita string OR list).
    # Fallback preserva compat sem tocar gate/policy.
    spec_ref_val = full_payload.get("spec_ref")
    if spec_ref_val is None:
        spec_ref_val = full_payload.get("spec_refs")
    minimal_payload = {
        "spec_ref": spec_ref_val,
        "acceptance_criteria": full_payload.get("acceptance_criteria"),
    }

    # task add
    add_args = [
        "task", "add", task["title"],
        "--sprint", target_sprint,
        "--project", task["project"],
        "--epic", task["epic_id"],
        "--wave", task["wave_ref"],
        "--payload", json.dumps(minimal_payload, ensure_ascii=False),
    ]
    if task.get("description"):
        add_args += ["--description", task["description"]]
    res = _run_kanban(add_args, actor=actor)
    real_id = res.get("task", {}).get("id")
    if not real_id:
        raise MaterializerError(
            "KANBAN_ADD_NO_ID",
            f"task add nao retornou id: res={res}",
        )
    prov_to_real[task["provisional_id"]] = real_id
    label_to_real[task.get("label", task["provisional_id"])] = real_id

    # Wave-8 fix: resolve blocked_by_labels -> IDs reais + chama
    # task set-blocked-by (wave-5 task-record source of truth)
    pred_labels = full_payload.get("blocked_by_labels") or []
    resolved_blocked_by = [
        label_to_real[pl] for pl in pred_labels if pl in label_to_real
    ]
    if resolved_blocked_by:
        preds_csv = ",".join(resolved_blocked_by)
        _run_kanban(
            ["task", "set-blocked-by", real_id, "--preds", preds_csv],
            actor=actor,
        )
    full_payload["blocked_by"] = resolved_blocked_by

    # Resolve depends_on provisional -> real (se presente)
    payload = full_payload
    if isinstance(payload.get("depends_on"), list):
        resolved: List[str] = []
        for d in payload["depends_on"]:
            resolved.append(prov_to_real.get(d, d))
        payload["depends_on"] = resolved

    # set-dispatch-payload: replace com payload completo (inclui depends_on
    # resolvido). Sobrescreve o minimal_payload do add — comportamento default
    # de set-dispatch-payload e `replace`.
    _run_kanban(
        ["task", "set-dispatch-payload", real_id,
         "--payload", json.dumps(payload, ensure_ascii=False)],
        actor=actor,
    )

    # Wave-8: --ready só promove tasks sem preds (root tasks). Tasks com
    # blocked_by esperam auto-release do wave-5 hook quando upstream done.
    if make_ready and not resolved_blocked_by:
        _run_kanban(["task", "move", real_id, "ready"], actor=actor)

    return real_id


# =================== wave-6: topological + materialize_proposal ===================

def _topological_order(
    computed_deps: Dict[str, List[str]], task_labels: List[str],
) -> List[str]:
    """Kahn's algorithm. Retorna ordem topologica de labels.

    Pressupoe grafo sem ciclos (resolver ja detectou). Se por algum motivo
    houver, detecta via tamanho do output e raise AssertionError.
    """
    from collections import defaultdict, deque

    in_degree = {l: 0 for l in task_labels}
    forward: Dict[str, List[str]] = defaultdict(list)  # pred -> [dep, ...]
    for label, preds in computed_deps.items():
        if label not in in_degree:
            continue
        for p in preds:
            if p in in_degree:
                forward[p].append(label)
                in_degree[label] += 1

    queue = deque([l for l in task_labels if in_degree.get(l, 0) == 0])
    order: List[str] = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for dep in forward[node]:
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                queue.append(dep)

    assert len(order) == len(task_labels), (
        f"Cycle survived resolver detection: order={order}, "
        f"labels={task_labels}"
    )
    return order


def materialize_proposal(
    proposal: Dict[str, Any],
    target_sprint: str,
    make_ready: bool,
    actor: str,
) -> List[Dict[str, Any]]:
    """Materializa proposal inteira (wave-6: 2-step + topological).

    .. warning:: SINGLE-PROJECT ONLY (post wave-4 schema v4).
        Esta função usa um único ``target_sprint`` aplicado a todas as tasks.
        Para multi-project proposals, use ``materialize()`` (production
        entrypoint), que resolve sprint per-task via project. Chamar aqui
        com uma proposal multi-project levanta ValueError.

    Fluxo:
      1. Resolve ordem topologica via computed_deps (fallback pra ordem
         de aparicao se schema_version antigo sem labels/computed_deps).
      2. Para cada label em ordem:
         a. task add com payload minimo (spec_ref + acceptance_criteria)
            -> wave-4 gate satisfeito.
         b. Resolve blocked_by_labels -> task_ids reais via label_to_real
            mapping incremental.
         c. task set-dispatch-payload com full payload incluindo
            blocked_by resolvido -> wave-5 gate valida ciclo + pred
            existence.
         d. Optional: move ready.

    Returns lista de {"label", "task_id", "preds"}.
    """
    # Guard: single-project assumption — multi-project proposals must use
    # materialize() which resolves sprint per-task via project field.
    tasks_list = proposal.get("tasks") or []
    projects_in_tasks = {t.get("project") for t in tasks_list if t.get("project")}
    if len(projects_in_tasks) > 1:
        raise ValueError(
            f"materialize_proposal SINGLE_PROJECT_ONLY: proposal has tasks from "
            f"{len(projects_in_tasks)} projects ({sorted(projects_in_tasks)}). "
            f"Use materialize() for multi-project proposals."
        )

    computed_deps = proposal.get("computed_deps") or {}
    tasks = proposal.get("tasks") or []

    # Backward-compat fallback: if no label field OR no computed_deps,
    # preserve order-by-appearance (proposal v1 shape).
    all_have_labels = all("label" in t for t in tasks)
    if not all_have_labels or not computed_deps:
        order_iter = [t.get("label") or t.get("provisional_id") for t in tasks]
        tasks_by_label = {
            (t.get("label") or t.get("provisional_id")): t for t in tasks
        }
    else:
        tasks_by_label = {t["label"]: t for t in tasks}
        labels = list(tasks_by_label.keys())
        order_iter = _topological_order(computed_deps, labels)

    label_to_real: Dict[str, str] = {}
    prov_to_real: Dict[str, str] = {}
    created: List[Dict[str, Any]] = []

    for label in order_iter:
        task = tasks_by_label[label]
        full_dp = dict(task.get("dispatch_payload") or {})
        pred_labels = full_dp.pop("blocked_by_labels", [])

        # Minimal payload for task add (wave-4 gate satisfaction)
        spec_ref_val = full_dp.get("spec_ref") or full_dp.get("spec_refs")
        minimal_payload = {
            "spec_ref": spec_ref_val,
            "acceptance_criteria": full_dp.get("acceptance_criteria"),
        }

        add_args = [
            "task", "add", task["title"],
            "--sprint", target_sprint,
            "--project", task["project"],
            "--epic", task["epic_id"],
            "--wave", task["wave_ref"],
            "--payload", json.dumps(minimal_payload, ensure_ascii=False),
        ]
        if task.get("description"):
            add_args += ["--description", task["description"]]
        res = _run_kanban(add_args, actor=actor)
        real_id = res.get("task", {}).get("id")
        if not real_id:
            raise MaterializerError(
                "KANBAN_ADD_NO_ID",
                f"task add nao retornou id: label={label} res={res}",
            )
        label_to_real[label] = real_id
        prov_to_real[task.get("provisional_id", label)] = real_id

        # Resolve blocked_by_labels -> task_ids reais
        resolved_blocked_by = [
            label_to_real[pl] for pl in pred_labels if pl in label_to_real
        ]
        full_dp["blocked_by"] = resolved_blocked_by

        # Wave-8 fix: popula wave-5 task-record blocked_by via CLI
        # (source of truth pra gate de move-to-ready + auto-release hooks)
        if resolved_blocked_by:
            preds_csv = ",".join(resolved_blocked_by)
            _run_kanban(
                ["task", "set-blocked-by", real_id, "--preds", preds_csv],
                actor=actor,
            )

        # Legacy depends_on resolution preserved
        if isinstance(full_dp.get("depends_on"), list):
            full_dp["depends_on"] = [
                prov_to_real.get(d, d) for d in full_dp["depends_on"]
            ]

        _run_kanban(
            ["task", "set-dispatch-payload", real_id,
             "--payload", json.dumps(full_dp, ensure_ascii=False)],
            actor=actor,
        )

        if make_ready:
            _run_kanban(["task", "move", real_id, "ready"], actor=actor)

        created.append({
            "label": label, "task_id": real_id,
            "preds": resolved_blocked_by,
        })

    return created


# =================== Test-only hook ===================

def _check_fail_hook(index: int, provisional_id: str) -> None:
    """Test hook: SCRUM_MASTER_FAIL_AT=<idx> forca falha antes de criar
    task de indice <idx> (0-based). Nao e usado em producao; existe pra
    auditar o comportamento de falha parcial via smoke.
    """
    fail_at = os.environ.get("SCRUM_MASTER_FAIL_AT")
    if fail_at is None:
        return
    try:
        target = int(fail_at)
    except ValueError:
        return
    if index == target:
        raise MaterializerError(
            "TEST_INJECTED_FAILURE",
            f"simulated failure before task {provisional_id} "
            f"(index {index}) via SCRUM_MASTER_FAIL_AT",
        )


# =================== Entry-point ===================

def materialize(
    proposal: Dict[str, Any],
    make_ready: bool,
    force_plan_drift: bool,
    actor: str,
) -> Dict[str, Any]:
    """Accept flow completo.

    Pipeline:
      1. preflight (checks sem mutacao)
      2. materializar tasks sequencialmente
      3. se tudo OK: set accepted_at + accepted_by + materialized_task_ids
      4. se erro no meio: set partial_at + partial_by + partial_failure
         + materialized_task_ids parcial. Raises MaterializerError com
         partial=True.

    Retorna summary em caso de sucesso.
    """
    pre = preflight(proposal, force_plan_drift=force_plan_drift)
    sprint_by_project = pre["resolved_sprint_by_project"]
    warnings = list(pre["warnings"])

    prov_to_real: Dict[str, str] = {}
    label_to_real: Dict[str, str] = {}
    created: List[str] = []
    tasks = proposal.get("tasks") or []

    for idx, task in enumerate(tasks):
        try:
            _check_fail_hook(idx, task["provisional_id"])
            # resolve sprint per-project (schema v4)
            project = task["project"]
            task_sprint = sprint_by_project.get(project, pre["resolved_sprint"])
            real_id = _materialize_one(
                task, prov_to_real, task_sprint, make_ready, actor,
                label_to_real=label_to_real,
            )
            created.append(real_id)
        except MaterializerError as e:
            # Falha parcial: marcar estado na proposal e reraise
            proposal["state"]["materialized_task_ids"] = list(created)
            proposal["state"]["partial_at"] = store.now_iso()
            proposal["state"]["partial_by"] = actor
            proposal["state"]["partial_failure"] = {
                "provisional_id": task["provisional_id"],
                "index": idx,
                "step": e.code,
                "error": e.detail,
            }
            store.update_proposal(proposal)
            raise MaterializerError(
                "PARTIAL_MATERIALIZATION",
                f"falha na task {idx + 1}/{len(tasks)} "
                f"({task['provisional_id']}): {e.code}: {e.detail[:120]}. "
                f"Criadas antes: {created}. Proposal marcada como partial. "
                f"Accept retry bloqueado; arquive manualmente e re-proponha.",
                partial=True,
            )
        except Exception as e:  # unknown — wrap como partial
            proposal["state"]["materialized_task_ids"] = list(created)
            proposal["state"]["partial_at"] = store.now_iso()
            proposal["state"]["partial_by"] = actor
            proposal["state"]["partial_failure"] = {
                "provisional_id": task["provisional_id"],
                "index": idx,
                "step": "UNEXPECTED",
                "error": str(e),
            }
            store.update_proposal(proposal)
            raise MaterializerError(
                "PARTIAL_MATERIALIZATION",
                f"falha inesperada na task {idx + 1}: {e}. "
                f"Criadas antes: {created}. Proposal marcada como partial.",
                partial=True,
            )

    # Caminho feliz: so aqui escrevemos accepted_at
    proposal["state"]["accepted_at"] = store.now_iso()
    proposal["state"]["accepted_by"] = actor
    proposal["state"]["materialized_task_ids"] = list(created)
    store.update_proposal(proposal)

    return {
        "ok": True,
        "proposal_id": proposal["proposal_id"],
        "resolved_sprint": pre["resolved_sprint"],
        "resolved_sprint_by_project": sprint_by_project,
        "materialized_task_ids": created,
        "total_materialized": len(created),
        "warnings": warnings,
    }
