# Kanban blocked_by Schema Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduzir dependência formal entre tasks via `dispatch_payload.blocked_by` com AND semantics + enforcement em transições + hooks atomic (auto-release em `done`, auto-block upstream em `rejected`/`archived`) + gate de detecção de ciclos universal (todos os write-paths de blocked_by) + schema bump v2→v3 aditivo retrocompatível.

**Architecture:** Funções puras em `lib/transitions.py` (`validate_blocked_by_field`, `detect_cycle`, `can_move_to_ready`) sem side-effects. Escrita via `lib/task.py::set_blocked_by` central que roda gate de ciclo antes de persistir. Hooks atomic dentro do mesmo `mutate_state()` de `task_move` (status→done/rejected) e `task_archive` (por lição wave-4: previne drift state.json ↔ events.jsonl). Gate de ciclo plugado em TRÊS write-paths: `task add` (via wave-4 payload), `set-dispatch-payload` (quando payload inclui blocked_by), `set-blocked-by` (dedicado). Schema migration via `rebuild` existente populando `blocked_by: []` default.

**Tech Stack:** Python 3 stdlib + unittest (kanban-tasks). TypeScript ESM + vitest (MC). Zero pip/npm install runtime. Consistência waves 1-4.

**Spec canônica:** `bevox-knowledge/35_specs/2026-04-21-e5-f4-kanban-blocked-by-schema.md`
**ADR governante:** `bevox-knowledge/30_adr/ADR-009-clarification-loop-unified-local-first.md` (cross-cut narrativo OH; wave vive em E5/F4)
**Bloco narrativo:** Operational Loop Hardening 2026-04-21 (wave-5 de 8)
**Runtime kanban-tasks:** `~/.openclaw/kanban-tasks/` (NÃO git-tracked)
**Source MC:** `~/code/mission-control/` (git, branch `feat/e5-f4-kanban-blocked-by-schema` a criar — branch DE `main`, NÃO empilhada em wave-4)
**Branch draft bevox-knowledge:** `draft/adr-009-clarification-daemon` (existente)

**Ajustes pós-spec (validados com Bernard 2026-04-22):**
1. **Hook ATOMIC** dentro de `mutate_state()` (não post-commit conforme spec §4.3). Lição wave-4: emitir event + mutar state deve acontecer na mesma transação senão `state.last_event_seq` drifa de `events.jsonl`.
2. **Ciclo gate UNIVERSAL** em TODOS os write-paths que tocam `blocked_by`: `task add` (via wave-4 payload), `set-dispatch-payload` (se payload inclui blocked_by com merge replace), `set-blocked-by` (dedicado). Spec §2.6 só menciona task add + set-blocked-by; fechamos loophole em set-dispatch-payload.
3. **`transitions.py` já existe** (85 linhas com `is_valid_transition/is_terminal/is_blockable/validate_or_raise`) — wave-5 ESTENDE, não cria arquivo novo.
4. **`archived` não é status** — é flag ortogonal via evento separado `task_archived`. Hook escuta AMBOS: `task_moved status_to in (rejected)` + `task_archived`. Spec §3.3 agrupa; real code split em dois eventos.
5. **`rebuild` command já existe** (`api.py:411`). Migração schema v2→v3 via extensão do rebuild existente (popular `dispatch_payload.blocked_by = []` default em tasks sem o campo).

---

## File Structure

**Arquivos a criar:**
- `~/.openclaw/kanban-tasks/tests/test_transitions_blocked_by.py` — tests puros (validate + cycle + can_move_to_ready)
- `~/.openclaw/kanban-tasks/tests/test_set_blocked_by.py` — tests integração CLI + state
- `~/.openclaw/kanban-tasks/tests/test_blocked_by_hooks.py` — tests auto-release + auto-block upstream
- `~/code/mission-control/src/app/api/kanban/tasks/[id]/blocked-by/route.ts` — PUT handler

**Arquivos a modificar (runtime kanban-tasks, NÃO git):**
- `lib/transitions.py` — +`validate_blocked_by_field`, +`detect_cycle`, +`can_move_to_ready`
- `lib/task.py` — +`set_blocked_by()`; estender `move()` e `archive()` com hooks atomic; estender `set_dispatch_payload()` com cycle gate quando blocked_by presente
- `lib/api.py` — +`cmd_task_set_blocked_by` + argparse subcmd; estender `cmd_rebuild` pra popular `blocked_by: []` default
- `lib/store.py` — bump `schema_version` constante (se hardcoded) ou adaptar rebuild pra normalizar

**Arquivos a modificar (MC repo, feat branch):**
- `src/lib/kanban/stateReader.ts` — Task type ganha `dispatch_payload.blocked_by?: string[]`
- `src/app/(dashboard)/kanban/page.tsx` — card exibe `deps: T-X, T-Y` quando `blocked_by` não vazio (minimal texto — UI graph é follow-up §1.3)

**Arquivos a modificar (bevox-knowledge draft branch):**
- `35_specs/2026-04-21-e5-f4-kanban-blocked-by-schema.md` — status draft → delivered + 5 delivery notes
- `40_roadmap/delivery-tracker.yml` — entry wave-5 delivered

**Runtime gerado (não versionado):**
- Backups `.pre-wave5.bak` de lib/task.py + lib/api.py + lib/transitions.py + lib/store.py

---

## Phase 0 — Setup

### Task 1: MC feat branch + kanban tests + backups

**Files:**
- New branch MC: `feat/e5-f4-kanban-blocked-by-schema` (de `main`, não de wave-4 feat)
- Backups: `lib/{task,api,transitions,store}.py.pre-wave5.bak`

- [ ] **Step 1: MC branch switch pra main + criar feat branch wave-5**

```bash
cd ~/code/mission-control
git status --short
# uncommitted unrelated continuam visíveis; ok
git checkout main
git checkout -b feat/e5-f4-kanban-blocked-by-schema
git branch --show-current
```

Expected: branch `feat/e5-f4-kanban-blocked-by-schema` ativa. Wave-4 commits ficam em `feat/e10-payload-completeness-gate` (isolado). Uncommitted (CLAUDE.md, health, hardening) preservados.

- [ ] **Step 2: Sanity — MC vitest baseline**

```bash
cd ~/code/mission-control
npm test -- --run 2>&1 | tail -10
```

Expected: 87/87 (ou número atual) verdes. Baseline estável.

- [ ] **Step 3: Backups kanban-tasks runtime**

```bash
cd ~/.openclaw/kanban-tasks/lib
cp task.py task.py.pre-wave5.bak
cp api.py api.py.pre-wave5.bak
cp transitions.py transitions.py.pre-wave5.bak
cp store.py store.py.pre-wave5.bak
ls *.pre-wave5.bak
```

Expected: 4 `.pre-wave5.bak` files.

- [ ] **Step 4: Sanity — kanban Python suite pre-wave5**

```bash
cd ~/.openclaw/kanban-tasks
python3 -m unittest discover tests -v 2>&1 | tail -5
```

Expected: 21/21 (wave-4 baseline). Suite verde antes de começar.

- [ ] **Step 5: Nenhum commit** (runtime não é git; MC feat branch ainda sem diffs).

---

## Phase 1 — Pure helpers (TDD)

### Task 2: `lib/transitions.py` — validate + cycle + can_move_to_ready

**Files:**
- Create: `~/.openclaw/kanban-tasks/tests/test_transitions_blocked_by.py`
- Modify: `~/.openclaw/kanban-tasks/lib/transitions.py` (append novas funcs)

- [ ] **Step 1: Escrever tests em `tests/test_transitions_blocked_by.py`**

```python
"""Testes puros transitions.py wave-5: validate_blocked_by_field, detect_cycle, can_move_to_ready."""
import unittest

from lib import transitions


class TestValidateBlockedByField(unittest.TestCase):
    def test_none_is_valid(self):
        valid, errors = transitions.validate_blocked_by_field(None)
        self.assertTrue(valid)
        self.assertEqual(errors, [])

    def test_empty_list_is_valid(self):
        valid, errors = transitions.validate_blocked_by_field([])
        self.assertTrue(valid)

    def test_string_list_with_T_prefix_is_valid(self):
        valid, errors = transitions.validate_blocked_by_field(["T-0001", "T-0042"])
        self.assertTrue(valid)

    def test_string_not_list_is_invalid(self):
        valid, errors = transitions.validate_blocked_by_field("T-0001")
        self.assertFalse(valid)
        self.assertIn("blocked_by_must_be_list", errors)

    def test_dict_is_invalid(self):
        valid, errors = transitions.validate_blocked_by_field({"T-0001": 1})
        self.assertFalse(valid)
        self.assertIn("blocked_by_must_be_list", errors)

    def test_non_T_prefix_is_invalid(self):
        valid, errors = transitions.validate_blocked_by_field(["T-0001", "X-0042"])
        self.assertFalse(valid)
        self.assertTrue(any("blocked_by[1]" in e for e in errors))

    def test_non_string_item_is_invalid(self):
        valid, errors = transitions.validate_blocked_by_field(["T-0001", 123])
        self.assertFalse(valid)
        self.assertTrue(any("blocked_by[1]" in e for e in errors))


class TestDetectCycle(unittest.TestCase):
    def _state(self, tasks):
        """Helper: constroi state com tasks = [{"id": ..., "blocked_by": [...]}, ...]."""
        return {"tasks": [
            {"id": t["id"], "dispatch_payload": {"blocked_by": t.get("blocked_by", [])}}
            for t in tasks
        ]}

    def test_self_cycle(self):
        state = self._state([])
        cycle = transitions.detect_cycle(state, "T-A", ["T-A"])
        self.assertEqual(cycle, ["T-A", "T-A"])

    def test_two_node_cycle(self):
        state = self._state([{"id": "T-B", "blocked_by": ["T-A"]}])
        cycle = transitions.detect_cycle(state, "T-A", ["T-B"])
        self.assertTrue(len(cycle) >= 2)
        self.assertIn("T-A", cycle)
        self.assertIn("T-B", cycle)

    def test_three_node_cycle(self):
        state = self._state([
            {"id": "T-B", "blocked_by": ["T-C"]},
            {"id": "T-C", "blocked_by": ["T-A"]},
        ])
        cycle = transitions.detect_cycle(state, "T-A", ["T-B"])
        self.assertTrue(len(cycle) >= 3)

    def test_no_cycle_linear_chain(self):
        state = self._state([
            {"id": "T-B", "blocked_by": []},
            {"id": "T-C", "blocked_by": []},
        ])
        cycle = transitions.detect_cycle(state, "T-A", ["T-B", "T-C"])
        self.assertEqual(cycle, [])

    def test_no_cycle_shared_ancestor_diamond(self):
        """T-A → T-B, T-A → T-C, T-B → T-D, T-C → T-D (diamond, no cycle)."""
        state = self._state([
            {"id": "T-A", "blocked_by": []},
            {"id": "T-B", "blocked_by": ["T-A"]},
            {"id": "T-C", "blocked_by": ["T-A"]},
        ])
        cycle = transitions.detect_cycle(state, "T-D", ["T-B", "T-C"])
        self.assertEqual(cycle, [])

    def test_nonexistent_pred_doesnt_false_positive(self):
        """Pred em blocked_by que nao existe no state: detect_cycle NAO reporta ciclo
        (pred missing eh validacao separada). Trata como folha."""
        state = self._state([])
        cycle = transitions.detect_cycle(state, "T-A", ["T-PHANTOM"])
        self.assertEqual(cycle, [])


class TestCanMoveToReady(unittest.TestCase):
    def _make_task(self, task_id, status="backlog", blocked_by=None):
        return {
            "id": task_id, "status": status,
            "dispatch_payload": {"blocked_by": blocked_by or []},
        }

    def _state(self, tasks):
        return {"tasks": tasks}

    def test_no_preds_can_move(self):
        task = self._make_task("T-A")
        state = self._state([task])
        ok, missing = transitions.can_move_to_ready(task, state)
        self.assertTrue(ok)
        self.assertEqual(missing, [])

    def test_all_preds_done_can_move(self):
        preds = [
            self._make_task("T-A", status="done"),
            self._make_task("T-B", status="done"),
        ]
        task = self._make_task("T-C", blocked_by=["T-A", "T-B"])
        state = self._state(preds + [task])
        ok, missing = transitions.can_move_to_ready(task, state)
        self.assertTrue(ok)

    def test_one_pred_not_done_blocks(self):
        preds = [
            self._make_task("T-A", status="done"),
            self._make_task("T-B", status="backlog"),
        ]
        task = self._make_task("T-C", blocked_by=["T-A", "T-B"])
        state = self._state(preds + [task])
        ok, missing = transitions.can_move_to_ready(task, state)
        self.assertFalse(ok)
        self.assertTrue(any("T-B" in m for m in missing))

    def test_pred_not_found_blocks(self):
        task = self._make_task("T-C", blocked_by=["T-PHANTOM"])
        state = self._state([task])
        ok, missing = transitions.can_move_to_ready(task, state)
        self.assertFalse(ok)
        self.assertTrue(any("not_found" in m for m in missing))

    def test_pred_rejected_blocks(self):
        preds = [self._make_task("T-A", status="rejected")]
        task = self._make_task("T-C", blocked_by=["T-A"])
        state = self._state(preds + [task])
        ok, missing = transitions.can_move_to_ready(task, state)
        self.assertFalse(ok)
        self.assertTrue(any("rejected" in m for m in missing))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar tests e confirmar FAIL**

```bash
cd ~/.openclaw/kanban-tasks
python3 -m unittest tests.test_transitions_blocked_by -v 2>&1 | tail -15
```

Expected: FAILs com `AttributeError: module 'lib.transitions' has no attribute 'validate_blocked_by_field'` (ou similar para detect_cycle / can_move_to_ready).

- [ ] **Step 3: Append novas funcs em `lib/transitions.py`**

Ler o final atual do arquivo. Adicionar DEPOIS da última função existente (`validate_or_raise`):

```python
# ================= Wave-5 helpers: blocked_by =================

def validate_blocked_by_field(value):
    """Valida o formato do campo dispatch_payload.blocked_by.

    Aceita:
    - None (ausente — valido)
    - list de strings com prefixo T-

    Retorna (valid: bool, errors: list[str]).
    """
    if value is None:
        return (True, [])
    if not isinstance(value, list):
        return (False, ["blocked_by_must_be_list"])
    errors = []
    for i, item in enumerate(value):
        if not isinstance(item, str) or not item.startswith("T-"):
            errors.append(f"blocked_by[{i}]_invalid")
    return (len(errors) == 0, errors)


def _blocked_by_of(task):
    """Extrai blocked_by de task (navegando dispatch_payload). Retorna lista."""
    dp = task.get("dispatch_payload") or {}
    return dp.get("blocked_by") or []


def detect_cycle(state, proposed_task_id, proposed_preds):
    """DFS topologica sobre o grafo blocked_by. Retorna path do ciclo (lista)
    ou [] se nao ha ciclo.

    proposed_task_id + proposed_preds representam uma proposta de mutacao
    (simula o grafo apos set-blocked-by). Sem side effect no state.

    Preds inexistentes no state sao tratados como folha (nao-cycle); gate
    de pred-not-found eh responsabilidade separada.
    """
    # Constroi grafo atual + substitui proposta
    graph = {}
    for t in state.get("tasks", []):
        graph[t["id"]] = list(_blocked_by_of(t))
    graph[proposed_task_id] = list(proposed_preds)

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {}

    def dfs(node, path):
        if color.get(node) == GRAY:
            # ciclo encontrado; retorna slice do path ate este node + ele
            start = path.index(node) if node in path else 0
            return path[start:] + [node]
        if color.get(node) == BLACK:
            return None
        color[node] = GRAY
        new_path = path + [node]
        for neighbor in graph.get(node, []):
            if neighbor not in graph:
                # pred nao existe no state → trata como folha (sem cycle)
                continue
            found = dfs(neighbor, new_path)
            if found:
                return found
        color[node] = BLACK
        return None

    return dfs(proposed_task_id, []) or []


def can_move_to_ready(task, state):
    """Retorna (ok: bool, missing_preds: list[str]).

    AND semantics: ok=True apenas se TODOS os preds do task estao status=done.
    Preds com status != done ou pred nao-existente contam como missing.
    """
    preds = _blocked_by_of(task)
    if not preds:
        return (True, [])
    missing = []
    by_id = {t["id"]: t for t in state.get("tasks", [])}
    for pred_id in preds:
        pred = by_id.get(pred_id)
        if pred is None:
            missing.append(f"{pred_id}:not_found")
            continue
        status = pred.get("status")
        if status != "done":
            missing.append(f"{pred_id}:{status}")
    return (len(missing) == 0, missing)
```

- [ ] **Step 4: Re-rodar tests e confirmar PASS**

```bash
python3 -m unittest tests.test_transitions_blocked_by -v 2>&1 | tail -5
```

Expected: `Ran 18 tests ... OK` (7 validate + 6 detect_cycle + 5 can_move_to_ready).

- [ ] **Step 5: Suite completa regressão**

```bash
python3 -m unittest discover tests -v 2>&1 | tail -5
```

Expected: 39/39 (21 pré-existentes + 18 novos).

---

## Phase 2 — Schema bump v2→v3 + rebuild default

### Task 3: Schema version bump + rebuild populando `blocked_by` default

**Files:**
- Modify: `~/.openclaw/kanban-tasks/lib/store.py` (constante schema_version em `_empty_state`)
- Modify: `~/.openclaw/kanban-tasks/lib/api.py` (`cmd_rebuild` garante default)
- Create: `~/.openclaw/kanban-tasks/tests/test_schema_v3_rebuild.py`

- [ ] **Step 1: Inspecionar `store.py::_empty_state` + `cmd_rebuild` atual**

```bash
grep -n "_empty_state\|schema_version\|cmd_rebuild" ~/.openclaw/kanban-tasks/lib/{store,api}.py | head -20
```

Reconhecer: `_empty_state` em store.py tem `"schema_version": 2` hardcoded; `cmd_rebuild` em api.py:411 replays events. Default de `blocked_by: []` não existe.

- [ ] **Step 2: Escrever tests em `tests/test_schema_v3_rebuild.py`**

```python
"""Tests schema v3 bump + rebuild popula blocked_by default (wave-5)."""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path


def _seed_v2_state(tmp):
    """Seed state.json v2 com tasks sem blocked_by em dispatch_payload."""
    seed = {
        "schema_version": 2,
        "projects": ["openclaw"],
        "sprints": [{"id": "sprint-1", "state": "current",
                     "start_date": "2026-04-21", "end_date": "2026-04-27",
                     "name": "test"}],
        "tasks": [
            {
                "id": "T-0001", "title": "legacy", "status": "backlog",
                "sprint_id": "sprint-1", "project": "openclaw",
                "description": "", "epic_id": None, "wave_ref": None,
                "created_at": "2026-04-21T00:00:00Z",
                "updated_at": "2026-04-21T00:00:00Z",
                "created_by": "test", "archived_at": None,
                "blocked": False, "blocked_reason": None, "blocked_at": None,
                "rejected_reason": None,
                "dispatch_payload": {"spec_ref": "x.md",
                                      "acceptance_criteria": ["AC"]},
                "test_result": None,
            },
            {
                "id": "T-0002", "title": "no payload", "status": "backlog",
                "sprint_id": "sprint-1", "project": "openclaw",
                "description": "", "epic_id": None, "wave_ref": None,
                "created_at": "2026-04-21T00:00:00Z",
                "updated_at": "2026-04-21T00:00:00Z",
                "created_by": "test", "archived_at": None,
                "blocked": False, "blocked_reason": None, "blocked_at": None,
                "rejected_reason": None, "dispatch_payload": None,
                "test_result": None,
            },
        ],
        "last_event_seq": 0,
    }
    (tmp / "state.json").write_text(json.dumps(seed))
    (tmp / "events.jsonl").write_text("")


def _reload_store():
    import importlib
    from lib import store as store_mod
    importlib.reload(store_mod)
    return store_mod


class TestSchemaV3EmptyState(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-schema-"))
        self._orig = os.environ.get("KANBAN_ROOT")
        os.environ["KANBAN_ROOT"] = str(self.tmp)

    def tearDown(self):
        if self._orig is None:
            os.environ.pop("KANBAN_ROOT", None)
        else:
            os.environ["KANBAN_ROOT"] = self._orig
        shutil.rmtree(self.tmp)

    def test_empty_state_uses_v3(self):
        store = _reload_store()
        empty = store._empty_state()
        self.assertEqual(empty["schema_version"], 3)


class TestRebuildPopulatesBlockedByDefault(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-rebuild-"))
        _seed_v2_state(self.tmp)
        self._orig = os.environ.get("KANBAN_ROOT")
        os.environ["KANBAN_ROOT"] = str(self.tmp)

    def tearDown(self):
        if self._orig is None:
            os.environ.pop("KANBAN_ROOT", None)
        else:
            os.environ["KANBAN_ROOT"] = self._orig
        shutil.rmtree(self.tmp)

    def _run_rebuild_cli(self):
        import subprocess
        CLI = os.path.expanduser("~/.openclaw/kanban-tasks/cli.sh")
        r = subprocess.run([CLI, "rebuild", "--json"],
                           env={**os.environ}, capture_output=True, text=True,
                           timeout=10)
        return r

    def test_rebuild_adds_blocked_by_default_to_existing_tasks(self):
        r = self._run_rebuild_cli()
        self.assertEqual(r.returncode, 0, f"stderr: {r.stderr}")
        # Apos rebuild, blocked_by deve existir como lista vazia
        state = json.loads((self.tmp / "state.json").read_text())
        self.assertEqual(state["schema_version"], 3)
        for t in state["tasks"]:
            dp = t.get("dispatch_payload") or {}
            self.assertIn("blocked_by", dp,
                          f"task {t['id']} sem blocked_by default")
            self.assertIsInstance(dp["blocked_by"], list)
            self.assertEqual(dp["blocked_by"], [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run tests — confirmar FAIL**

```bash
cd ~/.openclaw/kanban-tasks
python3 -m unittest tests.test_schema_v3_rebuild -v 2>&1 | tail -10
```

Expected: FAILs — schema_version ainda 2, blocked_by não populado.

- [ ] **Step 4: Modificar `lib/store.py::_empty_state`**

Localizar:
```python
def _empty_state():
    return {
        "schema_version": 2,
        ...
    }
```

Mudar `"schema_version": 2` para `"schema_version": 3`.

- [ ] **Step 5: Modificar `lib/api.py::cmd_rebuild` para popular default blocked_by + bump schema**

Localizar `cmd_rebuild` (linha ~411). Logo antes de `write_state_atomic(state)` (ou após o replay dos events), adicionar normalização:

```python
# Wave-5 schema v3 migration: garante blocked_by: [] default em toda task
state["schema_version"] = 3
for t in state.get("tasks", []):
    dp = t.get("dispatch_payload")
    if dp is None:
        t["dispatch_payload"] = {"blocked_by": []}
    elif "blocked_by" not in dp:
        dp["blocked_by"] = []
    elif dp["blocked_by"] is None:
        dp["blocked_by"] = []
```

(Posicionar DENTRO do mesmo `mutate_state` do rebuild existente ou onde o state é escrito.)

Ler o código atual de `cmd_rebuild` entre linhas 411-432 para posicionamento correto. Se ele já usa `mutate_state`, adicionar antes do `yield` exit. Se chama `write_state_atomic` direto, adicionar antes.

- [ ] **Step 6: Re-rodar tests schema**

```bash
python3 -m unittest tests.test_schema_v3_rebuild -v 2>&1 | tail -5
```

Expected: `Ran 2 tests ... OK`.

- [ ] **Step 7: Aplicar migração no runtime real (uma vez)**

```bash
~/.openclaw/kanban-tasks/cli.sh rebuild --json 2>&1 | tail -3
python3 -c "import json; s=json.load(open('~/.openclaw/kanban-tasks/state.json')); print('schema:', s['schema_version']); dp=s['tasks'][0].get('dispatch_payload'); print('first task blocked_by:', dp.get('blocked_by') if dp else 'NO_PAYLOAD')"
```

Expected: `schema: 3` + todas as 14 tasks agora têm `dispatch_payload.blocked_by: []`.

- [ ] **Step 8: Suite completa regressão**

```bash
python3 -m unittest discover tests -v 2>&1 | tail -5
```

Expected: 41/41 (39 + 2 schema).

---

## Phase 3 — Task integration: set_blocked_by + hooks atomic

### Task 4: `lib/task.py::set_blocked_by` — central write-path + cycle gate

**Files:**
- Modify: `~/.openclaw/kanban-tasks/lib/task.py` (nova func `set_blocked_by`)
- Create: `~/.openclaw/kanban-tasks/tests/test_set_blocked_by.py`

- [ ] **Step 1: Escrever tests integração em `tests/test_set_blocked_by.py`**

```python
"""Tests set_blocked_by: central write-path com cycle gate (wave-5)."""
import importlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path


def _seed(tmp, tasks_override=None):
    tasks = tasks_override or [
        {"id": "T-0001", "title": "A", "status": "backlog",
         "sprint_id": "sprint-1", "project": "openclaw",
         "description": "", "epic_id": None, "wave_ref": None,
         "created_at": "2026-04-22T00:00:00Z",
         "updated_at": "2026-04-22T00:00:00Z",
         "created_by": "test", "archived_at": None,
         "blocked": False, "blocked_reason": None, "blocked_at": None,
         "rejected_reason": None,
         "dispatch_payload": {"spec_ref": "x.md",
                              "acceptance_criteria": ["AC"],
                              "blocked_by": []},
         "test_result": None},
        {"id": "T-0002", "title": "B", "status": "backlog",
         "sprint_id": "sprint-1", "project": "openclaw",
         "description": "", "epic_id": None, "wave_ref": None,
         "created_at": "2026-04-22T00:00:00Z",
         "updated_at": "2026-04-22T00:00:00Z",
         "created_by": "test", "archived_at": None,
         "blocked": False, "blocked_reason": None, "blocked_at": None,
         "rejected_reason": None,
         "dispatch_payload": {"spec_ref": "y.md",
                              "acceptance_criteria": ["AC"],
                              "blocked_by": []},
         "test_result": None},
    ]
    seed = {
        "schema_version": 3,
        "projects": ["openclaw"],
        "sprints": [{"id": "sprint-1", "state": "current",
                     "start_date": "2026-04-21", "end_date": "2026-04-27",
                     "name": "test"}],
        "tasks": tasks,
        "last_event_seq": 0,
    }
    (tmp / "state.json").write_text(json.dumps(seed))
    (tmp / "events.jsonl").write_text("")


def _reload():
    from lib import store, transitions, task
    importlib.reload(store)
    importlib.reload(transitions)
    importlib.reload(task)
    return task


class TestSetBlockedBy(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-setbb-"))
        _seed(self.tmp)
        self._orig = os.environ.get("KANBAN_ROOT")
        os.environ["KANBAN_ROOT"] = str(self.tmp)

    def tearDown(self):
        if self._orig is None:
            os.environ.pop("KANBAN_ROOT", None)
        else:
            os.environ["KANBAN_ROOT"] = self._orig
        shutil.rmtree(self.tmp)

    def test_replace_preds_persists(self):
        task = _reload()
        res = task.set_blocked_by("T-0002", ["T-0001"], actor="test")
        self.assertTrue(res["ok"])
        self.assertEqual(res["task"]["dispatch_payload"]["blocked_by"],
                         ["T-0001"])
        # Event emitido
        events = (self.tmp / "events.jsonl").read_text().splitlines()
        set_events = [json.loads(l) for l in events
                      if json.loads(l).get("type") == "task_blocked_by_set"]
        self.assertEqual(len(set_events), 1)
        self.assertEqual(set_events[0]["payload"]["preds"], ["T-0001"])
        self.assertEqual(set_events[0]["payload"]["previous_preds"], [])

    def test_self_cycle_rejected(self):
        task = _reload()
        with self.assertRaises(task.TaskError) as ctx:
            task.set_blocked_by("T-0001", ["T-0001"], actor="test")
        self.assertEqual(ctx.exception.code, "CYCLE_DETECTED")

    def test_pred_not_found_rejected(self):
        task = _reload()
        with self.assertRaises(task.TaskError) as ctx:
            task.set_blocked_by("T-0001", ["T-9999"], actor="test")
        self.assertEqual(ctx.exception.code, "PRED_NOT_FOUND")
        # State intocado
        state = json.loads((self.tmp / "state.json").read_text())
        t1 = next(t for t in state["tasks"] if t["id"] == "T-0001")
        self.assertEqual(t1["dispatch_payload"]["blocked_by"], [])

    def test_task_not_found_rejected(self):
        task = _reload()
        with self.assertRaises(task.TaskError) as ctx:
            task.set_blocked_by("T-9999", ["T-0001"], actor="test")
        self.assertEqual(ctx.exception.code, "TASK_NOT_FOUND")

    def test_invalid_format_string_rejected(self):
        task = _reload()
        with self.assertRaises(task.TaskError) as ctx:
            task.set_blocked_by("T-0001", "T-0002", actor="test")
        self.assertEqual(ctx.exception.code, "BLOCKED_BY_INVALID")

    def test_event_carries_previous_preds_on_replace(self):
        task = _reload()
        task.set_blocked_by("T-0002", ["T-0001"], actor="test")
        task.set_blocked_by("T-0002", [], actor="test")
        events = (self.tmp / "events.jsonl").read_text().splitlines()
        set_events = [json.loads(l) for l in events
                      if json.loads(l).get("type") == "task_blocked_by_set"]
        self.assertEqual(len(set_events), 2)
        self.assertEqual(set_events[1]["payload"]["previous_preds"], ["T-0001"])
        self.assertEqual(set_events[1]["payload"]["preds"], [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar — confirmar FAIL (`set_blocked_by` não existe)**

```bash
cd ~/.openclaw/kanban-tasks
python3 -m unittest tests.test_set_blocked_by -v 2>&1 | tail -10
```

Expected: `AttributeError: module 'lib.task' has no attribute 'set_blocked_by'`.

- [ ] **Step 3: Adicionar `TaskError` class + `set_blocked_by` em `lib/task.py`**

Verificar se `TaskError` já existe em task.py. Se não, adicionar no topo (após imports):

```python
class TaskError(Exception):
    """Raised em erros semânticos de task ops (wave-5+).
    Attr `code` para mapping a exit code / HTTP status.
    """
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)
```

Adicionar a função `set_blocked_by` (coloque perto de outras setters, ex: depois de `set_dispatch_payload`):

```python
def set_blocked_by(task_id, preds, actor="unknown"):
    """Central write-path para blocked_by. Aplica validacao de formato,
    cycle detect universal, pred-not-found gate. Emite task_blocked_by_set.

    Args:
        task_id: target task.
        preds: list[str] de task_ids (preds).
        actor: quem origina.

    Raises:
        TaskError(CYCLE_DETECTED|PRED_NOT_FOUND|TASK_NOT_FOUND|BLOCKED_BY_INVALID).

    Returns:
        {"ok": True, "task": <task_dict>}
    """
    from lib import transitions

    # 1. Format validation (rejeita antes de abrir lock)
    valid, errors = transitions.validate_blocked_by_field(preds)
    if not valid:
        raise TaskError("BLOCKED_BY_INVALID",
                        f"blocked_by formato invalido: {errors}")

    with store.mutate_state() as state:
        # 2. Task exists
        t = find_task(state, task_id)
        if t is None:
            raise TaskError("TASK_NOT_FOUND", f"task nao existe: {task_id}")

        # 3. Pred existence
        by_id = {x["id"]: x for x in state["tasks"]}
        missing_preds = [p for p in preds if p not in by_id]
        if missing_preds:
            raise TaskError("PRED_NOT_FOUND",
                            f"preds nao existem: {missing_preds}")

        # 4. Cycle detect universal (inclui proposta no grafo)
        cycle = transitions.detect_cycle(state, task_id, preds)
        if cycle:
            raise TaskError("CYCLE_DETECTED",
                            f"ciclo detectado: {' -> '.join(cycle)}")

        # 5. Apply mutation + event (atomic dentro do mesmo mutate_state)
        dp = t.get("dispatch_payload") or {}
        previous = list(dp.get("blocked_by") or [])
        dp["blocked_by"] = list(preds)
        t["dispatch_payload"] = dp
        t["updated_at"] = store.now_iso()
        seq = store.next_seq(state)
        state["last_event_seq"] = seq
        store.append_event({
            "seq": seq, "ts": store.now_iso(),
            "type": "task_blocked_by_set", "actor": actor,
            "task_id": task_id, "preds": list(preds),
            "previous_preds": previous,
        })
        return {"ok": True, "task": t}
```

Nota: `append_event` dentro do `with mutate_state() as state:` MAIS `state["last_event_seq"] = seq`. Isso é crítico — wave-4 lição. Não usar `store.append_event` standalone fora do bloco.

- [ ] **Step 4: Re-rodar tests e confirmar 6/6 PASS**

```bash
python3 -m unittest tests.test_set_blocked_by -v 2>&1 | tail -5
```

Expected: `Ran 6 tests ... OK`.

- [ ] **Step 5: Suite completa regressão**

```bash
python3 -m unittest discover tests -v 2>&1 | tail -5
```

Expected: 47/47 (41 prev + 6 new).

### Task 5: Hooks atomic — auto-release + auto-block em task move + archive

**Files:**
- Modify: `~/.openclaw/kanban-tasks/lib/task.py` (hook handlers + integração em `move`, `archive`)
- Create: `~/.openclaw/kanban-tasks/tests/test_blocked_by_hooks.py`

- [ ] **Step 1: Escrever tests em `tests/test_blocked_by_hooks.py`**

```python
"""Tests hooks auto-release + auto-block upstream (wave-5 §3.3)."""
import importlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path


def _seed_abc(tmp):
    """T-A (backlog), T-B blocked_by=[T-A] (backlog), T-C blocked_by=[T-A, T-B] (backlog)."""
    tasks = [
        {"id": "T-A", "title": "A", "status": "backlog",
         "sprint_id": "sprint-1", "project": "openclaw",
         "description": "", "epic_id": None, "wave_ref": None,
         "created_at": "2026-04-22T00:00:00Z",
         "updated_at": "2026-04-22T00:00:00Z",
         "created_by": "test", "archived_at": None,
         "blocked": False, "blocked_reason": None, "blocked_at": None,
         "rejected_reason": None,
         "dispatch_payload": {"spec_ref": "a.md",
                              "acceptance_criteria": ["AC"],
                              "blocked_by": []},
         "test_result": None},
        {"id": "T-B", "title": "B", "status": "backlog",
         "sprint_id": "sprint-1", "project": "openclaw",
         "description": "", "epic_id": None, "wave_ref": None,
         "created_at": "2026-04-22T00:00:00Z",
         "updated_at": "2026-04-22T00:00:00Z",
         "created_by": "test", "archived_at": None,
         "blocked": False, "blocked_reason": None, "blocked_at": None,
         "rejected_reason": None,
         "dispatch_payload": {"spec_ref": "b.md",
                              "acceptance_criteria": ["AC"],
                              "blocked_by": ["T-A"]},
         "test_result": None},
        {"id": "T-C", "title": "C", "status": "backlog",
         "sprint_id": "sprint-1", "project": "openclaw",
         "description": "", "epic_id": None, "wave_ref": None,
         "created_at": "2026-04-22T00:00:00Z",
         "updated_at": "2026-04-22T00:00:00Z",
         "created_by": "test", "archived_at": None,
         "blocked": False, "blocked_reason": None, "blocked_at": None,
         "rejected_reason": None,
         "dispatch_payload": {"spec_ref": "c.md",
                              "acceptance_criteria": ["AC"],
                              "blocked_by": ["T-A", "T-B"]},
         "test_result": None},
    ]
    seed = {
        "schema_version": 3,
        "projects": ["openclaw"],
        "sprints": [{"id": "sprint-1", "state": "current",
                     "start_date": "2026-04-21", "end_date": "2026-04-27",
                     "name": "test"}],
        "tasks": tasks,
        "last_event_seq": 0,
    }
    (tmp / "state.json").write_text(json.dumps(seed))
    (tmp / "events.jsonl").write_text("")


def _reload():
    from lib import store, transitions, task
    importlib.reload(store); importlib.reload(transitions); importlib.reload(task)
    return task


class TestAutoRelease(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-hook-"))
        _seed_abc(self.tmp)
        self._orig = os.environ.get("KANBAN_ROOT")
        os.environ["KANBAN_ROOT"] = str(self.tmp)

    def tearDown(self):
        if self._orig is None:
            os.environ.pop("KANBAN_ROOT", None)
        else:
            os.environ["KANBAN_ROOT"] = self._orig
        shutil.rmtree(self.tmp)

    def _statuses(self):
        st = json.loads((self.tmp / "state.json").read_text())
        return {t["id"]: t["status"] for t in st["tasks"]}

    def test_done_releases_ready_dependent_with_single_pred(self):
        task = _reload()
        # T-A faz caminho backlog → ready → in_progress → testing → done
        task.move("T-A", "ready", actor="test")
        task.move("T-A", "in_progress", actor="test")
        task.move("T-A", "testing", actor="test")
        task.move("T-A", "done", actor="test")
        statuses = self._statuses()
        self.assertEqual(statuses["T-A"], "done")
        # T-B tinha blocked_by=[T-A]; agora deve ter sido auto-released pra ready
        self.assertEqual(statuses["T-B"], "ready")

    def test_done_does_not_release_dependent_with_partial_preds(self):
        task = _reload()
        # T-A done mas T-C depende de [T-A, T-B] e T-B ainda backlog
        for to in ["ready", "in_progress", "testing", "done"]:
            task.move("T-A", to, actor="test")
        statuses = self._statuses()
        self.assertEqual(statuses["T-A"], "done")
        self.assertEqual(statuses["T-C"], "backlog")  # NAO released

    def test_event_task_blocked_by_auto_released_emitted(self):
        task = _reload()
        for to in ["ready", "in_progress", "testing", "done"]:
            task.move("T-A", to, actor="test")
        events = (self.tmp / "events.jsonl").read_text().splitlines()
        release_events = [json.loads(l) for l in events
                          if json.loads(l).get("type") == "task_blocked_by_auto_released"]
        self.assertEqual(len(release_events), 1)
        self.assertEqual(release_events[0]["payload"]["task_id"], "T-B")
        self.assertEqual(release_events[0]["payload"]["trigger_pred"], "T-A")


class TestAutoBlockUpstreamRejected(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-upr-"))
        _seed_abc(self.tmp)
        self._orig = os.environ.get("KANBAN_ROOT")
        os.environ["KANBAN_ROOT"] = str(self.tmp)

    def tearDown(self):
        if self._orig is None:
            os.environ.pop("KANBAN_ROOT", None)
        else:
            os.environ["KANBAN_ROOT"] = self._orig
        shutil.rmtree(self.tmp)

    def test_rejected_blocks_dependents(self):
        task = _reload()
        task.move("T-A", "rejected", actor="test")
        state = json.loads((self.tmp / "state.json").read_text())
        by_id = {t["id"]: t for t in state["tasks"]}
        # T-B e T-C tinham T-A como pred; ambos devem estar blocked=True
        self.assertTrue(by_id["T-B"]["blocked"])
        self.assertIn("upstream_rejected: T-A", by_id["T-B"]["blocked_reason"])
        self.assertTrue(by_id["T-C"]["blocked"])
        self.assertIn("upstream_rejected: T-A", by_id["T-C"]["blocked_reason"])

    def test_rejected_emits_upstream_failed_events(self):
        task = _reload()
        task.move("T-A", "rejected", actor="test")
        events = (self.tmp / "events.jsonl").read_text().splitlines()
        upstream_events = [json.loads(l) for l in events
                           if json.loads(l).get("type") == "task_blocked_upstream_failed"]
        self.assertEqual(len(upstream_events), 2)  # T-B + T-C
        task_ids = {e["payload"]["task_id"] for e in upstream_events}
        self.assertEqual(task_ids, {"T-B", "T-C"})


class TestAutoBlockUpstreamArchived(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-upa-"))
        _seed_abc(self.tmp)
        self._orig = os.environ.get("KANBAN_ROOT")
        os.environ["KANBAN_ROOT"] = str(self.tmp)

    def tearDown(self):
        if self._orig is None:
            os.environ.pop("KANBAN_ROOT", None)
        else:
            os.environ["KANBAN_ROOT"] = self._orig
        shutil.rmtree(self.tmp)

    def test_archived_blocks_dependents(self):
        task = _reload()
        task.archive("T-A", reason="wave-5 smoke", actor="test")
        state = json.loads((self.tmp / "state.json").read_text())
        by_id = {t["id"]: t for t in state["tasks"]}
        self.assertTrue(by_id["T-B"]["blocked"])
        self.assertIn("upstream_rejected: T-A", by_id["T-B"]["blocked_reason"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar — confirmar FAIL (hooks não existem ainda)**

```bash
python3 -m unittest tests.test_blocked_by_hooks -v 2>&1 | tail -15
```

Expected: 6 FAILs. T-B e T-C permanecem backlog após T-A done; T-B permanece unblocked após T-A rejected/archived; eventos não emitidos.

- [ ] **Step 3: Adicionar hooks + integrar em `move` e `archive`**

Adicionar DENTRO de `lib/task.py` (helpers privados, depois de imports):

```python
def _auto_release_dependents(state, trigger_pred_id, actor):
    """Hook atomic: trigger_pred virou done. Varre dependentes; se TODOS
    os preds agora done, promove pra ready (+unblock se flag blocked).

    Emite task_blocked_by_auto_released. Chamado DENTRO do mesmo mutate_state
    do task_moved que triggerou. `state["last_event_seq"]` atualizado
    sequencialmente.
    """
    from lib import transitions
    for t in state["tasks"]:
        preds = (t.get("dispatch_payload") or {}).get("blocked_by") or []
        if trigger_pred_id not in preds:
            continue
        if t.get("status") not in ("backlog", "ready"):
            # ja saiu de backlog; nao promove (pode estar in_progress/testing/done)
            continue
        ok, _missing = transitions.can_move_to_ready(t, state)
        if not ok:
            continue
        # Promove atomic
        t["status"] = "ready"
        t["updated_at"] = store.now_iso()
        if t.get("blocked"):
            t["blocked"] = False
            t["blocked_reason"] = None
            t["blocked_at"] = None
        seq = store.next_seq(state)
        state["last_event_seq"] = seq
        store.append_event({
            "seq": seq, "ts": store.now_iso(),
            "type": "task_blocked_by_auto_released", "actor": actor or "system",
            "task_id": t["id"], "trigger_pred": trigger_pred_id,
            "preds": list(preds),
        })


def _block_dependents_upstream_failed(state, trigger_pred_id, failure_status, actor):
    """Hook atomic: trigger_pred virou rejected OR foi archive. Marca todos
    os dependentes nao-terminais como blocked com reason upstream_rejected.
    Emite task_blocked_upstream_failed.
    """
    for t in state["tasks"]:
        preds = (t.get("dispatch_payload") or {}).get("blocked_by") or []
        if trigger_pred_id not in preds:
            continue
        if t.get("status") in ("done", "rejected") or t.get("archived_at"):
            continue  # terminal; nao mexe
        # Block flag
        t["blocked"] = True
        t["blocked_reason"] = f"upstream_rejected: {trigger_pred_id}"
        t["blocked_at"] = store.now_iso()
        t["updated_at"] = store.now_iso()
        # Tag dispatch_payload pro historico
        dp = t.get("dispatch_payload") or {}
        dp["upstream_failure"] = {
            "failed_pred": trigger_pred_id,
            "failure_status": failure_status,
            "detected_at": store.now_iso(),
        }
        t["dispatch_payload"] = dp
        seq = store.next_seq(state)
        state["last_event_seq"] = seq
        store.append_event({
            "seq": seq, "ts": store.now_iso(),
            "type": "task_blocked_upstream_failed", "actor": actor or "system",
            "task_id": t["id"], "failed_pred": trigger_pred_id,
            "failure_status": failure_status,
        })
```

Agora **integrar nos métodos `move` e `archive` existentes**. Localizar a função `move` em task.py:

Pseudo-código do patch (a ser aplicado no contexto real — ler o código atual e ajustar localmente):
```python
def move(task_id, to_status, ..., actor=...):
    with store.mutate_state() as state:
        # ... código existente: encontra task, valida transição, muda status ...
        t["status"] = to_status
        # ... append_event task_moved existente ...

        # Wave-5 HOOK atomic — DENTRO do mesmo mutate_state
        if to_status == "done":
            _auto_release_dependents(state, task_id, actor)
        elif to_status == "rejected":
            _block_dependents_upstream_failed(state, task_id, "rejected", actor)
```

Para `archive`:
```python
def archive(task_id, reason, actor=...):
    with store.mutate_state() as state:
        # ... código existente: seta archived_at + append_event task_archived ...

        # Wave-5 HOOK atomic
        _block_dependents_upstream_failed(state, task_id, "archived", actor)
```

Importante: ler o código real de `move` e `archive` em `lib/task.py` antes de editar (linha exata pode variar). Adicionar hook chamada AO FINAL do bloco `with store.mutate_state`, APÓS o append do evento principal (task_moved / task_archived), mas ANTES da saída do `with`.

- [ ] **Step 4: Re-rodar tests e confirmar 6/6 PASS**

```bash
python3 -m unittest tests.test_blocked_by_hooks -v 2>&1 | tail -5
```

Expected: `Ran 6 tests ... OK`.

- [ ] **Step 5: Suite completa — zero regressão**

```bash
python3 -m unittest discover tests -v 2>&1 | tail -5
```

Expected: 53/53 (47 + 6 hooks).

### Task 6: Ciclo gate em `set_dispatch_payload` (fechar loophole)

**Files:**
- Modify: `~/.openclaw/kanban-tasks/lib/task.py::set_dispatch_payload`
- Modify: `~/.openclaw/kanban-tasks/tests/test_blocked_by_hooks.py` (append 2 tests)

- [ ] **Step 1: Escrever tests (append ao arquivo existente)**

Adicionar nova classe ao `tests/test_blocked_by_hooks.py`:

```python
class TestSetDispatchPayloadCycleGate(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-sdp-gate-"))
        _seed_abc(self.tmp)
        self._orig = os.environ.get("KANBAN_ROOT")
        os.environ["KANBAN_ROOT"] = str(self.tmp)

    def tearDown(self):
        if self._orig is None:
            os.environ.pop("KANBAN_ROOT", None)
        else:
            os.environ["KANBAN_ROOT"] = self._orig
        shutil.rmtree(self.tmp)

    def test_set_dispatch_payload_with_cycle_rejected(self):
        """Loophole fechado wave-5: set-dispatch-payload com blocked_by
        formando ciclo deve ser rejeitado pelo mesmo gate de set-blocked-by."""
        task = _reload()
        # T-B ja tem blocked_by=[T-A]. Tentar set-dispatch-payload em T-A
        # com blocked_by=[T-B] deve formar ciclo e ser rejeitado.
        with self.assertRaises(task.TaskError) as ctx:
            task.set_dispatch_payload(
                "T-A",
                {"spec_ref": "a.md",
                 "acceptance_criteria": ["AC"],
                 "blocked_by": ["T-B"]},
                merge=False, actor="test",
            )
        self.assertEqual(ctx.exception.code, "CYCLE_DETECTED")

    def test_set_dispatch_payload_without_blocked_by_change_ok(self):
        """Se set_dispatch_payload nao mexe em blocked_by, gate de ciclo
        nao dispara (nao re-valida grafo atual)."""
        task = _reload()
        # T-B ja tem blocked_by=[T-A]; mantem no novo payload
        res = task.set_dispatch_payload(
            "T-B",
            {"spec_ref": "b-new.md",
             "acceptance_criteria": ["AC-new"],
             "blocked_by": ["T-A"]},
            merge=False, actor="test",
        )
        self.assertTrue(res["ok"])
```

- [ ] **Step 2: Rodar — confirmar FAIL (gate não plugado ainda)**

```bash
python3 -m unittest tests.test_blocked_by_hooks -v 2>&1 | tail -10
```

Expected: `test_set_dispatch_payload_with_cycle_rejected` FAIL (sem exception).

- [ ] **Step 3: Modificar `set_dispatch_payload` em `lib/task.py`**

Localizar a função `set_dispatch_payload` (linha ~420). Adicionar gate de ciclo entre a validação de payload e a mutação do state. Padrão:

```python
def set_dispatch_payload(task_id, payload, merge=False, actor="unknown"):
    # ... código existente: validação basic ...
    if not isinstance(payload, dict):
        raise ValueError(...)

    with store.mutate_state() as state:
        t = find_task(state, task_id)
        if t is None:
            raise ValueError(f"task not found: {task_id}")

        existing = t.get("dispatch_payload") or {}
        new_payload = {**existing, **payload} if merge else payload

        # === Wave-5: validar format + cycle se blocked_by presente ===
        if "blocked_by" in new_payload:
            from lib import transitions
            bb = new_payload.get("blocked_by")
            valid, errors = transitions.validate_blocked_by_field(bb)
            if not valid:
                raise TaskError("BLOCKED_BY_INVALID",
                                f"blocked_by invalido: {errors}")
            # Pred existence
            by_id = {x["id"]: x for x in state["tasks"]}
            missing_preds = [p for p in (bb or []) if p not in by_id]
            if missing_preds:
                raise TaskError("PRED_NOT_FOUND",
                                f"preds nao existem: {missing_preds}")
            # Cycle detect
            cycle = transitions.detect_cycle(state, task_id, bb or [])
            if cycle:
                raise TaskError("CYCLE_DETECTED",
                                f"ciclo detectado: {' -> '.join(cycle)}")

        # ... código existente continua: aplica new_payload, emit task_dispatch_payload_set ...
```

Importante: `TaskError` já foi criado na Task 4. `from lib import transitions` import local evita circular.

Nota: se `set_dispatch_payload` já raise `ValueError` em alguns paths, pode-se manter compat convertendo ou preferir `TaskError` uniforme. Confirme o padrão ao ler o código real.

- [ ] **Step 4: Re-rodar e confirmar 8/8 pass (6 hooks + 2 gate)**

```bash
python3 -m unittest tests.test_blocked_by_hooks -v 2>&1 | tail -5
```

Expected: `Ran 8 tests ... OK`.

- [ ] **Step 5: Suite completa**

```bash
python3 -m unittest discover tests -v 2>&1 | tail -5
```

Expected: 55/55.

---

## Phase 4 — CLI `cmd_task_set_blocked_by`

### Task 7: CLI set-blocked-by com --preds / --add / --remove

**Files:**
- Modify: `~/.openclaw/kanban-tasks/lib/api.py` (cmd + argparse + error mapping)
- Create: `~/.openclaw/kanban-tasks/tests/test_cmd_set_blocked_by.py`

- [ ] **Step 1: Escrever tests end-to-end subprocess**

```python
"""Tests CLI task set-blocked-by (wave-5)."""
import importlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


CLI = os.path.expanduser("~/.openclaw/kanban-tasks/cli.sh")


def _seed_two_tasks(tmp):
    tasks = [
        {"id": "T-0001", "title": "A", "status": "backlog",
         "sprint_id": "sprint-1", "project": "openclaw",
         "description": "", "epic_id": None, "wave_ref": None,
         "created_at": "2026-04-22T00:00:00Z",
         "updated_at": "2026-04-22T00:00:00Z",
         "created_by": "test", "archived_at": None,
         "blocked": False, "blocked_reason": None, "blocked_at": None,
         "rejected_reason": None,
         "dispatch_payload": {"spec_ref": "a.md",
                              "acceptance_criteria": ["AC"],
                              "blocked_by": []},
         "test_result": None},
        {"id": "T-0002", "title": "B", "status": "backlog",
         "sprint_id": "sprint-1", "project": "openclaw",
         "description": "", "epic_id": None, "wave_ref": None,
         "created_at": "2026-04-22T00:00:00Z",
         "updated_at": "2026-04-22T00:00:00Z",
         "created_by": "test", "archived_at": None,
         "blocked": False, "blocked_reason": None, "blocked_at": None,
         "rejected_reason": None,
         "dispatch_payload": {"spec_ref": "b.md",
                              "acceptance_criteria": ["AC"],
                              "blocked_by": []},
         "test_result": None},
    ]
    seed = {
        "schema_version": 3,
        "projects": ["openclaw"],
        "sprints": [{"id": "sprint-1", "state": "current",
                     "start_date": "2026-04-21", "end_date": "2026-04-27",
                     "name": "test"}],
        "tasks": tasks, "last_event_seq": 0,
    }
    (tmp / "state.json").write_text(json.dumps(seed))
    (tmp / "events.jsonl").write_text("")


class TestCmdSetBlockedBy(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-cli-sbb-"))
        _seed_two_tasks(self.tmp)
        self.env = {**os.environ, "KANBAN_ROOT": str(self.tmp)}

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _run(self, *args):
        return subprocess.run([CLI, *args], env=self.env,
                              capture_output=True, text=True, timeout=10)

    def test_preds_replaces(self):
        r = self._run("task", "set-blocked-by", "T-0002", "--preds", "T-0001",
                      "--actor", "test", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        state = json.loads((self.tmp / "state.json").read_text())
        t2 = next(t for t in state["tasks"] if t["id"] == "T-0002")
        self.assertEqual(t2["dispatch_payload"]["blocked_by"], ["T-0001"])

    def test_add_appends(self):
        self._run("task", "set-blocked-by", "T-0002", "--preds", "T-0001",
                  "--actor", "test", "--json")
        # create T-0003 seed before? Simplify: use add w/ existing T-0001 (no-op)
        r = self._run("task", "set-blocked-by", "T-0002", "--add", "T-0001",
                      "--actor", "test", "--json")
        # Idempotent add: T-0001 ja presente -> preds continua [T-0001]
        self.assertEqual(r.returncode, 0)
        state = json.loads((self.tmp / "state.json").read_text())
        t2 = next(t for t in state["tasks"] if t["id"] == "T-0002")
        self.assertEqual(t2["dispatch_payload"]["blocked_by"], ["T-0001"])

    def test_remove_deletes_pred(self):
        self._run("task", "set-blocked-by", "T-0002", "--preds", "T-0001",
                  "--actor", "test", "--json")
        r = self._run("task", "set-blocked-by", "T-0002", "--remove", "T-0001",
                      "--actor", "test", "--json")
        self.assertEqual(r.returncode, 0)
        state = json.loads((self.tmp / "state.json").read_text())
        t2 = next(t for t in state["tasks"] if t["id"] == "T-0002")
        self.assertEqual(t2["dispatch_payload"]["blocked_by"], [])

    def test_self_cycle_exit_1(self):
        r = self._run("task", "set-blocked-by", "T-0001", "--preds", "T-0001",
                      "--actor", "test", "--json")
        self.assertEqual(r.returncode, 1)
        parsed = json.loads(r.stdout)
        self.assertEqual(parsed["code"], "CYCLE_DETECTED")

    def test_pred_not_found_exit_1(self):
        r = self._run("task", "set-blocked-by", "T-0001", "--preds", "T-9999",
                      "--actor", "test", "--json")
        self.assertEqual(r.returncode, 1)
        parsed = json.loads(r.stdout)
        self.assertEqual(parsed["code"], "PRED_NOT_FOUND")

    def test_preds_and_add_mutually_exclusive(self):
        r = self._run("task", "set-blocked-by", "T-0001",
                      "--preds", "T-0002", "--add", "T-0003",
                      "--actor", "test", "--json")
        # argparse ou cmd rejeita combinação
        self.assertNotEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar — confirmar FAIL (subcmd não existe)**

```bash
cd ~/.openclaw/kanban-tasks
python3 -m unittest tests.test_cmd_set_blocked_by -v 2>&1 | tail -10
```

Expected: argparse error `invalid choice: 'set-blocked-by'`.

- [ ] **Step 3: Adicionar `cmd_task_set_blocked_by` em `lib/api.py`**

Perto de outras cmds de task (ex: após `cmd_task_set_dispatch_payload`), adicionar:

```python
def cmd_task_set_blocked_by(args: argparse.Namespace) -> int:
    """Seta dispatch_payload.blocked_by com validacao + cycle gate.

    --preds P1,P2 (substitui), --add P (append), --remove P (delete).
    Mutuamente exclusivos.
    """
    task_lib = task  # alias (ajustar se task_lib ja import)
    # Mutex check: exatamente um de preds/add/remove
    set_flags = [args.preds is not None, args.add is not None,
                 args.remove is not None]
    if sum(set_flags) != 1:
        return _err("exatamente um de --preds/--add/--remove obrigatorio",
                    "invalid_input", args.json)

    from lib import task as task_lib
    try:
        current = task_lib.find_task(store.read_state(), args.task_id)
    except Exception:
        current = None
    if current is None:
        return _err(f"task not found: {args.task_id}",
                    "TASK_NOT_FOUND", args.json)

    existing_preds = list(
        (current.get("dispatch_payload") or {}).get("blocked_by") or []
    )

    if args.preds is not None:
        new_preds = [p.strip() for p in args.preds.split(",") if p.strip()]
    elif args.add is not None:
        new_preds = list(existing_preds)
        if args.add not in new_preds:
            new_preds.append(args.add)
    else:  # remove
        new_preds = [p for p in existing_preds if p != args.remove]

    try:
        res = task_lib.set_blocked_by(args.task_id, new_preds,
                                      actor=args.actor or "unknown")
    except task_lib.TaskError as e:
        return _err(str(e), e.code, args.json)

    _print(res, args.json, f"blocked_by set: {args.task_id} -> {new_preds}")
    return EXIT_OK
```

Agora **argparse subcmd**. Localizar onde `task set-dispatch-payload` é registrado (linha ~650 em api.py). Registrar `task set-blocked-by` em posição análoga:

```python
    sbb = leaf(tk_sub, "set-blocked-by")
    sbb.add_argument("task_id")
    group = sbb.add_mutually_exclusive_group(required=True)
    group.add_argument("--preds", help="CSV de task_ids (substitui)")
    group.add_argument("--add", help="1 task_id a acrescentar")
    group.add_argument("--remove", help="1 task_id a remover")
    sbb.set_defaults(func=cmd_task_set_blocked_by)
```

**Error mapping:** adicionar no `_err` handler (se usa if/elif como na wave-4):

```python
if code in ("CYCLE_DETECTED", "PRED_NOT_FOUND", "BLOCKED_BY_INVALID",
            "TASK_NOT_FOUND", "BLOCKED_BY_UNRESOLVED"):
    return EXIT_INPUT  # exit 1
```

(Mapear se existir dict; senão estender o if/elif chain.)

- [ ] **Step 4: Re-rodar tests — 6/6 PASS**

```bash
python3 -m unittest tests.test_cmd_set_blocked_by -v 2>&1 | tail -5
```

Expected: `Ran 6 tests ... OK`.

- [ ] **Step 5: Rodar suite completa**

```bash
python3 -m unittest discover tests -v 2>&1 | tail -5
```

Expected: 61/61.

- [ ] **Step 6: Sanity CLI help**

```bash
~/.openclaw/kanban-tasks/cli.sh task set-blocked-by --help 2>&1 | head -15
```

Expected: argparse help listando `--preds`, `--add`, `--remove`.

---

## Phase 5 — MC HTTP `/blocked-by` route

### Task 8: MC route PUT /api/kanban/tasks/[id]/blocked-by + type extension

**Files:**
- Create: `~/code/mission-control/src/app/api/kanban/tasks/[id]/blocked-by/route.ts`
- Modify: `~/code/mission-control/src/lib/kanban/stateReader.ts` (Task type ganha blocked_by)

- [ ] **Step 1: Ver tipo Task atual**

```bash
grep -n "export type Task\|export interface Task\|blocked_by" ~/code/mission-control/src/lib/kanban/stateReader.ts | head -10
```

Expected: tipo Task existe; `blocked_by` ausente.

- [ ] **Step 2: Modificar `stateReader.ts` — adicionar campo em DispatchPayload**

Localizar definição do Task type ou DispatchPayload type. Adicionar `blocked_by?: string[]` no shape de `dispatch_payload`:

```typescript
// Se existe type DispatchPayload separado:
export type DispatchPayload = {
  spec_ref?: string | string[];
  acceptance_criteria?: string[];
  blocked_by?: string[];
  // ... outros campos existentes
  [key: string]: unknown;
};

// Ou inline no Task:
export type Task = {
  // ... existente
  dispatch_payload?: {
    spec_ref?: string | string[];
    acceptance_criteria?: string[];
    blocked_by?: string[];
    [key: string]: unknown;
  } | null;
};
```

Escolher conforme o shape atual. Fazer a extensão mínima (adicionar só `blocked_by?`).

- [ ] **Step 3: Criar `src/app/api/kanban/tasks/[id]/blocked-by/route.ts`**

Conteúdo completo:

```typescript
import { NextResponse, NextRequest } from "next/server";
import { runCli, respondCli } from "@/lib/kanban/cli";
import { resolveActor } from "@/lib/kanban/auth";

export const dynamic = "force-dynamic";

/**
 * PUT /api/kanban/tasks/[id]/blocked-by
 * body: { preds?: string[], add?: string, remove?: string }
 *
 * Exatamente um dos tres flags deve estar presente. Forward pro CLI
 * `task set-blocked-by`. Mapping de exit-code para HTTP via cli.ts:
 *   - CYCLE_DETECTED, PRED_NOT_FOUND, BLOCKED_BY_INVALID → 422
 *     (sobrepõe default exit1→400 via check de code em respondCli se necessario)
 */
export async function PUT(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  if (!id || !id.startsWith("T-")) {
    return NextResponse.json(
      { error: "invalid_input", detail: "task id deve ser T-NNNN" },
      { status: 400 },
    );
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json(
      { error: "invalid_input", detail: "expected JSON body" },
      { status: 400 },
    );
  }

  const bb = (body ?? {}) as Record<string, unknown>;
  const hasPreds = Array.isArray(bb.preds);
  const hasAdd = typeof bb.add === "string";
  const hasRemove = typeof bb.remove === "string";
  const count = [hasPreds, hasAdd, hasRemove].filter(Boolean).length;
  if (count !== 1) {
    return NextResponse.json(
      {
        error: "invalid_input",
        detail: "exatamente um de preds | add | remove obrigatorio",
      },
      { status: 400 },
    );
  }

  const args = ["task", "set-blocked-by", id];
  if (hasPreds) {
    const preds = (bb.preds as unknown[]).filter(
      (p): p is string => typeof p === "string",
    );
    args.push("--preds", preds.join(","));
  } else if (hasAdd) {
    args.push("--add", bb.add as string);
  } else if (hasRemove) {
    args.push("--remove", bb.remove as string);
  }

  const result = runCli(args, resolveActor(req));
  // cli.ts mapeia exit 1 → 400 por default; promover codigos
  // PAYLOAD_INCOMPLETE / BLOCKED_BY / CYCLE_DETECTED / PRED_NOT_FOUND para 422.
  if (!result.ok) {
    const code = result.code;
    if (code === "CYCLE_DETECTED" || code === "PRED_NOT_FOUND" ||
        code === "BLOCKED_BY_INVALID") {
      return NextResponse.json(
        { error: "blocked_by_invalid", code, detail: result.error },
        { status: 422 },
      );
    }
  }
  return respondCli(result);
}
```

- [ ] **Step 4: tsc check**

```bash
cd ~/code/mission-control
npx tsc --noEmit 2>&1 | grep -E "route\.ts|stateReader\.ts|payload-gate" | head -10
```

Expected: zero errors relacionados aos arquivos wave-5.

- [ ] **Step 5: Vitest — nenhum novo teste pra esse route (integração E2E cobre)**

```bash
npm test -- --run 2>&1 | tail -10
```

Expected: baseline verde (87/87 ou atual número).

---

## Phase 6 — UI minimal deps display

### Task 9: Card exibe `deps: T-X, T-Y` quando blocked_by não vazio

**Files:**
- Modify: `~/code/mission-control/src/app/(dashboard)/kanban/page.tsx` (render do card)

- [ ] **Step 1: Localizar onde o card renderiza (provavelmente um componente TaskCard ou inline no page.tsx)**

```bash
grep -n "blocked_reason\|task.blocked\|TaskCard" ~/code/mission-control/src/app/\(dashboard\)/kanban/page.tsx | head -10
```

Expected: referências ao rendering das cards (linhas ~430-500 baseado em probes anteriores).

- [ ] **Step 2: Adicionar linha de `deps:` no render**

Onde task.blocked_reason é mostrado (~linha 437-446), adicionar ao lado ou abaixo:

```tsx
{task.dispatch_payload?.blocked_by && task.dispatch_payload.blocked_by.length > 0 && (
  <div className="text-xs text-muted-foreground">
    deps: {task.dispatch_payload.blocked_by.join(", ")}
  </div>
)}
```

Adaptar classes Tailwind ao estilo existente (usar mesma hierarquia de `text-xs text-muted-foreground` ou similar presente em outros subcampos do card).

- [ ] **Step 3: tsc + vitest**

```bash
cd ~/code/mission-control
npx tsc --noEmit 2>&1 | grep -E "kanban/page\.tsx" | head -5
npm test -- --run 2>&1 | tail -5
```

Expected: zero errors + baseline vitest.

- [ ] **Step 4: Smoke manual opcional** — se MC dev server rodando, abrir `/kanban` e verificar que task com blocked_by mostra a linha `deps:`. Pode ser deferido.

---

## Phase 7 — Smoke + delivery

### Task 10: Smoke E2E integrado (spec §5 cenários)

**Files:** nenhum (execução).

- [ ] **Step 1: Setup — tmpdir isolado para smoke**

```bash
TMP=$(mktemp -d)
export KANBAN_ROOT="$TMP"
# Seed: 3 tasks T-A, T-B (blocked_by=[T-A]), T-C (blocked_by=[T-A,T-B])
cat > "$TMP/state.json" <<'EOF'
{"schema_version":3,"projects":["openclaw"],"sprints":[{"id":"sprint-1","state":"current","start_date":"2026-04-21","end_date":"2026-04-27","name":"t"}],"tasks":[
{"id":"T-A","title":"A","status":"backlog","sprint_id":"sprint-1","project":"openclaw","description":"","epic_id":null,"wave_ref":null,"created_at":"2026-04-22T00:00:00Z","updated_at":"2026-04-22T00:00:00Z","created_by":"t","archived_at":null,"blocked":false,"blocked_reason":null,"blocked_at":null,"rejected_reason":null,"dispatch_payload":{"spec_ref":"a.md","acceptance_criteria":["AC"],"blocked_by":[]},"test_result":null},
{"id":"T-B","title":"B","status":"backlog","sprint_id":"sprint-1","project":"openclaw","description":"","epic_id":null,"wave_ref":null,"created_at":"2026-04-22T00:00:00Z","updated_at":"2026-04-22T00:00:00Z","created_by":"t","archived_at":null,"blocked":false,"blocked_reason":null,"blocked_at":null,"rejected_reason":null,"dispatch_payload":{"spec_ref":"b.md","acceptance_criteria":["AC"],"blocked_by":["T-A"]},"test_result":null}
],"last_event_seq":0}
EOF
echo "" > "$TMP/events.jsonl"
echo "Seeded: $TMP"
```

- [ ] **Step 2: Smoke §5.1 — auto-release happy**

```bash
CLI=~/.openclaw/kanban-tasks/cli.sh
$CLI task move T-A ready --actor smoke --json
$CLI task move T-A in_progress --actor smoke --json
$CLI task move T-A testing --actor smoke --json
$CLI task move T-A done --actor smoke --json
# Verificar T-B auto-promoted
python3 -c "import json,os; s=json.load(open(os.environ['KANBAN_ROOT']+'/state.json')); print({t['id']:t['status'] for t in s['tasks']})"
```

Expected: `{'T-A': 'done', 'T-B': 'ready'}`.

- [ ] **Step 3: Smoke §5.5 — gate bloqueia move premature**

```bash
# Reset T-A pra backlog (simular)
# Ou setup fresh
$CLI task move T-B ready --actor smoke --json
echo "Exit: $?"
```

Expected: (se T-A ainda não done) exit 1 + JSON com `code: BLOCKED_BY_UNRESOLVED`.

OBS: Task 4/5 não implementaram explicitamente o gate em `task move → ready`. Isso precisa ser parte do `move()` integration. Conferir se spec §3.2 `can_move_to_ready` está sendo invocado em `move()` quando `to_status == "ready"`. Se não, adicionar em Task 5.

**DEPENDENCY CHECK**: confirmar que Task 5 integrou `can_move_to_ready` no fluxo de `task move <id> ready`. Se só os hooks foram plugados, esse smoke falha. Voltar Task 5 e acrescentar:

```python
def move(task_id, to_status, ...):
    with store.mutate_state() as state:
        t = find_task(state, task_id)
        # ... transition validation existente ...
        if to_status == "ready":
            from lib import transitions
            ok, missing = transitions.can_move_to_ready(t, state)
            if not ok:
                raise TaskError("BLOCKED_BY_UNRESOLVED",
                                f"preds nao done: {missing}")
        # ... resto ...
```

**ATENÇÃO:** essa integração faz parte do Task 5 mas não foi explicitada no plan text original. Se subagent implementando Task 5 não cobrir, ajustar antes de smoke.

- [ ] **Step 4: Smoke §5.3 — upstream rejected auto-block**

```bash
# Fresh seed (pode repetir Step 1 em novo tmp)
# Após seed: reject T-A
$CLI task move T-A rejected --actor smoke --json
python3 -c "import json,os; s=json.load(open(os.environ['KANBAN_ROOT']+'/state.json')); tb=[t for t in s['tasks'] if t['id']=='T-B'][0]; print('T-B blocked:', tb['blocked'], 'reason:', tb['blocked_reason'])"
```

Expected: `T-B blocked: True reason: upstream_rejected: T-A`.

- [ ] **Step 5: Smoke §5.6 — ciclo detectado**

```bash
# T-A set-blocked-by [T-B] (T-B já tem [T-A] no seed) → ciclo
$CLI task set-blocked-by T-A --preds T-B --actor smoke --json
echo "Exit: $?"
```

Expected: exit 1 + JSON com `code: CYCLE_DETECTED`.

- [ ] **Step 6: Smoke §5.7 — pred inexistente**

```bash
$CLI task set-blocked-by T-A --preds T-9999 --actor smoke --json
echo "Exit: $?"
```

Expected: exit 1 + `code: PRED_NOT_FOUND`.

- [ ] **Step 7: Cleanup smoke tmp**

```bash
unset KANBAN_ROOT
rm -rf "$TMP"
```

- [ ] **Step 8: Suite completa final**

```bash
cd ~/.openclaw/kanban-tasks
python3 -m unittest discover tests 2>&1 | tail -3
echo "---MC:"
cd ~/code/mission-control
npm test -- --run 2>&1 | tail -5
```

Expected: kanban-tasks 61/61 + MC baseline (87/87 + eventual 1-2 novos se houver).

---

## Phase 8 — Delivery commits

### Task 11: Commit MC feat branch (só wave-5 files)

**Files:** git commit em `~/code/mission-control/`

- [ ] **Step 1: Confirmar branch + staged/unstaged state**

```bash
cd ~/code/mission-control
git branch --show-current
git status --short
```

Expected: branch `feat/e5-f4-kanban-blocked-by-schema`. Modified/new: `src/app/api/kanban/tasks/[id]/blocked-by/route.ts` (new), `src/lib/kanban/stateReader.ts` (modified), `src/app/(dashboard)/kanban/page.tsx` (modified). Uncommitted unrelated preservados (CLAUDE.md, health, hardening).

- [ ] **Step 2: Stage EXPLICITO só wave-5 files**

```bash
cd ~/code/mission-control
git add src/app/api/kanban/tasks/\[id\]/blocked-by/route.ts \
        src/lib/kanban/stateReader.ts \
        src/app/\(dashboard\)/kanban/page.tsx
git diff --cached --stat
```

Expected: 3 arquivos wave-5. Nada mais.

- [ ] **Step 3: Commit**

```bash
cd ~/code/mission-control
git commit -m "$(cat <<'EOF'
feat(kanban): blocked_by schema + HTTP route + UI deps display (E5/F4 OH wave-5)

PUT /api/kanban/tasks/[id]/blocked-by adicionado. Body shape:
  { preds: [...] } | { add: "T-X" } | { remove: "T-X" }

Forward pro CLI `kanban-tasks task set-blocked-by`. Mapping override:
CYCLE_DETECTED / PRED_NOT_FOUND / BLOCKED_BY_INVALID → HTTP 422.

stateReader.ts: Task.dispatch_payload.blocked_by?: string[] adicionado.
UI /kanban page: card exibe `deps: T-X, T-Y` quando blocked_by nao vazio
(minimal text display; UI graph visualization eh follow-up §1.3).

Python runtime em ~/.openclaw/kanban-tasks/ (NAO tracked): gate de ciclo
+ hooks atomic + 40+ unit tests; commit Python runtime nao aplicavel.

Spec: bevox-knowledge/35_specs/2026-04-21-e5-f4-kanban-blocked-by-schema.md
ADR: bevox-knowledge/30_adr/ADR-009-clarification-loop-unified-local-first.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)" && git log --oneline -2
```

Expected: novo commit em `feat/e5-f4-kanban-blocked-by-schema`, 3 arquivos wave-5.

- [ ] **Step 4: NÃO pushar.** Push condicional ao bloco OH completo.

### Task 12: Commit delivery em bevox-knowledge draft

**Files:**
- Modify: `~/bevox-knowledge/35_specs/2026-04-21-e5-f4-kanban-blocked-by-schema.md`
- Modify: `~/bevox-knowledge/40_roadmap/delivery-tracker.yml`

- [ ] **Step 1: Branch draft ativo**

```bash
cd ~/bevox-knowledge
git branch --show-current
```

Expected: `draft/adr-009-clarification-daemon`.

- [ ] **Step 2: Spec status + delivery notes (§2.1 novo bloco)**

Editar `35_specs/2026-04-21-e5-f4-kanban-blocked-by-schema.md`:
- Mudar `**Status:** draft` → `**Status:** delivered (2026-04-22)`

Após seção §2 (decisões) inserir §2.1:

```markdown
---

## 2.1 Delivery notes (2026-04-22)

Deltas entre spec e implementacao entregue:

1. **Hook ATOMIC dentro de `mutate_state()`** (nao post-commit conforme
   spec §4.3). Lição wave-4 aplicada: eventos + mutacao de state devem
   acontecer na mesma transacao, senao `state.last_event_seq` drifa de
   `events.jsonl`. Implementacao: `_auto_release_dependents` +
   `_block_dependents_upstream_failed` chamados DENTRO do mesmo
   `store.mutate_state()` block de `move`/`archive`, apos o append do
   evento principal.

2. **Ciclo gate UNIVERSAL em 3 write-paths** (spec §2.6 so menciona 2):
   - `task add` via wave-4 payload (novo teste);
   - `set-dispatch-payload` quando `blocked_by` presente no payload novo
     (loophole fechado — spec original omitia);
   - `set-blocked-by` dedicado.

3. **`transitions.py` ja existia** (85 linhas com
   is_valid_transition/is_terminal/is_blockable/validate_or_raise).
   Wave-5 estende (nao cria): +`validate_blocked_by_field`,
   +`detect_cycle`, +`can_move_to_ready`.

4. **`archived` nao eh status** — eh flag ortogonal via evento separado
   `task_archived`. Spec §3.3 agrupa `rejected` e `archived` num unico
   hook em `task_moved`; realidade code split: hook chamado em AMBOS
   `task.move(status=rejected)` e `task.archive(...)`.

5. **`rebuild` command ja existia** (`api.py:411`); migracao v2→v3
   estendeu o rebuild existente para popular `dispatch_payload.blocked_by = []`
   default em tasks pre-existentes. Sem cmd novo.
```

Adicionar §8 follow-up opcional:

```markdown
- **`can_move_to_ready` enforcement integrado em `task move ready`**:
  spec §3.2 descreve o gate mas wave-5 plan adicionou-o explicitamente
  dentro de `lib/task.py::move()` como TaskError `BLOCKED_BY_UNRESOLVED`.
  Comportamento identico ao que spec implicava.
```

- [ ] **Step 3: Tracker entry após wave-4**

Editar `40_roadmap/delivery-tracker.yml`. Localizar entry `payload-completeness-gate` (wave-4) e inserir APÓS:

```yaml
      - id: kanban-blocked-by-schema
        status: delivered
        delivered_at: 2026-04-22
        spec: 35_specs/2026-04-21-e5-f4-kanban-blocked-by-schema.md
        adr: 30_adr/ADR-009-clarification-loop-unified-local-first.md
        narrative: "Operational Loop Hardening 2026-04-22 — wave-5 de 8 (cross-cut E5/F4)"
        epic_ref: E5
        feature_ref: F4
        features:
          - "lib/transitions.py estendido: validate_blocked_by_field + detect_cycle (DFS) + can_move_to_ready (AND semantics)"
          - "lib/task.py::set_blocked_by central write-path com cycle gate universal + TaskError codes (CYCLE_DETECTED, PRED_NOT_FOUND, BLOCKED_BY_INVALID, TASK_NOT_FOUND)"
          - "Hooks ATOMIC dentro de mutate_state em task.move(done→auto-release) e task.move(rejected)/task.archive(→auto-block upstream_failed)"
          - "Ciclo gate em set_dispatch_payload quando blocked_by presente (loophole fechado; nao coberto na spec original)"
          - "Schema version 2→3 via rebuild existente (popula dispatch_payload.blocked_by=[] default em tasks pre-wave5)"
          - "CLI task set-blocked-by com --preds / --add / --remove (mutually exclusive)"
          - "MC PUT /api/kanban/tasks/[id]/blocked-by; CYCLE_DETECTED/PRED_NOT_FOUND/BLOCKED_BY_INVALID → HTTP 422"
          - "MC UI /kanban card exibe `deps: T-X, T-Y` minimal text (UI graph visualization follow-up §1.3)"
          - "Eventos auditaveis: task_blocked_by_set, task_blocked_by_auto_released, task_blocked_upstream_failed"
          - "40+ unit tests Python (transitions + set_blocked_by + hooks + set_dispatch_payload gate + cmd + schema); MC baseline vitest preservado"
          - "commit MC source: feat/e5-f4-kanban-blocked-by-schema (3 arquivos); NAO pushado"
```

- [ ] **Step 4: Commit draft**

```bash
cd ~/bevox-knowledge
git add 35_specs/2026-04-21-e5-f4-kanban-blocked-by-schema.md \
        40_roadmap/delivery-tracker.yml
git diff --cached --stat
git commit -m "$(cat <<'EOF'
delivery(E5/F4): wave-5 kanban-blocked-by-schema delivered

Operational Loop Hardening 2026-04-22 wave-5 (cross-cut E5/F4)
completa. Dependencia formal entre kanban tasks via
dispatch_payload.blocked_by com AND semantics, hooks atomic, gate de
ciclo universal, schema v2→v3 aditivo retrocompativel.

Implementado em 2 camadas:

1. Python runtime kanban-tasks (~/.openclaw/kanban-tasks/, NAO tracked):
   - lib/transitions.py: validate_blocked_by_field + detect_cycle DFS +
     can_move_to_ready (AND)
   - lib/task.py: set_blocked_by central + hooks atomic
     (_auto_release_dependents / _block_dependents_upstream_failed)
     dentro de mutate_state de move/archive
   - lib/task.py::set_dispatch_payload: cycle gate tambem (loophole
     fechado alem do que a spec original previa)
   - lib/api.py: cmd_task_set_blocked_by com --preds/--add/--remove
   - Schema v3 via rebuild existente populando blocked_by=[] default

2. MC source (feat/e5-f4-kanban-blocked-by-schema branch, NAO pushada):
   - PUT /api/kanban/tasks/[id]/blocked-by
   - Task type ganha dispatch_payload.blocked_by?: string[]
   - UI card exibe `deps: T-X, T-Y` minimal text

5 delivery notes inline (§2.1) cobrem deltas:
- Hook atomic (nao post-commit) — licao wave-4 aplicada
- Ciclo gate universal em 3 write-paths (spec so mencionava 2)
- transitions.py estendido (nao criado do zero)
- archived eh flag/evento separado (nao status)
- rebuild existente estendido (nao cmd novo)

40+ unit tests Python + baseline MC vitest preservado. Zero regressao.
Base estrutural pra wave-6 scrum-master-v2 (populacao automatica de
blocked_by a partir de plans de fase).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)" && git log --oneline -6
```

Expected: novo commit no topo, acima de `delivery(E10): wave-4 payload-completeness-gate delivered`.

- [ ] **Step 5: NÃO pushar.** Merge draft branch pra main condicional ao bloco OH completo.

---

## Checklist final

- [ ] **Phase 1-6 tests Python:** 61/61 verdes (18 transitions + 2 schema + 6 set_blocked_by + 8 hooks+gate + 6 cmd; 27 wave-4 prev = 61 total).
- [ ] **Phase 5-6 MC tests:** baseline vitest preservado (87/87 ou atual).
- [ ] **Smoke E2E §5 spec:** cenarios 1/3/5/6/7 validados via tmpdir isolado.
- [ ] **Schema migration runtime real:** `~/.openclaw/kanban-tasks/state.json` tem `schema_version: 3` + toda task com `dispatch_payload.blocked_by: []`.
- [ ] **MC feat branch:** `feat/e5-f4-kanban-blocked-by-schema`, 3 arquivos wave-5, uncommitted unrelated preservados. NÃO pushado.
- [ ] **bevox-knowledge draft:** 5 delivery notes + tracker entry. NÃO pushado.
- [ ] **Backups:** `lib/{task,api,transitions,store}.py.pre-wave5.bak` pra rollback.

---

## Próximos passos pós-delivery wave-5

1. Bernard valida cenarios live (criar 2-3 tasks com blocked_by real via CLI ou HTTP).
2. **Wave-6 (scrum-master-v2)** proxima — estende scrum-master para popular `blocked_by` automaticamente a partir de plans com fases ordenadas (Phase 1 → Phase 2 → ...). Spec em `35_specs/2026-04-21-e10-scrum-master-v2.md`.
3. **Wave-7 self-test** E2E do bloco OH completo (ultimo).
4. Quando bloco OH PASS, push das 4 branches pra main:
   - `bevox-knowledge/draft/adr-009-clarification-daemon`
   - `knowledge-sync/feat/e10-clarification-commands-plugin`
   - `mission-control/feat/e10-payload-completeness-gate`
   - `mission-control/feat/e5-f4-kanban-blocked-by-schema`
