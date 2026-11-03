"""Project derivation: deterministica, 3 rules, erro em ambiguidade.

Ordem fixa (primeira que bate vence):
1. plan-level `Project:` explicit (single) -> todas tasks = X.
   plan-level `Projects:` multi -> NAO seta; per-task resolution.
2. Path map canonico aplicado aos paths do `**Files:**` block da task:
   - Exactly 1 project resolvido -> task.project = X.
   - Multiple projects OU zero -> task sem project; cai no passo 3.
3. `--project-override <nome>`: aplica X a todas tasks nao-resolvidas;
   emite warning. Sem override, erro AMBIGUOUS_PROJECT com listing
   dos ids afetados.

Zero fallback silencioso, zero heuristica "mais provavel".
"""

from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


# Mapa canonico path prefix -> project name.
# Ordem matters: mais especifico antes.
# Suporta paths ~-expanded e absolutos.
_RAW_MAP: List[Tuple[str, str]] = [
    (f"{Path.home()}/.openclaw/", "openclaw"),
    ("~/.openclaw/", "openclaw"),
    (f"{Path.home()}/bevox-knowledge/", "bevox-knowledge"),
    ("~/bevox-knowledge/", "bevox-knowledge"),
    (f"{Path.home()}/code/mission-control/", "mission-control"),
    (f"{Path.home()}/code/vox/", "vox"),
    (f"{Path.home()}/code/bevox/bevox-backend/", "bevox-backend"),
    (f"{Path.home()}/code/bevox/bevox-harness/", "bevox-harness"),
    (f"{Path.home()}/code/bevox/bevox-mobile/", "bevox-mobile"),
    (f"{Path.home()}/code/bevox/bevox-web/", "bevox-web"),
]


def project_from_path(path: str) -> Optional[str]:
    """Normaliza path e retorna project ou None se nao mapeado.

    Testa tanto o path literal quanto a versao ~-expanded.
    """
    raw = path.strip()
    expanded = str(Path(raw).expanduser()) if raw.startswith("~") else raw
    for prefix, proj in _RAW_MAP:
        if raw.startswith(prefix) or expanded.startswith(prefix):
            return proj
    return None


def projects_from_task_paths(task_files: List[dict]) -> Set[str]:
    """Retorna set de projects resolvidos dos paths da task.

    Paths nao-mapeados sao ignorados (nao adicionam ao set, nao erram).
    """
    out: Set[str] = set()
    for f in task_files:
        proj = project_from_path(f.get("path", ""))
        if proj is not None:
            out.add(proj)
    return out


def resolve_task_project(
    task_files: List[dict],
    plan_project: Optional[str],
    plan_projects: Optional[List[str]],
    cli_override: Optional[str],
) -> Tuple[Optional[str], List[str]]:
    """Resolve project de UMA task. Returns (project | None, warnings).

    None como resultado significa: ambiguidade/sem-resolucao. Caller
    decide se dispara AMBIGUOUS_PROJECT (quando sem cli_override) ou
    aplica override.

    NAO faz fallback silencioso. Ordem:
    1. plan_project single -> always wins.
    2. path resolution single -> wins.
    3. path resolution ambiguous OU zero -> cli_override aplica (com
       warning) ou None.
    """
    warnings: List[str] = []

    # Rule 1: plan-level single wins
    if plan_project is not None:
        return plan_project, warnings

    # Rule 2: path resolution
    projs = projects_from_task_paths(task_files)
    if len(projs) == 1:
        return projs.pop(), warnings

    # Rule 3: cli override (nao resolvido por 1+2)
    if cli_override is not None:
        if len(projs) > 1:
            warnings.append(
                f"project_override_applied: resolved_from_paths="
                f"{sorted(projs)} -> override='{cli_override}'"
            )
        else:
            # zero paths reconhecidos
            warnings.append(
                f"project_override_applied: no path resolution -> "
                f"override='{cli_override}'"
            )
        return cli_override, warnings

    # Fall through: None (caller trata como AMBIGUOUS_PROJECT)
    return None, warnings


def known_projects() -> Set[str]:
    """Le `projects.yml` do kanban-tasks.

    Zero deps: parser simples de flat YAML list (`- item`).
    """
    path = Path(f"{Path.home()}/.openclaw/kanban-tasks/projects.yml")
    if not path.exists():
        return set()
    out: Set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("projects:"):
            continue
        if line.startswith("- "):
            out.add(line[2:].strip().strip('"').strip("'"))
    return out


class AmbiguousProjectError(Exception):
    """Raised quando resolucao nao inequivoca e sem override.

    Carrega `ambiguous_tasks` com ids + info diagnostico pra mensagem util.
    """

    def __init__(
        self,
        ambiguous_tasks: List[Dict[str, object]],
    ):
        self.ambiguous_tasks = ambiguous_tasks
        preview = ambiguous_tasks[:5]
        remainder = len(ambiguous_tasks) - len(preview)
        lines = [
            f"{len(ambiguous_tasks)} tasks sem project resolvido:",
        ]
        for t in preview:
            paths_sample = t.get("paths_sample") or []
            resolved = t.get("paths_resolved") or []
            lines.append(
                f"  - Task {t.get('task_num')} ({t.get('task_subject', '')[:40]})"
                f" paths={paths_sample} resolved={sorted(resolved)}"
            )
        if remainder > 0:
            lines.append(f"  ... ({remainder} more)")
        lines.append(
            "Adicione `**Project:**` ou `**Projects:**` no header do "
            "plan, ou use --project-override <nome>."
        )
        super().__init__("\n".join(lines))


class UnknownProjectError(Exception):
    """Raised quando um project resolvido nao esta em projects.yml canonico."""

    def __init__(self, unknown: Set[str]):
        self.unknown = unknown
        super().__init__(
            f"projects nao listados em ~/.openclaw/kanban-tasks/projects.yml: "
            f"{sorted(unknown)}. Rode `~/.openclaw/kanban-tasks/cli.sh project "
            f"add <nome>` pra cada um antes de re-invocar."
        )


def resolve_all_tasks(
    parsed_tasks: List[dict],
    header: dict,
    cli_override: Optional[str],
    validate_against_canonical: bool = True,
) -> Tuple[Dict[str, str], List[str]]:
    """Resolve project pra TODAS as tasks do plan.

    Returns: (task_num -> project, warnings list).

    Raises:
    - AmbiguousProjectError se 1+ tasks sem project resolvido e sem
      cli_override.
    - UnknownProjectError se algum project resolvido (via rule 1/2/3)
      nao existe em `projects.yml` canonico (se
      validate_against_canonical=True).
    """
    plan_project = header.get("project")
    plan_projects = header.get("projects")
    warnings: List[str] = []
    resolved_map: Dict[str, str] = {}
    ambiguous: List[Dict[str, object]] = []

    for t in parsed_tasks:
        task_files = t.get("files") or []
        # If called from proposer, files ja extraidos; se vier de
        # parse_plan_summary, tambem tem 'files' inline.
        proj, ws = resolve_task_project(
            task_files, plan_project, plan_projects, cli_override,
        )
        warnings.extend(ws)
        if proj is None:
            # Diagnostic info
            resolved_set = projects_from_task_paths(task_files)
            ambiguous.append({
                "task_num": t.get("task_num"),
                "task_subject": t.get("task_subject"),
                "paths_sample": [f.get("path") for f in task_files[:3]],
                "paths_resolved": sorted(resolved_set),
            })
        else:
            resolved_map[t["task_num"]] = proj

    if ambiguous:
        raise AmbiguousProjectError(ambiguous)

    if validate_against_canonical:
        known = known_projects()
        if known:  # se projects.yml vazio/ausente, skip
            unknown = {p for p in resolved_map.values() if p not in known}
            if unknown:
                raise UnknownProjectError(unknown)

    return resolved_map, warnings
