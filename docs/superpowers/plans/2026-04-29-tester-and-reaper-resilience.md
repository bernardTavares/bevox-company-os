# Tester + Reaper Resilience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tornar tester+reaper resilientes contra 3 bugs do `claude -p` / dispatcher state machine: (A) subprocess que não exit após terminar, (B) tester lendo execution.log com buffer perdido, (C) `post_action_applied` permanente que impede re-invocação do tester quando task volta pra testing.

**Architecture:** `tester-agent/lib/context_loader.py` ganha `load_session_evidence()` que lê `~/.claude/projects/<path>/<sess>.jsonl` (canonical Claude session) como fonte primária, `execution.log` vira fallback. `dispatcher-agent/lib/reaper.py` `classify_execution()` ganha 2 estados novos: `idle_finalize` (subprocess vivo + JSONL idle >3min → SIGINT ladder) e `needs_reinvoke` (task=testing + last inconclusive + backoff expirou → reset post_action). Backoff exponencial geometric 3x cap 10min controla loop.

**Tech Stack:** Python 3.13, `unittest` (framework já usado), `subprocess`, `signal`, `json`, `pathlib`. Sem deps novas.

**Spec:** `~/.openclaw/docs/superpowers/specs/2026-04-29-tester-and-reaper-resilience-vs-claude-cli-bugs.md` (commit `dc63731`)

---

## File Structure

### Modificados

| Arquivo | Responsabilidade |
|---|---|
| `tester-agent/lib/context_loader.py` | Adicionar `claude_project_dir`, `load_session_evidence`, `load_evidence`. Modificar `build_test_context` para usar `load_evidence`. |
| `dispatcher-agent/lib/reaper.py` | Adicionar `_detect_idle_finalize`, `_needs_tester_reinvoke`, `_backoff_delay_for`, `_idle_finalize_action`. Modificar `classify_execution` (signature ganha kwargs + 2 estados). Modificar `run_tick` (carrega kanban_state, branches novos). |
| `dispatcher-agent/lib/store.py` | Reusar `write_execution_status` (já existe). Sem mudança. |

### Criados

| Arquivo | Conteúdo |
|---|---|
| `tester-agent/tests/__init__.py` | Empty (pacote tests) |
| `tester-agent/tests/test_session_evidence.py` | Tests para `claude_project_dir`, `load_session_evidence`, `load_evidence` |
| `dispatcher-agent/tests/test_reaper_resilience.py` | Tests para `_detect_idle_finalize`, `_needs_tester_reinvoke`, `_backoff_delay_for`, `classify_execution` matriz |

### NÃO tocados

`runner.py`, `cron.py`, `selector.py`, `lifecycle.py`, `tester-agent/lib/{api,checker,prechecks,safety,store}.py`, notifier, clarification-agent, plugin Node, scrum-master, mission-control, kanban-tasks, projects-meta.json.

---

## Test Conventions

Framework: `unittest` (consistente com outros agents). Comando-padrão:

```bash
cd ~/.openclaw/<agent-dir> && python3 -m unittest tests.<test_file> -v
```

Para subset: `python3 -m unittest tests.test_X.TestY.test_specific -v`. Imports: `from lib import <module>` (cwd = `<agent-dir>/`).

---

## Task 1 — Phase 0: Branch

**Files:**
- (state change only — branch criação)

- [ ] **Step 1: Verify clean working tree em `~/.openclaw`**

```bash
cd ~/.openclaw && git status --short
```
Expected: empty (ou só untracked não-relevantes). Se houver modificações não-commitadas, parar e investigar.

- [ ] **Step 2: Create + checkout feature branch**

```bash
cd ~/.openclaw
git checkout -b feat/tester-reaper-resilience
git branch --show-current
```
Expected: `feat/tester-reaper-resilience`

- [ ] **Step 3: Confirm spec presente como referência**

```bash
ls -la docs/superpowers/specs/2026-04-29-tester-and-reaper-resilience-vs-claude-cli-bugs.md
```
Expected: file exists (~21KB, commit `dc63731` antes do branch).

- [ ] **Step 4: Sem commit nesta task** — só branch.

---

## Task 2 — Phase 1: `claude_project_dir` helper + tests

**Files:**
- Create: `~/.openclaw/tester-agent/tests/__init__.py` (empty)
- Create: `~/.openclaw/tester-agent/tests/test_session_evidence.py`
- Modify: `~/.openclaw/tester-agent/lib/context_loader.py` (append helper)

- [ ] **Step 1: Create empty tests __init__.py**

```bash
mkdir -p ~/.openclaw/tester-agent/tests
touch ~/.openclaw/tester-agent/tests/__init__.py
```

- [ ] **Step 2: Write failing tests for `claude_project_dir`**

Create `~/.openclaw/tester-agent/tests/test_session_evidence.py`:

```python
"""Tests for claude_project_dir + load_session_evidence + load_evidence."""
import unittest

from lib import context_loader


class TestClaudeProjectDir(unittest.TestCase):
    def test_simple_path(self):
        self.assertEqual(
            context_loader.claude_project_dir("~/code/bevox-site"),
            "-home-you-code-bevox-site",
        )

    def test_home_path(self):
        self.assertEqual(
            context_loader.claude_project_dir("~"),
            "-home-you",
        )

    def test_tilde_expansion(self):
        # ~ expande para $HOME (=~ nos testes)
        result = context_loader.claude_project_dir("~/code/bevox-site")
        self.assertEqual(result, "-home-you-code-bevox-site")

    def test_trailing_slash_stripped(self):
        self.assertEqual(
            context_loader.claude_project_dir("~/code/bevox-site/"),
            "-home-you-code-bevox-site",
        )

    def test_root_path(self):
        self.assertEqual(context_loader.claude_project_dir("/"), "-")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd ~/.openclaw/tester-agent && python3 -m unittest tests.test_session_evidence -v
```
Expected: FAIL — `AttributeError: module 'lib.context_loader' has no attribute 'claude_project_dir'`

- [ ] **Step 4: Implement `claude_project_dir` in context_loader.py**

Append to `~/.openclaw/tester-agent/lib/context_loader.py` (after existing functions, before any if-main block):

```python
def claude_project_dir(project_path: str) -> str:
    """Encode local project path to Claude CLI's project dir naming.

    Example: '~/code/bevox-site' → '-home-you-code-bevox-site'

    Claude CLI stores per-project sessions in
    ~/.claude/projects/<encoded_path>/<session_id>.jsonl, where <encoded_path>
    is the absolute path with '/' replaced by '-' and trailing slash stripped.
    """
    import os
    expanded = os.path.expanduser(project_path or "/")
    encoded = expanded.replace("/", "-").rstrip("-")
    if not encoded:
        encoded = "-"
    return encoded
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd ~/.openclaw/tester-agent && python3 -m unittest tests.test_session_evidence.TestClaudeProjectDir -v
```
Expected: 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
cd ~/.openclaw
git add tester-agent/lib/context_loader.py tester-agent/tests/__init__.py tester-agent/tests/test_session_evidence.py
git commit -m "$(cat <<'EOF'
feat(context_loader): add claude_project_dir helper

Encodes local project paths to Claude CLI session dir naming
('~/code/bevox-site' -> '-home-you-code-bevox-site').
Used by load_session_evidence (next task) to locate per-project
session jsonl files.

5 tests pass: simple, home, tilde, trailing slash, root.

Part of tester-reaper-resilience spec (2026-04-29).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3 — Phase 2: `load_session_evidence` + tests

**Files:**
- Modify: `~/.openclaw/tester-agent/lib/context_loader.py` (append function)
- Modify: `~/.openclaw/tester-agent/tests/test_session_evidence.py` (extend)

- [ ] **Step 1: Add failing tests for `load_session_evidence`**

Append to `~/.openclaw/tester-agent/tests/test_session_evidence.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TestLoadSessionEvidence(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        # Mock structure: ~/.claude/projects/-home-you-code-bevox-site/<sess>.jsonl
        self.proj_dir = self.tmp / "projects" / "-home-you-code-bevox-site"
        self.proj_dir.mkdir(parents=True)
        self.session_id = "abc1234-def5-6789-aaaa-bbbbccccdddd"
        self.session_path = self.proj_dir / f"{self.session_id}.jsonl"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_session(self, lines):
        with open(self.session_path, "w", encoding="utf-8") as f:
            for line in lines:
                f.write(json.dumps(line) + "\n")

    def test_returns_none_when_jsonl_missing(self):
        with patch.object(context_loader, "_claude_projects_root",
                          return_value=self.tmp / "projects"):
            result = context_loader.load_session_evidence(
                "nonexistent-session", "~/code/bevox-site",
            )
        self.assertIsNone(result)

    def test_parses_valid_jsonl_with_assistant_text(self):
        self._write_session([
            {"type": "user", "message": {"role": "user", "content": "hi"}},
            {"type": "assistant", "timestamp": "2026-04-29T10:00:00Z",
             "message": {"role": "assistant", "model": "claude-opus-4-7",
                         "content": [{"type": "text", "text": "Done"}]}},
        ])
        with patch.object(context_loader, "_claude_projects_root",
                          return_value=self.tmp / "projects"):
            result = context_loader.load_session_evidence(
                self.session_id, "~/code/bevox-site",
            )
        self.assertIsNotNone(result)
        self.assertEqual(result["session_id"], self.session_id)
        self.assertEqual(result["final_assistant_text"], "Done")
        self.assertEqual(result["model"], "claude-opus-4-7")
        self.assertEqual(result["raw_lines_count"], 2)
        self.assertEqual(result["source"], "jsonl")

    def test_extracts_tool_uses_and_files_touched(self):
        self._write_session([
            {"type": "assistant", "timestamp": "2026-04-29T10:00:00Z",
             "message": {"role": "assistant", "content": [
                 {"type": "tool_use", "name": "Write",
                  "input": {"file_path": "/tmp/foo.txt", "content": "x"}},
                 {"type": "tool_use", "name": "Edit",
                  "input": {"file_path": "/tmp/bar.py", "old_string": "a", "new_string": "b"}},
                 {"type": "tool_use", "name": "Read",
                  "input": {"file_path": "/tmp/baz.md"}},
             ]}},
        ])
        with patch.object(context_loader, "_claude_projects_root",
                          return_value=self.tmp / "projects"):
            result = context_loader.load_session_evidence(
                self.session_id, "~/code/bevox-site",
            )
        self.assertEqual(len(result["tool_uses"]), 3)
        # files_touched: só Write/Edit (não Read)
        self.assertIn("/tmp/foo.txt", result["files_touched"])
        self.assertIn("/tmp/bar.py", result["files_touched"])
        self.assertNotIn("/tmp/baz.md", result["files_touched"])

    def test_handles_corrupt_lines_gracefully(self):
        # write some valid lines + one corrupt
        with open(self.session_path, "w") as f:
            f.write(json.dumps({"type": "user",
                                "message": {"role": "user", "content": "hi"}}) + "\n")
            f.write("CORRUPTED LINE NOT JSON\n")
            f.write(json.dumps({"type": "assistant",
                                "timestamp": "2026-04-29T10:00:00Z",
                                "message": {"role": "assistant",
                                            "content": [{"type": "text", "text": "ok"}]}}) + "\n")
        with patch.object(context_loader, "_claude_projects_root",
                          return_value=self.tmp / "projects"):
            result = context_loader.load_session_evidence(
                self.session_id, "~/code/bevox-site",
            )
        self.assertIsNotNone(result)
        self.assertEqual(result["final_assistant_text"], "ok")
        self.assertEqual(result["raw_lines_count"], 3)

    def test_returns_none_when_only_corrupt(self):
        with open(self.session_path, "w") as f:
            f.write("not json\n")
            f.write("also not json\n")
        with patch.object(context_loader, "_claude_projects_root",
                          return_value=self.tmp / "projects"):
            result = context_loader.load_session_evidence(
                self.session_id, "~/code/bevox-site",
            )
        self.assertIsNone(result)

    def test_empty_final_text_when_only_user_messages(self):
        self._write_session([
            {"type": "user", "message": {"role": "user", "content": "hi"}},
            {"type": "user", "message": {"role": "user", "content": "ping"}},
        ])
        with patch.object(context_loader, "_claude_projects_root",
                          return_value=self.tmp / "projects"):
            result = context_loader.load_session_evidence(
                self.session_id, "~/code/bevox-site",
            )
        self.assertIsNotNone(result)
        self.assertEqual(result["final_assistant_text"], "")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/.openclaw/tester-agent && python3 -m unittest tests.test_session_evidence.TestLoadSessionEvidence -v
```
Expected: 6 tests FAIL — `AttributeError: module 'lib.context_loader' has no attribute 'load_session_evidence'`

- [ ] **Step 3: Implement `load_session_evidence` in context_loader.py**

Append to `~/.openclaw/tester-agent/lib/context_loader.py`:

```python
def _claude_projects_root() -> Path:
    """Return ~/.claude/projects (overridable in tests via patch)."""
    return Path.home() / ".claude" / "projects"


def load_session_evidence(session_id: str,
                          project_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Load Claude session jsonl as evidence dict.

    Reads ~/.claude/projects/<encoded_project_path>/<session_id>.jsonl (full file).
    Tolerates corrupt lines by skipping them. Returns None if file missing,
    completely unparseable, or no valid jsonl entries.

    Returns dict with:
      session_id: str
      model: str | None  (from last assistant message)
      started_at: str | None (timestamp of first message)
      finished_at: str | None (timestamp of last message)
      final_assistant_text: str (concatenated text-type content of last assistant msg)
      tool_uses: list[dict] (all tool_use entries from assistant messages)
      tool_results: list[dict] (all tool_result entries)
      files_touched: list[str] (file_path from Write/Edit tool_use entries)
      raw_lines_count: int (total lines processed, including skipped corrupt)
      source: "jsonl"
    """
    import json as _json
    if not session_id:
        return None
    project = project_path or str(Path.home())
    proj_dir = _claude_projects_root() / claude_project_dir(project)
    session_path = proj_dir / f"{session_id}.jsonl"
    if not session_path.is_file():
        return None
    try:
        with open(session_path, "r", encoding="utf-8") as f:
            raw_lines = f.readlines()
    except OSError:
        return None

    parsed = []
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        try:
            parsed.append(_json.loads(line))
        except _json.JSONDecodeError:
            continue
    if not parsed:
        return None

    final_assistant = None
    tool_uses: List[Dict[str, Any]] = []
    tool_results: List[Dict[str, Any]] = []
    files_touched: List[str] = []
    started_at = None
    finished_at = None

    for entry in parsed:
        ts = entry.get("timestamp")
        if ts and started_at is None:
            started_at = ts
        if ts:
            finished_at = ts
        msg = entry.get("message") or {}
        role = msg.get("role")
        content = msg.get("content") or []
        if not isinstance(content, list):
            continue
        for c in content:
            if not isinstance(c, dict):
                continue
            t = c.get("type")
            if t == "tool_use" and role == "assistant":
                tool_uses.append(c)
                if c.get("name") in ("Write", "Edit", "NotebookEdit"):
                    fp = (c.get("input") or {}).get("file_path")
                    if fp and fp not in files_touched:
                        files_touched.append(fp)
            elif t == "tool_result":
                tool_results.append(c)
        if role == "assistant":
            final_assistant = entry

    final_text = ""
    final_model = None
    if final_assistant:
        msg = final_assistant.get("message") or {}
        final_model = msg.get("model")
        for c in (msg.get("content") or []):
            if isinstance(c, dict) and c.get("type") == "text":
                final_text += c.get("text", "")

    return {
        "session_id": session_id,
        "model": final_model,
        "started_at": started_at,
        "finished_at": finished_at,
        "final_assistant_text": final_text,
        "tool_uses": tool_uses,
        "tool_results": tool_results,
        "files_touched": files_touched,
        "raw_lines_count": len(parsed),
        "source": "jsonl",
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ~/.openclaw/tester-agent && python3 -m unittest tests.test_session_evidence -v
```
Expected: 11 tests PASS (5 do TestClaudeProjectDir + 6 do TestLoadSessionEvidence).

- [ ] **Step 5: Commit**

```bash
cd ~/.openclaw
git add tester-agent/lib/context_loader.py tester-agent/tests/test_session_evidence.py
git commit -m "$(cat <<'EOF'
feat(context_loader): add load_session_evidence (Claude jsonl reader)

Reads ~/.claude/projects/<encoded_path>/<session>.jsonl as the canonical
source of truth for what Claude actually did during a task. Extracts
final assistant text, tool_use list, tool_results, and files_touched
(from Write/Edit/NotebookEdit). Tolerant to corrupt lines (per-line
try/except).

Returns None graciously when jsonl missing or completely unparseable.

6 tests cover: missing file, valid parse, tool_use + files_touched
extraction, corrupt lines mixed with valid, all-corrupt, only-user
(empty final_text).

Part of tester-reaper-resilience spec (Bug B fix — fonte canônica
substitui execution.log fraca).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4 — Phase 3: `load_evidence` wrapper + tests

**Files:**
- Modify: `~/.openclaw/tester-agent/lib/context_loader.py` (append wrapper)
- Modify: `~/.openclaw/tester-agent/tests/test_session_evidence.py` (extend)

- [ ] **Step 1: Add failing tests for `load_evidence` wrapper**

Append to `~/.openclaw/tester-agent/tests/test_session_evidence.py`:

```python
class TestLoadEvidence(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.proj_dir = self.tmp / "projects" / "-home-you-code-bevox-site"
        self.proj_dir.mkdir(parents=True)
        self.session_id = "sess-uuid-1234"
        self.session_path = self.proj_dir / f"{self.session_id}.jsonl"
        # Also mock execution.log dir
        self.exec_dir = self.tmp / "executions"
        self.exec_dir.mkdir(parents=True)
        self.exec_log = self.exec_dir / "T-9999.log"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_uses_jsonl_when_available(self):
        with open(self.session_path, "w") as f:
            f.write(json.dumps({"type": "assistant",
                                "timestamp": "2026-04-29T10:00:00Z",
                                "message": {"role": "assistant",
                                            "content": [{"type": "text", "text": "ok"}]}}) + "\n")
        # exec log also exists with content (should be IGNORED because jsonl wins)
        self.exec_log.write_text("execution log content (should not be used)")

        with patch.object(context_loader, "_claude_projects_root",
                          return_value=self.tmp / "projects"):
            with patch.object(context_loader, "execution_log_path",
                              return_value=self.exec_log):
                result = context_loader.load_evidence(
                    "T-9999", self.session_id, "~/code/bevox-site",
                )
        self.assertEqual(result["evidence_source"], "jsonl")
        self.assertEqual(result["final_assistant_text"], "ok")

    def test_falls_back_to_execution_log_when_jsonl_missing(self):
        # No jsonl created. Exec log has content.
        self.exec_log.write_text("real execution log content here")

        with patch.object(context_loader, "_claude_projects_root",
                          return_value=self.tmp / "projects"):
            with patch.object(context_loader, "execution_log_path",
                              return_value=self.exec_log):
                result = context_loader.load_evidence(
                    "T-9999", self.session_id, "~/code/bevox-site",
                )
        self.assertEqual(result["evidence_source"], "execution_log_fallback")
        self.assertIn("real execution log content", result["execution_log_tail"])

    def test_falls_back_when_session_id_none(self):
        self.exec_log.write_text("fallback content")
        with patch.object(context_loader, "execution_log_path",
                          return_value=self.exec_log):
            result = context_loader.load_evidence("T-9999", None, None)
        self.assertEqual(result["evidence_source"], "execution_log_fallback")

    def test_both_empty_returns_empty_evidence_with_fallback_marker(self):
        # No jsonl, exec log empty
        with patch.object(context_loader, "_claude_projects_root",
                          return_value=self.tmp / "projects"):
            with patch.object(context_loader, "execution_log_path",
                              return_value=self.exec_log):  # exec_log doesn't exist
                result = context_loader.load_evidence("T-9999", "missing", None)
        self.assertEqual(result["evidence_source"], "execution_log_fallback")
        self.assertEqual(result["execution_log_tail"], "")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/.openclaw/tester-agent && python3 -m unittest tests.test_session_evidence.TestLoadEvidence -v
```
Expected: 4 tests FAIL — `AttributeError: module 'lib.context_loader' has no attribute 'load_evidence'`

- [ ] **Step 3: Implement `load_evidence` wrapper**

Append to `~/.openclaw/tester-agent/lib/context_loader.py`:

```python
def load_evidence(task_id: str,
                  session_id: Optional[str] = None,
                  project_path: Optional[str] = None) -> Dict[str, Any]:
    """Load best-available evidence for a task.

    Tries load_session_evidence first (canonical jsonl). Falls back to
    read_execution_log_tail (legacy execution.log) if jsonl missing/empty.

    Always returns a dict with field `evidence_source`:
      - "jsonl" when load_session_evidence succeeded
      - "execution_log_fallback" otherwise

    On fallback, dict carries execution_log_tail (text) instead of
    final_assistant_text/tool_uses/files_touched.
    """
    if session_id:
        evidence = load_session_evidence(session_id, project_path)
        if evidence is not None:
            evidence["evidence_source"] = "jsonl"
            evidence["task_id"] = task_id
            return evidence

    # Fallback: execution log tail (legacy fonte fraca)
    log_tail = read_execution_log_tail(task_id)
    return {
        "task_id": task_id,
        "session_id": session_id,
        "evidence_source": "execution_log_fallback",
        "execution_log_tail": log_tail,
        "execution_log_path": str(execution_log_path(task_id)),
        # legacy compat fields (empty)
        "final_assistant_text": "",
        "tool_uses": [],
        "tool_results": [],
        "files_touched": [],
    }
```

- [ ] **Step 4: Run all tests to verify they pass**

```bash
cd ~/.openclaw/tester-agent && python3 -m unittest tests.test_session_evidence -v
```
Expected: 15 tests PASS (5 + 6 + 4).

- [ ] **Step 5: Commit**

```bash
cd ~/.openclaw
git add tester-agent/lib/context_loader.py tester-agent/tests/test_session_evidence.py
git commit -m "$(cat <<'EOF'
feat(context_loader): load_evidence wrapper (jsonl primary, exec_log fallback)

Wrapper that tries load_session_evidence first (canonical Claude jsonl),
falls back to read_execution_log_tail (legacy execution.log) only when
jsonl missing/empty. Returned dict always carries `evidence_source`
field for audit ('jsonl' or 'execution_log_fallback').

4 new tests cover: jsonl wins when both exist; fallback when jsonl
missing; fallback when session_id None; empty result with marker when
both absent.

Next task uses this wrapper from build_test_context.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5 — Phase 4: `build_test_context` usa `load_evidence`

**Files:**
- Modify: `~/.openclaw/tester-agent/lib/context_loader.py` (`build_test_context`)
- Modify: `~/.openclaw/tester-agent/tests/test_session_evidence.py` (extend)

- [ ] **Step 1: Add failing test for build_test_context with jsonl evidence**

Append to test file:

```python
class TestBuildTestContextEvidence(unittest.TestCase):
    """Verifies build_test_context uses load_evidence (jsonl primary)."""

    def test_carries_evidence_source_field(self):
        """When task has session_id and project, load_evidence is consulted."""
        from unittest.mock import patch, MagicMock
        fake_task = {
            "id": "T-9999",
            "project": "bevox-site",
            "dispatch_payload": {
                "execution_session_id": "fake-sess-uuid",
                "acceptance_criteria": ["AC1"],
            },
        }
        fake_evidence = {
            "task_id": "T-9999",
            "session_id": "fake-sess-uuid",
            "evidence_source": "jsonl",
            "final_assistant_text": "all done",
            "tool_uses": [],
            "tool_results": [],
            "files_touched": [],
        }
        with patch.object(context_loader, "load_task_via_kanban",
                          return_value=fake_task):
            with patch.object(context_loader, "load_evidence",
                              return_value=fake_evidence) as mock_load:
                ctx = context_loader.build_test_context("T-9999")
        self.assertIn("evidence_source", ctx)
        self.assertEqual(ctx["evidence_source"], "jsonl")
        self.assertEqual(ctx["evidence"]["final_assistant_text"], "all done")
        # Verify load_evidence was called with task + session_id
        mock_load.assert_called_once()
        args = mock_load.call_args
        self.assertEqual(args[0][0], "T-9999")
        self.assertEqual(args[0][1], "fake-sess-uuid")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ~/.openclaw/tester-agent && python3 -m unittest tests.test_session_evidence.TestBuildTestContextEvidence -v
```
Expected: FAIL — `KeyError: 'evidence_source'` or similar (build_test_context doesn't carry that field yet).

- [ ] **Step 3: Helper to resolve project_path (lookup local_repo_path)**

Add to `~/.openclaw/tester-agent/lib/context_loader.py` (before `build_test_context`):

```python
def _resolve_project_path(project_slug: Optional[str]) -> Optional[str]:
    """Resolve local repo path for a project slug.

    Checks projects-meta.json:projects.<slug>.local_repo_path; if absent,
    falls back to ~/code/<slug> convention. Returns None if
    project_slug is None (task without project).
    """
    if not project_slug:
        return None
    import json as _json
    meta_path = Path.home() / ".openclaw" / "projects-meta.json"
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = _json.load(f)
        entry = (meta.get("projects") or {}).get(project_slug) or {}
        if isinstance(entry, dict):
            path = entry.get("local_repo_path")
            if path:
                import os as _os
                return _os.path.expanduser(path)
    except (OSError, _json.JSONDecodeError):
        pass
    # Fallback convention
    return f"~/code/{project_slug}"
```

- [ ] **Step 4: Modify `build_test_context` to use load_evidence**

Find the existing `build_test_context` function (~ line 105). Replace the relevant block. Original:

```python
    log_tail = read_execution_log_tail(task_id)
```

Replace with:

```python
    payload = task.get("dispatch_payload") or {}
    session_id = payload.get("execution_session_id")
    project_slug = task.get("project")
    project_path = _resolve_project_path(project_slug)
    evidence = load_evidence(task_id, session_id, project_path)
    log_tail = evidence.get("execution_log_tail", "")
```

(Note: keep `payload = task.get("dispatch_payload") or {}` — the existing line 109 already does this; the goal is to insert session_id/project_path/evidence resolution before `log_tail` is needed.)

Then in the return dict at end of `build_test_context`, add 2 keys:

```python
    return {
        "task": task,
        "dispatch_payload": payload,
        "acceptance_criteria": payload.get("acceptance_criteria") or [],
        "execution_log_tail": log_tail,
        "execution_log_path": str(execution_log_path(task_id)),
        "evidence_source": evidence.get("evidence_source"),  # NEW
        "evidence": evidence,                                 # NEW
        "files_relevant": files_relevant_resolved,
        "files_relevant_unresolved": files_relevant_unresolved,
        "expected_outputs": payload.get("expected_outputs") or [],
        "spec_refs": spec_refs_resolved,
    }
```

- [ ] **Step 5: Run all tests to verify they pass**

```bash
cd ~/.openclaw/tester-agent && python3 -m unittest tests -v
```
Expected: 16 tests PASS (15 + 1 new). No regression in pre-existing tester-agent tests (none yet).

- [ ] **Step 6: Smoke check — invoke tester on existing T-0109 to verify field appears**

```bash
~/.openclaw/tester-agent/cli.sh check T-0109 --json 2>&1 | python3 -c "
import json,sys
# read last JSON object emitted (cli prints multiple)
for line in sys.stdin:
    line = line.strip()
    if line.startswith('{') and 'finished_at' in line:
        try:
            d = json.loads(line)
            ctx = d.get('context') or {}
            print('evidence_source:', ctx.get('evidence_source', 'MISSING'))
            break
        except Exception:
            continue
"
```
Expected: `evidence_source: jsonl` (T-0109 has session 9b6d9a04 in `~/.claude/projects/-home-you-code-bevox-site/`).

If smoke fails (`MISSING` ou execution_log_fallback), investigate before commit. May indicate test_result schema doesn't surface `evidence_source` in cli output — that's OK if internal context has it; check via debug.

- [ ] **Step 7: Commit**

```bash
cd ~/.openclaw
git add tester-agent/lib/context_loader.py tester-agent/tests/test_session_evidence.py
git commit -m "$(cat <<'EOF'
feat(context_loader): build_test_context uses load_evidence (jsonl primary)

build_test_context now resolves session_id (from dispatch_payload) and
project_path (via _resolve_project_path looking up local_repo_path in
projects-meta or falling back to ~/code/<slug>) and calls
load_evidence. Returned dict carries new fields:
- evidence_source: 'jsonl' or 'execution_log_fallback'
- evidence: full evidence dict (session details when jsonl wins)

Pre-existing execution_log_tail field preserved for backward compat
(populated from evidence.execution_log_tail when fallback fires).

1 new test verifies load_evidence is called with correct args and that
build_test_context surfaces evidence_source.

Smoke validated against T-0109 sample session.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6 — Phase 5a: `_backoff_delay_for` + `_needs_tester_reinvoke` + tests

**Files:**
- Modify: `~/.openclaw/dispatcher-agent/lib/reaper.py` (append helpers)
- Create: `~/.openclaw/dispatcher-agent/tests/test_reaper_resilience.py`

- [ ] **Step 1: Write failing tests**

Create `~/.openclaw/dispatcher-agent/tests/test_reaper_resilience.py`:

```python
"""Tests for reaper resilience: backoff, reinvoke, idle finalize, classify matrix."""
import unittest
from datetime import datetime, timezone, timedelta

from lib import reaper


class TestBackoffDelayFor(unittest.TestCase):
    def test_first_retry(self):
        self.assertEqual(reaper._backoff_delay_for(1), 30)

    def test_second_retry(self):
        self.assertEqual(reaper._backoff_delay_for(2), 90)

    def test_third_retry(self):
        self.assertEqual(reaper._backoff_delay_for(3), 300)

    def test_fourth_retry(self):
        self.assertEqual(reaper._backoff_delay_for(4), 600)

    def test_caps_at_5(self):
        self.assertEqual(reaper._backoff_delay_for(5), 600)

    def test_caps_at_100(self):
        self.assertEqual(reaper._backoff_delay_for(100), 600)


def _kanban_task(status="testing", overall="inconclusive", finished_at=None,
                 test_run_count=1):
    return {
        "id": "T-9999",
        "status": status,
        "dispatch_payload": {
            "test_result": {
                "last_test_overall": overall,
                "last_test_finished_at": finished_at,
                "test_run_count": test_run_count,
            }
        }
    }


class TestNeedsTesterReinvoke(unittest.TestCase):
    def test_returns_false_when_status_not_testing(self):
        task = _kanban_task(status="done")
        self.assertFalse(reaper._needs_tester_reinvoke(task, {}))

    def test_returns_false_when_overall_pass(self):
        task = _kanban_task(overall="pass")
        self.assertFalse(reaper._needs_tester_reinvoke(task, {}))

    def test_returns_true_when_no_last_finished_at(self):
        # First chance — no record means re-invoke immediately
        task = _kanban_task(finished_at=None)
        self.assertTrue(reaper._needs_tester_reinvoke(task, {}))

    def test_returns_false_when_backoff_window_active(self):
        # 10s ago, count=1 needs 30s
        recent = (datetime.now(timezone.utc) - timedelta(seconds=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        task = _kanban_task(finished_at=recent, test_run_count=1)
        self.assertFalse(reaper._needs_tester_reinvoke(task, {}))

    def test_returns_true_when_backoff_window_expired_count_1(self):
        # 35s ago, count=1 needs 30s — eligible
        elapsed = (datetime.now(timezone.utc) - timedelta(seconds=35)).strftime("%Y-%m-%dT%H:%M:%SZ")
        task = _kanban_task(finished_at=elapsed, test_run_count=1)
        self.assertTrue(reaper._needs_tester_reinvoke(task, {}))

    def test_returns_false_when_backoff_count_2_window_active(self):
        # 60s ago, count=2 needs 90s
        recent = (datetime.now(timezone.utc) - timedelta(seconds=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
        task = _kanban_task(finished_at=recent, test_run_count=2)
        self.assertFalse(reaper._needs_tester_reinvoke(task, {}))

    def test_returns_true_when_backoff_count_2_window_expired(self):
        # 100s ago, count=2 needs 90s — eligible
        elapsed = (datetime.now(timezone.utc) - timedelta(seconds=100)).strftime("%Y-%m-%dT%H:%M:%SZ")
        task = _kanban_task(finished_at=elapsed, test_run_count=2)
        self.assertTrue(reaper._needs_tester_reinvoke(task, {}))

    def test_handles_malformed_finished_at_gracefully(self):
        task = _kanban_task(finished_at="not-a-timestamp", test_run_count=1)
        # Returns False (defensive — don't re-invoke if can't compute backoff)
        self.assertFalse(reaper._needs_tester_reinvoke(task, {}))
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/.openclaw/dispatcher-agent && python3 -m unittest tests.test_reaper_resilience -v
```
Expected: tests FAIL — `AttributeError: module 'lib.reaper' has no attribute '_backoff_delay_for'`

- [ ] **Step 3: Implement helpers in reaper.py**

Append to `~/.openclaw/dispatcher-agent/lib/reaper.py` (before existing `def run_tick`):

```python
# ----------------------------------------------------------------------------
# Resilience helpers (spec 2026-04-29-tester-and-reaper-resilience)
# ----------------------------------------------------------------------------

import os as _os_resilience  # local alias to avoid clashing existing imports

IDLE_FINALIZE_THRESHOLD_S = int(_os_resilience.environ.get(
    "OPENCLAW_REAPER_IDLE_THRESHOLD", "180"))
GRACE_SIGINT_SECONDS = 15
GRACE_SIGTERM_SECONDS = 15
REINVOKE_BACKOFF_SCHEDULE = {1: 30, 2: 90, 3: 300, 4: 600}


def _backoff_delay_for(retry_count: int) -> int:
    """Geometric ratio 3x with cap at 10min (Bernard decision #4).

    1 -> 30s, 2 -> 90s, 3 -> 300s, 4 -> 600s, 5+ -> 600s (cap).
    """
    return REINVOKE_BACKOFF_SCHEDULE.get(retry_count, 600)


def _parse_iso_safe(ts: str):
    """Parse ISO timestamp tolerating Z suffix; returns datetime or None."""
    from datetime import datetime, timezone
    if not ts or not isinstance(ts, str):
        return None
    try:
        # Handle '...Z' (naive UTC) and explicit offsets
        s = ts.replace("Z", "+00:00") if ts.endswith("Z") else ts
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError):
        return None


def _needs_tester_reinvoke(kanban_task: Dict[str, Any],
                           exec_status: Dict[str, Any]) -> bool:
    """True if kanban indicates task came back to testing AND last test was
    inconclusive AND backoff window expired.

    Used when classify_execution sees finished_at + post_action_applied=True;
    instead of returning 'already_reaped' (legacy), checks if tester needs
    a second chance.
    """
    from datetime import datetime, timezone
    if (kanban_task or {}).get("status") != "testing":
        return False
    tr = ((kanban_task or {}).get("dispatch_payload") or {}).get("test_result") or {}
    if tr.get("last_test_overall") != "inconclusive":
        return False
    last_test_at = tr.get("last_test_finished_at")
    test_count = tr.get("test_run_count", 1)
    if not last_test_at:
        return True  # 1st chance, no prior record
    parsed = _parse_iso_safe(last_test_at)
    if parsed is None:
        return False  # defensive: don't loop on malformed timestamps
    delay_seconds = _backoff_delay_for(test_count)
    elapsed = (datetime.now(timezone.utc) - parsed).total_seconds()
    return elapsed >= delay_seconds
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd ~/.openclaw/dispatcher-agent && python3 -m unittest tests.test_reaper_resilience -v
```
Expected: 14 tests PASS (6 backoff + 8 needs_reinvoke).

- [ ] **Step 5: Verify no regression em outros reaper tests**

```bash
cd ~/.openclaw/dispatcher-agent && python3 -m unittest discover tests/ 2>&1 | tail -5
```
Expected: all PASS exceto 2 pre-existing failures em `test_notifier` (irrelevantes — não tocam reaper).

- [ ] **Step 6: Commit**

```bash
cd ~/.openclaw
git add dispatcher-agent/lib/reaper.py dispatcher-agent/tests/test_reaper_resilience.py
git commit -m "$(cat <<'EOF'
feat(reaper): _backoff_delay_for + _needs_tester_reinvoke helpers

Pure helpers for Bug C fix (reaper post_action_applied permanente):
- _backoff_delay_for(count): geometric 3x, cap 600s. 1->30s, 2->90s,
  3->300s, 4+->600s.
- _needs_tester_reinvoke(kanban_task, exec_status): True if
  status=testing AND last_test_overall=inconclusive AND backoff
  expired. Returns False if status!=testing, pass, or window active.
  Defensive: returns False on malformed last_test_finished_at.
- IDLE_FINALIZE_THRESHOLD_S env override, REINVOKE_BACKOFF_SCHEDULE
  constant.

14 tests cover: backoff schedule (6), needs_reinvoke matrix (8 cases
including no-record/malformed/each backoff level).

Next task wires these into classify_execution.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7 — Phase 5b: `classify_execution` aceita kanban_task + needs_reinvoke branch

**Files:**
- Modify: `~/.openclaw/dispatcher-agent/lib/reaper.py` (`classify_execution`)
- Modify: `~/.openclaw/dispatcher-agent/tests/test_reaper_resilience.py` (extend)

- [ ] **Step 1: Add failing test for new classify behavior**

Append to `tests/test_reaper_resilience.py`:

```python
class TestClassifyExecutionWithKanban(unittest.TestCase):
    def test_already_reaped_when_no_kanban_task_passed(self):
        # Backwards compat: signature without kanban_task still works
        status = {"finished_at": "2026-04-29T10:00:00Z", "post_action_applied": True}
        self.assertEqual(reaper.classify_execution(status), "already_reaped")

    def test_already_reaped_when_kanban_task_done(self):
        status = {"finished_at": "2026-04-29T10:00:00Z", "post_action_applied": True}
        task = _kanban_task(status="done", overall="pass")
        self.assertEqual(reaper.classify_execution(status, kanban_task=task),
                         "already_reaped")

    def test_needs_reinvoke_when_testing_inconclusive_backoff_expired(self):
        from datetime import datetime, timezone, timedelta
        elapsed = (datetime.now(timezone.utc) - timedelta(seconds=35)).strftime("%Y-%m-%dT%H:%M:%SZ")
        status = {"finished_at": "2026-04-29T10:00:00Z", "post_action_applied": True}
        task = _kanban_task(status="testing", overall="inconclusive",
                           finished_at=elapsed, test_run_count=1)
        self.assertEqual(reaper.classify_execution(status, kanban_task=task),
                         "needs_reinvoke")

    def test_already_reaped_when_testing_inconclusive_backoff_active(self):
        from datetime import datetime, timezone, timedelta
        recent = (datetime.now(timezone.utc) - timedelta(seconds=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        status = {"finished_at": "2026-04-29T10:00:00Z", "post_action_applied": True}
        task = _kanban_task(status="testing", overall="inconclusive",
                           finished_at=recent, test_run_count=1)
        # Backoff window not expired — skip
        self.assertEqual(reaper.classify_execution(status, kanban_task=task),
                         "already_reaped")

    def test_needs_lifecycle_unchanged_when_no_post_action(self):
        status = {"finished_at": "2026-04-29T10:00:00Z", "post_action_applied": False}
        task = _kanban_task(status="testing")
        self.assertEqual(reaper.classify_execution(status, kanban_task=task),
                         "needs_lifecycle")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/.openclaw/dispatcher-agent && python3 -m unittest tests.test_reaper_resilience.TestClassifyExecutionWithKanban -v
```
Expected: tests FAIL — `classify_execution()` doesn't accept `kanban_task` keyword arg.

- [ ] **Step 3: Modify `classify_execution` signature + add needs_reinvoke branch**

Find `def classify_execution(status: Dict[str, Any]) -> str:` (around line 103). Replace function:

```python
def classify_execution(status: Dict[str, Any],
                      kanban_task: Optional[Dict[str, Any]] = None,
                      session_jsonl_path: Optional[Path] = None) -> str:
    """Classify execution status into reaper action.

    Returns:
      'idle_finalize'    — alive + JSONL idle > IDLE_FINALIZE_THRESHOLD_S (Bug A)
      'still_running'    — alive + JSONL still active OR session jsonl unavailable
      'needs_reap'       — finished_at == None AND process dead/no pid
      'needs_lifecycle'  — finished_at + NOT post_action_applied
      'needs_reinvoke'   — finished_at + post_action_applied + tester re-needed (Bug C)
      'already_reaped'   — finished_at + post_action_applied + (no re-invoke needed)

    NAO modifica status. Sem side-effects. Sem I/O exceto _detect_idle_finalize
    (which reads jsonl when path provided).

    Backwards compat: kanban_task=None and session_jsonl_path=None preserve
    legacy behavior (5 outcomes, no idle/reinvoke detection).
    """
    pid = status.get("pid")
    if status.get("finished_at") is None:
        if pid and _pid_alive(pid):
            # Bug A check: did Claude already finish but subprocess hangs?
            if session_jsonl_path is not None and _detect_idle_finalize(session_jsonl_path):
                return "idle_finalize"
            return "still_running"
        return "needs_reap"

    if not status.get("post_action_applied"):
        return "needs_lifecycle"

    # Bug C check: task came back to testing after inconclusive
    if kanban_task is not None and _needs_tester_reinvoke(kanban_task, status):
        return "needs_reinvoke"

    return "already_reaped"
```

Note: `_detect_idle_finalize` is referenced but will be implemented in Task 9. Pre-defining a stub:

Add stub before `classify_execution`:

```python
def _detect_idle_finalize(jsonl_path: Optional[Path]) -> bool:
    """Stub: real impl in Task 9. Returns False to preserve legacy behavior."""
    return False
```

(This stub allows classify_execution to compile + pass tests now; Task 9 replaces the stub.)

- [ ] **Step 4: Run all reaper tests**

```bash
cd ~/.openclaw/dispatcher-agent && python3 -m unittest tests.test_reaper_resilience -v
```
Expected: 19 tests PASS (14 prior + 5 new TestClassifyExecutionWithKanban).

```bash
cd ~/.openclaw/dispatcher-agent && python3 -m unittest discover tests/ 2>&1 | tail -5
```
Expected: no new regressions (2 pre-existing notifier failures unchanged).

- [ ] **Step 5: Commit**

```bash
cd ~/.openclaw
git add dispatcher-agent/lib/reaper.py dispatcher-agent/tests/test_reaper_resilience.py
git commit -m "$(cat <<'EOF'
feat(reaper): classify_execution accepts kanban_task + needs_reinvoke branch

Signature extended (backwards compatible — both new args default None):
  classify_execution(status, kanban_task=None, session_jsonl_path=None)

New return value 'needs_reinvoke' fires when finished_at +
post_action_applied=True AND kanban indicates task is back in 'testing'
status with last_test_overall='inconclusive' AND backoff window expired.

_detect_idle_finalize stub added (returns False) to allow signature
extension; real impl in next phase.

5 new tests cover: backwards compat (no kanban arg), kanban=done
(already_reaped), inconclusive+expired (needs_reinvoke), inconclusive
+window active (already_reaped), no post_action (needs_lifecycle
unchanged).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8 — Phase 6: Reaper run_tick branch needs_reinvoke (reset post_action)

**Files:**
- Modify: `~/.openclaw/dispatcher-agent/lib/reaper.py` (`run_tick`)
- Modify: `~/.openclaw/dispatcher-agent/tests/test_reaper_resilience.py` (extend)

- [ ] **Step 1: Inspect run_tick to find the classify-then-action loop**

```bash
sed -n '180,260p' ~/.openclaw/dispatcher-agent/lib/reaper.py
```

Identify the loop where `classify_execution(entry)` is called and stats are appended. The loop will need:
- Pass `kanban_task` (loaded once at top of `run_tick`)
- New branch for `cls == "needs_reinvoke"` that calls `store.write_execution_status` with `post_action_applied=False`, appends audit + stats

- [ ] **Step 2: Add failing integration test**

Append to `tests/test_reaper_resilience.py`:

```python
class TestRunTickReinvokeBranch(unittest.TestCase):
    """Integration: full run_tick honoring needs_reinvoke."""

    def test_reinvoke_resets_post_action_and_records_stat(self):
        from unittest.mock import patch, MagicMock
        from datetime import datetime, timezone, timedelta
        import tempfile
        from pathlib import Path
        import json

        with tempfile.TemporaryDirectory() as td:
            execs_dir = Path(td) / "executions"
            execs_dir.mkdir()
            # Seed an execution.status.json: finished + post_action_applied=True
            status_file = execs_dir / "T-9999.status.json"
            status_file.write_text(json.dumps({
                "task_id": "T-9999",
                "session_id": "T-9999-x",
                "sprint_session_id": "sess-uuid",
                "finished_at": "2026-04-29T10:00:00Z",
                "exit_code": 0,
                "post_action_applied": True,
                "pid": None,
                "run_mode": "detach",
            }))
            lockfile = Path(td) / "reaper.lock"

            # Mock kanban load (T-9999 is in 'testing' + inconclusive 35s ago)
            elapsed = (datetime.now(timezone.utc) - timedelta(seconds=35)).strftime("%Y-%m-%dT%H:%M:%SZ")
            fake_kanban = {"tasks": [{
                "id": "T-9999",
                "status": "testing",
                "project": "bevox-site",
                "dispatch_payload": {
                    "execution_session_id": "sess-uuid",
                    "test_result": {
                        "last_test_overall": "inconclusive",
                        "last_test_finished_at": elapsed,
                        "test_run_count": 1,
                    },
                },
            }]}

            with patch.object(reaper, "_load_kanban_state",
                              return_value=fake_kanban):
                result = reaper.run_tick(
                    trigger="test", dry_run=False,
                    executions_dir=execs_dir, lockfile=lockfile,
                )

        # Verify reinvoke counted in stats
        self.assertGreaterEqual(result.get("reinvoke_scheduled_count", 0), 1)

        # Verify post_action_applied was reset
        post = json.loads(status_file.read_text())
        self.assertFalse(post.get("post_action_applied"))

        # Verify action is recorded
        actions = result.get("actions_per_task", [])
        self.assertTrue(any(a.get("outcome") == "reinvoke_scheduled" for a in actions))
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd ~/.openclaw/dispatcher-agent && python3 -m unittest tests.test_reaper_resilience.TestRunTickReinvokeBranch -v
```
Expected: FAIL — `_load_kanban_state` doesn't exist OR run_tick doesn't honor reinvoke OR stats key missing.

- [ ] **Step 4: Add `_load_kanban_state` helper + extend run_tick**

Add to `~/.openclaw/dispatcher-agent/lib/reaper.py` (before `run_tick`):

```python
KANBAN_STATE = Path("~/.openclaw/kanban-tasks/state.json")


def _load_kanban_state() -> Dict[str, Any]:
    """Load kanban state.json. Returns {} dict on error (degrade gracefully)."""
    import json as _json
    try:
        with open(KANBAN_STATE, "r", encoding="utf-8") as f:
            return _json.load(f) or {}
    except (OSError, _json.JSONDecodeError):
        return {}


def _find_kanban_task(kanban: Dict[str, Any], task_id: str) -> Optional[Dict[str, Any]]:
    for t in (kanban.get("tasks") or []):
        if t.get("id") == task_id:
            return t
    return None
```

Now find `run_tick` (around line 282). Inside `with global_lock(...)` block, after `entries = ...` is loaded but before the loop begins, add:

```python
        kanban_state = _load_kanban_state()
```

Find the `for entry in entries:` loop. Modify the `cls = classify_execution(entry)` call:

```python
            task_id = entry.get("task_id")
            if not task_id:
                continue
            kanban_task = _find_kanban_task(kanban_state, task_id)
            cls = classify_execution(entry, kanban_task=kanban_task,
                                     session_jsonl_path=None)  # session path Phase 7
```

After existing branches for `already_reaped` and `still_running`, add the new branch:

```python
            if cls == "needs_reinvoke":
                # Bug C fix: reset post_action_applied + audit; next tick will
                # see needs_lifecycle and re-invoke tester via existing flow.
                if not dry_run:
                    entry["post_action_applied"] = False
                    store.write_execution_status(task_id, entry)
                stats["reinvoke_scheduled_count"] = stats.get("reinvoke_scheduled_count", 0) + 1
                stats["actions_per_task"].append({
                    "task_id": task_id, "stage": "reinvoke",
                    "outcome": "reinvoke_scheduled",
                    "test_run_id": None,
                })
                append_audit({
                    "tick_id": tick_id,
                    "event": "reinvoke_scheduled",
                    "task_id": task_id,
                    "test_run_count": ((kanban_task or {}).get("dispatch_payload", {})
                                                          .get("test_result", {})
                                                          .get("test_run_count")),
                    "ts": store.now_iso(),
                })
                continue
```

Initialize the new stat key alongside others (find existing `"skipped_already_reaped": 0,` line, add):

```python
        "reinvoke_scheduled_count": 0,
        "idle_finalized_count": 0,
```

(Both — idle_finalized used in Task 10.)

- [ ] **Step 5: Run integration test + all tests**

```bash
cd ~/.openclaw/dispatcher-agent && python3 -m unittest tests.test_reaper_resilience -v
```
Expected: 20 tests PASS.

```bash
cd ~/.openclaw/dispatcher-agent && python3 -m unittest discover tests/ 2>&1 | tail -5
```
Expected: no new regressions.

- [ ] **Step 6: Smoke check live state**

```bash
# Find any task currently in testing+inconclusive
python3 -c "
import json
d = json.load(open('~/.openclaw/kanban-tasks/state.json'))
for t in d.get('tasks', []):
    if t.get('status') == 'testing':
        tr = t.get('dispatch_payload',{}).get('test_result',{}) or {}
        if tr.get('last_test_overall') == 'inconclusive':
            print(t['id'], 'count=', tr.get('test_run_count'),
                  'last=', tr.get('last_test_finished_at'))
"
```
If any task surfaces, force a reaper tick:
```bash
~/.openclaw/dispatcher-agent/cli.sh reap-detached --once 2>&1 | grep -E "reinvoke|reaped"
```
Expected: line `T-XXXX: reinvoke -> reinvoke_scheduled` (if backoff expired).

If no task in that state, skip — test from Step 3 already covers integration logic.

- [ ] **Step 7: Commit**

```bash
cd ~/.openclaw
git add dispatcher-agent/lib/reaper.py dispatcher-agent/tests/test_reaper_resilience.py
git commit -m "$(cat <<'EOF'
feat(reaper): run_tick branches needs_reinvoke + audit event

Bug C fix wiring:
- run_tick loads kanban-state once per tick via _load_kanban_state
  (degrades gracefully to {} on read error — preserves legacy behavior)
- _find_kanban_task helper resolves task by id within kanban state
- classify_execution now called with kanban_task=task (session_jsonl_path
  still None — Phase 7)
- New branch for cls=='needs_reinvoke': sets post_action_applied=False
  via store.write_execution_status, appends actions_per_task entry
  outcome='reinvoke_scheduled', emits audit event 'reinvoke_scheduled'
  with test_run_count, increments stats.reinvoke_scheduled_count.

stats dict gains 2 keys (reinvoke_scheduled_count + idle_finalized_count
— second used Phase 7).

1 integration test covers full run_tick lifecycle: seed
execution.status with post_action=True, mock kanban with task in
testing+inconclusive backoff-expired → run_tick → verify post_action
reset on disk + stat present + action recorded.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9 — Phase 7a: `_detect_idle_finalize` real impl + tests

**Files:**
- Modify: `~/.openclaw/dispatcher-agent/lib/reaper.py` (replace stub from Task 7)
- Modify: `~/.openclaw/dispatcher-agent/tests/test_reaper_resilience.py` (extend)

- [ ] **Step 1: Add failing tests for `_detect_idle_finalize`**

Append to test file:

```python
class TestDetectIdleFinalize(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_jsonl(self, lines):
        from pathlib import Path
        p = Path(self.tmp) / "session.jsonl"
        with open(p, "w") as f:
            for line in lines:
                import json as _json
                f.write(_json.dumps(line) + "\n")
        return p

    def test_returns_false_when_path_none(self):
        self.assertFalse(reaper._detect_idle_finalize(None))

    def test_returns_false_when_file_missing(self):
        from pathlib import Path
        self.assertFalse(reaper._detect_idle_finalize(Path("/nonexistent/file.jsonl")))

    def test_returns_false_when_last_message_is_tool_use(self):
        from datetime import datetime, timezone, timedelta
        old = (datetime.now(timezone.utc) - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        p = self._write_jsonl([
            {"type": "assistant", "timestamp": old,
             "message": {"role": "assistant", "content": [
                 {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
             ]}},
        ])
        # Tool_use means Claude still active — no idle finalize
        self.assertFalse(reaper._detect_idle_finalize(p))

    def test_returns_false_when_last_assistant_text_within_threshold(self):
        from datetime import datetime, timezone, timedelta
        recent = (datetime.now(timezone.utc) - timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        p = self._write_jsonl([
            {"type": "assistant", "timestamp": recent,
             "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]}},
        ])
        # 30s < 180s threshold — not idle yet
        self.assertFalse(reaper._detect_idle_finalize(p))

    def test_returns_true_when_last_assistant_text_idle_above_threshold(self):
        from datetime import datetime, timezone, timedelta
        old = (datetime.now(timezone.utc) - timedelta(seconds=200)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        p = self._write_jsonl([
            {"type": "assistant", "timestamp": old,
             "message": {"role": "assistant", "content": [{"type": "text", "text": "Done"}]}},
        ])
        # 200s > 180s — Claude finalized + idle
        self.assertTrue(reaper._detect_idle_finalize(p))

    def test_returns_false_when_corrupt_lines_only(self):
        from pathlib import Path
        p = Path(self.tmp) / "session.jsonl"
        p.write_text("not json\nalso not json\n")
        self.assertFalse(reaper._detect_idle_finalize(p))

    def test_skips_corrupt_lines_uses_last_valid_assistant(self):
        from datetime import datetime, timezone, timedelta
        old = (datetime.now(timezone.utc) - timedelta(seconds=200)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        from pathlib import Path
        import json as _json
        p = Path(self.tmp) / "session.jsonl"
        with open(p, "w") as f:
            f.write(_json.dumps({"type": "assistant", "timestamp": old,
                                 "message": {"role": "assistant",
                                             "content": [{"type": "text", "text": "old"}]}}) + "\n")
            f.write("CORRUPT LINE\n")
        # Only valid line is old assistant text — should still detect idle
        self.assertTrue(reaper._detect_idle_finalize(p))
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/.openclaw/dispatcher-agent && python3 -m unittest tests.test_reaper_resilience.TestDetectIdleFinalize -v
```
Expected: most FAIL — current `_detect_idle_finalize` is stub returning False.

- [ ] **Step 3: Replace stub `_detect_idle_finalize` with real impl**

Find the stub (added in Task 7):

```python
def _detect_idle_finalize(jsonl_path: Optional[Path]) -> bool:
    """Stub: real impl in Task 9. Returns False to preserve legacy behavior."""
    return False
```

Replace with:

```python
def _detect_idle_finalize(jsonl_path: Optional[Path]) -> bool:
    """True if last assistant msg is text-only (no tool_use) AND idle > threshold.

    Reads jsonl_path full file. Scans backwards for first assistant msg.
    If that message contains tool_use → still active → False.
    Else compute delta_t between message timestamp and now; if > threshold → True.

    Tolerates corrupt lines (per-line try/except). Returns False on missing
    path, missing file, no valid lines, no assistant message, missing
    timestamp, or unparseable timestamp.
    """
    from datetime import datetime, timezone
    import json as _json
    if jsonl_path is None or not jsonl_path.exists():
        return False
    try:
        with open(jsonl_path, "r", encoding="utf-8") as f:
            raw_lines = f.readlines()
    except OSError:
        return False
    last_assistant = None
    for line in reversed(raw_lines):
        line = line.strip()
        if not line:
            continue
        try:
            d = _json.loads(line)
        except _json.JSONDecodeError:
            continue
        msg = d.get("message") or {}
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content") or []
        if not isinstance(content, list):
            continue
        has_tool_use = any(isinstance(c, dict) and c.get("type") == "tool_use"
                           for c in content)
        if has_tool_use:
            return False  # Still in middle of tool chain
        last_assistant = d
        break
    if last_assistant is None:
        return False
    ts = last_assistant.get("timestamp")
    parsed = _parse_iso_safe(ts)
    if parsed is None:
        return False
    delta = (datetime.now(timezone.utc) - parsed).total_seconds()
    return delta > IDLE_FINALIZE_THRESHOLD_S
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ~/.openclaw/dispatcher-agent && python3 -m unittest tests.test_reaper_resilience.TestDetectIdleFinalize -v
```
Expected: 7 tests PASS.

```bash
cd ~/.openclaw/dispatcher-agent && python3 -m unittest discover tests/ 2>&1 | tail -5
```
Expected: no new regressions.

- [ ] **Step 5: Commit**

```bash
cd ~/.openclaw
git add dispatcher-agent/lib/reaper.py dispatcher-agent/tests/test_reaper_resilience.py
git commit -m "$(cat <<'EOF'
feat(reaper): _detect_idle_finalize real impl (replace stub)

Bug A detection: scan jsonl backwards for last assistant message.
If it contains tool_use → still active (False). Else if delta_t since
message timestamp > IDLE_FINALIZE_THRESHOLD_S → True.

Tolerates: missing path, missing file, no valid lines, corrupt lines
(skipped), no assistant message, missing/unparseable timestamp.

7 tests cover: None path, missing file, last msg=tool_use (False),
within threshold (False), idle above threshold (True), only-corrupt
(False), corrupt lines mixed with valid old assistant (True).

classify_execution can now return 'idle_finalize' when subprocess alive
+ JSONL idle. Action handler in next phase.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10 — Phase 7b: `_idle_finalize_action` SIGINT/SIGTERM/SIGKILL ladder + run_tick branch + jsonl path resolution

**Files:**
- Modify: `~/.openclaw/dispatcher-agent/lib/reaper.py` (action helper + run_tick branch)
- Modify: `~/.openclaw/dispatcher-agent/tests/test_reaper_resilience.py` (extend)

- [ ] **Step 1: Add failing tests for ladder**

Append to test file:

```python
class TestIdleFinalizeAction(unittest.TestCase):
    def test_sigint_when_pid_responds(self):
        from unittest.mock import patch, MagicMock
        sent_signals = []
        def fake_kill(pid, sig):
            sent_signals.append(sig)
            # After SIGINT, "subprocess" exits — _pid_alive returns False
            return None

        with patch.object(reaper, "_pid_alive", side_effect=[True, False, False]):
            with patch("os.kill", side_effect=fake_kill):
                with patch("time.sleep"):
                    reaper._idle_finalize_action("T-9999", {"pid": 12345})

        import signal
        self.assertIn(signal.SIGINT, sent_signals)
        # Should NOT escalate to SIGTERM because process exited after SIGINT
        self.assertNotIn(signal.SIGTERM, sent_signals)

    def test_escalates_to_sigterm_then_sigkill(self):
        from unittest.mock import patch
        import signal
        sent = []
        def fake_kill(pid, sig):
            sent.append(sig)

        # Process never dies: _pid_alive always True
        with patch.object(reaper, "_pid_alive", return_value=True):
            with patch("os.kill", side_effect=fake_kill):
                with patch("time.sleep"):
                    reaper._idle_finalize_action("T-9999", {"pid": 12345})

        self.assertEqual(sent, [signal.SIGINT, signal.SIGTERM, signal.SIGKILL])

    def test_no_pid_returns_quietly(self):
        from unittest.mock import patch
        # No pid in status — nothing to signal
        with patch("os.kill") as mock_kill:
            reaper._idle_finalize_action("T-9999", {"pid": None})
        mock_kill.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/.openclaw/dispatcher-agent && python3 -m unittest tests.test_reaper_resilience.TestIdleFinalizeAction -v
```
Expected: FAIL — `_idle_finalize_action` doesn't exist.

- [ ] **Step 3: Implement `_idle_finalize_action`**

Append to `~/.openclaw/dispatcher-agent/lib/reaper.py` (after `_detect_idle_finalize`):

```python
def _idle_finalize_action(task_id: str, status: Dict[str, Any]) -> None:
    """SIGINT → 15s grace → SIGTERM → 15s grace → SIGKILL.

    No-op when no pid. Uses os.kill (works for transient systemd-run units
    spawned by runner.py — pid is the claude-cli subprocess).
    """
    import os as _os
    import signal as _signal
    import time as _time
    pid = status.get("pid")
    if not pid:
        return

    # Stage 1: SIGINT (graceful interrupt; allows flush)
    try:
        _os.kill(pid, _signal.SIGINT)
    except (OSError, ProcessLookupError):
        return  # Already gone

    # Wait for graceful exit
    deadline = _time.monotonic() + GRACE_SIGINT_SECONDS
    while _time.monotonic() < deadline:
        if not _pid_alive(pid):
            return
        _time.sleep(1)

    # Stage 2: SIGTERM (firmer)
    try:
        _os.kill(pid, _signal.SIGTERM)
    except (OSError, ProcessLookupError):
        return

    deadline = _time.monotonic() + GRACE_SIGTERM_SECONDS
    while _time.monotonic() < deadline:
        if not _pid_alive(pid):
            return
        _time.sleep(1)

    # Stage 3: SIGKILL (last resort; OS unconditional)
    try:
        _os.kill(pid, _signal.SIGKILL)
    except (OSError, ProcessLookupError):
        pass
```

- [ ] **Step 4: Add jsonl path resolution + run_tick branch for idle_finalize**

Add helper near `_load_kanban_state`:

```python
def _resolve_session_jsonl_path(kanban_task: Optional[Dict[str, Any]],
                                exec_status: Dict[str, Any]) -> Optional[Path]:
    """Find ~/.claude/projects/<encoded_path>/<session_id>.jsonl.

    Returns None if session_id missing or projects-meta unavailable
    (degrades to no idle_finalize detection — preserves legacy).
    """
    sess_id = (exec_status.get("sprint_session_id")
               or (kanban_task or {}).get("dispatch_payload", {}).get("execution_session_id"))
    if not sess_id:
        return None
    project = (kanban_task or {}).get("project")
    # Default to ~/code/<slug>; fallback $HOME if no project
    if project:
        project_path = f"~/code/{project}"
    else:
        project_path = "~"
    encoded = project_path.replace("/", "-").rstrip("-") or "-"
    return Path.home() / ".claude" / "projects" / encoded / f"{sess_id}.jsonl"
```

Find the `run_tick` loop where `classify_execution(entry, kanban_task=kanban_task, session_jsonl_path=None)` was set in Task 8. Replace `session_jsonl_path=None` with:

```python
            sess_path = _resolve_session_jsonl_path(kanban_task, entry)
            cls = classify_execution(entry, kanban_task=kanban_task,
                                     session_jsonl_path=sess_path)
```

After the `needs_reinvoke` branch, add the `idle_finalize` branch:

```python
            if cls == "idle_finalize":
                if not dry_run:
                    _idle_finalize_action(task_id, entry)
                stats["idle_finalized_count"] = stats.get("idle_finalized_count", 0) + 1
                stats["actions_per_task"].append({
                    "task_id": task_id, "stage": "idle_finalize",
                    "outcome": "idle_finalize_triggered",
                    "test_run_id": None,
                })
                append_audit({
                    "tick_id": tick_id,
                    "event": "idle_finalize_triggered",
                    "task_id": task_id,
                    "pid": entry.get("pid"),
                    "ts": store.now_iso(),
                })
                continue
```

- [ ] **Step 5: Run all tests**

```bash
cd ~/.openclaw/dispatcher-agent && python3 -m unittest tests.test_reaper_resilience -v
```
Expected: 30 tests PASS (20 prior + 3 idle_finalize_action + 7 detect_idle).

```bash
cd ~/.openclaw/dispatcher-agent && python3 -m unittest discover tests/ 2>&1 | tail -5
```
Expected: no new regressions.

- [ ] **Step 6: Commit**

```bash
cd ~/.openclaw
git add dispatcher-agent/lib/reaper.py dispatcher-agent/tests/test_reaper_resilience.py
git commit -m "$(cat <<'EOF'
feat(reaper): _idle_finalize_action ladder + run_tick branch + jsonl path

Bug A action handler:
- _idle_finalize_action(task_id, status): SIGINT → 15s grace → SIGTERM
  → 15s grace → SIGKILL. No-op if pid missing. Tolerates ProcessLookupError
  (already exited).
- _resolve_session_jsonl_path(kanban_task, exec_status): finds
  ~/.claude/projects/<encoded>/<session>.jsonl using project slug
  (defaults ~/code/<slug>, $HOME fallback).
- run_tick now resolves sess_path per task and passes to classify; new
  branch for cls=='idle_finalize' fires _idle_finalize_action,
  increments stats, appends audit event 'idle_finalize_triggered'.

3 tests for ladder (SIGINT response, SIGTERM/SIGKILL escalation,
no-pid noop). idle_finalized_count stat key already present from Task 8.

After this commit, classify_execution returns ALL 6 outcomes from spec.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11 — Phase 8: Smoke E2E real

**Files:**
- (no source changes — manual smoke validation only)

- [ ] **Step 1: Verify nothing broke**

```bash
cd ~/.openclaw/tester-agent && python3 -m unittest discover tests/ 2>&1 | tail -5
cd ~/.openclaw/dispatcher-agent && python3 -m unittest discover tests/ 2>&1 | tail -5
```
Expected: tester-agent 16 PASS, dispatcher-agent 30+ PASS (only pre-existing notifier failures unchanged).

- [ ] **Step 2: Verify reaper runs without errors against current state**

```bash
~/.openclaw/dispatcher-agent/cli.sh reap-detached --once 2>&1 | tail -10
```
Expected: no Python exceptions; should output normal stats line + any non-quiet actions.

- [ ] **Step 3: Smoke 1 — re-invoke flow on T-0111 (if still inconclusive)**

```bash
~/.openclaw/kanban-tasks/cli.sh task show T-0111 --json 2>&1 | python3 -c "
import json,sys
t=json.load(sys.stdin).get('task',{}) or {}
tr=t.get('dispatch_payload',{}).get('test_result') or {}
print(f'status={t.get(\"status\")} blocked={t.get(\"blocked\")} overall={tr.get(\"last_test_overall\")} count={tr.get(\"test_run_count\")}')
"
```

If T-0111 still inconclusive in `testing` status:
1. Wait 30s (backoff for count=1)
2. Force a reaper tick: `~/.openclaw/dispatcher-agent/cli.sh reap-detached --once`
3. Verify T-0111 in actions_per_task as `reinvoke_scheduled`
4. Wait 10s (next reaper tick) — verify T-0111 transitions to needs_lifecycle → tester invoked
5. Final state: `T-0111` should pass (ACs satisfied via JSONL evidence) OR escalate properly

If T-0111 already done (Bernard manually fixed), skip — Step 4 below covers fresh smoke.

- [ ] **Step 4: Smoke 2 — fresh task with idle subprocess**

This requires running a real claude-task that hangs. Simplest: rely on existing T-0112 or T-0113 from sprint-33. If they run cleanly, no idle to detect. To force idle scenario:

```bash
# Move next task to ready and let cron-dispatcher pick it
~/.openclaw/kanban-tasks/cli.sh task move T-0112 ready --actor smoke --json 2>&1 | tail -1
# Watch claude-task spawn
journalctl --user -u openclaw-cron-dispatcher.service --since "10 seconds ago" --no-pager 2>&1 | tail -5
```

Then monitor:
```bash
# Watch reaper for idle_finalize_triggered audit events
journalctl --user -u openclaw-reaper.service --since "5 minutes ago" --no-pager 2>&1 | grep -E "idle_finalize|reinvoke"
```

If claude-cli idle bug manifests (subprocess hangs after assistant text), reaper should detect within 3min + idle threshold and SIGINT. Verify `T-XXXX: idle_finalize -> idle_finalize_triggered` in reaper output.

- [ ] **Step 5: Smoke 3 — verify backoff escalates on repeated inconclusive**

(Optional — only if a task naturally produces inconclusive twice. Skip if not observable in current sprint.)

- [ ] **Step 6: Inspect audit trail**

```bash
tail -30 ~/.openclaw/dispatcher-agent/reaper.jsonl 2>&1 | python3 -c "
import json,sys
for line in sys.stdin:
    try:
        e=json.loads(line)
        ev=e.get('event')
        if ev in ('reinvoke_scheduled', 'idle_finalize_triggered'):
            print(f'{e.get(\"ts\",\"\")[:19]} [{ev}] task={e.get(\"task_id\")} extras={ {k:v for k,v in e.items() if k not in (\"ts\",\"event\",\"task_id\",\"tick_id\")} }')
    except: pass
"
```
Expected: rows for reinvoke or idle_finalize when applicable, with task_id + relevant context.

- [ ] **Step 7: No commit (smoke validation produces no diff)**

If smoke reveals bugs, return to relevant task to iterate. Otherwise the spec is delivered.

---

## Self-Review Checklist (post-write, before handoff)

**1. Spec coverage** — every section/requirement maps to a task?

| Spec section | Task |
|---|---|
| §3 Decisão 1 (escopo) | Tasks 2-10 cover all 3 bugs |
| §3 Decisão 2 (state-driven trigger) | Tasks 6-8 (helpers + classify + run_tick) |
| §3 Decisão 3 (sem limite + backoff) | Task 6 (`_backoff_delay_for`) |
| §3 Decisão 4 (geometric 3x cap 10min) | Task 6 (REINVOKE_BACKOFF_SCHEDULE constant) |
| §3 Decisão 5 (idle threshold 3min) | Task 9 (IDLE_FINALIZE_THRESHOLD_S constant) |
| §3 Decisão 6 (full file read) | Task 3 (`load_session_evidence` reads `f.readlines()`) |
| §5.1 `claude_project_dir` | Task 2 |
| §5.1 `load_session_evidence` | Task 3 |
| §5.1 `load_evidence` wrapper | Task 4 |
| §5.2 `build_test_context` uses load_evidence | Task 5 |
| §5.3 `classify_execution` 6 estados | Tasks 7 (signature + needs_reinvoke) + 9 (idle_finalize via _detect_idle stub→real) + 10 (jsonl_path resolution) |
| §5.3 `_detect_idle_finalize` | Task 9 |
| §5.3 `_needs_tester_reinvoke` | Task 6 |
| §5.3 `_backoff_delay_for` | Task 6 |
| §5.3 `_idle_finalize_action` ladder | Task 10 |
| §5.4 run_tick branches | Tasks 8 (needs_reinvoke) + 10 (idle_finalize) |
| §5.5 kanban_state pre-load | Task 8 (`_load_kanban_state` + run_tick wires) |
| §5.6 Constants | Tasks 6 (REINVOKE_BACKOFF_SCHEDULE) + 6 (IDLE_FINALIZE_THRESHOLD_S env) + 10 (GRACE_*) |
| §6 data flow scenarios | Validated via Tasks 6-10 unit/integration tests + Task 11 smoke |
| §7 error handling | All test cases cover defensive branches (None, missing, corrupt, malformed timestamps) |
| §8 testing strategy | Tasks 2-10 follow TDD; Task 11 smoke |
| §9 8 phases delivery | Tasks 1-11 (Phase 0=Task 1, Phase 1=Task 2, ..., Phase 8=Task 11) |
| §10 acceptance criteria | All 12 covered: claude_project_dir (T2), load_session_evidence (T3), wrapper (T4), build_test_context (T5), _detect_idle_finalize 4 cenários (T9), _needs_tester_reinvoke matrix (T6), reaper detect needs_reinvoke + reset (T8), reaper detect idle_finalize SIGINT (T10), ladder escalation (T10), env var override (T6 IDLE_THRESHOLD constant), smoke E2E (T11) |

**2. Placeholder scan** — verified, no TBD/TODO; every code step has full code.

**3. Type consistency**
- `claude_project_dir(path)` — same signature in T2 and T3 (used in `_claude_projects_root`).
- `load_session_evidence(session_id, project_path)` — same in T3 and T4 (used in `load_evidence`).
- `_backoff_delay_for(retry_count)` — same in T6 and T7 (used in `classify_execution` chain).
- `_needs_tester_reinvoke(kanban_task, exec_status)` — same in T6 and T7 (used in `classify_execution`).
- `classify_execution(status, kanban_task, session_jsonl_path)` — same in T7, T8, T10.
- `_detect_idle_finalize(jsonl_path)` — stub in T7, real impl in T9, both same signature.
- `_idle_finalize_action(task_id, status)` — same in T10.
- `_load_kanban_state()` and `_find_kanban_task(kanban, task_id)` — added in T8, only used internally in run_tick.
- `_resolve_session_jsonl_path(kanban_task, exec_status)` — added in T10.
- Stats keys: `reinvoke_scheduled_count` and `idle_finalized_count` — both initialized in T8, T8 fills first, T10 fills second.

**Risks documented**:
- Task 5 Step 6 smoke depends on T-0109 sample; if cli.sh output format doesn't surface evidence_source, manual trace needed.
- Task 10 Step 4 smoke requires natural idle to occur — fallback documented (skip if not observed).
- Task 11 smokes are best-effort; spec does not block on them succeeding (unit + integration tests already gate).
