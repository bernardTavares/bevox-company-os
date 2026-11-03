"""Tests for greenfield/generators/prd.py."""
from pathlib import Path
from unittest.mock import MagicMock, patch

from lib.knowledge_watcher.greenfield import SourceSignals, Tier
from lib.knowledge_watcher.greenfield.generators.prd import generate_prd


def _signals(**overrides) -> SourceSignals:
    base = dict(
        slug="myproj", repo_root=Path("/tmp/repo"),
        has_schema_prisma=False, schema_models=[],
        package_json={}, deps={}, main_services=[], env_vars=[],
        has_readme=False, readme_text="",
        has_claude_md=False, claude_md_text="",
        git_tags=[], services_count=0,
        has_auth_middleware=False, has_org_id_pattern=False,
    )
    base.update(overrides)
    return SourceSignals(**base)


def test_no_source_skips_generation(tmp_path):
    sig = _signals()
    result = generate_prd(sig, state_path=tmp_path / "s.json")
    assert result.tier == Tier.SEMI_AUTO
    assert result.doc_type == "prd"
    assert result.cost_usd == 0.0
    assert result.content == ""
    assert any("no README" in w for w in result.warnings)


def test_full_source_generates_prd_with_frontmatter(tmp_path):
    sig = _signals(
        has_readme=True,
        readme_text="# myproj\n\nServiço de SaaS de marketing.",
        has_claude_md=True,
        claude_md_text="# CLAUDE\n\nÁrea: marketing automation.",
        deps={"express": "^4", "typescript": "^5"},
        schema_models=["User", "Campaign"],
        services_count=3,
    )
    fake_resp = MagicMock()
    fake_resp.content = [MagicMock(text="# myproj — PRD\n\n## Visão de uma linha\nSaaS de marketing.\n\n## Problema\nFalta automação.\n\n## Objetivos\n- objetivo 1\n- objetivo 2")]
    fake_resp.usage.input_tokens = 800
    fake_resp.usage.output_tokens = 200

    with patch("lib.knowledge_watcher.greenfield.generators.prd._call_haiku",
               return_value=fake_resp):
        result = generate_prd(sig, state_path=tmp_path / "s.json", budget_usd=5.0)

    assert result.tier == Tier.SEMI_AUTO
    assert result.cost_usd > 0  # registered cost
    body = result.content
    assert "---" in body
    assert "title: PRD — myproj" in body
    assert "status: Draft (greenfield bootstrap)" in body
    assert "## Visão de uma linha" in body
    assert "## Objetivos" in body
    assert "Review humano obrigatório" in body


def test_budget_exceeded_skips_generation(tmp_path):
    state = tmp_path / "s.json"
    import datetime as _dt
    now_month = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m")
    state.write_text(
        '{"version": 2, "repos": {}, "global": {},'
        f' "llm_usage_month": {{"month": "{now_month}", "spent_usd": 5.20}}}}'
    )
    sig = _signals(has_readme=True, readme_text="x", has_claude_md=False)
    result = generate_prd(sig, state_path=state, budget_usd=5.0)
    assert result.cost_usd == 0.0
    assert any("budget" in w.lower() for w in result.warnings)


def test_llm_call_failure_returns_warning(tmp_path):
    sig = _signals(has_readme=True, readme_text="x")
    with patch("lib.knowledge_watcher.greenfield.generators.prd._call_haiku",
               side_effect=RuntimeError("network down: dns lookup failed")):
        result = generate_prd(sig, state_path=tmp_path / "s.json")
    assert result.cost_usd == 0.0
    assert any("RuntimeError" in w for w in result.warnings)
    assert any("dns lookup failed" in w for w in result.warnings), \
        "Exception message must propagate, not just the type"


def test_strips_code_fence_in_response(tmp_path):
    sig = _signals(has_readme=True, readme_text="x")
    fake_resp = MagicMock()
    fake_resp.content = [MagicMock(text="```markdown\n# myproj — PRD\n\nbody\n```")]
    fake_resp.usage.input_tokens = 100
    fake_resp.usage.output_tokens = 20
    with patch("lib.knowledge_watcher.greenfield.generators.prd._call_haiku",
               return_value=fake_resp):
        result = generate_prd(sig, state_path=tmp_path / "s.json")
    assert "```" not in result.content
    assert "# myproj — PRD" in result.content
