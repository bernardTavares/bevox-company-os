"""Tests for project_factory.py — slugify + ID validation + pre-flight checks.

Spec: bevox-knowledge/35_specs/company-os/2026-04-26-mc-projects-factory.md §3.2
"""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from lib.project_factory import (
    slugify,
    is_valid_id,
    RESERVED_IDS,
    PreflightFailure,
    RemovePreflightFailure,
    StepFailure,
    check_id_collision,
    check_filesystems_writable,
    check_gh_auth,
    check_github_repo_free,
    render_template,
    step_1_create_kb_folders,
    step_2_kanban_bootstrap,
    step_3_create_workspace,
    step_4_meta_insert,
    step_5_code_init,
    step_6_github_push,
    run_remove_preflight,
    create_project,
    ProjectCreateConfig,
)
from lib.provisioners.knowledge import ProvisionResult


def _fake_provision_result(slug: str, prd_text: str = "") -> ProvisionResult:
    """Stub ProvisionResult for create_project orchestrator tests."""
    return ProvisionResult(
        state="provisioned",
        slot=slug,
        branch=f"draft/{slug}-knowledge-bootstrap",
        worktree_path=f"/tmp/bevox-knowledge-worktrees/draft__{slug}-knowledge-bootstrap",
        commit_hash="deadbeefcafe1234",
        branch_url=(
            "https://github.com/bernardTavares/bevox-knowledge"
            f"/tree/draft/{slug}-knowledge-bootstrap"
        ),
        folders_created=[
            f"00_inbox/{slug}", f"10_prd/{slug}", f"20_architecture/{slug}",
            f"30_adr/{slug}", f"35_specs/{slug}", f"40_roadmap/{slug}",
            f"50_releases/{slug}", f"60_customer-feedback/{slug}",
            f"70_metrics/{slug}",
        ],
        prd_committed=bool(prd_text and prd_text.strip()),
    )


class TestSlugify(unittest.TestCase):
    def test_lowercase_kebab(self):
        self.assertEqual(slugify("Customer Portal"), "customer-portal")

    def test_strip_diacritics(self):
        self.assertEqual(slugify("Notação Operacional"), "notacao-operacional")

    def test_collapses_repeated_hyphens(self):
        self.assertEqual(slugify("Foo  --  Bar"), "foo-bar")

    def test_strip_special_chars(self):
        self.assertEqual(slugify("Foo & Bar / Baz!"), "foo-bar-baz")

    def test_strip_leading_trailing_hyphens(self):
        self.assertEqual(slugify("  -- Foo --  "), "foo")

    def test_truncates_at_40_chars(self):
        long_name = "Lorem Ipsum " * 10
        result = slugify(long_name)
        self.assertLessEqual(len(result), 40)
        self.assertFalse(result.endswith("-"), "no trailing hyphen post-truncate")


class TestIsValidId(unittest.TestCase):
    def test_accepts_kebab_case(self):
        self.assertTrue(is_valid_id("customer-portal"))
        self.assertTrue(is_valid_id("foo-bar-baz"))
        self.assertTrue(is_valid_id("a1"))

    def test_rejects_uppercase(self):
        self.assertFalse(is_valid_id("Customer-Portal"))

    def test_rejects_starting_digit(self):
        self.assertFalse(is_valid_id("1-foo"))

    def test_rejects_starting_or_ending_hyphen(self):
        self.assertFalse(is_valid_id("-foo"))
        self.assertFalse(is_valid_id("foo-"))

    def test_rejects_too_short_or_long(self):
        self.assertFalse(is_valid_id("a"))
        self.assertFalse(is_valid_id("a" * 41))

    def test_rejects_reserved(self):
        for reserved in RESERVED_IDS:
            self.assertFalse(is_valid_id(reserved), f"{reserved} should be reserved")

    def test_rejects_special_chars(self):
        self.assertFalse(is_valid_id("foo_bar"))
        self.assertFalse(is_valid_id("foo bar"))
        self.assertFalse(is_valid_id("foo/bar"))


class TestCheckIdCollision(unittest.TestCase):
    def test_collision_in_yml(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            projects_yml = tdir / "projects.yml"
            projects_yml.write_text("projects:\n  - openclaw\n  - bevox-mobile\n")
            meta_json = tdir / "projects-meta.json"
            meta_json.write_text('{"version": 1, "projects": {}}')
            with self.assertRaises(PreflightFailure) as ctx:
                check_id_collision("openclaw", projects_yml, meta_json)
            self.assertEqual(ctx.exception.code, "collision")

    def test_collision_in_meta(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            projects_yml = tdir / "projects.yml"
            projects_yml.write_text("projects: []\n")
            meta_json = tdir / "projects-meta.json"
            meta_json.write_text('{"version": 1, "projects": {"customer-portal": {}}}')
            with self.assertRaises(PreflightFailure) as ctx:
                check_id_collision("customer-portal", projects_yml, meta_json)
            self.assertEqual(ctx.exception.code, "collision")

    def test_passes_for_unique(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            projects_yml = tdir / "projects.yml"
            projects_yml.write_text("projects:\n  - openclaw\n")
            meta_json = tdir / "projects-meta.json"
            meta_json.write_text('{"version": 1, "projects": {}}')
            check_id_collision("totally-new", projects_yml, meta_json)


class TestCheckFilesystemsWritable(unittest.TestCase):
    def test_all_writable_passes(self):
        with tempfile.TemporaryDirectory() as td:
            kb = Path(td) / "kb"
            kb.mkdir()
            oc = Path(td) / "oc"
            oc.mkdir()
            code = Path(td) / "code"
            code.mkdir()
            check_filesystems_writable(kb, oc, code)

    def test_missing_dir_raises(self):
        with tempfile.TemporaryDirectory() as td:
            kb = Path(td) / "missing"
            oc = Path(td) / "oc"
            oc.mkdir()
            code = Path(td) / "code"
            code.mkdir()
            with self.assertRaises(PreflightFailure) as ctx:
                check_filesystems_writable(kb, oc, code)
            self.assertIn("missing", ctx.exception.code)


class TestCheckGhAuth(unittest.TestCase):
    @patch("lib.project_factory.subprocess.run")
    def test_ok(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        check_gh_auth()

    @patch("lib.project_factory.subprocess.run")
    def test_unauthorized(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="not logged in")
        with self.assertRaises(PreflightFailure) as ctx:
            check_gh_auth()
        self.assertEqual(ctx.exception.code, "gh_auth_required")


class TestCheckGithubRepoFree(unittest.TestCase):
    @patch("lib.project_factory.subprocess.run")
    def test_404_means_free(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="HTTP 404")
        check_github_repo_free("bernardTavares", "new-project")

    @patch("lib.project_factory.subprocess.run")
    def test_existing_raises(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="repo exists")
        with self.assertRaises(PreflightFailure) as ctx:
            check_github_repo_free("bernardTavares", "openclaw")
        self.assertEqual(ctx.exception.code, "github_collision")


class TestRenderTemplate(unittest.TestCase):
    def test_substitutes_placeholders(self):
        with tempfile.TemporaryDirectory() as td:
            tmpl = Path(td) / "test.tmpl"
            tmpl.write_text("Hello $name, $description")
            result = render_template(tmpl, name="Foo", description="bar")
            self.assertEqual(result, "Hello Foo, bar")


class TestRenderTemplateBraces(unittest.TestCase):
    def test_braces_in_description_safe(self):
        with tempfile.TemporaryDirectory() as td:
            kb_dir = Path(td)
            templates_dir = Path(f"{Path.home()}/.openclaw/kanban-tasks/templates")
            # Description with curly braces — would break str.format
            paths = step_1_create_kb_folders(
                slug="brace-test",
                name="Brace Test",
                description="App with {curly} braces and ${dollar}",
                kb_dir=kb_dir,
                templates_dir=templates_dir,
                date_str="2026-04-26",
            )
            prd = kb_dir / "10_prd" / "brace-test" / "2026-04-26-brace-test-prd.md"
            content = prd.read_text()
            self.assertIn("{curly} braces", content)
            self.assertIn("${dollar}", content)


class TestStep1CreateKbFolders(unittest.TestCase):
    def test_creates_folders_and_stubs(self):
        with tempfile.TemporaryDirectory() as td:
            kb_dir = Path(td)
            templates_dir = Path(f"{Path.home()}/.openclaw/kanban-tasks/templates")
            paths = step_1_create_kb_folders(
                slug="customer-portal",
                name="Customer Portal",
                description="App de portal",
                kb_dir=kb_dir,
                templates_dir=templates_dir,
                date_str="2026-04-26",
            )
            prd = kb_dir / "10_prd" / "customer-portal" / "2026-04-26-customer-portal-prd.md"
            rm = kb_dir / "40_roadmap" / "customer-portal" / "2026-04-26-customer-portal-roadmap.md"
            self.assertTrue(prd.exists())
            self.assertTrue(rm.exists())
            content = prd.read_text()
            self.assertIn("Customer Portal", content)
            self.assertIn("App de portal", content)
            self.assertIn("Status:** stub", content)
            self.assertEqual(paths, [str(prd), str(rm)])

    def test_idempotent_skips_existing(self):
        with tempfile.TemporaryDirectory() as td:
            kb_dir = Path(td)
            templates_dir = Path(f"{Path.home()}/.openclaw/kanban-tasks/templates")
            step_1_create_kb_folders(
                slug="x", name="X", description="", kb_dir=kb_dir,
                templates_dir=templates_dir, date_str="2026-04-26",
            )
            # Second call doesn't raise
            step_1_create_kb_folders(
                slug="x", name="X", description="", kb_dir=kb_dir,
                templates_dir=templates_dir, date_str="2026-04-26",
            )


class TestStep2KanbanBootstrap(unittest.TestCase):
    @patch("lib.project_factory.sprint.bootstrap")
    @patch("lib.project_factory.task.add_project")
    def test_calls_existing_helpers(self, mock_add, mock_bootstrap):
        mock_add.return_value = {"ok": True, "name": "foo"}
        mock_bootstrap.return_value = {"ok": True, "created": [{"id": "s1"}, {"id": "s2"}]}
        result = step_2_kanban_bootstrap(slug="foo", actor="bernard")
        mock_add.assert_called_once_with("foo", actor="bernard")
        mock_bootstrap.assert_called_once_with(actor="bernard", projects=["foo"], dry_run=False)
        self.assertEqual(result["sprints_created"], 2)
        self.assertIn("project_add", result)


def _build_workspace_template_fixture(openclaw_dir: Path) -> Path:
    """Build a minimal workspace-template/ for tests that exercise step_3."""
    template_dir = openclaw_dir / "workspace-template"
    template_dir.mkdir(parents=True)
    # Persona stubs
    for fname in ("IDENTITY.md", "SOUL.md", "BOOTSTRAP.md", "HEARTBEAT.md",
                  "MEMORY.md", "TOOLS.md", "USER.md", "AGENTS.md"):
        (template_dir / fname).write_text(
            f"# {fname} for {{{{PROJECT_NAME}}}} ({{{{SLUG}}}})\n"
        )
    # Memory subtree
    mem = template_dir / "memory"
    mem.mkdir()
    for fname in ("MEMORY.md", "decisions.md", "lessons.md",
                  "people.md", "pending.md", "projects.md"):
        (mem / fname).write_text(f"memory/{fname} for {{{{PROJECT_NAME}}}}\n")
    (mem / "context").mkdir()
    for fname in ("business-context.md", "decisions.md", "lessons.md", "people.md"):
        (mem / "context" / fname).write_text(
            f"context/{fname} for {{{{PROJECT_NAME}}}}\n"
        )
    (mem / "feedback").mkdir()
    for fname in ("tone.json", "content.json", "tasks.json"):
        (mem / "feedback" / fname).write_text("{}\n")
    (mem / "integrations").mkdir()
    (mem / "integrations" / "README.md").write_text(
        "integrations for {{PROJECT_NAME}}\n"
    )
    (mem / "projects").mkdir()
    (mem / "sessions").mkdir()
    return template_dir


class TestStep3CreateWorkspace(unittest.TestCase):
    def test_creates_runtime_dirs_and_persona_stubs(self):
        with tempfile.TemporaryDirectory() as td:
            openclaw_dir = Path(td)
            _build_workspace_template_fixture(openclaw_dir)
            templates_dir = Path(f"{Path.home()}/.openclaw/kanban-tasks/templates")
            result = step_3_create_workspace(
                slug="customer-portal",
                name="Customer Portal",
                openclaw_dir=openclaw_dir,
                templates_dir=templates_dir,
                date_str="2026-04-26",
            )
            # Runtime workspace
            self.assertTrue((openclaw_dir / "customer-portal" / "clarifications").is_dir())
            self.assertTrue((openclaw_dir / "customer-portal" / "notifications").is_dir())
            self.assertTrue((openclaw_dir / "customer-portal" / "scripts").is_dir())
            # Persona stubs cloned from workspace-template/ with markers substituted
            workspace_dir = openclaw_dir / "workspace-customer-portal"
            self.assertTrue(workspace_dir.is_dir())
            for fname in ["IDENTITY.md", "SOUL.md", "BOOTSTRAP.md", "HEARTBEAT.md",
                          "MEMORY.md", "TOOLS.md", "USER.md", "AGENTS.md"]:
                f = workspace_dir / fname
                self.assertTrue(f.exists(), f"missing {fname}")
                content = f.read_text()
                self.assertIn("Customer Portal", content)
                self.assertIn("customer-portal", content)
                self.assertNotIn("{{PROJECT_NAME}}", content)
                self.assertNotIn("{{SLUG}}", content)
            self.assertTrue((workspace_dir / "memory").is_dir())
            self.assertIn("files_written", result)
            self.assertFalse(result["already_existed"])

    def test_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            openclaw_dir = Path(td)
            _build_workspace_template_fixture(openclaw_dir)
            templates_dir = Path(f"{Path.home()}/.openclaw/kanban-tasks/templates")
            step_3_create_workspace(
                slug="x", name="X", openclaw_dir=openclaw_dir,
                templates_dir=templates_dir, date_str="2026-04-26",
            )
            # Second call doesn't raise (idempotent — returns already_existed=True)
            result = step_3_create_workspace(
                slug="x", name="X", openclaw_dir=openclaw_dir,
                templates_dir=templates_dir, date_str="2026-04-26",
            )
            self.assertTrue(result["already_existed"])


class TestStep4MetaInsert(unittest.TestCase):
    def test_inserts_user_created_entry(self):
        with tempfile.TemporaryDirectory() as td:
            meta_path = Path(td) / "meta.json"
            result = step_4_meta_insert(
                slug="customer-portal",
                name="Customer Portal",
                description="App de portal",
                github_url="https://github.com/bernardTavares/customer-portal",
                meta_path=meta_path,
                date_iso="2026-04-26T12:00:00Z",
            )
            import json as _json
            data = _json.loads(meta_path.read_text())
            entry = data["projects"]["customer-portal"]
            self.assertEqual(entry["name"], "Customer Portal")
            self.assertEqual(entry["source"], "user_created")
            self.assertIsNone(entry["bot_id"])
            self.assertIsNone(entry["bot_username"])
            self.assertIsNone(entry["bot_port"])
            self.assertEqual(entry["created_at"], "2026-04-26T12:00:00Z")
            self.assertEqual(result["meta_path"], str(meta_path))


class TestStep5CodeInit(unittest.TestCase):
    def test_initializes_local_repo(self):
        with tempfile.TemporaryDirectory() as td:
            code_dir = Path(td)
            templates_dir = Path(f"{Path.home()}/.openclaw/kanban-tasks/templates")
            result = step_5_code_init(
                slug="customer-portal",
                name="Customer Portal",
                description="App de portal",
                code_dir=code_dir,
                templates_dir=templates_dir,
                date_str="2026-04-26",
                actor="bernard",
            )
            project_path = code_dir / "customer-portal"
            self.assertTrue(project_path.is_dir())
            self.assertTrue((project_path / ".git").is_dir())
            readme = project_path / "README.md"
            self.assertTrue(readme.exists())
            content = readme.read_text()
            self.assertIn("Customer Portal", content)
            self.assertIn("App de portal", content)
            log = subprocess.run(
                ["git", "-C", str(project_path), "log", "--oneline"],
                capture_output=True, text=True,
            )
            self.assertEqual(log.returncode, 0)
            self.assertIn("bootstrap", log.stdout.lower())
            self.assertEqual(result["repo_path"], str(project_path))

    def test_fails_if_dir_exists(self):
        with tempfile.TemporaryDirectory() as td:
            code_dir = Path(td)
            (code_dir / "x").mkdir()
            templates_dir = Path(f"{Path.home()}/.openclaw/kanban-tasks/templates")
            with self.assertRaises(StepFailure) as ctx:
                step_5_code_init(
                    slug="x", name="X", description="", code_dir=code_dir,
                    templates_dir=templates_dir, date_str="2026-04-26",
                    actor="bernard",
                )
            self.assertEqual(ctx.exception.step, 5)
            self.assertEqual(ctx.exception.code, "code_dir_exists")


class TestStep6GithubPush(unittest.TestCase):
    @patch("lib.project_factory.subprocess.run")
    def test_invokes_gh_create_with_push(self, mock_run):
        with tempfile.TemporaryDirectory() as td:
            repo_path = Path(td) / "repo"
            repo_path.mkdir()
            mock_run.return_value = MagicMock(returncode=0, stdout="created", stderr="")
            result = step_6_github_push(
                slug="customer-portal",
                org="bernardTavares",
                repo_path=repo_path,
            )
            create_cmd = mock_run.call_args[0][0]
            self.assertEqual(create_cmd[0], "gh")
            self.assertIn("repo", create_cmd)
            self.assertIn("create", create_cmd)
            self.assertIn("bernardTavares/customer-portal", create_cmd)
            self.assertIn("--private", create_cmd)
            self.assertIn("--push", create_cmd)
            self.assertEqual(result["github_url"],
                             "https://github.com/bernardTavares/customer-portal")

    @patch("lib.project_factory.subprocess.run")
    def test_raises_step_failure_on_gh_error(self, mock_run):
        with tempfile.TemporaryDirectory() as td:
            repo_path = Path(td) / "repo"
            repo_path.mkdir()
            mock_run.return_value = MagicMock(returncode=1, stderr="HTTP 422")
            with self.assertRaises(StepFailure) as ctx:
                step_6_github_push(
                    slug="x", org="bernardTavares", repo_path=repo_path,
                )
            self.assertEqual(ctx.exception.step, 6)
            self.assertEqual(ctx.exception.code, "gh_create_failed")


class TestCreateProject(unittest.TestCase):
    def _build_config(self, td):
        config = ProjectCreateConfig(
            kb_dir=Path(td) / "kb",
            openclaw_dir=Path(td) / "openclaw",
            code_dir=Path(td) / "code",
            meta_path=Path(td) / "openclaw" / "projects-meta.json",
            log_path=Path(td) / "openclaw" / "projects-create.jsonl",
            templates_dir=Path(f"{Path.home()}/.openclaw/kanban-tasks/templates"),
            org="bernardTavares",
        )
        config.kb_dir.mkdir()
        config.openclaw_dir.mkdir()
        config.code_dir.mkdir()
        # Mock projects.yml + git for kb_clean check
        kanban_dir = config.openclaw_dir / "kanban-tasks"
        kanban_dir.mkdir()
        (kanban_dir / "projects.yml").write_text("projects: []\n")
        # Minimal workspace-template fixture for step_3 (Phase 1: clone-based)
        template_dir = config.openclaw_dir / "workspace-template"
        template_dir.mkdir()
        (template_dir / "IDENTITY.md").write_text(
            "Voz {{PROJECT_NAME}} ({{SLUG}})\n"
        )
        (template_dir / "memory").mkdir()
        (template_dir / "memory" / "MEMORY.md").write_text(
            "Memory for {{PROJECT_NAME}}\n"
        )
        return config

    @patch("lib.project_factory.provision_knowledge")
    @patch("lib.project_factory.subprocess.run")
    @patch("lib.project_factory.sprint.bootstrap")
    @patch("lib.project_factory.task.add_project")
    def test_happy_path(
        self, mock_add, mock_bootstrap, mock_run, mock_provision,
    ):
        with tempfile.TemporaryDirectory() as td:
            config = self._build_config(td)
            mock_add.return_value = {"name": "demo-project", "noop": False}
            mock_bootstrap.return_value = {"created": ["S1", "S2"]}
            mock_provision.return_value = _fake_provision_result("demo-project")
            # Mock subprocess.run for: gh auth status (ok), gh repo view (404=free),
            # git -C kb status (clean), git init/add/commit (ok), gh repo create (ok)
            def fake_run(cmd, **kwargs):
                if cmd[:3] == ["gh", "auth", "status"]:
                    return MagicMock(returncode=0)
                if cmd[:3] == ["gh", "repo", "view"]:
                    return MagicMock(returncode=1, stderr="HTTP 404")
                if cmd[:2] == ["git", "-C"] and "status" in cmd:
                    return MagicMock(returncode=0, stdout="")
                return MagicMock(returncode=0, stdout="ok", stderr="")
            mock_run.side_effect = fake_run

            result = create_project(
                name="Demo Project",
                slug="demo-project",
                description="",
                config=config,
                actor="bernard",
            )
            self.assertTrue(result["success"], result)
            self.assertEqual(result["steps_completed"], 7)
            self.assertEqual(
                result["github_url"],
                "https://github.com/bernardTavares/demo-project",
            )
            log_lines = config.log_path.read_text().strip().splitlines()
            self.assertEqual(len(log_lines), 7)
            for line in log_lines:
                entry = json.loads(line)
                self.assertEqual(entry["status"], "ok")
            # provision_knowledge invoked exactly once
            mock_provision.assert_called_once()

    @patch("lib.project_factory.provision_knowledge")
    @patch("lib.project_factory.subprocess.run")
    @patch("lib.project_factory.sprint.bootstrap")
    @patch("lib.project_factory.task.add_project")
    def test_partial_failure_logs_steps(
        self, mock_add, mock_bootstrap, mock_run, mock_provision,
    ):
        """If step 6 (code_init) fails (code dir already has subdir), log 1-5 ok + 6 failed."""
        with tempfile.TemporaryDirectory() as td:
            config = self._build_config(td)
            (config.code_dir / "demo-project").mkdir()  # force step 5 to fail
            mock_add.return_value = {"name": "demo-project", "noop": False}
            mock_bootstrap.return_value = {"created": ["S1", "S2"]}
            mock_provision.return_value = _fake_provision_result("demo-project")
            def fake_run(cmd, **kwargs):
                if cmd[:3] == ["gh", "auth", "status"]:
                    return MagicMock(returncode=0)
                if cmd[:3] == ["gh", "repo", "view"]:
                    return MagicMock(returncode=1, stderr="HTTP 404")
                if cmd[:2] == ["git", "-C"] and "status" in cmd:
                    return MagicMock(returncode=0, stdout="")
                return MagicMock(returncode=0, stdout="", stderr="")
            mock_run.side_effect = fake_run

            result = create_project(
                name="Demo Project", slug="demo-project", description="",
                config=config, actor="bernard",
            )
            self.assertFalse(result["success"])
            self.assertEqual(result["failed_at"], 6)
            self.assertEqual(result["steps_completed"], 5)
            log_lines = config.log_path.read_text().strip().splitlines()
            self.assertEqual(len(log_lines), 6)
            self.assertEqual(json.loads(log_lines[-1])["status"], "failed")
            self.assertEqual(json.loads(log_lines[-1])["step"], 6)


class TestStep3MemoryTree(unittest.TestCase):
    def test_creates_memory_subtree(self):
        with tempfile.TemporaryDirectory() as td:
            openclaw_dir = Path(td)
            _build_workspace_template_fixture(openclaw_dir)
            templates_dir = Path(f"{Path.home()}/.openclaw/kanban-tasks/templates")
            result = step_3_create_workspace(
                slug="memtest",
                name="Memory Test",
                openclaw_dir=openclaw_dir,
                templates_dir=templates_dir,
                date_str="2026-04-27",
            )
            mem = openclaw_dir / "workspace-memtest" / "memory"
            # Top-level files
            for fname in ["MEMORY.md", "decisions.md", "lessons.md",
                          "people.md", "pending.md", "projects.md"]:
                self.assertTrue((mem / fname).exists(), f"missing {fname}")
                content = (mem / fname).read_text()
                self.assertIn("Memory Test", content)
            # Subdirs with files
            for sub_path in ["context/business-context.md", "context/decisions.md",
                             "context/lessons.md", "context/people.md",
                             "feedback/tone.json", "feedback/content.json",
                             "feedback/tasks.json", "integrations/README.md"]:
                self.assertTrue((mem / sub_path).exists(), f"missing {sub_path}")
            # Empty runtime dirs
            self.assertTrue((mem / "projects").is_dir())
            self.assertTrue((mem / "sessions").is_dir())
            self.assertEqual(len(list((mem / "projects").iterdir())), 0)
            self.assertEqual(len(list((mem / "sessions").iterdir())), 0)
            # Return dict (new clone-based contract)
            self.assertIn("files_written", result)
            self.assertFalse(result["already_existed"])

    def test_idempotent_skips_existing_memory_files(self):
        with tempfile.TemporaryDirectory() as td:
            openclaw_dir = Path(td)
            _build_workspace_template_fixture(openclaw_dir)
            templates_dir = Path(f"{Path.home()}/.openclaw/kanban-tasks/templates")
            step_3_create_workspace(
                slug="x", name="X", openclaw_dir=openclaw_dir,
                templates_dir=templates_dir, date_str="2026-04-27",
            )
            # Modify a file to detect overwrite
            mem_decisions = openclaw_dir / "workspace-x" / "memory" / "decisions.md"
            mem_decisions.write_text("custom content — should be preserved")
            # Second call (full-clone idempotence: skips entire workspace-<slug>/)
            result = step_3_create_workspace(
                slug="x", name="X", openclaw_dir=openclaw_dir,
                templates_dir=templates_dir, date_str="2026-04-27",
            )
            self.assertEqual(mem_decisions.read_text(), "custom content — should be preserved")
            self.assertTrue(result["already_existed"])


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
            meta_path.write_text('{"version": 1, "projects": {"weird": {"source": "imported"}}}')
            with self.assertRaises(RemovePreflightFailure) as ctx:
                run_remove_preflight("weird", meta_path)
            self.assertEqual(ctx.exception.code, "cannot_delete_non_user_created")

    def test_passes_for_user_created(self):
        with tempfile.TemporaryDirectory() as td:
            meta_path = Path(td) / "meta.json"
            meta_path.write_text('{"version": 1, "projects": {"my-app": {"source": "user_created"}}}')
            run_remove_preflight("my-app", meta_path)  # doesn't raise


import shutil
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
            self.assertFalse(result["removed"])


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

    @patch("lib.project_factory.subprocess.run")
    def test_soft_fail_on_already_gone(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1, stdout="",
            stderr="Could not resolve to a Repository (404)",
        )
        result = step_remove_github("my-app", "bernardTavares")
        self.assertFalse(result["github_deleted"])
        self.assertIn("already deleted", result["github_hint"])


class TestStepRemoveKanban(unittest.TestCase):
    def test_emits_event_and_cleans_state(self):
        with tempfile.TemporaryDirectory() as td:
            openclaw_dir = Path(td)
            kanban_dir = openclaw_dir / "kanban-tasks"
            kanban_dir.mkdir()
            (kanban_dir / "projects.yml").write_text(
                "projects:\n  - my-app\n  - other\n"
            )
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

            updated = json.loads((kanban_dir / "state.json").read_text())
            self.assertEqual(len(updated["sprints"]), 1)
            self.assertEqual(updated["sprints"][0]["project"], "other")
            self.assertEqual(len(updated["tasks"]), 1)

            yml = (kanban_dir / "projects.yml").read_text()
            self.assertNotIn("- my-app", yml)
            self.assertIn("- other", yml)

            events = (kanban_dir / "events.jsonl").read_text().strip().splitlines()
            self.assertEqual(len(events), 1)
            event = json.loads(events[0])
            self.assertEqual(event["type"], "project_deleted")
            self.assertEqual(event["project"], "my-app")
            self.assertEqual(sorted(event["snapshot"]["sprints_removed"]), ["sprint-1", "sprint-2"])
            self.assertEqual(event["snapshot"]["tasks_removed"], ["T-1"])

            self.assertEqual(result["sprints_removed"], 2)
            self.assertEqual(result["tasks_removed"], 1)


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
        # Seed local files
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
            self.assertEqual(result["steps_completed"], 7)
            self.assertTrue(result["github_deleted"])
            self.assertFalse((config.code_dir / "my-app").exists())
            self.assertFalse((config.openclaw_dir / "my-app").exists())
            self.assertFalse((config.openclaw_dir / "workspace-my-app").exists())
            self.assertFalse((config.kb_dir / "10_prd" / "my-app").exists())
            log_lines = config.log_path.read_text().strip().splitlines()
            self.assertEqual(len(log_lines), 7)
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
            self.assertTrue(result["success"])
            self.assertEqual(result["steps_completed"], 7)
            self.assertFalse(result["github_deleted"])
            self.assertIn("delete_repo", result["github_hint"])

    def test_preflight_canonical_rejection(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            openclaw_dir = td_path / "openclaw"
            openclaw_dir.mkdir()
            meta_path = openclaw_dir / "projects-meta.json"
            meta_path.write_text(
                '{"version": 1, "projects": {"openclaw": {"source": "canonical"}}}'
            )
            config = ProjectRemoveConfig(
                kb_dir=td_path / "kb", openclaw_dir=openclaw_dir,
                code_dir=td_path / "code",
                meta_path=meta_path,
                log_path=openclaw_dir / "projects-delete.jsonl",
                org="bernardTavares",
            )
            result = remove_project(slug="openclaw", config=config, actor="bernard")
            self.assertFalse(result["success"])
            self.assertEqual(result["error_code"], "cannot_delete_canonical")
            self.assertEqual(result["failed_at"], 0)


def test_step_3_clones_workspace_template_and_substitutes_markers(tmp_path):
    """step_3_create_workspace must cp -r workspace-template/ then sed markers."""
    from lib.project_factory import step_3_create_workspace

    # Arrange: build a minimal workspace-template fixture under tmp_path
    openclaw_dir = tmp_path / ".openclaw"
    template_dir = openclaw_dir / "workspace-template"
    template_dir.mkdir(parents=True)
    (template_dir / "memory").mkdir()
    (template_dir / "memory" / "integrations").mkdir()
    (template_dir / "memory" / "projects").mkdir()
    (template_dir / "IDENTITY.md").write_text(
        "Voz {{PROJECT_NAME}} para slug {{SLUG}} (domínio {{DOMAIN}}).\n"
    )
    (template_dir / "memory" / "projects" / "{{SLUG}}.md").write_text(
        "Projeto {{PROJECT_NAME}}\n"
    )

    # Act: clone for slug=foo
    result = step_3_create_workspace(
        slug="foo",
        name="Foo Project",
        openclaw_dir=openclaw_dir,
        templates_dir=tmp_path / "unused",  # legacy arg, kept for signature
        date_str="2026-04-28",
        domain="Produto",
    )

    # Assert: workspace-foo exists with substituted content
    workspace_foo = openclaw_dir / "workspace-foo"
    assert workspace_foo.is_dir()
    identity = (workspace_foo / "IDENTITY.md").read_text()
    assert "Voz Foo Project para slug foo (domínio Produto)." in identity
    assert "{{PROJECT_NAME}}" not in identity
    assert "{{SLUG}}" not in identity
    assert "{{DOMAIN}}" not in identity

    # Filename substitution: {{SLUG}}.md → foo.md
    project_file = workspace_foo / "memory" / "projects" / "foo.md"
    assert project_file.is_file()
    assert (workspace_foo / "memory" / "projects" / "{{SLUG}}.md").exists() is False

    assert result["workspace_dir"] == str(workspace_foo)


def test_step_3_idempotent_skip_if_exists(tmp_path):
    """step_3 must skip cloning if workspace-<slug>/ already exists."""
    from lib.project_factory import step_3_create_workspace

    openclaw_dir = tmp_path / ".openclaw"
    template_dir = openclaw_dir / "workspace-template"
    template_dir.mkdir(parents=True)
    (template_dir / "IDENTITY.md").write_text("from template\n")

    workspace_foo = openclaw_dir / "workspace-foo"
    workspace_foo.mkdir(parents=True)
    (workspace_foo / "IDENTITY.md").write_text("pre-existing\n")

    result = step_3_create_workspace(
        slug="foo", name="Foo",
        openclaw_dir=openclaw_dir,
        templates_dir=tmp_path / "unused",
        date_str="2026-04-28",
        domain="Produto",
    )

    # Pre-existing content preserved
    assert (workspace_foo / "IDENTITY.md").read_text() == "pre-existing\n"
    assert result["already_existed"] is True


def test_step_3_fails_when_template_missing(tmp_path):
    """step_3 must raise StepFailure if workspace-template/ is absent."""
    import pytest
    from lib.project_factory import step_3_create_workspace, StepFailure

    openclaw_dir = tmp_path / ".openclaw"
    openclaw_dir.mkdir()
    # NOTE: no workspace-template/ created

    with pytest.raises(StepFailure) as exc:
        step_3_create_workspace(
            slug="foo", name="Foo",
            openclaw_dir=openclaw_dir,
            templates_dir=tmp_path / "unused",
            date_str="2026-04-28",
            domain="Produto",
        )
    assert exc.value.code == "template_missing"


def test_step_3_idempotent_returns_files_written_key(tmp_path):
    """Both branches of step_3 return a dict with 'files_written' key (uniform contract)."""
    from lib.project_factory import step_3_create_workspace

    openclaw_dir = tmp_path / ".openclaw"
    template_dir = openclaw_dir / "workspace-template"
    template_dir.mkdir(parents=True)
    (template_dir / "IDENTITY.md").write_text("hello\n")

    # First call: creates workspace
    first = step_3_create_workspace(
        slug="foo", name="Foo",
        openclaw_dir=openclaw_dir,
        templates_dir=tmp_path / "unused",
        date_str="2026-04-28",
        domain="",
    )
    assert "files_written" in first
    assert first["already_existed"] is False
    assert len(first["files_written"]) >= 1

    # Second call: idempotent — workspace already exists
    second = step_3_create_workspace(
        slug="foo", name="Foo",
        openclaw_dir=openclaw_dir,
        templates_dir=tmp_path / "unused",
        date_str="2026-04-28",
        domain="",
    )
    assert "files_written" in second
    assert second["already_existed"] is True
    assert second["files_written"] == []


def _setup_workspace_with_pending_markers(tmp_path):
    """Helper: create workspace-foo/ with PERSONA: PENDING markers."""
    workspace = tmp_path / ".openclaw" / "workspace-foo"
    workspace.mkdir(parents=True)
    (workspace / "IDENTITY.md").write_text(
        "<!-- PERSONA: PENDING -->\nplaceholder identity\n"
    )
    (workspace / "SOUL.md").write_text(
        "<!-- PERSONA: PENDING -->\nplaceholder soul\n"
    )
    (workspace / "memory" / "projects").mkdir(parents=True)
    (workspace / "memory" / "projects" / "foo.md").write_text(
        "<!-- PERSONA: PENDING -->\nplaceholder project memory\n"
    )
    return workspace


def test_step_4_writes_persona_files_on_success(tmp_path):
    """step_4_persona_llm replaces PENDING content with extractor output."""
    from unittest.mock import patch
    from lib.project_factory import step_4_persona_llm

    workspace = _setup_workspace_with_pending_markers(tmp_path)

    fake_result = {
        "status": "generated",
        "identity": "real identity content\n",
        "soul": "real soul content\n",
        "memory_projects": "real project content\n",
    }

    with patch("lib.project_factory.persona_extractor.extract_persona",
               return_value=fake_result):
        out = step_4_persona_llm(
            slug="foo",
            name="Foo",
            domain="Produto",
            date_str="2026-04-28",
            prd_text="PRD here",
            workspace_dir=workspace,
        )

    assert out["persona_status"] == "generated"
    assert (workspace / "IDENTITY.md").read_text() == "real identity content\n"
    assert (workspace / "SOUL.md").read_text() == "real soul content\n"
    assert (workspace / "memory" / "projects" / "foo.md").read_text() == \
        "real project content\n"
    assert not (workspace / "PERSONA_PENDING.md").exists()


def test_step_4_writes_pending_marker_on_failure(tmp_path):
    """When extractor returns error, step_4 writes PERSONA_PENDING.md."""
    from unittest.mock import patch
    from lib.project_factory import step_4_persona_llm

    workspace = _setup_workspace_with_pending_markers(tmp_path)
    pre_identity = (workspace / "IDENTITY.md").read_text()

    fake_result = {"status": "error", "error": "timeout"}

    with patch("lib.project_factory.persona_extractor.extract_persona",
               return_value=fake_result):
        out = step_4_persona_llm(
            slug="foo",
            name="Foo",
            domain="Produto",
            date_str="2026-04-28",
            prd_text="PRD here",
            workspace_dir=workspace,
        )

    assert out["persona_status"] == "pending"
    assert out["error"] == "timeout"
    assert (workspace / "IDENTITY.md").read_text() == pre_identity
    assert (workspace / "PERSONA_PENDING.md").exists()
    pending_md = (workspace / "PERSONA_PENDING.md").read_text()
    assert "regenerate-persona foo" in pending_md
    assert "timeout" in pending_md


def test_step_4_writes_pending_marker_on_invalid(tmp_path):
    """Status 'invalid' (e.g. malformed JSON) also writes PENDING marker."""
    from unittest.mock import patch
    from lib.project_factory import step_4_persona_llm

    workspace = _setup_workspace_with_pending_markers(tmp_path)
    fake = {"status": "invalid", "error": "json decode: ..."}

    with patch("lib.project_factory.persona_extractor.extract_persona",
               return_value=fake):
        out = step_4_persona_llm(
            slug="foo", name="Foo", domain="Produto",
            date_str="2026-04-28", prd_text="x",
            workspace_dir=workspace,
        )

    assert out["persona_status"] == "pending"
    assert (workspace / "PERSONA_PENDING.md").exists()


def test_step_4_skips_when_already_generated(tmp_path):
    """If IDENTITY.md says persona_status: generated, step_4 skips (idempotent)."""
    from unittest.mock import patch
    from lib.project_factory import step_4_persona_llm

    workspace = _setup_workspace_with_pending_markers(tmp_path)
    (workspace / "IDENTITY.md").write_text(
        "---\npersona_status: generated\n---\nReal content already.\n"
    )

    with patch("lib.project_factory.persona_extractor.extract_persona") as mock_e:
        out = step_4_persona_llm(
            slug="foo", name="Foo", domain="Produto",
            date_str="2026-04-28", prd_text="x",
            workspace_dir=workspace,
        )

    mock_e.assert_not_called()
    assert out["persona_status"] == "already_generated"


def test_step_4_skipped_via_feature_flag(tmp_path, monkeypatch):
    """OPENCLAW_PERSONA_LLM=0 → step_4 is no-op."""
    from unittest.mock import patch
    from lib.project_factory import step_4_persona_llm

    workspace = _setup_workspace_with_pending_markers(tmp_path)
    monkeypatch.setenv("OPENCLAW_PERSONA_LLM", "0")

    with patch("lib.project_factory.persona_extractor.extract_persona") as mock_e:
        out = step_4_persona_llm(
            slug="foo", name="Foo", domain="Produto",
            date_str="2026-04-28", prd_text="x",
            workspace_dir=workspace,
        )

    mock_e.assert_not_called()
    assert out["persona_status"] == "skipped_flag"


def test_step_4_skips_when_no_prd_text(tmp_path):
    """Empty PRD → no point calling LLM; pending marker with that reason."""
    from unittest.mock import patch
    from lib.project_factory import step_4_persona_llm

    workspace = _setup_workspace_with_pending_markers(tmp_path)

    with patch("lib.project_factory.persona_extractor.extract_persona") as mock_e:
        out = step_4_persona_llm(
            slug="foo", name="Foo", domain="Produto",
            date_str="2026-04-28", prd_text="",
            workspace_dir=workspace,
        )

    mock_e.assert_not_called()
    assert out["persona_status"] == "pending"
    assert "no prd" in out["error"].lower()
    assert (workspace / "PERSONA_PENDING.md").exists()


def test_preflight_passes_when_no_prd_no_claude_check_needed(tmp_path, monkeypatch):
    """No PRD provided → claude CLI check is skipped (allowing persona-less creation)."""
    from unittest.mock import patch
    from lib.project_factory import run_preflight, check_claude_cli

    # Should not raise even if claude is missing — because prd_provided=False
    with patch("lib.project_factory.subprocess.run",
               side_effect=FileNotFoundError("claude")):
        check_claude_cli(prd_provided=False)


def test_preflight_fails_when_prd_provided_without_claude(monkeypatch):
    """PRD provided but claude CLI missing → PreflightFailure(claude_cli_missing)."""
    import pytest
    from unittest.mock import patch
    from lib.project_factory import check_claude_cli, PreflightFailure

    with patch("lib.project_factory.subprocess.run",
               side_effect=FileNotFoundError("claude")):
        with pytest.raises(PreflightFailure) as exc:
            check_claude_cli(prd_provided=True)
    assert exc.value.code == "claude_cli_missing"


def test_preflight_fails_when_claude_returns_nonzero(monkeypatch):
    """PRD + claude exits non-zero → PreflightFailure(claude_cli_unhealthy)."""
    import pytest
    import subprocess
    from unittest.mock import patch, MagicMock
    from lib.project_factory import check_claude_cli, PreflightFailure

    bad = MagicMock(spec=subprocess.CompletedProcess)
    bad.returncode = 2
    bad.stderr = "auth required"

    with patch("lib.project_factory.subprocess.run", return_value=bad):
        with pytest.raises(PreflightFailure) as exc:
            check_claude_cli(prd_provided=True)
    assert exc.value.code == "claude_cli_unhealthy"


def test_preflight_skipped_via_feature_flag(monkeypatch):
    """OPENCLAW_PERSONA_LLM=0 → claude check skipped even with PRD."""
    from unittest.mock import patch
    from lib.project_factory import check_claude_cli

    monkeypatch.setenv("OPENCLAW_PERSONA_LLM", "0")
    # Should not raise — claude lookup never happens
    with patch("lib.project_factory.subprocess.run",
               side_effect=FileNotFoundError("claude")):
        check_claude_cli(prd_provided=True)


def test_step_remove_bot_profile_no_bot_id(tmp_path):
    """When meta has no bot_id for this project, step is no-op."""
    from lib.project_factory import step_remove_bot_profile

    openclaw_dir = tmp_path / ".openclaw"
    openclaw_dir.mkdir()
    meta_path = openclaw_dir / "projects-meta.json"
    import json
    meta_path.write_text(json.dumps({
        "version": 1,
        "projects": [{"id": "noboi", "name": "NoBot"}],
    }))

    result = step_remove_bot_profile(
        slug="noboi", openclaw_dir=openclaw_dir, meta_path=meta_path,
    )
    assert result["removed"] is False
    assert result["reason"] == "no_bot_id"


def test_step_remove_bot_profile_full_cleanup(tmp_path, monkeypatch):
    """Bot connected → profile dir + env file removed; systemctl invoked."""
    from unittest.mock import MagicMock
    import json
    from lib.project_factory import step_remove_bot_profile

    openclaw_dir = tmp_path / ".openclaw"
    openclaw_dir.mkdir()

    # Build profile dir + env file
    profile = tmp_path / ".openclaw-voz-myproj"
    profile.mkdir()
    (profile / "openclaw.json").write_text("{}")
    (profile / "memory").mkdir()
    (profile / "memory" / "test.md").write_text("x")

    bots_dir = openclaw_dir / "gateway" / "bots"
    bots_dir.mkdir(parents=True)
    env_file = bots_dir / "voz-myproj.env"
    env_file.write_text("BOT_TOKEN_VOZ_MYPROJ=fake\n")

    meta_path = openclaw_dir / "projects-meta.json"
    meta_path.write_text(json.dumps({
        "version": 1,
        "projects": [{"id": "myproj", "bot_id": "voz-myproj"}],
    }))

    # Override HOME so step looks under tmp_path
    monkeypatch.setenv("HOME", str(tmp_path))

    # Mock subprocess.run for systemctl calls — record commands
    calls = []

    def fake_run(cmd, *args, **kwargs):
        calls.append(cmd)
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    monkeypatch.setattr("lib.project_factory.subprocess.run", fake_run)

    result = step_remove_bot_profile(
        slug="myproj", openclaw_dir=openclaw_dir, meta_path=meta_path,
    )

    assert result["removed"] is True
    assert result["bot_id"] == "voz-myproj"
    assert result["profile_removed"] is True
    assert result["env_removed"] is True
    assert result["systemd_disabled"] is True
    assert result["soft_failures"] == []
    assert not profile.exists()
    assert not env_file.exists()

    # systemctl stop + disable + daemon-reload were called
    cmd_strings = [" ".join(c) for c in calls]
    assert any("stop" in s and "voz-myproj" in s for s in cmd_strings)
    assert any("disable" in s and "voz-myproj" in s for s in cmd_strings)
    assert any("daemon-reload" in s for s in cmd_strings)


def test_step_remove_bot_profile_partial_artifacts(tmp_path, monkeypatch):
    """Profile dir missing but env present → env still cleaned; soft state correct."""
    from unittest.mock import MagicMock
    import json
    from lib.project_factory import step_remove_bot_profile

    openclaw_dir = tmp_path / ".openclaw"
    openclaw_dir.mkdir()

    bots_dir = openclaw_dir / "gateway" / "bots"
    bots_dir.mkdir(parents=True)
    env_file = bots_dir / "voz-myproj.env"
    env_file.write_text("x")

    # NOTE: no profile dir created

    meta_path = openclaw_dir / "projects-meta.json"
    meta_path.write_text(json.dumps({
        "version": 1,
        "projects": [{"id": "myproj", "bot_id": "voz-myproj"}],
    }))

    monkeypatch.setenv("HOME", str(tmp_path))

    def fake_run(cmd, *args, **kwargs):
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    monkeypatch.setattr("lib.project_factory.subprocess.run", fake_run)

    result = step_remove_bot_profile(
        slug="myproj", openclaw_dir=openclaw_dir, meta_path=meta_path,
    )

    assert result["removed"] is True
    assert result["profile_removed"] is False  # was already absent
    assert result["env_removed"] is True
    assert not env_file.exists()


def test_step_remove_bot_profile_systemctl_soft_fail(tmp_path, monkeypatch):
    """systemctl returning non-zero is recorded but doesn't raise."""
    from unittest.mock import MagicMock
    import json
    from lib.project_factory import step_remove_bot_profile

    openclaw_dir = tmp_path / ".openclaw"
    openclaw_dir.mkdir()

    profile = tmp_path / ".openclaw-voz-myproj"
    profile.mkdir()

    meta_path = openclaw_dir / "projects-meta.json"
    meta_path.write_text(json.dumps({
        "version": 1,
        "projects": [{"id": "myproj", "bot_id": "voz-myproj"}],
    }))

    monkeypatch.setenv("HOME", str(tmp_path))

    def fake_run(cmd, *args, **kwargs):
        result = MagicMock()
        if "disable" in cmd:
            result.returncode = 1
            result.stderr = "Unit not loaded"
        else:
            result.returncode = 0
            result.stderr = ""
        return result

    monkeypatch.setattr("lib.project_factory.subprocess.run", fake_run)

    result = step_remove_bot_profile(
        slug="myproj", openclaw_dir=openclaw_dir, meta_path=meta_path,
    )

    # Doesn't raise; soft_failures records the disable error
    assert result["removed"] is True
    assert result["systemd_disabled"] is False
    assert any("disable" in f.get("step", "") for f in result["soft_failures"])
    assert any("Unit not loaded" in f.get("error", "") for f in result["soft_failures"])


class TestCreateProjectCapabilities(unittest.TestCase):
    """W1: verify create_project populates capabilities sub-object correctly."""

    def _build_config(self, td):
        config = ProjectCreateConfig(
            kb_dir=Path(td) / "kb",
            openclaw_dir=Path(td) / "openclaw",
            code_dir=Path(td) / "code",
            meta_path=Path(td) / "openclaw" / "projects-meta.json",
            log_path=Path(td) / "openclaw" / "projects-create.jsonl",
            templates_dir=Path(f"{Path.home()}/.openclaw/kanban-tasks/templates"),
            org="bernardTavares",
        )
        config.kb_dir.mkdir()
        config.openclaw_dir.mkdir()
        config.code_dir.mkdir()
        kanban_dir = config.openclaw_dir / "kanban-tasks"
        kanban_dir.mkdir()
        (kanban_dir / "projects.yml").write_text("projects: []\n")
        template_dir = config.openclaw_dir / "workspace-template"
        template_dir.mkdir()
        (template_dir / "IDENTITY.md").write_text(
            "Voz {{PROJECT_NAME}} ({{SLUG}})\n"
        )
        return config

    @patch("lib.project_factory.provision_knowledge")
    @patch("lib.project_factory.subprocess.run")
    @patch("lib.project_factory.sprint.bootstrap")
    @patch("lib.project_factory.task.add_project")
    def test_capabilities_populated_after_happy_path(
        self, mock_add, mock_bootstrap, mock_run, mock_provision,
    ):
        with tempfile.TemporaryDirectory() as td:
            config = self._build_config(td)
            mock_add.return_value = {"name": "demo", "noop": False}
            mock_bootstrap.return_value = {"created": [{"id": "S1"}, {"id": "S2"}]}
            mock_provision.return_value = _fake_provision_result("demo")

            def fake_run(cmd, **kwargs):
                if cmd[:3] == ["gh", "auth", "status"]:
                    return MagicMock(returncode=0)
                if cmd[:3] == ["gh", "repo", "view"]:
                    return MagicMock(returncode=1, stderr="HTTP 404")
                if cmd[:2] == ["git", "-C"] and "status" in cmd:
                    return MagicMock(returncode=0, stdout="")
                return MagicMock(returncode=0, stdout="ok", stderr="")
            mock_run.side_effect = fake_run

            result = create_project(
                name="Demo", slug="demo", description="App demo",
                config=config, actor="bernard",
            )
            self.assertTrue(result["success"])

            data = json.loads(config.meta_path.read_text())
            entry = data["projects"]["demo"]

            # Schema markers
            self.assertEqual(entry["capabilities_schema_version"], 1)
            self.assertIn("capabilities", entry)

            # Flat legacy fields preserved (backwards-compat readers)
            self.assertEqual(
                entry["github_url"],
                "https://github.com/bernardTavares/demo",
            )
            self.assertEqual(entry["source"], "user_created")
            self.assertIsNone(entry["bot_id"])

            caps = entry["capabilities"]
            # All 8 capabilities present
            self.assertEqual(set(caps.keys()), {
                "code_repo", "knowledge_slot", "kanban_sprints", "workspace",
                "persona", "bot", "telegram_topics", "mission_control",
            })

            # State assertions per W2 §Persistência (post-provision):
            # knowledge_slot is now provisioned (9/9), with bootstrap branch
            # tracked for W5 doctor.
            self.assertEqual(caps["knowledge_slot"]["state"], "provisioned")
            self.assertEqual(caps["knowledge_slot"]["folders_present"], 9)
            self.assertEqual(caps["knowledge_slot"]["folders_total"], 9)
            self.assertEqual(
                caps["knowledge_slot"]["branch_at_bootstrap"],
                "draft/demo-knowledge-bootstrap",
            )
            self.assertEqual(
                caps["knowledge_slot"]["commit_hash_at_bootstrap"],
                "deadbeefcafe1234",
            )
            self.assertIn("last_bootstrap_at", caps["knowledge_slot"])
            self.assertEqual(caps["kanban_sprints"]["state"], "provisioned")
            self.assertEqual(caps["workspace"]["state"], "provisioned")
            # No PRD provided → persona pending → partial
            self.assertEqual(caps["persona"]["state"], "partial")
            # code_repo provisioned after step_6 github_push
            self.assertEqual(caps["code_repo"]["state"], "provisioned")
            self.assertEqual(
                caps["code_repo"]["github"],
                "https://github.com/bernardTavares/demo",
            )
            # Capabilities not covered by create flow: absent
            self.assertEqual(caps["bot"]["state"], "absent")
            self.assertEqual(caps["telegram_topics"]["state"], "absent")
            self.assertEqual(caps["mission_control"]["state"], "absent")

    @patch("lib.project_factory.provision_knowledge")
    @patch("lib.project_factory.subprocess.run")
    @patch("lib.project_factory.sprint.bootstrap")
    @patch("lib.project_factory.task.add_project")
    def test_capabilities_partial_on_step_6_failure(
        self, mock_add, mock_bootstrap, mock_run, mock_provision,
    ):
        """When code_init fails, code_repo stays absent and earlier caps reflect their states."""
        with tempfile.TemporaryDirectory() as td:
            config = self._build_config(td)
            (config.code_dir / "demo").mkdir()  # forces step 6 (code_init) to fail
            mock_add.return_value = {"name": "demo", "noop": False}
            mock_bootstrap.return_value = {"created": [{"id": "S1"}]}
            mock_provision.return_value = _fake_provision_result("demo")

            def fake_run(cmd, **kwargs):
                if cmd[:3] == ["gh", "auth", "status"]:
                    return MagicMock(returncode=0)
                if cmd[:3] == ["gh", "repo", "view"]:
                    return MagicMock(returncode=1, stderr="HTTP 404")
                if cmd[:2] == ["git", "-C"] and "status" in cmd:
                    return MagicMock(returncode=0, stdout="")
                return MagicMock(returncode=0, stdout="", stderr="")
            mock_run.side_effect = fake_run

            result = create_project(
                name="Demo", slug="demo", description="",
                config=config, actor="bernard",
            )
            self.assertFalse(result["success"])
            self.assertEqual(result["failed_at"], 6)

            data = json.loads(config.meta_path.read_text())
            caps = data["projects"]["demo"]["capabilities"]
            # Steps 1-5 completed → those capabilities updated
            # W2: knowledge_slot now provisioned (9/9) instead of partial (2/9)
            self.assertEqual(caps["knowledge_slot"]["state"], "provisioned")
            self.assertEqual(caps["kanban_sprints"]["state"], "provisioned")
            self.assertEqual(caps["workspace"]["state"], "provisioned")
            # code_repo never reached → still absent
            self.assertEqual(caps["code_repo"]["state"], "absent")


class TestCreateProjectSkeletonRollback(unittest.TestCase):
    """W1 review fix #1: failure in early steps must roll back the
    skeleton entry so retry of `openclaw project create <slug>` is not
    rejected with error_code=collision.
    """

    def _build_config(self, td):
        config = ProjectCreateConfig(
            kb_dir=Path(td) / "kb",
            openclaw_dir=Path(td) / "openclaw",
            code_dir=Path(td) / "code",
            meta_path=Path(td) / "openclaw" / "projects-meta.json",
            log_path=Path(td) / "openclaw" / "projects-create.jsonl",
            templates_dir=Path(f"{Path.home()}/.openclaw/kanban-tasks/templates"),
            org="bernardTavares",
        )
        config.kb_dir.mkdir()
        config.openclaw_dir.mkdir()
        config.code_dir.mkdir()
        kanban_dir = config.openclaw_dir / "kanban-tasks"
        kanban_dir.mkdir()
        (kanban_dir / "projects.yml").write_text("projects: []\n")
        template_dir = config.openclaw_dir / "workspace-template"
        template_dir.mkdir()
        (template_dir / "IDENTITY.md").write_text(
            "Voz {{PROJECT_NAME}} ({{SLUG}})\n"
        )
        return config

    @patch("lib.project_factory.provision_knowledge")
    @patch("lib.project_factory.subprocess.run")
    @patch("lib.project_factory.sprint.bootstrap")
    @patch("lib.project_factory.task.add_project")
    def test_create_failure_rolls_back_skeleton(
        self, mock_add, mock_bootstrap, mock_run, mock_provision,
    ):
        """Failure in step 2 (kanban_bootstrap) must remove the meta entry."""
        with tempfile.TemporaryDirectory() as td:
            config = self._build_config(td)
            # Force step 2 (kanban_bootstrap) to raise
            mock_add.side_effect = RuntimeError("simulated kanban failure")
            mock_bootstrap.return_value = {"created": []}
            mock_provision.return_value = _fake_provision_result("demo-rollback")

            def fake_run(cmd, **kwargs):
                if cmd[:3] == ["gh", "auth", "status"]:
                    return MagicMock(returncode=0)
                if cmd[:3] == ["gh", "repo", "view"]:
                    return MagicMock(returncode=1, stderr="HTTP 404")
                if cmd[:2] == ["git", "-C"] and "status" in cmd:
                    return MagicMock(returncode=0, stdout="")
                return MagicMock(returncode=0, stdout="", stderr="")
            mock_run.side_effect = fake_run

            result = create_project(
                name="Demo", slug="demo-rollback", description="",
                config=config, actor="bernard",
            )
            self.assertFalse(result["success"])
            self.assertEqual(result["failed_at"], 2)

            data = json.loads(config.meta_path.read_text())
            # Skeleton was rolled back — entry must not exist
            self.assertNotIn(
                "demo-rollback",
                data.get("projects", {}),
                "skeleton entry should have been rolled back after early-step failure",
            )

            # Log must record the rollback for auditability
            log_lines = config.log_path.read_text().strip().splitlines()
            rollback_entries = [
                json.loads(line) for line in log_lines
                if json.loads(line).get("name") == "skeleton_rollback"
            ]
            self.assertEqual(len(rollback_entries), 1)
            self.assertEqual(rollback_entries[0]["status"], "rolled_back")

    @patch("lib.project_factory.provision_knowledge")
    @patch("lib.project_factory.subprocess.run")
    @patch("lib.project_factory.sprint.bootstrap")
    @patch("lib.project_factory.task.add_project")
    def test_step_6_failure_preserves_skeleton(
        self, mock_add, mock_bootstrap, mock_run, mock_provision,
    ):
        """Failure at step 6 (code_init) must NOT roll back — preserves
        capability state visibility (parity with pre-W1 behavior where the
        meta entry existed by step 5 onwards).
        """
        with tempfile.TemporaryDirectory() as td:
            config = self._build_config(td)
            (config.code_dir / "demo").mkdir()  # forces step 6 (code_init) to fail
            mock_add.return_value = {"name": "demo", "noop": False}
            mock_bootstrap.return_value = {"created": [{"id": "S1"}]}
            mock_provision.return_value = _fake_provision_result("demo")

            def fake_run(cmd, **kwargs):
                if cmd[:3] == ["gh", "auth", "status"]:
                    return MagicMock(returncode=0)
                if cmd[:3] == ["gh", "repo", "view"]:
                    return MagicMock(returncode=1, stderr="HTTP 404")
                if cmd[:2] == ["git", "-C"] and "status" in cmd:
                    return MagicMock(returncode=0, stdout="")
                return MagicMock(returncode=0, stdout="", stderr="")
            mock_run.side_effect = fake_run

            result = create_project(
                name="Demo", slug="demo", description="",
                config=config, actor="bernard",
            )
            self.assertFalse(result["success"])
            self.assertEqual(result["failed_at"], 6)
            # Entry must still exist (not rolled back)
            data = json.loads(config.meta_path.read_text())
            self.assertIn("demo", data["projects"])


if __name__ == "__main__":
    unittest.main()
