"""Dependency resolver: computa blocked_by por task (wave-6 scrum-master-v2).

Modos:
- phase-sequence: cada task de Phase N depende da ULTIMA task de Phase N-1.
- explicit: apenas overrides da linha **Depends:**. Sem override em task
  non-initial = erro.
- hybrid (default): phase-sequence como base; overrides substituem por task.

Puro: sem side effects, sem I/O. Raises CycleDetectedError ou ValueError
em inputs invalidos.
"""
from typing import Dict, List


class CycleDetectedError(Exception):
    def __init__(self, cycle: list):
        self.cycle = cycle
        self.code = "CYCLE_DETECTED"
        super().__init__(f"cycle: {' -> '.join(cycle)}")


def build_phase_sequence_deps(tasks: list) -> Dict[str, List[str]]:
    """Default phase-sequence: task de Phase N+1 depende da ULTIMA task de Phase N.

    Input: lista de dicts {'label': str, 'phase_num': int, ...}.
    Output: dict label -> [label_pred, ...].

    Preserva ordem de insercao das tasks (assume parser devolve em ordem).
    """
    deps: Dict[str, List[str]] = {}
    current_phase = None
    last_in_current_phase = None
    prev_phase_last_label = None

    for t in tasks:
        label = t["label"]
        phase = t["phase_num"]
        if phase != current_phase:
            if last_in_current_phase is not None:
                prev_phase_last_label = last_in_current_phase
            current_phase = phase
            last_in_current_phase = None
        if prev_phase_last_label is not None:
            deps[label] = [prev_phase_last_label]
        else:
            deps[label] = []
        last_in_current_phase = label
    return deps


def apply_overrides(base_deps: Dict[str, List[str]], tasks: list,
                    mode: str) -> Dict[str, List[str]]:
    """Aplica overrides **Depends:** de cada task conforme mode.

    - hybrid: override SUBSTITUI phase-sequence default pra task com override.
      Tasks sem override mantêm phase-sequence.
    - phase-sequence: ignora overrides; retorna base_deps.
    - explicit: ignora base_deps; usa apenas overrides. Task sem override
      (exceto initial sem preds naturais) → ValueError.

    Returns new dict (nao muta base_deps).
    """
    if mode == "phase-sequence":
        return dict(base_deps)

    result: Dict[str, List[str]] = {}
    if mode == "hybrid":
        result = dict(base_deps)

    for t in tasks:
        label = t["label"]
        override = t.get("depends") or []
        if mode == "hybrid":
            if override:
                result[label] = list(override)
        elif mode == "explicit":
            if not override:
                if base_deps.get(label, []) == []:
                    result[label] = []
                else:
                    raise ValueError(
                        f"explicit mode: task {label} sem **Depends:** line"
                    )
            else:
                result[label] = list(override)
    return result


def detect_cycles(deps: Dict[str, List[str]]) -> list:
    """DFS topologico. Retorna primeiro ciclo encontrado ou [].

    Nodes nao-existentes no grafo (preds orphaos) sao tratados como folha
    (sem ciclo); validacao de pred-exists eh responsabilidade separada.
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color: Dict[str, int] = {}

    def dfs(node, path):
        if color.get(node) == GRAY:
            i = path.index(node) if node in path else 0
            return path[i:] + [node]
        if color.get(node) == BLACK:
            return None
        color[node] = GRAY
        new_path = path + [node]
        for n in deps.get(node, []):
            if n not in deps:
                continue
            c = dfs(n, new_path)
            if c:
                return c
        color[node] = BLACK
        return None

    for task_label in deps:
        cycle = dfs(task_label, [])
        if cycle:
            return cycle
    return []


def resolve(tasks: list, mode: str = "hybrid") -> Dict[str, List[str]]:
    """Orquestra resolver. Raises CycleDetectedError ou ValueError.

    Pipeline:
    1. build_phase_sequence_deps (base)
    2. apply_overrides conforme mode
    3. detect_cycles → raise se !=[]
    4. return final deps dict
    """
    if mode not in ("phase-sequence", "explicit", "hybrid"):
        raise ValueError(f"invalid mode: {mode}")
    base = build_phase_sequence_deps(tasks)
    final = apply_overrides(base, tasks, mode=mode)
    cycle = detect_cycles(final)
    if cycle:
        raise CycleDetectedError(cycle)
    return final
