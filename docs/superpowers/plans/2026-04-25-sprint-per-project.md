# Sprint per-project Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrar kanban-tasks pra sprints strictly per-project (schema_version 3→4); atualizar consumers (scrum-master, dispatcher com filtro + kill-switch, mission-control UI); migrar dados existentes (sprint-4 órfã com 27 tasks redistribuídas).

**Architecture:** Schema invariant change em `kanban-tasks/lib/sprint.py` propaga via `_resolve_sprint_id` em `task.py` e via novo módulo `migration.py`. Consumers (`scrum-master/lib/materializer.py`, `dispatcher/lib/selector.py`, `mission-control/src/`) atualizados sincronicamente em wave atomic. Kill-switch `OPENCLAW_DISPATCHER_IGNORE_SPRINT=1` permite rollback do filtro do dispatcher em <30s sem revert de código.

**Tech Stack:** Python stdlib (kanban-tasks, scrum-master, dispatcher) + unittest. TypeScript/Next.js + Vitest (mission-control).

**Spec:** `bevox-knowledge/35_specs/openclaw/2026-04-25-sprint-per-project.md` (commit `68e78c7` em `draft/spec-sprint-per-project`).

---

## File Structure

### Create

- `kanban-tasks/lib/migration.py` (~120 LOC) — `migrate_to_per_project(actor, dry_run=False)` + helpers
- `kanban-tasks/tests/test_sprint_per_project.py` (~12 tests)
- `kanban-tasks/tests/test_migrate_to_per_project.py` (~8 tests)
- `scrum-master-agent/tests/test_materializer_per_project_sprint.py` (~3 tests)
- `dispatcher-agent/tests/test_selector_sprint_filter.py` (~5 tests)

### Modify

- `kanban-tasks/lib/sprint.py` — `find_sprint(state, sprint_id, project=None)`, `get_current(state, project)`, `get_next(state, project)`, `bootstrap(actor, projects=None)` reads `projects.yml`, `close_current(carryover, actor, project)`
- `kanban-tasks/lib/task.py` — `_resolve_sprint_id(state, sprint_arg, project=None)` + invariant check `task.sprint_id.project == task.project` no add/move-to-sprint
- `kanban-tasks/lib/api.py` — subparsers `sprint bootstrap` (sem args lê projects.yml) + `sprint migrate-to-per-project` (--dry-run, --actor)
- `kanban-tasks/README.md` — bootstrap usage + close-current per-project + migrate command
- `scrum-master-agent/lib/materializer.py:138` — passa `project=task["project"]` no resolve
- `dispatcher-agent/lib/selector.py` — filter por current sprint + kill-switch env var
- `dispatcher-agent/lib/cron.py` — audit jsonl ganha `current_sprint_id` e `skip_reason="no_current_sprint"`
- `dispatcher-agent/README.md` — documentar `OPENCLAW_DISPATCHER_IGNORE_SPRINT`
- (separate repo) `mission-control/src/components/kanban/{useFilterPersistence,NewTaskModal,DetailDrawer}.{ts,tsx}` — project context propagation
- (separate repo) `mission-control/src/app/api/kanban/{state,tasks,tasks/[id]/move-to-sprint}/route.ts` — propagação de project

---

## Task 1: Setup branch + commit plano + abrir spec PR (gate)

**Files:**
- Create: `docs/superpowers/plans/2026-04-25-sprint-per-project.md` (este arquivo)

- [ ] **Step 1: Garantir branch correta**

```bash
cd ~/.openclaw && git status --short
git branch --show-current
```

Expected: branch `feat/sprint-per-project`. Se não, `git checkout -b feat/sprint-per-project` a partir de main.

- [ ] **Step 2: Commit do plano**

```bash
cd ~/.openclaw && git add docs/superpowers/plans/2026-04-25-sprint-per-project.md && git commit -m "$(cat <<'EOF'
plan(sprint-per-project): implementation plan for E10/sprint-per-project

Spec: bevox-knowledge/35_specs/openclaw/2026-04-25-sprint-per-project.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 3: Push spec branch + abrir PR no bevox-knowledge**

```bash
cd ~/bevox-knowledge && git checkout draft/spec-sprint-per-project
git push -u origin draft/spec-sprint-per-project
gh pr create --title "spec(openclaw): sprint per-project schema (E10/sprint-per-project)" --body "$(cat <<'EOF'
## Summary
Schema mudança no kanban-tasks: sprints viram strictly per-project (invariante: cada projeto canônico tem 1 current + 1 next ativos simultâneos). Habilita visualização correta na MC, filtro de dispatcher por current sprint, e prepara base pra C.1 (same-session reuse).

Wave síncrona com migração split-and-migrate da sprint-4 órfã, kill-switch \`OPENCLAW_DISPATCHER_IGNORE_SPRINT\`, 28 unit tests + 2 vitest tests + 5 smoke gates.

## Test plan
- [ ] Bernard revisa spec
- [ ] Approva pra implementação seguir
- [ ] Implementação PR (openclaw) abre só após este merge

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 4: PAUSA — aguardar Bernard mergear o spec PR**

Parar aqui. Bernard revisa + merge no `bernardTavares/bevox-knowledge`. Retomar Task 2 só depois de confirmação de merge.

---

## Task 2: TDD find_sprint per-project

**Files:**
- Create: `kanban-tasks/tests/test_sprint_per_project.py`
- Modify: `kanban-tasks/lib/sprint.py:38-56`

- [ ] **Step 1: Escrever os 3 testes em `test_sprint_per_project.py`**

Write `~/.openclaw/kanban-tasks/tests/test_sprint_per_project.py`:

```python
"""Tests sprint per-project schema (v4): find_sprint/get_current/get_next."""
import unittest
from typing import Any, Dict


def _make_state(*sprints) -> Dict[str, Any]:
    return {
        "schema_version": 4,
        "generated_at": "2026-04-25T00:00:00Z",
        "last_event_seq": 0,
        "projects": ["bevox-mobile", "bevox-backend"],
        "sprints": list(sprints),
        "tasks": [],
    }


def _sp(seq: int, st: str, project: str) -> Dict[str, Any]:
    return {
        "id": f"sprint-{seq}",
        "name": f"Sprint {seq}",
        "state": st,
        "project": project,
        "created_at": "2026-04-25T00:00:00Z",
        "closed_at": None,
        "created_by": "test",
    }


class TestFindSprintPerProject(unittest.TestCase):
    def test_find_sprint_current_requires_project_arg(self):
        from lib import sprint
        state = _make_state(_sp(1, "current", "bevox-mobile"))
        with self.assertRaises(ValueError) as ctx:
            sprint.find_sprint(state, "current")
        self.assertIn("project required", str(ctx.exception).lower())

    def test_find_sprint_current_per_project_returns_correct(self):
        from lib import sprint
        state = _make_state(
            _sp(1, "current", "bevox-mobile"),
            _sp(2, "current", "bevox-backend"),
            _sp(3, "next", "bevox-mobile"),
        )
        sp_mob = sprint.find_sprint(state, "current", project="bevox-mobile")
        self.assertEqual(sp_mob["id"], "sprint-1")
        sp_bac = sprint.find_sprint(state, "current", project="bevox-backend")
        self.assertEqual(sp_bac["id"], "sprint-2")

    def test_find_sprint_literal_id_works_without_project(self):
        from lib import sprint
        state = _make_state(_sp(7, "current", "bevox-mobile"))
        sp = sprint.find_sprint(state, "sprint-7")
        self.assertEqual(sp["id"], "sprint-7")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar testes (devem falhar)**

Run: `cd ~/.openclaw/kanban-tasks && python3 -m unittest tests.test_sprint_per_project -v`
Expected: 3 FAILs (signature mismatch — `find_sprint` ainda não aceita project arg).

- [ ] **Step 3: Modificar `lib/sprint.py:38-56`**

Replace the entire `find_sprint` / `get_current` / `get_next` block (linhas 38-56) com:

```python
def find_sprint(state: Dict[str, Any], sprint_id: str,
                project: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Resolve aliases 'current'/'next' (per-project) ou literal sprint_id.

    Aliases requerem project arg (raise ValueError sem). Literal id
    aceita project=None (id já é único).
    """
    if sprint_id in ("current", "next"):
        if project is None:
            raise ValueError(
                f"project required for alias resolution (got sprint_id={sprint_id!r})"
            )
        for sp in state["sprints"]:
            if sp["state"] == sprint_id and sp.get("project") == project:
                return sp
        return None
    for sp in state["sprints"]:
        if sp["id"] == sprint_id:
            return sp
    return None


def get_current(state: Dict[str, Any], project: str) -> Optional[Dict[str, Any]]:
    return find_sprint(state, "current", project=project)


def get_next(state: Dict[str, Any], project: str) -> Optional[Dict[str, Any]]:
    return find_sprint(state, "next", project=project)
```

- [ ] **Step 4: Rodar testes (devem passar)**

Run: `cd ~/.openclaw/kanban-tasks && python3 -m unittest tests.test_sprint_per_project -v`
Expected: 3/3 ok.

- [ ] **Step 5: Commit**

```bash
cd ~/.openclaw && git add kanban-tasks/lib/sprint.py kanban-tasks/tests/test_sprint_per_project.py && git commit -m "$(cat <<'EOF'
feat(kanban/sprint): find_sprint requires project arg for current/next aliases

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: TDD bootstrap reads projects.yml

**Files:**
- Modify: `kanban-tasks/tests/test_sprint_per_project.py` (append 3 tests)
- Modify: `kanban-tasks/lib/sprint.py:61-89`

- [ ] **Step 1: Escrever testes (append a `TestBootstrap` class)**

Adicionar ao `test_sprint_per_project.py`:

```python
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch


class TestBootstrap(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        # patch ROOT no store + projects.yml
        from lib import store
        self.tmp_state = Path(self.tmp) / "state.json"
        self.tmp_events = Path(self.tmp) / "events.jsonl"
        self.tmp_projects = Path(self.tmp) / "projects.yml"
        self.tmp_projects.write_text(
            "projects:\n  - bevox-mobile\n  - bevox-backend\n  - openclaw\n"
        )
        # initial empty state
        self.tmp_state.write_text(
            '{"schema_version": 4, "generated_at": "2026-04-25T00:00:00Z",'
            ' "last_event_seq": 0, "projects": ["bevox-mobile","bevox-backend","openclaw"],'
            ' "sprints": [], "tasks": []}'
        )
        self.patches = [
            patch.object(store, "STATE_PATH", self.tmp_state),
            patch.object(store, "EVENTS_PATH", self.tmp_events),
            patch.object(store, "PROJECTS_PATH", self.tmp_projects),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.tmp)

    def test_bootstrap_creates_for_each_projects_yml_entry(self):
        from lib import sprint
        result = sprint.bootstrap(actor="test")
        self.assertTrue(result["ok"])
        # 3 projects × (current+next) = 6 sprints
        import json
        state = json.loads(self.tmp_state.read_text())
        self.assertEqual(len(state["sprints"]), 6)
        by_project = {}
        for sp in state["sprints"]:
            by_project.setdefault(sp["project"], []).append(sp["state"])
        self.assertEqual(sorted(by_project.keys()),
                         ["bevox-backend", "bevox-mobile", "openclaw"])
        for proj, states in by_project.items():
            self.assertEqual(sorted(states), ["current", "next"])

    def test_bootstrap_idempotent_skips_existing(self):
        from lib import sprint
        sprint.bootstrap(actor="test")
        # second run is noop pra projetos já bootstrapados
        result2 = sprint.bootstrap(actor="test")
        self.assertTrue(result2["ok"])
        # still 6 sprints
        import json
        state = json.loads(self.tmp_state.read_text())
        self.assertEqual(len(state["sprints"]), 6)
        self.assertEqual(result2.get("created", []), [])

    def test_bootstrap_dry_run_does_not_mutate(self):
        from lib import sprint
        result = sprint.bootstrap(actor="test", dry_run=True)
        self.assertTrue(result["ok"])
        self.assertIn("would_create", result)
        self.assertEqual(len(result["would_create"]), 6)  # 3 projects × 2 sprints
        # state.json intocado (sprints vazio)
        import json
        state = json.loads(self.tmp_state.read_text())
        self.assertEqual(state["sprints"], [])
```

- [ ] **Step 2: Rodar testes (devem falhar)**

Run: `cd ~/.openclaw/kanban-tasks && python3 -m unittest tests.test_sprint_per_project.TestBootstrap -v`
Expected: 3 FAILs (bootstrap signature antiga, sem projects/dry_run args).

- [ ] **Step 3: Modificar `lib/sprint.py:61-89` (substituir `bootstrap`)**

Replace the entire `bootstrap` function:

```python
def bootstrap(actor: str = "bernard", projects: Optional[List[str]] = None,
              dry_run: bool = False) -> Dict[str, Any]:
    """Cria current+next pra cada projeto que ainda não tem.

    Se `projects` é None, lê de projects.yml (fonte canônica).
    Idempotente: projetos que já têm current+next são skipped.
    `dry_run=True` retorna plano sem mutar.
    """
    if projects is None:
        projects = store.read_projects()

    plan = []   # lista de (project, "current"|"next")

    if dry_run:
        # Ler state sem lock pra montar plano
        state = store.read_state()
        for proj in projects:
            has_current = any(
                sp["state"] == "current" and sp.get("project") == proj
                for sp in state["sprints"]
            )
            has_next = any(
                sp["state"] == "next" and sp.get("project") == proj
                for sp in state["sprints"]
            )
            if not has_current:
                plan.append((proj, "current"))
            if not has_next:
                plan.append((proj, "next"))
        return {"ok": True, "dry_run": True, "would_create": plan}

    created = []
    with store.mutate_state() as state:
        for proj in projects:
            has_current = any(
                sp["state"] == "current" and sp.get("project") == proj
                for sp in state["sprints"]
            )
            has_next = any(
                sp["state"] == "next" and sp.get("project") == proj
                for sp in state["sprints"]
            )
            if has_current and has_next:
                continue
            if not has_current:
                seq = _next_sprint_seq(state)
                sp = _make_sprint(seq, "current", proj, actor)
                state["sprints"].append(sp)
                seqn = store.next_seq(state)
                store.append_event({
                    "seq": seqn, "ts": store.now_iso(), "type": "sprint_created",
                    "actor": actor, "sprint_id": sp["id"], "state": "current",
                    "project": proj, "name": sp["name"],
                })
                state["last_event_seq"] = seqn
                created.append(sp)
            if not has_next:
                seq = _next_sprint_seq(state)
                sp = _make_sprint(seq, "next", proj, actor)
                state["sprints"].append(sp)
                seqn = store.next_seq(state)
                store.append_event({
                    "seq": seqn, "ts": store.now_iso(), "type": "sprint_created",
                    "actor": actor, "sprint_id": sp["id"], "state": "next",
                    "project": proj, "name": sp["name"],
                })
                state["last_event_seq"] = seqn
                created.append(sp)

    return {"ok": True, "dry_run": False, "created": created}
```

- [ ] **Step 4: Rodar testes**

Run: `cd ~/.openclaw/kanban-tasks && python3 -m unittest tests.test_sprint_per_project.TestBootstrap -v`
Expected: 3/3 ok.

- [ ] **Step 5: Commit**

```bash
cd ~/.openclaw && git add kanban-tasks/lib/sprint.py kanban-tasks/tests/test_sprint_per_project.py && git commit -m "$(cat <<'EOF'
feat(kanban/sprint): bootstrap reads projects.yml + dry-run + idempotent

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: TDD close_current per-project

**Files:**
- Modify: `kanban-tasks/tests/test_sprint_per_project.py` (append 3 tests)
- Modify: `kanban-tasks/lib/sprint.py:142-239` (substitui close_current)

- [ ] **Step 1: Escrever testes (append `TestCloseCurrentPerProject` class)**

Adicionar ao `test_sprint_per_project.py`:

```python
class TestCloseCurrentPerProject(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from lib import store
        self.tmp_state = Path(self.tmp) / "state.json"
        self.tmp_events = Path(self.tmp) / "events.jsonl"
        self.tmp_projects = Path(self.tmp) / "projects.yml"
        self.tmp_projects.write_text("projects:\n  - bevox-mobile\n  - bevox-backend\n")
        # state com current+next pra 2 projetos + 1 task em current[bevox-mobile]
        import json
        state = {
            "schema_version": 4,
            "generated_at": "2026-04-25T00:00:00Z",
            "last_event_seq": 4,
            "projects": ["bevox-mobile", "bevox-backend"],
            "sprints": [
                _sp(1, "current", "bevox-mobile"),
                _sp(2, "next", "bevox-mobile"),
                _sp(3, "current", "bevox-backend"),
                _sp(4, "next", "bevox-backend"),
            ],
            "tasks": [
                {"id": "T-A", "title": "A", "status": "ready",
                 "sprint_id": "sprint-1", "project": "bevox-mobile",
                 "blocked": False, "updated_at": "2026-04-25T00:00:00Z",
                 "dispatch_payload": {}},
            ],
        }
        self.tmp_state.write_text(json.dumps(state))
        self.patches = [
            patch.object(store, "STATE_PATH", self.tmp_state),
            patch.object(store, "EVENTS_PATH", self.tmp_events),
            patch.object(store, "PROJECTS_PATH", self.tmp_projects),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.tmp)

    def test_close_current_only_affects_target_project(self):
        from lib import sprint
        result = sprint.close_current(
            project="bevox-mobile",
            carryover=[{"task_id": "T-A", "action": "move_current"}],
            actor="test",
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["closed"], "sprint-1")
        # bevox-backend intocado
        import json
        state = json.loads(self.tmp_state.read_text())
        bb_sprints = [sp for sp in state["sprints"] if sp["project"] == "bevox-backend"]
        bb_states = sorted([sp["state"] for sp in bb_sprints])
        self.assertEqual(bb_states, ["current", "next"])

    def test_close_current_creates_new_next_for_project(self):
        from lib import sprint
        sprint.close_current(
            project="bevox-mobile",
            carryover=[{"task_id": "T-A", "action": "move_current"}],
            actor="test",
        )
        import json
        state = json.loads(self.tmp_state.read_text())
        mob_sprints = [sp for sp in state["sprints"] if sp["project"] == "bevox-mobile"]
        states = sorted([sp["state"] for sp in mob_sprints])
        self.assertEqual(states, ["closed", "current", "next"])

    def test_close_current_carryover_propagates_correctly(self):
        from lib import sprint
        sprint.close_current(
            project="bevox-mobile",
            carryover=[{"task_id": "T-A", "action": "move_current"}],
            actor="test",
        )
        import json
        state = json.loads(self.tmp_state.read_text())
        # task T-A devia estar agora no novo current de bevox-mobile (sprint-2 promovido)
        ta = next(t for t in state["tasks"] if t["id"] == "T-A")
        # sprint-2 era next de bevox-mobile, virou current após close
        self.assertEqual(ta["sprint_id"], "sprint-2")
```

- [ ] **Step 2: Rodar testes (devem falhar)**

Run: `cd ~/.openclaw/kanban-tasks && python3 -m unittest tests.test_sprint_per_project.TestCloseCurrentPerProject -v`
Expected: 3 FAILs (close_current ainda não aceita project arg).

- [ ] **Step 3: Modificar `lib/sprint.py:131-247` (substitui list_pending_in_current + close_current)**

Substituir a partir da linha 131:

```python
def list_pending_in_current(state: Dict[str, Any], project: str) -> List[Dict[str, Any]]:
    cur = get_current(state, project=project)
    if cur is None:
        return []
    return [
        t for t in state["tasks"]
        if t["sprint_id"] == cur["id"]
        and t["status"] not in ("done", "archived")
    ]


def close_current(carryover: List[Dict[str, str]], actor: str,
                  project: str) -> Dict[str, Any]:
    """Fecha current sprint do projeto P com carry-over decisions.

    Pos-execucao em P: current vira closed, next vira current,
    novo next nasce vazio. Outros projetos intocados.
    """
    with store.mutate_state() as state:
        cur = get_current(state, project=project)
        nxt = get_next(state, project=project)
        if cur is None or nxt is None:
            raise ValueError(
                f"invariant broken: project={project} missing current or next"
            )

        pending = list_pending_in_current(state, project=project)
        pending_ids = {t["id"] for t in pending}
        provided = {c["task_id"] for c in carryover}
        missing = pending_ids - provided
        if missing:
            raise ValueError(
                f"carryover incomplete for project={project}; "
                f"missing: {sorted(missing)}"
            )

        seq = store.next_seq(state)
        store.append_event({
            "seq": seq, "ts": store.now_iso(), "type": "sprint_closed",
            "actor": actor, "sprint_id": cur["id"],
            "project": project, "carryover": carryover,
        })
        state["last_event_seq"] = seq

        cur["state"] = "closed"
        cur["closed_at"] = store.now_iso()

        nxt["state"] = "current"
        seq = store.next_seq(state)
        store.append_event({
            "seq": seq, "ts": store.now_iso(), "type": "sprint_promoted",
            "actor": actor, "from_id": nxt["id"], "to_state": "current",
            "project": project,
        })
        state["last_event_seq"] = seq

        new_seq = _next_sprint_seq(state)
        new_next = _make_sprint(new_seq, "next", project, actor)
        state["sprints"].append(new_next)
        seq = store.next_seq(state)
        store.append_event({
            "seq": seq, "ts": store.now_iso(), "type": "sprint_created",
            "actor": actor, "sprint_id": new_next["id"], "state": "next",
            "project": project, "name": new_next["name"],
        })
        state["last_event_seq"] = seq

        new_current_id = nxt["id"]
        new_next_id = new_next["id"]
        tasks_by_id = {t["id"]: t for t in state["tasks"]}
        for entry in carryover:
            tid = entry["task_id"]
            action = entry["action"]
            t = tasks_by_id.get(tid)
            if t is None:
                continue
            if action == "move_current":
                old = t["sprint_id"]
                t["sprint_id"] = new_current_id
                t["updated_at"] = store.now_iso()
                seq = store.next_seq(state)
                store.append_event({
                    "seq": seq, "ts": store.now_iso(), "type": "task_resprinted",
                    "actor": actor, "task_id": tid,
                    "from_sprint_id": old, "to_sprint_id": new_current_id,
                })
                state["last_event_seq"] = seq
            elif action == "move_next":
                old = t["sprint_id"]
                t["sprint_id"] = new_next_id
                t["updated_at"] = store.now_iso()
                seq = store.next_seq(state)
                store.append_event({
                    "seq": seq, "ts": store.now_iso(), "type": "task_resprinted",
                    "actor": actor, "task_id": tid,
                    "from_sprint_id": old, "to_sprint_id": new_next_id,
                })
                state["last_event_seq"] = seq
            elif action == "archive":
                t["status"] = "archived"
                t["archived_at"] = store.now_iso()
                t["updated_at"] = store.now_iso()
                seq = store.next_seq(state)
                store.append_event({
                    "seq": seq, "ts": store.now_iso(), "type": "task_archived",
                    "actor": actor, "task_id": tid,
                })
                state["last_event_seq"] = seq
            else:
                raise ValueError(f"unknown carryover action: {action}")

        return {
            "ok": True,
            "project": project,
            "closed": cur["id"],
            "promoted_to_current": new_current_id,
            "new_next": new_next_id,
        }
```

- [ ] **Step 4: Rodar testes**

Run: `cd ~/.openclaw/kanban-tasks && python3 -m unittest tests.test_sprint_per_project.TestCloseCurrentPerProject -v`
Expected: 3/3 ok.

- [ ] **Step 5: Commit**

```bash
cd ~/.openclaw && git add kanban-tasks/lib/sprint.py kanban-tasks/tests/test_sprint_per_project.py && git commit -m "$(cat <<'EOF'
feat(kanban/sprint): close_current per-project (project arg required)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: TDD task invariant + _resolve_sprint_id project arg

**Files:**
- Modify: `kanban-tasks/tests/test_sprint_per_project.py` (append 3 tests)
- Modify: `kanban-tasks/lib/task.py:39-50` (resolve com project)
- Modify: `kanban-tasks/lib/task.py` (invariant em task_add)

- [ ] **Step 1: Escrever testes (append `TestTaskSprintInvariants` class)**

Adicionar ao `test_sprint_per_project.py`:

```python
class TestTaskSprintInvariants(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from lib import store
        self.tmp_state = Path(self.tmp) / "state.json"
        self.tmp_events = Path(self.tmp) / "events.jsonl"
        self.tmp_projects = Path(self.tmp) / "projects.yml"
        self.tmp_projects.write_text("projects:\n  - bevox-mobile\n  - bevox-backend\n")
        import json
        state = {
            "schema_version": 4,
            "generated_at": "2026-04-25T00:00:00Z",
            "last_event_seq": 0,
            "projects": ["bevox-mobile", "bevox-backend"],
            "sprints": [
                _sp(1, "current", "bevox-mobile"),
                _sp(2, "next", "bevox-mobile"),
                _sp(3, "current", "bevox-backend"),
                _sp(4, "next", "bevox-backend"),
            ],
            "tasks": [],
        }
        self.tmp_state.write_text(json.dumps(state))
        self.patches = [
            patch.object(store, "STATE_PATH", self.tmp_state),
            patch.object(store, "EVENTS_PATH", self.tmp_events),
            patch.object(store, "PROJECTS_PATH", self.tmp_projects),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.tmp)

    def test_task_sprint_project_consistency_enforced(self):
        """task add com sprint_id de outro projeto → INVALID_SPRINT_PROJECT_MISMATCH."""
        from lib import task
        # tenta criar task de bevox-mobile com sprint literal sprint-3 (de bevox-backend)
        with self.assertRaises(ValueError) as ctx:
            task.add(
                title="bad",
                payload={"goal": "x", "acceptance_criteria": ["x"], "spec_ref": "n/a"},
                actor="test",
                sprint="sprint-3",
                project="bevox-mobile",
            )
        self.assertIn("INVALID_SPRINT_PROJECT_MISMATCH", str(ctx.exception))

    def test_get_current_returns_none_when_project_has_no_current(self):
        from lib import sprint, store
        state = store.read_state()
        # remove bevox-mobile current
        state["sprints"] = [sp for sp in state["sprints"]
                            if not (sp["state"] == "current" and sp["project"] == "bevox-mobile")]
        import json
        self.tmp_state.write_text(json.dumps(state))
        # re-read e check
        state = store.read_state()
        result = sprint.get_current(state, project="bevox-mobile")
        self.assertIsNone(result)

    def test_resolve_sprint_id_alias_requires_project(self):
        from lib import task
        from lib import store
        state = store.read_state()
        # alias sem project → ValueError
        with self.assertRaises(ValueError):
            task._resolve_sprint_id(state, "current")
        # alias com project → sprint_id
        sid = task._resolve_sprint_id(state, "current", project="bevox-mobile")
        self.assertEqual(sid, "sprint-1")
```

- [ ] **Step 2: Rodar testes**

Run: `cd ~/.openclaw/kanban-tasks && python3 -m unittest tests.test_sprint_per_project.TestTaskSprintInvariants -v`
Expected: 3 FAILs (invariant não enforced + signature antiga).

- [ ] **Step 3: Modificar `lib/task.py:39-50` (substitui `_resolve_sprint_id`)**

```python
def _resolve_sprint_id(state: Dict[str, Any], sprint_arg: str,
                       project: Optional[str] = None) -> str:
    """Resolve aliases (current/next) com project obrigatório, ou literal id."""
    sp = sprint_lib.find_sprint(state, sprint_arg, project=project)
    if sp is None:
        raise ValueError(f"sprint not found: {sprint_arg} (project={project!r})")
    return sp["id"]
```

- [ ] **Step 4: Modificar `lib/task.py` `add` function**

Em `task.add()` (perto da linha 55-80), localizar onde `sprint_id = _resolve_sprint_id(state, sprint)` é chamado. Substituir + adicionar invariant check:

```python
        sprint_id = _resolve_sprint_id(state, sprint, project=project)
        # Invariant: sprint.project == task.project
        sp = sprint_lib.find_sprint(state, sprint_id)
        if sp is None:
            raise ValueError(f"sprint not found: {sprint_id}")
        if sp.get("project") and sp["project"] != project:
            raise ValueError(
                f"INVALID_SPRINT_PROJECT_MISMATCH: sprint={sprint_id} "
                f"belongs to project={sp['project']!r}, task project={project!r}"
            )
```

(Aplicar análoga em `task.move_to_sprint` na linha ~253 e onde mais `_resolve_sprint_id` é chamado.)

- [ ] **Step 5: Rodar testes**

Run: `cd ~/.openclaw/kanban-tasks && python3 -m unittest tests.test_sprint_per_project.TestTaskSprintInvariants -v`
Expected: 3/3 ok.

- [ ] **Step 6: Suite completa kanban-tasks (regression)**

Run: `cd ~/.openclaw/kanban-tasks && python3 -m unittest discover -v 2>&1 | tail -10`
Expected: All previous tests still pass + new tests green.

Se algum test pré-existente falha por não passar `project`, atualizar (são tests internos do kanban — passar project="openclaw" como default fixture).

- [ ] **Step 7: Commit**

```bash
cd ~/.openclaw && git add kanban-tasks/lib/task.py kanban-tasks/tests/test_sprint_per_project.py && git commit -m "$(cat <<'EOF'
feat(kanban/task): _resolve_sprint_id with project + INVALID_SPRINT_PROJECT_MISMATCH guard

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Migration module — happy path + idempotência + dry-run

**Files:**
- Create: `kanban-tasks/lib/migration.py`
- Create: `kanban-tasks/tests/test_migrate_to_per_project.py`

- [ ] **Step 1: Escrever 4 testes happy path**

Write `~/.openclaw/kanban-tasks/tests/test_migrate_to_per_project.py`:

```python
"""Tests migration script to schema_version 4 (split-and-migrate)."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def _seed_v3_state(state_path: Path):
    """state.json v3 com sprint-4 órfã (project=None) tendo tasks de 2 projetos."""
    state = {
        "schema_version": 3,
        "generated_at": "2026-04-24T00:00:00Z",
        "last_event_seq": 10,
        "projects": ["bevox-mobile", "bevox-backend"],
        "sprints": [
            {
                "id": "sprint-4", "name": "Sprint 4", "state": "current",
                "project": None, "created_at": "2026-04-18T15:36:25Z",
                "closed_at": None, "created_by": "bernard"
            }
        ],
        "tasks": [
            # ativa de bevox-mobile
            {"id": "T-100", "title": "active mobile", "status": "ready",
             "sprint_id": "sprint-4", "project": "bevox-mobile",
             "blocked": False, "updated_at": "2026-04-24T00:00:00Z",
             "dispatch_payload": {}},
            # ativa de bevox-backend
            {"id": "T-101", "title": "active backend", "status": "in_progress",
             "sprint_id": "sprint-4", "project": "bevox-backend",
             "blocked": False, "updated_at": "2026-04-24T00:00:00Z",
             "dispatch_payload": {}},
            # terminal — fica em sprint-4
            {"id": "T-102", "title": "archived", "status": "archived",
             "sprint_id": "sprint-4", "project": "bevox-mobile",
             "blocked": False, "updated_at": "2026-04-20T00:00:00Z",
             "dispatch_payload": {}},
        ],
    }
    state_path.write_text(json.dumps(state))


class TestMigrateHappyPath(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from lib import store
        self.tmp_state = Path(self.tmp) / "state.json"
        self.tmp_events = Path(self.tmp) / "events.jsonl"
        self.tmp_projects = Path(self.tmp) / "projects.yml"
        self.tmp_projects.write_text("projects:\n  - bevox-mobile\n  - bevox-backend\n")
        _seed_v3_state(self.tmp_state)
        self.patches = [
            patch.object(store, "STATE_PATH", self.tmp_state),
            patch.object(store, "EVENTS_PATH", self.tmp_events),
            patch.object(store, "PROJECTS_PATH", self.tmp_projects),
            patch.object(store, "ROOT", Path(self.tmp)),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.tmp)

    def test_migrate_creates_per_project_sprints(self):
        from lib import migration
        result = migration.migrate_to_per_project(actor="test")
        self.assertTrue(result["ok"])
        state = json.loads(self.tmp_state.read_text())
        self.assertEqual(state["schema_version"], 4)
        # Cada projeto tem current+next
        active_by_proj = {}
        for sp in state["sprints"]:
            if sp["state"] in ("current", "next"):
                active_by_proj.setdefault(sp.get("project"), []).append(sp["state"])
        self.assertEqual(sorted(active_by_proj.keys()),
                         ["bevox-backend", "bevox-mobile"])
        for proj, states in active_by_proj.items():
            self.assertEqual(sorted(states), ["current", "next"])

    def test_migrate_ignores_terminal_tasks_in_orphan_sprint(self):
        from lib import migration
        migration.migrate_to_per_project(actor="test")
        state = json.loads(self.tmp_state.read_text())
        # T-102 (archived) ficou em sprint-4
        t102 = next(t for t in state["tasks"] if t["id"] == "T-102")
        self.assertEqual(t102["sprint_id"], "sprint-4")
        # T-100 (ativa mobile) e T-101 (ativa backend) re-sprintadas
        t100 = next(t for t in state["tasks"] if t["id"] == "T-100")
        t101 = next(t for t in state["tasks"] if t["id"] == "T-101")
        # ambas devem estar em current de seu projeto
        sprints = {sp["id"]: sp for sp in state["sprints"]}
        self.assertEqual(sprints[t100["sprint_id"]]["project"], "bevox-mobile")
        self.assertEqual(sprints[t100["sprint_id"]]["state"], "current")
        self.assertEqual(sprints[t101["sprint_id"]]["project"], "bevox-backend")
        self.assertEqual(sprints[t101["sprint_id"]]["state"], "current")

    def test_migrate_idempotent_on_v4_schema(self):
        from lib import migration
        migration.migrate_to_per_project(actor="test")
        result2 = migration.migrate_to_per_project(actor="test")
        self.assertTrue(result2["ok"])
        self.assertTrue(result2.get("noop", False))
        self.assertEqual(result2.get("reason"), "already_migrated")

    def test_migrate_dry_run_outputs_plan_no_mutation(self):
        from lib import migration
        result = migration.migrate_to_per_project(actor="test", dry_run=True)
        self.assertTrue(result["ok"])
        self.assertTrue(result["dry_run"])
        # plano deve mostrar tasks a re-sprintar
        self.assertIn("would_resprint", result)
        self.assertEqual(len(result["would_resprint"]), 2)  # T-100 + T-101
        # state.json intocado
        state = json.loads(self.tmp_state.read_text())
        self.assertEqual(state["schema_version"], 3)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar testes (devem falhar)**

Run: `cd ~/.openclaw/kanban-tasks && python3 -m unittest tests.test_migrate_to_per_project.TestMigrateHappyPath -v`
Expected: ImportError (módulo não existe).

- [ ] **Step 3: Criar `lib/migration.py`**

Write `~/.openclaw/kanban-tasks/lib/migration.py`:

```python
"""Migration script: state.json v3 → v4 (sprints strictly per-project).

Split-and-migrate: tasks ativas em sprint global órfã viram tasks da
current sprint do projeto correspondente. Sprint órfã vira closed
legacy. Idempotente (v4 já → noop). Dry-run mostra plano sem mutar.
"""
from typing import Any, Dict, List, Optional

from . import sprint as sprint_lib
from . import store


_TERMINAL_STATUSES = ("archived", "done", "rejected")


def _build_resprint_plan(state: Dict[str, Any], orphan_sprint_id: str,
                         valid_projects: List[str]) -> Dict[str, Any]:
    """Lista tasks ativas que precisariam de re-sprint, e detecta erros."""
    to_resprint = []
    errors = []
    for t in state["tasks"]:
        if t.get("sprint_id") != orphan_sprint_id:
            continue
        if t.get("status") in _TERMINAL_STATUSES:
            continue
        proj = t.get("project")
        if proj is None:
            errors.append({"task_id": t["id"], "error": "TASK_MISSING_PROJECT"})
            continue
        if proj not in valid_projects:
            errors.append({
                "task_id": t["id"], "error": "TASK_UNKNOWN_PROJECT",
                "project": proj,
            })
            continue
        to_resprint.append({"task_id": t["id"], "target_project": proj})
    return {"to_resprint": to_resprint, "errors": errors}


def _find_orphan_sprint(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for sp in state["sprints"]:
        if sp.get("project") is None and sp["state"] == "current":
            return sp
    return None


def migrate_to_per_project(actor: str = "bernard",
                           dry_run: bool = False) -> Dict[str, Any]:
    """Migra state.json de v3 (sprints globais) pra v4 (per-project).

    Idempotente: se schema já é v4, retorna noop.
    `dry_run=True` retorna plano sem mutar.
    Fail-fast em data inconsistente (TASK_MISSING_PROJECT, TASK_UNKNOWN_PROJECT).
    """
    state = store.read_state()
    if state.get("schema_version") == 4:
        return {"ok": True, "noop": True, "reason": "already_migrated"}

    valid_projects = store.read_projects()
    orphan = _find_orphan_sprint(state)
    if orphan is None:
        # sem órfã, mas schema é v3 → só faltou o bump
        if not dry_run:
            sprint_lib.bootstrap(actor=actor)
            with store.mutate_state() as st:
                st["schema_version"] = 4
                seq = store.next_seq(st)
                store.append_event({
                    "seq": seq, "ts": store.now_iso(),
                    "type": "schema_migrated",
                    "actor": actor, "from_version": 3, "to_version": 4,
                })
                st["last_event_seq"] = seq
        return {"ok": True, "noop": False, "no_orphan": True}

    plan = _build_resprint_plan(state, orphan["id"], valid_projects)
    if plan["errors"]:
        raise ValueError(
            f"migration blocked by data errors (fix antes de re-rodar): "
            f"{plan['errors']}"
        )

    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "schema_from": 3,
            "schema_to": 4,
            "orphan_sprint_id": orphan["id"],
            "would_resprint": plan["to_resprint"],
            "would_close": orphan["id"],
        }

    # Backup defensivo
    backup_path = store.STATE_PATH.with_suffix(".pre-schema-v4.bak")
    backup_path.write_text(store.STATE_PATH.read_text(encoding="utf-8"),
                           encoding="utf-8")

    # Step 1: bootstrap per-project sprints
    sprint_lib.bootstrap(actor=actor)

    # Step 2-4: re-sprint ativas, fechar órfã, bump schema
    with store.mutate_state() as state:
        # mapa project → current sprint id
        current_by_proj = {}
        for sp in state["sprints"]:
            if sp["state"] == "current" and sp.get("project"):
                current_by_proj[sp["project"]] = sp["id"]

        # re-sprint ativas
        tasks_by_id = {t["id"]: t for t in state["tasks"]}
        for entry in plan["to_resprint"]:
            t = tasks_by_id[entry["task_id"]]
            old_sid = t["sprint_id"]
            new_sid = current_by_proj[entry["target_project"]]
            t["sprint_id"] = new_sid
            t["updated_at"] = store.now_iso()
            seq = store.next_seq(state)
            store.append_event({
                "seq": seq, "ts": store.now_iso(),
                "type": "task_resprinted",
                "actor": actor, "task_id": t["id"],
                "from_sprint_id": old_sid, "to_sprint_id": new_sid,
                "reason": "schema_v4_migration",
            })
            state["last_event_seq"] = seq

        # fechar órfã
        for sp in state["sprints"]:
            if sp["id"] == orphan["id"]:
                sp["state"] = "closed"
                sp["closed_at"] = store.now_iso()
                seq = store.next_seq(state)
                store.append_event({
                    "seq": seq, "ts": store.now_iso(),
                    "type": "sprint_closed",
                    "actor": actor, "sprint_id": sp["id"],
                    "reason": "schema_v4_migration_legacy_global",
                })
                state["last_event_seq"] = seq
                break

        # bump schema
        state["schema_version"] = 4
        seq = store.next_seq(state)
        store.append_event({
            "seq": seq, "ts": store.now_iso(),
            "type": "schema_migrated",
            "actor": actor, "from_version": 3, "to_version": 4,
        })
        state["last_event_seq"] = seq

    return {
        "ok": True,
        "noop": False,
        "schema_from": 3,
        "schema_to": 4,
        "resprinted_count": len(plan["to_resprint"]),
        "closed_orphan": orphan["id"],
        "backup_path": str(backup_path),
    }
```

- [ ] **Step 4: Rodar testes**

Run: `cd ~/.openclaw/kanban-tasks && python3 -m unittest tests.test_migrate_to_per_project.TestMigrateHappyPath -v`
Expected: 4/4 ok.

- [ ] **Step 5: Commit**

```bash
cd ~/.openclaw && git add kanban-tasks/lib/migration.py kanban-tasks/tests/test_migrate_to_per_project.py && git commit -m "$(cat <<'EOF'
feat(kanban/migration): split-and-migrate v3→v4 happy path + dry-run + idempotent

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Migration error cases + audit + backup

**Files:**
- Modify: `kanban-tasks/tests/test_migrate_to_per_project.py` (append 4 tests)
- (notar: backup já implementado em Task 6; se test fail, corrigir)

- [ ] **Step 1: Escrever 4 tests adicionais**

Adicionar ao `test_migrate_to_per_project.py`:

```python
class TestMigrateErrorCases(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from lib import store
        self.tmp_state = Path(self.tmp) / "state.json"
        self.tmp_events = Path(self.tmp) / "events.jsonl"
        self.tmp_projects = Path(self.tmp) / "projects.yml"
        self.tmp_projects.write_text("projects:\n  - bevox-mobile\n")
        self.patches = [
            patch.object(store, "STATE_PATH", self.tmp_state),
            patch.object(store, "EVENTS_PATH", self.tmp_events),
            patch.object(store, "PROJECTS_PATH", self.tmp_projects),
            patch.object(store, "ROOT", Path(self.tmp)),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.tmp)

    def test_migrate_fails_on_task_missing_project(self):
        # state v3 com task ativa project=None
        state = {
            "schema_version": 3, "generated_at": "2026-04-24T00:00:00Z",
            "last_event_seq": 0, "projects": ["bevox-mobile"],
            "sprints": [{
                "id": "sprint-4", "name": "Sprint 4", "state": "current",
                "project": None, "created_at": "2026-04-18T00:00:00Z",
                "closed_at": None, "created_by": "test",
            }],
            "tasks": [{
                "id": "T-200", "title": "no project", "status": "ready",
                "sprint_id": "sprint-4", "project": None,
                "blocked": False, "updated_at": "2026-04-24T00:00:00Z",
                "dispatch_payload": {},
            }],
        }
        self.tmp_state.write_text(json.dumps(state))
        from lib import migration
        with self.assertRaises(ValueError) as ctx:
            migration.migrate_to_per_project(actor="test")
        self.assertIn("TASK_MISSING_PROJECT", str(ctx.exception))
        # state.json não mutou
        post = json.loads(self.tmp_state.read_text())
        self.assertEqual(post["schema_version"], 3)

    def test_migrate_fails_on_unknown_project(self):
        state = {
            "schema_version": 3, "generated_at": "2026-04-24T00:00:00Z",
            "last_event_seq": 0, "projects": ["bevox-mobile"],
            "sprints": [{
                "id": "sprint-4", "name": "Sprint 4", "state": "current",
                "project": None, "created_at": "2026-04-18T00:00:00Z",
                "closed_at": None, "created_by": "test",
            }],
            "tasks": [{
                "id": "T-201", "title": "unknown proj", "status": "ready",
                "sprint_id": "sprint-4", "project": "wat",
                "blocked": False, "updated_at": "2026-04-24T00:00:00Z",
                "dispatch_payload": {},
            }],
        }
        self.tmp_state.write_text(json.dumps(state))
        from lib import migration
        with self.assertRaises(ValueError) as ctx:
            migration.migrate_to_per_project(actor="test")
        self.assertIn("TASK_UNKNOWN_PROJECT", str(ctx.exception))
        post = json.loads(self.tmp_state.read_text())
        self.assertEqual(post["schema_version"], 3)

    def test_migrate_creates_backup_before_mutation(self):
        state = {
            "schema_version": 3, "generated_at": "2026-04-24T00:00:00Z",
            "last_event_seq": 0, "projects": ["bevox-mobile"],
            "sprints": [{
                "id": "sprint-4", "name": "Sprint 4", "state": "current",
                "project": None, "created_at": "2026-04-18T00:00:00Z",
                "closed_at": None, "created_by": "test",
            }],
            "tasks": [{
                "id": "T-300", "title": "ok", "status": "ready",
                "sprint_id": "sprint-4", "project": "bevox-mobile",
                "blocked": False, "updated_at": "2026-04-24T00:00:00Z",
                "dispatch_payload": {},
            }],
        }
        self.tmp_state.write_text(json.dumps(state))
        from lib import migration
        result = migration.migrate_to_per_project(actor="test")
        self.assertTrue(result["ok"])
        backup = self.tmp_state.with_suffix(".pre-schema-v4.bak")
        self.assertTrue(backup.exists())
        # backup tem schema antigo (v3)
        backed = json.loads(backup.read_text())
        self.assertEqual(backed["schema_version"], 3)

    def test_migrate_emits_audit_events(self):
        state = {
            "schema_version": 3, "generated_at": "2026-04-24T00:00:00Z",
            "last_event_seq": 0, "projects": ["bevox-mobile"],
            "sprints": [{
                "id": "sprint-4", "name": "Sprint 4", "state": "current",
                "project": None, "created_at": "2026-04-18T00:00:00Z",
                "closed_at": None, "created_by": "test",
            }],
            "tasks": [{
                "id": "T-400", "title": "ok", "status": "ready",
                "sprint_id": "sprint-4", "project": "bevox-mobile",
                "blocked": False, "updated_at": "2026-04-24T00:00:00Z",
                "dispatch_payload": {},
            }],
        }
        self.tmp_state.write_text(json.dumps(state))
        from lib import migration
        migration.migrate_to_per_project(actor="test")
        # events.jsonl deve ter sprint_created, task_resprinted, sprint_closed, schema_migrated
        events_text = self.tmp_events.read_text()
        types = []
        for line in events_text.splitlines():
            if line.strip():
                types.append(json.loads(line)["type"])
        self.assertIn("sprint_created", types)
        self.assertIn("task_resprinted", types)
        self.assertIn("sprint_closed", types)
        self.assertIn("schema_migrated", types)
```

- [ ] **Step 2: Rodar testes**

Run: `cd ~/.openclaw/kanban-tasks && python3 -m unittest tests.test_migrate_to_per_project.TestMigrateErrorCases -v`
Expected: 4/4 ok (a impl em Task 6 já cobre estes casos).

Se algum falha, ajustar `migration.py` pra atingir o teste — provavelmente já está OK porque o helper `_build_resprint_plan` já coleta erros.

- [ ] **Step 3: Suite migration completa**

Run: `cd ~/.openclaw/kanban-tasks && python3 -m unittest tests.test_migrate_to_per_project -v 2>&1 | tail -5`
Expected: 8/8 ok.

- [ ] **Step 4: Commit**

```bash
cd ~/.openclaw && git add kanban-tasks/tests/test_migrate_to_per_project.py && git commit -m "$(cat <<'EOF'
test(kanban/migration): error cases + backup creation + audit events

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: CLI subparsers (sprint bootstrap + sprint migrate-to-per-project)

**Files:**
- Modify: `kanban-tasks/lib/api.py`

- [ ] **Step 1: Localizar subparser de `sprint` em api.py**

Run: `grep -n "sprint\|subparser" ~/.openclaw/kanban-tasks/lib/api.py | head -20`

Identificar onde subparsers de sprint são criados (provavelmente em uma função `_setup_sprint_parser` ou similar).

- [ ] **Step 2: Adicionar/modificar subparsers**

Em `lib/api.py`, na seção que adiciona subparsers de sprint:

```python
# bootstrap (read projects.yml)
boot = sprint_sub.add_parser("bootstrap",
    help="Cria current+next pra cada projeto em projects.yml (idempotente)")
boot.add_argument("--actor", default="bernard")
boot.add_argument("--project", default=None,
    help="Override: bootstrap só pra um projeto específico")
boot.add_argument("--dry-run", action="store_true")
boot.add_argument("--json", action="store_true")
boot.set_defaults(func=cmd_sprint_bootstrap)

# migrate-to-per-project
mig = sprint_sub.add_parser("migrate-to-per-project",
    help="Migra state.json de schema v3 (global) pra v4 (per-project)")
mig.add_argument("--actor", default="bernard")
mig.add_argument("--dry-run", action="store_true")
mig.add_argument("--json", action="store_true")
mig.set_defaults(func=cmd_sprint_migrate_to_per_project)


def cmd_sprint_bootstrap(args) -> int:
    from . import sprint as sprint_lib
    projects = [args.project] if args.project else None
    try:
        result = sprint_lib.bootstrap(
            actor=args.actor, projects=projects, dry_run=args.dry_run)
    except Exception as e:
        return _err(str(e), "BOOTSTRAP_FAILED", args.json)
    if args.json:
        print(json.dumps(result, default=str, indent=2))
    else:
        if args.dry_run:
            print(f"DRY RUN — would create {len(result['would_create'])} sprints:")
            for proj, st in result['would_create']:
                print(f"  {proj}: {st}")
        else:
            created = result.get("created", [])
            print(f"created {len(created)} sprints:")
            for sp in created:
                print(f"  {sp['id']} ({sp['state']}) project={sp['project']}")
    return EXIT_OK


def cmd_sprint_migrate_to_per_project(args) -> int:
    from . import migration
    try:
        result = migration.migrate_to_per_project(
            actor=args.actor, dry_run=args.dry_run)
    except ValueError as e:
        return _err(str(e), "MIGRATION_FAILED", args.json)
    if args.json:
        print(json.dumps(result, default=str, indent=2))
    else:
        if result.get("noop"):
            print(f"noop: {result.get('reason', '?')}")
        elif result.get("dry_run"):
            print(f"DRY RUN — would migrate to schema v4:")
            print(f"  resprint {len(result.get('would_resprint', []))} tasks")
            print(f"  close orphan sprint {result.get('would_close', '?')}")
        else:
            print(f"migrated to schema v4:")
            print(f"  resprinted {result['resprinted_count']} tasks")
            print(f"  closed orphan {result['closed_orphan']}")
            print(f"  backup at {result['backup_path']}")
    return EXIT_OK
```

- [ ] **Step 3: Smoke manual**

```bash
cd ~/.openclaw/kanban-tasks && ./cli.sh sprint bootstrap --help 2>&1 | head -10
./cli.sh sprint migrate-to-per-project --help 2>&1 | head -10
```

Expected: ambos help screens funcionais.

- [ ] **Step 4: Commit**

```bash
cd ~/.openclaw && git add kanban-tasks/lib/api.py && git commit -m "$(cat <<'EOF'
feat(kanban/api): subparsers sprint bootstrap + sprint migrate-to-per-project

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Scrum-master materializer per-project resolve

**Files:**
- Create: `scrum-master-agent/tests/test_materializer_per_project_sprint.py`
- Modify: `scrum-master-agent/lib/materializer.py:138`

- [ ] **Step 1: Escrever 3 testes**

Write `~/.openclaw/scrum-master-agent/tests/test_materializer_per_project_sprint.py`:

```python
"""Tests materializer resolve sprint_target per-project (schema v4)."""
import unittest
from unittest.mock import patch, MagicMock


class TestMaterializerPerProjectSprint(unittest.TestCase):
    def test_materialize_resolves_sprint_target_per_project(self):
        """proposal de bevox-mobile com sprint_target=current vai pra current de bevox-mobile."""
        from lib import materializer

        state = {
            "schema_version": 4,
            "sprints": [
                {"id": "sprint-7", "state": "current", "project": "bevox-mobile"},
                {"id": "sprint-8", "state": "next", "project": "bevox-mobile"},
                {"id": "sprint-9", "state": "current", "project": "bevox-backend"},
            ],
            "tasks": [],
        }
        # Stub: chama _resolve_target diretamente (helper interno se existir)
        # OU testa o path através de materialize_one fixture
        sid = materializer._resolve_target_sprint(state, "current", "bevox-mobile")
        self.assertEqual(sid, "sprint-7")
        sid2 = materializer._resolve_target_sprint(state, "current", "bevox-backend")
        self.assertEqual(sid2, "sprint-9")

    def test_materialize_fails_no_sprint_for_project(self):
        from lib import materializer
        state = {
            "schema_version": 4,
            "sprints": [
                {"id": "sprint-7", "state": "current", "project": "bevox-mobile"},
            ],
            "tasks": [],
        }
        with self.assertRaises(ValueError) as ctx:
            materializer._resolve_target_sprint(state, "current", "bevox-backend")
        self.assertIn("NO_SPRINT_FOR_PROJECT", str(ctx.exception))

    def test_materialize_target_next_works_per_project(self):
        from lib import materializer
        state = {
            "schema_version": 4,
            "sprints": [
                {"id": "sprint-7", "state": "current", "project": "bevox-mobile"},
                {"id": "sprint-8", "state": "next", "project": "bevox-mobile"},
            ],
            "tasks": [],
        }
        sid = materializer._resolve_target_sprint(state, "next", "bevox-mobile")
        self.assertEqual(sid, "sprint-8")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar testes**

Run: `cd ~/.openclaw/scrum-master-agent && python3 -m unittest tests.test_materializer_per_project_sprint -v`
Expected: AttributeError em `_resolve_target_sprint` (ainda não existe).

- [ ] **Step 3: Modificar `lib/materializer.py:138`**

Localizar o bloco `if target in ("current", "next"):` (linha ~138) e refatorar pra usar helper:

```python
def _resolve_target_sprint(state: dict, target: str, project: str) -> str:
    """Resolve sprint_target ('current'|'next'|literal) per-project.

    Aliases requerem project. Raise ValueError com NO_SPRINT_FOR_PROJECT
    se projeto não tem o sprint pedido.
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
```

E na linha onde antes era:

```python
if target in ("current", "next"):
    sprint_id = find_sprint(state, target).id
```

Substituir por:

```python
project = task["project"]   # já populado em proposal validation
sprint_id = _resolve_target_sprint(state, target, project)
```

- [ ] **Step 4: Rodar testes**

Run: `cd ~/.openclaw/scrum-master-agent && python3 -m unittest tests.test_materializer_per_project_sprint -v`
Expected: 3/3 ok.

- [ ] **Step 5: Regression — wave-8 tests**

Run: `cd ~/.openclaw/scrum-master-agent && python3 -m unittest discover -v 2>&1 | tail -8`
Expected: 38/38 (ou número atual) tests pass — zero regressão na suite wave-8.

Se algum test pré-existente falha, ajustar fixtures pra populá-las com schema v4 (cada sprint tem project) e propagar `task["project"]` em mocks.

- [ ] **Step 6: Commit**

```bash
cd ~/.openclaw && git add scrum-master-agent/lib/materializer.py scrum-master-agent/tests/test_materializer_per_project_sprint.py && git commit -m "$(cat <<'EOF'
feat(scrum-master/materializer): resolve sprint_target per-project (schema v4)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Dispatcher selector — sprint filter + kill-switch

**Files:**
- Create: `dispatcher-agent/tests/test_selector_sprint_filter.py`
- Modify: `dispatcher-agent/lib/selector.py:62-86` (substitui `select_next_ready`)

- [ ] **Step 1: Escrever 5 testes**

Write `~/.openclaw/dispatcher-agent/tests/test_selector_sprint_filter.py`:

```python
"""Tests dispatcher selector com sprint filter (per-project) + kill-switch."""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def _seed_state(state_path: Path, *, current_sprint_for_proj=None,
                tasks=None):
    """Cria state.json mínimo. Default: sem current pra teste de no-current."""
    sprints = []
    if current_sprint_for_proj:
        for proj, sid in current_sprint_for_proj.items():
            sprints.append({
                "id": sid, "name": f"Sprint X", "state": "current",
                "project": proj, "created_at": "2026-04-25T00:00:00Z",
                "closed_at": None, "created_by": "test",
            })
    state_path.write_text(json.dumps({
        "schema_version": 4,
        "sprints": sprints,
        "tasks": tasks or [],
    }))


class TestSelectorSprintFilter(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from lib import selector
        self.state_path = Path(self.tmp) / "state.json"
        self.patcher = patch.object(selector, "KANBAN_STATE", self.state_path)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        shutil.rmtree(self.tmp)
        os.environ.pop("OPENCLAW_DISPATCHER_IGNORE_SPRINT", None)

    def test_selector_filters_by_current_sprint(self):
        """Tasks ready em current sprint dispatchadas; em next sprint ignoradas."""
        _seed_state(self.state_path,
            current_sprint_for_proj={"test-project": "sprint-7"},
            tasks=[
                {"id": "T-1", "title": "in current", "status": "ready",
                 "sprint_id": "sprint-7", "project": "test-project",
                 "blocked": False, "created_at": "2026-04-25T00:00:00Z",
                 "dispatch_payload": {}},
                {"id": "T-2", "title": "in next", "status": "ready",
                 "sprint_id": "sprint-8", "project": "test-project",
                 "blocked": False, "created_at": "2026-04-25T00:00:00Z",
                 "dispatch_payload": {}},
            ])
        from lib import selector
        result = selector.select_next_ready("test-project")
        self.assertEqual(result["id"], "T-1")

    def test_selector_kill_switch_disables_filter(self):
        """OPENCLAW_DISPATCHER_IGNORE_SPRINT=1 → ignora filtro, retorna ready de qualquer sprint."""
        _seed_state(self.state_path,
            current_sprint_for_proj={"test-project": "sprint-7"},
            tasks=[
                {"id": "T-OUT", "title": "fora do sprint", "status": "ready",
                 "sprint_id": "sprint-99", "project": "test-project",
                 "blocked": False, "created_at": "2026-04-25T00:00:00Z",
                 "dispatch_payload": {}},
            ])
        os.environ["OPENCLAW_DISPATCHER_IGNORE_SPRINT"] = "1"
        from lib import selector
        result = selector.select_next_ready("test-project")
        self.assertEqual(result["id"], "T-OUT")

    def test_selector_no_current_sprint_raises(self):
        """Projeto sem current sprint → SelectorError NO_CURRENT_SPRINT."""
        _seed_state(self.state_path,
            current_sprint_for_proj=None,  # ninguém tem current
            tasks=[
                {"id": "T-X", "title": "lonely", "status": "ready",
                 "sprint_id": "sprint-7", "project": "test-project",
                 "blocked": False, "created_at": "2026-04-25T00:00:00Z",
                 "dispatch_payload": {}},
            ])
        from lib import selector
        with self.assertRaises(selector.SelectorError) as ctx:
            selector.select_next_ready("test-project")
        self.assertEqual(ctx.exception.code, "NO_CURRENT_SPRINT")

    def test_selector_respects_blocked_flag(self):
        """Task em current sprint mas blocked=True → ignorada."""
        _seed_state(self.state_path,
            current_sprint_for_proj={"test-project": "sprint-7"},
            tasks=[
                {"id": "T-B", "title": "blocked", "status": "ready",
                 "sprint_id": "sprint-7", "project": "test-project",
                 "blocked": True, "created_at": "2026-04-25T00:00:00Z",
                 "dispatch_payload": {}},
                {"id": "T-OK", "title": "ok", "status": "ready",
                 "sprint_id": "sprint-7", "project": "test-project",
                 "blocked": False, "created_at": "2026-04-25T00:01:00Z",
                 "dispatch_payload": {}},
            ])
        from lib import selector
        result = selector.select_next_ready("test-project")
        self.assertEqual(result["id"], "T-OK")

    def test_selector_returns_oldest_first(self):
        """Ordering por created_at ascendente preservada."""
        _seed_state(self.state_path,
            current_sprint_for_proj={"test-project": "sprint-7"},
            tasks=[
                {"id": "T-NEW", "title": "newer", "status": "ready",
                 "sprint_id": "sprint-7", "project": "test-project",
                 "blocked": False, "created_at": "2026-04-25T10:00:00Z",
                 "dispatch_payload": {}},
                {"id": "T-OLD", "title": "older", "status": "ready",
                 "sprint_id": "sprint-7", "project": "test-project",
                 "blocked": False, "created_at": "2026-04-25T08:00:00Z",
                 "dispatch_payload": {}},
            ])
        from lib import selector
        result = selector.select_next_ready("test-project")
        self.assertEqual(result["id"], "T-OLD")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar testes**

Run: `cd ~/.openclaw/dispatcher-agent && python3 -m unittest tests.test_selector_sprint_filter -v`
Expected: 5 FAILs (selector ainda não filtra por sprint).

- [ ] **Step 3: Modificar `lib/selector.py` — substitui `select_next_ready`**

```python
import os


def _get_current_sprint_for(state, project):
    for sp in state.get("sprints", []):
        if sp.get("state") == "current" and sp.get("project") == project:
            return sp
    return None


def select_next_ready(project):
    """Retorna primeira task ready nao-blocked do projeto, no current sprint.

    Filtro por current sprint do projeto (schema v4).
    Kill-switch via OPENCLAW_DISPATCHER_IGNORE_SPRINT=1 → pula filtro.
    Ordena por created_at ascendente. Raise NO_READY_TASK ou NO_CURRENT_SPRINT.
    """
    state = _read_state()
    ignore_sprint = os.environ.get("OPENCLAW_DISPATCHER_IGNORE_SPRINT") == "1"

    current = None
    if not ignore_sprint:
        current = _get_current_sprint_for(state, project)
        if current is None:
            raise SelectorError(
                "NO_CURRENT_SPRINT",
                f"projeto {project!r} não tem current sprint. "
                f"Rode `kanban-tasks/cli.sh sprint bootstrap`."
            )

    candidates = []
    for t in state.get("tasks", []):
        if t.get("status") != "ready":
            continue
        if t.get("blocked"):
            continue
        if project is not None and t.get("project") != project:
            continue
        if not ignore_sprint and t.get("sprint_id") != current["id"]:
            continue
        candidates.append(t)

    if not candidates:
        msg = "nenhuma task ready nao-blocked"
        if project:
            msg += f" no projeto '{project}'"
        if not ignore_sprint and current is not None:
            msg += f" no current sprint ({current['id']})"
        msg += (". Rode `vox scrum-master` OU `kanban-tasks/cli.sh task move <id> ready`")
        raise SelectorError("NO_READY_TASK", msg)

    candidates.sort(key=lambda t: t.get("created_at", ""))
    return candidates[0]
```

- [ ] **Step 4: Rodar testes**

Run: `cd ~/.openclaw/dispatcher-agent && python3 -m unittest tests.test_selector_sprint_filter -v`
Expected: 5/5 ok.

- [ ] **Step 5: Suite completa dispatcher**

Run: `cd ~/.openclaw/dispatcher-agent && python3 -m unittest discover -v 2>&1 | tail -8`
Expected: notifier tests (6/6 do wave anterior) + selector novos (5/5) green.

- [ ] **Step 6: Commit**

```bash
cd ~/.openclaw && git add dispatcher-agent/lib/selector.py dispatcher-agent/tests/test_selector_sprint_filter.py && git commit -m "$(cat <<'EOF'
feat(dispatcher/selector): filter por current sprint + kill-switch OPENCLAW_DISPATCHER_IGNORE_SPRINT

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Dispatcher cron audit — current_sprint_id + skip_reason

**Files:**
- Modify: `dispatcher-agent/lib/cron.py`

- [ ] **Step 1: Localizar onde cron-tick monta o entry de actions_per_project**

Run: `grep -n "actions_per_project\|skip_reason\|skipped_no_ready\|skipped_busy" ~/.openclaw/dispatcher-agent/lib/cron.py | head -10`

- [ ] **Step 2: Adicionar `current_sprint_id` no metadata por projeto**

Localizar bloco que constrói `action = {"project": ..., "outcome": ..., ...}`. Antes do append, adicionar:

```python
# Schema v4: capturar current sprint pra audit
current_sid = None
ignore_sprint = os.environ.get("OPENCLAW_DISPATCHER_IGNORE_SPRINT") == "1"
if not ignore_sprint:
    state = _read_kanban_state()
    cur = next((sp for sp in state.get("sprints", [])
                if sp.get("state") == "current"
                and sp.get("project") == proj), None)
    if cur:
        current_sid = cur["id"]

# ... dentro do action dict:
action["current_sprint_id"] = current_sid
```

E onde captura SelectorError, adicionar handling pra `NO_CURRENT_SPRINT`:

```python
except selector_lib.SelectorError as e:
    if e.code == "NO_CURRENT_SPRINT":
        action = {"project": proj, "outcome": "skipped_no_current_sprint",
                  "skip_reason": e.detail, "task_id": None,
                  "current_sprint_id": None}
    elif e.code == "NO_READY_TASK":
        action = {"project": proj, "outcome": "skipped_no_ready",
                  "skip_reason": e.detail, "task_id": None,
                  "current_sprint_id": current_sid}
    else:
        action = {"project": proj, "outcome": "skipped_error",
                  "skip_reason": str(e), "task_id": None,
                  "current_sprint_id": current_sid}
```

- [ ] **Step 3: Smoke manual após deploy (sem teste unitário pra cron — integration depois)**

Skip teste unitário direto desta mudança — coverage via E2E na §7.6 da spec (Task 16).

- [ ] **Step 4: Commit**

```bash
cd ~/.openclaw && git add dispatcher-agent/lib/cron.py && git commit -m "$(cat <<'EOF'
feat(dispatcher/cron): audit jsonl ganha current_sprint_id + skipped_no_current_sprint outcome

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: README updates (kanban-tasks + dispatcher-agent)

**Files:**
- Modify: `kanban-tasks/README.md`
- Modify: `dispatcher-agent/README.md`

- [ ] **Step 1: kanban-tasks/README.md**

Adicionar seção "Sprint per-project (schema v4)":

```markdown
## Sprint per-project (schema v4)

Desde 2026-04-25 (wave `sprint-per-project`), cada projeto canônico em
`projects.yml` tem seu próprio par `current` + `next` independente.

### Bootstrap

```bash
# Cria current+next pra cada projeto em projects.yml que ainda não tem
./cli.sh sprint bootstrap

# Override: só para um projeto específico
./cli.sh sprint bootstrap --project bevox-mobile

# Plan-only (sem mutação)
./cli.sh sprint bootstrap --dry-run
```

Idempotente: projetos que já têm current+next são skipados.

### Close per-project

```bash
./cli.sh sprint close-current --project bevox-mobile --actor bernard \
  --carryover '[{"task_id":"T-50","action":"move_current"},{"task_id":"T-51","action":"archive"}]'
```

Fecha current de bevox-mobile, promove next→current, nasce novo next.
Outros projetos intocados.

### Migração v3→v4

Comando one-shot rodado pós-deploy do schema v4:

```bash
./cli.sh sprint migrate-to-per-project --dry-run   # inspeciona plano
./cli.sh sprint migrate-to-per-project              # aplica
```

Backup defensivo automático em `state.json.pre-schema-v4.bak`.
Idempotente (re-rodar = noop "already_migrated").
```

- [ ] **Step 2: dispatcher-agent/README.md**

Adicionar seção sobre sprint filter:

```markdown
## Sprint filter (schema v4)

Desde 2026-04-25, dispatcher só dispatcha tasks que estão na **current
sprint do projeto da task**. Tasks em `next` sprint (ou outras) são
ignoradas até `close-current` promover next→current.

### Kill-switch

Se houver bug no filtro, restaurar comportamento legado em <30s:

```bash
systemctl --user edit openclaw-cron-dispatcher.service
# adiciona:
[Service]
Environment="OPENCLAW_DISPATCHER_IGNORE_SPRINT=1"

systemctl --user daemon-reload
systemctl --user restart openclaw-cron-dispatcher.timer
```

Filtro vira no-op, dispatcher volta a aceitar qualquer task ready.
Schema continua per-project (sprints intactos), só o filtro é desabilitado.

### Audit

`cron.jsonl` captura por tick:
- `current_sprint_id` pra cada projeto considerado
- Outcome novo `skipped_no_current_sprint` se projeto não tem current
```

- [ ] **Step 3: Commit**

```bash
cd ~/.openclaw && git add kanban-tasks/README.md dispatcher-agent/README.md && git commit -m "$(cat <<'EOF'
docs(kanban+dispatcher): documentar sprint per-project + kill-switch

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: Push openclaw PR + merge gate

**Files:**
- (push only)

- [ ] **Step 1: Verificar branch + status**

```bash
cd ~/.openclaw && git status --short
git log --oneline main..HEAD | head -15
```

Expected: branch `feat/sprint-per-project` com ~12 commits.

- [ ] **Step 2: Push**

```bash
cd ~/.openclaw && git push -u origin feat/sprint-per-project
```

- [ ] **Step 3: Abrir PR**

```bash
cd ~/.openclaw && gh pr create --title "feat(openclaw): sprint per-project schema (E10/sprint-per-project)" --body "$(cat <<'EOF'
## Summary
Schema mudança: kanban-tasks vira strictly per-project (schema_version 3→4). Cada projeto canônico tem 1 current + 1 next ativos simultâneos. Migração split-and-migrate da sprint-4 órfã (27 tasks de 3 projetos redistribuídas).

Consumer updates síncronos: scrum-master materializer + dispatcher selector com filtro de sprint + kill-switch \`OPENCLAW_DISPATCHER_IGNORE_SPRINT=1\`. MC UI fica em PR separado pós-deploy.

Spec: \`bevox-knowledge/35_specs/openclaw/2026-04-25-sprint-per-project.md\` (PR #merged)

## Test plan
- [x] kanban-tasks: 12+8 unit tests novos (sprint per-project + migration)
- [x] scrum-master: 3 unit tests novos (materializer per-project)
- [x] dispatcher: 5 unit tests novos (selector filter + kill-switch)
- [x] Suite completa: zero regressão wave anteriores (notifier + wave-8 + outros)
- [ ] Pós-merge: pull main → \`sprint migrate-to-per-project --dry-run\` → inspect → run sem dry-run
- [ ] Restart timers: \`systemctl --user restart openclaw-cron-dispatcher.timer openclaw-reaper.timer\`
- [ ] Smoke E2E §7.6 spec (5 cenários)

## Rollback
- Tier 1 (kill-switch): \`OPENCLAW_DISPATCHER_IGNORE_SPRINT=1\` em dropin → 30s
- Tier 2 (state restore): \`cp state.json.pre-schema-v4.bak state.json && git revert <merge>\` → minutos
- Tier 3 (abort total): revert + tracker rollback

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 4: PAUSA — aguardar Bernard mergear o PR**

Parar aqui. Bernard revisa + merge. Retomar Task 14 só após confirmação de merge em main.

---

## Task 14: Pull + dry-run + run migration + restart services

**Pré-requisito:** PR mergeada; `main` no GitHub atualizada.

- [ ] **Step 1: Pull main local**

```bash
cd ~/.openclaw && git checkout main && git pull --ff-only
git log --oneline -5
```

Expected: merge commit visível no top.

- [ ] **Step 2: Dry-run migration**

```bash
~/.openclaw/kanban-tasks/cli.sh sprint migrate-to-per-project --dry-run
```

Inspecionar output. Esperado:
- `would_resprint` = lista de tasks ativas (T-0024..T-0036 da bevox-backend, etc.)
- `would_close` = sprint-4
- Nenhum erro

Se houver erro `TASK_MISSING_PROJECT` ou `TASK_UNKNOWN_PROJECT`, **PAUSA** + arruma data antes (move tasks pra projeto válido OU adiciona projeto faltante em `projects.yml`) + re-roda dry-run.

- [ ] **Step 3: Apply migration**

```bash
~/.openclaw/kanban-tasks/cli.sh sprint migrate-to-per-project --actor bernard
```

Esperado: output mostra `migrated to schema v4`, count de tasks resprintadas, backup path.

- [ ] **Step 4: Verificar invariantes**

```bash
python3 -c "
import json
s = json.load(open('~/.openclaw/kanban-tasks/state.json'))
print('schema_version:', s['schema_version'])
print('projects:', s['projects'])
active = [sp for sp in s['sprints'] if sp['state'] in ('current','next')]
by_proj = {}
for sp in active:
    by_proj.setdefault(sp.get('project'), []).append(sp['state'])
for p, sts in by_proj.items():
    ok = '✅' if sorted(sts) == ['current','next'] else '❌'
    print(f'  {ok} {p}: {sorted(sts)}')
"
```

Expected: schema_version 4, cada projeto canônico com `[current, next]` pareado.

- [ ] **Step 5: Restart serviços**

```bash
systemctl --user daemon-reload
systemctl --user restart openclaw-cron-dispatcher.timer openclaw-reaper.timer
systemctl --user list-timers --no-pager | grep -E "cron-dispatcher|reaper" | head
```

Expected: timers active.

- [ ] **Step 6: Verificar primeiro tick pós-deploy**

Aguardar ~60s + checar:

```bash
tail -1 ~/.openclaw/dispatcher-agent/cron.jsonl | python3 -m json.tool
```

Expected: tick com novo campo `current_sprint_id` populado pra projetos com sprint, OR `skipped_no_current_sprint` pra projetos sem sprint (não deveria ter — bootstrap cobriu todos).

---

## Task 15: Smoke E2E (5 cenários gating delivery)

**Pré-requisito:** Task 14 completa; serviços rodando schema v4.

- [ ] **Cenário 1: sprint list mostra current+next por projeto**

```bash
~/.openclaw/kanban-tasks/cli.sh sprint list --json | python3 -c "
import sys, json
data = json.load(sys.stdin)
sprints = data.get('sprints', [])
active = [sp for sp in sprints if sp['state'] in ('current','next')]
by_proj = {}
for sp in active:
    by_proj.setdefault(sp.get('project'), []).append(sp['state'])
import sys
all_ok = True
for p, sts in by_proj.items():
    s = sorted(sts)
    ok = s == ['current','next']
    print(f'  {p}: {s} {\"✅\" if ok else \"❌\"}')
    if not ok: all_ok = False
sys.exit(0 if all_ok else 1)
"
```

Expected exit 0; cada projeto com par `[current, next]`.

- [ ] **Cenário 2: tasks ativas pré-existentes corretamente re-sprintadas**

```bash
python3 -c "
import json
s = json.load(open('~/.openclaw/kanban-tasks/state.json'))
sprints_by_id = {sp['id']: sp for sp in s['sprints']}
violations = []
for t in s['tasks']:
    if t.get('status') in ('archived','done','rejected'):
        continue
    sp = sprints_by_id.get(t.get('sprint_id'))
    if sp is None:
        violations.append((t['id'], 'MISSING_SPRINT'))
        continue
    if sp.get('project') and sp['project'] != t.get('project'):
        violations.append((t['id'], f'MISMATCH sp.project={sp[\"project\"]} t.project={t.get(\"project\")}'))
print(f'violations: {len(violations)}')
for v in violations: print(' ', v)
import sys; sys.exit(1 if violations else 0)
"
```

Expected exit 0.

- [ ] **Cenário 3: smoke synthetic happy path → notifier dispara**

```bash
~/.openclaw/kanban-tasks/cli.sh task add "smoke-sprint-v4-current" --project test-project --actor bernard --payload '{"goal":"Criar ~/sprint-v4-smoke.txt com texto ok","acceptance_criteria":["Arquivo existe"],"spec_ref":"n/a-smoke"}'
# captura task id criado
TID=$(~/.openclaw/kanban-tasks/cli.sh task list --json | python3 -c "
import sys, json
tasks = json.load(sys.stdin)['tasks']
matches = [t for t in tasks if 'smoke-sprint-v4-current' in (t.get('title') or '')]
print(matches[-1]['id'] if matches else '')")
echo "TID=$TID"
~/.openclaw/kanban-tasks/cli.sh task move $TID ready --actor bernard
```

Aguardar até 90s. Verificar:

```bash
tail -1 ~/.openclaw/dispatcher-agent/notifier.jsonl
```

Expected: `task_event_sent` com `outcome: "done"` e o TID. Mensagem `✅` no Telegram tópico dispatcher.

- [ ] **Cenário 4: task em next sprint NÃO dispatcha**

```bash
~/.openclaw/kanban-tasks/cli.sh task add "smoke-sprint-v4-next" --project test-project --actor bernard --sprint next --payload '{"goal":"echo skip","acceptance_criteria":["x"],"spec_ref":"n/a-smoke"}'
TID2=$(~/.openclaw/kanban-tasks/cli.sh task list --json | python3 -c "
import sys, json
tasks = json.load(sys.stdin)['tasks']
matches = [t for t in tasks if 'smoke-sprint-v4-next' in (t.get('title') or '')]
print(matches[-1]['id'] if matches else '')")
~/.openclaw/kanban-tasks/cli.sh task move $TID2 ready --actor bernard
```

Aguardar 90s. Verificar:

```bash
python3 -c "
import json
s = json.load(open('~/.openclaw/kanban-tasks/state.json'))
t = next(t for t in s['tasks'] if t['id'] == '$TID2')
print(f'status: {t[\"status\"]}')
"
```

Expected: status ainda `ready` (não dispatchou) — dispatcher ignorou porque task está em next sprint, não current.

Verificar audit:
```bash
tail -3 ~/.openclaw/dispatcher-agent/cron.jsonl | python3 -c "
import sys, json
for line in sys.stdin:
    if line.strip():
        d = json.loads(line)
        for a in d.get('actions_per_project', []):
            if a.get('project') == 'test-project':
                print(f\"  outcome={a['outcome']} current_sprint_id={a.get('current_sprint_id')} skip={a.get('skip_reason','')[:60]}\")
"
```

Expected: `outcome=skipped_no_ready` (task em next não conta como ready do current sprint).

- [ ] **Cenário 5: close-current per-project**

```bash
~/.openclaw/kanban-tasks/cli.sh sprint close-current --project test-project --actor bernard --carryover "[{\"task_id\":\"$TID2\",\"action\":\"move_current\"}]"
```

Expected: success output com `closed: sprint-X, promoted_to_current: sprint-Y, new_next: sprint-Z`.

Verificar bevox-mobile/etc intactos:
```bash
python3 -c "
import json
s = json.load(open('~/.openclaw/kanban-tasks/state.json'))
mob = [sp for sp in s['sprints'] if sp.get('project') == 'bevox-mobile' and sp['state'] in ('current','next')]
print('bevox-mobile active sprints:', sorted(sp['state'] for sp in mob))
"
```

Expected: `['current', 'next']` — outros projetos intocados.

Aguardar ~60s. T-id2 (que estava em next, agora foi promovido) deve dispatchar e produzir notifier ✅.

- [ ] **Step Final: GATE**

Se todos 5 cenários pass → prosseguir Task 16 (MC UI). Se algum falha → **rollback Tier 2** + investigar:

```bash
cp ~/.openclaw/kanban-tasks/state.json.pre-schema-v4.bak ~/.openclaw/kanban-tasks/state.json
cd ~/.openclaw && git revert <merge-sha> && git push
```

---

## Task 16: Mission Control — API routes update

**Files (separate repo `~/code/mission-control`):**
- Modify: `src/app/api/kanban/state/route.ts`
- Modify: `src/app/api/kanban/tasks/route.ts`
- Modify: `src/app/api/kanban/tasks/[id]/move-to-sprint/route.ts`
- Create/Modify: `tests/app/api/kanban/state.route.test.ts`

- [ ] **Step 1: Branch novo no MC**

```bash
cd ~/code/mission-control && git checkout main && git pull --ff-only
git checkout -b feat/sprint-per-project-ui
```

- [ ] **Step 2: Escrever vitest pra `state` route**

Em `tests/app/api/kanban/state.route.test.ts`, adicionar (ou criar se não existe):

```typescript
import { describe, it, expect, beforeEach, vi } from "vitest";
// ... setup pattern from existing tests

describe("GET /api/kanban/state currentSprintByProject", () => {
  it("returns map of project → current sprint id", async () => {
    // setup: state.json fixture com schema v4 + 2 projetos
    // GET /api/kanban/state
    // assert response.body.currentSprintByProject == {bevox-mobile: "sprint-7", bevox-backend: "sprint-9"}
  });
});
```

(Implementação concreta depende dos test patterns existentes — usar `MC_HOME` env override conforme `tests/app/api/projects/list.route.test.ts`.)

- [ ] **Step 3: Modificar `src/app/api/kanban/state/route.ts`**

Adicionar campo `currentSprintByProject` no GET response:

```typescript
// Após ler state.json:
const currentSprintByProject: Record<string, string> = {};
for (const sp of state.sprints || []) {
  if (sp.state === "current" && sp.project) {
    currentSprintByProject[sp.project] = sp.id;
  }
}

return NextResponse.json({
  ...existingFields,
  currentSprintByProject,
});
```

- [ ] **Step 4: Modificar `tasks/route.ts` (POST)**

POST `/api/kanban/tasks` já recebe `project` no body — propagar pro CLI. Localizar onde chama `kanban-tasks/cli.sh task add ...` e garantir `--project ${body.project}` é incluído.

- [ ] **Step 5: Modificar `tasks/[id]/move-to-sprint/route.ts`**

Antes de chamar CLI, derivar project do task:

```typescript
// Read state, find task
const task = state.tasks.find((t: any) => t.id === params.id);
if (!task) return NextResponse.json({error: "task_not_found"}, {status: 404});

// Pass project pra CLI (CLI internamente usa pra resolver alias current/next)
const cliArgs = ["task", "move-to-sprint", params.id, body.sprint, "--project", task.project, ...];
```

- [ ] **Step 6: Rodar tests + typecheck**

```bash
cd ~/code/mission-control && npm test -- --run 2>&1 | tail -10
npm run typecheck 2>&1 | tail -5
```

Expected: tests pass, zero type errors.

- [ ] **Step 7: Commit**

```bash
cd ~/code/mission-control && git add src/app/api/kanban/ tests/ && git commit -m "$(cat <<'EOF'
feat(api/kanban): currentSprintByProject map + project-aware sprint resolution

- /api/kanban/state inclui currentSprintByProject pra UI consumir nos filters
- POST /api/kanban/tasks propaga project pra CLI
- POST /api/kanban/tasks/[id]/move-to-sprint deriva project do task

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Task 17: Mission Control — UI components update

**Files (separate repo):**
- Modify: `src/components/kanban/useFilterPersistence.ts`
- Modify: `src/components/kanban/NewTaskModal.tsx`
- Modify: `src/components/kanban/DetailDrawer.tsx`
- Create/Modify: `tests/components/kanban/NewTaskModal.test.tsx`

- [ ] **Step 1: vitest pra NewTaskModal**

Criar/modificar `tests/components/kanban/NewTaskModal.test.tsx`:

```typescript
import { render, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import NewTaskModal from "@/components/kanban/NewTaskModal";

describe("NewTaskModal sprint resolution", () => {
  it("passes project + sprint_target in submit payload", async () => {
    const onSubmit = vi.fn();
    const { getByLabelText, getByRole } = render(
      <NewTaskModal isOpen={true} onClose={vi.fn()} onSubmit={onSubmit}
        defaultProject="bevox-mobile" defaultSprint="current" />
    );
    fireEvent.change(getByLabelText("Title"), {target: {value: "T-test"}});
    fireEvent.click(getByRole("button", {name: /submit/i}));
    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          project: "bevox-mobile",
          sprint: "current",
        })
      );
    });
  });
});
```

(Ajustar imports + props ao formato real do componente.)

- [ ] **Step 2: Rodar test (deve falhar se NewTaskModal não passa project)**

```bash
cd ~/code/mission-control && npm test -- --run tests/components/kanban/NewTaskModal 2>&1 | tail -5
```

- [ ] **Step 3: Modificar `useFilterPersistence.ts`**

Tipo `sprint: "current" | "next"` continua. Adicionar consumo do `currentSprintByProject` quando filtrar:

```typescript
// Helper: dado o project filter ativo, retorna o sprint id atual
export function resolveCurrentSprintId(
  project: string,
  sprintLabel: "current" | "next",
  currentSprintByProject: Record<string, string>,
  // ... lookup analogo pra next
): string | null {
  if (sprintLabel === "current") return currentSprintByProject[project] ?? null;
  // next: precisa de lookup similar — adicionar nextSprintByProject no API state response
  return null;
}
```

- [ ] **Step 4: Modificar `NewTaskModal.tsx`**

Garantir que `onSubmit` payload inclui `project`:

```typescript
onSubmit({
  title,
  payload,
  sprint,  // "current" | "next"
  project, // já input obrigatório
});
```

- [ ] **Step 5: Modificar `DetailDrawer.tsx`**

`onResprint(sprint)` handler deriva project de `task.project`:

```typescript
const handleResprint = (sprint: "current" | "next") => {
  return onResprint(sprint, task.project);
};
```

(Atualizar contrato `onResprint: (sprint, project) => ...` se necessário.)

- [ ] **Step 6: Rodar tests + typecheck**

```bash
cd ~/code/mission-control && npm test -- --run 2>&1 | tail -10
npm run typecheck 2>&1 | tail -5
```

Expected: green + zero errors.

- [ ] **Step 7: Smoke local browser**

```bash
cd ~/code/mission-control && npm run dev &
DEV_PID=$!
sleep 5
# Browse para /kanban e:
#  - Filtrar por bevox-mobile + current
#  - Criar task novo
#  - Re-sprint via DetailDrawer
# Verificar visual + console limpo
kill $DEV_PID
```

- [ ] **Step 8: Commit**

```bash
cd ~/code/mission-control && git add src/components/kanban/ tests/ && git commit -m "$(cat <<'EOF'
feat(ui/kanban): NewTaskModal + DetailDrawer + filterPersistence project-aware

Componentes propagam project explicitamente nos handlers de sprint
(current/next) pra resolver per-project no backend (schema v4).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Task 18: MC PR + merge + Vercel deploy + smoke

- [ ] **Step 1: Push + PR**

```bash
cd ~/code/mission-control && git push -u origin feat/sprint-per-project-ui
gh pr create --title "feat(mc/kanban): sprint per-project UI/API minimal patch" --body "$(cat <<'EOF'
## Summary
Mission Control consume schema v4 do kanban-tasks: \`currentSprintByProject\` map em /api/kanban/state, propagação de project nos endpoints de mutation, componentes UI (NewTaskModal/DetailDrawer/filterPersistence) project-aware.

Spec: \`bevox-knowledge/35_specs/openclaw/2026-04-25-sprint-per-project.md\`
Backend PR (openclaw): #merged

## Test plan
- [x] Vitest tests novos green
- [x] Typecheck zero errors
- [x] Smoke local browser: kanban filter + new task + re-sprint
- [ ] Pós-merge Vercel deploy → smoke prod via mc.example.com

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 2: PAUSA — aguardar Bernard mergear o PR**

Bernard merge → Vercel auto-deploy.

- [ ] **Step 3: Smoke production**

Browse `mc.example.com/kanban`, repetir cenários do Step 7 da Task 17 em production. Verificar console limpo + filtros + criação ok.

---

## Task 19: Tracker entry — wave delivered

**Files:**
- Modify: `bevox-knowledge/40_roadmap/_shared/delivery-tracker.yml`

- [ ] **Step 1: Branch + adicionar entry**

```bash
cd ~/bevox-knowledge && git checkout main && git pull --ff-only
git checkout -b draft/tracker-sprint-per-project-delivered
```

Editar `40_roadmap/_shared/delivery-tracker.yml`. Após `id: hotfix-dispatcher-notifier` no E10, adicionar:

```yaml
      - id: sprint-per-project
        status: delivered
        delivered_at: 2026-04-25
        spec: 35_specs/openclaw/2026-04-25-sprint-per-project.md
        pr_openclaw: https://github.com/bernardTavares/openclaw/pull/<N>
        pr_mc: https://github.com/bernardTavares/mission-control/pull/<N>
        narrative: "Schema kanban v3→v4: sprints strictly per-project; dispatcher filtra por current sprint; bridge pra C.1"
        features:
          - "kanban-tasks/lib/sprint.py: find_sprint(state, alias, project=) + bootstrap reads projects.yml + close_current(project=) per-project"
          - "kanban-tasks/lib/migration.py: split-and-migrate v3→v4; sprint-4 órfã com 27 tasks redistribuída pra current de cada projeto; tasks terminais ficam em sprint-4 closed legacy"
          - "Invariant task.sprint_id.project == task.project enforced em task add/move-to-sprint"
          - "scrum-master materializer: _resolve_target_sprint(state, alias, project) per-project"
          - "dispatcher selector: filter por current sprint do project + kill-switch OPENCLAW_DISPATCHER_IGNORE_SPRINT=1"
          - "dispatcher cron.jsonl audit: current_sprint_id per-project + outcome skipped_no_current_sprint"
          - "MC API: /api/kanban/state retorna currentSprintByProject map; POST /api/kanban/tasks propaga project; move-to-sprint deriva project do task"
          - "MC UI: NewTaskModal/DetailDrawer/useFilterPersistence project-aware"
          - "28 unit tests novos kanban+migration+scrum-master+dispatcher; 2 vitest tests novos MC; smoke E2E 5 cenários green"
          - "Bridge pra C.1 (same-session reuse): scope sprint bem-definido por projeto desbloqueia runner reusar Claude session entre tasks da mesma current sprint"
```

(Substituir `<N>` pelos PR numbers reais.)

- [ ] **Step 2: Validar YAML + commit + push + PR**

```bash
cd ~/bevox-knowledge && python3 -c "import yaml; yaml.safe_load(open('40_roadmap/_shared/delivery-tracker.yml')); print('valid')"
git add 40_roadmap/_shared/delivery-tracker.yml
git commit -m "$(cat <<'EOF'
tracker(E10/sprint-per-project): delivered 2026-04-25

Wave entregue end-to-end: schema v3→v4 + migração split-and-migrate
+ scrum-master + dispatcher selector com filtro + MC UI/API.

PRs: openclaw #<N>, mission-control #<N>
Spec: 35_specs/openclaw/2026-04-25-sprint-per-project.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git push -u origin draft/tracker-sprint-per-project-delivered
gh pr create --title "tracker(E10/sprint-per-project): delivered 2026-04-25" --body "## Summary
Entry no delivery-tracker registrando wave \`sprint-per-project\` do E10 como delivered.

## Test plan
- [x] YAML válido
- [x] Smoke E2E 5 cenários executados (§7.6 spec)
- [x] PRs openclaw + mc merged

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

- [ ] **Step 3: Aguardar Bernard mergear**

Bernard merge → wave fechada formalmente.

---

## Self-review

**Spec coverage:**
- §2 modelo de dados → Tasks 2-5 (find_sprint, bootstrap, close_current, invariants)
- §3 migração → Tasks 6-7 (happy + errors + dry-run + backup)
- §4.1 scrum-master → Task 9
- §4.2 MC UI/API → Tasks 16-17
- §4.3 dispatcher selector + kill-switch + cron → Tasks 10-11
- §5 arquivos → todos cobertos
- §6 ordem dos PRs → Tasks 1, 13, 18, 19 implementam a sequência (spec PR → openclaw PR → migration → MC PR → tracker PR)
- §7 testing → 28 unit tests distribuídos nos Tasks 2-10; smoke E2E em Task 15
- §7.1 rollback → kill-switch (Task 10), backup (Task 6), revert (post-Task 13 PR description)
- §8 DoD → checklist mapeia 1:1 nos cenários da Task 15

**Placeholder scan:** zero TBD/TODO/etc. nos steps.

**Type consistency:** `_resolve_sprint_id`, `find_sprint`, `_resolve_target_sprint`, `select_next_ready` — assinaturas batem entre tasks que se referenciam.

Issues encontrados: nenhum.
