"""Tests for greenfield/generators/roadmap.py."""
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from lib.knowledge_watcher.greenfield import SourceSignals, Tier
from lib.knowledge_watcher.greenfield.generators.roadmap import generate_roadmap


def _signals(repo_root, **overrides) -> SourceSignals:
    base = dict(
        slug="myproj", repo_root=repo_root,
        has_schema_prisma=False, schema_models=[],
        package_json={}, deps={}, main_services=[], env_vars=[],
        has_readme=False, readme_text="",
        has_claude_md=False, claude_md_text="",
        git_tags=[], services_count=0,
        has_auth_middleware=False, has_org_id_pattern=False,
    )
    base.update(overrides)
    return SourceSignals(**base)


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True)
    for msg in ["feat: A", "fix: B", "refactor: C"]:
        (repo / f"f{len(list(repo.glob('*.txt')))}.txt").write_text(msg)
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", msg], cwd=repo, check=True, capture_output=True)
    return repo


def test_no_git_history_skips_generation(tmp_path):
    repo = tmp_path / "notarepo"
    repo.mkdir()
    sig = _signals(repo)
    result = generate_roadmap(sig, state_path=tmp_path / "s.json")
    assert result.cost_usd == 0.0
    assert result.content == ""
    assert any("no git history" in w for w in result.warnings)


def test_budget_exceeded_skips_generation(tmp_path):
    repo = _make_repo(tmp_path)
    state = tmp_path / "s.json"
    import datetime as _dt
    now_month = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m")
    state.write_text(
        '{"version": 2, "repos": {}, "global": {},'
        f' "llm_usage_month": {{"month": "{now_month}", "spent_usd": 5.20}}}}'
    )
    sig = _signals(repo)
    result = generate_roadmap(sig, state_path=state, budget_usd=5.0)
    assert result.cost_usd == 0.0
    assert any("budget" in w.lower() for w in result.warnings)


def test_full_history_generates_roadmap(tmp_path):
    repo = _make_repo(tmp_path)
    sig = _signals(repo, deps={"express": "^4", "typescript": "^5"}, services_count=3)
    fake_resp = MagicMock()
    fake_resp.content = [MagicMock(text="# myproj — Roadmap\n\n## Visão estratégica\nMarketing automation\n\n## Q1\n- M1\n- M2")]
    fake_resp.usage.input_tokens = 700
    fake_resp.usage.output_tokens = 150

    with patch("lib.knowledge_watcher.greenfield.generators.roadmap._call_haiku",
               return_value=fake_resp):
        result = generate_roadmap(sig, state_path=tmp_path / "s.json", budget_usd=5.0)

    assert result.tier == Tier.SEMI_AUTO
    assert result.doc_type == "roadmap"
    assert "40_roadmap/myproj/" in result.relative_path
    assert result.cost_usd > 0
    body = result.content
    assert "title: Roadmap — myproj" in body
    assert "status: Draft" in body
    assert "## Visão estratégica" in body
    assert "Review humano obrigatório" in body


def test_llm_failure_returns_warning(tmp_path):
    repo = _make_repo(tmp_path)
    sig = _signals(repo)
    with patch("lib.knowledge_watcher.greenfield.generators.roadmap._call_haiku",
               side_effect=RuntimeError("network down: dns lookup failed")):
        result = generate_roadmap(sig, state_path=tmp_path / "s.json")
    assert result.cost_usd == 0.0
    assert any("RuntimeError" in w for w in result.warnings)
    assert any("dns lookup failed" in w for w in result.warnings), \
        "Exception message must propagate, not just the type"


def test_strips_code_fence(tmp_path):
    repo = _make_repo(tmp_path)
    sig = _signals(repo)
    fake_resp = MagicMock()
    fake_resp.content = [MagicMock(text="```markdown\n# myproj — Roadmap\n\nbody\n```")]
    fake_resp.usage.input_tokens = 100
    fake_resp.usage.output_tokens = 20
    with patch("lib.knowledge_watcher.greenfield.generators.roadmap._call_haiku",
               return_value=fake_resp):
        result = generate_roadmap(sig, state_path=tmp_path / "s.json")
    assert "```" not in result.content
    assert "# myproj — Roadmap" in result.content
