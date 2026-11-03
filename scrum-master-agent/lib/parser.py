"""Parser do implementation plan (convencao superpowers:writing-plans).

Responsabilidade unica: extrair estrutura do plan markdown.
NAO infere nada da spec canonica (guardrail Phase 3).
NAO faz best-effort: plan mal-formado -> ParseError claro.

Elementos extraidos:
- Header: Goal (opcional), Epico (obrigatorio), Project/Projects (opcional),
  Tech Stack (opcional), Specs canonicas (opcional refs)
- Phases: `^## Phase N: Name`
- Tasks: `^### Task N.M: Subject`
- Files blocks: **Files:** + bullet Create/Modify/Test com path em backticks
- Steps: `- [ ] **Step N: description**`
- Expected lines: `^Expected: X`
- Refs: paths a arquivos em bevox-knowledge/35_specs/ ou 30_adr/

Regex + text parsing puro. Zero deps externas.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# =================== Exception ===================

class ParseError(Exception):
    """Plan malformado ou missing header obrigatorio."""

    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


# =================== Regex ===================

RE_HEADER_GOAL = re.compile(r"^\*\*Goal:\*\*\s*(.+?)$", re.MULTILINE)
RE_HEADER_EPICO = re.compile(r"^\*\*Epico:\*\*\s*(\S+)\s*$", re.MULTILINE)
RE_HEADER_PROJECT = re.compile(r"^\*\*Project:\*\*\s*(\S+)\s*$", re.MULTILINE)
RE_HEADER_PROJECTS = re.compile(r"^\*\*Projects:\*\*\s*(.+?)$", re.MULTILINE)
RE_HEADER_TECH_STACK = re.compile(
    r"^\*\*Tech Stack:\*\*\s*\n((?:^[-*].+\n)+)", re.MULTILINE,
)

RE_PHASE = re.compile(r"^##\s+Phase\s+(\d+):\s*(.+?)\s*$", re.MULTILINE)
RE_TASK = re.compile(r"^###\s+Task\s+(\d+)\.(\d+):\s*(.+?)\s*$", re.MULTILINE)

RE_FILES_BLOCK = re.compile(
    r"^\*\*Files:\*\*\s*\n((?:^-\s+.+\n)+)",
    re.MULTILINE,
)
RE_FILE_LINE = re.compile(
    r"^-\s+(Create|Modify|Test):\s*`([^`]+)`",
    re.MULTILINE,
)

RE_STEP = re.compile(
    r"^-\s+\[\s*[x ]?\s*\]\s+\*\*Step\s+(\d+):\s*([^*]+?)\*\*",
    re.MULTILINE,
)

RE_EXPECTED = re.compile(r"^Expected:\s*(.+?)$", re.MULTILINE)

# Refs: paths tipo `bevox-knowledge/35_specs/X.md` ou `bevox-knowledge/30_adr/Y.md`
# em backticks OU bullets.
RE_REF_PATH = re.compile(
    r"`(bevox-knowledge/(?:35_specs|30_adr|20_architecture)/[^\s`]+\.md)`"
)


# =================== Header ===================

def _header_region(text: str) -> str:
    """Retorna o trecho do plan antes do primeiro `^## Phase N:` heading.

    Header metadata (Goal, Epico, Project, Tech Stack, Specs canonicas)
    deve viver EXCLUSIVAMENTE no prelude. Evita capturar ocorrencias de
    `**Epico:**` ou `**Project:**` dentro de code blocks de Phases
    (ex: plan com exemplo embutido de outra plan).
    """
    m = RE_PHASE.search(text)
    return text[: m.start()] if m else text


def parse_header(text: str) -> Dict[str, Any]:
    """Parse header. Raises ParseError se Epico ausente ou malformado.

    Header eh buscado APENAS no trecho antes da primeira `## Phase N:`
    (prelude). Ocorrencias dentro de phases/code-blocks sao ignoradas.

    Returns: {
      'goal': str | None,
      'epic_id': str,        # ex 'E5'
      'wave_slug': str,      # ex 'F4-kanban-dev-lifecycle'
      'wave_ref_root': str,  # ex 'E5/F4-kanban-dev-lifecycle'
      'project': str | None, # `**Project:**` single
      'projects': [str] | None, # `**Projects:** a, b, c`
      'tech_stack': [str],   # linhas bullet do Tech Stack (optional)
      'specs_canonicas': [str], # refs paths (optional)
    }
    """
    out: Dict[str, Any] = {
        "goal": None, "epic_id": None, "wave_slug": None,
        "wave_ref_root": None, "project": None, "projects": None,
        "tech_stack": [], "specs_canonicas": [],
    }
    header_text = _header_region(text)
    m = RE_HEADER_GOAL.search(header_text)
    if m:
        out["goal"] = m.group(1).strip()

    m = RE_HEADER_EPICO.search(header_text)
    if not m:
        raise ParseError(
            "PLAN_MISSING_EPIC",
            "plan header deve ter `**Epico:** <epic-id>/<wave-slug>` "
            "(ex: `**Epico:** E5/F4-kanban-dev-lifecycle`). "
            "Adicione a linha no cabecalho do plan (antes da primeira "
            "`## Phase N:`).",
        )
    epico_raw = m.group(1).strip()
    if "/" not in epico_raw:
        raise ParseError(
            "PLAN_MISSING_EPIC",
            f"`**Epico:**` value '{epico_raw}' deve ter forma "
            f"`<epic-id>/<wave-slug>` (ex: `E5/F4-kanban-dev-lifecycle`). "
            f"Barra separadora ausente.",
        )
    epic_id, wave_slug = epico_raw.split("/", 1)
    if not epic_id or not wave_slug:
        raise ParseError(
            "PLAN_MISSING_EPIC",
            f"`**Epico:**` value '{epico_raw}' tem componente vazio "
            f"(epic_id='{epic_id}' wave_slug='{wave_slug}')",
        )
    out["epic_id"] = epic_id
    out["wave_slug"] = wave_slug
    out["wave_ref_root"] = epico_raw

    m = RE_HEADER_PROJECT.search(header_text)
    if m:
        out["project"] = m.group(1).strip()
    else:
        m = RE_HEADER_PROJECTS.search(header_text)
        if m:
            projs = [p.strip() for p in m.group(1).split(",") if p.strip()]
            out["projects"] = projs

    m = RE_HEADER_TECH_STACK.search(header_text)
    if m:
        block = m.group(1)
        out["tech_stack"] = [
            line.lstrip("- *").strip()
            for line in block.splitlines()
            if line.strip()
        ]

    # Refs canonicas: qualquer ocorrencia de ref-path no header prelude
    for ref_m in RE_REF_PATH.finditer(header_text):
        ref = ref_m.group(1)
        if ref not in out["specs_canonicas"]:
            out["specs_canonicas"].append(ref)
    return out


# =================== Phases + Tasks ===================

def parse_phases_and_tasks(text: str) -> List[Dict[str, Any]]:
    """Extrai tasks com Phase context. Raises ParseError se plan vazio.

    Returns: lista de dicts:
      {'phase_num': int, 'phase_name': str,
       'task_num': str (ex '1.1'), 'task_subject': str,
       'body': str (texto da task ate proxima task/phase/EOF),
       'offset': int}
    """
    phase_positions: List[Tuple[int, int, str]] = []
    for m in RE_PHASE.finditer(text):
        phase_positions.append((m.start(), int(m.group(1)), m.group(2).strip()))
    if not phase_positions:
        raise ParseError(
            "NO_PHASES_FOUND",
            "plan nao tem headings `^## Phase N:`. Verifique convencao "
            "do superpowers:writing-plans (ex: `## Phase 1: Setup`).",
        )

    task_positions: List[Tuple[int, int, int, str]] = []
    for m in RE_TASK.finditer(text):
        task_positions.append(
            (m.start(), int(m.group(1)), int(m.group(2)), m.group(3).strip()),
        )
    if not task_positions:
        raise ParseError(
            "NO_TASKS_FOUND",
            "plan nao tem headings `^### Task N.M:`. Verifique convencao "
            "do superpowers:writing-plans (ex: `### Task 1.1: Create foo`).",
        )

    all_boundaries = sorted(
        [p[0] for p in phase_positions]
        + [t[0] for t in task_positions]
        + [len(text)]
    )

    out: List[Dict[str, Any]] = []
    for offset, phase_n_decl, task_n_sub, subject in task_positions:
        # Boundary posterior mais proxima
        next_offset = len(text)
        for b in all_boundaries:
            if b > offset:
                next_offset = b
                break
        # Phase context: maior offset de phase com numero == phase_n_decl <= offset
        phase_name = ""
        phase_num_actual = phase_n_decl
        for p_off, p_num, p_name in phase_positions:
            if p_off < offset and p_num == phase_n_decl:
                phase_name = p_name
                phase_num_actual = p_num
        body = text[offset:next_offset].rstrip()
        out.append({
            "phase_num": phase_num_actual,
            "phase_name": phase_name,
            "task_num": f"{phase_n_decl}.{task_n_sub}",
            "task_subject": subject,
            "body": body,
            "offset": offset,
        })
    return out


# =================== Task extractors ===================

def extract_files_from_task(task_body: str) -> List[Dict[str, str]]:
    """Extrai **Files:** block da task. Returns [{'op', 'path'}, ...]."""
    m = RE_FILES_BLOCK.search(task_body)
    if not m:
        return []
    block = m.group(1)
    out: List[Dict[str, str]] = []
    for fm in RE_FILE_LINE.finditer(block):
        out.append({"op": fm.group(1), "path": fm.group(2).strip()})
    return out


def extract_expected_lines(task_body: str) -> List[str]:
    """Extrai `Expected: X` lines (acceptance criteria candidates)."""
    return [m.group(1).strip() for m in RE_EXPECTED.finditer(task_body)]


def extract_steps(task_body: str) -> List[Dict[str, Any]]:
    """Extrai Steps da task: `- [ ] **Step N: description**`.

    Returns: [{'step_num': int, 'description': str}, ...]
    """
    out: List[Dict[str, Any]] = []
    for m in RE_STEP.finditer(task_body):
        out.append({
            "step_num": int(m.group(1)),
            "description": m.group(2).strip(),
        })
    return out


# =================== High-level API ===================

def load_plan(plan_path: Path) -> str:
    """Le plan file. Raises ParseError PLAN_NOT_FOUND se ausente."""
    if not plan_path.exists():
        raise ParseError(
            "PLAN_NOT_FOUND",
            f"plan path '{plan_path}' nao encontrado",
        )
    return plan_path.read_text(encoding="utf-8")


def parse_plan_summary(text: str) -> Dict[str, Any]:
    """Parse completo. Returns summary com header + phases + tasks.

    Shape:
    {
      'header': {...},
      'phases': [{'phase_num', 'phase_name', 'task_count'}],
      'tasks': [{'task_num', 'task_subject', 'phase_num', 'phase_name',
                 'files_count', 'steps_count', 'expected_count',
                 'files', 'steps', 'expected'}],
      'total_phases': int,
      'total_tasks': int,
    }
    """
    header = parse_header(text)
    tasks_raw = parse_phases_and_tasks(text)

    tasks_out: List[Dict[str, Any]] = []
    phase_counts: Dict[int, int] = {}
    phase_names: Dict[int, str] = {}
    for t in tasks_raw:
        files = extract_files_from_task(t["body"])
        steps = extract_steps(t["body"])
        expected = extract_expected_lines(t["body"])
        tasks_out.append({
            "task_num": t["task_num"],
            "task_subject": t["task_subject"],
            "phase_num": t["phase_num"],
            "phase_name": t["phase_name"],
            "body": t["body"],
            "files_count": len(files),
            "steps_count": len(steps),
            "expected_count": len(expected),
            "files": files,
            "steps": steps,
            "expected": expected,
        })
        phase_counts[t["phase_num"]] = phase_counts.get(t["phase_num"], 0) + 1
        phase_names[t["phase_num"]] = t["phase_name"]

    phases_out = [
        {
            "phase_num": n,
            "phase_name": phase_names.get(n, ""),
            "task_count": phase_counts[n],
        }
        for n in sorted(phase_counts.keys())
    ]

    return {
        "header": header,
        "phases": phases_out,
        "tasks": tasks_out,
        "total_phases": len(phases_out),
        "total_tasks": len(tasks_out),
    }


# ================= Wave-6: Depends extraction =================

RE_DEPENDS = re.compile(r"^\*\*Depends:\*\*\s+(.+)$", re.MULTILINE)
RE_PHASE_SUFFIX = re.compile(r"\s*\([^)]*\)\s*$")


def extract_depends(task_body: str) -> List[str]:
    """Retorna lista normalizada de labels declarados em `**Depends:**` line.

    Input: texto markdown do body da task (apos `### Task N.M:` heading,
    ate proxima task/phase/EOF).

    Output: lista tipo ['Task 3.1', 'Task 5.2'].

    Normalizacoes aplicadas:
    - Strip whitespace de cada label.
    - Strip sufixos parentese (ex: 'Task 2.1 (Phase 1)' -> 'Task 2.1').
    - Filtra vazios.
    """
    m = RE_DEPENDS.search(task_body)
    if not m:
        return []
    raw = m.group(1).strip()
    items = [x.strip() for x in raw.split(",")]
    items = [RE_PHASE_SUFFIX.sub("", x).strip() for x in items]
    return [x for x in items if x]
