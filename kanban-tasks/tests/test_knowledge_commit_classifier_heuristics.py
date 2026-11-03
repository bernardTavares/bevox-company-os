"""Tests for classifier_heuristics.py."""
from lib.knowledge_watcher.commit_watcher import (
    Commit, DocType, ClassifierLayer,
)
from lib.knowledge_watcher.commit_watcher.classifier_heuristics import classify_heuristic


def _make_commit(subject="feat: x", body="", files=None, diffstat="") -> Commit:
    return Commit(
        sha="a"*40, short_sha="a"*7, subject=subject, body=body,
        files_changed=files or [], diffstat=diffstat,
        author="t", timestamp_iso="2026-05-08T10:00:00Z",
    )


def test_release_prefix_detected_high_confidence():
    c = _make_commit(subject="release: v2.3.0", files=["CHANGELOG.md"])
    r = classify_heuristic(c)
    assert r is not None
    assert r.doc_type == DocType.RELEASE_NOTE
    assert r.confidence >= 0.90
    assert r.source == ClassifierLayer.HEURISTIC


def test_feat_with_new_service_detected_as_spec():
    c = _make_commit(
        subject="feat: add template service",
        files=["apps/api/src/services/template.service.ts"],
    )
    r = classify_heuristic(c)
    assert r is not None
    assert r.doc_type == DocType.SPEC
    assert r.confidence >= 0.70


def test_schema_prisma_change_flagged_as_adr():
    c = _make_commit(
        subject="feat: add tenant model",
        files=["prisma/schema.prisma"],
        diffstat="prisma/schema.prisma | 25 +++++++++++++++++++++--",
    )
    r = classify_heuristic(c)
    assert r is not None
    assert r.doc_type == DocType.ADR


def test_only_tests_returns_none_doctype():
    c = _make_commit(
        subject="test: add coverage",
        files=["apps/api/src/services/foo.test.ts", "apps/api/src/services/bar.spec.ts"],
    )
    r = classify_heuristic(c)
    assert r is not None
    assert r.doc_type == DocType.NONE


def test_only_ci_yaml_returns_none_doctype():
    c = _make_commit(
        subject="ci: bump node",
        files=[".github/workflows/deploy.yml"],
    )
    r = classify_heuristic(c)
    assert r is not None
    assert r.doc_type == DocType.NONE


def test_unknown_pattern_returns_none_for_l2_fallback():
    c = _make_commit(
        subject="chore: update deps",
        files=["package.json", "pnpm-lock.yaml"],
    )
    r = classify_heuristic(c)
    assert r is None or r.confidence < 0.70
