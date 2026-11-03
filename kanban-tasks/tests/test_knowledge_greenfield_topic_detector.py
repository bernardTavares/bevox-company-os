"""Tests for greenfield/topic_detector.py."""
from pathlib import Path

from lib.knowledge_watcher.greenfield import ADRTopic, SourceSignals
from lib.knowledge_watcher.greenfield.topic_detector import detect_adr_topics


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


def test_empty_signals_returns_empty_list():
    sig = _signals()
    assert detect_adr_topics(sig) == []


def test_schema_prisma_alone_detects_stack():
    sig = _signals(has_schema_prisma=True, schema_models=["User"])
    topics = detect_adr_topics(sig)
    assert any(t.slug == "stack-decisions" for t in topics)


def test_stack_absorbs_database_and_framework():
    """When stack-decisions fires, database-choice and framework-choice should not."""
    sig = _signals(
        has_schema_prisma=True,
        schema_models=["A", "B", "C", "D", "E"],
        deps={"express": "^4", "pg": "^8"},
    )
    topics = detect_adr_topics(sig)
    slugs = [t.slug for t in topics]
    assert "stack-decisions" in slugs
    assert "database-choice" not in slugs
    assert "framework-choice" not in slugs


def test_full_signals_detects_multiple_topics():
    sig = _signals(
        has_schema_prisma=True,
        schema_models=["User", "Workspace"],
        deps={"pg-boss": "^9", "redis": "^4", "stripe": "^15"},
        has_auth_middleware=True,
        has_org_id_pattern=True,
    )
    topics = detect_adr_topics(sig)
    slugs = {t.slug for t in topics}
    assert "stack-decisions" in slugs
    assert "job-queue" in slugs
    assert "auth-model" in slugs
    assert "tenancy-model" in slugs
    assert "external-providers" in slugs
    assert "cache-strategy" in slugs


def test_max_topics_cap_enforced():
    sig = _signals(
        has_schema_prisma=True,
        schema_models=["A"] * 10,
        deps={
            "pg-boss": "^9", "redis": "^4", "stripe": "^15",
            "express": "^4", "ioredis": "^5", "@nestjs/core": "^9",
        },
        has_auth_middleware=True,
        has_org_id_pattern=True,
    )
    topics = detect_adr_topics(sig, max_topics=3)
    assert len(topics) == 3
    # top 3 by confidence
    assert all(t.confidence >= 0.75 for t in topics)


def test_topics_sorted_by_confidence_desc():
    sig = _signals(
        has_schema_prisma=True,
        schema_models=["A"] * 5,
        has_auth_middleware=True,
        deps={"redis": "^4"},
    )
    topics = detect_adr_topics(sig)
    confidences = [t.confidence for t in topics]
    assert confidences == sorted(confidences, reverse=True)


def test_database_choice_fires_only_without_stack():
    """If has only `pg` in deps but no schema/models → database-choice fires."""
    sig = _signals(deps={"pg": "^8"})
    topics = detect_adr_topics(sig)
    slugs = [t.slug for t in topics]
    # No schema, no models, so stack does not fire
    assert "database-choice" in slugs
    assert "stack-decisions" not in slugs


def test_meta_provider_substring_detected():
    sig = _signals(deps={"@meta/whatsapp-cloud": "^1"})
    topics = detect_adr_topics(sig)
    assert any(t.slug == "external-providers" for t in topics)


def test_drizzle_alone_triggers_stack_decisions():
    """W4.5: ORM detection (não só Prisma) absorbs stack."""
    sig = _signals(has_drizzle=True, has_orm=True, deps={"drizzle-orm": "^0.45"})
    topics = detect_adr_topics(sig)
    slugs = [t.slug for t in topics]
    assert "stack-decisions" in slugs
    # database-choice should be absorbed
    assert "database-choice" not in slugs
    # rationale should mention Drizzle
    stack = next(t for t in topics if t.slug == "stack-decisions")
    assert "Drizzle" in stack.rationale


def test_typeorm_triggers_stack_decisions():
    sig = _signals(has_typeorm=True, has_orm=True, deps={"typeorm": "^0.3"})
    topics = detect_adr_topics(sig)
    stack = next((t for t in topics if t.slug == "stack-decisions"), None)
    assert stack is not None
    assert "TypeORM" in stack.rationale


def test_mongoose_triggers_stack_decisions():
    sig = _signals(has_mongoose=True, has_orm=True, deps={"mongoose": "^8"})
    topics = detect_adr_topics(sig)
    assert any(t.slug == "stack-decisions" for t in topics)


def test_no_orm_signals_no_stack_unless_models_or_pg():
    """If has_orm=False and no schema, stack should not fire from ORM path."""
    sig = _signals(deps={"express": "^4"})
    topics = detect_adr_topics(sig)
    assert not any(t.slug == "stack-decisions" for t in topics)
