"""Tests for greenfield/generators/architecture.py."""
from pathlib import Path

from lib.knowledge_watcher.greenfield import SourceSignals, Tier
from lib.knowledge_watcher.greenfield.generators.architecture import (
    generate_architecture,
)


def _signals(**overrides) -> SourceSignals:
    base = dict(
        slug="myproj",
        repo_root=Path("/tmp/repo"),
        has_schema_prisma=False,
        schema_models=[],
        package_json={},
        deps={},
        main_services=[],
        env_vars=[],
        has_readme=False,
        readme_text="",
        has_claude_md=False,
        claude_md_text="",
        git_tags=[],
        services_count=0,
        has_auth_middleware=False,
        has_org_id_pattern=False,
    )
    base.update(overrides)
    return SourceSignals(**base)


def test_full_signals_renders_complete_overview():
    sig = _signals(
        has_schema_prisma=True,
        schema_models=["User", "Workspace"],
        deps={"express": "^4", "pg-boss": "^9", "typescript": "^5"},
        main_services=["apps/api/src/services/auth.service.ts"],
        env_vars=["DATABASE_URL", "API_KEY"],
        has_auth_middleware=True,
    )
    result = generate_architecture(sig)
    assert result.tier == Tier.MECANICO
    assert result.doc_type == "architecture"
    assert result.relative_path == "20_architecture/myproj/system-overview.md"
    assert result.cost_usd == 0.0

    body = result.content
    assert "# System overview — myproj" in body
    assert "Status:** Aceita" in body
    assert "TypeScript / Node.js" in body
    assert "Express" in body
    assert "Postgres via Prisma" in body
    assert "pg-boss" in body
    assert "Custom middleware" in body
    assert "- `User`" in body
    assert "- `Workspace`" in body
    assert "| `express` | `^4` |" in body
    assert "auth.service.ts" in body
    assert "- `DATABASE_URL`" in body


def test_empty_signals_renders_skeleton_with_fallback_lines():
    sig = _signals()
    result = generate_architecture(sig)
    body = result.content
    assert "Schema not detected" in body
    assert "Services not detected" in body
    assert "No env vars detected" in body
    # No framework line if no framework deps
    assert "Framework:" not in body


def test_no_schema_omits_database_line():
    sig = _signals(deps={"express": "^4"})
    result = generate_architecture(sig)
    assert "Postgres via Prisma" not in result.content


def test_bullmq_detected_as_queue():
    sig = _signals(deps={"bullmq": "^5"})
    result = generate_architecture(sig)
    assert "BullMQ" in result.content


def test_no_auth_middleware_omits_auth_line():
    sig = _signals(deps={"express": "^4"})
    result = generate_architecture(sig)
    assert "Custom middleware" not in result.content


def test_python_services_without_deps_classified_as_python():
    sig = _signals(main_services=["lib/foo/bar.py"])
    result = generate_architecture(sig)
    assert "Python" in result.content
