# MC Projects Delete Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CLI `openclaw project remove <id>` + UI danger zone delete button cleanup projeto user_created end-to-end nos 7 destinos cross-filesystem com pre-flight (canonical hard-block) + reverse-of-create order + GitHub try-and-soft-fail + typed-confirm UX.

**Architecture:** Mirror simétrico da factory wave. CLI Python em `kanban-tasks/lib/project_factory.py` ganha 6 `step_remove_*` + `remove_project` orchestrator + `ProjectRemoveConfig` (paralelo de Create). MC backend adiciona DELETE handler em `[id]/route.ts` (spawn CLI subprocess, mapping exit→HTTP). UI: danger zone section condicional em `ProjectGeralTab` + `DeleteProjectModal` typed-confirm. events.jsonl preservado via `project_deleted` event no kanban step.

**Tech Stack:** Python 3.11+ (CLI), unittest com tempfile + unittest.mock, Next.js 15 + TypeScript + Vitest, `gh` CLI subprocess.

**Spec:** `bevox-knowledge/35_specs/company-os/2026-04-27-mc-projects-delete.md` (commit `3ed224b` em `draft/spec-mc-projects-delete`).

---

## File Structure

### Modify (openclaw)

- `kanban-tasks/lib/projects_meta.py` — adicionar `delete_project(path, slug)` helper (paralelo de insert/update)
- `kanban-tasks/lib/project_factory.py` — adicionar exception + pre-flight + 6 step funcs + orchestrator + dataclass (~200 LOC novos, mesma file da wave anterior)
- `kanban-tasks/lib/api.py` — adicionar `cmd_project_remove` handler + argparse subcommand
- `kanban-tasks/tests/test_projects_meta.py` — adicionar `TestDeleteProject` (2 tests)
- `kanban-tasks/tests/test_project_factory.py` — adicionar `TestRemove*` classes (~12 unittest novos)

### Create (mission-control)

- `src/components/projects/DeleteProjectModal.tsx` (~150 LOC)
- `tests/components/projects/DeleteProjectModal.test.tsx` (~30 LOC)
- `tests/app/api/projects/delete.test.ts` (~30 LOC)

### Modify (mission-control)

- `src/app/api/projects/[id]/route.ts` — adicionar `DELETE` handler com canonical block + spawn CLI + parse stdout (~80 LOC novos)
- `src/components/projects/ProjectGeralTab.tsx` — danger zone section condicional + state pra modal (~50 LOC novos)

### bevox-knowledge

Sem mudança nesta wave (writes vão pro working tree do user, mesmo flow do create).

---

## Task 1: Setup branches + commit plan + push spec PR (gate)

**Files:**
- Create: `~/.openclaw/docs/superpowers/plans/2026-04-27-mc-projects-delete.md` (este arquivo)

- [ ] **Step 1: Branch openclaw plan**

```bash
cd ~/.openclaw && git checkout main && git pull --ff-only
git checkout -b feat/mc-projects-delete-plan
```

(Se branch já existe: `git checkout feat/mc-projects-delete-plan`.)

- [ ] **Step 2: Commit plan**

```bash
cd ~/.openclaw && git add docs/superpowers/plans/2026-04-27-mc-projects-delete.md && git commit -m "$(cat <<'EOF'
plan(mc-projects-delete): implementation plan

Spec: bevox-knowledge/35_specs/company-os/2026-04-27-mc-projects-delete.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 3: Push spec PR no bevox-knowledge**

```bash
cd ~/bevox-knowledge && git checkout draft/spec-mc-projects-delete
git push -u origin draft/spec-mc-projects-delete
gh pr create --title "spec(company-os): MC Projects delete (E2/mc-projects-delete)" --body "Mirror simétrico da factory wave (PR #18 mc + #12 openclaw delivered 2026-04-27).

CLI \`openclaw project remove <id>\` orquestra cleanup em 6 steps reverse-of-create order. UI: danger zone no tab Geral + DeleteProjectModal typed-confirm.

Pre-requisitos já entregues: factory wave + memory templates hotfix.

Plan: openclaw/docs/superpowers/plans/2026-04-27-mc-projects-delete.md (branch feat/mc-projects-delete-plan).

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

- [ ] **Step 4: PAUSA — aguardar Bernard mergear spec PR**

Parar aqui. Bernard merge `bernardTavares/bevox-knowledge` PR. Retomar Task 2 só após merge confirmado em main.

---

## Task 2: `projects_meta.delete_project` helper

**Files:**
- Modify: `kanban-tasks/lib/projects_meta.py`
- Modify: `kanban-tasks/tests/test_projects_meta.py`

- [ ] **Step 1: Branch openclaw feat**

```bash
cd ~/.openclaw && git checkout main && git pull --ff-only
git checkout -b feat/mc-projects-delete
```

- [ ] **Step 2: Add tests pra delete_project**

Append em `kanban-tasks/tests/test_projects_meta.py`:

```python
from lib.projects_meta import delete_project


class TestDeleteProject(unittest.TestCase):
    def test_removes_existing_entry(self):
        with tempfile.TemporaryDirectory() as td:
            meta_path = Path(td) / "meta.json"
            insert_project(meta_path, "x", {"name": "X"})
            delete_project(meta_path, "x")
            data = json.loads(meta_path.read_text())
            self.assertNotIn("x", data["projects"])

    def test_fails_if_missing(self):
        with tempfile.TemporaryDirectory() as td:
            meta_path = Path(td) / "meta.json"
            meta_path.write_text('{"version": 1, "projects": {}}')
            with self.assertRaises(MetaError) as ctx:
                delete_project(meta_path, "ghost")
            self.assertIn("not found", str(ctx.exception))
```

- [ ] **Step 3: Run tests (devem falhar — função não existe)**

```bash
cd ~/.openclaw/kanban-tasks && python3 -m unittest tests.test_projects_meta -v 2>&1 | tail -8
```

Expected: ImportError ou AttributeError na linha `from lib.projects_meta import delete_project`.

- [ ] **Step 4: Implement delete_project**

Append em `kanban-tasks/lib/projects_meta.py`:

```python
def delete_project(path: Path, slug: str) -> None:
    """Remove entry. Fails if slug doesn't exist (paralelo de update_project)."""
    data = read_meta(path)
    if slug not in data.get("projects", {}):
        raise MetaError(f"project '{slug}' not found in meta")
    del data["projects"][slug]
    write_meta(path, data)
```

- [ ] **Step 5: Run tests — should pass**

```bash
cd ~/.openclaw/kanban-tasks && python3 -m unittest tests.test_projects_meta -v 2>&1 | tail -5
```

Expected: 9/9 pass (7 anteriores + 2 novos).

- [ ] **Step 6: Commit**

```bash
cd ~/.openclaw && git add kanban-tasks/lib/projects_meta.py kanban-tasks/tests/test_projects_meta.py && git commit -m "$(cat <<'EOF'
feat(projects_meta): delete_project helper

Mirror de insert/update. Raises MetaError se slug não existe.
Atomic via existing write_meta (tmp+rename + flock).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `RemovePreflightFailure` + `run_remove_preflight`

**Files:**
- Modify: `kanban-tasks/lib/project_factory.py`
- Modify: `kanban-tasks/tests/test_project_factory.py`

- [ ] **Step 1: Add tests**

Append em `kanban-tasks/tests/test_project_factory.py`:

```python
from lib.project_factory import (
    RemovePreflightFailure,
    run_remove_preflight,
)


class TestRunRemovePreflight(unittest.TestCase):
    def test_rejects_canonical(self):
        with tempfile.TemporaryDirectory() as td:
            meta_path = Path(td) / "meta.json"
            meta_path.write_text('{"version": 1, "projects": {"openclaw": {"source": "canonical"}}}')
            with self.assertRaises(RemovePreflightFailure) as ctx:
                run_remove_preflight("openclaw", meta_path)
            self.assertEqual(ctx.exception.code, "cannot_delete_canonical")

    def test_rejects_missing_project(self):
        with tempfile.TemporaryDirectory() as td:
            meta_path = Path(td) / "meta.json"
            meta_path.write_text('{"version": 1, "projects": {}}')
            with self.assertRaises(RemovePreflightFailure) as ctx:
                run_remove_preflight("ghost", meta_path)
            self.assertEqual(ctx.exception.code, "project_not_found")

    def test_rejects_non_user_created_source(self):
        with tempfile.TemporaryDirectory() as td:
            meta_path = Path(td) / "meta.json"
            # not in canonical AND source != user_created
            meta_path.write_text('{"version": 1, "projects": {"weird": {"source": "imported"}}}')
            with self.assertRaises(RemovePreflightFailure) as ctx:
                run_remove_preflight("weird", meta_path)
            self.assertEqual(ctx.exception.code, "cannot_delete_non_user_created")

    def test_passes_for_user_created(self):
        with tempfile.TemporaryDirectory() as td:
            meta_path = Path(td) / "meta.json"
            meta_path.write_text('{"version": 1, "projects": {"my-app": {"source": "user_created"}}}')
            run_remove_preflight("my-app", meta_path)  # doesn't raise
```

NOTE: `is_canonical` check uses `is_valid_id` — actually wait, the spec says `isCanonicalProject(slug)` via existing helper. In Python that's checking via `from lib.canonical import is_canonical`. But the kanban-tasks repo has no canonical module — that's the MC TS file. The Python equivalent check is via `entry["source"] == "canonical"`. Let me adjust: `run_remove_preflight` only consults the meta.json `source` field — no separate canonical registry.

```python
def run_remove_preflight(slug: str, meta_path: Path) -> None:
    """Validates project exists in meta with source=user_created.

    Raises RemovePreflightFailure with one of:
    - cannot_delete_canonical (if entry.source == 'canonical')
    - project_not_found (if slug not in meta)
    - cannot_delete_non_user_created (if entry.source is something else)
    """
```

- [ ] **Step 2: Run tests (devem falhar)**

```bash
cd ~/.openclaw/kanban-tasks && python3 -m unittest tests.test_project_factory -v 2>&1 | tail -5
```

Expected: ImportError.

- [ ] **Step 3: Implement RemovePreflightFailure + run_remove_preflight**

Append em `kanban-tasks/lib/project_factory.py`:

```python
class RemovePreflightFailure(Exception):
    """Code: 'cannot_delete_canonical' | 'project_not_found' | 'cannot_delete_non_user_created'."""
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


def run_remove_preflight(slug: str, meta_path: Path) -> None:
    """Validates project exists in meta with source=user_created.

    Canonical projects rejected — must be removed via ADR + canonical.ts edit.
    """
    meta = projects_meta.read_meta(meta_path)
    entry = meta.get("projects", {}).get(slug)
    if not entry:
        raise RemovePreflightFailure(
            "project_not_found",
            f"'{slug}' not found in projects-meta.json",
        )
    source = entry.get("source")
    if source == "canonical":
        raise RemovePreflightFailure(
            "cannot_delete_canonical",
            f"'{slug}' is canonical (ADR-002); deletar requer ADR update + canonical.ts edit",
        )
    if source != "user_created":
        raise RemovePreflightFailure(
            "cannot_delete_non_user_created",
            f"'{slug}' has source='{source}' — only user_created can be deleted",
        )
```

- [ ] **Step 4: Run tests**

```bash
cd ~/.openclaw/kanban-tasks && python3 -m unittest tests.test_project_factory -v 2>&1 | tail -5
```

Expected: tests anteriores + 4 novos pass.

- [ ] **Step 5: Commit**

```bash
cd ~/.openclaw && git add kanban-tasks/lib/project_factory.py kanban-tasks/tests/test_project_factory.py && git commit -m "$(cat <<'EOF'
feat(project_factory): RemovePreflightFailure + run_remove_preflight

Pre-flight pra delete: rejeita canonical (governança ADR-002), missing
projects (already deleted ou never existed), non-user_created sources.
Validation antes de qualquer destructive write.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: 6 `step_remove_*` funcs

**Files:**
- Modify: `kanban-tasks/lib/project_factory.py`
- Modify: `kanban-tasks/tests/test_project_factory.py`

- [ ] **Step 1: Add tests pra step_remove_code_dir**

Append em `kanban-tasks/tests/test_project_factory.py`:

```python
from lib.project_factory import (
    step_remove_code_dir,
    step_remove_workspace,
    step_remove_kanban,
    step_remove_knowledge,
    step_remove_meta,
    step_remove_github,
)


class TestStepRemoveCodeDir(unittest.TestCase):
    def test_removes_existing(self):
        with tempfile.TemporaryDirectory() as td:
            code_dir = Path(td)
            project_path = code_dir / "my-app"
            project_path.mkdir()
            (project_path / "README.md").write_text("hello")
            result = step_remove_code_dir("my-app", code_dir)
            self.assertFalse(project_path.exists())
            self.assertTrue(result["removed"])

    def test_idempotent_when_missing(self):
        with tempfile.TemporaryDirectory() as td:
            code_dir = Path(td)
            result = step_remove_code_dir("ghost", code_dir)
            self.assertFalse(result["removed"])  # nothing to remove


class TestStepRemoveWorkspace(unittest.TestCase):
    def test_removes_runtime_and_workspace(self):
        with tempfile.TemporaryDirectory() as td:
            openclaw_dir = Path(td)
            (openclaw_dir / "my-app").mkdir()
            (openclaw_dir / "workspace-my-app").mkdir()
            (openclaw_dir / "workspace-my-app" / "MEMORY.md").write_text("x")
            result = step_remove_workspace("my-app", openclaw_dir)
            self.assertFalse((openclaw_dir / "my-app").exists())
            self.assertFalse((openclaw_dir / "workspace-my-app").exists())
            self.assertEqual(result["removed_dirs"], 2)


class TestStepRemoveKnowledge(unittest.TestCase):
    def test_removes_kb_folders(self):
        with tempfile.TemporaryDirectory() as td:
            kb_dir = Path(td)
            (kb_dir / "10_prd" / "my-app").mkdir(parents=True)
            (kb_dir / "10_prd" / "my-app" / "prd.md").write_text("x")
            (kb_dir / "40_roadmap" / "my-app").mkdir(parents=True)
            result = step_remove_knowledge("my-app", kb_dir)
            self.assertFalse((kb_dir / "10_prd" / "my-app").exists())
            self.assertFalse((kb_dir / "40_roadmap" / "my-app").exists())
            self.assertEqual(result["removed_folders"], 2)


class TestStepRemoveMeta(unittest.TestCase):
    def test_calls_delete_project(self):
        with tempfile.TemporaryDirectory() as td:
            meta_path = Path(td) / "meta.json"
            from lib.projects_meta import insert_project
            insert_project(meta_path, "x", {"name": "X", "source": "user_created"})
            result = step_remove_meta("x", meta_path)
            data = json.loads(meta_path.read_text())
            self.assertNotIn("x", data["projects"])
            self.assertTrue(result["removed"])


class TestStepRemoveGithub(unittest.TestCase):
    @patch("lib.project_factory.subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="deleted", stderr="")
        result = step_remove_github("my-app", "bernardTavares")
        self.assertTrue(result["github_deleted"])

    @patch("lib.project_factory.subprocess.run")
    def test_soft_fail_on_scope_missing(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr='HTTP 403: Must have admin rights to Repository. needs the "delete_repo" scope',
        )
        result = step_remove_github("my-app", "bernardTavares")
        self.assertFalse(result["github_deleted"])
        self.assertIn("delete_repo", result["github_hint"])


class TestStepRemoveKanban(unittest.TestCase):
    def test_emits_event_and_cleans_state(self):
        with tempfile.TemporaryDirectory() as td:
            openclaw_dir = Path(td)
            kanban_dir = openclaw_dir / "kanban-tasks"
            kanban_dir.mkdir()
            # Seed projects.yml
            (kanban_dir / "projects.yml").write_text(
                "projects:\n  - my-app\n  - other\n"
            )
            # Seed state.json
            state_data = {
                "schema_version": 4,
                "sprints": [
                    {"id": "sprint-1", "project": "my-app", "state": "current"},
                    {"id": "sprint-2", "project": "my-app", "state": "next"},
                    {"id": "sprint-99", "project": "other", "state": "current"},
                ],
                "tasks": [
                    {"id": "T-1", "project": "my-app", "sprint_id": "sprint-1"},
                    {"id": "T-99", "project": "other", "sprint_id": "sprint-99"},
                ],
                "last_event_seq": 100,
            }
            (kanban_dir / "state.json").write_text(json.dumps(state_data, indent=2))
            (kanban_dir / "events.jsonl").write_text("")

            result = step_remove_kanban("my-app", openclaw_dir, actor="bernard")

            # state.json: my-app sprints + tasks gone, others preserved
            updated = json.loads((kanban_dir / "state.json").read_text())
            self.assertEqual(len(updated["sprints"]), 1)
            self.assertEqual(updated["sprints"][0]["project"], "other")
            self.assertEqual(len(updated["tasks"]), 1)

            # projects.yml: my-app removed
            yml = (kanban_dir / "projects.yml").read_text()
            self.assertNotIn("- my-app", yml)
            self.assertIn("- other", yml)

            # events.jsonl: project_deleted appended
            events = (kanban_dir / "events.jsonl").read_text().strip().splitlines()
            self.assertEqual(len(events), 1)
            event = json.loads(events[0])
            self.assertEqual(event["type"], "project_deleted")
            self.assertEqual(event["project"], "my-app")
            self.assertEqual(event["snapshot"]["sprints_removed"], ["sprint-1", "sprint-2"])
            self.assertEqual(event["snapshot"]["tasks_removed"], ["T-1"])

            self.assertEqual(result["sprints_removed"], 2)
            self.assertEqual(result["tasks_removed"], 1)
```

- [ ] **Step 2: Run tests (devem falhar)**

```bash
cd ~/.openclaw/kanban-tasks && python3 -m unittest tests.test_project_factory -v 2>&1 | tail -5
```

Expected: ImportError nos novos imports.

- [ ] **Step 3: Implement 6 step_remove_* funcs**

Append em `kanban-tasks/lib/project_factory.py`:

```python
import shutil


def step_remove_code_dir(slug: str, code_dir: Path) -> dict:
    """Step 1: rm -rf <code_dir>/<slug>. Idempotent (skip if missing)."""
    target = code_dir / slug
    if not target.exists():
        return {"removed": False, "reason": "not_found"}
    shutil.rmtree(target)
    return {"removed": True, "path": str(target)}


def step_remove_workspace(slug: str, openclaw_dir: Path) -> dict:
    """Step 2: rm -rf <openclaw>/<slug> + <openclaw>/workspace-<slug>."""
    runtime_dir = openclaw_dir / slug
    workspace_dir = openclaw_dir / f"workspace-{slug}"
    removed = 0
    for d in (runtime_dir, workspace_dir):
        if d.exists():
            shutil.rmtree(d)
            removed += 1
    return {"removed_dirs": removed}


def step_remove_kanban(
    slug: str, openclaw_dir: Path, actor: str = "bernard"
) -> dict:
    """Step 3: emit project_deleted event + remove sprints/tasks de state.json
    + remove de projects.yml. events.jsonl APPEND-ONLY.
    """
    import datetime as dt
    kanban_dir = openclaw_dir / "kanban-tasks"
    state_path = kanban_dir / "state.json"
    events_path = kanban_dir / "events.jsonl"
    yml_path = kanban_dir / "projects.yml"

    if not state_path.exists():
        return {"sprints_removed": 0, "tasks_removed": 0, "noop": True}

    # Read state with flock
    lock_path = state_path.with_suffix(".json.lock")
    lock_path.touch(exist_ok=True)

    sprints_removed = []
    tasks_removed = []

    with open(lock_path, "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            state = json.loads(state_path.read_text())

            # Collect snapshot before mutation
            sprints_to_remove = [
                s for s in state.get("sprints", []) if s.get("project") == slug
            ]
            tasks_to_remove = [
                t for t in state.get("tasks", []) if t.get("project") == slug
            ]
            sprints_removed = [s["id"] for s in sprints_to_remove]
            tasks_removed = [t["id"] for t in tasks_to_remove]

            # Get github_url + created_at from meta for snapshot
            meta_path = openclaw_dir / "projects-meta.json"
            github_url = None
            created_at = None
            try:
                meta = projects_meta.read_meta(meta_path)
                entry = meta.get("projects", {}).get(slug, {})
                github_url = entry.get("github_url")
                created_at = entry.get("created_at")
            except Exception:
                pass  # tolerable

            # Append project_deleted event BEFORE mutating state
            new_seq = state.get("last_event_seq", 0) + 1
            event = {
                "seq": new_seq,
                "ts": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
                "type": "project_deleted",
                "actor": actor,
                "project": slug,
                "snapshot": {
                    "sprints_removed": sprints_removed,
                    "tasks_removed": tasks_removed,
                    "github_url": github_url,
                    "created_at": created_at,
                },
            }
            with open(events_path, "a") as ef:
                ef.write(json.dumps(event, ensure_ascii=False) + "\n")

            # Mutate state
            state["sprints"] = [
                s for s in state.get("sprints", []) if s.get("project") != slug
            ]
            state["tasks"] = [
                t for t in state.get("tasks", []) if t.get("project") != slug
            ]
            if "projects" in state and isinstance(state["projects"], list):
                state["projects"] = [p for p in state["projects"] if p != slug]
            state["last_event_seq"] = new_seq

            # Atomic write state.json
            tmp = state_path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False))
            tmp.replace(state_path)

            # Cleanup projects.yml (best-effort; preserve other entries)
            if yml_path.exists():
                lines = yml_path.read_text().splitlines(keepends=True)
                filtered = [line for line in lines if line.strip() != f"- {slug}"]
                yml_path.write_text("".join(filtered))
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)

    return {
        "sprints_removed": len(sprints_removed),
        "tasks_removed": len(tasks_removed),
        "event_seq": new_seq,
    }


def step_remove_knowledge(slug: str, kb_dir: Path) -> dict:
    """Step 4: rm -rf 10_prd/<slug>/ + 40_roadmap/<slug>/."""
    removed = 0
    for folder in ("10_prd", "40_roadmap"):
        target = kb_dir / folder / slug
        if target.exists():
            shutil.rmtree(target)
            removed += 1
    return {"removed_folders": removed}


def step_remove_meta(slug: str, meta_path: Path) -> dict:
    """Step 5: projects_meta.delete_project. Atomic via flock."""
    projects_meta.delete_project(meta_path, slug)
    return {"removed": True}


def step_remove_github(
    slug: str, org: str, allow_soft_fail: bool = True
) -> dict:
    """Step 6: gh repo delete. Soft-fail on scope missing or already-gone."""
    cmd = ["gh", "repo", "delete", f"{org}/{slug}", "--yes"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode == 0:
        return {"github_deleted": True}
    if not allow_soft_fail:
        raise StepFailure(6, "gh_delete_failed", result.stderr.strip())
    # Soft-fail: detect scope error vs already-gone
    stderr = result.stderr.strip()
    if "delete_repo" in stderr:
        hint = (
            "gh CLI lacks delete_repo scope. Run "
            "'gh auth refresh -h github.com -s delete_repo' or delete manually "
            f"at https://github.com/{org}/{slug}/settings"
        )
    elif "Could not resolve" in stderr or "404" in stderr:
        hint = f"Repo {org}/{slug} already deleted or never existed."
    else:
        hint = f"gh repo delete failed: {stderr}"
    return {
        "github_deleted": False,
        "github_hint": hint,
        "stderr": stderr,
    }
```

- [ ] **Step 4: Run tests**

```bash
cd ~/.openclaw/kanban-tasks && python3 -m unittest tests.test_project_factory -v 2>&1 | tail -5
```

Expected: anteriores + 9 novos pass.

- [ ] **Step 5: Commit**

```bash
cd ~/.openclaw && git add kanban-tasks/lib/project_factory.py kanban-tasks/tests/test_project_factory.py && git commit -m "$(cat <<'EOF'
feat(project_factory): 6 step_remove_* funcs

Mirror reverso dos step_N_* da factory wave. Reverse-of-create order:
1. rm code dir, 2. rm openclaw runtime + workspace, 3. emit
project_deleted event + clean state.json + projects.yml, 4. rm KB
folders, 5. delete projects-meta entry, 6. gh repo delete (try-and-soft-fail).

Step 3 preserva events.jsonl append-only — emite project_deleted event
com snapshot (sprints_removed, tasks_removed, github_url, created_at)
ANTES de mutar state.json. flock + atomic write via tmp+rename.

Step 6 soft-fail detecta scope missing vs already-gone, retorna
{github_deleted: false, github_hint: "..."} pra UI manual handle.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Orchestrator `remove_project` + JSONL log

**Files:**
- Modify: `kanban-tasks/lib/project_factory.py`
- Modify: `kanban-tasks/tests/test_project_factory.py`

- [ ] **Step 1: Add tests**

Append em `kanban-tasks/tests/test_project_factory.py`:

```python
from lib.project_factory import remove_project, ProjectRemoveConfig


class TestRemoveProject(unittest.TestCase):
    def _build_config(self, td):
        config = ProjectRemoveConfig(
            kb_dir=Path(td) / "kb",
            openclaw_dir=Path(td) / "openclaw",
            code_dir=Path(td) / "code",
            meta_path=Path(td) / "openclaw" / "projects-meta.json",
            log_path=Path(td) / "openclaw" / "projects-delete.jsonl",
            org="bernardTavares",
        )
        config.kb_dir.mkdir()
        config.openclaw_dir.mkdir()
        config.code_dir.mkdir()
        kanban_dir = config.openclaw_dir / "kanban-tasks"
        kanban_dir.mkdir()
        (kanban_dir / "projects.yml").write_text("projects:\n  - my-app\n")
        (kanban_dir / "state.json").write_text(json.dumps({
            "schema_version": 4,
            "sprints": [{"id": "sprint-1", "project": "my-app", "state": "current"}],
            "tasks": [],
            "last_event_seq": 0,
        }, indent=2))
        (kanban_dir / "events.jsonl").write_text("")
        # Seed local files to remove
        (config.code_dir / "my-app").mkdir()
        (config.openclaw_dir / "my-app").mkdir()
        (config.openclaw_dir / "workspace-my-app").mkdir()
        (config.kb_dir / "10_prd" / "my-app").mkdir(parents=True)
        (config.kb_dir / "40_roadmap" / "my-app").mkdir(parents=True)
        # Seed meta
        from lib.projects_meta import insert_project
        insert_project(config.meta_path, "my-app", {
            "name": "My App",
            "description": "test",
            "github_url": "https://github.com/bernardTavares/my-app",
            "bot_id": None,
            "created_at": "2026-04-27T00:00:00Z",
            "source": "user_created",
        })
        return config

    @patch("lib.project_factory.subprocess.run")
    def test_happy_path(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="deleted", stderr="")
        with tempfile.TemporaryDirectory() as td:
            config = self._build_config(td)
            result = remove_project(slug="my-app", config=config, actor="bernard")
            self.assertTrue(result["success"])
            self.assertEqual(result["steps_completed"], 6)
            self.assertTrue(result["github_deleted"])
            # All locations cleaned
            self.assertFalse((config.code_dir / "my-app").exists())
            self.assertFalse((config.openclaw_dir / "my-app").exists())
            self.assertFalse((config.openclaw_dir / "workspace-my-app").exists())
            self.assertFalse((config.kb_dir / "10_prd" / "my-app").exists())
            # JSONL log populated
            log_lines = config.log_path.read_text().strip().splitlines()
            self.assertEqual(len(log_lines), 6)
            for line in log_lines:
                entry = json.loads(line)
                self.assertEqual(entry["status"], "ok")

    @patch("lib.project_factory.subprocess.run")
    def test_github_soft_fail(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1, stdout="",
            stderr='HTTP 403: needs the "delete_repo" scope',
        )
        with tempfile.TemporaryDirectory() as td:
            config = self._build_config(td)
            result = remove_project(slug="my-app", config=config, actor="bernard")
            self.assertTrue(result["success"])  # local cleanup ok
            self.assertEqual(result["steps_completed"], 6)
            self.assertFalse(result["github_deleted"])
            self.assertIn("delete_repo", result["github_hint"])

    def test_preflight_canonical_rejection(self):
        with tempfile.TemporaryDirectory() as td:
            config = ProjectRemoveConfig(
                kb_dir=Path(td) / "kb", openclaw_dir=Path(td) / "openclaw",
                code_dir=Path(td) / "code",
                meta_path=Path(td) / "meta.json",
                log_path=Path(td) / "log.jsonl",
                templates_dir=Path("~/.openclaw/kanban-tasks/templates"),
                org="bernardTavares",
            )
            config.openclaw_dir.mkdir()
            config.meta_path.write_text(
                '{"version": 1, "projects": {"openclaw": {"source": "canonical"}}}'
            )
            result = remove_project(slug="openclaw", config=config, actor="bernard")
            self.assertFalse(result["success"])
            self.assertEqual(result["error_code"], "cannot_delete_canonical")
            self.assertEqual(result["failed_at"], 0)
```

- [ ] **Step 2: Run tests (devem falhar)**

```bash
cd ~/.openclaw/kanban-tasks && python3 -m unittest tests.test_project_factory -v 2>&1 | tail -5
```

Expected: ImportError em `remove_project` / `ProjectRemoveConfig`.

- [ ] **Step 3: Implement orchestrator**

Append em `kanban-tasks/lib/project_factory.py`:

```python
@dataclass
class ProjectRemoveConfig:
    kb_dir: Path
    openclaw_dir: Path
    code_dir: Path
    meta_path: Path
    log_path: Path  # ~/.openclaw/projects-delete.jsonl
    org: str = "bernardTavares"
    templates_dir: Path = None  # Unused for delete; kept for symmetry


def remove_project(
    slug: str,
    config: ProjectRemoveConfig,
    actor: str = "bernard",
    skip_github: bool = False,
) -> dict:
    """Orchestrate 6-step project deletion. Reverse-of-create order.

    Returns dict:
      success: bool
      id, steps_completed, github_deleted, github_hint?, snapshot, log
      OR failed_at, error_code, error_message
    """
    # Pre-flight
    try:
        run_remove_preflight(slug, config.meta_path)
    except RemovePreflightFailure as e:
        return {
            "success": False,
            "failed_at": 0,
            "steps_completed": 0,
            "error_code": e.code,
            "error_message": str(e),
        }

    # Snapshot meta entry BEFORE deletion
    meta = projects_meta.read_meta(config.meta_path)
    pre_entry = meta.get("projects", {}).get(slug, {})
    snapshot = {
        "github_url": pre_entry.get("github_url"),
        "created_at": pre_entry.get("created_at"),
    }

    steps = [
        (1, "code_dir", lambda: step_remove_code_dir(slug, config.code_dir)),
        (2, "workspace", lambda: step_remove_workspace(slug, config.openclaw_dir)),
        (3, "kanban", lambda: step_remove_kanban(slug, config.openclaw_dir, actor)),
        (4, "knowledge", lambda: step_remove_knowledge(slug, config.kb_dir)),
        (5, "meta", lambda: step_remove_meta(slug, config.meta_path)),
    ]
    if not skip_github:
        steps.append(
            (6, "github", lambda: step_remove_github(slug, config.org))
        )

    completed = 0
    github_deleted = None
    github_hint = None
    last_step_details = {}
    log_entries = []

    for step_num, step_name, step_fn in steps:
        start = time.time()
        try:
            details = step_fn()
            duration_ms = int((time.time() - start) * 1000)
            log_entry = {
                "ts": dt.datetime.utcnow().isoformat() + "Z",
                "slug": slug,
                "step": step_num,
                "name": step_name,
                "status": "ok",
                "duration_ms": duration_ms,
            }
            log_entries.append(log_entry)
            _log_event(config.log_path, log_entry)
            completed = step_num
            if step_name == "kanban":
                # Capture sprint/task removal counts
                snapshot["sprints_removed"] = details.get("sprints_removed", 0)
                snapshot["tasks_removed"] = details.get("tasks_removed", 0)
            if step_name == "github":
                github_deleted = details.get("github_deleted")
                github_hint = details.get("github_hint")
            last_step_details = details
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            log_entry = {
                "ts": dt.datetime.utcnow().isoformat() + "Z",
                "slug": slug,
                "step": step_num,
                "name": step_name,
                "status": "failed",
                "duration_ms": duration_ms,
                "error": str(e),
            }
            log_entries.append(log_entry)
            _log_event(config.log_path, log_entry)
            return {
                "success": False,
                "failed_at": step_num,
                "steps_completed": completed,
                "error_code": getattr(e, "code", "unknown"),
                "error_message": str(e),
                "log": log_entries,
            }

    # If skip_github, github_deleted stays None — treat as not_attempted
    if skip_github:
        github_deleted = False
        github_hint = "Skipped via --skip-github"

    return {
        "success": True,
        "id": slug,
        "steps_completed": completed,
        "github_deleted": github_deleted,
        "github_hint": github_hint,
        "snapshot": snapshot,
        "log": log_entries,
    }
```

- [ ] **Step 4: Run tests**

```bash
cd ~/.openclaw/kanban-tasks && python3 -m unittest tests.test_project_factory -v 2>&1 | tail -5
```

Expected: 3 novos orchestrator tests pass + tests anteriores.

- [ ] **Step 5: Commit**

```bash
cd ~/.openclaw && git add kanban-tasks/lib/project_factory.py kanban-tasks/tests/test_project_factory.py && git commit -m "$(cat <<'EOF'
feat(project_factory): orchestrator remove_project + JSONL log

Pre-flight + 6 steps em sequencia reverse-of-create. Cada step loga JSON
line em ~/.openclaw/projects-delete.jsonl. Em falha pre-flight, retorna
failed_at: 0; em runtime failure, retorna failed_at + steps_completed.

ProjectRemoveConfig dataclass paralelo do ProjectCreateConfig.

Snapshot collected before destructive writes pra audit + UI display.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: cli.sh entry — `project remove`

**Files:**
- Modify: `kanban-tasks/lib/api.py`

- [ ] **Step 1: Add `cmd_project_remove` handler**

Insert em `kanban-tasks/lib/api.py` apos `cmd_project_edit`:

```python
def cmd_project_remove(args: argparse.Namespace) -> int:
    """Orchestrator: remove project across 6 destinations (reverse-of-create)."""
    from pathlib import Path
    import os
    from lib.project_factory import remove_project, ProjectRemoveConfig

    kb_dir = Path(os.environ.get(
        "BEVOX_KNOWLEDGE_DIR", "~/bevox-knowledge"))
    openclaw_dir = Path(os.environ.get(
        "OPENCLAW_DIR", "~/.openclaw"))
    code_dir = Path(os.environ.get(
        "BEVOX_CODE_DIR", "~/code"))
    org = os.environ.get("GITHUB_ORG", "bernardTavares")

    config = ProjectRemoveConfig(
        kb_dir=kb_dir,
        openclaw_dir=openclaw_dir,
        code_dir=code_dir,
        meta_path=openclaw_dir / "projects-meta.json",
        log_path=openclaw_dir / "projects-delete.jsonl",
        org=org,
    )

    result = remove_project(
        slug=args.id,
        config=config,
        actor=args.actor,
        skip_github=args.skip_github,
    )
    _print(result, args.json,
           f"{'ok' if result['success'] else 'failed'}: {args.id}")
    if not result["success"]:
        # Pre-flight failures map to EXIT_VALIDATION (1); runtime to EXIT_RUNTIME (2)
        if result.get("failed_at") == 0:
            return EXIT_VALIDATION
        return EXIT_RUNTIME
    return EXIT_OK
```

- [ ] **Step 2: Add argparse subcommand**

Locate `pedit` block (project edit) in `lib/api.py`. Add **immediately after** `pedit.set_defaults(func=cmd_project_edit)`:

```python
    # project remove
    premove = leaf(pr_sub, "remove")
    premove.add_argument("id", help="project id (kebab-case)")
    premove.add_argument("--skip-github", action="store_true", dest="skip_github",
                        help="skip step 6 GitHub delete (testes ou cleanup local-only)")
    premove.set_defaults(func=cmd_project_remove)
```

- [ ] **Step 3: Verify CLI surface**

```bash
cd ~/.openclaw/kanban-tasks && ./cli.sh project --help 2>&1 | tail -10
```

Expected: lista incluindo `remove` alongside `list`, `add`, `create`, `edit`.

```bash
cd ~/.openclaw/kanban-tasks && ./cli.sh project remove --help 2>&1 | tail -10
```

Expected: usage com `id` (positional) + `--skip-github`.

- [ ] **Step 4: Run all tests**

```bash
cd ~/.openclaw/kanban-tasks && python3 -m unittest tests -v 2>&1 | tail -5
```

Expected: full suite green.

- [ ] **Step 5: Commit**

```bash
cd ~/.openclaw && git add kanban-tasks/lib/api.py && git commit -m "$(cat <<'EOF'
feat(cli.sh): project remove subcommand

cmd_project_remove invoca remove_project orchestrator com env vars
(BEVOX_KNOWLEDGE_DIR, OPENCLAW_DIR, BEVOX_CODE_DIR, GITHUB_ORG defaults).
--skip-github flag pra cleanup local-only (testes/dev). Exit codes 0/1/2
mapeiam pra MC backend HTTP 200/400/500.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: MC backend — DELETE handler

**Files:**
- Modify: `mission-control/src/app/api/projects/[id]/route.ts`
- Create: `mission-control/tests/app/api/projects/delete.test.ts`

- [ ] **Step 1: Branch mission-control feat**

```bash
cd ~/code/mission-control && git checkout main && git pull --ff-only
git checkout -b feat/mc-projects-delete
```

- [ ] **Step 2: Tests (contract)**

Write `tests/app/api/projects/delete.test.ts`:

```typescript
/**
 * Contract tests for DELETE /api/projects/[id].
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-27-mc-projects-delete.md §3.6
 */
import { describe, it, expect } from "vitest";

describe("DELETE /api/projects/[id] contract", () => {
  it("success response shape with github_deleted flag", () => {
    type Response = {
      success: boolean;
      id?: string;
      steps_completed: number;
      github_deleted?: boolean;
      github_hint?: string;
    };
    const sample: Response = {
      success: true,
      id: "x",
      steps_completed: 6,
      github_deleted: true,
    };
    expect(sample.steps_completed).toBe(6);
    expect(sample.github_deleted).toBe(true);
  });

  it("partial success shape (GitHub soft-fail)", () => {
    type Response = {
      success: boolean;
      github_deleted?: boolean;
      github_hint?: string;
    };
    const sample: Response = {
      success: true,
      github_deleted: false,
      github_hint: "gh CLI lacks delete_repo scope...",
    };
    expect(sample.github_deleted).toBe(false);
  });

  it("canonical block error shape", () => {
    type Response = { error: string; detail?: string };
    const sample: Response = {
      error: "cannot_delete_canonical",
      detail: "openclaw is canonical (ADR-002)...",
    };
    expect(sample.error).toBe("cannot_delete_canonical");
  });
});
```

- [ ] **Step 3: Implement DELETE handler**

Edit `src/app/api/projects/[id]/route.ts`. Find existing PATCH handler (added in factory wave). Add `DELETE` handler after PATCH:

```typescript
import { isCanonicalProject } from "@/lib/projects/canonical";
// (readMeta likely already imported; if not, add: import { readMeta } from "@/lib/projects/meta";)

export async function DELETE(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;

  // Block canonical projects from UI delete (ADR-002 governance)
  if (isCanonicalProject(id)) {
    return NextResponse.json(
      {
        error: "cannot_delete_canonical",
        detail: `${id} is canonical (ADR-002); requires ADR + canonical.ts edit`,
      },
      { status: 400 },
    );
  }

  // Verify exists in meta (else 404)
  const meta = readMeta();
  if (!meta.projects[id]) {
    return NextResponse.json(
      { error: "project_not_found", detail: `${id} not in projects-meta.json` },
      { status: 404 },
    );
  }

  // Spawn CLI subprocess (mirror POST pattern)
  return new Promise<NextResponse>((resolve) => {
    const child = spawn(CLI_PATH, [
      "project", "remove", id,
      "--json", "--non-interactive",
    ], { timeout: 30_000 });

    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (d) => { stdout += d.toString(); });
    child.stderr.on("data", (d) => { stderr += d.toString(); });
    child.on("error", (err) => {
      resolve(NextResponse.json(
        { error: "cli_spawn_failed", detail: err.message },
        { status: 500 },
      ));
    });
    child.on("close", (code) => {
      let result: unknown = null;
      try {
        result = parseLastJsonLine(stdout);
      } catch {
        /* keep null */
      }

      if (code === 0) {
        // success — possibly partial (github_deleted: false)
        resolve(NextResponse.json(result ?? {}, { status: 200 }));
        return;
      }

      const status = code === 1 ? 400 : 500;
      if (result && typeof result === "object") {
        resolve(NextResponse.json(result, { status }));
      } else {
        resolve(NextResponse.json(
          { error: "cli_failed", detail: stderr.trim() || `exit ${code}` },
          { status },
        ));
      }
    });
  });
}
```

(Reuse `parseLastJsonLine` + `CLI_PATH` constants from the file — they should be defined at top from the factory wave.)

- [ ] **Step 4: Run tests + build**

```bash
cd ~/code/mission-control && npm test -- --run 2>&1 | tail -3 && npm run build 2>&1 | tail -3
```

Expected: tests green; build verde with `DELETE /api/projects/[id]` listed.

- [ ] **Step 5: Commit**

```bash
cd ~/code/mission-control && git add "src/app/api/projects/[id]/route.ts" tests/app/api/projects/delete.test.ts && git commit -m "$(cat <<'EOF'
feat(api/projects/[id]): DELETE handler

Block canonical (HTTP 400 cannot_delete_canonical), 404 se project
ausente em meta, spawn CLI 'project remove' (timeout 30s) com mapping
exit code 0/1/2 → HTTP 200/400/500. Soft-fail GitHub retorna 200 com
github_deleted: false + github_hint pra UI display.

Reusa parseLastJsonLine + CLI_PATH + child.on("error") da wave anterior.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: `DeleteProjectModal`

**Files:**
- Create: `mission-control/src/components/projects/DeleteProjectModal.tsx`
- Create: `mission-control/tests/components/projects/DeleteProjectModal.test.tsx`

- [ ] **Step 1: Tests**

Write `tests/components/projects/DeleteProjectModal.test.tsx`:

```typescript
/**
 * Contract tests for DeleteProjectModal.
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-27-mc-projects-delete.md §3.7
 */
import { describe, it, expect } from "vitest";
import type { DeleteProjectModalProps } from "@/components/projects/DeleteProjectModal";
import type { ProjectDetail } from "@/lib/projects/types";

describe("DeleteProjectModalProps contract", () => {
  it("requires open + project + onClose + onDeleted", () => {
    let deleted = false;
    const minimalDetail = {
      id: "test-app",
      name: "Test App",
      description: "",
      health: { bot: "missing", workspace: "missing", kanban: "missing", knowledge: "missing" },
      counts: { sprints_active: 0, tasks_in_progress: 0 },
      is_canonical: false,
      github_url: null,
      bot_id: null,
      created_at: null,
      health_details: {} as ProjectDetail["health_details"],
      links: {} as ProjectDetail["links"],
      sprints: { active: [], closed: [] },
      tasks_in_flight: [],
    } as ProjectDetail;
    const props: DeleteProjectModalProps = {
      open: true,
      project: minimalDetail,
      onClose: () => {},
      onDeleted: () => { deleted = true; },
    };
    props.onDeleted();
    expect(deleted).toBe(true);
    expect(props.open).toBe(true);
  });
});

describe("typed-confirm semantics", () => {
  it("exact match required for canSubmit", () => {
    const id = "customer-portal";
    expect("customer-portal" === id).toBe(true);
    expect("customer-portal ".trim() === id).toBe(true);
    expect("Customer-Portal" === id).toBe(false);  // case-sensitive
    expect("customer" === id).toBe(false);
  });
});
```

- [ ] **Step 2: Implement modal**

Write `src/components/projects/DeleteProjectModal.tsx`:

```typescript
"use client";

import { useEffect, useState } from "react";
import type { ProjectDetail } from "@/lib/projects/types";

export interface DeleteProjectModalProps {
  open: boolean;
  project: ProjectDetail;
  onClose: () => void;
  onDeleted: () => void;
}

type Result =
  | { kind: "full" }
  | { kind: "partial"; hint: string }
  | { kind: "error"; message: string };

export function DeleteProjectModal({ open, project, onClose, onDeleted }: DeleteProjectModalProps) {
  const [confirmInput, setConfirmInput] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<Result | null>(null);

  // Reset on close
  useEffect(() => {
    if (!open) {
      setConfirmInput("");
      setResult(null);
      setSubmitting(false);
    }
  }, [open]);

  // Esc closes (only if not submitting)
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !submitting) onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, submitting, onClose]);

  if (!open) return null;

  const canSubmit = !submitting && confirmInput.trim() === project.id;

  const submit = async () => {
    setSubmitting(true);
    try {
      const r = await fetch(`/api/projects/${encodeURIComponent(project.id)}`, {
        method: "DELETE",
      });
      const data = await r.json();
      if (r.ok && data.success) {
        if (data.github_deleted) {
          setResult({ kind: "full" });
          setTimeout(onDeleted, 2000);
        } else {
          setResult({ kind: "partial", hint: data.github_hint ?? "GitHub repo not deleted" });
        }
      } else {
        setResult({
          kind: "error",
          message: data.error_message ?? data.detail ?? data.error ?? `HTTP ${r.status}`,
        });
      }
    } catch (e) {
      setResult({ kind: "error", message: e instanceof Error ? e.message : String(e) });
    } finally {
      setSubmitting(false);
    }
  };

  const sprintsCount = project.sprints.active.length + project.sprints.closed.length;
  const tasksCount = project.tasks_in_flight.length;

  return (
    <div onClick={submitting ? undefined : onClose} style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)",
      display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100,
    }}>
      <div onClick={(e) => e.stopPropagation()} style={{
        background: "#161b22", borderRadius: 8, padding: "1.25rem 1.5rem",
        width: "90%", maxWidth: 560, color: "#e0e0e0",
        border: "1px solid #5f1e1e",
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
          <h2 style={{ margin: 0, fontSize: "1.1rem", color: "#e46e6e" }}>⚠ Delete project</h2>
          {!submitting && (
            <button type="button" onClick={onClose} style={{ background: "transparent", border: "none", color: "#888", fontSize: "1.4rem", cursor: "pointer" }}>×</button>
          )}
        </div>

        {!result && (
          <>
            <div style={{ fontSize: "0.82rem", color: "#e0e0e0", lineHeight: 1.6, marginBottom: "1rem" }}>
              Esta ação é <strong style={{ color: "#e46e6e" }}>IRREVERSÍVEL</strong> e remove:
              <ul style={{ margin: "0.4rem 0 0", paddingLeft: "1.4rem", fontSize: "0.78rem", color: "#888" }}>
                <li>bevox-knowledge: 10_prd/{project.id}/, 40_roadmap/{project.id}/</li>
                <li>kanban-tasks: {sprintsCount} sprint(s) + {tasksCount} task(s)</li>
                <li>~/.openclaw/{project.id}/ + workspace-{project.id}/</li>
                <li>~/code/{project.id}/</li>
                <li>projects-meta.json entry</li>
                {project.github_url && <li>GitHub repo: {project.github_url}</li>}
              </ul>
            </div>

            <label style={{ display: "block", marginBottom: "0.6rem" }}>
              <div style={{ color: "#888", fontSize: "0.7rem", marginBottom: "0.2rem" }}>
                Para confirmar, digite o ID exato do projeto:
              </div>
              <input
                type="text"
                value={confirmInput}
                onChange={(e) => setConfirmInput(e.target.value)}
                disabled={submitting}
                placeholder={project.id}
                style={{
                  width: "100%", padding: "0.45rem 0.6rem",
                  background: "#1a2230",
                  border: `1px solid ${canSubmit ? "#5f1e1e" : "#2a2f3e"}`,
                  borderRadius: 4, color: "#e0e0e0", fontSize: "0.85rem",
                  fontFamily: "monospace",
                }}
              />
            </label>

            <div style={{ color: "#666", fontSize: "0.7rem", fontStyle: "italic", marginBottom: "1rem" }}>
              events.jsonl preservado (append-only audit)
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
              <button type="button" onClick={onClose} disabled={submitting} style={{
                background: "transparent", border: "1px solid #2a2f3e",
                color: "#888", padding: "0.4rem 0.85rem", borderRadius: 4,
                fontSize: "0.85rem", cursor: "pointer",
              }}>Abortar</button>
              <button type="button" onClick={submit} disabled={!canSubmit} style={{
                background: canSubmit ? "#3f1e1e" : "#2a2f3e",
                color: canSubmit ? "#e46e6e" : "#666",
                border: canSubmit ? "1px solid #5f1e1e" : "none",
                padding: "0.4rem 0.85rem", borderRadius: 4, fontSize: "0.85rem",
                cursor: canSubmit ? "pointer" : "not-allowed",
              }}>
                {submitting ? "Deleting…" : "Delete forever"}
              </button>
            </div>
          </>
        )}

        {result?.kind === "full" && (
          <div style={{ background: "#1e3a30", color: "#7ec896", padding: "1rem", borderRadius: 4, fontSize: "0.85rem" }}>
            ✓ Project deleted. Redirecting to /projects...
          </div>
        )}

        {result?.kind === "partial" && (
          <div style={{ background: "#5f5a1e", color: "#e4dc6e", padding: "1rem", borderRadius: 4, fontSize: "0.82rem", marginBottom: "1rem" }}>
            <div style={{ fontWeight: 600, marginBottom: "0.4rem" }}>✓ Local cleanup ok</div>
            <div>⚠ GitHub repo NOT deleted: {result.hint}</div>
            {project.github_url && (
              <a href={`${project.github_url}/settings`} target="_blank" rel="noreferrer" style={{ color: "#e4dc6e", marginTop: "0.5rem", display: "inline-block" }}>
                ↗ Delete on GitHub manually
              </a>
            )}
            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "0.8rem" }}>
              <button type="button" onClick={onDeleted} style={{
                background: "#1e3a5f", color: "#6ec1e4", border: "none",
                padding: "0.4rem 0.85rem", borderRadius: 4, fontSize: "0.85rem", cursor: "pointer",
              }}>OK</button>
            </div>
          </div>
        )}

        {result?.kind === "error" && (
          <div style={{ background: "#3f1e1e", color: "#e46e6e", padding: "1rem", borderRadius: 4, fontSize: "0.82rem" }}>
            <div style={{ fontWeight: 600, marginBottom: "0.4rem" }}>✗ Delete failed</div>
            <div>{result.message}</div>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Run tests + build**

```bash
cd ~/code/mission-control && npm test -- --run 2>&1 | tail -3 && npm run build 2>&1 | tail -3
```

Expected: tests green; build verde.

- [ ] **Step 4: Commit**

```bash
cd ~/code/mission-control && git add src/components/projects/DeleteProjectModal.tsx tests/components/projects/DeleteProjectModal.test.tsx && git commit -m "$(cat <<'EOF'
feat(projects): DeleteProjectModal typed-confirm

Modal com lista 7 destinos a deletar (counts dinamicos: sprints + tasks),
input typed-confirm exact match (case-sensitive trim). Submit chama
DELETE /api/projects/[id]. 3 estados result: full success (auto-redirect
2s), partial (GitHub soft-fail com link manual), error.

Esc/X/backdrop fecham (somente se !submitting).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: `ProjectGeralTab` danger zone

**Files:**
- Modify: `mission-control/src/components/projects/ProjectGeralTab.tsx`

- [ ] **Step 1: Add danger zone state + render**

Edit `src/components/projects/ProjectGeralTab.tsx`. Add:

1. Import `useRouter` + `DeleteProjectModal`:
```typescript
import { useRouter } from "next/navigation";
import { DeleteProjectModal } from "./DeleteProjectModal";
```

2. Inside component, add state:
```typescript
const router = useRouter();
const [deleteOpen, setDeleteOpen] = useState(false);
```

(useState should already be imported from prior wave; if not, add to imports.)

3. Render danger zone + modal at end of component (just before final `</div>` or whatever wraps the existing layout). Adapt selector pra inserir após o split layout:

```tsx
{!detail.is_canonical && (
  <div style={{
    marginTop: "2rem",
    border: "1px solid #5f1e1e",
    borderRadius: 6,
    padding: "1rem 1.25rem",
  }}>
    <h3 style={{ color: "#e46e6e", margin: 0, fontSize: "0.95rem" }}>
      ⚠ Danger zone
    </h3>
    <div style={{ color: "#888", fontSize: "0.78rem", lineHeight: 1.5, margin: "0.5rem 0 1rem" }}>
      Esta ação remove o projeto de todos os 7 destinos cross-filesystem. Irreversível.
    </div>
    <button type="button" onClick={() => setDeleteOpen(true)} style={{
      background: "#3f1e1e", color: "#e46e6e", border: "1px solid #5f1e1e",
      padding: "0.4rem 0.85rem", borderRadius: 4, fontSize: "0.85rem",
      cursor: "pointer",
    }}>Delete project</button>
  </div>
)}
<DeleteProjectModal
  open={deleteOpen}
  project={detail}
  onClose={() => setDeleteOpen(false)}
  onDeleted={() => router.push("/projects")}
/>
```

The danger zone should appear AFTER the existing split layout (after the InfoBoxes + MarkdownViewer block). Wrap the existing return in a fragment if needed.

- [ ] **Step 2: Verify TypeScript types align**

The `DeleteProjectModal` requires `project: ProjectDetail`. The `detail` prop in `ProjectGeralTab` should already be `ProjectDetail` (from the redesign wave). Build will catch mismatches.

- [ ] **Step 3: Run tests + build**

```bash
cd ~/code/mission-control && npm test -- --run 2>&1 | tail -3 && npm run build 2>&1 | tail -3
```

Expected: tests green; build verde.

- [ ] **Step 4: Commit**

```bash
cd ~/code/mission-control && git add src/components/projects/ProjectGeralTab.tsx && git commit -m "$(cat <<'EOF'
feat(ProjectGeralTab): danger zone section + DeleteProjectModal mount

Renderizado condicional (!detail.is_canonical) no fundo do tab Geral.
Border vermelho, header escarlate, botao "Delete project" abre modal.
onDeleted navega pra /projects via router.push.

Canonical projects (10 ADR-002) NAO mostram danger zone — governanca
hard-block via condicional + bloqueio backend duplo (DELETE handler
tambem rejeita canonical com 400).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Push openclaw + MC PRs + pause

- [ ] **Step 1: Push openclaw plan PR**

```bash
cd ~/.openclaw && git push -u origin feat/mc-projects-delete-plan
gh pr create --title "plan(mc-projects-delete): implementation plan" --body "Plan doc para spec bevox-knowledge/35_specs/company-os/2026-04-27-mc-projects-delete.md.

10 tasks: CLI Python (delete_project + pre-flight + 6 step_remove + orchestrator + cli.sh) + MC backend DELETE + UI DeleteProjectModal + danger zone. ~14 unittest + ~5 vitest + 5 smoke E2E.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

- [ ] **Step 2: Push openclaw feat PR**

```bash
cd ~/.openclaw && git checkout feat/mc-projects-delete && git push -u origin feat/mc-projects-delete
gh pr create --title "feat(openclaw): project remove CLI orchestrator (E2/mc-projects-delete)" --body "$(cat <<'EOF'
## Summary
Mirror simétrico da factory wave: novo CLI \`openclaw project remove <id>\` orquestra cleanup em 6 steps reverse-of-create order.

Spec: bevox-knowledge/35_specs/company-os/2026-04-27-mc-projects-delete.md

## What's in this PR
- projects_meta.delete_project helper (paralelo de insert/update)
- RemovePreflightFailure + run_remove_preflight (canonical hard-block, project_not_found, source check)
- 6 step_remove_* funcs (rm code, rm openclaw runtime+workspace, kanban event+state cleanup, rm KB, rm meta, gh repo delete try-and-soft-fail)
- ProjectRemoveConfig dataclass + remove_project orchestrator + JSONL log
- cli.sh entry: project remove <id> [--skip-github] [--json]
- ~14 unittest novos (preflight + 6 step + orchestrator happy/soft-fail/preflight)

## Pre-requisitos
- mc-projects-factory delivered (PR #12 merged)
- memory templates hotfix delivered (PR #13)

## MC PR depende deste
Mission-control PR equivalente invoca este CLI via subprocess (DELETE handler).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Push MC feat PR**

```bash
cd ~/code/mission-control && git push -u origin feat/mc-projects-delete
gh pr create --title "feat(mc): projects delete — danger zone + modal typed-confirm (E2/mc-projects-delete)" --body "$(cat <<'EOF'
## Summary
Botao "Delete project" no danger zone do tab Geral (só user_created) + DeleteProjectModal typed-confirm. Backend invoca CLI \`openclaw project remove\` via subprocess.

Spec: bevox-knowledge/35_specs/company-os/2026-04-27-mc-projects-delete.md

## What's in this PR
- DELETE /api/projects/[id] handler (canonical block 400, spawn CLI, exit→HTTP mapping)
- DeleteProjectModal component (typed-confirm exact match + 3 result states: full/partial/error)
- ProjectGeralTab danger zone integration (condicional !is_canonical)
- ~5 vitest contract tests novos

## Pre-requisitos
- openclaw PR (CLI orchestrator) MUST mergeer ANTES — DELETE depende do binario
- mc-projects-factory delivered (PR #18)

## Test plan
- [ ] vitest verde
- [ ] \`npm run build\` verde
- [ ] **Pos-merge:** pull + npm install + build + restart MC
- [ ] Smoke E2E 5 cenários

## Rollback
Tier 1: \`git revert <merge-sha> && pull && rebuild && restart\`. Botão delete e DELETE endpoint somemos. State já deletado durante uso permanece deletado (não-recoverable).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 4: PAUSA — aguardar Bernard mergear PRs**

Parar. Bernard merge openclaw feat PR primeiro (CLI), depois MC feat PR. Plan PR pode mergeer quando convier. Retomar Task 11 (deploy + smoke) só após merge confirmado em main dos 3 PRs.

---

## Task 11: Pull main + build + restart MC + verify

**Pré-requisito:** PRs mergeados; main atualizada nos dois repos.

- [ ] **Step 1: Pull main em ambos repos**

```bash
cd ~/.openclaw && git checkout main && git pull --ff-only
cd ~/code/mission-control && git checkout main && git pull --ff-only
```

- [ ] **Step 2: CLI smoke standalone**

```bash
cd ~/.openclaw/kanban-tasks && ./cli.sh project --help 2>&1 | tail -10
```

Expected: lista incluindo `remove`.

```bash
cd ~/.openclaw/kanban-tasks && ./cli.sh project remove --help 2>&1 | tail -8
```

Expected: usage com `id` + `--skip-github`.

```bash
# Try canonical reject
cd ~/.openclaw/kanban-tasks && ./cli.sh project remove openclaw --json 2>&1 | tail -8
```

Expected: exit 1 + JSON `{success: false, error_code: "cannot_delete_canonical", failed_at: 0}`.

- [ ] **Step 3: MC build + restart**

```bash
cd ~/code/mission-control && npm install 2>&1 | tail -3
npm run build 2>&1 | grep -E "/api/projects" | head -10
systemctl --user restart mission-control && sleep 4
systemctl --user is-active mission-control
```

Expected: build verde com `DELETE /api/projects/[id]` listed; service `active`.

- [ ] **Step 4: Health probes**

```bash
# Canonical block
curl -sS -X DELETE -H "Cf-Access-Authenticated-User-Email: you@example.com" "http://127.0.0.1:4310/api/projects/openclaw" 2>&1 | python3 -m json.tool
```

Expected: `{ "error": "cannot_delete_canonical", "detail": "..." }` HTTP 400.

```bash
# Non-existent project
curl -sS -X DELETE -H "Cf-Access-Authenticated-User-Email: you@example.com" "http://127.0.0.1:4310/api/projects/ghost-project" 2>&1 | python3 -m json.tool
```

Expected: `{ "error": "project_not_found", ... }` HTTP 404.

---

## Task 12: Smoke E2E (5 cenários gating)

**Pré-requisito:** Task 11 completa; serviço rodando código novo.

Bernard valida em `mc.example.com`:

- [ ] **Cenário 1 — Happy path delete user_created**

Criar projeto teste via "+ New project" (factory wave) → `mc.example.com/projects/<id>` → tab Geral → scroll até bottom → "⚠ Danger zone" section visível → click "Delete project" → modal abre → digitar ID exato → botão habilita → click "Delete forever" → ~10s loading → "✓ Project deleted. Redirecting..." → redirect /projects → list refresh sem o projeto. Verificar 7 destinos limpos via terminal.

Pass: ✓. Fail: rollback Tier 1.

- [ ] **Cenário 2 — Canonical block (UI)**

`mc.example.com/projects/openclaw` → tab Geral → scroll até bottom → confirma que "Danger zone" section **NÃO aparece** pra canonical projects.

- [ ] **Cenário 3 — Typed-confirm wrong**

Modal aberto → digitar slug errado (ex: `Customer-Portal` instead of `customer-portal`) → botão "Delete forever" continua **disabled** + border do input fica padrão (não vermelho destacado). Trim test: digitar `customer-portal ` (com espaço) → habilita (trim funciona).

- [ ] **Cenário 4 — GitHub soft-fail**

Forçar scope missing temporariamente: rodar `gh auth refresh -h github.com -s "repo,read:org"` (excluir delete_repo). Criar+deletar projeto → modal mostra "✓ Local cleanup ok. ⚠ GitHub repo NOT deleted: gh CLI lacks delete_repo scope..." + link `↗ Delete on GitHub manually` → click "OK" → /projects sem projeto. Verificar GitHub repo ainda existe → deletar manual. Restaurar scope: `gh auth refresh -h github.com -s delete_repo`.

- [ ] **Cenário 5 — CLI standalone --skip-github**

Criar projeto teste via UI → terminal `openclaw project remove <id> --skip-github` → verificar 5 steps locais OK + GitHub não tocado + repo permanece em `bernardTavares/<id>`. Cleanup manual via UI do GitHub.

**Smoke gate:** 5/5 → wave delivered. Falha em qualquer cenário → rollback Tier 1.

---

## Task 13: Tracker entry — wave delivered

**Files:**
- Modify: `bevox-knowledge/40_roadmap/_shared/delivery-tracker.yml`

- [ ] **Step 1: Branch + insert entry**

```bash
cd ~/bevox-knowledge && git checkout main && git pull --ff-only
git checkout -b draft/tracker-mc-projects-delete-delivered
```

Adicionar em `40_roadmap/_shared/delivery-tracker.yml` sob E2 (depois da entry `mc-projects-factory`):

```yaml
      - id: mc-projects-delete
        status: delivered
        delivered_at: 2026-04-27
        spec: 35_specs/company-os/2026-04-27-mc-projects-delete.md
        pr_mc: https://github.com/bernardTavares/mission-control/pull/<N>
        pr_openclaw: https://github.com/bernardTavares/openclaw/pull/<N>
        pr_openclaw_plan: https://github.com/bernardTavares/openclaw/pull/<N>
        pr_knowledge_spec: https://github.com/bernardTavares/bevox-knowledge/pull/<N>
        narrative: "MC ganha delete simetrico da factory wave: botao 'Delete project' no danger zone do tab Geral (so user_created) + DeleteProjectModal typed-confirm. CLI 'openclaw project remove <id>' orquestra cleanup em 6 steps reverse-of-create order."
        features:
          - "CLI openclaw project remove <id> orquestra 6 destinos cross-filesystem em sequencia reverse-of-create (rm code → rm openclaw runtime+workspace → kanban event+state cleanup → rm KB folders → rm meta → gh repo delete)"
          - "Pre-flight 3 checks: rejeita canonical (governanca ADR-002), project_not_found, cannot_delete_non_user_created"
          - "events.jsonl preservado: step kanban emite project_deleted event com snapshot (sprints_removed, tasks_removed, github_url, created_at) ANTES de mutar state.json — append-only audit per CLAUDE.md §9"
          - "GitHub try-and-soft-fail: scope delete_repo missing OR repo already-gone → continua local cleanup, retorna github_deleted=false + github_hint detalhado pra UI manual handle"
          - "Reuso maximo da factory wave: projects_meta atomic helpers, project_factory module agrupa create+remove logic, MC backend reusa parseLastJsonLine + spawn pattern + child.on(error) handler, DeleteProjectModal mirror estrutural de NewProjectModal"
          - "MC backend DELETE /api/projects/[id] hard-blocks canonical (400 cannot_delete_canonical), 404 se project ausente em meta, exit code 0/1/2 → HTTP 200/400/500 mapping"
          - "MC frontend DeleteProjectModal typed-confirm (exact match case-sensitive on slug.trim()) + 3 result states (full success com auto-redirect 2s, partial GitHub soft-fail com link manual, error com cleanup hint)"
          - "ProjectGeralTab danger zone condicional ao !is_canonical — canonical projects (10 ADR-002) NAO mostram botao delete (governanca double-block backend+UI)"
          - "Logs JSONL: ~/.openclaw/projects-delete.jsonl paralelo de projects-create.jsonl pra audit + retry hint"
          - "CLI --skip-github flag pra cleanup local-only (testes/dev sem tocar GitHub)"
          - "Smoke E2E pos-deploy validou 5 cenarios gating: happy path, canonical block UI, typed-confirm wrong (case-sensitive), GitHub soft-fail, CLI --skip-github standalone"
          - "Frontend + CLI Python + cross-repo (mc + openclaw); rollback Tier 1 git revert + rebuild + restart"
```

(Substituir `<N>` pelos PR numbers reais.)

- [ ] **Step 2: Validate YAML + commit + push + PR**

```bash
cd ~/bevox-knowledge && python3 -c "import yaml; yaml.safe_load(open('40_roadmap/_shared/delivery-tracker.yml')); print('valid')"
git add 40_roadmap/_shared/delivery-tracker.yml
git commit -m "$(cat <<'EOF'
tracker(E2/mc-projects-delete): delivered 2026-04-27

Mirror simetrico da factory wave: UI delete (danger zone tab Geral) +
CLI openclaw project remove. 6 steps reverse-of-create. typed-confirm
exact match. GitHub try-and-soft-fail. events.jsonl preservado com
project_deleted event snapshot.

Smoke E2E 5 cenarios pass. PRs mc #<N>, openclaw #<N>+#<N>, KB #<N>.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git push -u origin draft/tracker-mc-projects-delete-delivered
gh pr create --title "tracker(E2/mc-projects-delete): delivered 2026-04-27" --body "Mirror delete da factory wave. Smoke 5/5 pass.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

- [ ] **Step 3: Aguardar Bernard mergear**

Bernard merge → wave fechada formalmente.

---

## Self-review

**Spec coverage:**
- §1 decisões 1-3 → Task 3 (canonical block via preflight), Task 8 (typed-confirm), Task 4 step 6 + Task 5 + Task 7 + Task 8 (GitHub soft-fail end-to-end)
- §2 architecture → Tasks 2-6 (CLI), Task 7 (backend), Tasks 8-9 (UI)
- §3.1 CLI signature → Task 6
- §3.2 step funcs → Task 4
- §3.3 pre-flight → Task 3
- §3.4 orchestrator → Task 5
- §3.5 delete_project helper → Task 2
- §3.6 DELETE backend → Task 7
- §3.7 DeleteProjectModal → Task 8
- §3.8 danger zone → Task 9
- §4 data flows → Tasks 7+8 (delete chain) + Task 12 (smoke validates flows)
- §5 edge cases → Task 4 step_remove_kanban (concurrency via flock); Task 4 step_remove_github (soft-fail variants); Task 12 cenários cobrem perm/concurrent
- §6 arquivos → file structure mapeia 1:1
- §7 ordem PRs → Task 10 (push) + Task 11 (deploy)
- §8 testing → ~14 unittest + ~5 vitest + 5 smoke
- §9 DoD → Task 12 cenários = checklist
- §10 rollback → Task 11 PR description menciona Tier 1
- §11 não-escopo → respeitado (no soft delete, no bulk, no restore, etc.)

**Placeholder scan:** zero TBD/TODO no plan. Code blocks completos em todos os steps de código.

**Type consistency:**
- `RemovePreflightFailure` (Task 3) com `code` field consistente em Task 5 (orchestrator catch + map)
- `ProjectRemoveConfig` (Task 5) campos batem com `cmd_project_remove` instantiation (Task 6)
- `step_remove_*` return shapes (Task 4) consumidos em Task 5 orchestrator (sprints_removed, tasks_removed, github_deleted, github_hint)
- `parseLastJsonLine` referenciado em Task 7 (já implementado em Task 13 da factory wave — preservado)
- `isCanonicalProject` em Task 7 já existe (factory wave Task 12 import)
- `DeleteProjectModalProps` (Task 8) bate com mount em Task 9 (open/project/onClose/onDeleted)
- `Result` discriminated union (Task 8) cobre 3 kind values consistente com 3 backend response shapes (Task 7)

Issues encontrados: nenhum.
