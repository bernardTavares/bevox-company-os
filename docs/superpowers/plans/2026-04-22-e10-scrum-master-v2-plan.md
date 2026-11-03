# Scrum-Master v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evoluir `~/.openclaw/scrum-master-agent/` in-place: parseia `**Depends:**` em plans, computa `blocked_by` por task (hybrid default = phase-sequence + explicit override), roda cycle detect + gate self-check (espelho wave-4) ANTES de submeter proposal, e materializa via 2-step (task add minimal payload + set-dispatch-payload full com `blocked_by` resolvido — aproveita gate wave-5 em set_dispatch_payload).

**Architecture:** Novo módulo puro `lib/dependency_resolver.py` (build_phase_sequence_deps, apply_overrides, detect_cycles, resolve). Novo `lib/gate_check.py` (espelha wave-4 payload_gate — valida spec_ref + acceptance_criteria local antes de submeter). Parser `lib/parser.py` ganha helper `extract_depends(body_text)`. Proposer integra resolver + gate_check; adiciona `label`, `blocked_by_labels`, `computed_deps`, `dependency_mode` ao proposal JSON. Materializer mapeia `blocked_by_labels` → task_ids reais via `prov_to_real` (nova chave `label_to_real`), injeta em full_payload antes de set-dispatch-payload. CLI `propose` ganha `--dependency-mode {phase-sequence,explicit,hybrid}`.

**Tech Stack:** Python 3 stdlib + unittest. Zero pip install. Consistência waves 1-5.

**Spec canônica:** `bevox-knowledge/35_specs/2026-04-21-e10-scrum-master-v2.md`
**ADR governante:** `bevox-knowledge/30_adr/ADR-009-clarification-loop-unified-local-first.md`
**Bloco narrativo:** Operational Loop Hardening 2026-04-21 (wave-6 de 8)
**Runtime source:** `~/.openclaw/scrum-master-agent/` (NÃO git-tracked)
**Branch draft bevox-knowledge:** `draft/adr-009-clarification-daemon` (existente)

**Ajustes pós-spec (validados com Bernard 2026-04-22):**
1. **Label format: `Task N.M`** (não `Task N`) — real parser emits `task_num="1.1"`, `"2.3"`. Spec §3.2 e §3.8 usam `Task 3` singular; adaptar para N.M.
2. **Cross-phase label suffixes**: `Depends: Task 2 (Phase 1)` — parser strip `(Phase X)` antes de resolver label.
3. **Plans sem `Expected:` lines omitem acceptance_criteria** no payload hoje (proposer line 124: condicional). Wave-6 `gate_check` CAPTURA isso e falha proposal — plans incompletos rejeitados upstream.
4. **Source proposer mantém `spec_refs` (plural)** — inexistentes mudanças de naming. Materializer wave-5 já tem fallback `spec_ref = dp.get("spec_ref") or dp.get("spec_refs")`. Wave-6 preserva o nome legado.
5. **2-step materialize** (Bernard aprovou): `task add --payload '{spec_ref, ac}'` (wave-4 gate) → `set-dispatch-payload --payload '{full com blocked_by resolved}'` (wave-5 gate valida ciclo/pred). Mais DRY que o 3-step da spec §3.6; aproveita defesa wave-5.
6. **Proposal task ganha field `label`** (ex: `"Task 1.1"`) — hoje proposal task só tem `provisional_id`/`title`/etc. Usado como key no `computed_deps` dict + source pro materializer resolver via `label_to_real`.
7. **Scrum-master-agent é runtime-only (não git)** — wave-6 não gera commit próprio; apenas bevox-knowledge delivery commit no fim.

---

## File Structure

**Arquivos a criar (runtime, NÃO git):**
- `~/.openclaw/scrum-master-agent/lib/dependency_resolver.py` — resolver puro
- `~/.openclaw/scrum-master-agent/lib/gate_check.py` — espelho wave-4 payload_gate
- `~/.openclaw/scrum-master-agent/tests/__init__.py` — init (se não existir)
- `~/.openclaw/scrum-master-agent/tests/test_dependency_resolver.py`
- `~/.openclaw/scrum-master-agent/tests/test_gate_check.py`
- `~/.openclaw/scrum-master-agent/tests/test_parser_extract_depends.py`
- `~/.openclaw/scrum-master-agent/tests/test_proposer_v2.py`
- `~/.openclaw/scrum-master-agent/tests/test_materializer_v2.py`

**Arquivos a modificar (runtime, NÃO git):**
- `~/.openclaw/scrum-master-agent/lib/parser.py` — +`extract_depends(body)` helper
- `~/.openclaw/scrum-master-agent/lib/proposer.py` — +resolver integration, +gate_check, +label/blocked_by_labels/computed_deps/dependency_mode; nova signature `build_proposal(..., dependency_mode="hybrid")`
- `~/.openclaw/scrum-master-agent/lib/materializer.py` — topological sort + label_to_real mapping + `blocked_by` resolved no full_payload
- `~/.openclaw/scrum-master-agent/lib/api.py` — `cmd_propose` ganha flag `--dependency-mode`
- `~/.openclaw/scrum-master-agent/playbook.md` — seção nova "Dependency projection"

**Arquivos a modificar (bevox-knowledge draft branch):**
- `35_specs/2026-04-21-e10-scrum-master-v2.md` — status draft → delivered + delivery notes (7 deltas)
- `35_specs/2026-04-19-e10-scrum-master-agent.md` — header `superseded_by: 35_specs/2026-04-21-e10-scrum-master-v2.md`
- `40_roadmap/delivery-tracker.yml` — entry wave-6 delivered

**Runtime gerado (não versionado):**
- Backups `.pre-wave6.bak` de parser.py, proposer.py, materializer.py, api.py

---

## Phase 0 — Setup

### Task 1: Backups + tests scaffold + sanity

**Files:**
- Create: `~/.openclaw/scrum-master-agent/tests/__init__.py` (se não existir — probe primeiro)
- Backup: `lib/{parser,proposer,materializer,api}.py.pre-wave6.bak`

- [ ] **Step 1: Probe existing tests dir**

```bash
ls ~/.openclaw/scrum-master-agent/tests/ 2>/dev/null || echo "NO TESTS DIR"
```

Expected: provavelmente "NO TESTS DIR" (wave-1 original scrum-master sem tests). Se existir, não sobrescrever `__init__.py`.

- [ ] **Step 2: Criar tests dir + init**

```bash
mkdir -p ~/.openclaw/scrum-master-agent/tests
touch ~/.openclaw/scrum-master-agent/tests/__init__.py
```

- [ ] **Step 3: Backups 4 files**

```bash
cd ~/.openclaw/scrum-master-agent/lib
cp parser.py parser.py.pre-wave6.bak
cp proposer.py proposer.py.pre-wave6.bak
cp materializer.py materializer.py.pre-wave6.bak
cp api.py api.py.pre-wave6.bak
ls *.pre-wave6.bak
```

Expected: 4 `.pre-wave6.bak` files.

- [ ] **Step 4: Sanity — scrum-master CLI list ainda funciona**

```bash
~/.openclaw/scrum-master-agent/cli.sh list --json 2>&1 | head -5
```

Expected: JSON válido (probably `{"proposals": []}` ou lista pequena).

- [ ] **Step 5: Sanity — kanban-tasks suite ainda verde pós-wave-5**

```bash
cd ~/.openclaw/kanban-tasks && python3 -m unittest discover tests 2>&1 | tail -3
```

Expected: `Ran 63 tests ... OK` (baseline wave-5).

- [ ] **Step 6: Nenhum commit** (runtime não é git).

---

## Phase 1 — Parser extension

### Task 2: `parser.py::extract_depends` + 6 tests (TDD red→green)

**Files:**
- Create: `~/.openclaw/scrum-master-agent/tests/test_parser_extract_depends.py`
- Modify: `~/.openclaw/scrum-master-agent/lib/parser.py` (append helper)

- [ ] **Step 1: Escrever tests**

```python
"""Testes parser.extract_depends (wave-6 scrum-master-v2)."""
import unittest

from lib import parser


class TestExtractDepends(unittest.TestCase):
    def test_no_depends_line_returns_empty(self):
        body = "### Task 2.1: X\n\n**Files:**\n- Create: `a.py`\n\n- [ ] Step 1"
        self.assertEqual(parser.extract_depends(body), [])

    def test_single_dep(self):
        body = "**Depends:** Task 1.1"
        self.assertEqual(parser.extract_depends(body), ["Task 1.1"])

    def test_comma_separated_deps(self):
        body = "**Depends:** Task 1.1, Task 2.3, Task 3.2"
        self.assertEqual(parser.extract_depends(body),
                         ["Task 1.1", "Task 2.3", "Task 3.2"])

    def test_phase_suffix_stripped(self):
        """Cross-phase normalization: `Task 2 (Phase 1)` → `Task 2.X`
        eh preservado como-esta; parser nao inventa task_num."""
        # Spec §3.2 allows 'Task 2 (Phase 1)' — strip parenthesis suffix.
        body = "**Depends:** Task 1.1 (Phase 1), Task 2.3 (Phase 2)"
        result = parser.extract_depends(body)
        # Expect parens stripped, labels normalized
        self.assertEqual(result, ["Task 1.1", "Task 2.3"])

    def test_extra_whitespace_normalized(self):
        body = "**Depends:**   Task 1.1  ,   Task 2.1  "
        self.assertEqual(parser.extract_depends(body),
                         ["Task 1.1", "Task 2.1"])

    def test_empty_after_colon_returns_empty(self):
        body = "**Depends:** "
        self.assertEqual(parser.extract_depends(body), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar — confirmar FAIL**

```bash
cd ~/.openclaw/scrum-master-agent
python3 -m unittest tests.test_parser_extract_depends -v 2>&1 | tail -10
```

Expected: `AttributeError: module 'lib.parser' has no attribute 'extract_depends'`.

- [ ] **Step 3: Append em `lib/parser.py`**

No final do arquivo, adicionar:

```python
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
    # Strip parenthetical suffix (cross-phase reference)
    items = [RE_PHASE_SUFFIX.sub("", x).strip() for x in items]
    return [x for x in items if x]
```

- [ ] **Step 4: Re-rodar — 6/6 PASS**

```bash
python3 -m unittest tests.test_parser_extract_depends -v 2>&1 | tail -5
```

Expected: `Ran 6 tests ... OK`.

---

## Phase 2 — Dependency resolver

### Task 3: `lib/dependency_resolver.py` + 14 tests (TDD red→green)

**Files:**
- Create: `~/.openclaw/scrum-master-agent/tests/test_dependency_resolver.py`
- Create: `~/.openclaw/scrum-master-agent/lib/dependency_resolver.py`

- [ ] **Step 1: Escrever tests (3 classes)**

```python
"""Testes dependency_resolver (wave-6): build_phase_sequence, apply_overrides,
detect_cycles, resolve orchestration."""
import unittest

from lib import dependency_resolver as resolver


def _t(label, phase_num, depends=None):
    """Helper: constroi task dict mínimo para resolver (label + phase + override list)."""
    return {"label": label, "phase_num": phase_num, "depends": depends or []}


class TestBuildPhaseSequenceDeps(unittest.TestCase):
    def test_single_phase_no_deps(self):
        tasks = [_t("Task 1.1", 1), _t("Task 1.2", 1)]
        deps = resolver.build_phase_sequence_deps(tasks)
        self.assertEqual(deps["Task 1.1"], [])
        self.assertEqual(deps["Task 1.2"], [])

    def test_two_phases_last_of_previous_is_pred(self):
        tasks = [
            _t("Task 1.1", 1), _t("Task 1.2", 1),
            _t("Task 2.1", 2), _t("Task 2.2", 2),
        ]
        deps = resolver.build_phase_sequence_deps(tasks)
        self.assertEqual(deps["Task 1.1"], [])
        self.assertEqual(deps["Task 1.2"], [])
        # Phase 2 tasks: each depends on LAST task of Phase 1 (= Task 1.2)
        self.assertEqual(deps["Task 2.1"], ["Task 1.2"])
        self.assertEqual(deps["Task 2.2"], ["Task 1.2"])

    def test_three_phases_chain(self):
        tasks = [
            _t("Task 1.1", 1),
            _t("Task 2.1", 2),
            _t("Task 3.1", 3),
        ]
        deps = resolver.build_phase_sequence_deps(tasks)
        self.assertEqual(deps["Task 1.1"], [])
        self.assertEqual(deps["Task 2.1"], ["Task 1.1"])
        self.assertEqual(deps["Task 3.1"], ["Task 2.1"])


class TestApplyOverrides(unittest.TestCase):
    def test_hybrid_preserves_defaults_when_no_override(self):
        tasks = [_t("Task 1.1", 1), _t("Task 2.1", 2)]
        base = {"Task 1.1": [], "Task 2.1": ["Task 1.1"]}
        result = resolver.apply_overrides(base, tasks, mode="hybrid")
        self.assertEqual(result["Task 2.1"], ["Task 1.1"])

    def test_hybrid_override_replaces_default(self):
        tasks = [
            _t("Task 1.1", 1),
            _t("Task 2.1", 2, depends=["Task 1.1", "Task 3.2"]),
        ]
        base = {"Task 1.1": [], "Task 2.1": ["Task 1.1"]}
        result = resolver.apply_overrides(base, tasks, mode="hybrid")
        self.assertEqual(sorted(result["Task 2.1"]), ["Task 1.1", "Task 3.2"])

    def test_phase_sequence_mode_ignores_overrides(self):
        tasks = [
            _t("Task 1.1", 1),
            _t("Task 2.1", 2, depends=["Task 99.9"]),
        ]
        base = {"Task 1.1": [], "Task 2.1": ["Task 1.1"]}
        result = resolver.apply_overrides(base, tasks, mode="phase-sequence")
        self.assertEqual(result["Task 2.1"], ["Task 1.1"])  # override ignorado

    def test_explicit_mode_requires_override_raises(self):
        tasks = [
            _t("Task 1.1", 1, depends=["Task 0.1"]),
            _t("Task 2.1", 2),  # sem depends
        ]
        with self.assertRaises(ValueError) as ctx:
            resolver.apply_overrides({}, tasks, mode="explicit")
        self.assertIn("Task 2.1", str(ctx.exception))

    def test_explicit_mode_first_task_can_have_empty_override(self):
        """Task 1.1 pode nao ter override SE ja tinha deps vazias no phase-sequence.
        Em explicit puro, Task 1.1 sem override ainda deve ser permitida
        (first task nao tem predecessores)."""
        tasks = [_t("Task 1.1", 1, depends=[])]
        # Em explicit puro, vazia-lista eh aceitavel para Task 1.1
        result = resolver.apply_overrides({}, tasks, mode="explicit")
        self.assertEqual(result.get("Task 1.1", []), [])


class TestDetectCycles(unittest.TestCase):
    def test_no_cycle_linear(self):
        deps = {"A": [], "B": ["A"], "C": ["B"]}
        self.assertEqual(resolver.detect_cycles(deps), [])

    def test_self_cycle(self):
        deps = {"A": ["A"]}
        cycle = resolver.detect_cycles(deps)
        self.assertTrue(cycle)
        self.assertIn("A", cycle)

    def test_two_node_cycle(self):
        deps = {"A": ["B"], "B": ["A"]}
        cycle = resolver.detect_cycles(deps)
        self.assertTrue(cycle)
        self.assertIn("A", cycle)
        self.assertIn("B", cycle)

    def test_three_node_cycle(self):
        deps = {"A": ["B"], "B": ["C"], "C": ["A"]}
        cycle = resolver.detect_cycles(deps)
        self.assertTrue(cycle)


class TestResolve(unittest.TestCase):
    def test_hybrid_happy_path(self):
        tasks = [
            _t("Task 1.1", 1),
            _t("Task 2.1", 2),
            _t("Task 2.2", 2, depends=["Task 1.1"]),
        ]
        result = resolver.resolve(tasks, mode="hybrid")
        self.assertEqual(result["Task 1.1"], [])
        self.assertEqual(result["Task 2.1"], ["Task 1.1"])  # phase-sequence
        # Task 2.2: override replaces phase-sequence
        self.assertEqual(result["Task 2.2"], ["Task 1.1"])

    def test_resolve_cycle_raises(self):
        tasks = [
            _t("Task 1.1", 1, depends=["Task 2.1"]),
            _t("Task 2.1", 2, depends=["Task 1.1"]),
        ]
        with self.assertRaises(resolver.CycleDetectedError):
            resolver.resolve(tasks, mode="hybrid")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar — confirmar FAIL**

```bash
cd ~/.openclaw/scrum-master-agent
python3 -m unittest tests.test_dependency_resolver -v 2>&1 | tail -10
```

Expected: `ModuleNotFoundError: No module named 'lib.dependency_resolver'`.

- [ ] **Step 3: Criar `lib/dependency_resolver.py`**

```python
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
    last_in_current_phase: str = None  # label
    prev_phase_last_label: str = None  # for next iteration's tasks

    for t in tasks:
        label = t["label"]
        phase = t["phase_num"]
        if phase != current_phase:
            # Phase transition: the last_in_current_phase becomes prev_phase_last
            if last_in_current_phase is not None:
                prev_phase_last_label = last_in_current_phase
            current_phase = phase
            last_in_current_phase = None  # reset for new phase
        # This task's default dep: prev_phase_last_label (if exists)
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
            # else: keep phase-sequence default
        elif mode == "explicit":
            if not override:
                # Permitida apenas se eh a primeira task (sem phase-sequence
                # predecessor naturalmente). Heuristica: se label nao tinha
                # pred em base (Task 1.1 first), aceita vazio.
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
    """Orquestra resolver. Raises CycleDetectedError ou ValueError (explicit mode
    + task sem override).

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
```

- [ ] **Step 4: Re-rodar — 14/14 PASS**

```bash
python3 -m unittest tests.test_dependency_resolver -v 2>&1 | tail -5
```

Expected: `Ran 14 tests ... OK`.

---

## Phase 3 — Gate check

### Task 4: `lib/gate_check.py` + 8 tests (TDD red→green)

**Files:**
- Create: `~/.openclaw/scrum-master-agent/tests/test_gate_check.py`
- Create: `~/.openclaw/scrum-master-agent/lib/gate_check.py`

- [ ] **Step 1: Escrever tests**

```python
"""Testes gate_check (wave-6): espelha wave-4 payload_gate localmente."""
import unittest

from lib import gate_check


class TestCheckTaskPayload(unittest.TestCase):
    def test_happy_with_spec_ref_string_and_ac(self):
        t = {"label": "Task 1.1", "dispatch_payload": {
            "spec_ref": "x.md",
            "acceptance_criteria": ["AC1"],
        }}
        ok, missing = gate_check.check_task_payload(t)
        self.assertTrue(ok)
        self.assertEqual(missing, [])

    def test_happy_with_spec_refs_plural_list(self):
        """spec_refs (plural) tambem aceito (source shape do proposer)."""
        t = {"label": "T", "dispatch_payload": {
            "spec_refs": ["a.md", "b.md"],
            "acceptance_criteria": ["AC"],
        }}
        ok, missing = gate_check.check_task_payload(t)
        self.assertTrue(ok)

    def test_missing_ac_fails(self):
        t = {"label": "T", "dispatch_payload": {"spec_ref": "x.md"}}
        ok, missing = gate_check.check_task_payload(t)
        self.assertFalse(ok)
        self.assertIn("acceptance_criteria", missing)

    def test_empty_ac_list_fails(self):
        t = {"label": "T", "dispatch_payload": {
            "spec_ref": "x.md", "acceptance_criteria": [],
        }}
        ok, missing = gate_check.check_task_payload(t)
        self.assertFalse(ok)
        self.assertIn("acceptance_criteria", missing)

    def test_missing_spec_ref_fails(self):
        t = {"label": "T", "dispatch_payload": {
            "acceptance_criteria": ["AC"],
        }}
        ok, missing = gate_check.check_task_payload(t)
        self.assertFalse(ok)
        self.assertIn("spec_ref", missing)

    def test_empty_spec_refs_list_fails(self):
        t = {"label": "T", "dispatch_payload": {
            "spec_refs": [], "acceptance_criteria": ["AC"],
        }}
        ok, missing = gate_check.check_task_payload(t)
        self.assertFalse(ok)
        self.assertIn("spec_ref", missing)


class TestCheckProposal(unittest.TestCase):
    def test_all_tasks_valid_no_raise(self):
        proposal = {"tasks": [
            {"label": "Task 1.1", "dispatch_payload": {
                "spec_ref": "x.md", "acceptance_criteria": ["AC"]}},
            {"label": "Task 1.2", "dispatch_payload": {
                "spec_refs": ["x.md"], "acceptance_criteria": ["AC"]}},
        ]}
        gate_check.check_proposal(proposal)

    def test_one_task_missing_ac_raises(self):
        proposal = {"tasks": [
            {"label": "Task 1.1", "dispatch_payload": {
                "spec_ref": "x.md", "acceptance_criteria": ["AC"]}},
            {"label": "Task 1.2", "dispatch_payload": {"spec_ref": "x.md"}},
        ]}
        with self.assertRaises(gate_check.GateCheckFailedError) as ctx:
            gate_check.check_proposal(proposal)
        self.assertTrue(any("Task 1.2" in f for f in ctx.exception.failures))
        self.assertTrue(any("acceptance_criteria" in f for f in ctx.exception.failures))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar — confirmar FAIL**

```bash
cd ~/.openclaw/scrum-master-agent
python3 -m unittest tests.test_gate_check -v 2>&1 | tail -5
```

Expected: `ModuleNotFoundError: No module named 'lib.gate_check'`.

- [ ] **Step 3: Criar `lib/gate_check.py`**

```python
"""Gate check local — espelha wave-4 payload_gate (E10/OH wave-6).

Propósito: scrum-master valida localmente que cada task proposta tem
spec_ref + acceptance_criteria populados ANTES de submeter ao kanban.
Sem isso, o wave-4 gate do kanban rejeitaria o materialize downstream.

Guard-rail: fail-fast upstream → feedback imediato ao dev em vez de
submissao parcial + partial_failure (que exige triagem manual).
"""
from typing import Tuple, List


class GateCheckFailedError(Exception):
    def __init__(self, failures: List[str]):
        self.failures = list(failures)
        self.code = "GATE_CHECK_FAILED"
        super().__init__(f"gate check failures: {self.failures}")


def check_task_payload(task) -> Tuple[bool, List[str]]:
    """Valida 1 task. Aceita tanto `spec_ref` (singular) quanto `spec_refs`
    (plural, list) — source shape do proposer atual usa plural.

    Returns (ok, missing_fields_list).
    """
    dp = task.get("dispatch_payload") or {}
    missing: List[str] = []

    # spec_ref: string nao-vazia OR spec_refs: lista nao-vazia
    spec = dp.get("spec_ref")
    spec_refs = dp.get("spec_refs")
    spec_ok = False
    if isinstance(spec, str) and spec.strip():
        spec_ok = True
    elif isinstance(spec, list) and len(spec) > 0:
        spec_ok = True
    elif isinstance(spec_refs, list) and len(spec_refs) > 0:
        spec_ok = True
    if not spec_ok:
        missing.append("spec_ref")

    # acceptance_criteria: lista non-vazia
    ac = dp.get("acceptance_criteria")
    if not isinstance(ac, list) or len(ac) == 0:
        missing.append("acceptance_criteria")

    return (len(missing) == 0, missing)


def check_proposal(proposal) -> None:
    """Valida todas as tasks do proposal. Raise GateCheckFailedError
    se qualquer task falhar. Message lista todas as falhas.
    """
    failures: List[str] = []
    for i, t in enumerate(proposal.get("tasks") or []):
        ok, missing = check_task_payload(t)
        if not ok:
            label = t.get("label", f"task[{i}]")
            failures.append(f"{label}: missing {missing}")
    if failures:
        raise GateCheckFailedError(failures)
```

- [ ] **Step 4: Re-rodar — 8/8 PASS**

```bash
python3 -m unittest tests.test_gate_check -v 2>&1 | tail -5
```

Expected: `Ran 8 tests ... OK`.

---

## Phase 4 — Proposer integration

### Task 5: proposer.py integra resolver + gate_check + shape extensions

**Files:**
- Modify: `~/.openclaw/scrum-master-agent/lib/proposer.py`
- Create: `~/.openclaw/scrum-master-agent/tests/test_proposer_v2.py`

- [ ] **Step 1: Escrever tests integração**

```python
"""Testes proposer v2 (wave-6): integração com resolver + gate_check + shape."""
import importlib
import os
import shutil
import tempfile
import unittest
from pathlib import Path


PLAN_HAPPY = """# Plan Happy

> For agentic workers: use subagent-driven.

**Goal:** Test wave-6 scrum-master proposer.

**Epico:** E10

**Tech Stack:**
- python3 stdlib

**Project:** openclaw

**Specs:** `bevox-knowledge/35_specs/xxx.md`

## Phase 1 — Setup

### Task 1.1: Primeiro step

**Files:**
- Create: `a.py`

- [ ] **Step 1: Foo**

Expected: bar baz

### Task 1.2: Segundo step

**Files:**
- Create: `b.py`

- [ ] **Step 1: Foo**

Expected: bar

## Phase 2 — Implementation

### Task 2.1: Componente A

**Files:**
- Create: `c.py`

- [ ] **Step 1: Impl**

Expected: all tests pass

### Task 2.2: Componente B

**Files:**
- Create: `d.py`

**Depends:** Task 1.1, Task 2.1

- [ ] **Step 1: Final**

Expected: suite green
"""

PLAN_MISSING_AC = """# Plan Missing AC

**Goal:** Plan sem Expected lines.

**Epico:** E10

**Project:** openclaw

## Phase 1 — Setup

### Task 1.1: Sem expected

**Files:**
- Create: `a.py`

- [ ] **Step 1: Foo**
"""


def _reload_proposer():
    from lib import parser, proposer, dependency_resolver, gate_check
    importlib.reload(parser)
    importlib.reload(dependency_resolver)
    importlib.reload(gate_check)
    importlib.reload(proposer)
    return proposer


class TestBuildProposalHybrid(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="scrum-v2-happy-"))
        self.plan = self.tmp / "plan.md"
        self.plan.write_text(PLAN_HAPPY)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_hybrid_mode_phase_sequence_with_override(self):
        proposer = _reload_proposer()
        proposal = proposer.build_proposal(
            self.plan, cli_project_override=None,
            cli_target_sprint="current", actor="test",
            dependency_mode="hybrid",
        )
        self.assertEqual(proposal["dependency_mode"], "hybrid")
        self.assertIn("computed_deps", proposal)
        deps = proposal["computed_deps"]
        # Task 1.1 no deps (first in Phase 1)
        self.assertEqual(deps.get("Task 1.1", []), [])
        # Task 1.2 no deps (same phase)
        self.assertEqual(deps.get("Task 1.2", []), [])
        # Task 2.1 phase-sequence: last of Phase 1 = Task 1.2
        self.assertEqual(deps.get("Task 2.1", []), ["Task 1.2"])
        # Task 2.2 override: Task 1.1 + Task 2.1 (ignores phase-sequence)
        self.assertEqual(sorted(deps.get("Task 2.2", [])),
                         ["Task 1.1", "Task 2.1"])

    def test_proposal_task_has_label(self):
        proposer = _reload_proposer()
        proposal = proposer.build_proposal(
            self.plan, cli_project_override=None,
            cli_target_sprint="current", actor="test",
            dependency_mode="hybrid",
        )
        labels = [t.get("label") for t in proposal["tasks"]]
        self.assertEqual(labels, ["Task 1.1", "Task 1.2", "Task 2.1", "Task 2.2"])

    def test_blocked_by_labels_in_dispatch_payload(self):
        proposer = _reload_proposer()
        proposal = proposer.build_proposal(
            self.plan, cli_project_override=None,
            cli_target_sprint="current", actor="test",
            dependency_mode="hybrid",
        )
        by_label = {t["label"]: t for t in proposal["tasks"]}
        # Task 2.2: dispatch_payload.blocked_by_labels = sorted override
        t22_bb = by_label["Task 2.2"]["dispatch_payload"].get("blocked_by_labels")
        self.assertIsNotNone(t22_bb)
        self.assertEqual(sorted(t22_bb), ["Task 1.1", "Task 2.1"])


class TestPhaseSequenceMode(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="scrum-v2-ps-"))
        self.plan = self.tmp / "plan.md"
        self.plan.write_text(PLAN_HAPPY)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_phase_sequence_ignores_override(self):
        proposer = _reload_proposer()
        proposal = proposer.build_proposal(
            self.plan, cli_project_override=None,
            cli_target_sprint="current", actor="test",
            dependency_mode="phase-sequence",
        )
        deps = proposal["computed_deps"]
        # Task 2.2 in phase-sequence: last of Phase 1 = Task 1.2 (ignore **Depends:**)
        self.assertEqual(deps.get("Task 2.2", []), ["Task 1.2"])


class TestGateCheckFail(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="scrum-v2-gate-"))
        self.plan = self.tmp / "plan.md"
        self.plan.write_text(PLAN_MISSING_AC)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_plan_missing_ac_raises_gate_check_failed(self):
        from lib import gate_check
        proposer = _reload_proposer()
        with self.assertRaises(gate_check.GateCheckFailedError) as ctx:
            proposer.build_proposal(
                self.plan, cli_project_override=None,
                cli_target_sprint="current", actor="test",
                dependency_mode="hybrid",
            )
        self.assertTrue(any("Task 1.1" in f for f in ctx.exception.failures))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar — confirmar FAIL**

```bash
cd ~/.openclaw/scrum-master-agent
python3 -m unittest tests.test_proposer_v2 -v 2>&1 | tail -15
```

Expected: TypeError (`build_proposal` got unexpected kwarg `dependency_mode`) + KeyErrors em proposal shape (labels missing, computed_deps missing).

- [ ] **Step 3: Modificar `lib/proposer.py::build_proposal` signature + logica**

Ler função atual em `~/.openclaw/scrum-master-agent/lib/proposer.py`:

```bash
grep -n "def build_proposal\|def _build_task_entry\|def _build_dispatch_payload" ~/.openclaw/scrum-master-agent/lib/proposer.py
sed -n '160,220p' ~/.openclaw/scrum-master-agent/lib/proposer.py
```

**3a.** Adicionar imports no topo:

```python
from . import dependency_resolver, gate_check
```

**3b.** Estender `_build_task_entry` para incluir `label` e `blocked_by_labels`:

Adaptar a função. Adicionar ao dict retornado:

```python
return {
    "provisional_id": provisional_id,
    "label": f"Task {parsed_task['task_num']}",   # NOVO wave-6
    "title": parsed_task["task_subject"],
    # ... resto existente ...
    "dispatch_payload": {
        **_build_dispatch_payload(parsed_task, spec_refs, plan_ref_display),
        "blocked_by_labels": blocked_by_labels,   # NOVO wave-6 (resolved depois)
    },
}
```

Assinatura estendida:
```python
def _build_task_entry(
    parsed_task, provisional_id, header, resolved_project,
    target_sprint, spec_refs, plan_ref_display,
    blocked_by_labels=None,           # NOVO wave-6
):
    blocked_by_labels = list(blocked_by_labels or [])
    ...
```

**3c.** Modificar `build_proposal`:

Assinatura ganha kwarg:
```python
def build_proposal(
    plan_path: Path,
    cli_project_override: Optional[str],
    cli_target_sprint: str,
    actor: str = "bernard",
    dependency_mode: str = "hybrid",   # NOVO wave-6
) -> Dict[str, Any]:
```

Após o parse + project resolution existentes, adicionar ANTES de montar task entries:

```python
    # Wave-6: resolver deps
    # summary["tasks"] tem dicts com 'phase_num', 'task_num', 'task_subject', 'body', etc.
    # Normalizar pro shape resolver espera: {label, phase_num, depends}.
    resolver_tasks = []
    for pt in summary["tasks"]:
        label = f"Task {pt['task_num']}"
        depends = parser_lib.extract_depends(pt["body"])
        resolver_tasks.append({
            "label": label,
            "phase_num": pt["phase_num"],
            "depends": depends,
        })

    # detect_cycle + apply resolver pipeline (raises CycleDetectedError ou
    # ValueError em modo explicit sem override)
    computed_deps = dependency_resolver.resolve(resolver_tasks,
                                                mode=dependency_mode)
```

Após construir `task_entries`, aplicar `blocked_by_labels` a cada:

```python
    task_entries = []
    for pt, prov in zip(summary["tasks"], ...):  # adaptar conforme zip atual
        label = f"Task {pt['task_num']}"
        blocked_by_labels = computed_deps.get(label, [])
        entry = _build_task_entry(
            pt, prov, summary["header"], proj_map[pt_key], cli_target_sprint,
            spec_refs, plan_ref_display,
            blocked_by_labels=blocked_by_labels,
        )
        task_entries.append(entry)
```

**3d.** Top-level proposal dict ganha novos campos:

```python
    proposal = {
        "schema_version": 2,   # bump de 1 → 2 (wave-6)
        # ... campos existentes: proposal_id, created_at, plan_ref, etc ...
        "dependency_mode": dependency_mode,      # NOVO
        "computed_deps": computed_deps,           # NOVO
        "tasks": task_entries,
    }

    # Wave-6 gate self-check: valida spec_ref + ac em TODAS antes de submeter
    gate_check.check_proposal(proposal)

    return proposal
```

**IMPORTANTE:** Adapte o código existente real — o padrão acima é guia; leia o código real e integre mantendo outros campos/behavior existentes (ex: `proposal_id`, `plan_sha`, etc.).

- [ ] **Step 4: Re-rodar tests — 5/5 PASS**

```bash
cd ~/.openclaw/scrum-master-agent
python3 -m unittest tests.test_proposer_v2 -v 2>&1 | tail -7
```

Expected: `Ran 5 tests ... OK`.

- [ ] **Step 5: Full suite regression (scrum-master tests)**

```bash
python3 -m unittest discover tests -v 2>&1 | tail -3
```

Expected: 33/33 (6 parser + 14 resolver + 8 gate_check + 5 proposer).

---

## Phase 5 — Materializer integration (2-step)

### Task 6: materializer.py: topological sort + label_to_real + blocked_by em full_payload

**Files:**
- Modify: `~/.openclaw/scrum-master-agent/lib/materializer.py`
- Create: `~/.openclaw/scrum-master-agent/tests/test_materializer_v2.py`

- [ ] **Step 1: Escrever tests (mock subprocess)**

```python
"""Testes materializer v2 (wave-6): topological sort + label_to_real + blocked_by."""
import importlib
import json
import unittest
from unittest.mock import patch


def _reload_mat():
    from lib import materializer
    importlib.reload(materializer)
    return materializer


PROPOSAL_FIXTURE = {
    "schema_version": 2,
    "proposal_id": "test-proposal-v6",
    "dependency_mode": "hybrid",
    "target_sprint": "current",
    "computed_deps": {
        "Task 1.1": [],
        "Task 2.1": ["Task 1.1"],
        "Task 2.2": ["Task 1.1", "Task 2.1"],
    },
    "tasks": [
        {
            "provisional_id": "prov-1", "label": "Task 1.1",
            "title": "A", "project": "openclaw", "epic_id": "E10",
            "wave_ref": "E10/OH/Phase-1",
            "dispatch_payload": {
                "spec_refs": ["x.md"], "acceptance_criteria": ["AC1"],
                "goal": "g", "plan_ref": "p", "plan_anchor": "a",
                "blocked_by_labels": [],
            },
            "description": "",
        },
        {
            "provisional_id": "prov-2", "label": "Task 2.1",
            "title": "B", "project": "openclaw", "epic_id": "E10",
            "wave_ref": "E10/OH/Phase-2",
            "dispatch_payload": {
                "spec_refs": ["x.md"], "acceptance_criteria": ["AC2"],
                "goal": "g", "plan_ref": "p", "plan_anchor": "a",
                "blocked_by_labels": ["Task 1.1"],
            },
            "description": "",
        },
        {
            "provisional_id": "prov-3", "label": "Task 2.2",
            "title": "C", "project": "openclaw", "epic_id": "E10",
            "wave_ref": "E10/OH/Phase-2",
            "dispatch_payload": {
                "spec_refs": ["x.md"], "acceptance_criteria": ["AC3"],
                "goal": "g", "plan_ref": "p", "plan_anchor": "a",
                "blocked_by_labels": ["Task 1.1", "Task 2.1"],
            },
            "description": "",
        },
    ],
}


class TestMaterializerV2(unittest.TestCase):
    def test_topological_order_and_blocked_by_resolution(self):
        materializer = _reload_mat()
        calls: list = []

        def fake_run_kanban(args, actor=None):
            calls.append(("cli", tuple(args)))
            if args[0] == "task" and args[1] == "add":
                # Captura o --payload passado
                p_idx = args.index("--payload") if "--payload" in args else None
                minimal_payload = json.loads(args[p_idx + 1]) if p_idx else {}
                # Retorna task_id baseado no indice criado
                idx = len([c for c in calls if c[1][1] == "add"])
                return {"ok": True, "task": {"id": f"T-000{idx}"}}
            elif args[0] == "task" and args[1] == "set-dispatch-payload":
                return {"ok": True}
            return {}

        with patch.object(materializer, "_run_kanban", side_effect=fake_run_kanban):
            result = materializer.materialize_proposal(
                PROPOSAL_FIXTURE, target_sprint="current",
                make_ready=False, actor="test",
            )

        # Verificar ordem: Task 1.1 criada antes de Task 2.1 antes de Task 2.2
        add_calls = [c for c in calls if c[1][0] == "task" and c[1][1] == "add"]
        self.assertEqual(len(add_calls), 3)
        # Titles add na ordem topologica
        titles_ordered = []
        for c in add_calls:
            args = c[1]
            titles_ordered.append(args[2])
        self.assertEqual(titles_ordered, ["A", "B", "C"])

        # Verificar set-dispatch-payload: para T-0002 (Task 2.1), blocked_by=[T-0001]
        sdp_calls = [c for c in calls if c[1][0] == "task"
                     and c[1][1] == "set-dispatch-payload"]
        self.assertEqual(len(sdp_calls), 3)
        # Encontra call para T-0002 (Task 2.1)
        for c in sdp_calls:
            args = c[1]
            tid = args[2]  # task_id positional
            p_idx = args.index("--payload")
            payload = json.loads(args[p_idx + 1])
            if tid == "T-0002":
                self.assertEqual(payload.get("blocked_by"), ["T-0001"])
            elif tid == "T-0003":
                self.assertEqual(sorted(payload.get("blocked_by", [])),
                                 ["T-0001", "T-0002"])


if __name__ == "__main__":
    unittest.main()
```

**NOTE:** Este test mocka `_run_kanban` internal function. Se o nome real no materializer for diferente, adaptar.

- [ ] **Step 2: Rodar tests — confirmar FAIL**

```bash
cd ~/.openclaw/scrum-master-agent
python3 -m unittest tests.test_materializer_v2 -v 2>&1 | tail -15
```

Expected: falha em `materialize_proposal` signature ou na ordem/blocked_by não resolvido.

- [ ] **Step 3: Modificar `lib/materializer.py`**

Ler código atual:
```bash
grep -n "def _materialize_one\|def materialize\|def _run_kanban\|prov_to_real" ~/.openclaw/scrum-master-agent/lib/materializer.py | head -10
```

**3a.** Adicionar função `_topological_order` (private):

```python
def _topological_order(computed_deps, task_labels):
    """Kahn's algorithm. Retorna ordem topologica de labels.

    Inputs:
    - computed_deps: dict {label: [pred_label, ...]}
    - task_labels: conjunto/lista dos labels no proposal

    Output: list[str] em ordem topologica (preds antes de deps).

    Pressupoe: grafo sem ciclos (resolver ja detectou). Se por algum motivo
    houver, esta funcao detecta via tamanho do output e raise AssertionError.
    """
    from collections import defaultdict, deque

    in_degree = {l: 0 for l in task_labels}
    forward = defaultdict(list)  # pred -> [dep, ...]
    for label, preds in computed_deps.items():
        if label not in in_degree:
            continue
        for p in preds:
            if p in in_degree:
                forward[p].append(label)
                in_degree[label] += 1

    queue = deque([l for l in task_labels if in_degree.get(l, 0) == 0])
    order = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for dep in forward[node]:
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                queue.append(dep)

    assert len(order) == len(task_labels), \
        f"Cycle survived resolver detection: order={order}, labels={task_labels}"
    return order
```

**3b.** Modificar `_materialize_one` (ou criar novo wrapper `materialize_proposal`) para:
- Iterar tasks em ordem topológica
- Resolver `blocked_by_labels` → `blocked_by` (task_ids reais) antes de `set-dispatch-payload`
- Incluir `blocked_by` no full_payload passado ao set-dispatch-payload

Padrão (adaptar ao código existente):

```python
def materialize_proposal(proposal, target_sprint, make_ready, actor):
    """Materializa proposal inteira. Retorna lista de {label, task_id, preds}."""
    computed_deps = proposal.get("computed_deps") or {}
    tasks_by_label = {t["label"]: t for t in proposal.get("tasks") or []}
    labels = list(tasks_by_label.keys())
    order = _topological_order(computed_deps, labels)

    label_to_real: Dict[str, str] = {}
    prov_to_real: Dict[str, str] = {}
    created: list = []

    for label in order:
        task = tasks_by_label[label]
        pred_labels = (task.get("dispatch_payload") or {}).get("blocked_by_labels", [])

        # Construir minimal_payload pra task add (gate wave-4)
        full_dp = dict(task.get("dispatch_payload") or {})
        # Strip blocked_by_labels do full_payload (substitui por blocked_by resolvido)
        full_dp.pop("blocked_by_labels", None)

        spec_ref_val = full_dp.get("spec_ref")
        if spec_ref_val is None:
            spec_ref_val = full_dp.get("spec_refs")
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
        prov_to_real[task["provisional_id"]] = real_id

        # Resolver blocked_by: labels → task_ids reais (2-step, wave-5 gate valida ciclo)
        resolved_blocked_by = [label_to_real[pl] for pl in pred_labels
                               if pl in label_to_real]
        full_dp["blocked_by"] = resolved_blocked_by

        # depends_on legacy resolution preservada
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

        created.append({"label": label, "task_id": real_id,
                        "preds": resolved_blocked_by})

    return created
```

**3c.** Se já existe função `materialize` (ou `accept` chamando _materialize_one), atualizar o call site para usar `materialize_proposal`. Caller anterior (em api.py::cmd_accept) passa `proposal["tasks"]` sequencialmente; agora passa o proposal inteiro + usa topological order via computed_deps.

**IMPORTANTE:** Ler código atual + manter compatibilidade com o shape antigo (sem `computed_deps` ou `label`) via fallback — senão proposals v1 quebram. Sugestão: se `computed_deps` absent ou task sem `label`, degrade to order-by-appearance (backward-compat).

- [ ] **Step 4: Re-rodar — 1/1 PASS**

```bash
python3 -m unittest tests.test_materializer_v2 -v 2>&1 | tail -5
```

Expected: `Ran 1 tests ... OK`.

- [ ] **Step 5: Full suite**

```bash
python3 -m unittest discover tests -v 2>&1 | tail -3
```

Expected: 34/34 (33 + 1 materializer).

---

## Phase 6 — CLI flag

### Task 7: api.py --dependency-mode em cmd_propose + error handling

**Files:**
- Modify: `~/.openclaw/scrum-master-agent/lib/api.py`

- [ ] **Step 1: Ler cmd_propose atual**

```bash
grep -n "def cmd_propose\|add_parser\|propose" ~/.openclaw/scrum-master-agent/lib/api.py | head -15
```

- [ ] **Step 2: Adicionar --dependency-mode ao argparse do propose subparser**

Localizar bloco onde `propose` subparser é construído. Adicionar:

```python
propose.add_argument(
    "--dependency-mode",
    choices=["phase-sequence", "explicit", "hybrid"],
    default="hybrid",
    help="como deduzir blocked_by entre tasks (default: hybrid)",
)
```

- [ ] **Step 3: Modificar `cmd_propose` para passar flag + tratar errors novos**

```python
def cmd_propose(args):
    from . import proposer, dependency_resolver, gate_check

    try:
        proposal = proposer.build_proposal(
            Path(args.plan_path),
            cli_project_override=args.project_override,
            cli_target_sprint=args.target_sprint,
            actor=args.actor,
            dependency_mode=args.dependency_mode,   # NOVO wave-6
        )
    except dependency_resolver.CycleDetectedError as e:
        return _err(f"cycle: {' -> '.join(e.cycle)}", "CYCLE_DETECTED",
                    args.json)
    except ValueError as e:
        # Modo explicit sem override + outros ValueError
        msg = str(e)
        if "explicit mode" in msg:
            return _err(msg, "EXPLICIT_MODE_MISSING_OVERRIDE", args.json)
        raise
    except gate_check.GateCheckFailedError as e:
        detail = "; ".join(e.failures)
        return _err(detail, "GATE_CHECK_FAILED", args.json)

    # ... resto existente (write proposal, _print, etc) ...
    store.write_proposal(proposal)
    _print(proposal, args.json, f"proposal: {proposal['proposal_id']}")
    return EXIT_OK
```

**NOTE:** Adapte conforme padrão do `_err` no api.py real. Se não existir `_err`, seguir pattern existente de erro no código.

- [ ] **Step 4: Sanity CLI help**

```bash
~/.openclaw/scrum-master-agent/cli.sh propose --help 2>&1 | head -20
```

Expected: `--dependency-mode` flag visível no help.

- [ ] **Step 5: Sanity — py_compile pós-edits**

```bash
python3 -m py_compile ~/.openclaw/scrum-master-agent/lib/api.py \
                      ~/.openclaw/scrum-master-agent/lib/proposer.py \
                      ~/.openclaw/scrum-master-agent/lib/materializer.py \
                      ~/.openclaw/scrum-master-agent/lib/dependency_resolver.py \
                      ~/.openclaw/scrum-master-agent/lib/gate_check.py && echo OK
```

Expected: `OK`.

- [ ] **Step 6: Suite completa regression**

```bash
cd ~/.openclaw/scrum-master-agent
python3 -m unittest discover tests 2>&1 | tail -3
```

Expected: `Ran 34 tests ... OK`.

---

## Phase 7 — Smoke E2E + delivery

### Task 8: Smoke E2E + update playbook.md

**Files:** nenhum (smoke) + modify playbook.md

- [ ] **Step 1: Smoke — propose com plan happy (não materializa; só JSON)**

```bash
# Usa um plan existente entregue em wave prévia
PLAN=~/.openclaw/docs/superpowers/plans/2026-04-22-e5-f4-kanban-blocked-by-schema-plan.md
~/.openclaw/scrum-master-agent/cli.sh propose "$PLAN" --dependency-mode hybrid --json 2>&1 | head -30
```

Expected: ou proposal JSON válido com `computed_deps`/`dependency_mode`/`tasks[*].label`/`tasks[*].dispatch_payload.blocked_by_labels`, OU `GATE_CHECK_FAILED` se o plan em questão não tem `Expected:` em todas as tasks (nesse caso, seguir pra smoke #2 com plan conhecido compliant). Reportar qual aconteceu.

- [ ] **Step 2: Se smoke #1 reporta GATE_CHECK_FAILED**

Usar plan sintético criado em tmpdir pra smoke limpo:

```bash
TMP=$(mktemp -d)
cat > "$TMP/plan.md" <<'EOF'
# Smoke Plan

**Goal:** Smoke wave-6.
**Epico:** E10
**Project:** openclaw
**Specs:** `bevox-knowledge/35_specs/2026-04-21-e10-scrum-master-v2.md`

## Phase 1 — Setup

### Task 1.1: A

**Files:**
- Create: `a.py`

- [ ] **Step 1: Foo**

Expected: pass

### Task 1.2: B

**Files:**
- Create: `b.py`

- [ ] **Step 1: Foo**

Expected: pass

## Phase 2 — Main

### Task 2.1: C

**Files:**
- Create: `c.py`

**Depends:** Task 1.1

- [ ] **Step 1: Foo**

Expected: pass
EOF

~/.openclaw/scrum-master-agent/cli.sh propose "$TMP/plan.md" --dependency-mode hybrid --json 2>&1 | python3 -m json.tool
rm -rf "$TMP"
```

Expected: proposal JSON com computed_deps = `{"Task 1.1": [], "Task 1.2": [], "Task 2.1": ["Task 1.1"]}` (override replaces phase-sequence default `["Task 1.2"]`).

- [ ] **Step 3: Update playbook.md com seção "Dependency projection"**

Abrir `~/.openclaw/scrum-master-agent/playbook.md`. Encontrar seção apropriada (depois de "Responsabilidades" ou similar). Adicionar:

```markdown
## Dependency projection (wave-6)

Scrum-master projeta `blocked_by` automaticamente via 2 fontes:

1. **Phase-sequence default (implicit)**: cada task de Phase N+1 depende
   da ULTIMA task de Phase N.
2. **`**Depends:**` override (explicit)**: linha no body da task lista
   labels de preds: `**Depends:** Task 1.1, Task 2.3`.

Flag `--dependency-mode {phase-sequence,explicit,hybrid}` (default hybrid):
- `hybrid`: phase-sequence como base + override substitui por task com
  `**Depends:**` linha.
- `phase-sequence`: ignora overrides; só sequência de fases.
- `explicit`: exige `**Depends:**` em toda task non-initial; erro caso
  ausente.

Cycle detect e pred existence validados antes de submeter ao kanban.
Gate self-check (spec_ref + acceptance_criteria) roda tambem.

Materializacao 2-step:
1. `task add` com payload minimal (wave-4 gate).
2. `task set-dispatch-payload` com full payload incluindo blocked_by
   resolved (task_ids). Wave-5 gate em set_dispatch_payload valida ciclo +
   pred existence.
```

- [ ] **Step 4: Sem commit** (runtime não é git).

### Task 9: Commit bevox-knowledge delivery

**Files:**
- Modify: `~/bevox-knowledge/35_specs/2026-04-21-e10-scrum-master-v2.md` (status + delivery notes)
- Modify: `~/bevox-knowledge/35_specs/2026-04-19-e10-scrum-master-agent.md` (header superseded_by)
- Modify: `~/bevox-knowledge/40_roadmap/delivery-tracker.yml` (entry wave-6 delivered)

- [ ] **Step 1: Confirmar branch draft ativo**

```bash
cd ~/bevox-knowledge
git branch --show-current
```

Expected: `draft/adr-009-clarification-daemon`.

- [ ] **Step 2: Atualizar status + 7 delivery notes em spec wave-6**

Editar `35_specs/2026-04-21-e10-scrum-master-v2.md`:
- Status: `draft` → `delivered (2026-04-22)`
- Após §2 (Decisoes), inserir §2.1:

```markdown
---

## 2.1 Delivery notes (2026-04-22)

Deltas entre spec e implementacao entregue:

1. **Label format eh `Task N.M`** (nao `Task N` puro como em §3.2/§3.8).
   Parser real emits `task_num="1.1"`, `"2.3"`. Plans canonicos seguem
   convencao Task N.M. Labels ficam `"Task 1.1"`, `"Task 2.3"`.

2. **Cross-phase label normalization** em extract_depends: `Task 2 (Phase 1)`
   → `Task 2` via regex strip parenthetical suffix.

3. **Plans sem `Expected:` lines omitem `acceptance_criteria`** do payload
   (proposer behavior). Wave-6 gate_check captura e rejeita proposal —
   feedback imediato em vez de materializar parcial.

4. **`spec_refs` (plural, list) preservado** no source (legacy naming).
   Materializer wave-5 faz fallback `spec_ref = dp.get("spec_ref") or
   dp.get("spec_refs")`. Gate_check aceita ambos os keys.

5. **Proposal task ganha field `label`**: `f"Task {task_num}"` (ex:
   `"Task 1.1"`). Usado como chave em `computed_deps` top-level +
   `blocked_by_labels` no dispatch_payload.

6. **Materializacao 2-step** (nao 3-step como spec §3.6):
   - `task add --payload '{spec_ref, ac}'` (minimal, wave-4 gate)
   - `task set-dispatch-payload <id> --payload '{full COM blocked_by resolved}'`
     (wave-5 gate em set_dispatch_payload valida ciclo + pred existence)

   Justificativa: DRY + menos calls CLI + reuso da defesa wave-5.

7. **Scrum-master-agent runtime-only** (nao git-tracked). Wave-6 nao gera
   commit proprio em repo canonico; apenas delivery metadata commit em
   bevox-knowledge draft branch.
```

- [ ] **Step 3: Marcar v1 spec como superseded**

Editar `35_specs/2026-04-19-e10-scrum-master-agent.md`. No header frontmatter (ou topo):
```markdown
**Superseded by:** `35_specs/2026-04-21-e10-scrum-master-v2.md` (2026-04-22)
```

Posicionar logo após a linha `**Status:** ...` existente.

- [ ] **Step 4: Acrescentar entry tracker após wave-5**

Localizar em `40_roadmap/delivery-tracker.yml` a entry `kanban-blocked-by-schema` (wave-5). Inserir APÓS:

```yaml
      - id: scrum-master-v2
        status: delivered
        delivered_at: 2026-04-22
        spec: 35_specs/2026-04-21-e10-scrum-master-v2.md
        adr: 30_adr/ADR-009-clarification-loop-unified-local-first.md
        narrative: "Operational Loop Hardening 2026-04-22 — wave-6 de 8"
        supersedes: 35_specs/2026-04-19-e10-scrum-master-agent.md
        features:
          - "parser.py: extract_depends regex + cross-phase label normalization (Task X.Y (Phase N) -> Task X.Y)"
          - "lib/dependency_resolver.py (novo): build_phase_sequence_deps + apply_overrides + detect_cycles + resolve orchestration; 3 modes (phase-sequence/explicit/hybrid)"
          - "lib/gate_check.py (novo): espelho wave-4 payload_gate local; check_task_payload + check_proposal; aceita tanto spec_ref (singular) quanto spec_refs (plural)"
          - "proposer.py: integra resolver + gate_check; schema_version bump 1→2; campos novos no proposal JSON (label, blocked_by_labels em dispatch_payload, computed_deps top-level, dependency_mode)"
          - "materializer.py: topological sort (Kahn's) + label_to_real resolution + 2-step materializacao (task add minimal + set-dispatch-payload com blocked_by resolvido; aproveita wave-5 gate em set_dispatch_payload)"
          - "api.py: flag --dependency-mode {phase-sequence,explicit,hybrid} default hybrid em cmd_propose; error mapping CYCLE_DETECTED / EXPLICIT_MODE_MISSING_OVERRIDE / GATE_CHECK_FAILED"
          - "Backward compat preservada: plans pre-wave-6 sem `**Depends:**` operam via phase-sequence default; proposal v1 tolerado em materializer com fallback order-by-appearance"
          - "34 novos unit tests (6 parser + 14 resolver + 8 gate_check + 5 proposer + 1 materializer); suite scrum-master green"
          - "scrum-master-agent runtime-only (nao git-tracked); delivery metadata apenas em bevox-knowledge"
      - id: finance-agent
```

Ajustar posição exata para inserir antes de `finance-agent` ou similar, seguindo ordem cronológica wave-1..6 do bloco OH.

- [ ] **Step 5: Commit draft**

```bash
cd ~/bevox-knowledge
git add 35_specs/2026-04-21-e10-scrum-master-v2.md \
        35_specs/2026-04-19-e10-scrum-master-agent.md \
        40_roadmap/delivery-tracker.yml
git diff --cached --stat
git commit -m "$(cat <<'EOF'
delivery(E10): wave-6 scrum-master-v2 delivered

Operational Loop Hardening 2026-04-22 wave-6 completa. Scrum-master-agent
evoluido em-place (runtime-only em ~/.openclaw/scrum-master-agent/, NAO
git-tracked). Agora popula dispatch_payload.blocked_by automaticamente
via:

1. Phase-sequence default (Phase N+1 task -> last of Phase N)
2. Explicit override via `**Depends:**` line in plan task body
3. Hybrid = default + explicit (ganha override onde presente)

CLI flag --dependency-mode {phase-sequence, explicit, hybrid}.

Shape proposal v2: +label, +dispatch_payload.blocked_by_labels,
+computed_deps top-level, +dependency_mode.

Gate self-check (espelho wave-4) rejeita proposal cujo plan omita
spec_ref ou acceptance_criteria — feedback imediato em vez de
materializacao parcial.

Materializacao 2-step: task add minimal payload (wave-4 gate) +
set-dispatch-payload com blocked_by resolvido (wave-5 gate valida
ciclo + pred existence). DRY; reusa defesas downstream.

7 delivery notes inline (§2.1) cobrem deltas:
- Label format Task N.M (nao Task N puro)
- Cross-phase label stripping (Task X.Y (Phase N))
- Plans sem Expected rejeitados by gate_check
- spec_refs (plural) preservado com gate_check tolerante
- Proposal task ganha label field
- Materializacao 2-step (nao 3-step spec §3.6)
- Runtime-only delivery (sem commit proprio no repo canonico)

34 novos unit tests Python (6 parser + 14 resolver + 8 gate_check +
5 proposer + 1 materializer). Scrum-master suite green.

Spec v1 (2026-04-19-e10-scrum-master-agent.md) agora marca
`Superseded by: 35_specs/2026-04-21-e10-scrum-master-v2.md`.

Cadeia preventiva upstream completa: scrum-master-v2 gera task compliant
-> payload gate wave-4 passa -> blocked_by schema wave-5 orquestra ->
clarification-daemon wave-1 processa -> notifier wave-2 pushes ->
reply-handler wave-3 resolve. Proxima: wave-7 self-test E2E do bloco.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)" && git log --oneline -8
```

Expected: novo commit no topo, acima de `delivery(E5/F4): wave-5 kanban-blocked-by-schema delivered`.

- [ ] **Step 6: NÃO pushar** — merge condicional ao bloco OH completo (wave-7 PASS).

---

## Checklist final

- [ ] **Phase 1-6 tests Python:** 34/34 verdes (6 parser + 14 resolver + 8 gate_check + 5 proposer + 1 materializer).
- [ ] **Backups:** `lib/{parser,proposer,materializer,api}.py.pre-wave6.bak` pra rollback 1-cmd.
- [ ] **Smoke E2E:** `propose --dependency-mode hybrid` num plan sintético retorna JSON válido com `computed_deps` populado conforme esperado.
- [ ] **CLI sanity:** `propose --help` lista `--dependency-mode`.
- [ ] **Py_compile clean:** 5 arquivos modificados/novos compilam sem erros.
- [ ] **bevox-knowledge draft:** spec v6 status delivered + 7 delivery notes §2.1 + v1 marcada superseded_by + tracker entry. Branch `draft/adr-009-clarification-daemon`, NÃO pushada.
- [ ] **Backward compat:** proposals v1 (sem `computed_deps`/`label`) toleradas pelo materializer via fallback order-by-appearance.

---

## Próximos passos pós-delivery wave-6

1. **Wave-7 self-test E2E** do bloco OH inteiro (última). Scrum-master-v2 alimenta a cadeia preventiva upstream, wave-1/2/3 fecha o loop downstream.
2. Bernard testa `propose` live num plan real + `accept` pra materializar; verifica que kanban tasks têm `blocked_by` populado automaticamente via phase-sequence.
3. Writing-plans skill follow-up (externa ao bloco OH): adicionar convenção `**Depends:**` no template gerador de plans. Canônico futuro.
4. Quando wave-7 PASS, push das 4 branches pra main:
   - `bevox-knowledge/draft/adr-009-clarification-daemon`
   - `knowledge-sync/feat/e10-clarification-commands-plugin`
   - `mission-control/feat/e10-payload-completeness-gate`
   - `mission-control/feat/e5-f4-kanban-blocked-by-schema`
