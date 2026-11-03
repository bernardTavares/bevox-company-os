"""Tests for classifier orchestrator."""
from unittest.mock import patch

from lib.knowledge_watcher.commit_watcher import (
    Commit, DocType, ClassifierLayer, ClassifierResult,
)
from lib.knowledge_watcher.commit_watcher.classifier import classify


def _c(subject="feat: x", body="", files=None) -> Commit:
    return Commit("a"*40, "a"*7, subject, body, files or [], "", "t", "2026-05-08T10:00:00Z")


def test_pr_override_wins_over_heuristic(tmp_path):
    c = _c(subject="release: v2", body="<!-- knowledge: type=adr -->")
    r = classify(c, state_path=tmp_path / "s.json")
    assert r.doc_type == DocType.ADR
    assert r.source == ClassifierLayer.HUMAN


def test_heuristic_high_confidence_skips_llm(tmp_path):
    c = _c(subject="release: v2", files=["CHANGELOG.md"])
    with patch("lib.knowledge_watcher.commit_watcher.classifier.classify_llm") as m_llm:
        r = classify(c, state_path=tmp_path / "s.json")
    assert r.source == ClassifierLayer.HEURISTIC
    m_llm.assert_not_called()


def test_no_heuristic_match_falls_through_to_llm(tmp_path):
    c = _c(subject="chore: x", files=["package.json"])
    fake = ClassifierResult(DocType.NONE, 0.40, "deps", ClassifierLayer.LLM)
    with patch("lib.knowledge_watcher.commit_watcher.classifier.classify_llm",
               return_value=fake):
        r = classify(c, state_path=tmp_path / "s.json")
    assert r.source == ClassifierLayer.LLM


def test_low_confidence_heuristic_escalates_to_llm(tmp_path):
    c = _c(subject="refactor: A", files=["a/x.ts", "b/x.ts", "c/x.ts"])  # heuristic = 0.66
    fake = ClassifierResult(DocType.ARCHITECTURE, 0.85, "confirmed", ClassifierLayer.LLM)
    with patch("lib.knowledge_watcher.commit_watcher.classifier.classify_llm",
               return_value=fake):
        r = classify(c, state_path=tmp_path / "s.json", llm_threshold=0.70)
    assert r.source == ClassifierLayer.LLM
    assert r.confidence == 0.85


def test_heuristic_preferred_when_more_confident_than_llm(tmp_path):
    """If heuristic existed (low conf) but LLM returns even lower conf, prefer heuristic."""
    c = _c(subject="refactor: A", files=["a/x.ts", "b/x.ts", "c/x.ts"])  # heuristic = 0.66
    fake = ClassifierResult(DocType.NONE, 0.30, "uncertain", ClassifierLayer.LLM)
    with patch("lib.knowledge_watcher.commit_watcher.classifier.classify_llm",
               return_value=fake):
        r = classify(c, state_path=tmp_path / "s.json", llm_threshold=0.70)
    assert r.source == ClassifierLayer.HEURISTIC
    assert r.doc_type == DocType.ARCHITECTURE
