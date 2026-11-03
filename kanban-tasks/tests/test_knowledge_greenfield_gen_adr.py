"""Tests for greenfield/generators/adr.py."""
from pathlib import Path
from unittest.mock import patch

from lib.knowledge_watcher.greenfield import (
    ADRTopic, SourceSignals, Tier,
)
from lib.knowledge_watcher.greenfield.generators.adr import generate_adrs


def _signals(**overrides) -> SourceSignals:
    base = dict(
        slug="myproj", repo_root=Path("/tmp/repo"),
        has_schema_prisma=True, schema_models=["User"],
        package_json={}, deps={"pg-boss": "^9"},
        main_services=["apps/api/src/services/auth.service.ts"],
        env_vars=["DATABASE_URL"],
        has_readme=False, readme_text="",
        has_claude_md=False, claude_md_text="",
        git_tags=[], services_count=1,
        has_auth_middleware=True, has_org_id_pattern=False,
    )
    base.update(overrides)
    return SourceSignals(**base)


def _topic(slug="auth-model", confidence=0.80) -> ADRTopic:
    return ADRTopic(
        slug=slug, title=f"Title {slug}",
        rationale="test rationale", confidence=confidence,
    )


def test_no_topics_returns_empty(tmp_path):
    sig = _signals()
    assert generate_adrs(sig, [], tmp_path / "kb") == []


def test_dry_run_returns_placeholders_no_subprocess(tmp_path):
    sig = _signals()
    topics = [_topic("auth-model"), _topic("tenancy-model")]
    with patch("lib.knowledge_watcher.greenfield.generators.adr.run_claude_p") as m_run:
        results = generate_adrs(sig, topics, tmp_path / "kb", dry_run=True)
    assert len(results) == 2
    for r in results:
        assert r.tier == Tier.JUDGMENT
        assert r.doc_type == "adr"
        assert r.cost_usd == 0.0
        assert "dry-run" in r.content
        assert "dry_run" in r.warnings
    m_run.assert_not_called()


def test_real_call_returns_processed_content(tmp_path):
    sig = _signals()
    topics = [_topic("job-queue", 0.85)]
    fake_md = """# ADR-001: Title job-queue

**Status:** Aceita
**Data:** 2026-05-09

## Contexto

Use `pg-boss` because reasons.

## Decisão

Pick pg-boss.

## Alternativas consideradas

- `bullmq` — rejected for X

## Consequências

OK.
"""
    with patch("lib.knowledge_watcher.greenfield.generators.adr.run_claude_p",
               return_value=fake_md):
        results = generate_adrs(sig, topics, tmp_path / "kb", max_workers=1)
    assert len(results) == 1
    r = results[0]
    assert r.tier == Tier.JUDGMENT
    assert r.relative_path == "30_adr/myproj/ADR-001-job-queue.md"
    assert r.cost_usd == 0.30
    # Guardrail G1 should have flipped Aceita → Proposta
    assert "Status:" in r.content
    assert "Proposta" in r.content
    assert any("G1" in w for w in r.warnings)


def test_claude_p_returns_none_records_warning(tmp_path):
    sig = _signals()
    topics = [_topic("auth-model")]
    with patch("lib.knowledge_watcher.greenfield.generators.adr.run_claude_p",
               return_value=None):
        results = generate_adrs(sig, topics, tmp_path / "kb", max_workers=1)
    assert len(results) == 1
    r = results[0]
    assert r.content == ""
    assert r.cost_usd == 0.0
    assert any("claude -p returned None" in w for w in r.warnings)


def test_adr_numbering_continues_from_existing(tmp_path):
    kb = tmp_path / "kb"
    adr_dir = kb / "30_adr" / "myproj"
    adr_dir.mkdir(parents=True)
    (adr_dir / "ADR-005-foo.md").write_text("existing")
    (adr_dir / "ADR-009-bar.md").write_text("existing")

    sig = _signals()
    topics = [_topic("auth-model")]
    fake_md = "# ADR\n**Status:** Proposta\nbody"
    with patch("lib.knowledge_watcher.greenfield.generators.adr.run_claude_p",
               return_value=fake_md):
        results = generate_adrs(sig, topics, kb, max_workers=1)
    # Should be ADR-010 (next after 009)
    assert results[0].relative_path == "30_adr/myproj/ADR-010-auth-model.md"


def test_parallel_dispatch_returns_results_in_topic_order(tmp_path):
    sig = _signals()
    topics = [_topic("auth-model"), _topic("tenancy-model"), _topic("job-queue")]

    def fake_run(prompt, **kwargs):
        # Different output per topic to verify ordering preserved
        for slug in ("auth-model", "tenancy-model", "job-queue"):
            if slug in prompt:
                return f"# ADR\n**Status:** Proposta\n\nbody for {slug}"
        return None

    with patch("lib.knowledge_watcher.greenfield.generators.adr.run_claude_p",
               side_effect=fake_run):
        results = generate_adrs(sig, topics, tmp_path / "kb", max_workers=4)

    assert len(results) == 3
    assert "auth-model" in results[0].content
    assert "tenancy-model" in results[1].content
    assert "job-queue" in results[2].content


def test_executor_exception_recorded_per_topic(tmp_path):
    sig = _signals()
    topics = [_topic("auth-model")]
    with patch("lib.knowledge_watcher.greenfield.generators.adr.run_claude_p",
               side_effect=RuntimeError("boom")):
        results = generate_adrs(sig, topics, tmp_path / "kb", max_workers=4)
    assert len(results) == 1
    # Should record warning, not crash entire generation
    assert any("RuntimeError" in w or "executor" in w.lower() for w in results[0].warnings)


# --- W5 tests: scan param integration ---

def test_generate_adrs_uses_scan_prefix_and_numbering(tmp_path, monkeypatch):
    """Scan with prefix=MA next=13 → ADRs born MA-013, MA-014..."""
    from lib.knowledge_watcher.greenfield.adr_canonical_scan import CanonicalAdrScan

    scan = CanonicalAdrScan(
        existing_ids=["MA-001", "MA-012"], detected_prefix="MA",
        prefix_source="auto", next_free_number=13,
        topics_index={},
    )
    sig = _signals()
    topics = [_topic("topic-a", 0.9), _topic("topic-b", 0.9)]

    def fake_run(prompt, model=None, timeout_s=None, **kwargs):
        return "# ADR-fake\n\n**Status:** Proposta\n"

    monkeypatch.setattr(
        "lib.knowledge_watcher.greenfield.generators.adr.run_claude_p",
        fake_run,
    )

    results = generate_adrs(sig, topics, tmp_path / "kb", dry_run=False, scan=scan)

    paths = sorted(r.relative_path for r in results)
    assert paths[0].endswith("MA-013-topic-a.md"), f"got: {paths[0]}"
    assert paths[1].endswith("MA-014-topic-b.md"), f"got: {paths[1]}"


def test_generate_adrs_legacy_fallback_when_scan_none(tmp_path, monkeypatch):
    """scan=None → legacy _next_adr_number path; ADRs born ADR-001-..."""
    sig = _signals()
    topics = [_topic("x", 0.9)]

    def fake_run(prompt, model=None, timeout_s=None, **kwargs):
        return "# ADR-fake\n\n**Status:** Proposta\n"

    monkeypatch.setattr(
        "lib.knowledge_watcher.greenfield.generators.adr.run_claude_p",
        fake_run,
    )

    # No scan param → legacy
    results = generate_adrs(sig, topics, tmp_path / "kb", dry_run=False)
    assert len(results) == 1
    assert results[0].relative_path == "30_adr/myproj/ADR-001-x.md", \
        f"got: {results[0].relative_path}"


def test_adr_template_includes_status_history_block(tmp_path):
    """W6: ADR template gera bloco **Status history:** com entry inicial."""
    from lib.knowledge_watcher.greenfield.generators.adr import _build_prompt

    sig = _signals()
    topic = _topic("auth-model", 0.80)
    prompt = _build_prompt(sig, topic, "001")

    # Template deve incluir bloco Status history
    assert "**Status history:**" in prompt
    # Entry inicial mencionando F3 + Proposta + data
    assert "Proposta (auto-generated by F3)" in prompt
