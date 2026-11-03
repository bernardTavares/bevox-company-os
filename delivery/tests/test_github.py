"""E6 wave 1 — GitHub integration tests.

Covers:
- Actor matrix extension (3 new event types)
- Pure helpers: build_issue_title, resolve_spec_link, build_issue_body, parse_gh_error
- Subprocess helpers: ensure_delivery_label, create_github_issue
- Projection extension: github_repo in active_specs, github_link in proposals
- Integration: linkage subflow ordering invariants
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import agent


class TestActorMatrixE6(unittest.TestCase):
    """ACTOR_TYPE_MATRIX extension for E6. delivery-agent MUST stay restricted
    to E5 types (task.proposed + scan.run)."""

    def test_cli_can_emit_spec_github_repo_set(self):
        agent.validate_actor("cli", "spec.github_repo_set")

    def test_cli_can_emit_task_github_linked(self):
        agent.validate_actor("cli", "task.github_linked")

    def test_cli_can_emit_task_github_link_failed(self):
        agent.validate_actor("cli", "task.github_link_failed")

    def test_delivery_agent_cannot_emit_spec_github_repo_set(self):
        with self.assertRaises(agent.ActorError):
            agent.validate_actor("delivery-agent", "spec.github_repo_set")

    def test_delivery_agent_cannot_emit_task_github_linked(self):
        with self.assertRaises(agent.ActorError):
            agent.validate_actor("delivery-agent", "task.github_linked")

    def test_delivery_agent_cannot_emit_task_github_link_failed(self):
        with self.assertRaises(agent.ActorError):
            agent.validate_actor("delivery-agent", "task.github_link_failed")

    def test_delivery_agent_still_can_emit_e5_types(self):
        agent.validate_actor("delivery-agent", "task.proposed")
        agent.validate_actor("delivery-agent", "scan.run")

    def test_unknown_actor_still_rejected(self):
        with self.assertRaises(agent.ActorError):
            agent.validate_actor("github-agent", "task.github_linked")


class TestIssueTitleBuilder(unittest.TestCase):
    """build_issue_title trunca item_text a 80 chars com … se necessário."""

    def test_short_title_unchanged(self):
        result = agent.build_issue_title("Short task")
        self.assertEqual(result, "Short task")

    def test_exactly_80_chars_unchanged(self):
        text = "x" * 80
        result = agent.build_issue_title(text)
        self.assertEqual(result, text)
        self.assertEqual(len(result), 80)

    def test_81_chars_truncated_with_ellipsis(self):
        text = "x" * 81
        result = agent.build_issue_title(text)
        self.assertEqual(len(result), 80)
        self.assertTrue(result.endswith("…"))
        self.assertEqual(result, "x" * 79 + "…")

    def test_long_text_truncated(self):
        text = "a" * 200
        result = agent.build_issue_title(text)
        self.assertEqual(len(result), 80)
        self.assertTrue(result.endswith("…"))

    def test_empty_string(self):
        result = agent.build_issue_title("")
        self.assertEqual(result, "")

    def test_unicode_preserved(self):
        result = agent.build_issue_title("Implementar função ção")
        self.assertEqual(result, "Implementar função ção")


class TestSpecLinkResolver(unittest.TestCase):
    """resolve_spec_link vira markdown link se spec_path começa com namespace
    canônico do bevox-knowledge; caso contrário, retorna raw."""

    def test_35_specs_namespace_becomes_link(self):
        result = agent.resolve_spec_link("35_specs/2026-04-14-e6-...md")
        self.assertEqual(
            result,
            "[35_specs/2026-04-14-e6-...md](https://github.com/bernardTavares/bevox-knowledge/blob/main/35_specs/2026-04-14-e6-...md)"
        )

    def test_30_adr_namespace_becomes_link(self):
        result = agent.resolve_spec_link("30_adr/ADR-001-boundary.md")
        self.assertIn("github.com/bernardTavares/bevox-knowledge/blob/main", result)
        self.assertTrue(result.startswith("["))

    def test_40_roadmap_namespace_becomes_link(self):
        result = agent.resolve_spec_link("40_roadmap/2026-04-09-openclaw.md")
        self.assertTrue(result.startswith("["))
        self.assertIn("github.com", result)

    def test_all_canonical_namespaces_resolve(self):
        for ns in (
            "00_inbox",
            "10_prd",
            "20_architecture",
            "30_adr",
            "35_specs",
            "40_roadmap",
            "50_releases",
            "60_customer-feedback",
            "70_metrics",
            "99_templates",
        ):
            path = f"{ns}/test.md"
            result = agent.resolve_spec_link(path)
            self.assertTrue(
                result.startswith("["),
                f"namespace {ns} should resolve to markdown link, got: {result}"
            )

    def test_non_namespace_returns_raw(self):
        result = agent.resolve_spec_link("/tmp/random/path.md")
        self.assertEqual(result, "/tmp/random/path.md")

    def test_unknown_namespace_returns_raw(self):
        result = agent.resolve_spec_link("src/something.md")
        self.assertEqual(result, "src/something.md")

    def test_no_slash_returns_raw(self):
        result = agent.resolve_spec_link("standalone.md")
        self.assertEqual(result, "standalone.md")

    def test_empty_string_returns_raw(self):
        result = agent.resolve_spec_link("")
        self.assertEqual(result, "")


class TestIssueBodyBuilder(unittest.TestCase):
    """build_issue_body produz markdown determinista bit-para-bit."""

    def _sample_proposal(self):
        return {
            "spec_path": "35_specs/2026-04-14-e6-...md",
            "section_id": "Tarefas",
            "item_text": "Primeiro item dogfood",
            "proposal_id": "prop_356a0bf2b2f8",
            "task_id": "task_c38f0eb59755",
            "key": "8632fa03044e8c2f",
            "proposed_at": "2026-04-14T00:28:00.093Z",
            "resolved_at": "2026-04-14T00:28:02.660Z",
        }

    def test_body_contains_e6_wave_1_opening(self):
        body = agent.build_issue_body(self._sample_proposal())
        self.assertIn("Auto-created by OpenClaw Delivery via GitHub Operations (E6 wave 1)", body)

    def test_body_opening_uses_resolved_at(self):
        body = agent.build_issue_body(self._sample_proposal())
        self.assertIn("on 2026-04-14T00:28:02.660Z", body)

    def test_body_contains_spec_link_markdown(self):
        body = agent.build_issue_body(self._sample_proposal())
        self.assertIn("**Spec:** [35_specs/2026-04-14-e6-...md](https://github.com/bernardTavares/bevox-knowledge/blob/main/35_specs/2026-04-14-e6-...md)", body)

    def test_body_contains_section_and_item(self):
        body = agent.build_issue_body(self._sample_proposal())
        self.assertIn("**Section:** Tarefas", body)
        self.assertIn("**Item:** Primeiro item dogfood", body)

    def test_body_contains_metadata_table(self):
        body = agent.build_issue_body(self._sample_proposal())
        self.assertIn("| Task ID | `task_c38f0eb59755` |", body)
        self.assertIn("| Proposal ID | `prop_356a0bf2b2f8` |", body)
        self.assertIn("| Key | `8632fa03044e8c2f` |", body)
        self.assertIn("| Proposed at | 2026-04-14T00:28:00.093Z |", body)
        self.assertIn("| Accepted at | 2026-04-14T00:28:02.660Z |", body)

    def test_body_footer_mentions_local_sot(self):
        body = agent.build_issue_body(self._sample_proposal())
        self.assertIn("Managed locally in `~/.openclaw/delivery/events.jsonl`", body)
        self.assertIn("GitHub is operational reflex", body)
        self.assertIn("local is source of truth", body)

    def test_body_deterministic(self):
        """Duas chamadas consecutivas com mesma input produzem exatamente o
        mesmo output bit-a-bit."""
        p = self._sample_proposal()
        body1 = agent.build_issue_body(p)
        body2 = agent.build_issue_body(p)
        self.assertEqual(body1, body2)

    def test_body_with_non_namespace_spec_path_is_raw(self):
        p = self._sample_proposal()
        p["spec_path"] = "/tmp/throwaway.md"
        body = agent.build_issue_body(p)
        # Spec field has raw path, not markdown link
        self.assertIn("**Spec:** /tmp/throwaway.md", body)
        self.assertNotIn("[/tmp/throwaway.md]", body)


class TestErrorKindMapping(unittest.TestCase):
    """parse_gh_error mapeia resultado do subprocess.run para 1 dos 8 buckets
    canônicos de error_kind. Retorna (error_kind, message) onde message é
    truncado a 500 chars."""

    def test_returncode_zero_raises(self):
        """parse_gh_error só deve ser chamado quando há erro; sucesso explode."""
        with self.assertRaises(ValueError):
            agent.parse_gh_error(returncode=0, stdout="", stderr="")

    def test_file_not_found_maps_to_gh_not_installed(self):
        exc = FileNotFoundError("No such file or directory: 'gh'")
        kind, msg = agent.parse_gh_error(returncode=None, stdout="", stderr="", exception=exc)
        self.assertEqual(kind, "gh_not_installed")

    def test_timeout_maps_to_network_timeout(self):
        exc = subprocess.TimeoutExpired(cmd=["gh"], timeout=10)
        kind, msg = agent.parse_gh_error(returncode=None, stdout="", stderr="", exception=exc)
        self.assertEqual(kind, "network_timeout")

    def test_auth_error_in_stderr(self):
        stderr = "error: HTTP 401: Bad credentials (https://api.github.com/...)"
        kind, msg = agent.parse_gh_error(returncode=1, stdout="", stderr=stderr)
        self.assertEqual(kind, "gh_auth")

    def test_auth_forbidden_maps_to_gh_auth(self):
        stderr = "HTTP 403: Resource not accessible by integration"
        kind, msg = agent.parse_gh_error(returncode=1, stdout="", stderr=stderr)
        self.assertEqual(kind, "gh_auth")

    def test_not_found_maps_to_repo_not_found(self):
        stderr = "GraphQL: Could not resolve to a Repository with the name 'nonexistent'. (createIssue)"
        kind, msg = agent.parse_gh_error(returncode=1, stdout="", stderr=stderr)
        self.assertEqual(kind, "repo_not_found")

    def test_http_404_maps_to_repo_not_found(self):
        stderr = "HTTP 404: Not Found"
        kind, msg = agent.parse_gh_error(returncode=1, stdout="", stderr=stderr)
        self.assertEqual(kind, "repo_not_found")

    def test_rate_limit_maps_to_rate_limit(self):
        stderr = "HTTP 429: API rate limit exceeded for user ID"
        kind, msg = agent.parse_gh_error(returncode=1, stdout="", stderr=stderr)
        self.assertEqual(kind, "rate_limit")

    def test_rate_limit_text_in_stderr(self):
        stderr = "You have triggered an abuse detection mechanism — rate limit"
        kind, msg = agent.parse_gh_error(returncode=1, stdout="", stderr=stderr)
        self.assertEqual(kind, "rate_limit")

    def test_unknown_nonzero_maps_to_gh_exit_nonzero(self):
        stderr = "error: something weird happened in gh"
        kind, msg = agent.parse_gh_error(returncode=1, stdout="", stderr=stderr)
        self.assertEqual(kind, "gh_exit_nonzero")

    def test_unexpected_exception_maps_to_unknown(self):
        exc = ValueError("surprise!")
        kind, msg = agent.parse_gh_error(returncode=None, stdout="", stderr="", exception=exc)
        self.assertEqual(kind, "unknown")

    def test_message_truncated_to_500_chars(self):
        long_stderr = "x" * 1000
        kind, msg = agent.parse_gh_error(returncode=1, stdout="", stderr=long_stderr)
        self.assertLessEqual(len(msg), 500)

    def test_message_preserves_short_stderr(self):
        stderr = "short error"
        kind, msg = agent.parse_gh_error(returncode=1, stdout="", stderr=stderr)
        self.assertIn("short error", msg)


class TestEnsureDeliveryLabel(unittest.TestCase):
    """ensure_delivery_label best-effort: retorna True se a label existe no
    repo alvo depois da chamada (já existia ou foi criada), False caso
    contrário. Nunca levanta exceção."""

    def _mock_run(self, scenarios):
        """Helper para construir side_effect do subprocess.run."""
        calls = iter(scenarios)
        def side_effect(*args, **kwargs):
            nonlocal calls
            s = next(calls)
            if isinstance(s, Exception):
                raise s
            return MagicMock(returncode=s["returncode"], stdout=s["stdout"], stderr=s["stderr"])
        return side_effect

    def test_label_already_exists(self):
        existing = json.dumps([{"name": "bug"}, {"name": "delivery"}, {"name": "enhancement"}])
        with patch("subprocess.run", side_effect=self._mock_run([
            {"returncode": 0, "stdout": existing, "stderr": ""},
        ])) as m:
            result = agent.ensure_delivery_label("bernardTavares/bevox-knowledge")
            self.assertTrue(result)
            # Should only list, not create (label already exists)
            self.assertEqual(m.call_count, 1)

    def test_label_does_not_exist_create_succeeds(self):
        existing = json.dumps([{"name": "bug"}, {"name": "enhancement"}])
        with patch("subprocess.run", side_effect=self._mock_run([
            {"returncode": 0, "stdout": existing, "stderr": ""},
            {"returncode": 0, "stdout": "", "stderr": ""},
        ])) as m:
            result = agent.ensure_delivery_label("bernardTavares/bevox-knowledge")
            self.assertTrue(result)
            self.assertEqual(m.call_count, 2)  # list + create

    def test_label_does_not_exist_create_fails(self):
        existing = json.dumps([{"name": "bug"}])
        with patch("subprocess.run", side_effect=self._mock_run([
            {"returncode": 0, "stdout": existing, "stderr": ""},
            {"returncode": 1, "stdout": "", "stderr": "HTTP 403: Forbidden"},
        ])):
            result = agent.ensure_delivery_label("bernardTavares/bevox-knowledge")
            self.assertFalse(result)

    def test_list_fails_returns_false(self):
        with patch("subprocess.run", side_effect=self._mock_run([
            {"returncode": 1, "stdout": "", "stderr": "HTTP 404"},
        ])):
            result = agent.ensure_delivery_label("bernardTavares/bevox-knowledge")
            self.assertFalse(result)

    def test_gh_not_installed_returns_false(self):
        with patch("subprocess.run", side_effect=self._mock_run([
            FileNotFoundError("gh"),
        ])):
            result = agent.ensure_delivery_label("bernardTavares/bevox-knowledge")
            self.assertFalse(result)

    def test_list_json_parse_error_returns_false(self):
        with patch("subprocess.run", side_effect=self._mock_run([
            {"returncode": 0, "stdout": "not json", "stderr": ""},
        ])):
            result = agent.ensure_delivery_label("bernardTavares/bevox-knowledge")
            self.assertFalse(result)

    def test_timeout_returns_false(self):
        with patch("subprocess.run", side_effect=self._mock_run([
            subprocess.TimeoutExpired(cmd=["gh"], timeout=10),
        ])):
            result = agent.ensure_delivery_label("bernardTavares/bevox-knowledge")
            self.assertFalse(result)


class TestCreateGithubIssue(unittest.TestCase):
    """create_github_issue(repo, title, body, with_label) -> dict

    Returns: {'issue_number': int, 'issue_url': str} on success
    Raises: GithubIssueError(error_kind, message) on any failure

    GithubIssueError é uma exceção custom do agent que carrega os 2 campos
    já mapeados para evento task.github_link_failed.
    """

    def test_success_returns_issue_dict(self):
        gh_stdout = "https://github.com/bernardTavares/bevox-knowledge/issues/42\n"
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0, stdout=gh_stdout, stderr="")
            result = agent.create_github_issue(
                repo="bernardTavares/bevox-knowledge",
                title="test",
                body="body",
                with_label=True,
            )
            self.assertEqual(result["issue_number"], 42)
            self.assertEqual(
                result["issue_url"],
                "https://github.com/bernardTavares/bevox-knowledge/issues/42"
            )

    def test_success_includes_label_when_with_label_true(self):
        gh_stdout = "https://github.com/x/y/issues/1\n"
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0, stdout=gh_stdout, stderr="")
            agent.create_github_issue(
                repo="x/y", title="t", body="b", with_label=True,
            )
            args = m.call_args[0][0]
            self.assertIn("--label", args)
            self.assertIn("delivery", args)

    def test_success_omits_label_when_with_label_false(self):
        gh_stdout = "https://github.com/x/y/issues/1\n"
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0, stdout=gh_stdout, stderr="")
            agent.create_github_issue(
                repo="x/y", title="t", body="b", with_label=False,
            )
            args = m.call_args[0][0]
            self.assertNotIn("--label", args)

    def test_url_parsing_extracts_number(self):
        for url, expected_num in [
            ("https://github.com/a/b/issues/1\n", 1),
            ("https://github.com/a/b/issues/42\n", 42),
            ("https://github.com/a/b/issues/99999\n", 99999),
        ]:
            with patch("subprocess.run") as m:
                m.return_value = MagicMock(returncode=0, stdout=url, stderr="")
                result = agent.create_github_issue(
                    repo="a/b", title="t", body="b", with_label=False,
                )
                self.assertEqual(result["issue_number"], expected_num)

    def test_malformed_url_raises_unknown(self):
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0, stdout="not a url", stderr="")
            with self.assertRaises(agent.GithubIssueError) as ctx:
                agent.create_github_issue(
                    repo="a/b", title="t", body="b", with_label=False,
                )
            self.assertEqual(ctx.exception.error_kind, "unknown")

    def test_gh_not_installed_raises_mapped(self):
        with patch("subprocess.run", side_effect=FileNotFoundError("gh")):
            with self.assertRaises(agent.GithubIssueError) as ctx:
                agent.create_github_issue(
                    repo="a/b", title="t", body="b", with_label=False,
                )
            self.assertEqual(ctx.exception.error_kind, "gh_not_installed")

    def test_auth_error_raises_mapped(self):
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=1, stdout="", stderr="HTTP 401: Bad credentials")
            with self.assertRaises(agent.GithubIssueError) as ctx:
                agent.create_github_issue(
                    repo="a/b", title="t", body="b", with_label=False,
                )
            self.assertEqual(ctx.exception.error_kind, "gh_auth")

    def test_timeout_raises_mapped(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["gh"], timeout=10)):
            with self.assertRaises(agent.GithubIssueError) as ctx:
                agent.create_github_issue(
                    repo="a/b", title="t", body="b", with_label=False,
                )
            self.assertEqual(ctx.exception.error_kind, "network_timeout")


def _events_to_path(events: list[dict]) -> Path:
    """Helper para testes de projection: escreve eventos num tempfile jsonl."""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
    for evt in events:
        tmp.write(json.dumps(evt) + "\n")
    tmp.close()
    return Path(tmp.name)


class TestProjectionGithubRepo(unittest.TestCase):
    """spec.github_repo_set popula state.active_specs[path].github_repo."""

    def test_no_event_means_null(self):
        e1 = agent.make_event(actor="cli", type="spec.activated", payload={"spec_path": "35_specs/x.md"})
        path = _events_to_path([e1])
        try:
            state = agent.project_state(path)
            self.assertIn("35_specs/x.md", state["active_specs"])
            self.assertIsNone(state["active_specs"]["35_specs/x.md"].get("github_repo"))
        finally:
            path.unlink()

    def test_github_repo_set_populates_field(self):
        e1 = agent.make_event(actor="cli", type="spec.activated", payload={"spec_path": "x.md"})
        e2 = agent.make_event(actor="cli", type="spec.github_repo_set", payload={"spec_path": "x.md", "repo": "bernardTavares/bevox-knowledge"})
        path = _events_to_path([e1, e2])
        try:
            state = agent.project_state(path)
            self.assertEqual(
                state["active_specs"]["x.md"]["github_repo"],
                "bernardTavares/bevox-knowledge"
            )
        finally:
            path.unlink()

    def test_second_set_supersedes_first(self):
        e1 = agent.make_event(actor="cli", type="spec.activated", payload={"spec_path": "x.md"})
        e2 = agent.make_event(actor="cli", type="spec.github_repo_set", payload={"spec_path": "x.md", "repo": "a/b"})
        e3 = agent.make_event(actor="cli", type="spec.github_repo_set", payload={"spec_path": "x.md", "repo": "c/d"})
        path = _events_to_path([e1, e2, e3])
        try:
            state = agent.project_state(path)
            self.assertEqual(state["active_specs"]["x.md"]["github_repo"], "c/d")
        finally:
            path.unlink()

    def test_archive_removes_github_repo(self):
        """Reativação de spec arquivada começa sem github_repo (guardrail Q3)."""
        e1 = agent.make_event(actor="cli", type="spec.activated", payload={"spec_path": "x.md"})
        e2 = agent.make_event(actor="cli", type="spec.github_repo_set", payload={"spec_path": "x.md", "repo": "a/b"})
        e3 = agent.make_event(actor="cli", type="spec.archived", payload={"spec_path": "x.md", "reason": "delivered"})
        e4 = agent.make_event(actor="cli", type="spec.activated", payload={"spec_path": "x.md"})
        path = _events_to_path([e1, e2, e3, e4])
        try:
            state = agent.project_state(path)
            self.assertIn("x.md", state["active_specs"])
            self.assertIsNone(state["active_specs"]["x.md"].get("github_repo"))
        finally:
            path.unlink()


class TestProjectionGithubLink(unittest.TestCase):
    """github_link em state.proposals[...] para proposta accepted."""

    def _accepted_proposal_events(self):
        """Returns a list of events producing an accepted proposal."""
        return [
            agent.make_event(actor="cli", type="spec.activated", payload={"spec_path": "x.md"}),
            agent.make_event(actor="delivery-agent", type="task.proposed", payload={
                "proposal_id": "prop_abc",
                "key": "key1",
                "spec_path": "x.md",
                "section_id": "Tarefas",
                "item_text": "do thing",
                "run_id": "run_1",
            }),
            agent.make_event(actor="cli", type="task.created", payload={
                "proposal_id": "prop_abc",
                "key": "key1",
                "task_id": "task_xyz",
            }),
        ]

    def test_accepted_proposal_without_linkage_has_null(self):
        path = _events_to_path(self._accepted_proposal_events())
        try:
            state = agent.project_state(path)
            self.assertIsNone(state["proposals"]["prop_abc"]["github_link"])
        finally:
            path.unlink()

    def test_task_github_linked_projects_linked_state(self):
        events = self._accepted_proposal_events()
        events.append(agent.make_event(actor="cli", type="task.github_linked", payload={
            "task_id": "task_xyz",
            "key": "key1",
            "repo": "bernardTavares/bevox-knowledge",
            "issue_number": 42,
            "issue_url": "https://github.com/bernardTavares/bevox-knowledge/issues/42",
        }))
        path = _events_to_path(events)
        try:
            state = agent.project_state(path)
            gl = state["proposals"]["prop_abc"]["github_link"]
            self.assertEqual(gl["state"], "linked")
            self.assertEqual(gl["repo"], "bernardTavares/bevox-knowledge")
            self.assertEqual(gl["issue_number"], 42)
            self.assertIsNone(gl["error_kind"])
        finally:
            path.unlink()

    def test_task_github_link_failed_projects_failed_state(self):
        events = self._accepted_proposal_events()
        events.append(agent.make_event(actor="cli", type="task.github_link_failed", payload={
            "task_id": "task_xyz",
            "key": "key1",
            "repo": "bernardTavares/bevox-knowledge",
            "error_kind": "network_timeout",
            "message": "timeout",
        }))
        path = _events_to_path(events)
        try:
            state = agent.project_state(path)
            gl = state["proposals"]["prop_abc"]["github_link"]
            self.assertEqual(gl["state"], "failed")
            self.assertEqual(gl["error_kind"], "network_timeout")
            self.assertIsNone(gl["issue_number"])
            self.assertIsNone(gl["issue_url"])
        finally:
            path.unlink()

    def test_repo_unresolved_has_null_repo(self):
        events = self._accepted_proposal_events()
        events.append(agent.make_event(actor="cli", type="task.github_link_failed", payload={
            "task_id": "task_xyz",
            "key": "key1",
            "repo": None,
            "error_kind": "repo_unresolved",
            "message": "pass --repo or run set-spec-repo",
        }))
        path = _events_to_path(events)
        try:
            state = agent.project_state(path)
            gl = state["proposals"]["prop_abc"]["github_link"]
            self.assertEqual(gl["state"], "failed")
            self.assertEqual(gl["error_kind"], "repo_unresolved")
            self.assertIsNone(gl["repo"])
        finally:
            path.unlink()

    def test_failed_then_linked_supersedes(self):
        events = self._accepted_proposal_events()
        events.append(agent.make_event(actor="cli", type="task.github_link_failed", payload={
            "task_id": "task_xyz", "key": "key1", "repo": "a/b",
            "error_kind": "gh_auth", "message": "401",
        }))
        events.append(agent.make_event(actor="cli", type="task.github_linked", payload={
            "task_id": "task_xyz", "key": "key1",
            "repo": "a/b", "issue_number": 1,
            "issue_url": "https://github.com/a/b/issues/1",
        }))
        path = _events_to_path(events)
        try:
            state = agent.project_state(path)
            gl = state["proposals"]["prop_abc"]["github_link"]
            self.assertEqual(gl["state"], "linked")
            self.assertEqual(gl["issue_number"], 1)
            self.assertIsNone(gl["error_kind"])
        finally:
            path.unlink()

    def test_last_attempt_tracks_event_id(self):
        events = self._accepted_proposal_events()
        linked_evt = agent.make_event(actor="cli", type="task.github_linked", payload={
            "task_id": "task_xyz", "key": "key1",
            "repo": "a/b", "issue_number": 1,
            "issue_url": "https://github.com/a/b/issues/1",
        })
        events.append(linked_evt)
        path = _events_to_path(events)
        try:
            state = agent.project_state(path)
            gl = state["proposals"]["prop_abc"]["github_link"]
            self.assertEqual(gl["last_attempt_event"], linked_evt["event_id"])
            self.assertEqual(gl["last_attempt_at"], linked_evt["ts"])
        finally:
            path.unlink()


class TestLinkageSubflowInvariants(unittest.TestCase):
    """Testa que o linkage subflow preserva os invariantes críticos:
    - task.created é emitido antes de qualquer evento task.github_*
    - repo_unresolved produz task.github_link_failed com repo=null
    - fail-soft: qualquer exceção do gh vira evento failed, não raises
    """

    def setUp(self):
        """Backup original state files."""
        import shutil
        self.tmpdir = Path(tempfile.mkdtemp())
        self.backup_events = self.tmpdir / "backup_events.jsonl"
        self.backup_state = self.tmpdir / "backup_state.json"

        # Backup originals
        if agent.EVENTS_PATH.exists():
            shutil.copy(agent.EVENTS_PATH, self.backup_events)
        if agent.STATE_PATH.exists():
            shutil.copy(agent.STATE_PATH, self.backup_state)

    def tearDown(self):
        """Restore original state files."""
        import shutil
        try:
            if self.backup_events.exists():
                shutil.copy(self.backup_events, agent.EVENTS_PATH)
            elif agent.EVENTS_PATH.exists():
                agent.EVENTS_PATH.unlink()

            if self.backup_state.exists():
                shutil.copy(self.backup_state, agent.STATE_PATH)
            elif agent.STATE_PATH.exists():
                agent.STATE_PATH.unlink()
        finally:
            shutil.rmtree(self.tmpdir)

    def test_accept_ordering_task_created_before_link(self):
        """
        Dado uma proposta pending + spec com github_repo setado,
        quando cmd_accept roda com gh mockado para sucesso,
        então o events.jsonl mostra task.created ANTES de task.github_linked
        (ordem temporal estrita).
        """
        import cli as cli_mod

        # Clear and seed state with test data
        agent.EVENTS_PATH.unlink(missing_ok=True)
        agent.STATE_PATH.unlink(missing_ok=True)

        agent.emit_event_to(agent.EVENTS_PATH, actor="cli", type="spec.activated",
                            payload={"spec_path": "35_specs/x.md"})
        agent.emit_event_to(agent.EVENTS_PATH, actor="cli", type="spec.github_repo_set",
                            payload={"spec_path": "35_specs/x.md", "repo": "bernardTavares/test"})
        agent.emit_event_to(agent.EVENTS_PATH, actor="delivery-agent", type="task.proposed",
                            payload={
                                "proposal_id": "prop_test1",
                                "key": "key_test1",
                                "spec_path": "35_specs/x.md",
                                "section_id": "Tarefas",
                                "item_text": "test item",
                                "run_id": "run_test",
                            })
        agent.rebuild_state()

        # Mock gh for label list/create + issue create
        def mock_run(*args, **kwargs):
            cmd = args[0]
            if "label" in cmd and "list" in cmd:
                return MagicMock(returncode=0, stdout='[{"name":"delivery"}]', stderr="")
            if "issue" in cmd and "create" in cmd:
                return MagicMock(
                    returncode=0,
                    stdout="https://github.com/bernardTavares/test/issues/1\n",
                    stderr="",
                )
            return MagicMock(returncode=1, stdout="", stderr="unexpected")

        with patch("subprocess.run", side_effect=mock_run):
            # Build fake args for cmd_accept
            ns = type("NS", (), {})()
            ns.proposal_id = "prop_test1"
            ns.repo = None
            rc = cli_mod.cmd_accept(ns)
            self.assertEqual(rc, 0)

        # Read events.jsonl and verify ordering
        events = list(agent.iter_events(agent.EVENTS_PATH))
        types = [e["type"] for e in events]
        # Find index of task.created and task.github_linked
        self.assertIn("task.created", types, f"task.created not in events: {types}")
        self.assertIn("task.github_linked", types, f"task.github_linked not in events: {types}")
        tc_idx = types.index("task.created")
        tl_idx = types.index("task.github_linked")
        self.assertLess(tc_idx, tl_idx,
                        f"task.created must come before task.github_linked; got order: {types}")

    def test_accept_with_unresolved_repo_still_emits_task_created(self):
        """
        Dado uma proposta pending + spec sem github_repo setado + sem --repo flag,
        quando cmd_accept roda,
        então task.created é emitido + task.github_link_failed com error_kind=repo_unresolved
        + exit 0.
        """
        import cli as cli_mod

        # Clear and seed state with test data
        agent.EVENTS_PATH.unlink(missing_ok=True)
        agent.STATE_PATH.unlink(missing_ok=True)

        agent.emit_event_to(agent.EVENTS_PATH, actor="cli", type="spec.activated",
                            payload={"spec_path": "35_specs/x.md"})
        # NO spec.github_repo_set
        agent.emit_event_to(agent.EVENTS_PATH, actor="delivery-agent", type="task.proposed",
                            payload={
                                "proposal_id": "prop_test2",
                                "key": "key_test2",
                                "spec_path": "35_specs/x.md",
                                "section_id": "Tarefas",
                                "item_text": "unresolved test",
                                "run_id": "run_test",
                            })
        agent.rebuild_state()

        ns = type("NS", (), {})()
        ns.proposal_id = "prop_test2"
        ns.repo = None

        rc = cli_mod.cmd_accept(ns)
        self.assertEqual(rc, 0, "accept must exit 0 even when repo unresolved")

        events = list(agent.iter_events(agent.EVENTS_PATH))
        types = [e["type"] for e in events]
        self.assertIn("task.created", types)
        self.assertIn("task.github_link_failed", types)

        # Verify the failed event has error_kind=repo_unresolved and repo=null
        failed = next(e for e in events if e["type"] == "task.github_link_failed")
        self.assertEqual(failed["payload"]["error_kind"], "repo_unresolved")
        self.assertIsNone(failed["payload"]["repo"])


class TestCLIGithubLinkPreconditions(unittest.TestCase):
    """cmd_github_link precondition validation:
    - task_id must exist in state.proposals
    - proposal must be in state 'accepted'
    - github_link.state must be null or 'failed' (refuse 'linked' terminal)
    """

    def setUp(self):
        """Backup original state files."""
        import shutil
        self.tmpdir = Path(tempfile.mkdtemp())
        self.backup_events = self.tmpdir / "backup_events.jsonl"
        self.backup_state = self.tmpdir / "backup_state.json"

        # Backup originals
        if agent.EVENTS_PATH.exists():
            shutil.copy(agent.EVENTS_PATH, self.backup_events)
        if agent.STATE_PATH.exists():
            shutil.copy(agent.STATE_PATH, self.backup_state)

    def tearDown(self):
        """Restore original state files."""
        import shutil
        try:
            if self.backup_events.exists():
                shutil.copy(self.backup_events, agent.EVENTS_PATH)
            elif agent.EVENTS_PATH.exists():
                agent.EVENTS_PATH.unlink()

            if self.backup_state.exists():
                shutil.copy(self.backup_state, agent.STATE_PATH)
            elif agent.STATE_PATH.exists():
                agent.STATE_PATH.unlink()
        finally:
            shutil.rmtree(self.tmpdir)

    def test_refuse_linked_terminal(self):
        import cli as cli_mod

        # Clear and seed state with test data
        agent.EVENTS_PATH.unlink(missing_ok=True)
        agent.STATE_PATH.unlink(missing_ok=True)

        agent.emit_event_to(agent.EVENTS_PATH, actor="cli", type="spec.activated",
                            payload={"spec_path": "x.md"})
        agent.emit_event_to(agent.EVENTS_PATH, actor="delivery-agent", type="task.proposed",
                            payload={
                                "proposal_id": "prop_abc", "key": "k1",
                                "spec_path": "x.md", "section_id": "Tarefas",
                                "item_text": "test", "run_id": "run_1",
                            })
        agent.emit_event_to(agent.EVENTS_PATH, actor="cli", type="task.created",
                            payload={"proposal_id": "prop_abc", "key": "k1", "task_id": "task_xyz"})
        agent.emit_event_to(agent.EVENTS_PATH, actor="cli", type="task.github_linked",
                            payload={
                                "task_id": "task_xyz", "key": "k1",
                                "repo": "a/b", "issue_number": 1,
                                "issue_url": "https://github.com/a/b/issues/1",
                            })
        agent.rebuild_state()

        ns = type("NS", (), {})()
        ns.task_id = "task_xyz"
        ns.repo = None

        rc = cli_mod.cmd_github_link(ns)
        self.assertEqual(rc, 2, "github-link must refuse linked terminal")

        # Zero new events since refusal
        events_after = list(agent.iter_events(agent.EVENTS_PATH))
        types_after = [e["type"] for e in events_after]
        # Should still be: spec.activated, task.proposed, task.created, task.github_linked
        self.assertEqual(len(events_after), 4)

    def test_retry_from_failed_emits_new_event(self):
        import cli as cli_mod

        # Clear and seed state with test data
        agent.EVENTS_PATH.unlink(missing_ok=True)
        agent.STATE_PATH.unlink(missing_ok=True)

        agent.emit_event_to(agent.EVENTS_PATH, actor="cli", type="spec.activated",
                            payload={"spec_path": "35_specs/x.md"})
        agent.emit_event_to(agent.EVENTS_PATH, actor="cli", type="spec.github_repo_set",
                            payload={"spec_path": "35_specs/x.md", "repo": "bernardTavares/test"})
        agent.emit_event_to(agent.EVENTS_PATH, actor="delivery-agent", type="task.proposed",
                            payload={
                                "proposal_id": "prop_abc", "key": "k1",
                                "spec_path": "35_specs/x.md", "section_id": "Tarefas",
                                "item_text": "test item", "run_id": "run_1",
                            })
        agent.emit_event_to(agent.EVENTS_PATH, actor="cli", type="task.created",
                            payload={"proposal_id": "prop_abc", "key": "k1", "task_id": "task_xyz"})
        agent.emit_event_to(agent.EVENTS_PATH, actor="cli", type="task.github_link_failed",
                            payload={
                                "task_id": "task_xyz", "key": "k1",
                                "repo": "bernardTavares/test",
                                "error_kind": "network_timeout",
                                "message": "timeout",
                            })
        agent.rebuild_state()

        def mock_run(*args, **kwargs):
            cmd = args[0]
            if "label" in cmd and "list" in cmd:
                return MagicMock(returncode=0, stdout='[{"name":"delivery"}]', stderr="")
            if "issue" in cmd and "create" in cmd:
                return MagicMock(
                    returncode=0,
                    stdout="https://github.com/bernardTavares/test/issues/5\n",
                    stderr="",
                )
            return MagicMock(returncode=1, stdout="", stderr="")

        with patch("subprocess.run", side_effect=mock_run):
            ns = type("NS", (), {})()
            ns.task_id = "task_xyz"
            ns.repo = None
            rc = cli_mod.cmd_github_link(ns)
            self.assertEqual(rc, 0)

        # Verify new task.github_linked event appears
        state = agent.read_state(agent.STATE_PATH)
        gl = state["proposals"]["prop_abc"]["github_link"]
        self.assertEqual(gl["state"], "linked")
        self.assertEqual(gl["issue_number"], 5)

    def test_task_not_found(self):
        import cli as cli_mod
        # Uses real state.json but task_id "nonexistent" shouldn't be there
        ns = type("NS", (), {})()
        ns.task_id = "task_nonexistent_12345"
        ns.repo = None
        rc = cli_mod.cmd_github_link(ns)
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
