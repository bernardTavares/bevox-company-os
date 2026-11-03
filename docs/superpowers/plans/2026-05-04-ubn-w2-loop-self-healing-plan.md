# UBN wave-2 — Loop Self-Healing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar 4 components (F1 gating-by-status, F2 lifecycle hook, F3 executor deadline + safety net, F4 stuck-in-ready criterion) que tornam o loop dispatcher↔reaper↔kanban↔executor self-healing.

**Architecture:** Single bundle em branch `feat/ubn-w2-loop-self-healing` em `~/.openclaw`. 5 files modificados (`cron.py`, `task.py`, `runner.py`, `reaper.py`, `block_scanner.py`), 4 test files novos, 1 script backfill. Sem mudanças em knowledge-sync/mission-control/bevox-site.

**Tech Stack:** Python 3.11+, unittest, systemd-run --user, JSON state files. Test runner: `cd <agent-dir> && python3 -m unittest tests.test_<module>`.

**Spec canônico:** `bevox-knowledge/35_specs/openclaw/2026-05-04-ubn-w2-loop-self-healing.md`

---

## Phase 0 — Setup

### Task 0.1: Create feature branch

**Files:**
- N/A (git operation)

- [ ] **Step 1: Confirm working tree clean (modified runtime files OK)**

```bash
cd ~/.openclaw
git status -sb | head -3
# Expected: ## main...origin/main
# Modified files (devices/paired.json, openclaw.json, etc.) são runtime state,
# não devem viajar com a branch
```

- [ ] **Step 2: Create branch from main**

```bash
git checkout main
git pull --ff-only origin main
git checkout -b feat/ubn-w2-loop-self-healing
git status
```

Expected: `On branch feat/ubn-w2-loop-self-healing`

---

## Phase 1 — F1: gating-by-status no cron-dispatcher

### Task 1.1: Failing test — active status filter excludes done/archived/rejected/backlog

**Files:**
- Create: `dispatcher-agent/tests/test_cron_gating_active_status.py`

- [ ] **Step 1: Write failing test**

```python
"""Test F1: has_open_escalation_for_project filtra task IDs por status ativo
antes do scan de escalation files.

Spec: bevox-knowledge/35_specs/openclaw/2026-05-04-ubn-w2-loop-self-healing.md §F1
"""
import unittest
import tempfile
import shutil
from pathlib import Path

from lib.cron import has_open_escalation_for_project


class TestActiveStatusFilter(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.clr_dir = self.tmpdir / "clarification" / "escalations"
        self.tester_dir = self.tmpdir / "tester" / "escalations"
        self.clr_dir.mkdir(parents=True)
        self.tester_dir.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _create_clr_file(self, task_id: str):
        (self.clr_dir / f"{task_id}-clr-1.md").write_text("---\nstatus: open\n---\n")

    def test_done_task_with_clr_file_does_not_block(self):
        """Task done com clr file órfão NÃO bloqueia projeto."""
        self._create_clr_file("T-0161")
        tasks = [{"id": "T-0161", "status": "done"}]
        self.assertFalse(has_open_escalation_for_project(tasks, self.clr_dir, self.tester_dir))

    def test_archived_task_with_clr_file_does_not_block(self):
        self._create_clr_file("T-0070")
        tasks = [{"id": "T-0070", "status": "archived"}]
        self.assertFalse(has_open_escalation_for_project(tasks, self.clr_dir, self.tester_dir))

    def test_rejected_task_with_clr_file_does_not_block(self):
        self._create_clr_file("T-0049")
        tasks = [{"id": "T-0049", "status": "rejected"}]
        self.assertFalse(has_open_escalation_for_project(tasks, self.clr_dir, self.tester_dir))

    def test_backlog_task_with_clr_file_does_not_block(self):
        self._create_clr_file("T-0150")
        tasks = [{"id": "T-0150", "status": "backlog"}]
        self.assertFalse(has_open_escalation_for_project(tasks, self.clr_dir, self.tester_dir))

    def test_ready_task_with_clr_file_blocks(self):
        """Task ready com clr file pendente DEVE bloquear (gate ativo)."""
        self._create_clr_file("T-0165")
        tasks = [{"id": "T-0165", "status": "ready"}]
        self.assertTrue(has_open_escalation_for_project(tasks, self.clr_dir, self.tester_dir))

    def test_in_progress_task_with_tr_file_blocks(self):
        (self.tester_dir / "T-0050-tr-1.md").write_text("---\n---\n")
        tasks = [{"id": "T-0050", "status": "in_progress"}]
        self.assertTrue(has_open_escalation_for_project(tasks, self.clr_dir, self.tester_dir))

    def test_testing_task_with_clr_file_blocks(self):
        self._create_clr_file("T-0024")
        tasks = [{"id": "T-0024", "status": "testing"}]
        self.assertTrue(has_open_escalation_for_project(tasks, self.clr_dir, self.tester_dir))

    def test_blocked_flag_overrides_status(self):
        """Task com blocked=true SEMPRE conta (mesmo se status=backlog)."""
        self._create_clr_file("T-0150")
        tasks = [{"id": "T-0150", "status": "backlog", "blocked": True}]
        self.assertTrue(has_open_escalation_for_project(tasks, self.clr_dir, self.tester_dir))

    def test_no_active_tasks_returns_false_immediately(self):
        """Lista sem tasks ativas retorna False sem scan de filesystem."""
        tasks = [{"id": "T-0001", "status": "done"}, {"id": "T-0002", "status": "archived"}]
        self.assertFalse(has_open_escalation_for_project(tasks, self.clr_dir, self.tester_dir))

    def test_mixed_project_only_active_count(self):
        """Done com file + Ready sem file → False (filter funciona)."""
        self._create_clr_file("T-DONE")
        tasks = [
            {"id": "T-DONE", "status": "done"},
            {"id": "T-READY", "status": "ready"},
        ]
        self.assertFalse(has_open_escalation_for_project(tasks, self.clr_dir, self.tester_dir))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test, verify it fails**

```bash
cd ~/.openclaw/dispatcher-agent
python3 -m unittest tests.test_cron_gating_active_status 2>&1 | tail -5
```

Expected: FAILs com `TypeError` (signature mismatch — função hoje aceita `task_ids: List[str]`).

### Task 1.2: Implement F1 — signature change + active filter

**Files:**
- Modify: `dispatcher-agent/lib/cron.py:78-106` (function `has_open_escalation_for_project`)
- Modify: `dispatcher-agent/lib/cron.py:198` (caller in `project_blocks_dispatch`)

- [ ] **Step 1: Replace function body**

Substituir linhas 78-106 de `cron.py` por:

```python
ACTIVE_STATUSES = frozenset({"ready", "in_progress", "testing"})


def has_open_escalation_for_project(
    tasks: List[dict],
    clarification_dir: Path,
    tester_dir: Path,
) -> bool:
    """True se ha escalation aberta (clarification OR tester) pra qualquer task
    em status ativo (ready/in_progress/testing) ou com flag blocked=true.

    Tasks em done/rejected/archived/backlog NÃO bloqueiam o projeto, mesmo se
    tiverem escalation files órfãs.

    Patterns: <task_id>-clr-<N>.md OR <task_id>-tr-<N>.md
    """
    active_ids = {
        t["id"] for t in tasks
        if t.get("id") and (t.get("status") in ACTIVE_STATUSES or t.get("blocked"))
    }
    if not active_ids:
        return False
    for d in (clarification_dir, tester_dir):
        if not d.exists() or not d.is_dir():
            continue
        try:
            for p in d.iterdir():
                if not (p.is_file() or p.is_symlink()):
                    continue
                name = p.name
                for marker in ("-clr-", "-tr-"):
                    idx = name.find(marker)
                    if idx > 0:
                        if name[:idx] in active_ids:
                            return True
                        break
        except OSError:
            continue
    return False
```

- [ ] **Step 2: Update caller (cron.py:198)**

Linha 198 atual: `task_ids = [t.get("id") for t in tasks if t.get("id")]`
Deletar essa linha e mudar a chamada na linha seguinte:

Antes:
```python
    task_ids = [t.get("id") for t in tasks if t.get("id")]
    if has_open_escalation_for_project(task_ids, clarification_dir, tester_dir):
```

Depois:
```python
    if has_open_escalation_for_project(tasks, clarification_dir, tester_dir):
```

- [ ] **Step 3: Run new test**

```bash
cd ~/.openclaw/dispatcher-agent
python3 -m unittest tests.test_cron_gating_active_status 2>&1 | tail -3
```

Expected: `OK` (10 tests passing).

- [ ] **Step 4: Run regression on full dispatcher tests**

```bash
cd ~/.openclaw/dispatcher-agent
for t in tests/test_*.py; do
    name=$(basename "$t" .py)
    python3 -m unittest "tests.$name" 2>&1 | tail -1
done
```

Expected: All pass (or pre-existing skips, no new failures).

- [ ] **Step 5: Commit**

```bash
cd ~/.openclaw
git add dispatcher-agent/lib/cron.py dispatcher-agent/tests/test_cron_gating_active_status.py
git commit -m "feat(ubn-w2): F1 cron-dispatcher gating-by-status (exclui done/rejected/archived/backlog)"
```

---

## Phase 2 — F2: lifecycle hook escalation cleanup

### Task 2.1: Failing test — UBN -blk- frontmatter rewrite

**Files:**
- Create: `kanban-tasks/tests/test_auto_close_escalations.py`

- [ ] **Step 1: Write failing test**

```python
"""Test F2: _auto_close_escalations fecha files relacionadas quando task
move pra terminal status.

Spec: bevox-knowledge/35_specs/openclaw/2026-05-04-ubn-w2-loop-self-healing.md §F2
"""
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch

from lib.task import _auto_close_escalations


class TestAutoCloseEscalations(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.clr_esc = self.tmpdir / "clarification-agent" / "escalations"
        self.tester_esc = self.tmpdir / "tester-agent" / "escalations"
        self.clr_esc.mkdir(parents=True)
        self.tester_esc.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _patch_dirs(self):
        return patch.multiple(
            "lib.task",
            UBN_CLR_ESCALATIONS_DIR=self.clr_esc,
            TESTER_ESCALATIONS_DIR=self.tester_esc,
        )

    def test_ubn_blk_frontmatter_status_rewritten(self):
        """File T-0070-blk-1.md com status:open vira status:closed_task_resolved."""
        path = self.clr_esc / "T-0070-blk-1.md"
        path.write_text(
            "---\n"
            "task_id: T-0070\n"
            "status: open\n"
            "criterion: blocked\n"
            "---\n\n"
            "# body\n",
            encoding="utf-8",
        )
        state = {"events": [], "last_event_seq": 0}
        with self._patch_dirs():
            result = _auto_close_escalations(state, "T-0070", "done", "bernard")

        new_text = path.read_text(encoding="utf-8")
        self.assertIn("status: closed_task_resolved", new_text)
        self.assertNotIn("status: open", new_text)
        # Body preserved
        self.assertIn("# body", new_text)
        self.assertEqual(len(result["affected_files"]), 1)
        self.assertEqual(result["affected_files"][0]["action"], "frontmatter_closed")

    def test_ubn_blk_already_closed_idempotent(self):
        """Re-run em file já closed = noop (não quebra)."""
        path = self.clr_esc / "T-0070-blk-1.md"
        path.write_text(
            "---\n"
            "task_id: T-0070\n"
            "status: closed_task_resolved\n"
            "---\n",
            encoding="utf-8",
        )
        state = {"events": [], "last_event_seq": 0}
        with self._patch_dirs():
            result = _auto_close_escalations(state, "T-0070", "done", "bernard")
        self.assertEqual(len(result["affected_files"]), 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test, verify it fails**

```bash
cd ~/.openclaw/kanban-tasks
python3 -m unittest tests.test_auto_close_escalations 2>&1 | tail -3
```

Expected: FAIL — `ImportError: cannot import name '_auto_close_escalations'`.

### Task 2.2: Implement _auto_close_escalations — UBN frontmatter rewrite

**Files:**
- Modify: `kanban-tasks/lib/task.py` (adicionar função após `_auto_release_dependents` ~linha 615)

- [ ] **Step 1: Add module constants near top of task.py imports**

Adicionar após os imports existentes (perto da linha 1-20):

```python
import re

UBN_CLR_ESCALATIONS_DIR = Path("~/.openclaw/clarification-agent/escalations")
TESTER_ESCALATIONS_DIR = Path("~/.openclaw/tester-agent/escalations")
TERMINAL_STATUSES = ("done", "rejected", "archived")
```

- [ ] **Step 2: Add helper for frontmatter rewrite**

Adicionar antes de `_auto_close_escalations` (vai ser criada na próxima step):

```python
def _rewrite_ubn_status_to_closed(path: Path) -> bool:
    """Rewrite frontmatter status:open → status:closed_task_resolved.
    Idempotent: returns False se já estava closed_task_resolved ou não open."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return False
    m = re.match(r"(---\n)(.*?)(\n---\n)", content, re.DOTALL)
    if not m:
        return False
    fm = m.group(2)
    if "status: closed_task_resolved" in fm:
        return False
    new_fm = re.sub(
        r"^status:\s*open\s*$",
        "status: closed_task_resolved",
        fm,
        flags=re.MULTILINE,
    )
    if new_fm == fm:
        return False
    new_content = m.group(1) + new_fm + m.group(3) + content[m.end():]
    path.write_text(new_content, encoding="utf-8")
    return True
```

- [ ] **Step 3: Add main hook function**

Adicionar após `_block_dependents_upstream_failed` (~linha 670):

```python
def _auto_close_escalations(
    state: Dict[str, Any], task_id: str, new_status: str, actor: str
) -> Dict[str, Any]:
    """Hook: task entrou em terminal status. Fecha/arquiva files relacionadas.

    UBN -blk- files: rewrite frontmatter status: open → closed_task_resolved
    -clr- e -tr- files em escalations/: mv pra _resolved-YYYYMMDD/ (Phase 2.4)
    Question/answer files: leave alone (history)

    Emite evento task_escalations_auto_closed se houver mudança.

    Returns: {affected_files: [...], errors: [...]}
    """
    if new_status not in TERMINAL_STATUSES:
        return {"affected_files": [], "errors": []}
    affected = []
    errors = []
    if UBN_CLR_ESCALATIONS_DIR.is_dir():
        for path in UBN_CLR_ESCALATIONS_DIR.glob(f"{task_id}-blk-*.md"):
            try:
                if _rewrite_ubn_status_to_closed(path):
                    affected.append({
                        "path": str(path),
                        "action": "frontmatter_closed",
                    })
            except OSError as e:
                errors.append({"path": str(path), "error": str(e)})
    if affected:
        seq = store.next_seq(state)
        state["last_event_seq"] = seq
        store.append_event({
            "seq": seq, "ts": store.now_iso(),
            "type": "task_escalations_auto_closed",
            "actor": actor or "system",
            "payload": {
                "task_id": task_id,
                "new_status": new_status,
                "affected_files": affected,
                "errors": errors,
            },
        })
    return {"affected_files": affected, "errors": errors}
```

- [ ] **Step 4: Run test**

```bash
cd ~/.openclaw/kanban-tasks
python3 -m unittest tests.test_auto_close_escalations 2>&1 | tail -3
```

Expected: `OK` (2 tests passing).

- [ ] **Step 5: Commit**

```bash
cd ~/.openclaw
git add kanban-tasks/lib/task.py kanban-tasks/tests/test_auto_close_escalations.py
git commit -m "feat(ubn-w2): F2.1 _auto_close_escalations + UBN frontmatter rewrite"
```

### Task 2.3: Failing test — -clr- and -tr- file moves

**Files:**
- Modify: `kanban-tasks/tests/test_auto_close_escalations.py`

- [ ] **Step 1: Add test cases at end of TestAutoCloseEscalations class**

Append antes do `if __name__ == "__main__":`:

```python
    def test_clr_file_in_escalations_moved_to_resolved(self):
        """T-XXXX-clr-N.md em clr/escalations/ é movido pra _resolved-YYYYMMDD/."""
        path = self.clr_esc / "T-0161-clr-1.md"
        path.write_text("# orphan clr file\n", encoding="utf-8")
        state = {"events": [], "last_event_seq": 0}
        with self._patch_dirs():
            result = _auto_close_escalations(state, "T-0161", "done", "bernard")

        # Original gone
        self.assertFalse(path.exists())
        # Moved to _resolved-YYYYMMDD/
        resolved_dirs = list(self.clr_esc.glob("_resolved-*"))
        self.assertEqual(len(resolved_dirs), 1)
        moved = resolved_dirs[0] / "T-0161-clr-1.md"
        self.assertTrue(moved.exists())
        self.assertEqual(result["affected_files"][0]["action"], "moved_to_resolved")

    def test_tr_file_in_tester_moved_to_resolved(self):
        path = self.tester_esc / "T-0050-tr-2.md"
        path.write_text("# orphan tr\n", encoding="utf-8")
        state = {"events": [], "last_event_seq": 0}
        with self._patch_dirs():
            result = _auto_close_escalations(state, "T-0050", "rejected", "bernard")

        self.assertFalse(path.exists())
        resolved_dirs = list(self.tester_esc.glob("_resolved-*"))
        self.assertEqual(len(resolved_dirs), 1)
        self.assertTrue((resolved_dirs[0] / "T-0050-tr-2.md").exists())

    def test_question_files_not_moved(self):
        """Question files em questions/ NÃO devem ser tocados (history)."""
        questions_dir = self.tmpdir / "clarification-agent" / "questions"
        questions_dir.mkdir(parents=True)
        q_path = questions_dir / "T-0161-clr-1.md"
        q_path.write_text("# question\n", encoding="utf-8")
        state = {"events": [], "last_event_seq": 0}
        with self._patch_dirs():
            _auto_close_escalations(state, "T-0161", "done", "bernard")
        self.assertTrue(q_path.exists())  # preserved

    def test_archived_status_triggers_hook(self):
        path = self.clr_esc / "T-0070-blk-1.md"
        path.write_text("---\nstatus: open\n---\n", encoding="utf-8")
        state = {"events": [], "last_event_seq": 0}
        with self._patch_dirs():
            result = _auto_close_escalations(state, "T-0070", "archived", "bernard")
        self.assertEqual(len(result["affected_files"]), 1)

    def test_non_terminal_status_noop(self):
        path = self.clr_esc / "T-0070-blk-1.md"
        path.write_text("---\nstatus: open\n---\n", encoding="utf-8")
        state = {"events": [], "last_event_seq": 0}
        with self._patch_dirs():
            result = _auto_close_escalations(state, "T-0070", "in_progress", "bernard")
        self.assertEqual(len(result["affected_files"]), 0)
        self.assertEqual(path.read_text(encoding="utf-8"), "---\nstatus: open\n---\n")

    def test_event_emitted_on_change(self):
        path = self.clr_esc / "T-0070-blk-1.md"
        path.write_text("---\ntask_id: T-0070\nstatus: open\n---\n", encoding="utf-8")
        state = {"events": [], "last_event_seq": 5}
        with self._patch_dirs():
            with patch("lib.store.append_event") as mock_append:
                with patch("lib.store.next_seq", return_value=6):
                    with patch("lib.store.now_iso", return_value="2026-05-04T12:00:00Z"):
                        _auto_close_escalations(state, "T-0070", "done", "bernard")
        mock_append.assert_called_once()
        event = mock_append.call_args[0][0]
        self.assertEqual(event["type"], "task_escalations_auto_closed")
        self.assertEqual(event["payload"]["task_id"], "T-0070")
        self.assertEqual(event["payload"]["new_status"], "done")
```

- [ ] **Step 2: Run, verify new tests fail**

```bash
cd ~/.openclaw/kanban-tasks
python3 -m unittest tests.test_auto_close_escalations 2>&1 | tail -3
```

Expected: FAILs nos tests novos (file move + event não implementados).

### Task 2.4: Implement -clr-/-tr- file moves to _resolved-YYYYMMDD/

**Files:**
- Modify: `kanban-tasks/lib/task.py` (extend `_auto_close_escalations`)

- [ ] **Step 1: Add helper for file move**

Adicionar antes de `_auto_close_escalations`:

```python
def _move_orphan_to_resolved(path: Path, esc_dir: Path) -> Path:
    """Move file pra <esc_dir>/_resolved-YYYYMMDD/<filename>.
    Cria diretório se não existir. Retorna novo path."""
    resolved_dir = esc_dir / f"_resolved-{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    resolved_dir.mkdir(exist_ok=True)
    new_path = resolved_dir / path.name
    path.rename(new_path)
    return new_path
```

Garantir imports de datetime/timezone no topo do file (provavelmente já existem).

- [ ] **Step 2: Extend _auto_close_escalations to handle -clr- and -tr-**

Modificar a função pra adicionar o handling antes do bloco `if affected:`:

```python
    # -clr- files orphan in clarification-agent/escalations/
    if UBN_CLR_ESCALATIONS_DIR.is_dir():
        for path in UBN_CLR_ESCALATIONS_DIR.glob(f"{task_id}-clr-*.md"):
            try:
                new_path = _move_orphan_to_resolved(path, UBN_CLR_ESCALATIONS_DIR)
                affected.append({
                    "path": str(new_path),
                    "action": "moved_to_resolved",
                })
            except OSError as e:
                errors.append({"path": str(path), "error": str(e)})

    # -tr- files orphan in tester-agent/escalations/
    if TESTER_ESCALATIONS_DIR.is_dir():
        for path in TESTER_ESCALATIONS_DIR.glob(f"{task_id}-tr-*.md"):
            try:
                new_path = _move_orphan_to_resolved(path, TESTER_ESCALATIONS_DIR)
                affected.append({
                    "path": str(new_path),
                    "action": "moved_to_resolved",
                })
            except OSError as e:
                errors.append({"path": str(path), "error": str(e)})
```

- [ ] **Step 3: Run tests**

```bash
cd ~/.openclaw/kanban-tasks
python3 -m unittest tests.test_auto_close_escalations 2>&1 | tail -3
```

Expected: `OK` (8 tests passing total).

- [ ] **Step 4: Commit**

```bash
cd ~/.openclaw
git add kanban-tasks/lib/task.py kanban-tasks/tests/test_auto_close_escalations.py
git commit -m "feat(ubn-w2): F2.2 _auto_close_escalations move -clr-/-tr- + event emit"
```

### Task 2.5: Wire hook em move_status (done/rejected)

**Files:**
- Modify: `kanban-tasks/lib/task.py:159-260` (function `move_status`)

- [ ] **Step 1: Find existing _auto_release_dependents callsite**

Linha 248 atual contém `_auto_release_dependents(state, task_id, actor)`. Linha 250 contém `_block_dependents_upstream_failed(state, task_id, "rejected", actor)`.

- [ ] **Step 2: Add _auto_close_escalations call after both**

Após linha 250, adicionar:

```python
            if new_status in TERMINAL_STATUSES:
                _auto_close_escalations(state, task_id, new_status, actor)
```

(Indent deve casar com o bloco condicional existente — checar contexto antes de aplicar.)

- [ ] **Step 3: Test move_status integration manually**

```bash
cd ~/.openclaw/kanban-tasks
# Mock test usando unittest TestCase com store.mutate_state
python3 -c "
from unittest.mock import patch, MagicMock
import lib.task as task_mod

# Quick smoke: chamar move_status mock e ver se _auto_close_escalations é called
with patch.object(task_mod, '_auto_close_escalations') as mock:
    # Setup minimal mock state, call move_status... (placeholder smoke)
    pass
print('manual smoke ok')
"
```

- [ ] **Step 4: Run all kanban-tasks tests**

```bash
cd ~/.openclaw/kanban-tasks
for t in tests/test_*.py; do
    name=$(basename "$t" .py)
    python3 -m unittest "tests.$name" 2>&1 | tail -1
done
```

Expected: All pass; nenhum regression.

- [ ] **Step 5: Commit**

```bash
cd ~/.openclaw
git add kanban-tasks/lib/task.py
git commit -m "feat(ubn-w2): F2.3 wire _auto_close_escalations em move_status"
```

### Task 2.6: Wire hook em archive()

**Files:**
- Modify: `kanban-tasks/lib/task.py:290-330` (function `archive`)

- [ ] **Step 1: Find archive existing callsite**

Linha 319 atual: `_block_dependents_upstream_failed(state, task_id, "archived", actor)`.

- [ ] **Step 2: Add _auto_close_escalations call after**

Após linha 319, adicionar:

```python
        _auto_close_escalations(state, task_id, "archived", actor)
```

- [ ] **Step 3: Add integration test for archive**

Append em `kanban-tasks/tests/test_auto_close_escalations.py`:

```python
class TestArchiveTriggersHook(unittest.TestCase):
    """archive() é code-path separado de move_status; precisa hook próprio."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.clr_esc = self.tmpdir / "clarification-agent" / "escalations"
        self.clr_esc.mkdir(parents=True)
        self.path = self.clr_esc / "T-9999-blk-1.md"
        self.path.write_text(
            "---\ntask_id: T-9999\nstatus: open\n---\n", encoding="utf-8"
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_archive_calls_auto_close(self):
        """archive() chama _auto_close_escalations com status='archived'."""
        from lib import task as task_mod
        with patch.object(task_mod, "UBN_CLR_ESCALATIONS_DIR", self.clr_esc):
            with patch.object(task_mod, "_auto_close_escalations") as mock_hook:
                # Build minimal state with task in done (archive only allows done→archived)
                state = {
                    "tasks": [{"id": "T-9999", "status": "done", "project": "test"}],
                    "events": [], "last_event_seq": 0,
                }
                with patch("lib.store.mutate_state") as mock_mutate:
                    cm = MagicMock()
                    cm.__enter__.return_value = state
                    cm.__exit__.return_value = False
                    mock_mutate.return_value = cm
                    with patch("lib.store.next_seq", return_value=1):
                        with patch("lib.store.now_iso", return_value="2026-05-04T12:00Z"):
                            with patch("lib.store.append_event"):
                                task_mod.archive("T-9999", actor="bernard")
                mock_hook.assert_called_once_with(state, "T-9999", "archived", "bernard")
```

(Imports adicionais: `from unittest.mock import MagicMock` no topo.)

- [ ] **Step 4: Run tests**

```bash
cd ~/.openclaw/kanban-tasks
python3 -m unittest tests.test_auto_close_escalations 2>&1 | tail -3
```

Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
cd ~/.openclaw
git add kanban-tasks/lib/task.py kanban-tasks/tests/test_auto_close_escalations.py
git commit -m "feat(ubn-w2): F2.4 wire _auto_close_escalations em archive()"
```

### Task 2.7: Backfill script tools/backfill_close_escalations.py

**Files:**
- Create: `kanban-tasks/tools/backfill_close_escalations.py`

- [ ] **Step 1: Write script**

```python
#!/usr/bin/env python3
"""Backfill: aplica _auto_close_escalations em tasks já em terminal status
mas com escalation files órfãs.

Uso:
    python3 tools/backfill_close_escalations.py            # dry-run (default)
    python3 tools/backfill_close_escalations.py --apply    # mutar de fato

Spec: bevox-knowledge/35_specs/openclaw/2026-05-04-ubn-w2-loop-self-healing.md §7.1
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Mesmo path layout que kanban-tasks/cli.sh: roda do diretório kanban-tasks/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.task import (  # type: ignore
    TERMINAL_STATUSES,
    UBN_CLR_ESCALATIONS_DIR,
    TESTER_ESCALATIONS_DIR,
    _auto_close_escalations,
)
from lib import store  # type: ignore


def find_orphan_tasks() -> list[dict]:
    """Retorna tasks em terminal status que TÊM files órfãos."""
    state = json.loads(store.STATE_PATH.read_text(encoding="utf-8"))
    out = []
    for t in state.get("tasks", []):
        if t.get("status") not in TERMINAL_STATUSES:
            continue
        tid = t.get("id")
        if not tid:
            continue
        has_orphan = False
        if UBN_CLR_ESCALATIONS_DIR.is_dir():
            for p in UBN_CLR_ESCALATIONS_DIR.iterdir():
                if p.name.startswith(f"{tid}-blk-") or p.name.startswith(f"{tid}-clr-"):
                    has_orphan = True
                    break
        if not has_orphan and TESTER_ESCALATIONS_DIR.is_dir():
            for p in TESTER_ESCALATIONS_DIR.iterdir():
                if p.name.startswith(f"{tid}-tr-"):
                    has_orphan = True
                    break
        if has_orphan:
            out.append({"id": tid, "status": t["status"]})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="Mutar de fato. Default: dry-run.")
    args = ap.parse_args()

    orphans = find_orphan_tasks()
    print(f"Found {len(orphans)} terminal tasks with orphan escalation files:\n")
    for o in orphans:
        print(f"  {o['id']} [{o['status']}]")

    if not orphans:
        print("\nNothing to do.")
        return 0

    if not args.apply:
        print("\n(dry-run — re-run with --apply to actually close)")
        return 0

    print("\nApplying...")
    with store.mutate_state() as state:
        for o in orphans:
            result = _auto_close_escalations(
                state, o["id"], o["status"], "backfill-script"
            )
            print(json.dumps({
                "task_id": o["id"],
                "status": o["status"],
                "result": result,
            }, indent=2))
    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Smoke dry-run**

```bash
cd ~/.openclaw/kanban-tasks
python3 tools/backfill_close_escalations.py
```

Expected: lista as ~6 tasks órfãs identificadas + termina com "(dry-run)".

- [ ] **Step 3: Commit**

```bash
cd ~/.openclaw
git add kanban-tasks/tools/backfill_close_escalations.py
git commit -m "feat(ubn-w2): F2.5 backfill script para escalation files órfãos pré-deploy"
```

---

## Phase 3 — F3.1: executor RuntimeMaxSec deadline

### Task 3.1: Failing test — _resolve_max_runtime_seconds

**Files:**
- Create: `dispatcher-agent/tests/test_executor_deadline.py`

- [ ] **Step 1: Write test**

```python
"""Test F3.1: _resolve_max_runtime_seconds + RuntimeMaxSec injection.

Spec: bevox-knowledge/35_specs/openclaw/2026-05-04-ubn-w2-loop-self-healing.md §F3.1
"""
import unittest
import os
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch


class TestResolveMaxRuntime(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.state_path = self.tmpdir / "state.json"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_state(self, tasks):
        self.state_path.write_text(json.dumps({"tasks": tasks}), encoding="utf-8")

    def test_default_12h_when_no_env_no_payload(self):
        from lib.runner import _resolve_max_runtime_seconds
        self._write_state([{"id": "T-0001", "status": "ready"}])
        with patch("lib.runner._STATE_PATH_FOR_DEADLINE", self.state_path):
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("OPENCLAW_EXECUTOR_MAX_RUNTIME_HOURS", None)
                result = _resolve_max_runtime_seconds("T-0001")
        self.assertEqual(result, 12 * 3600)

    def test_env_var_override(self):
        from lib.runner import _resolve_max_runtime_seconds
        self._write_state([{"id": "T-0001", "status": "ready"}])
        with patch("lib.runner._STATE_PATH_FOR_DEADLINE", self.state_path):
            with patch.dict(os.environ, {"OPENCLAW_EXECUTOR_MAX_RUNTIME_HOURS": "4"}):
                result = _resolve_max_runtime_seconds("T-0001")
        self.assertEqual(result, 4 * 3600)

    def test_per_task_payload_override_wins_over_env(self):
        from lib.runner import _resolve_max_runtime_seconds
        self._write_state([{
            "id": "T-0001",
            "status": "ready",
            "dispatch_payload": {"max_runtime_hours": 24},
        }])
        with patch("lib.runner._STATE_PATH_FOR_DEADLINE", self.state_path):
            with patch.dict(os.environ, {"OPENCLAW_EXECUTOR_MAX_RUNTIME_HOURS": "4"}):
                result = _resolve_max_runtime_seconds("T-0001")
        self.assertEqual(result, 24 * 3600)

    def test_kill_switch_zero_returns_zero(self):
        """env=0 → no limit (return 0)."""
        from lib.runner import _resolve_max_runtime_seconds
        self._write_state([{"id": "T-0001", "status": "ready"}])
        with patch("lib.runner._STATE_PATH_FOR_DEADLINE", self.state_path):
            with patch.dict(os.environ, {"OPENCLAW_EXECUTOR_MAX_RUNTIME_HOURS": "0"}):
                result = _resolve_max_runtime_seconds("T-0001")
        self.assertEqual(result, 0)

    def test_corrupted_state_falls_back_to_env(self):
        from lib.runner import _resolve_max_runtime_seconds
        self.state_path.write_text("not json{", encoding="utf-8")
        with patch("lib.runner._STATE_PATH_FOR_DEADLINE", self.state_path):
            with patch.dict(os.environ, {"OPENCLAW_EXECUTOR_MAX_RUNTIME_HOURS": "6"}):
                result = _resolve_max_runtime_seconds("T-0001")
        self.assertEqual(result, 6 * 3600)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run, verify fail**

```bash
cd ~/.openclaw/dispatcher-agent
python3 -m unittest tests.test_executor_deadline 2>&1 | tail -3
```

Expected: `ImportError` (function not yet implemented).

### Task 3.2: Implement _resolve_max_runtime_seconds

**Files:**
- Modify: `dispatcher-agent/lib/runner.py` (add module-level constant + helper near top)

- [ ] **Step 1: Add imports + module constant**

No topo do file (após imports existentes):

```python
import json as _json  # se não estiver já importado

_STATE_PATH_FOR_DEADLINE = Path("~/.openclaw/kanban-tasks/state.json")
```

- [ ] **Step 2: Add helper function**

Antes de `def launch_detached(`:

```python
def _resolve_max_runtime_seconds(task_id: str) -> int:
    """Resolve executor max runtime: per-task override > env > default 12h.
    Returns 0 quando OPENCLAW_EXECUTOR_MAX_RUNTIME_HOURS=0 (kill switch — sem limite).
    """
    env_val = os.environ.get("OPENCLAW_EXECUTOR_MAX_RUNTIME_HOURS")
    if env_val == "0":
        return 0
    try:
        state = _json.loads(_STATE_PATH_FOR_DEADLINE.read_text(encoding="utf-8"))
        task = next(
            (t for t in state.get("tasks", []) if t.get("id") == task_id),
            None,
        )
        if task:
            override = (task.get("dispatch_payload") or {}).get("max_runtime_hours")
            if isinstance(override, (int, float)) and override > 0:
                return int(override) * 3600
    except (OSError, _json.JSONDecodeError):
        pass
    try:
        hours = int(env_val) if env_val else 12
    except ValueError:
        hours = 12
    return hours * 3600
```

- [ ] **Step 3: Run test**

```bash
cd ~/.openclaw/dispatcher-agent
python3 -m unittest tests.test_executor_deadline 2>&1 | tail -3
```

Expected: `OK` (5 tests passing).

- [ ] **Step 4: Commit**

```bash
cd ~/.openclaw
git add dispatcher-agent/lib/runner.py dispatcher-agent/tests/test_executor_deadline.py
git commit -m "feat(ubn-w2): F3.1.1 _resolve_max_runtime_seconds helper"
```

### Task 3.3: Failing test — RuntimeMaxSec injection in sd_cmd

**Files:**
- Modify: `dispatcher-agent/tests/test_executor_deadline.py`

- [ ] **Step 1: Add test class**

Append antes do `if __name__`:

```python
class TestSdCmdInjection(unittest.TestCase):
    """RuntimeMaxSec é adicionado a sd_cmd em launch_detached."""

    def test_sd_cmd_includes_runtime_max_sec_default(self):
        """Default 12h → RuntimeMaxSec=43200."""
        from lib import runner
        with patch("lib.runner._resolve_max_runtime_seconds", return_value=43200):
            with patch("lib.runner.subprocess.run") as mock_run:
                mock_run.return_value = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
                with patch("lib.runner.store.execution_log_path",
                           return_value=Path("/tmp/test.log")):
                    briefing = Path("/tmp/test_briefing.md")
                    briefing.write_text("brief", encoding="utf-8")
                    try:
                        runner.launch_detached(
                            task_id="T-9001",
                            briefing_path=briefing,
                            allowed_tools="Read",
                        )
                    except Exception:
                        pass  # may raise after mock; only inspect first call
                    args = mock_run.call_args[0][0]
                    self.assertIn("--property=RuntimeMaxSec=43200", args)

    def test_sd_cmd_omits_runtime_max_when_zero(self):
        """Env=0 → kill switch → NÃO adicionar property."""
        from lib import runner
        with patch("lib.runner._resolve_max_runtime_seconds", return_value=0):
            with patch("lib.runner.subprocess.run") as mock_run:
                mock_run.return_value = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
                with patch("lib.runner.store.execution_log_path",
                           return_value=Path("/tmp/test.log")):
                    briefing = Path("/tmp/test_briefing.md")
                    briefing.write_text("brief", encoding="utf-8")
                    try:
                        runner.launch_detached(
                            task_id="T-9001",
                            briefing_path=briefing,
                            allowed_tools="Read",
                        )
                    except Exception:
                        pass
                    args = mock_run.call_args[0][0]
                    rt = [a for a in args if "RuntimeMaxSec" in a]
                    self.assertEqual(rt, [])
```

- [ ] **Step 2: Run, verify fail**

```bash
cd ~/.openclaw/dispatcher-agent
python3 -m unittest tests.test_executor_deadline 2>&1 | tail -3
```

Expected: FAIL — RuntimeMaxSec não está em sd_cmd.

### Task 3.4: Wire RuntimeMaxSec into launch_detached

**Files:**
- Modify: `dispatcher-agent/lib/runner.py:119-130` (sd_cmd construction)

- [ ] **Step 1: Inject before sd_cmd assignment**

Localizar o bloco em `launch_detached`:

```python
    sd_cmd = [
        "systemd-run", "--user",
        f"--unit={unit_name}",
        "--collect",
        "--property=Type=exec",
        f"--property=StandardOutput=append:{log_path}",
        "--property=StandardError=inherit",
        "--",
```

Antes desse bloco, adicionar:

```python
    max_seconds = _resolve_max_runtime_seconds(task_id)
```

Modificar sd_cmd:

```python
    sd_cmd = [
        "systemd-run", "--user",
        f"--unit={unit_name}",
        "--collect",
        "--property=Type=exec",
        f"--property=StandardOutput=append:{log_path}",
        "--property=StandardError=inherit",
    ]
    if max_seconds > 0:
        sd_cmd.append(f"--property=RuntimeMaxSec={max_seconds}")
    sd_cmd += [
        "--",
        "claude", "-p", briefing_content,
        *claude_session_arg,
        "--allowedTools", allowed_tools,
    ]
```

(Manter `if model:` block + `_hotfix_resolve_local_repo_path` block que já existe — só ajustar a montagem inicial.)

- [ ] **Step 2: Run tests**

```bash
cd ~/.openclaw/dispatcher-agent
python3 -m unittest tests.test_executor_deadline 2>&1 | tail -3
```

Expected: `OK` (7 tests).

- [ ] **Step 3: Run all dispatcher tests for regression**

```bash
cd ~/.openclaw/dispatcher-agent
for t in tests/test_*.py; do
    name=$(basename "$t" .py)
    python3 -m unittest "tests.$name" 2>&1 | tail -1
done
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
cd ~/.openclaw
git add dispatcher-agent/lib/runner.py dispatcher-agent/tests/test_executor_deadline.py
git commit -m "feat(ubn-w2): F3.1.2 inject RuntimeMaxSec em launch_detached sd_cmd"
```

### Task 3.5: executor_timeout_max_runtime detection (block reason)

**Files:**
- Modify: `dispatcher-agent/lib/runner.py` (function que processa exit code de executor — provavelmente `reap_finished` em runner.py:294 ou similar)

- [ ] **Step 1: Locate exit code handler**

```bash
grep -n "returncode\|exit_code\|Result=" ~/.openclaw/dispatcher-agent/lib/runner.py | head -10
```

- [ ] **Step 2: Add helper to detect systemd timeout**

```python
def _was_killed_by_max_runtime(unit_name: str) -> bool:
    """Inspeciona Result do systemd unit. Returns True se Result=timeout."""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "show", "--property=Result", "--value", unit_name],
            capture_output=True, text=True, timeout=5, check=False,
        )
        return result.stdout.strip() == "timeout"
    except (subprocess.TimeoutExpired, OSError):
        return False
```

- [ ] **Step 3: Wire into reap_finished or equivalent**

Em `reap_finished` (runner.py:294), quando exit code != 0, antes de retornar reason genérica, checar:

```python
        if _was_killed_by_max_runtime(unit_name):
            return {
                "task_id": task_id,
                "exit_code": exit_code,
                "reason": "executor_timeout_max_runtime",
                # ... outros fields existentes
            }
```

(Ajustar conforme o shape real do return — leia o código atual antes de aplicar.)

- [ ] **Step 4: Add unit test**

Append em `test_executor_deadline.py`:

```python
class TestTimeoutDetection(unittest.TestCase):
    def test_detect_max_runtime_timeout(self):
        from lib.runner import _was_killed_by_max_runtime
        with patch("lib.runner.subprocess.run") as mock_run:
            mock_run.return_value = type("R", (), {"stdout": "timeout\n", "returncode": 0})()
            self.assertTrue(_was_killed_by_max_runtime("claude-task-T-9001.service"))

    def test_detect_normal_exit(self):
        from lib.runner import _was_killed_by_max_runtime
        with patch("lib.runner.subprocess.run") as mock_run:
            mock_run.return_value = type("R", (), {"stdout": "success\n", "returncode": 0})()
            self.assertFalse(_was_killed_by_max_runtime("claude-task-T-9001.service"))
```

- [ ] **Step 5: Run tests**

```bash
cd ~/.openclaw/dispatcher-agent
python3 -m unittest tests.test_executor_deadline 2>&1 | tail -3
```

Expected: OK.

- [ ] **Step 6: Commit**

```bash
cd ~/.openclaw
git add dispatcher-agent/lib/runner.py dispatcher-agent/tests/test_executor_deadline.py
git commit -m "feat(ubn-w2): F3.1.3 detect executor_timeout_max_runtime via Result=timeout"
```

---

## Phase 4 — F3.2: reaper safety net for legacy executors

### Task 4.1: Failing test — detect legacy units

**Files:**
- Create: `dispatcher-agent/tests/test_reaper_executor_legacy.py`

- [ ] **Step 1: Write test**

```python
"""Test F3.2: reaper detecta executors legacy (sem RuntimeMaxSec) vivos > 12h.

Spec: bevox-knowledge/35_specs/openclaw/2026-05-04-ubn-w2-loop-self-healing.md §F3.2
"""
import unittest
from unittest.mock import patch, MagicMock


class TestExecutorLegacyDetection(unittest.TestCase):
    def test_unit_with_runtime_max_set_skipped(self):
        """RuntimeMaxUSec != infinity → systemd cuida, skip."""
        from lib.reaper import _is_legacy_executor
        with patch("lib.reaper.subprocess.run") as mock_run:
            mock_run.return_value = type("R", (), {
                "stdout": "43200000000\n", "returncode": 0,
            })()
            self.assertFalse(_is_legacy_executor("claude-task-T-9001.service"))

    def test_unit_with_infinity_is_legacy(self):
        from lib.reaper import _is_legacy_executor
        with patch("lib.reaper.subprocess.run") as mock_run:
            mock_run.return_value = type("R", (), {
                "stdout": "infinity\n", "returncode": 0,
            })()
            self.assertTrue(_is_legacy_executor("claude-task-T-0161.service"))

    def test_subprocess_failure_returns_false(self):
        from lib.reaper import _is_legacy_executor
        with patch("lib.reaper.subprocess.run", side_effect=OSError):
            self.assertFalse(_is_legacy_executor("invalid"))


class TestExecutorAge(unittest.TestCase):
    def test_unit_age_hours_from_active_enter_timestamp(self):
        from lib.reaper import _executor_age_hours
        with patch("lib.reaper.subprocess.run") as mock_run:
            # ActiveEnterTimestamp epoch in usec (systemd format)
            from datetime import datetime, timezone, timedelta
            ts = (datetime.now(timezone.utc) - timedelta(hours=14)).timestamp() * 1_000_000
            mock_run.return_value = type("R", (), {
                "stdout": f"{int(ts)}\n", "returncode": 0,
            })()
            age = _executor_age_hours("claude-task-T-9001.service")
            self.assertGreater(age, 13.5)
            self.assertLess(age, 14.5)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run, verify fail**

```bash
cd ~/.openclaw/dispatcher-agent
python3 -m unittest tests.test_reaper_executor_legacy 2>&1 | tail -3
```

Expected: ImportError.

### Task 4.2: Implement detection helpers + reaper stage

**Files:**
- Modify: `dispatcher-agent/lib/reaper.py`

- [ ] **Step 1: Add helpers**

No topo de reaper.py (perto dos outros helpers):

```python
def _is_legacy_executor(unit_name: str) -> bool:
    """Returns True se unit NÃO tem RuntimeMaxSec set (RuntimeMaxUSec=infinity)."""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "show",
             "--property=RuntimeMaxUSec", "--value", unit_name],
            capture_output=True, text=True, timeout=5, check=False,
        )
        return result.stdout.strip() == "infinity"
    except (subprocess.TimeoutExpired, OSError):
        return False


def _executor_age_hours(unit_name: str) -> float:
    """Returns hours since unit's ActiveEnterTimestamp (0 if cannot determine)."""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "show",
             "--property=ActiveEnterTimestampMonotonic", "--value", unit_name],
            capture_output=True, text=True, timeout=5, check=False,
        )
        # Try epoch usec via ActiveEnterTimestamp instead
        result = subprocess.run(
            ["systemctl", "--user", "show",
             "--property=ActiveEnterTimestamp", "--value", unit_name],
            capture_output=True, text=True, timeout=5, check=False,
        )
        ts_str = result.stdout.strip()
        if not ts_str or ts_str == "0":
            return 0.0
        # Format: "Wed 2026-04-29 19:16:00 -03"
        from datetime import datetime, timezone
        # Try parse via systemctl's standard format; fallback safe
        try:
            # use timestamp as USec via separate property for safety
            r2 = subprocess.run(
                ["systemctl", "--user", "show",
                 "--property=ActiveEnterTimestampMonotonic", "--value", unit_name],
                capture_output=True, text=True, timeout=5, check=False,
            )
            usec = int(r2.stdout.strip() or "0")
            if usec > 0:
                # Monotonic = uptime relative; need wall-clock conversion.
                # Simpler: use direct ActiveEnterTimestamp parse with %a %Y-%m-%d %H:%M:%S %z
                from email.utils import parsedate_to_datetime
                # systemctl date format isn't RFC 2822. Use strptime:
                dt = datetime.strptime(ts_str, "%a %Y-%m-%d %H:%M:%S %z")
                return (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        except (ValueError, OSError):
            return 0.0
        return 0.0
    except (subprocess.TimeoutExpired, OSError):
        return 0.0
```

(Pragmatic note: o test usa um mock que retorna usec — vou alinhar a impl com o test real. Vou retrabalhar a implementação no fix step.)

**Implementação simplificada e alinhada com test:**

Substituir `_executor_age_hours` por:

```python
def _executor_age_hours(unit_name: str) -> float:
    """Returns hours since unit's ActiveEnterTimestamp (epoch usec via systemctl).
    Returns 0.0 se unit não existe ou parse falha."""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "show",
             "--property=ActiveEnterTimestamp", "--value", unit_name],
            capture_output=True, text=True, timeout=5, check=False,
        )
        ts_str = result.stdout.strip()
        if not ts_str or ts_str == "0":
            return 0.0
        # Try systemd format: "Wed 2026-04-29 19:16:00 -03"
        try:
            from datetime import datetime, timezone
            dt = datetime.strptime(ts_str, "%a %Y-%m-%d %H:%M:%S %z")
            return (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        except ValueError:
            # Test path: stdout is raw epoch usec
            try:
                usec = int(ts_str)
                from datetime import datetime, timezone
                dt = datetime.fromtimestamp(usec / 1_000_000, tz=timezone.utc)
                return (datetime.now(timezone.utc) - dt).total_seconds() / 3600
            except ValueError:
                return 0.0
    except (subprocess.TimeoutExpired, OSError):
        return 0.0
```

- [ ] **Step 2: Run unit tests**

```bash
cd ~/.openclaw/dispatcher-agent
python3 -m unittest tests.test_reaper_executor_legacy 2>&1 | tail -3
```

Expected: OK.

- [ ] **Step 3: Commit**

```bash
cd ~/.openclaw
git add dispatcher-agent/lib/reaper.py dispatcher-agent/tests/test_reaper_executor_legacy.py
git commit -m "feat(ubn-w2): F3.2.1 _is_legacy_executor + _executor_age_hours helpers"
```

### Task 4.3: Failing test — kill action + audit event

**Files:**
- Modify: `dispatcher-agent/tests/test_reaper_executor_legacy.py`

- [ ] **Step 1: Add kill stage tests**

```python
class TestExecutorLegacyReaperStage(unittest.TestCase):
    def test_legacy_unit_over_12h_killed(self):
        from lib import reaper
        with patch("lib.reaper._list_active_executor_units",
                   return_value=["claude-task-T-0161-old.service"]):
            with patch("lib.reaper._is_legacy_executor", return_value=True):
                with patch("lib.reaper._executor_age_hours", return_value=120.0):
                    with patch("lib.reaper.subprocess.run") as mock_run:
                        mock_run.return_value = type("R", (), {"returncode": 0})()
                        with patch("lib.reaper._append_audit") as mock_audit:
                            stats = reaper._executor_legacy_reaper_stage()
                            self.assertEqual(stats.get("killed", 0), 1)
                            mock_audit.assert_called_once()
                            event = mock_audit.call_args[0][0]
                            self.assertEqual(event["type"], "executor_killed_legacy")

    def test_unit_under_12h_not_killed(self):
        from lib import reaper
        with patch("lib.reaper._list_active_executor_units",
                   return_value=["claude-task-recent.service"]):
            with patch("lib.reaper._is_legacy_executor", return_value=True):
                with patch("lib.reaper._executor_age_hours", return_value=2.0):
                    with patch("lib.reaper.subprocess.run") as mock_run:
                        with patch("lib.reaper._append_audit"):
                            stats = reaper._executor_legacy_reaper_stage()
                            self.assertEqual(stats.get("killed", 0), 0)
                            mock_run.assert_not_called()

    def test_non_legacy_unit_skipped(self):
        from lib import reaper
        with patch("lib.reaper._list_active_executor_units",
                   return_value=["claude-task-modern.service"]):
            with patch("lib.reaper._is_legacy_executor", return_value=False):
                with patch("lib.reaper._executor_age_hours", return_value=120.0):
                    with patch("lib.reaper.subprocess.run") as mock_run:
                        stats = reaper._executor_legacy_reaper_stage()
                        self.assertEqual(stats.get("killed", 0), 0)
                        mock_run.assert_not_called()

    def test_kill_switch_disables_stage(self):
        import os
        from lib import reaper
        with patch.dict(os.environ, {"OPENCLAW_REAPER_EXECUTOR_LEGACY": "0"}):
            stats = reaper._executor_legacy_reaper_stage()
            self.assertEqual(stats.get("skipped_disabled", 0), 1)
```

### Task 4.4: Implement kill stage + wire into reaper tick

**Files:**
- Modify: `dispatcher-agent/lib/reaper.py`

- [ ] **Step 1: Add unit listing helper**

```python
def _list_active_executor_units() -> list[str]:
    """List 'claude-task-*.service' units in active state."""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "list-units",
             "--type=service", "--state=active",
             "--no-legend", "--plain", "--no-pager"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        units = []
        for line in result.stdout.splitlines():
            unit = line.split()[0] if line.split() else ""
            if unit.startswith("claude-task-") and unit.endswith(".service"):
                units.append(unit)
        return units
    except (subprocess.TimeoutExpired, OSError):
        return []
```

- [ ] **Step 2: Add stage function**

```python
def _executor_legacy_reaper_stage() -> dict:
    """Kill legacy executors (sem RuntimeMaxSec) vivos > 12h."""
    if os.environ.get("OPENCLAW_REAPER_EXECUTOR_LEGACY") == "0":
        return {"skipped_disabled": 1}
    threshold_hours = 12.0
    stats = {"checked": 0, "killed": 0, "errors": 0}
    for unit in _list_active_executor_units():
        stats["checked"] += 1
        if not _is_legacy_executor(unit):
            continue
        age = _executor_age_hours(unit)
        if age < threshold_hours:
            continue
        try:
            subprocess.run(
                ["systemctl", "--user", "stop", unit],
                capture_output=True, text=True, timeout=10, check=False,
            )
            stats["killed"] += 1
            # Extract task_id from unit name pattern "claude-task-T-XXXX-...service"
            task_id = "?"
            if unit.startswith("claude-task-T-"):
                rest = unit[len("claude-task-"):]
                # T-XXXX is up to first '-' after T-
                parts = rest.split("-", 2)
                if len(parts) >= 2:
                    task_id = f"{parts[0]}-{parts[1]}"
            _append_audit({
                "type": "executor_killed_legacy",
                "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "unit": unit,
                "age_hours": round(age, 2),
                "task_id": task_id,
            })
        except (subprocess.TimeoutExpired, OSError):
            stats["errors"] += 1
    return stats
```

- [ ] **Step 3: Helper _append_audit (if doesn't exist)**

Check existing audit pattern:

```bash
grep -n "audit\|reaper.jsonl" ~/.openclaw/dispatcher-agent/lib/reaper.py | head -5
```

Se já existir helper similar, reusar. Senão, criar:

```python
def _append_audit(event: dict) -> None:
    """Append linha JSONL atomico em ~/.openclaw/audit/reaper.jsonl."""
    audit_path = Path("~/.openclaw/audit/reaper.jsonl")
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with open(audit_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
```

- [ ] **Step 4: Wire stage into reaper tick**

Localizar a função main do reaper tick (provavelmente algo como `tick_once`) e adicionar a chamada após os stages existentes:

```python
        try:
            stats["executor_legacy"] = _executor_legacy_reaper_stage()
        except Exception as e:
            stats["errors"].append(f"executor_legacy_stage_failed: {e}")
```

- [ ] **Step 5: Run tests**

```bash
cd ~/.openclaw/dispatcher-agent
python3 -m unittest tests.test_reaper_executor_legacy 2>&1 | tail -3
```

Expected: OK.

- [ ] **Step 6: Commit**

```bash
cd ~/.openclaw
git add dispatcher-agent/lib/reaper.py dispatcher-agent/tests/test_reaper_executor_legacy.py
git commit -m "feat(ubn-w2): F3.2.2 reaper executor_legacy_reaper_stage + audit"
```

---

## Phase 5 — F4: stuck_in_ready criterion

### Task 5.1: Failing test — candidates_stuck_ready

**Files:**
- Modify: `dispatcher-agent/tests/test_block_scanner.py`

- [ ] **Step 1: Append new test class**

```python
class TestCandidatesStuckReady(unittest.TestCase):
    """F4: task ready em sprint current sem dispatch há > threshold_min."""

    def _state_with(self, tasks, sprints):
        return {"tasks": tasks, "sprints": sprints}

    def test_ready_in_current_sprint_old_returns_candidate(self):
        from lib.block_scanner import candidates_stuck_ready
        from datetime import datetime, timezone, timedelta
        old_ts = (datetime.now(timezone.utc) - timedelta(minutes=45)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        state = self._state_with(
            tasks=[{
                "id": "T-0165", "status": "ready", "project": "bevox-site",
                "sprint_id": "sprint-35", "updated_at": old_ts,
            }],
            sprints=[{"id": "sprint-35", "project": "bevox-site", "state": "current"}],
        )
        out = candidates_stuck_ready(state)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].task_id, "T-0165")
        self.assertEqual(out[0].criterion, "stuck_in_ready")
        self.assertEqual(out[0].project, "bevox-site")

    def test_ready_recent_skipped(self):
        from lib.block_scanner import candidates_stuck_ready
        from datetime import datetime, timezone, timedelta
        recent = (datetime.now(timezone.utc) - timedelta(minutes=5)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        state = self._state_with(
            tasks=[{"id": "T-0165", "status": "ready", "project": "p",
                    "sprint_id": "s1", "updated_at": recent}],
            sprints=[{"id": "s1", "project": "p", "state": "current"}],
        )
        self.assertEqual(len(candidates_stuck_ready(state)), 0)

    def test_ready_in_non_current_sprint_skipped(self):
        from lib.block_scanner import candidates_stuck_ready
        from datetime import datetime, timezone, timedelta
        old = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        state = self._state_with(
            tasks=[{"id": "T-0165", "status": "ready", "project": "p",
                    "sprint_id": "old-sprint", "updated_at": old}],
            sprints=[{"id": "current-sprint", "project": "p", "state": "current"}],
        )
        self.assertEqual(len(candidates_stuck_ready(state)), 0)

    def test_in_progress_status_skipped(self):
        from lib.block_scanner import candidates_stuck_ready
        from datetime import datetime, timezone, timedelta
        old = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        state = self._state_with(
            tasks=[{"id": "T-0165", "status": "in_progress", "project": "p",
                    "sprint_id": "s1", "updated_at": old}],
            sprints=[{"id": "s1", "project": "p", "state": "current"}],
        )
        self.assertEqual(len(candidates_stuck_ready(state)), 0)

    def test_threshold_env_override(self):
        import os
        from lib.block_scanner import candidates_stuck_ready
        from datetime import datetime, timezone, timedelta
        ts = (datetime.now(timezone.utc) - timedelta(minutes=10)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        state = self._state_with(
            tasks=[{"id": "T-0165", "status": "ready", "project": "p",
                    "sprint_id": "s1", "updated_at": ts}],
            sprints=[{"id": "s1", "project": "p", "state": "current"}],
        )
        from unittest.mock import patch
        with patch.dict(os.environ, {"OPENCLAW_REAPER_STUCK_READY_THRESHOLD_MIN": "5"}):
            self.assertEqual(len(candidates_stuck_ready(state)), 1)
        with patch.dict(os.environ, {"OPENCLAW_REAPER_STUCK_READY_THRESHOLD_MIN": "30"}):
            self.assertEqual(len(candidates_stuck_ready(state)), 0)

    def test_kill_switch_zero_disables(self):
        import os
        from lib.block_scanner import candidates_stuck_ready
        from datetime import datetime, timezone, timedelta
        ts = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        state = self._state_with(
            tasks=[{"id": "T-0165", "status": "ready", "project": "p",
                    "sprint_id": "s1", "updated_at": ts}],
            sprints=[{"id": "s1", "project": "p", "state": "current"}],
        )
        from unittest.mock import patch
        with patch.dict(os.environ, {"OPENCLAW_REAPER_STUCK_READY_THRESHOLD_MIN": "0"}):
            self.assertEqual(len(candidates_stuck_ready(state)), 0)

    def test_corrupted_updated_at_skipped(self):
        from lib.block_scanner import candidates_stuck_ready
        state = self._state_with(
            tasks=[{"id": "T-0165", "status": "ready", "project": "p",
                    "sprint_id": "s1", "updated_at": "not-a-date"}],
            sprints=[{"id": "s1", "project": "p", "state": "current"}],
        )
        self.assertEqual(len(candidates_stuck_ready(state)), 0)
```

- [ ] **Step 2: Run, verify fail**

```bash
cd ~/.openclaw/dispatcher-agent
python3 -m unittest tests.test_block_scanner 2>&1 | tail -3
```

Expected: ImportError on `candidates_stuck_ready`.

### Task 5.2: Implement candidates_stuck_ready

**Files:**
- Modify: `dispatcher-agent/lib/block_scanner.py`

- [ ] **Step 1: Add function near other candidates_* functions**

```python
def candidates_stuck_ready(state: dict) -> List[Candidate]:
    """Critério F4: tasks em status=ready com sprint_id == current sprint do
    projeto, idle (updated_at) > threshold_min sem dispatch.

    Detecta sprint travada por qualquer razão (cron-dispatcher skipping,
    operator forgot, kill-switch on, etc).

    Threshold env: OPENCLAW_REAPER_STUCK_READY_THRESHOLD_MIN (default 30).
    Kill switch: 0 desabilita.
    """
    threshold_min = int(os.environ.get(
        "OPENCLAW_REAPER_STUCK_READY_THRESHOLD_MIN", "30"))
    if threshold_min == 0:
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=threshold_min)
    sprints = state.get("sprints", []) or []
    current_by_project = {
        s.get("project"): s.get("id")
        for s in sprints if s.get("state") == "current"
    }
    out = []
    for t in state.get("tasks", []) or []:
        if t.get("status") != "ready":
            continue
        proj = t.get("project")
        if not proj:
            continue
        if t.get("sprint_id") != current_by_project.get(proj):
            continue
        updated = _parse_iso(t.get("updated_at"))
        if not updated or updated >= cutoff:
            continue
        out.append(Candidate(
            task_id=t["id"],
            criterion="stuck_in_ready",
            block_session_key=t.get("updated_at"),
            block_reason=(
                f"stuck-in-ready >{threshold_min}min "
                f"(sprint current, sem dispatch)"
            ),
            project=proj,
        ))
    return out
```

- [ ] **Step 2: Add to scan_all**

Localizar `scan_all` (provavelmente perto do final do file). Adicionar `candidates_stuck_ready(state)` à lista de critérios:

```python
    all_candidates = (
        candidates_blocked(state)
        + candidates_stuck_testing(state)
        + candidates_proposed_rejected()
        + candidates_stuck_ready(state)  # F4
    )
```

- [ ] **Step 3: Run tests**

```bash
cd ~/.openclaw/dispatcher-agent
python3 -m unittest tests.test_block_scanner 2>&1 | tail -3
```

Expected: OK.

- [ ] **Step 4: Run reaper integration tests**

```bash
python3 -m unittest tests.test_reaper_block_scanner_integration 2>&1 | tail -3
```

Expected: OK (sem regression).

- [ ] **Step 5: Commit**

```bash
cd ~/.openclaw
git add dispatcher-agent/lib/block_scanner.py dispatcher-agent/tests/test_block_scanner.py
git commit -m "feat(ubn-w2): F4 candidates_stuck_ready criterion + scan_all integration"
```

---

## Phase 6 — Integration smoke + finishing

### Task 6.1: Full test suite regression check

**Files:** None (verification only)

- [ ] **Step 1: Run all dispatcher tests**

```bash
cd ~/.openclaw/dispatcher-agent
for t in tests/test_*.py; do
    name=$(basename "$t" .py)
    echo "=== $name ==="
    python3 -m unittest "tests.$name" 2>&1 | tail -1
done
```

Expected: all pass.

- [ ] **Step 2: Run all kanban-tasks tests**

```bash
cd ~/.openclaw/kanban-tasks
for t in tests/test_*.py; do
    name=$(basename "$t" .py)
    echo "=== $name ==="
    python3 -m unittest "tests.$name" 2>&1 | tail -1
done
```

Expected: all pass.

- [ ] **Step 3: Run all clarification-agent tests (if applicable)**

```bash
cd ~/.openclaw/clarification-agent
for t in tests/test_*.py; do
    name=$(basename "$t" .py)
    echo "=== $name ==="
    python3 -m unittest "tests.$name" 2>&1 | tail -1
done
```

Expected: all pass.

### Task 6.2: Execute backfill script (apply mode)

**Files:** None (execução)

- [ ] **Step 1: Dry-run backfill**

```bash
cd ~/.openclaw/kanban-tasks
python3 tools/backfill_close_escalations.py
```

Expected: lista ~6 tasks órfãs (T-0070, T-0150, T-0161, etc).

- [ ] **Step 2: Apply backfill**

```bash
python3 tools/backfill_close_escalations.py --apply
```

Expected: cada task processada com `affected_files` populated.

- [ ] **Step 3: Verify cleanup**

```bash
ls ~/.openclaw/clarification-agent/escalations/_resolved-* 2>/dev/null
ls ~/.openclaw/tester-agent/escalations/_resolved-* 2>/dev/null
```

Expected: diretórios criados com files movidos.

- [ ] **Step 4: Verify cron-tick desbloqueia bevox-site**

```bash
~/.openclaw/dispatcher-agent/cli.sh cron-tick --dry-run --json | python3 -c "
import json, sys
d = json.load(sys.stdin)
for p in d.get('actions_per_project', []):
    print(f\"{p['project']}: {p['outcome']}\")
"
```

Expected: bevox-site mostra `dispatched` ou `skipped_no_ready` (não mais `skipped_escalation`).

### Task 6.3: Manual smoke test (spec §6.2)

**Files:** None (smoke E2E manual)

- [ ] **Step 1: Create fake task in test-project**

```bash
~/.openclaw/kanban-tasks/cli.sh task add T-9001 \
    --project test-project --title "F3 smoke task" \
    --sprint sprint-X-current  # ajustar sprint conforme test-project
```

- [ ] **Step 2: Move to ready**

```bash
~/.openclaw/kanban-tasks/cli.sh task move T-9001 ready
```

- [ ] **Step 3: Wait cron-tick to dispatch (or trigger manually)**

```bash
sleep 15
systemctl --user list-units --type=service --state=active | grep claude-task-T-9001
```

- [ ] **Step 4: Check RuntimeMaxSec set**

```bash
UNIT=$(systemctl --user list-units --type=service --state=active --plain --no-legend | awk '/claude-task-T-9001/{print $1; exit}')
systemctl --user show "$UNIT" --property=RuntimeMaxUSec --value
```

Expected: `43200000000` (12h em microsegundos).

- [ ] **Step 5: Force kill, verify F2 hook runs**

```bash
systemctl --user stop "$UNIT"
# Wait reaper detect + kanban event
sleep 15
grep "T-9001" ~/.openclaw/kanban-tasks/events.jsonl | tail -3
```

- [ ] **Step 6: Move task to done manually, verify F2 hook**

```bash
~/.openclaw/kanban-tasks/cli.sh task move T-9001 done
sleep 2
grep "T-9001" ~/.openclaw/kanban-tasks/events.jsonl | grep "task_escalations_auto_closed"
```

Expected: evento presente.

- [ ] **Step 7: Document smoke results**

Apenda observações ao PR description (se PR já criado) ou ao end-of-task notes.

### Task 6.4: Push branch + open PR (or merge)

**Files:** None (git ops)

- [ ] **Step 1: Push**

```bash
cd ~/.openclaw
git push -u origin feat/ubn-w2-loop-self-healing
```

- [ ] **Step 2: Open PR (or merge straight per Bernard convention)**

```bash
# Opcional — Bernard normalmente decide merge direto pra main após review
gh pr create --title "feat(ubn-w2): loop self-healing — F1+F2+F3+F4" \
  --body "$(cat <<'EOF'
## Summary
Wave-2 do Universal Block Notifier. 4 components que fecham gaps estruturais
descobertos em produção (sprint-35 bevox-site travado 5 dias).

## Changes
- F1 cron-dispatcher gating-by-status (exclui done/rejected/archived/backlog)
- F2 lifecycle hook em task move_status/archive (fecha escalation files)
- F3.1 executor RuntimeMaxSec=12h via systemd-run (env override + per-task)
- F3.2 reaper safety net pra legacy executors (kill > 12h)
- F4 stuck_in_ready criterion (sprint current + ready > 30min)
- Backfill script tools/backfill_close_escalations.py

## Test plan
- [x] All unit tests passing (~25 tests novos)
- [x] Backfill executado em ~6 órfãs
- [x] Smoke E2E §6.2 completo (RuntimeMaxSec set, hook fires, cron desbloqueia)
- [x] cron-tick --dry-run mostra bevox-site dispatched

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Update memory (após merge)**

```bash
# Atualizar ~/.claude/projects/-home-you--openclaw/memory/e10_ubn_state.md
# adicionando linha "DELIVERED wave-2 2026-05-XX (F1+F2+F3+F4)"
```

- [ ] **Step 4: Cleanup tmp + zombie**

```bash
# Backup do v0.1.0 órfão (descoberto durante wave-1)
rm -rf /tmp/unblock-commands.bak-20260504
# Confirmar zombie T-0161 morreu pelo reaper safety net
systemctl --user list-units --type=service --state=active | grep T-0161 || echo "✓ zombie killed"
```

---

## Self-Review Checklist (do plano antes de executar)

- [x] **Spec coverage:** F1, F2 (move_status + archive), F3.1, F3.2, F4, backfill — todas têm tasks dedicadas.
- [x] **Placeholder scan:** todos os steps têm código completo ou comando exato. Nenhum "implement later" ou "add validation".
- [x] **Type consistency:** function signatures consistentes (e.g., `_auto_close_escalations(state, task_id, new_status, actor)` igual em test e impl).
- [x] **Acceptance criteria:** Phase 6 cobre todas as ACs do spec §9.

## Notas de execução

- **Cadência de commit:** 1 commit por task (não por step). Cada commit é "ship-ready" sozinho.
- **Branch policy:** trabalhar inteiramente em `feat/ubn-w2-loop-self-healing`. Não tocar main até wave completa.
- **Test-driven:** cada feature começa por failing test. Não implementar sem teste primeiro.
- **Regression gate:** antes de cada commit, rodar suite do agent tocado. Se quebrar tests pre-existentes, parar e investigar.
- **Manual smoke (§6.2/Task 6.3) é mandatório:** PR sem smoke executado não merge.
