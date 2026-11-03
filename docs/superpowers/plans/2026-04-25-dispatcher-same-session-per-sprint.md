# Dispatcher Same-Session Reuse Per Sprint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tasks da mesma current sprint do projeto compartilham 1 session_id Claude Code via `--resume`; runner gera UUID na primeira task + grava em `sprint.execution_session_id`; tasks subsequentes spawnam com `--resume <uuid>`.

**Architecture:** Schema additive (sprint ganha field opcional `execution_session_id`, sem schema_version bump). Runner em `dispatcher-agent/lib/runner.py` ramifica entre `--session-id <new-uuid>` (fresh) e `--resume <uuid>` (resume). `cmd_next` em api.py lê sprint, passa session pro runner, grava UUID via kanban CLI quando fresh. Kill-switch `OPENCLAW_DISPATCHER_DISABLE_SESSION_REUSE=1` força sempre fresh + skip kanban write.

**Tech Stack:** Python stdlib (uuid, subprocess, os) + unittest. systemd-run user transient. Sem dependência externa.

**Spec:** `bevox-knowledge/35_specs/openclaw/2026-04-25-dispatcher-same-session-per-sprint.md` (commit `f166908` em `draft/spec-dispatcher-same-session-per-sprint`).

---

## File Structure

### Create

- `kanban-tasks/tests/test_sprint_session_id.py` — 6 unit tests
- `dispatcher-agent/tests/test_runner_session_reuse.py` — 5 unit tests
- `dispatcher-agent/tests/test_cmd_next_session_propagation.py` — 3 integration tests
- `dispatcher-agent/tests/test_cron_audit_session_id.py` — 2 audit tests

### Modify

- `kanban-tasks/lib/sprint.py` — `set_session_id`, `clear_session_id` helpers
- `kanban-tasks/lib/api.py` — subparsers `sprint set-session-id` + `sprint clear-session-id`
- `kanban-tasks/README.md` — sprint set/clear-session-id usage
- `dispatcher-agent/lib/runner.py` — `launch_detached` + `launch_foreground` branch fresh/resume + log header pre-write
- `dispatcher-agent/lib/api.py` — `cmd_next` reads sprint, passes session_id, grava via kanban CLI
- `dispatcher-agent/lib/cron.py` — action dict ganha `execution_session_id` + `session_was_fresh`
- `dispatcher-agent/README.md` — kill-switch + dropin snippet

---

## Task 1: Branch setup + commit plan + push spec PR (gate)

**Files:**
- Create: `docs/superpowers/plans/2026-04-25-dispatcher-same-session-per-sprint.md` (este arquivo)

- [ ] **Step 1: Verificar branch correta**

```bash
cd ~/.openclaw && git branch --show-current
```

Expected: `feat/dispatcher-same-session-per-sprint` (criada a partir de main fresh).

- [ ] **Step 2: Commit do plano**

```bash
cd ~/.openclaw && git add docs/superpowers/plans/2026-04-25-dispatcher-same-session-per-sprint.md && git commit -m "$(cat <<'EOF'
plan(dispatcher-same-session-per-sprint): implementation plan for E10 wave

Spec: bevox-knowledge/35_specs/openclaw/2026-04-25-dispatcher-same-session-per-sprint.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 3: Push spec branch + abrir PR no bevox-knowledge**

```bash
cd ~/bevox-knowledge && git checkout draft/spec-dispatcher-same-session-per-sprint
git push -u origin draft/spec-dispatcher-same-session-per-sprint
gh pr create --title "spec(openclaw): dispatcher same-session reuse per sprint (E10)" --body "$(cat <<'EOF'
## Summary
Tasks da mesma current sprint do projeto compartilham 1 session_id Claude Code via \`--resume\`. Schema additive (sprint.execution_session_id field opcional, sem schema_version bump). Kill-switch \`OPENCLAW_DISPATCHER_DISABLE_SESSION_REUSE=1\` pra rollback operacional <30s.

5 decisões brainstormadas: (a) sprint-level scope + (a) lazy create + close-current discard + (a) briefing idêntico + kill-switch + tester preserved.

Bridge pra C.1 do backlog operacional, motivador da wave sprint-per-project.

## Test plan
- [ ] Bernard revisa spec
- [ ] Approva pra implementação seguir
- [ ] Implementação PR (openclaw) abre só após este merge

## Plan
Implementation plan já escrito: \`docs/superpowers/plans/2026-04-25-dispatcher-same-session-per-sprint.md\` no openclaw branch \`feat/dispatcher-same-session-per-sprint\`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 4: PAUSA — aguardar Bernard mergear o spec PR**

Parar aqui. Bernard merge no `bernardTavares/bevox-knowledge`. Retomar Task 2 só após confirmação de merge em main.

---

## Task 2: TDD set_session_id (kanban-tasks/lib/sprint.py)

**Files:**
- Create: `kanban-tasks/tests/test_sprint_session_id.py`
- Modify: `kanban-tasks/lib/sprint.py` (append `set_session_id` near `set_project`)

- [ ] **Step 1: Criar arquivo de teste com 4 tests**

Write `~/.openclaw/kanban-tasks/tests/test_sprint_session_id.py`:

```python
"""Tests sprint.set_session_id / clear_session_id (wave dispatcher-same-session-per-sprint)."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def _seed_state(state_path: Path, sprints):
    state_path.write_text(json.dumps({
        "schema_version": 4,
        "generated_at": "2026-04-25T12:00:00Z",
        "last_event_seq": 0,
        "projects": ["test-project"],
        "sprints": sprints,
        "tasks": [],
    }))


def _sp(seq, st, project, session_id=None):
    sp = {
        "id": f"sprint-{seq}",
        "name": f"Sprint {seq}",
        "state": st,
        "project": project,
        "created_at": "2026-04-25T00:00:00Z",
        "closed_at": None,
        "created_by": "test",
    }
    if session_id is not None:
        sp["execution_session_id"] = session_id
    return sp


class TestSetSessionId(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from lib import store
        self.tmp_state = Path(self.tmp) / "state.json"
        self.tmp_events = Path(self.tmp) / "events.jsonl"
        self.tmp_projects = Path(self.tmp) / "projects.yml"
        self.tmp_projects.write_text("projects:\n  - test-project\n")
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

    def test_set_session_id_on_active_sprint_persists(self):
        _seed_state(self.tmp_state, [_sp(1, "current", "test-project")])
        from lib import sprint
        result = sprint.set_session_id("sprint-1", "abc-123-uuid", actor="test")
        self.assertTrue(result["ok"])
        self.assertFalse(result.get("noop", False))
        self.assertEqual(result["session_id"], "abc-123-uuid")
        # state.json mutated
        state = json.loads(self.tmp_state.read_text())
        self.assertEqual(state["sprints"][0]["execution_session_id"], "abc-123-uuid")
        # event emitted
        events = [json.loads(l) for l in self.tmp_events.read_text().splitlines() if l.strip()]
        self.assertEqual(events[-1]["type"], "sprint_session_id_set")
        self.assertEqual(events[-1]["session_id"], "abc-123-uuid")

    def test_set_session_id_idempotent_returns_existing(self):
        _seed_state(self.tmp_state, [_sp(1, "current", "test-project", session_id="existing-uuid")])
        from lib import sprint
        result = sprint.set_session_id("sprint-1", "new-attempt-uuid", actor="test")
        self.assertTrue(result["ok"])
        self.assertTrue(result["noop"])
        self.assertEqual(result["existing"], "existing-uuid")
        # state NOT mutated
        state = json.loads(self.tmp_state.read_text())
        self.assertEqual(state["sprints"][0]["execution_session_id"], "existing-uuid")

    def test_set_session_id_on_closed_sprint_raises(self):
        _seed_state(self.tmp_state, [_sp(1, "closed", "test-project")])
        from lib import sprint
        with self.assertRaises(ValueError) as ctx:
            sprint.set_session_id("sprint-1", "abc-uuid", actor="test")
        self.assertIn("closed", str(ctx.exception).lower())

    def test_set_session_id_unknown_sprint_raises(self):
        _seed_state(self.tmp_state, [_sp(1, "current", "test-project")])
        from lib import sprint
        with self.assertRaises(ValueError) as ctx:
            sprint.set_session_id("sprint-99", "abc-uuid", actor="test")
        self.assertIn("not found", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar testes (devem falhar)**

```bash
cd ~/.openclaw/kanban-tasks && python3 -m unittest tests.test_sprint_session_id -v
```

Expected: AttributeError em `set_session_id` (não existe ainda).

- [ ] **Step 3: Implementar `set_session_id` em `lib/sprint.py`**

Adicionar logo após `set_project` (linha ~159):

```python
def set_session_id(sprint_id: str, session_id: str, actor: str) -> Dict[str, Any]:
    """Define execution_session_id pra primeira task da sprint.

    Idempotente: se já tem session_id, retorna noop com o existing.
    Sprint closed: rejeita (closed = imutável).
    """
    with store.mutate_state() as state:
        sp = find_sprint(state, sprint_id)
        if sp is None:
            raise ValueError(f"sprint not found: {sprint_id}")
        if sp["state"] == "closed":
            raise ValueError(f"cannot set session on closed sprint: {sprint_id}")
        if sp.get("execution_session_id"):
            return {"ok": True, "noop": True, "existing": sp["execution_session_id"]}
        sp["execution_session_id"] = session_id
        seq = store.next_seq(state)
        store.append_event({
            "seq": seq, "ts": store.now_iso(),
            "type": "sprint_session_id_set",
            "actor": actor, "sprint_id": sprint_id,
            "session_id": session_id,
        })
        state["last_event_seq"] = seq
        return {"ok": True, "noop": False, "session_id": session_id}
```

- [ ] **Step 4: Rodar testes**

```bash
cd ~/.openclaw/kanban-tasks && python3 -m unittest tests.test_sprint_session_id.TestSetSessionId -v
```

Expected: 4/4 ok.

- [ ] **Step 5: Verificar suite total kanban-tasks**

```bash
cd ~/.openclaw/kanban-tasks && python3 -m unittest discover 2>&1 | tail -3
```

Expected: pre-existing tests + 4 novos = 87+ tests, 0 failures.

- [ ] **Step 6: Commit**

```bash
cd ~/.openclaw && git add kanban-tasks/lib/sprint.py kanban-tasks/tests/test_sprint_session_id.py && git commit -m "$(cat <<'EOF'
feat(kanban/sprint): set_session_id helper (idempotent, rejects closed)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: TDD clear_session_id + close_current preservation

**Files:**
- Modify: `kanban-tasks/tests/test_sprint_session_id.py` (append 3 tests)
- Modify: `kanban-tasks/lib/sprint.py` (append `clear_session_id`)

- [ ] **Step 1: Append `TestClearSessionId` + close-current preservation test**

Adicionar ao `test_sprint_session_id.py`:

```python
class TestClearSessionId(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from lib import store
        self.tmp_state = Path(self.tmp) / "state.json"
        self.tmp_events = Path(self.tmp) / "events.jsonl"
        self.tmp_projects = Path(self.tmp) / "projects.yml"
        self.tmp_projects.write_text("projects:\n  - test-project\n")
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

    def test_clear_session_id_on_active_sprint(self):
        _seed_state(self.tmp_state, [_sp(1, "current", "test-project", session_id="abc-uuid")])
        from lib import sprint
        result = sprint.clear_session_id("sprint-1", actor="bernard", reason="test")
        self.assertTrue(result["ok"])
        self.assertFalse(result.get("noop", False))
        self.assertEqual(result["cleared"], "abc-uuid")
        state = json.loads(self.tmp_state.read_text())
        self.assertIsNone(state["sprints"][0]["execution_session_id"])
        events = [json.loads(l) for l in self.tmp_events.read_text().splitlines() if l.strip()]
        self.assertEqual(events[-1]["type"], "sprint_session_id_cleared")
        self.assertEqual(events[-1]["previous_session_id"], "abc-uuid")
        self.assertEqual(events[-1]["reason"], "test")

    def test_clear_session_id_idempotent(self):
        _seed_state(self.tmp_state, [_sp(1, "current", "test-project")])  # no session_id
        from lib import sprint
        result = sprint.clear_session_id("sprint-1", actor="bernard")
        self.assertTrue(result["ok"])
        self.assertTrue(result["noop"])

    def test_clear_session_id_on_closed_sprint_raises(self):
        _seed_state(self.tmp_state, [_sp(1, "closed", "test-project", session_id="abc")])
        from lib import sprint
        with self.assertRaises(ValueError) as ctx:
            sprint.clear_session_id("sprint-1", actor="bernard")
        self.assertIn("closed", str(ctx.exception).lower())


class TestCloseCurrentDoesNotMigrateSession(unittest.TestCase):
    """Regression: close_current promove next→current sem migrar session_id (lazy semantics)."""
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from lib import store
        self.tmp_state = Path(self.tmp) / "state.json"
        self.tmp_events = Path(self.tmp) / "events.jsonl"
        self.tmp_projects = Path(self.tmp) / "projects.yml"
        self.tmp_projects.write_text("projects:\n  - test-project\n")
        # current com session_id, next sem
        _seed_state(self.tmp_state, [
            _sp(1, "current", "test-project", session_id="current-uuid"),
            _sp(2, "next", "test-project"),
        ])
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

    def test_close_current_does_not_migrate_session_id(self):
        from lib import sprint
        result = sprint.close_current(carryover=[], actor="bernard", project="test-project")
        self.assertTrue(result["ok"])
        state = json.loads(self.tmp_state.read_text())
        sprints_by_id = {sp["id"]: sp for sp in state["sprints"]}
        # sprint-1 (closed) preservou session_id
        self.assertEqual(sprints_by_id["sprint-1"]["state"], "closed")
        self.assertEqual(sprints_by_id["sprint-1"]["execution_session_id"], "current-uuid")
        # sprint-2 (promoted to current) NÃO tem session_id
        self.assertEqual(sprints_by_id["sprint-2"]["state"], "current")
        self.assertIsNone(sprints_by_id["sprint-2"].get("execution_session_id"))
```

- [ ] **Step 2: Rodar tests (devem falhar — clear_session_id não existe)**

```bash
cd ~/.openclaw/kanban-tasks && python3 -m unittest tests.test_sprint_session_id -v 2>&1 | tail -10
```

Expected: 4 ok da Task 2 + 3 FAIL (TestClearSessionId) + 1 FAIL ou pass (TestCloseCurrentDoesNotMigrateSession) — depende se close_current já preservava ou criava session_id. Provavelmente passa porque close_current não toca sprint.execution_session_id (additive field).

- [ ] **Step 3: Implementar `clear_session_id` em `lib/sprint.py`**

Logo após `set_session_id`:

```python
def clear_session_id(sprint_id: str, actor: str, reason: str = "") -> Dict[str, Any]:
    """Limpa execution_session_id (recovery operacional).

    Próxima task dispatchada gera fresh UUID. Sprints closed rejeitadas.
    Idempotente: já null → noop.
    """
    with store.mutate_state() as state:
        sp = find_sprint(state, sprint_id)
        if sp is None:
            raise ValueError(f"sprint not found: {sprint_id}")
        if sp["state"] == "closed":
            raise ValueError(f"cannot clear session on closed sprint: {sprint_id}")
        if not sp.get("execution_session_id"):
            return {"ok": True, "noop": True}
        old = sp["execution_session_id"]
        sp["execution_session_id"] = None
        seq = store.next_seq(state)
        store.append_event({
            "seq": seq, "ts": store.now_iso(),
            "type": "sprint_session_id_cleared",
            "actor": actor, "sprint_id": sprint_id,
            "previous_session_id": old, "reason": reason,
        })
        state["last_event_seq"] = seq
        return {"ok": True, "noop": False, "cleared": old}
```

- [ ] **Step 4: Rodar tests**

```bash
cd ~/.openclaw/kanban-tasks && python3 -m unittest tests.test_sprint_session_id -v 2>&1 | tail -10
```

Expected: 8 ok (4 set + 3 clear + 1 close-current preservation).

Se `test_close_current_does_not_migrate_session_id` falhar porque close_current NÃO preserva o field automaticamente, atualizar `close_current` em sprint.py pra preservar (provavelmente já preserva por dictionary copy semantics — additive field é carregado naturalmente). Investigar e ajustar.

- [ ] **Step 5: Suite total**

```bash
cd ~/.openclaw/kanban-tasks && python3 -m unittest discover 2>&1 | tail -3
```

Expected: 91+ tests, 0 failures.

- [ ] **Step 6: Commit**

```bash
cd ~/.openclaw && git add kanban-tasks/lib/sprint.py kanban-tasks/tests/test_sprint_session_id.py && git commit -m "$(cat <<'EOF'
feat(kanban/sprint): clear_session_id + close_current preservation regression

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: CLI subparsers (sprint set-session-id + sprint clear-session-id)

**Files:**
- Modify: `kanban-tasks/lib/api.py`

- [ ] **Step 1: Inspecionar padrão de subparsers existentes**

```bash
grep -n "leaf(sp_sub\|sp_sub.add_parser\|cmd_sprint_" ~/.openclaw/kanban-tasks/lib/api.py | head -15
```

Identificar onde subparsers de sprint são montados (~linha 765-810). Reusa o helper `leaf(sp_sub, name)` que já passa `parents=[common]` (que inclui `--actor`, `--json`).

- [ ] **Step 2: Adicionar 2 subparsers + 2 cmd functions**

Localizar o bloco que monta sp_sub subparsers. Adicionar (no padrão dos existentes):

```python
    # set-session-id (chamado primariamente pelo dispatcher; Bernard pode usar pra forçar)
    setsid = leaf(sp_sub, "set-session-id")
    setsid.add_argument("--sprint-id", required=True, help="Sprint id (literal sprint-N)")
    setsid.add_argument("--session-id", required=True, help="UUID da Claude session")
    setsid.set_defaults(func=cmd_sprint_set_session_id)

    # clear-session-id (recovery operacional manual)
    clearsid = leaf(sp_sub, "clear-session-id")
    clearsid.add_argument("--sprint-id", required=True)
    clearsid.add_argument("--reason", default="")
    clearsid.set_defaults(func=cmd_sprint_clear_session_id)
```

E adicionar as 2 funções no nível do módulo (mesmo nível dos outros `cmd_sprint_*`):

```python
def cmd_sprint_set_session_id(args) -> int:
    from . import sprint as sprint_lib
    try:
        result = sprint_lib.set_session_id(
            sprint_id=args.sprint_id,
            session_id=args.session_id,
            actor=args.actor,
        )
    except ValueError as e:
        return _err(str(e), "SET_SESSION_FAILED", args.json)
    if args.json:
        print(json.dumps(result, default=str, indent=2))
    else:
        if result.get("noop"):
            print(f"noop: sprint {args.sprint_id} already has session_id={result['existing']}")
        else:
            print(f"set: sprint {args.sprint_id} session_id={result['session_id']}")
    return EXIT_OK


def cmd_sprint_clear_session_id(args) -> int:
    from . import sprint as sprint_lib
    try:
        result = sprint_lib.clear_session_id(
            sprint_id=args.sprint_id,
            actor=args.actor,
            reason=args.reason,
        )
    except ValueError as e:
        return _err(str(e), "CLEAR_SESSION_FAILED", args.json)
    if args.json:
        print(json.dumps(result, default=str, indent=2))
    else:
        if result.get("noop"):
            print(f"noop: sprint {args.sprint_id} has no session_id")
        else:
            print(f"cleared: sprint {args.sprint_id} previous_session_id={result['cleared']}")
    return EXIT_OK
```

- [ ] **Step 3: Smoke manual (help screens)**

```bash
cd ~/.openclaw/kanban-tasks && ./cli.sh sprint set-session-id --help 2>&1 | head -8
./cli.sh sprint clear-session-id --help 2>&1 | head -8
```

Expected: ambos help screens funcionais (mostram `--sprint-id`, `--session-id`/`--reason`, `--actor` herdado, `--json` herdado).

- [ ] **Step 4: Suite total — zero regressão**

```bash
cd ~/.openclaw/kanban-tasks && python3 -m unittest discover 2>&1 | tail -3
```

Expected: 91+ green.

- [ ] **Step 5: Commit**

```bash
cd ~/.openclaw && git add kanban-tasks/lib/api.py && git commit -m "$(cat <<'EOF'
feat(kanban/api): subparsers sprint set-session-id + sprint clear-session-id

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: TDD runner.launch_detached fresh/resume + kill-switch + log header

**Files:**
- Create: `dispatcher-agent/tests/test_runner_session_reuse.py`
- Modify: `dispatcher-agent/lib/runner.py`

- [ ] **Step 1: Criar arquivo de teste**

Write `~/.openclaw/dispatcher-agent/tests/test_runner_session_reuse.py`:

```python
"""Tests dispatcher runner session reuse (fresh/resume branching + kill-switch + log header)."""
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestRunnerSessionReuse(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.briefing_path = Path(self.tmp) / "briefing.md"
        self.briefing_path.write_text("# Briefing\nGoal: do X")
        # patch executions dir
        from lib import store
        self.exec_dir = Path(self.tmp) / "executions"
        self.exec_dir.mkdir()
        self.store_patch = patch.object(store, "EXECUTIONS_DIR", self.exec_dir)
        self.store_patch.start()

    def tearDown(self):
        self.store_patch.stop()
        shutil.rmtree(self.tmp)
        os.environ.pop("OPENCLAW_DISPATCHER_DISABLE_SESSION_REUSE", None)

    def test_launch_detached_fresh_generates_uuid_when_sprint_has_none(self):
        """sprint_session_id=None → spawn cmd contém --session-id <uuid>, retorna is_fresh=True."""
        from lib import runner
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            status = runner.launch_detached(
                "T-test", self.briefing_path, "Read,Write",
                sprint_session_id=None,
                sprint_id="sprint-22",
            )
        self.assertTrue(status["sprint_session_was_fresh"])
        self.assertIsNotNone(status["sprint_session_id"])
        # cmd array tem --session-id, NÃO tem --resume
        cmd_call = mock_run.call_args.args[0]
        self.assertIn("--session-id", cmd_call)
        self.assertNotIn("--resume", cmd_call)

    def test_launch_detached_resume_when_sprint_has_session(self):
        """sprint_session_id="abc-123" → cmd contém --resume, NÃO contém --session-id, is_fresh=False."""
        from lib import runner
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            status = runner.launch_detached(
                "T-test", self.briefing_path, "Read,Write",
                sprint_session_id="abc-123-uuid",
                sprint_id="sprint-22",
            )
        self.assertFalse(status["sprint_session_was_fresh"])
        self.assertEqual(status["sprint_session_id"], "abc-123-uuid")
        cmd_call = mock_run.call_args.args[0]
        self.assertIn("--resume", cmd_call)
        self.assertIn("abc-123-uuid", cmd_call)
        self.assertNotIn("--session-id", cmd_call)

    def test_kill_switch_disable_session_reuse_forces_fresh(self):
        """env=1 + sprint_session_id presente → ainda usa --session-id <new>, is_fresh=True."""
        os.environ["OPENCLAW_DISPATCHER_DISABLE_SESSION_REUSE"] = "1"
        from lib import runner
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            status = runner.launch_detached(
                "T-test", self.briefing_path, "Read,Write",
                sprint_session_id="ignored-uuid",
                sprint_id="sprint-22",
            )
        self.assertTrue(status["sprint_session_was_fresh"])
        self.assertNotEqual(status["sprint_session_id"], "ignored-uuid")
        self.assertTrue(status["kill_switch_active"])
        cmd_call = mock_run.call_args.args[0]
        self.assertIn("--session-id", cmd_call)
        self.assertNotIn("--resume", cmd_call)

    def test_launch_detached_writes_metadata_header_to_log(self):
        """log file deve ter header com metadata pre-spawn."""
        from lib import runner
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            status = runner.launch_detached(
                "T-test", self.briefing_path, "Read,Write",
                sprint_session_id=None,
                sprint_id="sprint-22",
            )
        log_path = Path(status["log_path"])
        content = log_path.read_text()
        self.assertIn("# DISPATCHER METADATA", content)
        self.assertIn("# task_id: T-test", content)
        self.assertIn("# sprint_id: sprint-22", content)
        self.assertIn(f"# execution_session_id: {status['sprint_session_id']}", content)
        self.assertIn("# session_was_fresh: True", content)
        self.assertIn("# ----- claude output below -----", content)

    def test_launch_foreground_supports_session_reuse_same_logic(self):
        """foreground tem mesmo branching que detached."""
        from lib import runner
        with patch("subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.communicate.return_value = ("ok", "")
            mock_proc.returncode = 0
            mock_popen.return_value = mock_proc
            status = runner.launch_foreground(
                "T-fg-test", self.briefing_path, "Read,Write",
                sprint_session_id="fg-abc-uuid",
                sprint_id="sprint-22",
            )
        self.assertFalse(status["sprint_session_was_fresh"])
        self.assertEqual(status["sprint_session_id"], "fg-abc-uuid")
        cmd_call = mock_popen.call_args.args[0]
        self.assertIn("--resume", cmd_call)
        self.assertIn("fg-abc-uuid", cmd_call)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar tests (devem falhar — runner não tem branching)**

```bash
cd ~/.openclaw/dispatcher-agent && python3 -m unittest tests.test_runner_session_reuse -v
```

Expected: 5 FAILs / ERRORs (signature mismatch ou KeyError em status).

- [ ] **Step 3: Modificar `lib/runner.py`**

Substituir TODA a função `launch_detached` (linhas ~37-92) por:

```python
import os
import uuid as _uuid


def launch_detached(
    task_id: str, briefing_path: Path, allowed_tools: str,
    *, sprint_session_id: Optional[str] = None,
    sprint_id: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """Spawn `claude -p` como transient systemd-run user service.

    Branching session reuse:
    - sprint_session_id is None → fresh: gera UUID novo + retorna is_fresh=True
    - sprint_session_id presente → resume: spawn com --resume <uuid>
    - Kill-switch OPENCLAW_DISPATCHER_DISABLE_SESSION_REUSE=1 → sempre fresh
    """
    transient_unit_id = _build_session_id(task_id)
    log_path = store.execution_log_path(task_id)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    disable_reuse = os.environ.get("OPENCLAW_DISPATCHER_DISABLE_SESSION_REUSE") == "1"

    if sprint_session_id and not disable_reuse:
        claude_session_arg = ["--resume", sprint_session_id]
        sprint_session_id_used = sprint_session_id
        is_fresh = False
    else:
        new_uuid = str(_uuid.uuid4())
        claude_session_arg = ["--session-id", new_uuid]
        sprint_session_id_used = new_uuid
        is_fresh = True

    # Pre-write log header (metadata + delimiter) before spawn.
    log_path.write_text(
        f"# DISPATCHER METADATA\n"
        f"# task_id: {task_id}\n"
        f"# sprint_id: {sprint_id or '?'}\n"
        f"# execution_session_id: {sprint_session_id_used}\n"
        f"# session_was_fresh: {is_fresh}\n"
        f"# kill_switch_active: {disable_reuse}\n"
        f"# briefing_path: {briefing_path}\n"
        f"# spawned_at: {store.now_iso()}\n"
        f"# ----- claude output below -----\n",
        encoding="utf-8",
    )

    unit_name = f"claude-task-{transient_unit_id}.service"
    briefing_content = briefing_path.read_text(encoding="utf-8")

    sd_cmd = [
        "systemd-run", "--user",
        f"--unit={unit_name}",
        "--collect",
        "--property=Type=exec",
        f"--property=StandardOutput=append:{log_path}",   # CHANGED: truncate→append
        "--property=StandardError=inherit",
        "--",
        "claude", "-p", briefing_content,
        *claude_session_arg,
        "--allowedTools", allowed_tools,
    ]
    if model:
        sd_cmd += ["--model", model]

    try:
        result = subprocess.run(
            sd_cmd, capture_output=True, text=True, timeout=15, check=False,
        )
    except subprocess.TimeoutExpired:
        raise RunnerError(
            "SYSTEMD_RUN_TIMEOUT",
            f"systemd-run --user excedeu 15s pra spawnar claude-task {task_id}",
        )
    if result.returncode != 0:
        raise RunnerError(
            "SYSTEMD_RUN_FAILED",
            f"systemd-run exit={result.returncode}: {result.stderr.strip()[:300]}",
        )

    status = {
        "task_id": task_id,
        "session_id": transient_unit_id,
        "sprint_session_id": sprint_session_id_used,
        "sprint_session_was_fresh": is_fresh,
        "sprint_id": sprint_id,
        "kill_switch_active": disable_reuse,
        "unit_name": unit_name,
        "pid": None,
        "run_mode": "detach",
        "started_at": store.now_iso(),
        "briefing_path": str(briefing_path),
        "log_path": str(log_path),
        "finished_at": None,
        "exit_code": None,
        "model": model or "default",
    }
    store.write_execution_status(task_id, status)
    return status
```

- [ ] **Step 4: Modificar `launch_foreground` (mesmo branching)**

Substituir `launch_foreground` (linhas ~95+) com a mesma logic:

```python
def launch_foreground(
    task_id: str, briefing_path: Path, allowed_tools: str,
    *, sprint_session_id: Optional[str] = None,
    sprint_id: Optional[str] = None,
    model: Optional[str] = None,
    timeout_seconds: int = 1800,
) -> Dict[str, Any]:
    """Spawn `claude -p` em foreground (debug). Bloqueia ate terminar.

    Mesmo branching session reuse que launch_detached.
    """
    log_path = store.execution_log_path(task_id)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    disable_reuse = os.environ.get("OPENCLAW_DISPATCHER_DISABLE_SESSION_REUSE") == "1"

    if sprint_session_id and not disable_reuse:
        claude_session_arg = ["--resume", sprint_session_id]
        sprint_session_id_used = sprint_session_id
        is_fresh = False
    else:
        new_uuid = str(_uuid.uuid4())
        claude_session_arg = ["--session-id", new_uuid]
        sprint_session_id_used = new_uuid
        is_fresh = True

    # Pre-write log header
    log_path.write_text(
        f"# DISPATCHER METADATA (FOREGROUND)\n"
        f"# task_id: {task_id}\n"
        f"# sprint_id: {sprint_id or '?'}\n"
        f"# execution_session_id: {sprint_session_id_used}\n"
        f"# session_was_fresh: {is_fresh}\n"
        f"# kill_switch_active: {disable_reuse}\n"
        f"# spawned_at: {store.now_iso()}\n"
        f"# ----- claude output below -----\n",
        encoding="utf-8",
    )

    briefing_content = briefing_path.read_text(encoding="utf-8")
    cmd = [
        "claude", "-p", briefing_content,
        *claude_session_arg,
        "--allowedTools", allowed_tools,
    ]
    if model:
        cmd += ["--model", model]

    started_at = store.now_iso()
    try:
        # Append claude output to log (after pre-written header)
        with open(log_path, "a", encoding="utf-8") as f:
            proc = subprocess.Popen(
                cmd, stdout=f, stderr=subprocess.STDOUT, text=True,
            )
            try:
                _, _ = proc.communicate(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                proc.kill()
                raise RunnerError(
                    "CLAUDE_TIMEOUT",
                    f"claude -p excedeu {timeout_seconds}s",
                )
        exit_code = proc.returncode
    except FileNotFoundError as e:
        raise RunnerError("CLAUDE_NOT_FOUND", str(e))

    status = {
        "task_id": task_id,
        "session_id": _build_session_id(task_id),
        "sprint_session_id": sprint_session_id_used,
        "sprint_session_was_fresh": is_fresh,
        "sprint_id": sprint_id,
        "kill_switch_active": disable_reuse,
        "pid": proc.pid,
        "run_mode": "foreground",
        "started_at": started_at,
        "briefing_path": str(briefing_path),
        "log_path": str(log_path),
        "finished_at": store.now_iso(),
        "exit_code": exit_code,
        "model": model or "default",
    }
    store.write_execution_status(task_id, status)
    return status
```

- [ ] **Step 5: Rodar tests**

```bash
cd ~/.openclaw/dispatcher-agent && python3 -m unittest tests.test_runner_session_reuse -v
```

Expected: 5/5 ok.

- [ ] **Step 6: Suite dispatcher total**

```bash
cd ~/.openclaw/dispatcher-agent && python3 -m unittest discover 2>&1 | tail -3
```

Expected: pré-existing tests + 5 novos. Se algum pré-existing falhou por causa de signature change (ex: testes antigos chamavam `launch_detached(task, briefing, allowed_tools)` sem novos args), eles ainda funcionam porque novos args são keyword-only com defaults `None`. Se houve regressão, ajustar fixtures (provavelmente nenhum test pré-existing usa launch_detached diretamente — só via cmd_next).

- [ ] **Step 7: Commit**

```bash
cd ~/.openclaw && git add dispatcher-agent/lib/runner.py dispatcher-agent/tests/test_runner_session_reuse.py && git commit -m "$(cat <<'EOF'
feat(dispatcher/runner): branch fresh/resume session + kill-switch + log header

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: TDD cmd_next session_id propagation

**Files:**
- Create: `dispatcher-agent/tests/test_cmd_next_session_propagation.py`
- Modify: `dispatcher-agent/lib/api.py`

- [ ] **Step 1: Criar test file**

Write `~/.openclaw/dispatcher-agent/tests/test_cmd_next_session_propagation.py`:

```python
"""Tests cmd_next session_id propagation: lê sprint, passa pro runner, grava se fresh."""
import argparse
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestCmdNextSessionPropagation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.state_path = Path(self.tmp) / "state.json"
        self.state_path.write_text(json.dumps({
            "schema_version": 4,
            "sprints": [
                {"id": "sprint-22", "state": "current", "project": "test-project"},
            ],
            "tasks": [
                {"id": "T-1", "title": "x", "status": "ready",
                 "sprint_id": "sprint-22", "project": "test-project",
                 "blocked": False, "created_at": "2026-04-25T00:00:00Z",
                 "dispatch_payload": {"goal": "do X",
                                       "acceptance_criteria": ["x"],
                                       "spec_ref": "n/a"}},
            ],
        }))
        from lib import selector
        self.selector_patch = patch.object(selector, "KANBAN_STATE", self.state_path)
        self.selector_patch.start()

    def tearDown(self):
        self.selector_patch.stop()
        shutil.rmtree(self.tmp)
        os.environ.pop("OPENCLAW_DISPATCHER_DISABLE_SESSION_REUSE", None)

    def _build_args(self, **overrides):
        args = argparse.Namespace(
            project="test-project",
            launch=True,
            foreground=False,
            no_tester=False,
            json=False,
            model=None,
            **overrides,
        )
        return args

    def test_cmd_next_first_dispatch_calls_kanban_set_session_id(self):
        """Sprint sem session_id → runner retorna is_fresh=True → cmd_next chama kanban set-session-id."""
        from lib import api
        with patch("lib.runner.launch_detached") as mock_launch, \
             patch("subprocess.run") as mock_subproc, \
             patch("lib.briefing.write_briefing") as mock_briefing, \
             patch("lib.lifecycle.move_to_in_progress"), \
             patch("lib.lifecycle.merge_dispatch_payload"):
            mock_briefing.return_value = Path(self.tmp) / "briefing.md"
            (Path(self.tmp) / "briefing.md").write_text("# B")
            mock_launch.return_value = {
                "task_id": "T-1", "session_id": "T-1-ts",
                "sprint_session_id": "fresh-uuid-abc",
                "sprint_session_was_fresh": True,
                "kill_switch_active": False,
                "started_at": "...", "log_path": "...",
                "run_mode": "detach",
            }
            mock_subproc.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
            args = self._build_args()
            api.cmd_next(args)
        # subprocess.run foi chamado com kanban CLI sprint set-session-id
        kanban_calls = [c for c in mock_subproc.call_args_list
                        if any("set-session-id" in str(arg) for arg in c.args[0])]
        self.assertGreaterEqual(len(kanban_calls), 1)
        # session-id passed = fresh-uuid-abc
        cmd = kanban_calls[0].args[0]
        self.assertIn("fresh-uuid-abc", cmd)
        self.assertIn("sprint-22", cmd)

    def test_cmd_next_resume_does_not_call_set_session_id(self):
        """Sprint COM session_id → runner returns is_fresh=False → kanban NÃO é tocado."""
        # Update state to have session_id
        state = json.loads(self.state_path.read_text())
        state["sprints"][0]["execution_session_id"] = "existing-uuid"
        self.state_path.write_text(json.dumps(state))
        from lib import api
        with patch("lib.runner.launch_detached") as mock_launch, \
             patch("subprocess.run") as mock_subproc, \
             patch("lib.briefing.write_briefing") as mock_briefing, \
             patch("lib.lifecycle.move_to_in_progress"), \
             patch("lib.lifecycle.merge_dispatch_payload"):
            mock_briefing.return_value = Path(self.tmp) / "briefing.md"
            (Path(self.tmp) / "briefing.md").write_text("# B")
            mock_launch.return_value = {
                "task_id": "T-1", "session_id": "T-1-ts",
                "sprint_session_id": "existing-uuid",
                "sprint_session_was_fresh": False,
                "kill_switch_active": False,
                "started_at": "...", "log_path": "...",
                "run_mode": "detach",
            }
            mock_subproc.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
            args = self._build_args()
            api.cmd_next(args)
        # NO kanban set-session-id call
        kanban_calls = [c for c in mock_subproc.call_args_list
                        if any("set-session-id" in str(arg) for arg in c.args[0])]
        self.assertEqual(len(kanban_calls), 0)

    def test_cmd_next_kill_switch_skips_set_session_id(self):
        """Kill-switch ativo + runner is_fresh=True → kanban NÃO tocado."""
        os.environ["OPENCLAW_DISPATCHER_DISABLE_SESSION_REUSE"] = "1"
        from lib import api
        with patch("lib.runner.launch_detached") as mock_launch, \
             patch("subprocess.run") as mock_subproc, \
             patch("lib.briefing.write_briefing") as mock_briefing, \
             patch("lib.lifecycle.move_to_in_progress"), \
             patch("lib.lifecycle.merge_dispatch_payload"):
            mock_briefing.return_value = Path(self.tmp) / "briefing.md"
            (Path(self.tmp) / "briefing.md").write_text("# B")
            mock_launch.return_value = {
                "task_id": "T-1", "session_id": "T-1-ts",
                "sprint_session_id": "killswitch-fresh-uuid",
                "sprint_session_was_fresh": True,
                "kill_switch_active": True,
                "started_at": "...", "log_path": "...",
                "run_mode": "detach",
            }
            mock_subproc.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
            args = self._build_args()
            api.cmd_next(args)
        kanban_calls = [c for c in mock_subproc.call_args_list
                        if any("set-session-id" in str(arg) for arg in c.args[0])]
        self.assertEqual(len(kanban_calls), 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar tests (devem falhar — cmd_next não propaga ainda)**

```bash
cd ~/.openclaw/dispatcher-agent && python3 -m unittest tests.test_cmd_next_session_propagation -v
```

Expected: 3 FAILs (mock_launch foi chamado sem `sprint_session_id` arg, OR kanban call nunca aconteceu).

- [ ] **Step 3: Modificar `lib/api.py:cmd_next`**

Localizar onde `runner_lib.launch_detached(...)` é chamado em cmd_next (~linha 130+). Modificar para:

(a) Antes da chamada, ler sprint do state.json:

```python
        # Lê sprint pra obter session_id (lazy create na primeira task)
        from . import selector as selector_lib
        kanban_state = json.loads(
            selector_lib.KANBAN_STATE.read_text(encoding="utf-8")
        )
        sprint_obj = next(
            (sp for sp in kanban_state.get("sprints", [])
             if sp["id"] == task["sprint_id"]),
            None,
        )
        sprint_session_id_in = sprint_obj.get("execution_session_id") if sprint_obj else None
```

(b) Passar pro runner:

```python
        if args.foreground:
            status = runner_lib.launch_foreground(
                task["id"], bpath, allowed_tools,
                sprint_session_id=sprint_session_id_in,
                sprint_id=task["sprint_id"],
                model=args.model,
            )
            # ... existing tester invoke logic
        else:
            status = runner_lib.launch_detached(
                task["id"], bpath, allowed_tools,
                sprint_session_id=sprint_session_id_in,
                sprint_id=task["sprint_id"],
                model=args.model,
            )
            # ... existing detached metadata logic
```

(c) Após `runner_lib.launch_*`, antes do `lifecycle.merge_dispatch_payload`, adicionar gravação condicional:

```python
        # Se foi fresh E kill-switch off, gravar UUID na sprint via kanban CLI
        disable_reuse = os.environ.get("OPENCLAW_DISPATCHER_DISABLE_SESSION_REUSE") == "1"
        if status.get("sprint_session_was_fresh") and not disable_reuse:
            kanban_cli_path = "~/.openclaw/kanban-tasks/cli.sh"
            try:
                subprocess.run(
                    [kanban_cli_path, "sprint", "set-session-id",
                     "--sprint-id", task["sprint_id"],
                     "--session-id", status["sprint_session_id"],
                     "--actor", "dispatcher", "--json"],
                    capture_output=True, text=True, timeout=10, check=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                # Não bloqueia dispatch — próxima task vai gerar fresh UUID
                pass
```

(Ajustar imports `import os` e `import subprocess` no topo se ainda não tem.)

- [ ] **Step 4: Rodar tests**

```bash
cd ~/.openclaw/dispatcher-agent && python3 -m unittest tests.test_cmd_next_session_propagation -v
```

Expected: 3/3 ok.

- [ ] **Step 5: Suite dispatcher total**

```bash
cd ~/.openclaw/dispatcher-agent && python3 -m unittest discover 2>&1 | tail -3
```

Expected: 6 (notifier) + 5 (selector filter) + 1 (cron audit) + 5 (runner reuse) + 3 (cmd_next prop) = 20+ green.

- [ ] **Step 6: Commit**

```bash
cd ~/.openclaw && git add dispatcher-agent/lib/api.py dispatcher-agent/tests/test_cmd_next_session_propagation.py && git commit -m "$(cat <<'EOF'
feat(dispatcher/api): cmd_next propagates sprint_session_id + sets kanban on fresh

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: TDD cron audit fields (execution_session_id + session_was_fresh)

**Files:**
- Create: `dispatcher-agent/tests/test_cron_audit_session_id.py`
- Modify: `dispatcher-agent/lib/cron.py`

- [ ] **Step 1: Criar test file**

Write `~/.openclaw/dispatcher-agent/tests/test_cron_audit_session_id.py`:

```python
"""Tests cron audit jsonl includes execution_session_id + session_was_fresh em dispatched outcome."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestCronAuditSessionId(unittest.TestCase):
    def test_cron_action_dispatched_includes_execution_session_id(self):
        """outcome=dispatched action dict tem execution_session_id + session_was_fresh."""
        from lib import cron
        # Mock dispatch_one_fn pra retornar outcome com session metadata
        dispatch_one_fn = MagicMock(return_value={
            "outcome": "dispatched",
            "task_id": "T-1",
            "execution_session_id": "abc-uuid",
            "session_was_fresh": True,
        })
        check_blocks_fn = MagicMock(return_value=False)
        action_dicts, stats = cron.process_projects(
            opted_in=["test-project"],
            dispatch_one_fn=dispatch_one_fn,
            check_blocks_fn=check_blocks_fn,
        )
        self.assertEqual(len(action_dicts), 1)
        a = action_dicts[0]
        self.assertEqual(a["outcome"], "dispatched")
        self.assertEqual(a["execution_session_id"], "abc-uuid")
        self.assertTrue(a["session_was_fresh"])

    def test_cron_action_skipped_omits_execution_session_id(self):
        """skipped_no_ready / skipped_no_current_sprint NÃO têm session field."""
        from lib import cron
        dispatch_one_fn = MagicMock(return_value={
            "outcome": "skipped_no_ready",
            "task_id": None,
            "skip_reason": "no ready",
        })
        check_blocks_fn = MagicMock(return_value=False)
        action_dicts, stats = cron.process_projects(
            opted_in=["test-project"],
            dispatch_one_fn=dispatch_one_fn,
            check_blocks_fn=check_blocks_fn,
        )
        self.assertEqual(len(action_dicts), 1)
        a = action_dicts[0]
        self.assertEqual(a["outcome"], "skipped_no_ready")
        # campo session_id é opcional / null pra skipped
        self.assertNotIn("execution_session_id", a)
        self.assertNotIn("session_was_fresh", a)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar tests (devem falhar)**

```bash
cd ~/.openclaw/dispatcher-agent && python3 -m unittest tests.test_cron_audit_session_id -v
```

Expected: 2 FAILs (action dict não tem os fields novos).

- [ ] **Step 3: Modificar `lib/cron.py:process_projects`**

Localizar onde action dict é construído pra outcome `dispatched` (procurar por `"outcome": "dispatched"`). Adicionar propagação dos fields do return de `dispatch_one_fn`:

```python
    # No loop de process_projects, após dispatch_one_fn returnar:
    # Existing logic populates outcome, task_id, current_sprint_id, etc.
    # ADD:
    if action.get("outcome") == "dispatched":
        if "execution_session_id" in dispatch_result:
            action["execution_session_id"] = dispatch_result["execution_session_id"]
        if "session_was_fresh" in dispatch_result:
            action["session_was_fresh"] = dispatch_result["session_was_fresh"]
```

(Adapt to actual existing code shape — pode já estar copiando dispatch_result fields ou montando action dict from scratch.)

E em `_dispatch_one_for_project`, após `runner.launch_detached` retornar, propagar pro return value:

```python
    return {
        "outcome": "dispatched",
        "task_id": task["id"],
        # ... existing fields ...
        "execution_session_id": status.get("sprint_session_id"),
        "session_was_fresh": status.get("sprint_session_was_fresh", False),
    }
```

- [ ] **Step 4: Rodar tests**

```bash
cd ~/.openclaw/dispatcher-agent && python3 -m unittest tests.test_cron_audit_session_id -v
```

Expected: 2/2 ok.

- [ ] **Step 5: Suite dispatcher total**

```bash
cd ~/.openclaw/dispatcher-agent && python3 -m unittest discover 2>&1 | tail -3
```

Expected: 22+ green.

- [ ] **Step 6: Commit**

```bash
cd ~/.openclaw && git add dispatcher-agent/lib/cron.py dispatcher-agent/tests/test_cron_audit_session_id.py && git commit -m "$(cat <<'EOF'
feat(dispatcher/cron): audit dispatched ganha execution_session_id + session_was_fresh

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: README updates (kanban-tasks + dispatcher-agent)

**Files:**
- Modify: `kanban-tasks/README.md`
- Modify: `dispatcher-agent/README.md`

- [ ] **Step 1: Append "Sprint session_id helpers" ao kanban-tasks/README.md**

Adicionar no fim do arquivo (sem alterar conteúdo existente):

```markdown

## Sprint session_id helpers (wave dispatcher-same-session-per-sprint)

Sprints ganham field `execution_session_id` (UUID) populado lazy quando primeira task da sprint dispatcha. Tasks subsequentes da mesma sprint reusam via `claude --resume`.

### Set (chamado primariamente pelo dispatcher; manual override possível)

```bash
./cli.sh sprint set-session-id --sprint-id sprint-22 --session-id <uuid> --actor dispatcher
```

Idempotente: se sprint já tem session_id, retorna noop com o existing. Closed sprint: rejeita.

### Clear (recovery operacional)

```bash
./cli.sh sprint clear-session-id --sprint-id sprint-22 --actor bernard --reason "context contamination"
```

Limpa session_id (próxima task gera fresh). Idempotente. Closed sprint: rejeita.
```

- [ ] **Step 2: Append "Session reuse + kill-switch" ao dispatcher-agent/README.md**

```markdown

## Session reuse per sprint (wave dispatcher-same-session-per-sprint)

Tasks da mesma current sprint do projeto compartilham 1 session Claude Code via `claude --resume`. Primeira task gera UUID e grava em `sprint.execution_session_id`; subsequentes reusam.

### Kill-switch

Se houver bug com `--resume` ou suspeita de context contamination, restaurar comportamento legado em <30s:

```bash
systemctl --user edit openclaw-cron-dispatcher.service
# adiciona:
[Service]
Environment="OPENCLAW_DISPATCHER_DISABLE_SESSION_REUSE=1"

systemctl --user daemon-reload
systemctl --user restart openclaw-cron-dispatcher.timer
```

Comportamento com kill-switch ativo:
- Cada task spawna `claude --session-id <novo-uuid>` (fresh)
- Kanban estado de sprint NÃO muda (sprint mantém session_id existing read-only)
- Cron audit registra `kill_switch_active: true` + `session_was_fresh: true`

Desativar kill-switch volta automaticamente ao reuse.

### Recovery cirúrgico (sprint específica)

Sem kill-switch global, limpar só uma sprint problemática:

```bash
~/.openclaw/kanban-tasks/cli.sh sprint clear-session-id --sprint-id sprint-22 \
  --actor bernard --reason "context bloat after Task 1.3"
```

Próxima task da sprint gera UUID novo. Outras sprints intocadas.

### Audit

`cron.jsonl` por tick captura em ações `dispatched`:
- `execution_session_id`: UUID usado (resume ou fresh)
- `session_was_fresh`: `true` se primeira task da sprint, `false` se resume

`executions/<task>.log` ganha header pré-spawn com metadata:
```
# DISPATCHER METADATA
# task_id: T-0099
# sprint_id: sprint-22
# execution_session_id: abc-uuid
# session_was_fresh: true
# kill_switch_active: false
# ----- claude output below -----
```
```

- [ ] **Step 3: Verify content**

```bash
tail -25 ~/.openclaw/kanban-tasks/README.md
echo "---"
tail -45 ~/.openclaw/dispatcher-agent/README.md
```

- [ ] **Step 4: Commit**

```bash
cd ~/.openclaw && git add kanban-tasks/README.md dispatcher-agent/README.md && git commit -m "$(cat <<'EOF'
docs(kanban+dispatcher): documentar session reuse + kill-switch

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Push openclaw PR + pause for merge gate

- [ ] **Step 1: Verificar branch + status**

```bash
cd ~/.openclaw && git status --short
git log --oneline main..HEAD | head -10
```

Expected: branch `feat/dispatcher-same-session-per-sprint` com ~8 commits.

- [ ] **Step 2: Suite final completa**

```bash
cd ~/.openclaw/kanban-tasks && python3 -m unittest discover 2>&1 | tail -3
cd ~/.openclaw/dispatcher-agent && python3 -m unittest discover 2>&1 | tail -3
cd ~/.openclaw/scrum-master-agent && python3 -m unittest discover 2>&1 | tail -3
```

Expected: kanban 91+, dispatcher 22+, scrum-master 41 — todos green, zero regressão.

- [ ] **Step 3: Push**

```bash
cd ~/.openclaw && git push -u origin feat/dispatcher-same-session-per-sprint
```

- [ ] **Step 4: Abrir PR**

```bash
cd ~/.openclaw && gh pr create --title "feat(dispatcher): same-session reuse per sprint (E10/dispatcher-same-session-per-sprint)" --body "$(cat <<'EOF'
## Summary
Tasks da mesma current sprint do projeto compartilham 1 session_id Claude Code via \`--resume\`. Primeira task gera UUID + grava em \`sprint.execution_session_id\`; tasks subsequentes spawnam com \`--resume <uuid>\`.

Schema additive (sprint.execution_session_id field opcional, sem schema_version bump). Kill-switch \`OPENCLAW_DISPATCHER_DISABLE_SESSION_REUSE=1\` pra rollback operacional <30s.

Spec: \`bevox-knowledge/35_specs/openclaw/2026-04-25-dispatcher-same-session-per-sprint.md\` (PR #merged)
Plano: \`docs/superpowers/plans/2026-04-25-dispatcher-same-session-per-sprint.md\`

## What's in this PR
~9 commits TDD:
- plan + spec PR push
- set_session_id helper + 4 tests
- clear_session_id helper + 3 tests + close_current preservation regression
- CLI subparsers (sprint set-session-id + clear-session-id)
- runner branch fresh/resume + kill-switch + log header pre-write + 5 tests
- cmd_next propagation + 3 integration tests
- cron audit fields + 2 tests
- READMEs (kanban + dispatcher)

## Test plan
- [x] kanban-tasks: 91/91 tests green (+8 novos: set/clear session_id + close_current preservation)
- [x] scrum-master-agent: 41/41 zero regressão
- [x] dispatcher-agent: 22/22 tests green (+10 novos: runner reuse + cmd_next propagation + cron audit)
- [ ] **Pós-merge:** pull main → restart timers → smoke E2E (5 cenários gating)

## Rollback
- **Tier 1** (kill-switch): \`OPENCLAW_DISPATCHER_DISABLE_SESSION_REUSE=1\` em dropin → 30s
- **Tier 2** (clear seletivo): \`kanban-tasks/cli.sh sprint clear-session-id --sprint-id X\` → minutos
- **Tier 3** (revert): \`git revert\` → schema additive, zero migration reversa

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 5: PAUSA — aguardar Bernard mergear**

Parar aqui. Bernard revisa + merge. Retomar Task 10 só após merge confirmado em main.

---

## Task 10: Pull main + restart timers + verify

**Pré-requisito:** PR mergeada; main atualizada no GitHub.

- [ ] **Step 1: Pull main local**

```bash
cd ~/.openclaw && git checkout main && git pull --ff-only
git log --oneline -3
```

Expected: merge commit visível.

- [ ] **Step 2: Restart serviços (carregam runner.py + cron.py atualizados)**

```bash
systemctl --user daemon-reload
systemctl --user restart openclaw-cron-dispatcher.timer openclaw-reaper.timer
systemctl --user list-timers --no-pager 2>&1 | grep -E "cron-dispatcher|reaper" | head
```

Expected: timers active.

- [ ] **Step 3: Verificar primeiro tick pós-deploy**

```bash
systemctl --user start openclaw-cron-dispatcher.service
sleep 3
tail -1 ~/.openclaw/dispatcher-agent/cron.jsonl | python3 -c "
import sys, json
d = json.loads(sys.stdin.read())
print('tick:', d['tick_id'])
for a in d.get('actions_per_project',[]):
    out = a.get('outcome')
    sid = a.get('execution_session_id')
    fresh = a.get('session_was_fresh')
    if out == 'dispatched':
        print(f'  {a[\"project\"]:20} dispatched session={sid} fresh={fresh}')
    else:
        print(f'  {a[\"project\"]:20} {out}')
"
```

Expected: tick rodou sem erro. Se algum dispatch ocorreu, mostrar campos novos populated. Se todos skipped, OK também (test-project pode estar sem ready).

---

## Task 11: Smoke E2E (5 cenários gating delivery)

**Pré-requisito:** Task 10 completa; serviços rodando código novo.

- [ ] **Cenário 1: Fresh session na primeira task**

```bash
~/.openclaw/kanban-tasks/cli.sh task add "smoke-session-T1" --project test-project --actor bernard --payload '{"goal":"Criar ~/smoke-session-T1.txt com texto first","acceptance_criteria":["Arquivo existe"],"spec_ref":"n/a"}' --json | python3 -c "import sys, json; print('id:', json.load(sys.stdin)['task']['id'])"
# Captura task id (e.g., T-0099)
TID1=$(~/.openclaw/kanban-tasks/cli.sh task list --json | python3 -c "
import sys, json
tasks = json.load(sys.stdin)['tasks']
match = [t for t in tasks if 'smoke-session-T1' in (t.get('title') or '')]
print(match[-1]['id'] if match else '')")
echo "TID1=$TID1"
~/.openclaw/kanban-tasks/cli.sh task move $TID1 ready --actor bernard
# Trigger tick
systemctl --user start openclaw-cron-dispatcher.service
sleep 3
# Verify cron.jsonl tem session_was_fresh: true
tail -1 ~/.openclaw/dispatcher-agent/cron.jsonl | python3 -c "
import sys, json
d = json.loads(sys.stdin.read())
for a in d.get('actions_per_project',[]):
    if a.get('task_id') == '$TID1':
        assert a.get('session_was_fresh') == True, f'expected fresh, got {a}'
        sid = a.get('execution_session_id')
        assert sid, 'no session_id'
        print(f'OK: T1 dispatched fresh session_id={sid}')
        # Save sid pra cenário 2
        with open('/tmp/smoke-sid.txt','w') as f: f.write(sid)
"
# Verify sprint.execution_session_id populated
python3 -c "
import json
s = json.load(open('~/.openclaw/kanban-tasks/state.json'))
sp = next(sp for sp in s['sprints'] if sp['state']=='current' and sp['project']=='test-project')
print('sprint:', sp['id'], 'session_id:', sp.get('execution_session_id'))
assert sp.get('execution_session_id'), 'sprint session_id not populated'
"
```

Expected: ✅ T1 dispatched fresh + sprint session_id populated.

Aguardar T1 reach testing/done (varia, ~1-2min). Verificar artefato:
```bash
ls ~/smoke-session-T1.txt && cat ~/smoke-session-T1.txt
```

- [ ] **Cenário 2: Resume na segunda task**

Cria T2 na mesma sprint:

```bash
~/.openclaw/kanban-tasks/cli.sh task add "smoke-session-T2" --project test-project --actor bernard --payload '{"goal":"Modifique o arquivo ~/smoke-session-T1.txt adicionando linha second; o nome do arquivo deve estar evidente para você sem precisar Read","acceptance_criteria":["Arquivo ~/smoke-session-T1.txt contem linha second"],"spec_ref":"n/a"}'
TID2=$(~/.openclaw/kanban-tasks/cli.sh task list --json | python3 -c "
import sys, json
tasks = json.load(sys.stdin)['tasks']
match = [t for t in tasks if 'smoke-session-T2' in (t.get('title') or '')]
print(match[-1]['id'] if match else '')")
echo "TID2=$TID2"
# Aguardar T1 reach testing OR done (não pode dispatchar T2 enquanto T1 in_progress — 1-task-per-project)
# Quando T1 done: mover T2 ready
~/.openclaw/kanban-tasks/cli.sh task move $TID2 ready --actor bernard
systemctl --user start openclaw-cron-dispatcher.service
sleep 3
tail -1 ~/.openclaw/dispatcher-agent/cron.jsonl | python3 -c "
import sys, json
d = json.loads(sys.stdin.read())
expected_sid = open('/tmp/smoke-sid.txt').read().strip()
for a in d.get('actions_per_project',[]):
    if a.get('task_id') == '$TID2':
        assert a.get('session_was_fresh') == False, f'expected resume, got {a}'
        assert a.get('execution_session_id') == expected_sid, f'session changed: {a.get(\"execution_session_id\")} vs {expected_sid}'
        print(f'OK: T2 resumed session_id={expected_sid}')
"
```

Expected: ✅ T2 resumed; session_id MESMO da T1.

Verificar log header:
```bash
head -10 ~/.openclaw/dispatcher-agent/executions/$TID2.log
```

Expected: tem `# session_was_fresh: False` e `# execution_session_id: <mesmo da T1>`.

- [ ] **Cenário 3: Continuidade lógica**

Verificar que Claude na T2 modificou o arquivo certo SEM Read explícito (porque sabe da memória da sessão):

```bash
grep -c "Read" ~/.openclaw/dispatcher-agent/executions/$TID2.log || true
grep -c "Read" ~/.openclaw/dispatcher-agent/executions/$TID1.log || true
```

Expected: T2 tem MENOS Read calls que T1 (T1 fez Read pra contextualizar; T2 não precisou refazer).

E verificar arquivo final:
```bash
cat ~/smoke-session-T1.txt
```

Expected: contém linha "first" + "second" — Claude T2 lembrou do arquivo da T1 sem briefing dizer.

- [ ] **Cenário 4: Kill-switch força fresh**

```bash
mkdir -p ~/.config/systemd/user/openclaw-cron-dispatcher.service.d/
cat > ~/.config/systemd/user/openclaw-cron-dispatcher.service.d/disable-session-reuse.conf <<'EOF'
[Service]
Environment="OPENCLAW_DISPATCHER_DISABLE_SESSION_REUSE=1"
EOF
systemctl --user daemon-reload
systemctl --user restart openclaw-cron-dispatcher.timer

# Cria T3 na mesma sprint
~/.openclaw/kanban-tasks/cli.sh task add "smoke-session-T3-killswitch" --project test-project --actor bernard --payload '{"goal":"echo killswitch","acceptance_criteria":["x"],"spec_ref":"n/a"}'
TID3=$(~/.openclaw/kanban-tasks/cli.sh task list --json | python3 -c "
import sys, json
tasks = json.load(sys.stdin)['tasks']
match = [t for t in tasks if 'killswitch' in (t.get('title') or '')]
print(match[-1]['id'] if match else '')")
~/.openclaw/kanban-tasks/cli.sh task move $TID3 ready --actor bernard
systemctl --user start openclaw-cron-dispatcher.service
sleep 3
tail -1 ~/.openclaw/dispatcher-agent/cron.jsonl | python3 -c "
import sys, json
d = json.loads(sys.stdin.read())
expected_sid = open('/tmp/smoke-sid.txt').read().strip()
for a in d.get('actions_per_project',[]):
    if a.get('task_id') == '$TID3':
        assert a.get('session_was_fresh') == True, f'expected kill-switch fresh, got {a}'
        assert a.get('execution_session_id') != expected_sid, 'should be NEW uuid'
        print(f'OK: T3 with kill-switch dispatched fresh, NEW session={a[\"execution_session_id\"]}')
"
# Verify sprint state.json NÃO mudou (kill-switch skip kanban write)
python3 -c "
import json
s = json.load(open('~/.openclaw/kanban-tasks/state.json'))
sp = next(sp for sp in s['sprints'] if sp['state']=='current' and sp['project']=='test-project')
expected = open('/tmp/smoke-sid.txt').read().strip()
assert sp.get('execution_session_id') == expected, f'sprint state mutated! {sp.get(\"execution_session_id\")} vs {expected}'
print(f'OK: sprint state.json preserved (still {expected})')
"
# Disable kill-switch
rm ~/.config/systemd/user/openclaw-cron-dispatcher.service.d/disable-session-reuse.conf
systemctl --user daemon-reload
systemctl --user restart openclaw-cron-dispatcher.timer
```

Expected: ✅ T3 fresh com UUID diferente; sprint estado intocado.

- [ ] **Cenário 5: Close-current reset session**

Aguardar T3 chegar a um estado terminal (testing, done, or blocked). Então fechar sprint:

```bash
# Aguardar todas tasks ativas em test-project terminarem (testing/done/rejected)
# OU mover manualmente pra simplificar smoke
~/.openclaw/kanban-tasks/cli.sh sprint close-current --project test-project --actor bernard --carryover '[]'

# Verificar novo current sprint sem session_id
python3 -c "
import json
s = json.load(open('~/.openclaw/kanban-tasks/state.json'))
sp_new = next(sp for sp in s['sprints'] if sp['state']=='current' and sp['project']=='test-project')
print(f'novo current: {sp_new[\"id\"]} session_id={sp_new.get(\"execution_session_id\")}')
assert sp_new.get('execution_session_id') is None, 'novo current não deveria ter session_id'
print('OK: novo current sem session_id (lazy)')
"

# Cria T4 na nova current → deve gerar UUID NOVO
~/.openclaw/kanban-tasks/cli.sh task add "smoke-session-T4-after-close" --project test-project --actor bernard --payload '{"goal":"echo new sprint","acceptance_criteria":["x"],"spec_ref":"n/a"}'
TID4=$(~/.openclaw/kanban-tasks/cli.sh task list --json | python3 -c "
import sys, json
tasks = json.load(sys.stdin)['tasks']
match = [t for t in tasks if 'after-close' in (t.get('title') or '')]
print(match[-1]['id'] if match else '')")
~/.openclaw/kanban-tasks/cli.sh task move $TID4 ready --actor bernard
systemctl --user start openclaw-cron-dispatcher.service
sleep 3
tail -1 ~/.openclaw/dispatcher-agent/cron.jsonl | python3 -c "
import sys, json
d = json.loads(sys.stdin.read())
old_sid = open('/tmp/smoke-sid.txt').read().strip()
for a in d.get('actions_per_project',[]):
    if a.get('task_id') == '$TID4':
        assert a.get('session_was_fresh') == True, 'novo sprint task deveria ser fresh'
        assert a.get('execution_session_id') != old_sid, 'session deveria ser NOVA'
        print(f'OK: T4 fresh com novo session_id={a[\"execution_session_id\"]}')
"
```

Expected: ✅ Novo current sprint sem session_id; T4 gera UUID NOVO (≠ T1/T2/T3).

- [ ] **Step Final — Smoke gate**

Se 5/5 pass → wave delivered. Se qualquer falha → rollback Tier 1 (kill-switch) + investigar:

```bash
# Rollback rápido se necessário
mkdir -p ~/.config/systemd/user/openclaw-cron-dispatcher.service.d/
cat > ~/.config/systemd/user/openclaw-cron-dispatcher.service.d/disable-session-reuse.conf <<'EOF'
[Service]
Environment="OPENCLAW_DISPATCHER_DISABLE_SESSION_REUSE=1"
EOF
systemctl --user daemon-reload && systemctl --user restart openclaw-cron-dispatcher.timer
```

---

## Task 12: Tracker entry — wave delivered

**Files:**
- Modify: `bevox-knowledge/40_roadmap/_shared/delivery-tracker.yml`

- [ ] **Step 1: Branch + adicionar entry**

```bash
cd ~/bevox-knowledge && git checkout main && git pull --ff-only
git checkout -b draft/tracker-dispatcher-same-session-delivered
```

Editar `40_roadmap/_shared/delivery-tracker.yml`. Após `id: sprint-per-project` no E10 block, adicionar:

```yaml
      - id: dispatcher-same-session-per-sprint
        status: delivered
        delivered_at: 2026-04-25
        spec: 35_specs/openclaw/2026-04-25-dispatcher-same-session-per-sprint.md
        pr_openclaw: https://github.com/bernardTavares/openclaw/pull/<N>
        narrative: "Tasks da mesma current sprint do projeto compartilham 1 session Claude Code via --resume; primeira task gera UUID lazy + grava em sprint.execution_session_id; subsequentes reusam"
        features:
          - "Schema additive: sprint.execution_session_id field opcional (sem schema_version bump). Backward/forward-compat automático"
          - "kanban-tasks/lib/sprint.py: set_session_id (idempotente, rejeita closed) + clear_session_id (recovery operacional, idempotente, rejeita closed)"
          - "kanban-tasks CLI: sprint set-session-id + sprint clear-session-id subparsers (set chamado primariamente pelo dispatcher; clear é manual recovery)"
          - "dispatcher-agent/lib/runner.py: launch_detached + launch_foreground com branching fresh/resume; gera UUID novo + retorna is_fresh=True (primeira task) OU usa --resume <uuid> (subsequentes); pre-write log header com metadata (DISPATCHER METADATA preâmbulo)"
          - "dispatcher-agent/lib/api.py:cmd_next propaga sprint_session_id pro runner; quando is_fresh=True E kill-switch off, chama kanban CLI sprint set-session-id pra gravar UUID na sprint"
          - "dispatcher-agent/lib/cron.py: actions_per_project[] em outcome=dispatched ganha execution_session_id + session_was_fresh fields (audit completo)"
          - "Kill-switch OPENCLAW_DISPATCHER_DISABLE_SESSION_REUSE=1 força fresh per task + skip kanban write; rollback operacional <30s sem code revert"
          - "Tester boundary preservada: tester-agent spawn fresh session_id próprio (validator ≠ author). Worker session NÃO compartilhada"
          - "8 unit tests kanban-tasks (set/clear session_id + close_current preservation regression) + 10 unit/integration tests dispatcher (runner reuse + cmd_next propagation + cron audit) + 5 smoke E2E gating pós-deploy"
          - "Smoke E2E validou: (1) primeira task fresh + sprint.execution_session_id populated; (2) segunda task na mesma sprint resume com mesmo UUID + log header consistente; (3) continuidade lógica observada (T2 não re-Read arquivos da T1); (4) kill-switch força fresh + sprint state.json intocado; (5) close-current promove next→current sem migrar session_id; T4 da nova sprint gera UUID novo"
          - "Wave habilita C.1 do backlog operacional (motivador da sprint-per-project): scope sprint bem-definido + reuse session permite continuidade lógica + token economy entre tasks de uma sprint"
```

(Substituir `<N>` pelo PR number real do openclaw.)

- [ ] **Step 2: Validar YAML + commit + push + PR**

```bash
cd ~/bevox-knowledge && python3 -c "import yaml; yaml.safe_load(open('40_roadmap/_shared/delivery-tracker.yml')); print('valid')"
git add 40_roadmap/_shared/delivery-tracker.yml
git commit -m "$(cat <<'EOF'
tracker(E10/dispatcher-same-session-per-sprint): delivered 2026-04-25

Wave entregue end-to-end: same-session reuse per sprint via --resume,
schema additive, kill-switch operacional, audit completo.

PRs: openclaw #<N>, bevox-knowledge spec #<N>
Spec: 35_specs/openclaw/2026-04-25-dispatcher-same-session-per-sprint.md
Smoke E2E 5 cenários gating todos pass.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git push -u origin draft/tracker-dispatcher-same-session-delivered
gh pr create --title "tracker(E10/dispatcher-same-session-per-sprint): delivered 2026-04-25" --body "## Summary
Entry no delivery-tracker registrando wave \`dispatcher-same-session-per-sprint\` do E10 como delivered.

## Test plan
- [x] YAML válido
- [x] Smoke E2E 5 cenários executados (§7.5 spec)
- [x] PRs (spec + impl) merged

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

- [ ] **Step 3: Aguardar Bernard mergear**

Bernard merge → wave fechada formalmente.

---

## Self-review

**Spec coverage:**
- §2 modelo de dados → Tasks 2-3 (set/clear session_id + close_current preservation)
- §3 componentes → Tasks 2-7 (sprint helpers + CLI + runner + cmd_next + cron audit)
- §4 edge cases → coberto distribuído nos tests + smoke E2E
- §5 arquivos → todos cobertos
- §6 ordem dos PRs → Tasks 1 (spec PR), 9 (impl PR), 12 (tracker)
- §7 testing → 16 unit tests distribuídos; 5 smoke gating em Task 11
- §7.1-7.3 rollback → kill-switch (Task 5+8 docs), clear-session-id (Task 3), revert (PR description Task 9)
- §8 DoD → 10 critérios mapeados nos cenários da Task 11

**Placeholder scan:** zero TBD/TODO. Code blocks completos em todos os steps.

**Type consistency:**
- `set_session_id(sprint_id, session_id, actor)` — assinatura consistent entre Task 2 (criação) e Task 4 (CLI subparser).
- `clear_session_id(sprint_id, actor, reason)` — Task 3 + Task 4.
- `launch_detached(task_id, briefing_path, allowed_tools, *, sprint_session_id, sprint_id, model)` — keyword-only args, Task 5 + Task 6.
- Status dict keys (`sprint_session_id`, `sprint_session_was_fresh`, `kill_switch_active`) — consistentes Task 5 (runner) → Task 6 (cmd_next) → Task 7 (cron audit).

Issues encontrados: nenhum.
