from lib.knowledge_watcher.commit_watcher import Commit, DocType, ClassifierLayer
from lib.knowledge_watcher.commit_watcher.classifier_pr_override import extract_pr_override


def _c(body: str) -> Commit:
    return Commit("a"*40, "a"*7, "feat: x", body, [], "", "t", "2026-05-08T10:00:00Z")


def test_override_marker_extracts_doctype():
    c = _c("body\n<!-- knowledge: type=spec -->")
    r = extract_pr_override(c)
    assert r is not None
    assert r.doc_type == DocType.SPEC
    assert r.source == ClassifierLayer.HUMAN
    assert r.confidence == 1.0


def test_override_skip_marker_returns_none_doctype():
    c = _c("body\n<!-- knowledge: type=none -->")
    r = extract_pr_override(c)
    assert r is not None
    assert r.doc_type == DocType.NONE


def test_no_marker_returns_none():
    c = _c("plain body")
    assert extract_pr_override(c) is None


def test_invalid_doctype_returns_none():
    c = _c("<!-- knowledge: type=garbage -->")
    assert extract_pr_override(c) is None
