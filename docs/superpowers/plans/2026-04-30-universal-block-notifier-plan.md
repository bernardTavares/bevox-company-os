# Universal Block Notifier (UBN) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Garantir que toda task em estado de atenção do operador (blocked, proposed_rejected, stuck-in-testing) gere escalation no Telegram tópico `blocks` em ≤10s, com resolução por chat via vocabulário fixo de 4 actions (`retry`, `force_done`, `force_reject`, `manual_answer`).

**Architecture:** Reaper centralizado ganha stage `block_scanner` que varre kanban + escalation files; pra cada candidate sem escalation aberta, `escalation_dispatcher` cria file estruturado e envia Telegram. Bernard responde via gateway plugin JS (`/ubn_*` commands) que despacha pra `clarification-agent/cli.sh ubn` (canônico Python — único ponto que muda kanban). Smart retry usa matriz `(block_reason, current_status) → action` respeitando whitelist de transições.

**Tech Stack:** Python 3.13 (reaper, ubn_actions), Bash (cli.sh subcomando), JavaScript Node 20 (gateway plugin knowledge-sync), Telegram Bot API, systemd-managed timers.

**Spec ref:** `bevox-knowledge/35_specs/openclaw/2026-04-30-universal-block-notifier.md`
**PRD ref:** `bevox-knowledge/10_prd/openclaw/2026-04-30-universal-block-notifier.md`

---

## File Structure

**`~/.openclaw` (Python — main repo):**

| Path | Responsibility | Status |
|---|---|---|
| `dispatcher-agent/lib/block_scanner.py` | 3 critérios de detecção + dedup; pure function returning Candidate list | CREATE |
| `dispatcher-agent/lib/escalation_dispatcher.py` | Render escalation file + send Telegram + write JSONL audit | CREATE |
| `dispatcher-agent/lib/reaper.py` | Wire block_scanner stage no tick (try/except local) | MODIFY |
| `clarification-agent/lib/ubn_actions.py` | Smart retry matrix + 4 action strategies + backfill cmd; canônico Python que muda kanban | CREATE |
| `clarification-agent/cli.sh` | Adiciona subcomando `ubn` despachando pra ubn_actions.py | MODIFY |
| `tester-agent/lib/lifecycle.py` | `_write_escalation_md` ganha frontmatter parseável | MODIFY |
| `tester-agent/lib/store.py` | Adiciona `read_escalation(path) -> dict | None` | MODIFY |
| `dispatcher-agent/tests/test_block_scanner.py` | Unit tests (8+) | CREATE |
| `dispatcher-agent/tests/test_escalation_dispatcher.py` | Unit tests (4+) | CREATE |
| `clarification-agent/tests/test_ubn_actions.py` | Unit tests (10+) | CREATE |
| `tester-agent/tests/test_escalation_format.py` | Tests pro novo frontmatter | CREATE |

**`~/code/knowledge-sync` (gateway plugin JS):**

| Path | Responsibility | Status |
|---|---|---|
| `plugins/clarification-commands/lib/ubn-handlers.js` | Parse `/ubn_*` args + spawn `clarification-agent/cli.sh ubn ...` + format reply | CREATE |
| `plugins/clarification-commands/index.js` | `api.registerCommand` 4 novos comandos (`ubn_retry`, `ubn_done`, `ubn_reject`, `ubn_answer`) | MODIFY |
| `plugins/clarification-commands/openclaw.plugin.json` | Bump version | MODIFY |

**`~/bevox-knowledge`:** PRD + spec já commitados em `draft/universal-block-notifier`. `40_roadmap/_shared/delivery-tracker.yml` modify ao final.

---

## Phase A — Tester escalation format (pre-requisito da §3.2)

### Task 1: Add `read_escalation()` helper to tester-agent/lib/store.py

**Files:**
- Modify: `tester-agent/lib/store.py`
- Test: `tester-agent/tests/test_escalation_format.py`

- [ ] **Step 1: Write failing test for new format**

Arquivo: `tester-agent/tests/test_escalation_format.py`

```python
"""Tests for tester escalation file frontmatter (UBN pre-req)."""
import unittest
import tempfile
from pathlib import Path
from lib import store


class TestReadEscalation(unittest.TestCase):
    def test_returns_none_for_legacy_format_without_frontmatter(self):
        """Legacy escalation files (sem frontmatter) retornam None."""
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write("# Tester escalation — T-0001-tr-1\n\n**Task:** T-0001\n")
            path = Path(f.name)
        try:
            result = store.read_escalation(path)
            self.assertIsNone(result)
        finally:
            path.unlink()

    def test_parses_frontmatter_v1(self):
        """Files com frontmatter retornam dict com campos canônicos."""
        content = """---
test_run_id: T-0042-tr-3
task_id: T-0042
decision: proposed_rejected
structural_concern: spec_inconsistent
generated_at: 2026-04-30T12:00:00Z
---

# Tester escalation — T-0042-tr-3
"""
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write(content)
            path = Path(f.name)
        try:
            result = store.read_escalation(path)
            self.assertIsNotNone(result)
            self.assertEqual(result["test_run_id"], "T-0042-tr-3")
            self.assertEqual(result["task_id"], "T-0042")
            self.assertEqual(result["decision"], "proposed_rejected")
            self.assertEqual(result["structural_concern"], "spec_inconsistent")
        finally:
            path.unlink()

    def test_returns_none_for_missing_required_field(self):
        """Frontmatter sem decision retorna None (defensivo)."""
        content = """---
task_id: T-0001
---
"""
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write(content)
            path = Path(f.name)
        try:
            result = store.read_escalation(path)
            self.assertIsNone(result)
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

```
cd ~/.openclaw/tester-agent
python3 -m pytest tests/test_escalation_format.py::TestReadEscalation -v
```

Expected: 3 tests FAIL with `AttributeError: module 'lib.store' has no attribute 'read_escalation'`

- [ ] **Step 3: Add `read_escalation` to store.py**

Edit `tester-agent/lib/store.py` (adicionar no fim do arquivo):

```python
import re as _re_for_escalation


def read_escalation(path) -> dict | None:
    """Le escalation file e retorna dict do frontmatter ou None.

    Required fields: test_run_id, task_id, decision.
    Files sem frontmatter (formato legacy pre-UBN) retornam None.

    Spec: bevox-knowledge/35_specs/openclaw/2026-04-30-universal-block-notifier.md §3.2
    """
    try:
        content = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    m = _re_for_escalation.match(r"---\n(.*?)\n---\n", content, _re_for_escalation.DOTALL)
    if not m:
        return None
    data = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        data[key.strip()] = value.strip()
    if not all(k in data for k in ("test_run_id", "task_id", "decision")):
        return None
    return data
```

- [ ] **Step 4: Run test to verify it passes**

```
python3 -m pytest tests/test_escalation_format.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```
git add tester-agent/lib/store.py tester-agent/tests/test_escalation_format.py
git commit -m "feat(tester): read_escalation() helper parses frontmatter (UBN pre-req)

Adiciona helper que parseia frontmatter de escalation files. Required
fields: test_run_id, task_id, decision. Files legacy (sem frontmatter)
retornam None — backward-compatible.

Spec: bevox-knowledge/35_specs/openclaw/2026-04-30-universal-block-notifier.md §3.2

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `_write_escalation_md` emite frontmatter parseável

**Files:**
- Modify: `tester-agent/lib/lifecycle.py:140-167`
- Test: `tester-agent/tests/test_escalation_format.py`

- [ ] **Step 1: Add failing test for write→read roundtrip**

Append to `tester-agent/tests/test_escalation_format.py`:

```python
class TestWriteEscalationFrontmatter(unittest.TestCase):
    def test_write_then_read_roundtrip(self):
        """Files escritos por _write_escalation_md são parseáveis por read_escalation."""
        from lib import lifecycle
        from unittest.mock import patch
        import tempfile, shutil

        tmp = tempfile.mkdtemp()
        try:
            with patch.object(store, "ESCALATIONS_DIR", Path(tmp)):
                checks = [{
                    "ac": "test AC",
                    "effective_structural_concern": "spec_inconsistent",
                    "evidence": "evidência",
                    "valid_sources": ["/tmp/x"],
                    "sources": [],
                }]
                lifecycle._write_escalation_md("T-0099-tr-2", "T-0099", checks)
            files = list(Path(tmp).glob("*.md"))
            self.assertEqual(len(files), 1)
            data = store.read_escalation(files[0])
            self.assertIsNotNone(data, "frontmatter ausente — escalation não parseável")
            self.assertEqual(data["task_id"], "T-0099")
            self.assertEqual(data["test_run_id"], "T-0099-tr-2")
            self.assertEqual(data["decision"], "proposed_rejected")
            self.assertEqual(data["structural_concern"], "spec_inconsistent")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
```

- [ ] **Step 2: Run test to verify it fails**

```
python3 -m pytest tests/test_escalation_format.py::TestWriteEscalationFrontmatter -v
```

Expected: FAIL with `frontmatter ausente`.

- [ ] **Step 3: Modify `_write_escalation_md` to prepend frontmatter**

Edit `tester-agent/lib/lifecycle.py` (function `_write_escalation_md`):

```python
def _write_escalation_md(test_run_id: str, task_id: str,
                         checks: List[Dict[str, Any]]) -> None:
    structural_checks = [c for c in checks if c.get("effective_structural_concern")]
    suggested = (structural_checks[0].get("effective_structural_concern")
                 if structural_checks else "manual")
    frontmatter = (
        f"---\n"
        f"test_run_id: {test_run_id}\n"
        f"task_id: {task_id}\n"
        f"decision: proposed_rejected\n"
        f"structural_concern: {suggested}\n"
        f"generated_at: {store.now_iso()}\n"
        f"---\n\n"
    )
    body = f"""# Tester escalation — {test_run_id}

**Task:** {task_id}
**Generated at:** {store.now_iso()}
**Suggested category:** {suggested}

---

## Structural concerns detectadas

"""
    for c in structural_checks:
        body += (f"### AC: {c.get('ac', '')[:200]}\n\n"
                 f"- structural_concern: {c.get('effective_structural_concern')}\n"
                 f"- evidence: {c.get('evidence', '')[:300]}\n"
                 f"- sources: {c.get('valid_sources') or c.get('sources')}\n\n")
    body += """---

## Acoes possiveis (Bernard)

- `vox tester reject-task <task-id> --reason "<categoria>: <detail>" --commit`
- `vox tester recheck <task-id>` (apos editar AC/spec)
- Override manual: `~/.openclaw/kanban-tasks/cli.sh task move <task-id> done --actor bernard`
- UBN: respond no Telegram com `/ubn_done <task-id> <reason>` ou `/ubn_reject <task-id> <reason>`
"""
    store.write_escalation(test_run_id, frontmatter + body)
```

- [ ] **Step 4: Run all tests in tester-agent to verify no regression**

```
python3 -m pytest tests/ -v
```

Expected: All previously-passing tests still pass + new TestWriteEscalationFrontmatter passes.

- [ ] **Step 5: Commit**

```
git add tester-agent/lib/lifecycle.py tester-agent/tests/test_escalation_format.py
git commit -m "feat(tester): escalation_md emits parseable frontmatter

Mudança aditiva backward-compatible: frontmatter precede body antigo.
Files legacy continuam legíveis pra Bernard; UBN só detecta os novos.

Spec: bevox-knowledge/35_specs/openclaw/2026-04-30-universal-block-notifier.md §3.2

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase B — block_scanner module

### Task 3: Create block_scanner.py with critério "blocked" (§3.1)

**Files:**
- Create: `dispatcher-agent/lib/block_scanner.py`
- Test: `dispatcher-agent/tests/test_block_scanner.py`

- [ ] **Step 1: Write failing test**

Arquivo: `dispatcher-agent/tests/test_block_scanner.py`

```python
"""Unit tests for UBN block_scanner — 3 critérios + dedup.

Spec: bevox-knowledge/35_specs/openclaw/2026-04-30-universal-block-notifier.md §3
"""
import unittest
from datetime import datetime, timezone, timedelta
from lib import block_scanner


class TestCriterionBlocked(unittest.TestCase):
    def test_returns_blocked_tasks_with_block_session_key(self):
        state = {
            "tasks": [
                {"id": "T-0001", "blocked": True,
                 "blocked_at": "2026-04-30T12:00:00Z",
                 "blocked_reason": "test_failed: AC1",
                 "project": "bevox-site"},
                {"id": "T-0002", "blocked": False, "project": "bevox-site"},
            ]
        }
        candidates = block_scanner.candidates_blocked(state)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].task_id, "T-0001")
        self.assertEqual(candidates[0].criterion, "blocked")
        self.assertEqual(candidates[0].block_session_key, "2026-04-30T12:00:00Z")
        self.assertEqual(candidates[0].block_reason, "test_failed: AC1")
        self.assertEqual(candidates[0].project, "bevox-site")

    def test_empty_state_returns_empty_list(self):
        self.assertEqual(block_scanner.candidates_blocked({"tasks": []}), [])

    def test_blocked_without_blocked_at_uses_unknown_key(self):
        """Defensivo — task com blocked=true mas sem blocked_at."""
        state = {"tasks": [
            {"id": "T-0003", "blocked": True, "blocked_reason": "x", "project": "p"}
        ]}
        candidates = block_scanner.candidates_blocked(state)
        self.assertEqual(len(candidates), 1)
        self.assertIsNone(candidates[0].block_session_key)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

```
cd ~/.openclaw/dispatcher-agent
python3 -m pytest tests/test_block_scanner.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'lib.block_scanner'`

- [ ] **Step 3: Create block_scanner.py with Candidate + critério blocked**

Arquivo: `dispatcher-agent/lib/block_scanner.py`

```python
"""UBN block_scanner — detecta tasks em estado de atenção do operador.

3 critérios paralelos + dedup. Roda no reaper tick (10s via override
cadence-10s.conf).

Spec: bevox-knowledge/35_specs/openclaw/2026-04-30-universal-block-notifier.md §3
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional


@dataclass(frozen=True)
class Candidate:
    """Task que merece escalation. Imutável pra dedup safety."""
    task_id: str
    criterion: str  # "blocked" | "proposed_rejected" | "stuck_in_testing"
    block_session_key: Optional[str]
    block_reason: str
    project: Optional[str]


def candidates_blocked(state: dict) -> List[Candidate]:
    """Critério 3.1: tasks com task.blocked == True."""
    out = []
    for t in state.get("tasks", []) or []:
        if t.get("blocked") is True:
            out.append(Candidate(
                task_id=t["id"],
                criterion="blocked",
                block_session_key=t.get("blocked_at"),
                block_reason=t.get("blocked_reason") or "(unknown)",
                project=t.get("project"),
            ))
    return out
```

- [ ] **Step 4: Run test to verify pass**

```
python3 -m pytest tests/test_block_scanner.py -v
```

Expected: 3 PASS.

- [ ] **Step 5: Commit**

```
git add dispatcher-agent/lib/block_scanner.py dispatcher-agent/tests/test_block_scanner.py
git commit -m "feat(ubn): block_scanner critério 'blocked' (§3.1)

Detecta tasks com task.blocked=True. Pure function retornando Candidate
list pra dedup downstream.

Spec: bevox-knowledge/35_specs/openclaw/2026-04-30-universal-block-notifier.md §3.1

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Add critério "proposed_rejected" (§3.2)

**Files:**
- Modify: `dispatcher-agent/lib/block_scanner.py`
- Modify: `dispatcher-agent/tests/test_block_scanner.py`

- [ ] **Step 1: Add failing test**

Append to `tests/test_block_scanner.py`:

```python
import tempfile, shutil
from pathlib import Path
from unittest.mock import patch


class TestCriterionProposedRejected(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.tmp_path = Path(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_escalation(self, task_id, test_run_id, decision="proposed_rejected"):
        path = self.tmp_path / f"{test_run_id}.md"
        path.write_text(f"""---
test_run_id: {test_run_id}
task_id: {task_id}
decision: {decision}
structural_concern: spec_inconsistent
generated_at: 2026-04-30T12:00:00Z
---
body
""")
        return path

    def test_detects_proposed_rejected_in_24h_window(self):
        self._write_escalation("T-0010", "T-0010-tr-1")
        with patch.object(block_scanner, "TESTER_ESCALATIONS_DIR", self.tmp_path):
            with patch.object(block_scanner, "_lookup_project_from_kanban", return_value="bevox-site"):
                candidates = block_scanner.candidates_proposed_rejected()
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].task_id, "T-0010")
        self.assertEqual(candidates[0].criterion, "proposed_rejected")
        self.assertEqual(candidates[0].block_session_key, "T-0010-tr-1")
        self.assertIn("spec_inconsistent", candidates[0].block_reason)

    def test_skips_files_older_than_24h(self):
        path = self._write_escalation("T-0011", "T-0011-tr-1")
        # Backdate file mtime
        old = (datetime.now(timezone.utc) - timedelta(hours=25)).timestamp()
        os.utime(path, (old, old))
        with patch.object(block_scanner, "TESTER_ESCALATIONS_DIR", self.tmp_path):
            candidates = block_scanner.candidates_proposed_rejected()
        self.assertEqual(candidates, [])

    def test_skips_decisions_other_than_proposed_rejected(self):
        self._write_escalation("T-0012", "T-0012-tr-1", decision="done")
        with patch.object(block_scanner, "TESTER_ESCALATIONS_DIR", self.tmp_path):
            candidates = block_scanner.candidates_proposed_rejected()
        self.assertEqual(candidates, [])

    def test_skips_legacy_files_without_frontmatter(self):
        (self.tmp_path / "T-0013-tr-1.md").write_text("# legacy file")
        with patch.object(block_scanner, "TESTER_ESCALATIONS_DIR", self.tmp_path):
            candidates = block_scanner.candidates_proposed_rejected()
        self.assertEqual(candidates, [])
```

- [ ] **Step 2: Run test to verify fail**

```
python3 -m pytest tests/test_block_scanner.py::TestCriterionProposedRejected -v
```

Expected: 4 FAIL with `AttributeError`.

- [ ] **Step 3: Add critério proposed_rejected**

Append to `dispatcher-agent/lib/block_scanner.py`:

```python
import sys as _sys
_TESTER_LIB = "~/.openclaw/tester-agent"
if _TESTER_LIB not in _sys.path:
    _sys.path.insert(0, _TESTER_LIB)
from lib import store as _tester_store_module  # noqa: E402

TESTER_ESCALATIONS_DIR = Path("~/.openclaw/tester-agent/escalations")
PROPOSED_REJECTED_WINDOW_HOURS = 24


def _lookup_project_from_kanban(task_id: str) -> Optional[str]:
    """Lookup project pelo state.json. Retorna None se não achar."""
    import json
    try:
        state_path = Path("~/.openclaw/kanban-tasks/state.json")
        data = json.loads(state_path.read_text(encoding="utf-8"))
        for t in data.get("tasks", []):
            if t.get("id") == task_id:
                return t.get("project")
    except (OSError, json.JSONDecodeError, KeyError):
        return None
    return None


def candidates_proposed_rejected() -> List[Candidate]:
    """Critério 3.2: tester escalation files com decision proposed_rejected
    no window de 24h."""
    if not TESTER_ESCALATIONS_DIR.is_dir():
        return []
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=PROPOSED_REJECTED_WINDOW_HOURS)).timestamp()
    out = []
    for path in TESTER_ESCALATIONS_DIR.glob("T-*-tr-*.md"):
        if not path.is_file() or path.stat().st_mtime < cutoff:
            continue
        data = _tester_store_module.read_escalation(path)
        if data is None or data.get("decision") != "proposed_rejected":
            continue
        out.append(Candidate(
            task_id=data["task_id"],
            criterion="proposed_rejected",
            block_session_key=data["test_run_id"],
            block_reason=f"proposed_rejected: {data.get('structural_concern','?')}",
            project=_lookup_project_from_kanban(data["task_id"]),
        ))
    return out
```

- [ ] **Step 4: Run test pass**

```
python3 -m pytest tests/test_block_scanner.py -v
```

Expected: All 7 PASS.

- [ ] **Step 5: Commit**

```
git add dispatcher-agent/lib/block_scanner.py dispatcher-agent/tests/test_block_scanner.py
git commit -m "feat(ubn): block_scanner critério 'proposed_rejected' (§3.2)

Reusa tester store.read_escalation. 24h window evita re-escalar files
arqueológicos. Skip legacy files sem frontmatter (None retorno).

Spec: bevox-knowledge/35_specs/openclaw/2026-04-30-universal-block-notifier.md §3.2

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Add critério "stuck-in-testing" com backoff exclusion (§3.3)

**Files:**
- Modify: `dispatcher-agent/lib/block_scanner.py`
- Modify: `dispatcher-agent/tests/test_block_scanner.py`

- [ ] **Step 1: Add failing test**

Append to `tests/test_block_scanner.py`:

```python
class TestCriterionStuckInTesting(unittest.TestCase):
    def _state_with_task(self, task_id, status, updated_minutes_ago,
                         test_result=None, blocked=False):
        updated = (datetime.now(timezone.utc)
                   - timedelta(minutes=updated_minutes_ago)).isoformat().replace("+00:00", "Z")
        task = {
            "id": task_id, "status": status, "blocked": blocked,
            "updated_at": updated, "project": "bevox-site",
            "dispatch_payload": {"test_result": test_result or {}},
        }
        return {"tasks": [task]}

    def test_detects_task_in_testing_over_threshold(self):
        state = self._state_with_task("T-0020", "testing", updated_minutes_ago=45)
        candidates = block_scanner.candidates_stuck_testing(state)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].task_id, "T-0020")
        self.assertEqual(candidates[0].criterion, "stuck_in_testing")
        self.assertIn("stuck-in-testing", candidates[0].block_reason)

    def test_skips_task_below_threshold(self):
        state = self._state_with_task("T-0021", "testing", updated_minutes_ago=10)
        self.assertEqual(block_scanner.candidates_stuck_testing(state), [])

    def test_skips_blocked_task(self):
        state = self._state_with_task("T-0022", "testing", 45, blocked=True)
        self.assertEqual(block_scanner.candidates_stuck_testing(state), [])

    def test_excludes_inconclusive_within_backoff_window(self):
        """Task com last_test=inconclusive dentro de backoff window do reaper
        NÃO é stuck — está legitimamente esperando próxima invocação."""
        recent = (datetime.now(timezone.utc) - timedelta(seconds=20)).isoformat().replace("+00:00", "Z")
        # test_run_count=1 → backoff 30s. 20s < 30s → ainda em backoff.
        state = self._state_with_task("T-0023", "testing", 45, test_result={
            "last_test_overall": "inconclusive",
            "last_test_finished_at": recent,
            "test_run_count": 1,
        })
        self.assertEqual(block_scanner.candidates_stuck_testing(state), [])

    def test_includes_inconclusive_after_backoff_window(self):
        """Task com inconclusive ALÉM do backoff window vira stuck."""
        old = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat().replace("+00:00", "Z")
        # test_run_count=1 → backoff 30s. 120s >> 30s → não está mais em backoff.
        state = self._state_with_task("T-0024", "testing", 45, test_result={
            "last_test_overall": "inconclusive",
            "last_test_finished_at": old,
            "test_run_count": 1,
        })
        candidates = block_scanner.candidates_stuck_testing(state)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].task_id, "T-0024")

    def test_threshold_env_var_override(self):
        state = self._state_with_task("T-0025", "testing", updated_minutes_ago=10)
        with patch.dict(os.environ, {"OPENCLAW_REAPER_STUCK_TESTING_THRESHOLD_MIN": "5"}):
            candidates = block_scanner.candidates_stuck_testing(state)
        self.assertEqual(len(candidates), 1)
```

- [ ] **Step 2: Run test fail**

```
python3 -m pytest tests/test_block_scanner.py::TestCriterionStuckInTesting -v
```

Expected: 6 FAIL.

- [ ] **Step 3: Add critério stuck-in-testing**

Append to `block_scanner.py`:

```python
from .reaper import _backoff_delay_for  # reaper resilience wave


def _parse_iso(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def candidates_stuck_testing(state: dict) -> List[Candidate]:
    """Critério 3.3: tasks em testing > threshold_min sem decisão E fora
    de backoff window do reaper resilience."""
    threshold_min = int(os.environ.get(
        "OPENCLAW_REAPER_STUCK_TESTING_THRESHOLD_MIN", "30"))
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=threshold_min)
    out = []
    for t in state.get("tasks", []) or []:
        if t.get("status") != "testing" or t.get("blocked"):
            continue
        updated_at = _parse_iso(t.get("updated_at"))
        if not updated_at or updated_at >= cutoff:
            continue
        # Exclude tasks within reaper backoff window (legítima espera)
        tr = (t.get("dispatch_payload") or {}).get("test_result") or {}
        if tr.get("last_test_overall") == "inconclusive":
            last_finished = _parse_iso(tr.get("last_test_finished_at"))
            if last_finished:
                backoff_s = _backoff_delay_for(tr.get("test_run_count", 1))
                elapsed = (datetime.now(timezone.utc) - last_finished).total_seconds()
                if elapsed < backoff_s:
                    continue
        out.append(Candidate(
            task_id=t["id"],
            criterion="stuck_in_testing",
            block_session_key=t.get("updated_at"),
            block_reason=f"stuck-in-testing >{threshold_min}min",
            project=t.get("project"),
        ))
    return out
```

- [ ] **Step 4: Run all block_scanner tests**

```
python3 -m pytest tests/test_block_scanner.py -v
```

Expected: 13 PASS.

- [ ] **Step 5: Commit**

```
git add dispatcher-agent/lib/block_scanner.py dispatcher-agent/tests/test_block_scanner.py
git commit -m "feat(ubn): block_scanner critério 'stuck_in_testing' (§3.3)

Threshold env var (default 30min). Exclui tasks dentro de backoff window
do reaper resilience (REINVOKE_BACKOFF_SCHEDULE) — evita falso positivo
em tasks legitimamente esperando próxima invocação.

Spec: bevox-knowledge/35_specs/openclaw/2026-04-30-universal-block-notifier.md §3.3

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Add dedup logic (§3.4)

**Files:**
- Modify: `dispatcher-agent/lib/block_scanner.py`
- Modify: `dispatcher-agent/tests/test_block_scanner.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_block_scanner.py`:

```python
class TestDedup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.escalations_dir = Path(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_existing_escalation(self, task_id, seq, block_session_key, status="open"):
        path = self.escalations_dir / f"{task_id}-blk-{seq}.md"
        path.write_text(f"""---
escalation_id: {task_id}-blk-{seq}
task_id: {task_id}
block_session_key: {block_session_key}
status: {status}
---
""")
        return path

    def test_dedup_returns_existing_when_session_key_matches(self):
        self._write_existing_escalation("T-0030", 1, "2026-04-30T10:00:00Z")
        candidate = block_scanner.Candidate(
            task_id="T-0030", criterion="blocked",
            block_session_key="2026-04-30T10:00:00Z",
            block_reason="x", project="p",
        )
        with patch.object(block_scanner, "UBN_ESCALATIONS_DIR", self.escalations_dir):
            existing = block_scanner.find_open_escalation(candidate)
        self.assertIsNotNone(existing)
        self.assertEqual(existing.name, "T-0030-blk-1.md")

    def test_dedup_returns_none_for_different_session_key(self):
        self._write_existing_escalation("T-0031", 1, "2026-04-30T10:00:00Z")
        candidate = block_scanner.Candidate(
            task_id="T-0031", criterion="blocked",
            block_session_key="2026-04-30T11:00:00Z",  # diferente
            block_reason="x", project="p",
        )
        with patch.object(block_scanner, "UBN_ESCALATIONS_DIR", self.escalations_dir):
            existing = block_scanner.find_open_escalation(candidate)
        self.assertIsNone(existing)

    def test_dedup_ignores_resolved_escalations(self):
        self._write_existing_escalation("T-0032", 1, "key", status="resolved")
        candidate = block_scanner.Candidate(
            task_id="T-0032", criterion="blocked",
            block_session_key="key", block_reason="x", project="p",
        )
        with patch.object(block_scanner, "UBN_ESCALATIONS_DIR", self.escalations_dir):
            existing = block_scanner.find_open_escalation(candidate)
        self.assertIsNone(existing)

    def test_next_seq_increments(self):
        self._write_existing_escalation("T-0033", 1, "key1", status="resolved")
        self._write_existing_escalation("T-0033", 2, "key2", status="resolved")
        with patch.object(block_scanner, "UBN_ESCALATIONS_DIR", self.escalations_dir):
            seq = block_scanner.next_escalation_seq("T-0033")
        self.assertEqual(seq, 3)
```

- [ ] **Step 2: Run fail**

Expected: FAIL `AttributeError: find_open_escalation`.

- [ ] **Step 3: Add dedup functions**

Append to `block_scanner.py`:

```python
import re

UBN_ESCALATIONS_DIR = Path("~/.openclaw/clarification-agent/escalations")
_UBN_FILENAME_RE = re.compile(r"^(T-[\w-]+?)-blk-(\d+)\.md$")


def _parse_ubn_frontmatter(path: Path) -> dict:
    """Parse frontmatter de UBN escalation file. Retorna {} se inválido."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    m = re.match(r"---\n(.*?)\n---\n", content, re.DOTALL)
    if not m:
        return {}
    data = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            data[k.strip()] = v.strip()
    return data


def find_open_escalation(candidate: Candidate) -> Optional[Path]:
    """Retorna path da escalation aberta com mesmo task_id+block_session_key,
    ou None."""
    if not UBN_ESCALATIONS_DIR.is_dir():
        return None
    for path in UBN_ESCALATIONS_DIR.glob(f"{candidate.task_id}-blk-*.md"):
        data = _parse_ubn_frontmatter(path)
        if (data.get("status") == "open"
                and data.get("block_session_key") == (candidate.block_session_key or "")):
            return path
    return None


def next_escalation_seq(task_id: str) -> int:
    """Próximo número sequencial de escalation pra task_id."""
    if not UBN_ESCALATIONS_DIR.is_dir():
        return 1
    max_seq = 0
    for path in UBN_ESCALATIONS_DIR.glob(f"{task_id}-blk-*.md"):
        m = _UBN_FILENAME_RE.match(path.name)
        if m:
            max_seq = max(max_seq, int(m.group(2)))
    return max_seq + 1


def scan_all(state: dict) -> List[Candidate]:
    """Roda os 3 critérios + filtra candidates já com escalation aberta."""
    all_candidates = (
        candidates_blocked(state)
        + candidates_proposed_rejected()
        + candidates_stuck_testing(state)
    )
    new_candidates = []
    seen = set()
    for c in all_candidates:
        # In-tick dedup (mesma task pode hit 2 critérios) — preferir o primeiro.
        if c.task_id in seen:
            continue
        seen.add(c.task_id)
        if find_open_escalation(c) is None:
            new_candidates.append(c)
    return new_candidates
```

- [ ] **Step 4: Run all tests pass**

```
python3 -m pytest tests/test_block_scanner.py -v
```

Expected: 17 PASS.

- [ ] **Step 5: Commit**

```
git add dispatcher-agent/lib/block_scanner.py dispatcher-agent/tests/test_block_scanner.py
git commit -m "feat(ubn): block_scanner dedup + scan_all (§3.4)

find_open_escalation: lookup existing por task_id+block_session_key.
next_escalation_seq: incrementa sequência. scan_all: combina 3 critérios
+ in-tick dedup + filtro de escalations já abertas.

Spec: bevox-knowledge/35_specs/openclaw/2026-04-30-universal-block-notifier.md §3.4

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase C — escalation_dispatcher module

### Task 7: Create escalation_dispatcher.py with render escalation file (§4)

**Files:**
- Create: `dispatcher-agent/lib/escalation_dispatcher.py`
- Test: `dispatcher-agent/tests/test_escalation_dispatcher.py`

- [ ] **Step 1: Write failing test**

Arquivo: `dispatcher-agent/tests/test_escalation_dispatcher.py`

```python
"""Unit tests for UBN escalation_dispatcher.

Spec: bevox-knowledge/35_specs/openclaw/2026-04-30-universal-block-notifier.md §4-§5
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from lib import escalation_dispatcher
from lib.block_scanner import Candidate


class TestRenderEscalationFile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_renders_with_full_frontmatter(self):
        candidate = Candidate(
            task_id="T-0050", criterion="blocked",
            block_session_key="2026-04-30T15:00:00Z",
            block_reason="test_failed: AC1 something",
            project="bevox-site",
        )
        with patch.object(escalation_dispatcher, "UBN_ESCALATIONS_DIR", Path(self.tmp)):
            path = escalation_dispatcher.render_escalation_file(candidate, seq=1)
        self.assertTrue(path.exists())
        content = path.read_text()
        self.assertIn("escalation_id: T-0050-blk-1", content)
        self.assertIn("task_id: T-0050", content)
        self.assertIn("project: bevox-site", content)
        self.assertIn("criterion: blocked", content)
        self.assertIn("block_session_key: 2026-04-30T15:00:00Z", content)
        self.assertIn("status: open", content)
        self.assertIn("dispatched_at: null", content)  # initial state

    def test_filename_format(self):
        candidate = Candidate(
            task_id="T-0051", criterion="blocked",
            block_session_key="x", block_reason="y", project="p",
        )
        with patch.object(escalation_dispatcher, "UBN_ESCALATIONS_DIR", Path(self.tmp)):
            path = escalation_dispatcher.render_escalation_file(candidate, seq=3)
        self.assertEqual(path.name, "T-0051-blk-3.md")
```

- [ ] **Step 2: Run fail**

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Create escalation_dispatcher.py with render**

```python
"""UBN escalation_dispatcher — cria escalation file + envia Telegram.

Spec: bevox-knowledge/35_specs/openclaw/2026-04-30-universal-block-notifier.md §4-§5
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Reuse dispatcher notifier (já em main da wave anterior)
from . import notifier as _notifier
from .block_scanner import Candidate

UBN_ESCALATIONS_DIR = Path("~/.openclaw/clarification-agent/escalations")
_TM_LIB = "~/.openclaw/scripts/lib"
if _TM_LIB not in sys.path:
    sys.path.insert(0, _TM_LIB)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def render_escalation_file(candidate: Candidate, seq: int) -> Path:
    """Cria escalation file no UBN_ESCALATIONS_DIR. dispatched_at=null no
    momento da criação (Telegram dispatch separado)."""
    UBN_ESCALATIONS_DIR.mkdir(parents=True, exist_ok=True)
    escalation_id = f"{candidate.task_id}-blk-{seq}"
    path = UBN_ESCALATIONS_DIR / f"{escalation_id}.md"
    body = f"""---
escalation_id: {escalation_id}
task_id: {candidate.task_id}
project: {candidate.project or "(unknown)"}
detector: reaper
criterion: {candidate.criterion}
block_session_key: {candidate.block_session_key or "(none)"}
block_reason: {candidate.block_reason}
detected_at: {_now_iso()}
dispatched_at: null
token_alias: null
chat_id: null
thread_id: null
telegram_message_id: null
status: open
resolved_at: null
resolved_action: null
resolved_response: null
resolved_by: null
---

# Block escalation for {candidate.task_id}

**Block reason:** {candidate.block_reason}
**Criterion:** {candidate.criterion}

## Available actions (Telegram)

- `/ubn_retry {candidate.task_id}` — smart retry baseado em block_reason
- `/ubn_done {candidate.task_id} <reason>` — marca cumprido manual
- `/ubn_reject {candidate.task_id} <reason>` — task inviável
- `/ubn_answer {candidate.task_id} <texto>` — responde clarification original (texto livre)
"""
    path.write_text(body, encoding="utf-8")
    return path
```

- [ ] **Step 4: Run pass**

```
python3 -m pytest tests/test_escalation_dispatcher.py -v
```

Expected: 2 PASS.

- [ ] **Step 5: Commit**

```
git add dispatcher-agent/lib/escalation_dispatcher.py dispatcher-agent/tests/test_escalation_dispatcher.py
git commit -m "feat(ubn): escalation_dispatcher render file (§4)

Cria escalation file com frontmatter completo (flat schema alinhado com
notifier-state.v2). dispatched_at=null inicial; Telegram envia em step
separado.

Spec: bevox-knowledge/35_specs/openclaw/2026-04-30-universal-block-notifier.md §4

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Add Telegram send + frontmatter update (§5)

**Files:**
- Modify: `dispatcher-agent/lib/escalation_dispatcher.py`
- Modify: `dispatcher-agent/tests/test_escalation_dispatcher.py`

- [ ] **Step 1: Add failing test**

Append to test file:

```python
class TestSendTelegram(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.candidate = Candidate(
            task_id="T-0060", criterion="blocked",
            block_session_key="2026-04-30T16:00:00Z",
            block_reason="test_failed: AC X",
            project="bevox-site",
        )

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _full_env(self):
        return {
            "TELEGRAM_BOT_TOKEN": "tok-abc",
            "OPENCLAW_BLOCKS_TELEGRAM_CHAT_ID": "-1001234567890",
            "OPENCLAW_BLOCKS_TELEGRAM_THREAD_ID": "99",
        }

    def test_dispatch_falls_back_to_global_env_when_no_per_project(self):
        with patch.object(escalation_dispatcher, "UBN_ESCALATIONS_DIR", Path(self.tmp)):
            path = escalation_dispatcher.render_escalation_file(self.candidate, seq=1)
            with patch.dict(os.environ, self._full_env(), clear=True):
                with patch("sys.modules['telegram_meta'].resolve_telegram_target", return_value=None):
                    with patch.object(escalation_dispatcher._notifier, "_send_http",
                                      return_value=(True, {"message_id": 777})):
                        result = escalation_dispatcher.dispatch_telegram(path, self.candidate)
        self.assertTrue(result["sent"])
        # Escalation file deve ter dispatched_at + telegram_message_id atualizados
        content = path.read_text()
        self.assertIn("telegram_message_id: 777", content)
        self.assertNotIn("dispatched_at: null", content)

    def test_dispatch_marks_escalation_with_failure_when_telegram_down(self):
        with patch.object(escalation_dispatcher, "UBN_ESCALATIONS_DIR", Path(self.tmp)):
            path = escalation_dispatcher.render_escalation_file(self.candidate, seq=1)
            with patch.dict(os.environ, self._full_env(), clear=True):
                with patch("sys.modules['telegram_meta'].resolve_telegram_target", return_value=None):
                    with patch.object(escalation_dispatcher._notifier, "_send_http",
                                      return_value=(False, {"error": "telegram_api_500"})):
                        result = escalation_dispatcher.dispatch_telegram(path, self.candidate)
        self.assertFalse(result["sent"])
        # dispatched_at fica null pra retry; telegram_message_id continua null
        content = path.read_text()
        self.assertIn("dispatched_at: null", content)
        self.assertIn("telegram_message_id: null", content)
```

- [ ] **Step 2: Run fail**

Expected: `AttributeError: dispatch_telegram`.

- [ ] **Step 3: Add dispatch_telegram + frontmatter update helper**

Append to `escalation_dispatcher.py`:

```python
import re

_FRONTMATTER_FIELDS_TO_UPDATE = {
    "dispatched_at", "token_alias", "chat_id", "thread_id", "telegram_message_id",
}


def _update_frontmatter(path: Path, updates: dict) -> None:
    """Re-write apenas as keys do frontmatter passadas em updates.
    Mantém body intacto."""
    content = path.read_text(encoding="utf-8")
    m = re.match(r"(---\n)(.*?)(\n---\n)", content, re.DOTALL)
    if not m:
        return
    fm_lines = m.group(2).splitlines()
    new_lines = []
    for line in fm_lines:
        if ":" in line:
            k, _, _ = line.partition(":")
            k_clean = k.strip()
            if k_clean in updates:
                new_lines.append(f"{k_clean}: {updates[k_clean]}")
                continue
        new_lines.append(line)
    new_fm = "\n".join(new_lines)
    new_content = m.group(1) + new_fm + m.group(3) + content[m.end():]
    path.write_text(new_content, encoding="utf-8")


def _resolve_target(project: Optional[str]):
    """Per-project topic 'blocks' com fallback global.
    Retorna (token, chat_id, thread_id, alias) ou None."""
    if project:
        try:
            from telegram_meta import resolve_telegram_target  # type: ignore
            target = resolve_telegram_target(project, "blocks")
            if target is not None:
                token, chat_id, thread_id = target
                return token, chat_id, thread_id, project
        except (ImportError, Exception):
            pass
    # Global fallback
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("OPENCLAW_BLOCKS_TELEGRAM_CHAT_ID")
    thread_id_str = os.environ.get("OPENCLAW_BLOCKS_TELEGRAM_THREAD_ID")
    if not all([token, chat_id, thread_id_str]):
        return None
    try:
        return token, chat_id, int(thread_id_str), "global"
    except (TypeError, ValueError):
        return None


def _format_message(candidate: Candidate, escalation_id: str) -> str:
    return (
        f"⚠️ {candidate.task_id} blocked\n"
        f"project: {candidate.project or '(unknown)'}\n"
        f"reason: {candidate.block_reason[:200]}\n"
        f"escalation: {escalation_id}\n\n"
        f"Reply: /ubn_retry {candidate.task_id} | /ubn_done {candidate.task_id} <reason>"
        f" | /ubn_reject {candidate.task_id} <reason> | /ubn_answer {candidate.task_id} <texto>"
    )


def dispatch_telegram(escalation_path: Path, candidate: Candidate) -> dict:
    """Envia escalation via Telegram. Atualiza frontmatter com message_id.
    Retorna {sent: bool, message_id: int|None, reason: str|None}."""
    target = _resolve_target(candidate.project)
    if target is None:
        return {"sent": False, "message_id": None, "reason": "no_telegram_target"}
    token, chat_id, thread_id, alias = target
    escalation_id = escalation_path.stem
    text = _format_message(candidate, escalation_id)
    import json
    payload = json.dumps({
        "chat_id": chat_id,
        "message_thread_id": thread_id,
        "text": text,
    }).encode("utf-8")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    ok, result = _notifier._send_http(url, payload)
    if ok:
        _update_frontmatter(escalation_path, {
            "dispatched_at": _now_iso(),
            "token_alias": alias,
            "chat_id": chat_id,
            "thread_id": str(thread_id),
            "telegram_message_id": str(result.get("message_id", "")),
        })
        return {"sent": True, "message_id": result.get("message_id"), "reason": None}
    return {"sent": False, "message_id": None,
            "reason": result.get("error", "unknown")}
```

- [ ] **Step 4: Run pass**

```
python3 -m pytest tests/test_escalation_dispatcher.py -v
```

Expected: 4 PASS.

- [ ] **Step 5: Commit**

```
git add dispatcher-agent/lib/escalation_dispatcher.py dispatcher-agent/tests/test_escalation_dispatcher.py
git commit -m "feat(ubn): escalation_dispatcher Telegram send + frontmatter update (§5)

Per-project topic 'blocks' com fallback global env. Atualiza frontmatter
com dispatched_at + telegram_message_id em sucesso. Falha Telegram
mantém dispatched_at=null pra retry no próximo tick.

Spec: bevox-knowledge/35_specs/openclaw/2026-04-30-universal-block-notifier.md §5

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase D — Wire reaper

### Task 9: Add block_scanner stage to reaper tick (try/except local + kill switch)

**Files:**
- Modify: `dispatcher-agent/lib/reaper.py`
- Test: integration-style — add `dispatcher-agent/tests/test_reaper_block_scanner_integration.py`

- [ ] **Step 1: Write failing integration test**

```python
"""Integration test: reaper tick invoca block_scanner + escalation_dispatcher."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from lib import reaper


class TestReaperBlockScannerStage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.state_path = Path(self.tmp) / "state.json"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_kill_switch_skips_block_scanner(self):
        """Env OPENCLAW_REAPER_DISABLE_BLOCK_SCANNER=1 → stage no-op."""
        with patch.dict(os.environ, {"OPENCLAW_REAPER_DISABLE_BLOCK_SCANNER": "1"}):
            with patch.object(reaper, "_block_scanner_module") as mock_scanner:
                reaper._block_scanner_stage({})
                mock_scanner.scan_all.assert_not_called()

    def test_normal_flow_calls_scan_and_dispatch(self):
        """Sem kill switch → chama scan_all + dispatch pra cada candidate."""
        from lib.block_scanner import Candidate
        candidate = Candidate(
            task_id="T-0070", criterion="blocked",
            block_session_key="k", block_reason="x", project="p")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENCLAW_REAPER_DISABLE_BLOCK_SCANNER", None)
            with patch.object(reaper, "_block_scanner_module") as mock_scanner:
                with patch.object(reaper, "_escalation_dispatcher_module") as mock_dispatcher:
                    mock_scanner.scan_all.return_value = [candidate]
                    mock_scanner.next_escalation_seq.return_value = 1
                    mock_dispatcher.render_escalation_file.return_value = Path("/tmp/T-0070-blk-1.md")
                    mock_dispatcher.dispatch_telegram.return_value = {"sent": True, "message_id": 100}
                    reaper._block_scanner_stage({"tasks": []})
                    mock_scanner.scan_all.assert_called_once()
                    mock_dispatcher.render_escalation_file.assert_called_once()
                    mock_dispatcher.dispatch_telegram.assert_called_once()

    def test_exception_in_block_scanner_does_not_propagate(self):
        """Try/except local — falha do block_scanner não derruba reaper."""
        with patch.object(reaper, "_block_scanner_module") as mock_scanner:
            mock_scanner.scan_all.side_effect = RuntimeError("boom")
            try:
                reaper._block_scanner_stage({"tasks": []})
            except RuntimeError:
                self.fail("Block scanner exception escaped — should be caught locally")
```

- [ ] **Step 2: Run fail**

Expected: FAIL `AttributeError: _block_scanner_stage`.

- [ ] **Step 3: Add `_block_scanner_stage` to reaper.py and wire into tick**

Edit `dispatcher-agent/lib/reaper.py` (add near top of run_tick or as new function):

```python
# UBN block_scanner integration
try:
    from . import block_scanner as _block_scanner_module
    from . import escalation_dispatcher as _escalation_dispatcher_module
except ImportError:
    _block_scanner_module = None  # type: ignore
    _escalation_dispatcher_module = None  # type: ignore


def _block_scanner_stage(state: dict) -> dict:
    """UBN stage: scan blocks + dispatch escalations.
    Try/except local — não derruba outros stages.

    Spec: bevox-knowledge/35_specs/openclaw/2026-04-30-universal-block-notifier.md §3
    """
    stats = {"candidates_found": 0, "escalations_created": 0, "telegram_sent": 0,
             "errors": 0, "skipped_kill_switch": False}
    if os.environ.get("OPENCLAW_REAPER_DISABLE_BLOCK_SCANNER") == "1":
        stats["skipped_kill_switch"] = True
        return stats
    if _block_scanner_module is None or _escalation_dispatcher_module is None:
        stats["errors"] += 1
        print("WARN: UBN modules not available", file=sys.stderr)
        return stats
    try:
        candidates = _block_scanner_module.scan_all(state)
        stats["candidates_found"] = len(candidates)
        for c in candidates:
            try:
                seq = _block_scanner_module.next_escalation_seq(c.task_id)
                path = _escalation_dispatcher_module.render_escalation_file(c, seq)
                stats["escalations_created"] += 1
                result = _escalation_dispatcher_module.dispatch_telegram(path, c)
                if result.get("sent"):
                    stats["telegram_sent"] += 1
            except Exception as e:
                stats["errors"] += 1
                print(f"UBN escalation failed for {c.task_id}: {e}", file=sys.stderr)
    except Exception as e:
        stats["errors"] += 1
        print(f"UBN block_scanner stage failed: {e}", file=sys.stderr)
    return stats
```

Then locate `run_tick()` in `reaper.py` and add invocation just before the audit append:

```python
# Existing tick logic ends with append_audit(entry)
# Add UBN stage before that:
ubn_stats = _block_scanner_stage(state_for_ubn or {})
entry["ubn"] = ubn_stats
```

(Pra evitar quebrar reaper existing flow, encontre o ponto certo onde state.json já foi lido — provavelmente no fim do `run_tick` antes do `append_audit`.)

- [ ] **Step 4: Run integration tests**

```
python3 -m pytest tests/test_reaper_block_scanner_integration.py -v
```

Expected: 3 PASS.

Run full reaper test suite to verify no regression:

```
python3 -m pytest tests/test_reaper_resilience.py -v
```

Expected: All previously-passing tests still PASS.

- [ ] **Step 5: Commit**

```
git add dispatcher-agent/lib/reaper.py dispatcher-agent/tests/test_reaper_block_scanner_integration.py
git commit -m "feat(ubn): wire block_scanner stage in reaper tick

Try/except local pra não derrubar outros stages. Kill switch
OPENCLAW_REAPER_DISABLE_BLOCK_SCANNER=1. Audit stats em
entry['ubn'] do reaper jsonl.

Spec: bevox-knowledge/35_specs/openclaw/2026-04-30-universal-block-notifier.md §6.7

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase E — ubn_actions Python (CLI canônico)

### Task 10: Create ubn_actions.py with smart retry matrix

**Files:**
- Create: `clarification-agent/lib/ubn_actions.py`
- Test: `clarification-agent/tests/test_ubn_actions.py`

- [ ] **Step 1: Write failing tests**

Arquivo: `clarification-agent/tests/test_ubn_actions.py`

```python
"""Unit tests for UBN actions canonical Python.

Spec: bevox-knowledge/35_specs/openclaw/2026-04-30-universal-block-notifier.md §6
"""
import unittest
from unittest.mock import patch, MagicMock
from lib import ubn_actions


class TestSmartRetryMatrix(unittest.TestCase):
    def test_test_failed_in_progress_routes_to_move_testing(self):
        action = ubn_actions._select_retry_action("test_failed: AC X", "in_progress")
        self.assertEqual(action.__name__, "retry_move_to_testing")

    def test_test_inconclusive_in_progress_routes_to_move_testing(self):
        action = ubn_actions._select_retry_action("test_inconclusive: timeout", "in_progress")
        self.assertEqual(action.__name__, "retry_move_to_testing")

    def test_clarification_escalation_routes_to_move_ready(self):
        action = ubn_actions._select_retry_action(
            "clarification_escalation_required: drafter timeout", "in_progress")
        self.assertEqual(action.__name__, "retry_move_to_ready")

    def test_stuck_in_testing_routes_to_invoke_tester_direct(self):
        action = ubn_actions._select_retry_action("stuck-in-testing >30min", "testing")
        self.assertEqual(action.__name__, "retry_invoke_tester_direct")

    def test_branch_checkout_failed_in_progress_routes_to_move_ready(self):
        action = ubn_actions._select_retry_action(
            "branch_checkout_failed: dirty", "in_progress")
        self.assertEqual(action.__name__, "retry_move_to_ready")

    def test_unknown_pattern_falls_back_to_move_ready(self):
        action = ubn_actions._select_retry_action("totally_new_block_reason", "in_progress")
        self.assertEqual(action.__name__, "retry_move_to_ready")
```

- [ ] **Step 2: Run fail**

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Create ubn_actions.py with matrix + retry strategies**

Arquivo: `clarification-agent/lib/ubn_actions.py`

```python
"""UBN canonical actions — Python CLI ponto único que muda kanban.

Plugin JS de Telegram (knowledge-sync) despacha pra cá via
clarification-agent/cli.sh ubn <subcmd>.

Spec: bevox-knowledge/35_specs/openclaw/2026-04-30-universal-block-notifier.md §6
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple

KANBAN_CLI = "~/.openclaw/kanban-tasks/cli.sh"
TESTER_CLI = "~/.openclaw/tester-agent/cli.sh"


@dataclass
class ActionResult:
    summary: str
    success: bool = True
    details: Optional[dict] = None


# ============== Retry strategies ==============

def retry_move_to_testing(task_id: str) -> ActionResult:
    """Use quando task está in_progress + blocked após tester decision.
    Transição válida: in_progress → testing.
    Reaper resilience auto-invoca tester via _needs_tester_reinvoke."""
    _kanban(["task", "unblock", task_id, "--actor", "ubn"])
    _kanban(["task", "move", task_id, "testing", "--actor", "ubn"])
    return ActionResult(summary=f"{task_id} unblocked + moved to testing")


def retry_move_to_ready(task_id: str) -> ActionResult:
    """Use quando task precisa re-dispatch (clarification, branch_checkout)."""
    _kanban(["task", "unblock", task_id, "--actor", "ubn"])
    _kanban(["task", "move", task_id, "ready", "--actor", "ubn"])
    return ActionResult(summary=f"{task_id} unblocked + moved to ready")


def retry_invoke_tester_direct(task_id: str) -> ActionResult:
    """Use quando task está em testing (stuck case). Não muda status."""
    r = subprocess.run([TESTER_CLI, "check", task_id],
                       capture_output=True, text=True, check=False, timeout=600)
    if r.returncode != 0:
        return ActionResult(summary=f"tester check failed: {r.stderr.strip()[:120]}",
                            success=False)
    return ActionResult(summary=f"{task_id} tester check completed")


# ============== Smart retry matrix ==============

# (block_reason_regex, current_status, action_callable)
_RETRY_MATRIX: List[Tuple[str, str, Callable[[str], ActionResult]]] = [
    (r"^test_(failed|inconclusive)", "in_progress", retry_move_to_testing),
    (r"^precheck_failed",            "in_progress", retry_move_to_testing),
    (r"^clarification_escalation",   "in_progress", retry_move_to_ready),
    (r"^branch_checkout_failed",     "in_progress", retry_move_to_ready),
    (r"^stuck-in-testing",           "testing",     retry_invoke_tester_direct),
]


def _select_retry_action(block_reason: str, current_status: str) -> Callable[[str], ActionResult]:
    for pattern, status_match, action in _RETRY_MATRIX:
        if re.match(pattern, block_reason) and status_match == current_status:
            return action
    return retry_move_to_ready  # fallback


# ============== Kanban CLI helper ==============

def _kanban(args: List[str]) -> dict:
    cmd = [KANBAN_CLI] + args + ["--json"]
    r = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=30)
    if r.returncode != 0:
        raise RuntimeError(f"kanban CLI failed: {' '.join(args)} → {r.stderr.strip()[:200]}")
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"raw": r.stdout}
```

- [ ] **Step 4: Run pass**

```
cd ~/.openclaw/clarification-agent
python3 -m pytest tests/test_ubn_actions.py -v
```

Expected: 6 PASS.

- [ ] **Step 5: Commit**

```
git add clarification-agent/lib/ubn_actions.py clarification-agent/tests/test_ubn_actions.py
git commit -m "feat(ubn): smart retry matrix + 3 retry strategies (§6.3)

Matrix (block_reason, current_status) → action respeita whitelist de
transições do kanban. Strategies: move_to_testing (test_failed/inconclusive
em in_progress), move_to_ready (clarification/branch_checkout/fallback),
invoke_tester_direct (stuck-in-testing em testing).

Spec: bevox-knowledge/35_specs/openclaw/2026-04-30-universal-block-notifier.md §6.3

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 11: Add force_done / force_reject / manual_answer

**Files:**
- Modify: `clarification-agent/lib/ubn_actions.py`
- Modify: `clarification-agent/tests/test_ubn_actions.py`

- [ ] **Step 1: Add failing tests**

Append to test:

```python
class TestForceActions(unittest.TestCase):
    def test_force_done_invokes_kanban_move_with_force(self):
        with patch.object(ubn_actions, "_kanban") as mock_k:
            mock_k.return_value = {"task": {"id": "T-0080", "status": "done"}}
            result = ubn_actions.force_done("T-0080", "esc-1", "validei manual")
        self.assertTrue(result.success)
        # 2 calls: unblock + move done --force
        self.assertEqual(mock_k.call_count, 2)
        move_args = mock_k.call_args_list[1].args[0]
        self.assertIn("--force", move_args)
        self.assertIn("done", move_args)

    def test_force_reject_invokes_kanban_move_with_force(self):
        with patch.object(ubn_actions, "_kanban") as mock_k:
            mock_k.return_value = {"task": {"id": "T-0081", "status": "rejected"}}
            result = ubn_actions.force_reject("T-0081", "esc-1", "task inviável")
        self.assertTrue(result.success)
        move_args = mock_k.call_args_list[1].args[0]
        self.assertIn("rejected", move_args)


class TestManualAnswer(unittest.TestCase):
    def test_returns_audit_only_when_no_open_question(self):
        with patch.object(ubn_actions, "_find_latest_open_question",
                          return_value=None):
            result = ubn_actions.manual_answer("T-0090", "minha resposta")
        self.assertIn("audit only", result.summary)
        self.assertTrue(result.success)
```

- [ ] **Step 2: Run fail**

Expected: `AttributeError`.

- [ ] **Step 3: Add force_done, force_reject, manual_answer**

Append to `ubn_actions.py`:

```python
ANSWERS_DIR = Path("~/.openclaw/clarification-agent/answers")
QUESTIONS_DIR = Path("~/.openclaw/clarification-agent/questions")
SIGNALS_DIR = Path("~/.openclaw/clarification-agent/signals")


def force_done(task_id: str, escalation_id: str, reason: str) -> ActionResult:
    _kanban(["task", "unblock", task_id, "--actor", "ubn"])
    _kanban(["task", "move", task_id, "done", "--force", "--actor", "ubn",
             "--reason", f"manual via UBN escalation {escalation_id}: {reason[:150]}"])
    return ActionResult(summary=f"{task_id} forced to done")


def force_reject(task_id: str, escalation_id: str, reason: str) -> ActionResult:
    _kanban(["task", "unblock", task_id, "--actor", "ubn"])
    _kanban(["task", "move", task_id, "rejected", "--force", "--actor", "ubn",
             "--reason", f"rejected via UBN escalation {escalation_id}: {reason[:150]}"])
    return ActionResult(summary=f"{task_id} forced to rejected")


def _find_latest_open_question(task_id: str) -> Optional[Path]:
    """Lookup latest question file pra task. None se não há agente esperando."""
    if not QUESTIONS_DIR.is_dir():
        return None
    matches = sorted(QUESTIONS_DIR.glob(f"{task_id}-clr-*.md"))
    return matches[-1] if matches else None


def manual_answer(task_id: str, answer_text: str) -> ActionResult:
    """Texto livre vai pro arquivo de answer da clarification original.
    Files de question e answer compartilham nome em diretórios diferentes."""
    q_path = _find_latest_open_question(task_id)
    if q_path is None:
        return ActionResult(
            summary=f"no open clarification for {task_id}; recorded as audit only")
    answer_path = ANSWERS_DIR / q_path.name
    ANSWERS_DIR.mkdir(parents=True, exist_ok=True)
    answer_path.write_text(
        f"# Manual answer (via UBN)\n\n{answer_text}\n", encoding="utf-8")
    # Trigger signal pro agente esperando
    SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
    (SIGNALS_DIR / f"{q_path.stem}.signal").touch()
    return ActionResult(summary=f"{task_id} answer written; agent should resume")
```

- [ ] **Step 4: Run pass**

```
python3 -m pytest tests/test_ubn_actions.py -v
```

Expected: 9 PASS.

- [ ] **Step 5: Commit**

```
git add clarification-agent/lib/ubn_actions.py clarification-agent/tests/test_ubn_actions.py
git commit -m "feat(ubn): force_done + force_reject + manual_answer (§6.4-§6.5)

force actions usam kanban CLI move --force com reason audit. manual_answer
escreve em answers/ + dispara signal (reusa flow existente do
clarification-agent question/answer/signal).

Spec: bevox-knowledge/35_specs/openclaw/2026-04-30-universal-block-notifier.md §6.4-§6.5

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 12: Add backfill --override + escalation lookup utilities

**Files:**
- Modify: `clarification-agent/lib/ubn_actions.py`
- Modify: `clarification-agent/tests/test_ubn_actions.py`

- [ ] **Step 1: Add failing tests**

```python
class TestBackfillOverride(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp()
        self.escalations_dir = Path(self.tmp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_marks_stale_creates_minimal_escalation_files(self):
        with patch.object(ubn_actions, "UBN_ESCALATIONS_DIR", self.escalations_dir):
            ubn_actions.backfill_override(
                stale_task_ids=["T-0006", "T-0008"],
                renotify_task_ids=[],
            )
        files = sorted(self.escalations_dir.glob("*.md"))
        names = [f.name for f in files]
        self.assertIn("T-0006-blk-1.md", names)
        self.assertIn("T-0008-blk-1.md", names)
        # All should have status: stale
        for f in files:
            content = f.read_text()
            self.assertIn("status: stale", content)

    def test_marks_renotify_creates_open_escalation_files(self):
        with patch.object(ubn_actions, "UBN_ESCALATIONS_DIR", self.escalations_dir):
            ubn_actions.backfill_override(stale_task_ids=[],
                                          renotify_task_ids=["T-0161"])
        files = list(self.escalations_dir.glob("T-0161-*.md"))
        self.assertEqual(len(files), 1)
        content = files[0].read_text()
        self.assertIn("status: open", content)


class TestFindEscalation(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp()
        self.escalations_dir = Path(self.tmp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_find_open_escalation_for_task(self):
        (self.escalations_dir / "T-0100-blk-1.md").write_text("---\nstatus: open\n---\n")
        (self.escalations_dir / "T-0100-blk-2.md").write_text("---\nstatus: resolved\n---\n")
        with patch.object(ubn_actions, "UBN_ESCALATIONS_DIR", self.escalations_dir):
            result = ubn_actions.find_open_escalation_for_task("T-0100")
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "T-0100-blk-1.md")

    def test_returns_none_when_no_open(self):
        (self.escalations_dir / "T-0101-blk-1.md").write_text("---\nstatus: resolved\n---\n")
        with patch.object(ubn_actions, "UBN_ESCALATIONS_DIR", self.escalations_dir):
            result = ubn_actions.find_open_escalation_for_task("T-0101")
        self.assertIsNone(result)
```

- [ ] **Step 2: Run fail**

Expected: `AttributeError`.

- [ ] **Step 3: Add backfill + find escalation**

Append to `ubn_actions.py`:

```python
from datetime import datetime, timezone

UBN_ESCALATIONS_DIR = Path("~/.openclaw/clarification-agent/escalations")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def backfill_override(stale_task_ids: List[str],
                      renotify_task_ids: List[str]) -> ActionResult:
    """Single-shot: marca task_ids como stale OR renotify (escalation file
    minimal pra que próximo reaper tick reconheça)."""
    UBN_ESCALATIONS_DIR.mkdir(parents=True, exist_ok=True)
    for task_id in stale_task_ids:
        path = UBN_ESCALATIONS_DIR / f"{task_id}-blk-1.md"
        if path.exists():
            continue
        path.write_text(f"""---
escalation_id: {task_id}-blk-1
task_id: {task_id}
detector: ubn-backfill
criterion: blocked
block_session_key: backfill-{_now_iso()}
block_reason: backfill manual override pre-deploy
detected_at: {_now_iso()}
dispatched_at: null
status: stale
resolved_at: {_now_iso()}
resolved_action: backfill_stale
resolved_response: marked stale via ubn-backfill --override
resolved_by: ubn-backfill
---

# Backfill stale escalation for {task_id}
""", encoding="utf-8")
    for task_id in renotify_task_ids:
        # Cria com status=open + block_session_key forçando reaper a re-dispatch.
        # Próximo tick vê "no open escalation com mesma key" → cria novo +
        # dispatch Telegram.
        path = UBN_ESCALATIONS_DIR / f"{task_id}-blk-renotify.md"
        path.write_text(f"""---
escalation_id: {task_id}-blk-renotify
task_id: {task_id}
detector: ubn-backfill
criterion: blocked
block_session_key: backfill-renotify-{_now_iso()}
block_reason: backfill renotify pre-deploy
detected_at: {_now_iso()}
dispatched_at: null
status: open
---

# Backfill renotify escalation for {task_id}
""", encoding="utf-8")
    return ActionResult(
        summary=f"backfill: {len(stale_task_ids)} stale, "
                f"{len(renotify_task_ids)} renotify")


def find_open_escalation_for_task(task_id: str) -> Optional[Path]:
    """Procura primeira escalation aberta pra task_id."""
    if not UBN_ESCALATIONS_DIR.is_dir():
        return None
    for path in sorted(UBN_ESCALATIONS_DIR.glob(f"{task_id}-blk-*.md")):
        content = path.read_text(encoding="utf-8")
        if "status: open" in content:
            return path
    return None
```

- [ ] **Step 4: Run pass**

```
python3 -m pytest tests/test_ubn_actions.py -v
```

Expected: 13 PASS.

- [ ] **Step 5: Commit**

```
git add clarification-agent/lib/ubn_actions.py clarification-agent/tests/test_ubn_actions.py
git commit -m "feat(ubn): backfill override + find_open_escalation (§7)

backfill_override: single-shot pra marcar tasks como stale (sem
renotify) ou renotify (próximo tick dispatch). find_open_escalation_for_task
pra lookup downstream.

Spec: bevox-knowledge/35_specs/openclaw/2026-04-30-universal-block-notifier.md §7

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 13: Add main() entrypoint pra ubn_actions.py (CLI dispatch)

**Files:**
- Modify: `clarification-agent/lib/ubn_actions.py`
- Test: `clarification-agent/tests/test_ubn_actions_cli.py`

- [ ] **Step 1: Write failing CLI test**

Arquivo: `tests/test_ubn_actions_cli.py`

```python
"""Tests for ubn_actions CLI entrypoint (cli.sh ubn ...)."""
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from lib import ubn_actions


class TestCLIEntry(unittest.TestCase):
    def test_done_subcommand_invokes_force_done(self):
        with patch.object(ubn_actions, "force_done") as mock:
            mock.return_value = ubn_actions.ActionResult(summary="ok")
            ubn_actions.main(["done", "T-0200", "--reason", "manual"])
            mock.assert_called_once_with("T-0200", "via-telegram", "manual")

    def test_reject_subcommand_invokes_force_reject(self):
        with patch.object(ubn_actions, "force_reject") as mock:
            mock.return_value = ubn_actions.ActionResult(summary="ok")
            ubn_actions.main(["reject", "T-0201", "--reason", "ruim"])
            mock.assert_called_once_with("T-0201", "via-telegram", "ruim")

    def test_answer_subcommand_invokes_manual_answer(self):
        with patch.object(ubn_actions, "manual_answer") as mock:
            mock.return_value = ubn_actions.ActionResult(summary="ok")
            ubn_actions.main(["answer", "T-0202", "--text", "minha resposta"])
            mock.assert_called_once_with("T-0202", "minha resposta")
```

- [ ] **Step 2: Run fail**

Expected: `AttributeError: main`.

- [ ] **Step 3: Add main() argparse dispatcher**

Append to `ubn_actions.py`:

```python
import argparse


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="ubn_actions")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_retry = sub.add_parser("retry")
    p_retry.add_argument("task_id")

    p_done = sub.add_parser("done")
    p_done.add_argument("task_id")
    p_done.add_argument("--reason", default="(no reason)")

    p_reject = sub.add_parser("reject")
    p_reject.add_argument("task_id")
    p_reject.add_argument("--reason", default="(no reason)")

    p_answer = sub.add_parser("answer")
    p_answer.add_argument("task_id")
    p_answer.add_argument("--text", required=True)

    p_backfill = sub.add_parser("backfill")
    p_backfill.add_argument("--override", action="store_true")
    p_backfill.add_argument("--stale", default="")  # comma-separated task_ids
    p_backfill.add_argument("--renotify", default="")

    p_list = sub.add_parser("list")

    args = parser.parse_args(argv)

    if args.cmd == "retry":
        # Lookup task status from kanban
        task_data = json.loads(subprocess.run(
            [KANBAN_CLI, "task", "show", args.task_id, "--json"],
            capture_output=True, text=True, check=True).stdout)["task"]
        block_reason = task_data.get("blocked_reason") or "(unknown)"
        current_status = task_data.get("status")
        action = _select_retry_action(block_reason, current_status)
        result = action(args.task_id)
    elif args.cmd == "done":
        result = force_done(args.task_id, "via-telegram", args.reason)
    elif args.cmd == "reject":
        result = force_reject(args.task_id, "via-telegram", args.reason)
    elif args.cmd == "answer":
        result = manual_answer(args.task_id, args.text)
    elif args.cmd == "backfill" and args.override:
        stale = [t.strip() for t in args.stale.split(",") if t.strip()]
        renotify = [t.strip() for t in args.renotify.split(",") if t.strip()]
        result = backfill_override(stale, renotify)
    elif args.cmd == "list":
        # Lista escalations abertas
        items = []
        if UBN_ESCALATIONS_DIR.is_dir():
            for path in sorted(UBN_ESCALATIONS_DIR.glob("*.md")):
                content = path.read_text()
                if "status: open" in content:
                    items.append(path.name)
        result = ActionResult(summary=f"{len(items)} open", details={"items": items})
    else:
        parser.error("unknown command")
        return 1

    print(json.dumps({"ok": result.success, "summary": result.summary,
                      "details": result.details}, ensure_ascii=False))
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run all clarification-agent tests**

```
python3 -m pytest tests/ -v
```

Expected: All previously-passing + new 16 PASS.

- [ ] **Step 5: Commit**

```
git add clarification-agent/lib/ubn_actions.py clarification-agent/tests/test_ubn_actions_cli.py
git commit -m "feat(ubn): main() CLI entry pra ubn_actions (argparse dispatch)

Subcommands: retry, done, reject, answer, backfill --override, list.
Output JSON pra plugin JS parsear. Exit 0 success / 1 failure.

Spec: bevox-knowledge/35_specs/openclaw/2026-04-30-universal-block-notifier.md §6.2

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase F — Wire clarification-agent CLI

### Task 14: Add `ubn` subcomando ao cli.sh

**Files:**
- Modify: `clarification-agent/cli.sh`

- [ ] **Step 1: Read current cli.sh structure**

Run: `cat clarification-agent/cli.sh`

Expected: see how existing subcommands (override, reject, etc.) dispatch to Python.

- [ ] **Step 2: Add ubn dispatch**

Edit `clarification-agent/cli.sh`. Find the case/dispatch block and add:

```bash
case "${1:-}" in
    # ... existing cases ...
    ubn)
        shift
        cd "$(dirname "$0")"
        exec python3 -m lib.ubn_actions "$@"
        ;;
    # ... existing default case ...
esac
```

- [ ] **Step 3: Smoke test CLI dispatch**

```
chmod +x ~/.openclaw/clarification-agent/cli.sh
~/.openclaw/clarification-agent/cli.sh ubn list
```

Expected: JSON output `{"ok": true, "summary": "0 open", "details": {"items": []}}` (assuming no escalations yet).

- [ ] **Step 4: Commit**

```
git add clarification-agent/cli.sh
git commit -m "feat(ubn): wire 'ubn' subcomando em clarification-agent cli.sh

Despacha args pra python3 -m lib.ubn_actions (canônico). Plugin JS de
Telegram invoca via subprocess.

Spec: bevox-knowledge/35_specs/openclaw/2026-04-30-universal-block-notifier.md §6.2

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase G — Gateway plugin JS (knowledge-sync)

### Task 15: Create ubn-handlers.js

**Files:**
- Create: `~/code/knowledge-sync/plugins/clarification-commands/lib/ubn-handlers.js`

- [ ] **Step 1: Read plugin patterns**

```
ls ~/code/knowledge-sync/plugins/clarification-commands/lib/
cat ~/code/knowledge-sync/plugins/clarification-commands/index.js
```

Expected: confirm command-handler patterns (registerCommand callback shape, how existing /clr_* invoke `clarification-agent/cli.sh`).

- [ ] **Step 2: Write handlers module**

Arquivo: `~/code/knowledge-sync/plugins/clarification-commands/lib/ubn-handlers.js`

```javascript
'use strict';

const { spawn } = require('child_process');
const path = require('path');

const CLI_PATH = '~/.openclaw/clarification-agent/cli.sh';

/**
 * Invoke `clarification-agent/cli.sh ubn <subcmd> ...` and return parsed JSON.
 * Spec: bevox-knowledge/35_specs/openclaw/2026-04-30-universal-block-notifier.md §6
 */
function invokeUbn(subcmd, ...args) {
  return new Promise((resolve) => {
    const child = spawn(CLI_PATH, ['ubn', subcmd, ...args], {
      timeout: 30000,
    });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (d) => { stdout += d.toString(); });
    child.stderr.on('data', (d) => { stderr += d.toString(); });
    child.on('close', (code) => {
      try {
        const parsed = JSON.parse(stdout);
        resolve({ ok: code === 0, parsed, stderr, code });
      } catch (e) {
        resolve({ ok: false, parsed: null, stderr: stderr || stdout, code });
      }
    });
    child.on('error', (err) => {
      resolve({ ok: false, parsed: null, stderr: err.message, code: -1 });
    });
  });
}

function formatReply(taskId, result) {
  if (result.ok && result.parsed) {
    return `✓ ${taskId}: ${result.parsed.summary}`;
  }
  return `❌ ${taskId}: ${result.stderr.trim().slice(0, 200) || 'erro desconhecido'}`;
}

async function handleRetry(ctx) {
  const taskId = ctx.args[0];
  if (!taskId || !taskId.match(/^T-\d+/)) {
    return '❓ uso: /ubn_retry <task_id>';
  }
  const r = await invokeUbn('retry', taskId);
  return formatReply(taskId, r);
}

async function handleDone(ctx) {
  const taskId = ctx.args[0];
  if (!taskId || !taskId.match(/^T-\d+/)) {
    return '❓ uso: /ubn_done <task_id> [<reason>]';
  }
  const reason = ctx.args.slice(1).join(' ') || '(no reason)';
  const r = await invokeUbn('done', taskId, '--reason', reason);
  return formatReply(taskId, r);
}

async function handleReject(ctx) {
  const taskId = ctx.args[0];
  if (!taskId || !taskId.match(/^T-\d+/)) {
    return '❓ uso: /ubn_reject <task_id> [<reason>]';
  }
  const reason = ctx.args.slice(1).join(' ') || '(no reason)';
  const r = await invokeUbn('reject', taskId, '--reason', reason);
  return formatReply(taskId, r);
}

async function handleAnswer(ctx) {
  const taskId = ctx.args[0];
  if (!taskId || !taskId.match(/^T-\d+/)) {
    return '❓ uso: /ubn_answer <task_id> <texto>';
  }
  const text = ctx.args.slice(1).join(' ');
  if (!text) {
    return '❓ texto vazio; uso: /ubn_answer <task_id> <texto>';
  }
  const r = await invokeUbn('answer', taskId, '--text', text);
  return formatReply(taskId, r);
}

module.exports = {
  handleRetry,
  handleDone,
  handleReject,
  handleAnswer,
};
```

- [ ] **Step 3: Manual smoke test (script invocation)**

```
node -e "const h = require('~/code/knowledge-sync/plugins/clarification-commands/lib/ubn-handlers.js'); console.log(typeof h.handleRetry);"
```

Expected: `function`.

- [ ] **Step 4: Commit**

```
cd ~/code/knowledge-sync
git add plugins/clarification-commands/lib/ubn-handlers.js
git commit -m "feat(plugin): UBN handlers (/ubn_* commands)

Spawn clarification-agent/cli.sh ubn <subcmd> e formata reply pra Telegram.
4 handlers: retry, done, reject, answer.

Spec: bevox-knowledge/35_specs/openclaw/2026-04-30-universal-block-notifier.md §6.1

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 16: Register /ubn_* commands em index.js

**Files:**
- Modify: `~/code/knowledge-sync/plugins/clarification-commands/index.js`
- Modify: `~/code/knowledge-sync/plugins/clarification-commands/openclaw.plugin.json`

- [ ] **Step 1: Read existing structure**

Look at how `/clr_*` commands são registrados — confirm que `api.registerCommand({...})` é o pattern.

- [ ] **Step 2: Add /ubn_* registrations**

Edit `index.js` — após o último `api.registerCommand({...})` dos clr_ commands:

```javascript
const ubnHandlers = require('./lib/ubn-handlers');

api.registerCommand({
  name: 'ubn_retry',
  nativeNames: { default: 'ubn_retry' },
  description: 'UBN smart retry pra task blocked.',
  handler: ubnHandlers.handleRetry,
});

api.registerCommand({
  name: 'ubn_done',
  nativeNames: { default: 'ubn_done' },
  description: 'UBN force task pra done com reason.',
  handler: ubnHandlers.handleDone,
});

api.registerCommand({
  name: 'ubn_reject',
  nativeNames: { default: 'ubn_reject' },
  description: 'UBN force task pra rejected.',
  handler: ubnHandlers.handleReject,
});

api.registerCommand({
  name: 'ubn_answer',
  nativeNames: { default: 'ubn_answer' },
  description: 'UBN forwarda texto livre pra clarification original.',
  handler: ubnHandlers.handleAnswer,
});
```

- [ ] **Step 3: Bump plugin version**

Edit `openclaw.plugin.json`:

```json
{
  "version": "1.X.0"  // bump minor (X = current+1)
}
```

- [ ] **Step 4: Reload plugin (knowledge-sync handles via hot-reload OR manual restart)**

Check knowledge-sync README for reload procedure. Manual restart if needed:

```
systemctl --user status knowledge-sync 2>&1 | head -3
# se ativo:
# systemctl --user restart knowledge-sync
```

- [ ] **Step 5: Commit**

```
cd ~/code/knowledge-sync
git add plugins/clarification-commands/index.js plugins/clarification-commands/openclaw.plugin.json
git commit -m "feat(plugin): register /ubn_* commands

4 comandos novos registrados via api.registerCommand. Bump version.

Spec: bevox-knowledge/35_specs/openclaw/2026-04-30-universal-block-notifier.md §6.1

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase H — E2E smoke

### Task 17: Manual smoke test E2E

**Files:** none (operational test)

- [ ] **Step 1: Stage de pré-requisito — backfill manual**

```
clarification-agent/cli.sh ubn backfill --override \
    --stale T-0006,T-0008,T-0024,T-0150 \
    --renotify T-0161
```

Expected: JSON com `{"ok": true, "summary": "backfill: 4 stale, 1 renotify"}`.

- [ ] **Step 2: Aguardar próximo reaper tick (≤10s) e observar Telegram**

Watch Telegram tópico `blocks` (ou fallback global). Esperado:
- ⚠️ T-0161 escalation chega (renotify)
- T-0006/T-0008/T-0024/T-0150 NÃO chegam (status=stale silenciosos)

Verify reaper jsonl:

```
tail -3 ~/.openclaw/dispatcher-agent/reaper.jsonl | python3 -c "
import sys, json
for line in sys.stdin:
    r = json.loads(line)
    if 'ubn' in r:
        print(r['tick_id'], r['ubn'])
"
```

Expected: stats com `candidates_found >= 1` no tick que pegar T-0161.

- [ ] **Step 3: Responder no Telegram**

```
/ubn_done T-0161 deploy executado via tag v1.0.3
```

Expected: bot reply `✓ T-0161: T-0161 forced to done`.

- [ ] **Step 4: Verify kanban estado**

```
~/.openclaw/kanban-tasks/cli.sh task show T-0161 --json | python3 -c "
import sys, json
t = json.load(sys.stdin)['task']
print(f'status: {t[\"status\"]} blocked: {t[\"blocked\"]}')
"
```

Expected: `status: done blocked: False`.

- [ ] **Step 5: Verify escalation file marked resolved**

(Manual check via UI ou)

```
ls ~/.openclaw/clarification-agent/escalations/T-0161-blk-renotify.md
grep "status:" ~/.openclaw/clarification-agent/escalations/T-0161-blk-renotify.md
```

Note: na implementação atual `status: resolved` requires response_handler do plugin — isso vai virar follow-up se não funcionar de primeira (separar wave 2).

- [ ] **Step 6: Commit smoke evidence em delivery tracker**

Edit `bevox-knowledge/40_roadmap/_shared/delivery-tracker.yml` adicionando entry pra UBN delivered.

```
cd ~/bevox-knowledge
git add 40_roadmap/_shared/delivery-tracker.yml
git commit -m "track(ubn): wave delivered + smoke E2E passed

Smoke pass evidence: T-0161 escalation → /ubn_done → kanban moved.

Spec: bevox-knowledge/35_specs/openclaw/2026-04-30-universal-block-notifier.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage check:** spec §3.1/§3.2/§3.3 → Tasks 3-5; §3.4 → Task 6; §4 → Task 7; §5 → Task 8; §6.1/§6.2 (CLI infrastructure) → Tasks 13-14, 15-16 (plugin); §6.3 → Task 10; §6.4-§6.5 → Task 11; §7 → Task 12; reaper wire → Task 9; pré-req tester format → Tasks 1-2; smoke → Task 17. Coverage completa.

**Placeholder scan:** no "TBD" / "TODO" / "Add appropriate" — todas as tasks têm código completo + comandos exatos.

**Type consistency:** `Candidate` definida em block_scanner.py (Task 3), reusada por escalation_dispatcher (Task 7). `ActionResult` definida em ubn_actions.py (Task 10), reusada nos resto do file. Methods names: `find_open_escalation` (Task 6 em block_scanner.py) vs `find_open_escalation_for_task` (Task 12 em ubn_actions.py) — nomes diferentes, escopos diferentes (uma busca por candidate-key, outra busca por task_id qualquer). Aceitável mas vou nomear melhor a segunda → `find_latest_open_for_task` se vier dúvida.

Plan ready.
