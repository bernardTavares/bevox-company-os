"""Tests for greenfield/workflow.py — top-level pipeline orchestrator."""
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from lib.knowledge_watcher.greenfield import Tier
from lib.knowledge_watcher.greenfield.workflow import bootstrap_project


def _make_minimal_repo(tmp_path: Path, slug: str) -> Path:
    repo = tmp_path / "code" / slug
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True)
    (repo / "f.txt").write_text("x")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "feat: initial"], cwd=repo, check=True, capture_output=True)
    return repo


def test_missing_repo_returns_skipped(tmp_path):
    code = tmp_path / "code"
    code.mkdir()
    kb = tmp_path / "kb"
    kb.mkdir()
    result = bootstrap_project(
        "missing", kb, code, dry_run=True,
    )
    assert result.skipped_reason is not None
    assert "repo missing" in result.skipped_reason
    assert result.docs_generated == []


def test_dry_run_full_pipeline(tmp_path):
    repo = _make_minimal_repo(tmp_path, "myproj")
    kb = tmp_path / "kb"
    kb.mkdir()
    code = tmp_path / "code"

    with patch("lib.knowledge_watcher.greenfield.generators.adr.run_claude_p") as m_run:
        result = bootstrap_project(
            "myproj", kb, code, dry_run=True, state_path=tmp_path / "s.json",
        )

    assert result.skipped_reason is None
    assert result.total_cost_usd == 0.0
    assert len(result.docs_generated) >= 2  # at least architecture + dry-run placeholders
    # No files written in dry_run
    assert not any((kb / r.relative_path).exists() for r in result.docs_generated)
    # claude -p must not be called in dry_run
    m_run.assert_not_called()


def test_no_adr_skips_judgment_tier(tmp_path):
    repo = _make_minimal_repo(tmp_path, "myproj")
    # Add schema.prisma to trigger ADR topic detection if not skipped
    prisma = repo / "prisma"
    prisma.mkdir()
    (prisma / "schema.prisma").write_text("model A { id String @id }")
    kb = tmp_path / "kb"; kb.mkdir()
    code = tmp_path / "code"

    with patch("lib.knowledge_watcher.greenfield.workflow.detect_adr_topics") as m_topics:
        result = bootstrap_project(
            "myproj", kb, code, dry_run=True, no_adr=True,
            state_path=tmp_path / "s.json",
        )
    m_topics.assert_not_called()
    assert all(r.tier != Tier.JUDGMENT for r in result.docs_generated)


def test_real_run_writes_files(tmp_path):
    repo = _make_minimal_repo(tmp_path, "myproj")
    kb = tmp_path / "kb"; kb.mkdir()
    code = tmp_path / "code"

    # Mock LLM calls (PRD + roadmap Haiku, ADR claude -p)
    fake_haiku_resp = MagicMock()
    fake_haiku_resp.content = [MagicMock(text="# myproj — PRD\n\n## Visão de uma linha\nx")]
    fake_haiku_resp.usage.input_tokens = 100
    fake_haiku_resp.usage.output_tokens = 30

    with patch("lib.knowledge_watcher.commit_watcher.classifier_llm._call_haiku",
               return_value=fake_haiku_resp), \
         patch("lib.knowledge_watcher.greenfield.generators.adr.run_claude_p",
               return_value=None):  # ADR generation returns None → empty content
        result = bootstrap_project(
            "myproj", kb, code, dry_run=False, no_adr=True,
            state_path=tmp_path / "s.json", budget_usd=5.0,
        )

    # Architecture written (factual, non-empty)
    arch_path = kb / "20_architecture" / "myproj" / "system-overview.md"
    assert arch_path.is_file()
    assert "# System overview — myproj" in arch_path.read_text()


def test_idempotence_skips_existing_files(tmp_path):
    repo = _make_minimal_repo(tmp_path, "myproj")
    kb = tmp_path / "kb"
    arch_path = kb / "20_architecture" / "myproj" / "system-overview.md"
    arch_path.parent.mkdir(parents=True)
    arch_path.write_text("PRE-EXISTING CONTENT")
    code = tmp_path / "code"

    with patch("lib.knowledge_watcher.greenfield.generators.adr.run_claude_p",
               return_value=None):
        result = bootstrap_project(
            "myproj", kb, code, dry_run=False, no_adr=True,
            state_path=tmp_path / "s.json",
        )

    # Architecture entry has "already exists" warning
    arch_results = [r for r in result.docs_generated if r.doc_type == "architecture"]
    assert len(arch_results) == 1
    assert any("already exists" in w for w in arch_results[0].warnings)
    assert arch_results[0].content == ""
    # File still has original content (not overwritten)
    assert arch_path.read_text() == "PRE-EXISTING CONTENT"


def test_pipeline_records_total_cost_and_duration(tmp_path):
    repo = _make_minimal_repo(tmp_path, "myproj")
    kb = tmp_path / "kb"; kb.mkdir()
    code = tmp_path / "code"

    with patch("lib.knowledge_watcher.greenfield.generators.adr.run_claude_p",
               return_value=None):
        result = bootstrap_project(
            "myproj", kb, code, dry_run=True, no_adr=True,
            state_path=tmp_path / "s.json",
        )

    assert result.duration_seconds >= 0.0
    assert result.total_cost_usd == 0.0  # dry_run + no_adr → all $0


# --- W5 tests: overlap filter + force_topics ---

def _noop_doc(doc_type: str = "prd"):
    """Return a minimal DocGenResult for mocked semi-auto generators."""
    from lib.knowledge_watcher.greenfield import DocGenResult, Tier
    return DocGenResult(
        tier=Tier.SEMI_AUTO, doc_type=doc_type,
        relative_path=f"10_prd/myproj/noop-{doc_type}.md",
        content="(noop)", cost_usd=0.0, warnings=[],
    )


def test_workflow_skips_overlap_topic_with_warning(tmp_path, monkeypatch):
    """Topic overlapping canonical ADR → skip + warning, generate_adrs not called for it."""
    repo = _make_minimal_repo(tmp_path, "myproj")
    kb = tmp_path / "kb"
    # Setup 2 canonical ADRs so auto-detect majority prefix works (MA × 2)
    adr_dir = kb / "30_adr" / "myproj"
    adr_dir.mkdir(parents=True)
    (adr_dir / "MA-001-stack.md").write_text(
        "# MA-001: Stack decisions\n\nQueue via BullMQ; cache via Redis.\n"
    )
    (adr_dir / "MA-002-other.md").write_text(
        "# MA-002: Other\n\nScheduler config using bullmq queue.\n"
    )
    code = tmp_path / "code"

    # detect_adr_topics returns a topic that overlaps via "bullmq" + "queue"
    from lib.knowledge_watcher.greenfield import ADRTopic
    monkeypatch.setattr(
        "lib.knowledge_watcher.greenfield.workflow.detect_adr_topics",
        lambda signals, **kw: [ADRTopic(
            slug="job-queue", title="Queue strategy bullmq",
            rationale="bullmq detected", confidence=0.9,
        )],
    )

    # Track if generate_adrs is called (should not for the overlapping topic)
    generate_adrs_calls = {"topics": []}
    original_generate_adrs = None

    def fake_generate_adrs(signals, topics, kb_root, **kwargs):
        generate_adrs_calls["topics"].extend([t.slug for t in topics])
        return []

    monkeypatch.setattr(
        "lib.knowledge_watcher.greenfield.workflow.generate_adrs",
        fake_generate_adrs,
    )

    # Mock semi-auto to avoid Haiku LLM calls
    monkeypatch.setattr(
        "lib.knowledge_watcher.greenfield.workflow.generate_prd",
        lambda *a, **kw: _noop_doc("prd"),
    )
    monkeypatch.setattr(
        "lib.knowledge_watcher.greenfield.workflow.generate_roadmap",
        lambda *a, **kw: _noop_doc("roadmap"),
    )

    result = bootstrap_project(
        "myproj", kb, code, dry_run=False,
        state_path=tmp_path / "s.json",
    )

    # job-queue should be skipped → skip DocGenResult with overlap warning
    skip_docs = [
        d for d in result.docs_generated
        if d.doc_type == "adr" and any("overlap" in w.lower() for w in d.warnings)
    ]
    assert len(skip_docs) >= 1, "expected at least 1 skip doc with overlap warning"
    assert any("MA-001" in w or "MA-002" in w for w in skip_docs[0].warnings), \
        f"overlap warning should mention canonical ADR; got: {skip_docs[0].warnings}"
    assert skip_docs[0].cost_usd == 0.0

    # generate_adrs should not have been called with job-queue
    assert "job-queue" not in generate_adrs_calls["topics"], \
        "overlapping topic should not reach generate_adrs"


def test_workflow_force_topics_bypass_overlap(tmp_path, monkeypatch):
    """force_topics=['job-queue'] → overlap not filtered, topic reaches generate_adrs."""
    repo = _make_minimal_repo(tmp_path, "myproj")
    kb = tmp_path / "kb"
    adr_dir = kb / "30_adr" / "myproj"
    adr_dir.mkdir(parents=True)
    (adr_dir / "MA-001-stack.md").write_text(
        "# MA-001\n\nQueue via BullMQ; bullmq bullmq bullmq.\n"
    )
    (adr_dir / "MA-002-x.md").write_text("# MA-002\n\nBullMQ queue scheduler.\n")
    code = tmp_path / "code"

    from lib.knowledge_watcher.greenfield import ADRTopic
    monkeypatch.setattr(
        "lib.knowledge_watcher.greenfield.workflow.detect_adr_topics",
        lambda signals, **kw: [ADRTopic(
            slug="job-queue", title="Queue bullmq",
            rationale="x", confidence=0.9,
        )],
    )

    forced_call: dict = {"called": False, "topics": [], "scan": None}

    def fake_generate_adrs(signals, topics, kb_root, **kwargs):
        forced_call["called"] = True
        forced_call["topics"] = [t.slug for t in topics]
        forced_call["scan"] = kwargs.get("scan")
        return []

    monkeypatch.setattr(
        "lib.knowledge_watcher.greenfield.workflow.generate_adrs",
        fake_generate_adrs,
    )

    monkeypatch.setattr(
        "lib.knowledge_watcher.greenfield.workflow.generate_prd",
        lambda *a, **kw: _noop_doc("prd"),
    )
    monkeypatch.setattr(
        "lib.knowledge_watcher.greenfield.workflow.generate_roadmap",
        lambda *a, **kw: _noop_doc("roadmap"),
    )

    bootstrap_project(
        "myproj", kb, code, dry_run=False,
        state_path=tmp_path / "s.json",
        force_topics=["job-queue"],
    )

    assert forced_call["called"], "generate_adrs should have been called"
    assert "job-queue" in forced_call["topics"], \
        "force_topics should bypass overlap filter"
    assert forced_call["scan"] is not None, \
        "scan must be passed to generate_adrs even with force_topics"
