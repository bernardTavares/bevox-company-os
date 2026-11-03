"""Tests for adr_canonical_scan — pre-gen scan of 30_adr/<slug>/*.md."""
from __future__ import annotations

from pathlib import Path

from lib.knowledge_watcher.greenfield.adr_canonical_scan import (
    CanonicalAdrScan,
)


def test_canonical_adr_scan_required_fields():
    s = CanonicalAdrScan(
        existing_ids=["MA-001", "MA-012"],
        detected_prefix="MA",
        prefix_source="auto",
        next_free_number=13,
        topics_index={"queue": ["MA-001"], "stack": ["MA-001"]},
    )
    assert s.detected_prefix == "MA"
    assert s.next_free_number == 13
    assert "queue" in s.topics_index


def test_scan_empty_folder_fallback_prefix(tmp_path):
    """Folder não existe → prefix=ADR (fallback), next=1."""
    from lib.knowledge_watcher.greenfield.adr_canonical_scan import scan_canonical_adrs
    s = scan_canonical_adrs(tmp_path, "newproject")
    assert s.existing_ids == []
    assert s.detected_prefix == "ADR"
    assert s.prefix_source == "fallback"
    assert s.next_free_number == 1


def test_scan_empty_existing_folder_fallback(tmp_path):
    """Folder existe mas vazio → prefix=ADR fallback."""
    from lib.knowledge_watcher.greenfield.adr_canonical_scan import scan_canonical_adrs
    (tmp_path / "30_adr" / "myproj").mkdir(parents=True)
    s = scan_canonical_adrs(tmp_path, "myproj")
    assert s.detected_prefix == "ADR"
    assert s.prefix_source == "fallback"


def test_scan_override_prefix_wins(tmp_path):
    """Override prefix wins independente de folder."""
    from lib.knowledge_watcher.greenfield.adr_canonical_scan import scan_canonical_adrs
    s = scan_canonical_adrs(tmp_path, "myproj", override_prefix="BD")
    assert s.detected_prefix == "BD"
    assert s.prefix_source == "config"


def test_scan_auto_detect_majority(tmp_path):
    """Folder com 12 MA-NNN → detect MA, next=13."""
    from lib.knowledge_watcher.greenfield.adr_canonical_scan import scan_canonical_adrs
    adr_dir = tmp_path / "30_adr" / "bevox-meta-api"
    adr_dir.mkdir(parents=True)
    for n in range(1, 13):
        (adr_dir / f"MA-{n:03d}-topic-{n}.md").write_text(f"# MA-{n:03d}\n")
    s = scan_canonical_adrs(tmp_path, "bevox-meta-api")
    assert s.detected_prefix == "MA"
    assert s.prefix_source == "auto"
    assert s.next_free_number == 13
    assert len(s.existing_ids) == 12


def test_scan_mixed_prefix_majority_wins(tmp_path):
    """Folder com 3 MA-NNN + 1 ADR-NNN → MA wins (majority)."""
    from lib.knowledge_watcher.greenfield.adr_canonical_scan import scan_canonical_adrs
    adr_dir = tmp_path / "30_adr" / "myproj"
    adr_dir.mkdir(parents=True)
    (adr_dir / "MA-001-foo.md").write_text("")
    (adr_dir / "MA-002-bar.md").write_text("")
    (adr_dir / "MA-003-baz.md").write_text("")
    (adr_dir / "ADR-001-orphan.md").write_text("")
    s = scan_canonical_adrs(tmp_path, "myproj")
    assert s.detected_prefix == "MA"
    assert s.prefix_source == "auto"
    assert s.next_free_number == 4
    assert len(s.existing_ids) == 4


def test_scan_single_adr_below_threshold(tmp_path):
    """Folder com 1 ADR só → threshold 2 não atingido → fallback ADR."""
    from lib.knowledge_watcher.greenfield.adr_canonical_scan import scan_canonical_adrs
    adr_dir = tmp_path / "30_adr" / "myproj"
    adr_dir.mkdir(parents=True)
    (adr_dir / "MA-001-foo.md").write_text("")
    s = scan_canonical_adrs(tmp_path, "myproj")
    assert s.detected_prefix == "ADR"
    assert s.prefix_source == "fallback"
    assert s.next_free_number == 1


def test_scan_override_uses_correct_numbering(tmp_path):
    """Override BD: folder MA-001..003 + BD-002, prefix=BD, next=3."""
    from lib.knowledge_watcher.greenfield.adr_canonical_scan import scan_canonical_adrs
    adr_dir = tmp_path / "30_adr" / "myproj"
    adr_dir.mkdir(parents=True)
    for n in (1, 2, 3):
        (adr_dir / f"MA-{n:03d}-foo.md").write_text("")
    (adr_dir / "BD-002-existing.md").write_text("")
    s = scan_canonical_adrs(tmp_path, "myproj", override_prefix="BD")
    assert s.detected_prefix == "BD"
    assert s.prefix_source == "config"
    assert s.next_free_number == 3


def test_scan_populates_topics_index(tmp_path):
    """topics_index ganha keywords (lower, len >= 4) → ADR ids."""
    from lib.knowledge_watcher.greenfield.adr_canonical_scan import scan_canonical_adrs
    adr_dir = tmp_path / "30_adr" / "myproj"
    adr_dir.mkdir(parents=True)
    (adr_dir / "MA-001-stack.md").write_text(
        "# MA-001: Stack decisions\n\nWe use BullMQ for queue processing.\n"
    )
    (adr_dir / "MA-002-cache.md").write_text(
        "# MA-002: Cache strategy\n\nRedis for hot data caching.\n"
    )
    s = scan_canonical_adrs(tmp_path, "myproj")
    assert "MA-001" in s.topics_index.get("bullmq", [])
    assert "MA-001" in s.topics_index.get("queue", [])
    assert "MA-002" in s.topics_index.get("redis", [])
    assert "MA-002" in s.topics_index.get("cache", [])


# ---------------------------------------------------------------------------
# T2.1: detect_overlap
# ---------------------------------------------------------------------------

def test_detect_overlap_two_keywords_match():
    """2+ keywords presentes em mesmo ADR → match."""
    from lib.knowledge_watcher.greenfield.adr_canonical_scan import (
        CanonicalAdrScan, detect_overlap,
    )
    scan = CanonicalAdrScan(
        existing_ids=["MA-001"], detected_prefix="MA",
        prefix_source="auto", next_free_number=2,
        topics_index={
            "bullmq": ["MA-001"],
            "queue": ["MA-001"],
            "redis": ["MA-001"],
        },
    )
    matched = detect_overlap(scan, "job-queue", ["bullmq", "queue", "scheduler"])
    assert "MA-001" in matched


def test_detect_overlap_single_keyword_offensive_match():
    """1 keyword 'ofensiva' (frequência alta no doc) → match.

    Para teste, simulamos via topics_index com ADR id repetido 3x na mesma keyword.
    """
    from lib.knowledge_watcher.greenfield.adr_canonical_scan import (
        CanonicalAdrScan, detect_overlap,
    )
    scan = CanonicalAdrScan(
        existing_ids=["MA-001"], detected_prefix="MA",
        prefix_source="auto", next_free_number=2,
        topics_index={
            "bullmq": ["MA-001", "MA-001", "MA-001"],
        },
    )
    matched = detect_overlap(scan, "queue", ["bullmq"])
    assert "MA-001" in matched


def test_detect_overlap_no_match_returns_empty():
    """Topic novo sem keywords em comum → []."""
    from lib.knowledge_watcher.greenfield.adr_canonical_scan import (
        CanonicalAdrScan, detect_overlap,
    )
    scan = CanonicalAdrScan(
        existing_ids=["MA-001"], detected_prefix="MA",
        prefix_source="auto", next_free_number=2,
        topics_index={"bullmq": ["MA-001"], "queue": ["MA-001"]},
    )
    assert detect_overlap(scan, "auth", ["jwt", "oauth", "session"]) == []


# ---------------------------------------------------------------------------
# T2.2: compose_adr_filename + used_numbers tracking
# ---------------------------------------------------------------------------

def test_compose_filename_simple():
    """Sem números usados → next_free_number diretamente."""
    from lib.knowledge_watcher.greenfield.adr_canonical_scan import (
        CanonicalAdrScan, compose_adr_filename,
    )
    scan = CanonicalAdrScan(
        existing_ids=["MA-001"], detected_prefix="MA",
        prefix_source="auto", next_free_number=2,
        topics_index={},
    )
    used: set = set()
    fname = compose_adr_filename(scan, "stack-decisions", used)
    assert fname == "MA-002-stack-decisions.md"
    assert 2 in used


def test_compose_filename_skips_used_in_run():
    """Números já consumidos no run paralelo → próximo livre."""
    from lib.knowledge_watcher.greenfield.adr_canonical_scan import (
        CanonicalAdrScan, compose_adr_filename,
    )
    scan = CanonicalAdrScan(
        existing_ids=[], detected_prefix="ADR",
        prefix_source="fallback", next_free_number=1,
        topics_index={},
    )
    used: set = set()
    f1 = compose_adr_filename(scan, "topic-a", used)
    f2 = compose_adr_filename(scan, "topic-b", used)
    f3 = compose_adr_filename(scan, "topic-c", used)
    assert f1 == "ADR-001-topic-a.md"
    assert f2 == "ADR-002-topic-b.md"
    assert f3 == "ADR-003-topic-c.md"
    assert used == {1, 2, 3}


def test_compose_filename_zero_pads():
    """Sequência paddada com 3 dígitos."""
    from lib.knowledge_watcher.greenfield.adr_canonical_scan import (
        CanonicalAdrScan, compose_adr_filename,
    )
    scan = CanonicalAdrScan(
        existing_ids=[], detected_prefix="MA",
        prefix_source="auto", next_free_number=99,
        topics_index={},
    )
    used: set = set()
    fname = compose_adr_filename(scan, "x", used)
    assert fname == "MA-099-x.md"
