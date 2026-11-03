"""E6/F4 wave 1 — Release notes assistidas tests.

Covers:
- Pure helpers: _group_commits, _parse_issue_refs, _render_markdown
- _resolve_repo (lookup hardcoded SUPPORTED_REPOS)
- _resolve_range (since/to ref resolution + last-tag fallback)
- _read_git_log (with --no-merges per spec §2.11)
- _publish_draft (gh subprocess wrapper)
- cmd_release_notes E2E in tmpdir

Spec: bevox-knowledge/35_specs/2026-04-18-e6-f4-release-notes-wave-1.md
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cli


class TestGroupCommits(unittest.TestCase):
    """_group_commits classifies commits by conventional prefix.

    Input: list of {sha, subject, body} dicts.
    Output: dict with 7 keys (feat/fix/docs/refactor/chore/test/other),
    each a list of the matching commit dicts in input order.
    """

    def test_empty_list_returns_seven_empty_groups(self):
        result = cli._group_commits([])
        self.assertEqual(
            set(result.keys()),
            {"feat", "fix", "docs", "refactor", "chore", "test", "other"},
        )
        for group in result.values():
            self.assertEqual(group, [])

    def test_single_feat_goes_to_feat_group(self):
        commits = [{"sha": "abc1234", "subject": "feat: add new thing", "body": ""}]
        result = cli._group_commits(commits)
        self.assertEqual(len(result["feat"]), 1)
        self.assertEqual(result["feat"][0]["sha"], "abc1234")
        for k in ("fix", "docs", "refactor", "chore", "test", "other"):
            self.assertEqual(result[k], [])

    def test_scoped_prefix_is_recognized(self):
        commits = [
            {"sha": "a1", "subject": "feat(parser): scoped feature", "body": ""},
            {"sha": "a2", "subject": "fix(api): scoped fix", "body": ""},
        ]
        result = cli._group_commits(commits)
        self.assertEqual(len(result["feat"]), 1)
        self.assertEqual(len(result["fix"]), 1)

    def test_all_seven_prefixes_classify_correctly(self):
        commits = [
            {"sha": "1", "subject": "feat: x", "body": ""},
            {"sha": "2", "subject": "fix: x", "body": ""},
            {"sha": "3", "subject": "docs: x", "body": ""},
            {"sha": "4", "subject": "refactor: x", "body": ""},
            {"sha": "5", "subject": "chore: x", "body": ""},
            {"sha": "6", "subject": "test: x", "body": ""},
            {"sha": "7", "subject": "random subject without prefix", "body": ""},
        ]
        result = cli._group_commits(commits)
        self.assertEqual(len(result["feat"]), 1)
        self.assertEqual(len(result["fix"]), 1)
        self.assertEqual(len(result["docs"]), 1)
        self.assertEqual(len(result["refactor"]), 1)
        self.assertEqual(len(result["chore"]), 1)
        self.assertEqual(len(result["test"]), 1)
        self.assertEqual(len(result["other"]), 1)
        self.assertEqual(result["other"][0]["sha"], "7")

    def test_unmatched_prefix_falls_to_other(self):
        commits = [
            {"sha": "x1", "subject": "wip: in progress", "body": ""},
            {"sha": "x2", "subject": "Update README", "body": ""},
        ]
        result = cli._group_commits(commits)
        self.assertEqual(len(result["other"]), 2)

    def test_input_order_preserved_within_group(self):
        commits = [
            {"sha": "first", "subject": "feat: a", "body": ""},
            {"sha": "second", "subject": "feat: b", "body": ""},
            {"sha": "third", "subject": "feat: c", "body": ""},
        ]
        result = cli._group_commits(commits)
        self.assertEqual([c["sha"] for c in result["feat"]], ["first", "second", "third"])


class TestParseIssueRefs(unittest.TestCase):
    """_parse_issue_refs extracts unique #N references from commit bodies+subjects.

    Input: list of commit dicts.
    Output: sorted ascending list of int issue numbers (deduplicated).
    """

    def test_empty_list_returns_empty(self):
        self.assertEqual(cli._parse_issue_refs([]), [])

    def test_no_references_returns_empty(self):
        commits = [{"sha": "1", "subject": "feat: x", "body": "no refs here"}]
        self.assertEqual(cli._parse_issue_refs(commits), [])

    def test_single_ref_in_subject(self):
        commits = [{"sha": "1", "subject": "fix: closes #42", "body": ""}]
        self.assertEqual(cli._parse_issue_refs(commits), [42])

    def test_single_ref_in_body(self):
        commits = [{"sha": "1", "subject": "feat: x", "body": "see #7 for context"}]
        self.assertEqual(cli._parse_issue_refs(commits), [7])

    def test_multiple_refs_deduped_and_sorted(self):
        commits = [
            {"sha": "1", "subject": "feat: #5", "body": "also #2"},
            {"sha": "2", "subject": "fix: #5", "body": "duplicate; new #100"},
        ]
        self.assertEqual(cli._parse_issue_refs(commits), [2, 5, 100])

    def test_does_not_match_hash_inside_word(self):
        # `abc#123` should NOT be picked up — only standalone #N references.
        commits = [{"sha": "1", "subject": "feat: x", "body": "see abc#123 issue"}]
        self.assertEqual(cli._parse_issue_refs(commits), [])

    def test_does_not_match_sha_like_hashes(self):
        # `#abc123` is not an issue ref (alpha not allowed).
        commits = [{"sha": "1", "subject": "feat: #abc", "body": "ref #def123"}]
        self.assertEqual(cli._parse_issue_refs(commits), [])


class TestRenderMarkdown(unittest.TestCase):
    """_render_markdown builds the spec §5.5 markdown shape.

    Input:
        repo_short: str
        since_sha_short, to_sha_short: str
        commit_count: int
        generated_at: str (formatted)
        groups: dict from _group_commits
        issue_refs: list[int]

    Output: str (the full markdown).
    """

    def _basic_inputs(self, **overrides):
        defaults = {
            "repo_short": "knowledge-sync",
            "since_sha_short": "83bed3c",
            "to_sha_short": "0af58c2",
            "commit_count": 1,
            "generated_at": "2026-04-18 17:42:11 -03",
            "groups": {k: [] for k in cli._RN_GROUPS},
            "issue_refs": [],
        }
        defaults.update(overrides)
        return defaults

    def test_header_includes_repo_range_and_generated(self):
        md = cli._render_markdown(**self._basic_inputs())
        self.assertIn("# Release notes — knowledge-sync", md)
        self.assertIn("83bed3c..0af58c2", md)
        self.assertIn("(1 commit, merges excluidos)", md)
        self.assertIn("2026-04-18 17:42:11 -03", md)

    def test_commit_count_plural_form(self):
        md = cli._render_markdown(**self._basic_inputs(commit_count=5))
        self.assertIn("(5 commits, merges excluidos)", md)

    def test_empty_groups_omit_all_sections(self):
        md = cli._render_markdown(**self._basic_inputs())
        for section in ("## Features", "## Bug Fixes", "## Documentation",
                        "## Refactoring", "## Chores", "## Tests", "## Other",
                        "## Referenced issues"):
            self.assertNotIn(section, md)

    def test_feat_group_renders_features_section(self):
        groups = {k: [] for k in cli._RN_GROUPS}
        groups["feat"] = [{"sha": "abc1234", "subject": "feat: add thing", "body": ""}]
        md = cli._render_markdown(**self._basic_inputs(groups=groups, commit_count=1))
        self.assertIn("## Features", md)
        self.assertIn("- add thing (abc1234)", md)

    def test_scoped_prefix_stripped_from_subject(self):
        groups = {k: [] for k in cli._RN_GROUPS}
        groups["fix"] = [{"sha": "def5678", "subject": "fix(parser): handle edge", "body": ""}]
        md = cli._render_markdown(**self._basic_inputs(groups=groups, commit_count=1))
        self.assertIn("- handle edge (def5678)", md)
        self.assertNotIn("fix(parser)", md)

    def test_other_group_keeps_full_subject(self):
        groups = {k: [] for k in cli._RN_GROUPS}
        groups["other"] = [{"sha": "999aaaa", "subject": "Update README", "body": ""}]
        md = cli._render_markdown(**self._basic_inputs(groups=groups, commit_count=1))
        self.assertIn("## Other", md)
        self.assertIn("- Update README (999aaaa)", md)

    def test_section_order_is_spec_canonical(self):
        # Per spec §5.5: Features, Bug Fixes, Documentation, Refactoring,
        # Chores, Tests, Other, Referenced issues.
        groups = {k: [{"sha": "x", "subject": f"{k}: x", "body": ""}] for k in cli._RN_GROUPS}
        md = cli._render_markdown(**self._basic_inputs(
            groups=groups, commit_count=7, issue_refs=[1, 2]))
        positions = [
            md.index("## Features"),
            md.index("## Bug Fixes"),
            md.index("## Documentation"),
            md.index("## Refactoring"),
            md.index("## Chores"),
            md.index("## Tests"),
            md.index("## Other"),
            md.index("## Referenced issues"),
        ]
        self.assertEqual(positions, sorted(positions))

    def test_referenced_issues_section_lists_refs(self):
        md = cli._render_markdown(**self._basic_inputs(issue_refs=[7, 42, 100]))
        self.assertIn("## Referenced issues", md)
        self.assertIn("- #7", md)
        self.assertIn("- #42", md)
        self.assertIn("- #100", md)


class TestResolveRepo(unittest.TestCase):
    """_resolve_repo looks up SUPPORTED_REPOS by short or full name."""

    def test_short_name_resolves(self):
        info = cli._resolve_repo("knowledge-sync")
        self.assertEqual(info["github"], "bernardTavares/knowledge-sync")
        self.assertEqual(info["clone"], f"{Path.home()}/code/knowledge-sync")

    def test_full_name_resolves(self):
        info = cli._resolve_repo("bernardTavares/knowledge-sync")
        self.assertEqual(info["github"], "bernardTavares/knowledge-sync")

    def test_bevox_knowledge_short_resolves(self):
        info = cli._resolve_repo("bevox-knowledge")
        self.assertEqual(info["clone"], f"{Path.home()}/bevox-knowledge")

    def test_unknown_repo_raises(self):
        with self.assertRaises(ValueError) as ctx:
            cli._resolve_repo("nonexistent-repo")
        self.assertIn("unknown repo", str(ctx.exception).lower())
        self.assertIn("supported", str(ctx.exception).lower())


class _GitRepoFixture:
    """Builds a real tiny git repo in a tmpdir for E2E-ish tests."""

    def __init__(self):
        self.tmp = tempfile.mkdtemp(prefix="rn-test-")
        self.path = Path(self.tmp)
        self._git("init", "-q", "-b", "main")
        self._git("config", "user.email", "test@test.local")
        self._git("config", "user.name", "test")

    def _git(self, *args):
        result = subprocess.run(
            ["git", "-C", str(self.path), *args],
            check=True, capture_output=True, text=True,
        )
        return result.stdout.strip()

    def commit(self, subject, body=""):
        marker = self.path / "marker.txt"
        marker.write_text(marker.read_text() + "x" if marker.exists() else "x")
        self._git("add", "marker.txt")
        msg = subject if not body else f"{subject}\n\n{body}"
        self._git("commit", "-q", "-m", msg)
        return self._git("rev-parse", "HEAD")

    def tag(self, name, ref="HEAD"):
        self._git("tag", "-a", name, ref, "-m", f"tag {name}")

    def merge_commit(self, branch_to_merge):
        self._git("merge", "--no-ff", "-m", f"Merge {branch_to_merge}", branch_to_merge)
        return self._git("rev-parse", "HEAD")

    def cleanup(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestResolveRange(unittest.TestCase):
    """_resolve_range determines (since_ref, to_ref, since_sha, to_sha).

    Inputs:
        clone_path: str
        since: Optional[str]  (None → use last tag)
        to: Optional[str]     (None → "HEAD")
    Returns: tuple (since_ref_label, to_ref_label, since_sha, to_sha).
    Raises:
        FileNotFoundError if clone path missing.
        ValueError("no tags found...") if since=None and no tags exist.
        ValueError("ref not found: X") if since/to don't exist.
    """

    def setUp(self):
        self.repo = _GitRepoFixture()
        self.first_sha = self.repo.commit("init")
        self.repo.commit("feat: x")
        self.repo.commit("fix: y")

    def tearDown(self):
        self.repo.cleanup()

    def test_explicit_since_and_to(self):
        head = self.repo._git("rev-parse", "HEAD")
        result = cli._resolve_range(str(self.repo.path), self.first_sha, "HEAD")
        self.assertEqual(result[0], self.first_sha)
        self.assertEqual(result[1], "HEAD")
        self.assertEqual(result[2], self.first_sha)
        self.assertEqual(result[3], head)

    def test_default_to_is_head(self):
        head = self.repo._git("rev-parse", "HEAD")
        _, to_ref, _, to_sha = cli._resolve_range(str(self.repo.path), self.first_sha, None)
        self.assertEqual(to_ref, "HEAD")
        self.assertEqual(to_sha, head)

    def test_since_none_uses_last_tag(self):
        self.repo.tag("v0.1.0", self.first_sha)
        v0_sha = self.first_sha
        since_ref, to_ref, since_sha, _ = cli._resolve_range(str(self.repo.path), None, None)
        self.assertEqual(since_ref, "v0.1.0")
        self.assertEqual(to_ref, "HEAD")
        self.assertEqual(since_sha, v0_sha)

    def test_since_none_no_tags_raises(self):
        with self.assertRaises(ValueError) as ctx:
            cli._resolve_range(str(self.repo.path), None, None)
        self.assertIn("no tags", str(ctx.exception).lower())
        self.assertIn("--since", str(ctx.exception))

    def test_invalid_ref_raises(self):
        with self.assertRaises(ValueError) as ctx:
            cli._resolve_range(str(self.repo.path), "nope-ref", "HEAD")
        self.assertIn("not found", str(ctx.exception).lower())
        self.assertIn("nope-ref", str(ctx.exception))

    def test_missing_clone_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            cli._resolve_range("/nonexistent/path", "HEAD", None)


class TestReadGitLog(unittest.TestCase):
    """_read_git_log reads commits in (since..to] range, EXCLUDING merges
    per spec §2.11.

    Returns list of {sha, subject, body} dicts in git log default order
    (newest first).
    """

    def setUp(self):
        self.repo = _GitRepoFixture()
        self.base_sha = self.repo.commit("init")

    def tearDown(self):
        self.repo.cleanup()

    def test_simple_range(self):
        c1 = self.repo.commit("feat: a")
        c2 = self.repo.commit("fix: b")
        commits = cli._read_git_log(str(self.repo.path), self.base_sha, "HEAD")
        self.assertEqual(len(commits), 2)
        # newest first
        self.assertEqual(commits[0]["sha"], c2)
        self.assertEqual(commits[0]["subject"], "fix: b")
        self.assertEqual(commits[1]["sha"], c1)

    def test_empty_range_returns_empty_list(self):
        commits = cli._read_git_log(str(self.repo.path), "HEAD", "HEAD")
        self.assertEqual(commits, [])

    def test_merge_commits_excluded(self):
        # Build a branch + merge to create a merge commit
        self.repo._git("checkout", "-q", "-b", "feature")
        feat_sha = self.repo.commit("feat: feature work")
        self.repo._git("checkout", "-q", "main")
        # Make main diverge so merge is non-FF
        main_sha = self.repo.commit("fix: main work")
        merge_sha = self.repo.merge_commit("feature")

        commits = cli._read_git_log(str(self.repo.path), self.base_sha, "HEAD")
        shas = [c["sha"] for c in commits]
        self.assertIn(feat_sha, shas)
        self.assertIn(main_sha, shas)
        self.assertNotIn(merge_sha, shas, "merge commit must be excluded")

    def test_body_captured(self):
        self.repo.commit("feat: with body", body="Closes #42\nCo-Authored-By: x")
        commits = cli._read_git_log(str(self.repo.path), self.base_sha, "HEAD")
        self.assertEqual(len(commits), 1)
        self.assertIn("#42", commits[0]["body"])

    def test_invalid_range_raises_runtime(self):
        with self.assertRaises(RuntimeError) as ctx:
            cli._read_git_log(str(self.repo.path), "bogus-ref", "HEAD")
        self.assertIn("git log failed", str(ctx.exception).lower())


import agent  # noqa: E402  imported here so cli loads first


class TestActorMatrixReleaseNotes(unittest.TestCase):
    """Spec §5.2: cli must be allowed to emit both new event types."""

    def test_cli_can_emit_release_notes_drafted(self):
        agent.validate_actor("cli", "release_notes.drafted")

    def test_cli_can_emit_release_notes_draft_publish_failed(self):
        agent.validate_actor("cli", "release_notes.draft_publish_failed")

    def test_delivery_agent_cannot_emit_release_notes_drafted(self):
        with self.assertRaises(agent.ActorError):
            agent.validate_actor("delivery-agent", "release_notes.drafted")


class TestPublishDraft(unittest.TestCase):
    """_publish_draft pre-checks + creates GH Release draft via gh CLI.

    Returns dict:
        {"ok": True, "url": "https://..."}                    on success
        {"ok": False, "error_kind": "tag_exists",  "message": "..."}
        {"ok": False, "error_kind": "network_timeout", ...}
        etc.

    Mock target: subprocess.run inside cli module.
    """

    def _mock_run(self, behavior):
        """behavior: list of MagicMock or callable; one per subprocess.run call."""
        return patch("cli.subprocess.run", side_effect=behavior)

    def test_success_creates_draft_and_returns_url(self):
        # Pre-check: gh release view → not found (rc != 0, stderr "release not found")
        view = MagicMock(returncode=1, stdout="",
                         stderr="release not found\n")
        # Create: gh release create → success, returns URL
        url = "https://github.com/bernardTavares/knowledge-sync/releases/tag/v0.1.0"
        create = MagicMock(returncode=0, stdout=url + "\n", stderr="")
        with self._mock_run([view, create]):
            result = cli._publish_draft(
                "bernardTavares/knowledge-sync", "v0.1.0",
                "Release notes — x", "# body\n",
            )
        self.assertTrue(result["ok"])
        self.assertEqual(result["url"], url)

    def test_tag_exists_pre_check_returns_tag_exists(self):
        # Pre-check: gh release view → success (tag exists)
        view = MagicMock(returncode=0,
                         stdout='{"tagName":"v0.1.0"}', stderr="")
        with self._mock_run([view]):
            result = cli._publish_draft(
                "bernardTavares/knowledge-sync", "v0.1.0",
                "Release notes — x", "# body\n",
            )
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_kind"], "tag_exists")
        self.assertIn("v0.1.0", result["message"])

    def test_create_fail_propagates_error_kind(self):
        view = MagicMock(returncode=1, stdout="",
                         stderr="release not found")
        # Create fails with auth error
        create = MagicMock(returncode=1, stdout="",
                           stderr="HTTP 401: Bad credentials")
        with self._mock_run([view, create]):
            result = cli._publish_draft(
                "bernardTavares/knowledge-sync", "v0.1.0",
                "Release notes — x", "# body\n",
            )
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_kind"], "gh_auth")

    def test_url_parse_fail_returns_unknown(self):
        view = MagicMock(returncode=1, stdout="", stderr="release not found")
        create = MagicMock(returncode=0, stdout="this is not a url\n", stderr="")
        with self._mock_run([view, create]):
            result = cli._publish_draft(
                "bernardTavares/knowledge-sync", "v0.1.0",
                "Release notes — x", "# body\n",
            )
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_kind"], "unknown")

    def test_gh_not_installed(self):
        def raise_fnf(*args, **kwargs):
            raise FileNotFoundError("gh not found")
        with self._mock_run(raise_fnf):
            result = cli._publish_draft(
                "bernardTavares/knowledge-sync", "v0.1.0",
                "Release notes — x", "# body\n",
            )
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_kind"], "gh_not_installed")


import io
import json
from contextlib import redirect_stdout, redirect_stderr


def _events_to_path(events):
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
    for evt in events:
        tmp.write(json.dumps(evt) + "\n")
    tmp.close()
    return Path(tmp.name)


class TestProjectionReleaseNotes(unittest.TestCase):
    """release_notes.drafted projects to state.release_notes[repo].

    Spec §5.4: bounded to 20 entries per repo, newest first.
    draft_publish_failed does NOT project.
    """

    def test_drafted_event_projects_entry(self):
        evt = agent.make_event(
            actor="cli", type="release_notes.drafted",
            payload={
                "repo": "knowledge-sync",
                "github_repo": "bernardTavares/knowledge-sync",
                "since_ref": "v0.1.0", "to_ref": "HEAD",
                "since_sha": "abc1234", "to_sha": "def5678",
                "commit_count": 3,
                "groups": {},
                "publish": {"mode": "stdout", "tag": None, "draft_url": None},
            },
        )
        path = _events_to_path([evt])
        try:
            state = agent.project_state(path)
            self.assertIn("release_notes", state)
            self.assertIn("knowledge-sync", state["release_notes"])
            entries = state["release_notes"]["knowledge-sync"]
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["since_ref"], "v0.1.0")
            self.assertEqual(entries[0]["commit_count"], 3)
            self.assertEqual(entries[0]["publish_mode"], "stdout")
        finally:
            path.unlink()

    def test_publish_failed_does_NOT_project(self):
        evt = agent.make_event(
            actor="cli", type="release_notes.draft_publish_failed",
            payload={
                "repo": "knowledge-sync",
                "github_repo": "bernardTavares/knowledge-sync",
                "since_ref": "v0.1.0", "to_ref": "HEAD",
                "since_sha": "abc1234", "to_sha": "def5678",
                "commit_count": 3,
                "tag": "v0.2",
                "error_kind": "tag_exists",
                "message": "x",
            },
        )
        path = _events_to_path([evt])
        try:
            state = agent.project_state(path)
            self.assertEqual(state.get("release_notes", {}).get("knowledge-sync", []), [])
        finally:
            path.unlink()

    def test_bound_to_20_per_repo_newest_first(self):
        events = []
        for i in range(25):
            events.append(agent.make_event(
                actor="cli", type="release_notes.drafted",
                payload={
                    "repo": "knowledge-sync",
                    "github_repo": "bernardTavares/knowledge-sync",
                    "since_ref": f"v0.{i}", "to_ref": "HEAD",
                    "since_sha": f"sha{i:04d}", "to_sha": "head",
                    "commit_count": 1, "groups": {},
                    "publish": {"mode": "stdout", "tag": None, "draft_url": None},
                },
            ))
        path = _events_to_path(events)
        try:
            state = agent.project_state(path)
            entries = state["release_notes"]["knowledge-sync"]
            self.assertEqual(len(entries), 20)
            # Newest first: most recent event was v0.24
            self.assertEqual(entries[0]["since_ref"], "v0.24")
            self.assertEqual(entries[-1]["since_ref"], "v0.5")
        finally:
            path.unlink()

    def test_per_repo_isolation(self):
        events = [
            agent.make_event(actor="cli", type="release_notes.drafted",
                             payload={
                                 "repo": "knowledge-sync",
                                 "github_repo": "bernardTavares/knowledge-sync",
                                 "since_ref": "v0.1", "to_ref": "HEAD",
                                 "since_sha": "a", "to_sha": "b",
                                 "commit_count": 1, "groups": {},
                                 "publish": {"mode": "stdout", "tag": None, "draft_url": None},
                             }),
            agent.make_event(actor="cli", type="release_notes.drafted",
                             payload={
                                 "repo": "bevox-knowledge",
                                 "github_repo": "bernardTavares/bevox-knowledge",
                                 "since_ref": "v1.0", "to_ref": "HEAD",
                                 "since_sha": "c", "to_sha": "d",
                                 "commit_count": 2, "groups": {},
                                 "publish": {"mode": "stdout", "tag": None, "draft_url": None},
                             }),
        ]
        path = _events_to_path(events)
        try:
            state = agent.project_state(path)
            self.assertEqual(len(state["release_notes"]["knowledge-sync"]), 1)
            self.assertEqual(len(state["release_notes"]["bevox-knowledge"]), 1)
        finally:
            path.unlink()


class TestCmdReleaseNotesE2E(unittest.TestCase):
    """End-to-end test of cmd_release_notes against a real tmpdir git repo.

    Strategy: monkeypatch SUPPORTED_REPOS to point at our tmpdir; redirect
    EVENTS_PATH/STATE_PATH to tmpdir; mock subprocess.run only when
    --publish-draft is involved (gh).
    """

    def setUp(self):
        self.repo = _GitRepoFixture()
        self.base_sha = self.repo.commit("init")
        self.repo.commit("feat: add thing")
        self.repo.commit("fix: bug")

        self.tmpdir = Path(tempfile.mkdtemp(prefix="rn-e2e-"))
        self.events_path = self.tmpdir / "events.jsonl"
        self.state_path = self.tmpdir / "state.json"

        # Backup module-level paths
        self._orig_events = agent.EVENTS_PATH
        self._orig_state = agent.STATE_PATH
        self._orig_supported = dict(cli.SUPPORTED_REPOS)

        agent.EVENTS_PATH = self.events_path
        agent.STATE_PATH = self.state_path
        cli.SUPPORTED_REPOS.clear()
        cli.SUPPORTED_REPOS["test-repo"] = {
            "github": "bernardTavares/test-repo",
            "clone": str(self.repo.path),
        }

    def tearDown(self):
        self.repo.cleanup()
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        agent.EVENTS_PATH = self._orig_events
        agent.STATE_PATH = self._orig_state
        cli.SUPPORTED_REPOS.clear()
        cli.SUPPORTED_REPOS.update(self._orig_supported)

    def _read_events(self):
        if not self.events_path.exists():
            return []
        return [json.loads(line) for line in self.events_path.read_text().splitlines() if line]

    def _make_args(self, **kwargs):
        defaults = {
            "repo": "test-repo", "since": self.base_sha, "to": None,
            "publish_draft": False, "tag": None,
        }
        defaults.update(kwargs)
        return type("Args", (), defaults)()

    def test_stdout_mode_emits_drafted_event(self):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = cli.cmd_release_notes(self._make_args())
        self.assertEqual(rc, 0)
        body = out.getvalue()
        self.assertIn("# Release notes — test-repo", body)
        self.assertIn("## Features", body)
        self.assertIn("## Bug Fixes", body)

        events = self._read_events()
        drafted = [e for e in events if e["type"] == "release_notes.drafted"]
        self.assertEqual(len(drafted), 1)
        self.assertEqual(drafted[0]["payload"]["publish"]["mode"], "stdout")
        self.assertEqual(drafted[0]["payload"]["commit_count"], 2)

    def test_unknown_repo_exits_2_no_event(self):
        err = io.StringIO()
        with redirect_stderr(err):
            rc = cli.cmd_release_notes(self._make_args(repo="ghost"))
        self.assertEqual(rc, 2)
        self.assertIn("unknown repo", err.getvalue().lower())
        self.assertEqual(self._read_events(), [])

    def test_no_tag_no_since_exits_2(self):
        err = io.StringIO()
        with redirect_stderr(err):
            rc = cli.cmd_release_notes(self._make_args(since=None))
        self.assertEqual(rc, 2)
        self.assertIn("no tags", err.getvalue().lower())
        self.assertEqual(self._read_events(), [])

    def test_empty_range_emits_drafted_count_zero(self):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = cli.cmd_release_notes(self._make_args(since="HEAD"))
        self.assertEqual(rc, 0)
        events = self._read_events()
        drafted = [e for e in events if e["type"] == "release_notes.drafted"]
        self.assertEqual(len(drafted), 1)
        self.assertEqual(drafted[0]["payload"]["commit_count"], 0)

    def test_publish_draft_success_path(self):
        # Mock _publish_draft directly (avoids interfering with git subprocess
        # calls inside _resolve_range / _read_git_log).
        url = "https://github.com/bernardTavares/test-repo/releases/tag/x"
        with patch("cli._publish_draft", return_value={"ok": True, "url": url}):
            out = io.StringIO()
            with redirect_stdout(out):
                rc = cli.cmd_release_notes(self._make_args(
                    publish_draft=True, tag="x"))
        self.assertEqual(rc, 0)
        self.assertIn(url, out.getvalue())
        events = self._read_events()
        drafted = [e for e in events if e["type"] == "release_notes.drafted"]
        self.assertEqual(len(drafted), 1)
        self.assertEqual(drafted[0]["payload"]["publish"]["mode"], "draft")
        self.assertEqual(drafted[0]["payload"]["publish"]["tag"], "x")
        self.assertEqual(drafted[0]["payload"]["publish"]["draft_url"], url)

    def test_publish_draft_failure_emits_failed_not_drafted(self):
        with patch("cli._publish_draft", return_value={
            "ok": False, "error_kind": "tag_exists",
            "message": "draft already exists for tag x",
        }):
            err = io.StringIO()
            with redirect_stderr(err):
                rc = cli.cmd_release_notes(self._make_args(
                    publish_draft=True, tag="x"))
        self.assertEqual(rc, 1)
        events = self._read_events()
        types = [e["type"] for e in events]
        self.assertIn("release_notes.draft_publish_failed", types)
        self.assertNotIn("release_notes.drafted", types)


if __name__ == "__main__":
    unittest.main()
