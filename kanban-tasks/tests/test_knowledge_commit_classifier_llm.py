"""Tests for classifier_llm.py — mocks anthropic SDK."""
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from lib.knowledge_watcher.commit_watcher import Commit, DocType, ClassifierLayer
from lib.knowledge_watcher.commit_watcher.classifier_llm import (
    classify_llm, build_prompt,
    _call_haiku, _call_haiku_via_subprocess, _estimate_tokens,
)


def _c() -> Commit:
    return Commit(
        "a"*40, "a"*7, "feat: add X", "body",
        ["apps/api/src/services/x.service.ts"],
        "diffstat", "t", "2026-05-08T10:00:00Z",
    )


def test_build_prompt_contains_subject_and_files():
    c = _c()
    p = build_prompt(c)
    assert "feat: add X" in p
    assert "x.service.ts" in p
    assert "diffstat" in p


def test_classify_llm_parses_response(tmp_path):
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text='{"doc_type": "spec", "confidence": 0.78, "rationale": "service file added"}')]
    fake_response.usage.input_tokens = 200
    fake_response.usage.output_tokens = 30

    with patch("lib.knowledge_watcher.commit_watcher.classifier_llm._call_haiku",
               return_value=fake_response):
        r = classify_llm(_c(), state_path=tmp_path / "state.json", budget_usd=5.0)

    assert r.doc_type == DocType.SPEC
    assert r.confidence == 0.78
    assert r.source == ClassifierLayer.LLM


def test_classify_llm_budget_exceeded_returns_low_confidence(tmp_path):
    import json
    from datetime import datetime, timezone
    state_path = tmp_path / "state.json"
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    state_path.write_text(json.dumps({
        "version": 2,
        "repos": {},
        "global": {"last_full_audit_at": None, "f1_telegram_digest_seq": 0},
        "llm_usage_month": {"month": month, "spent_usd": 5.10, "calls": 3},
    }))

    r = classify_llm(_c(), state_path=state_path, budget_usd=5.0)
    assert r.confidence < 0.5
    assert "budget" in r.rationale.lower()


def test_classify_llm_handles_invalid_json(tmp_path):
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text='not json')]
    fake_response.usage.input_tokens = 100
    fake_response.usage.output_tokens = 5

    with patch("lib.knowledge_watcher.commit_watcher.classifier_llm._call_haiku",
               return_value=fake_response):
        r = classify_llm(_c(), state_path=tmp_path / "state.json", budget_usd=5.0)
    assert r.doc_type == DocType.NONE
    assert r.confidence < 0.5


def test_classify_llm_propagates_exception_message(tmp_path):
    """Exception detail must flow into rationale, not just the type."""
    with patch("lib.knowledge_watcher.commit_watcher.classifier_llm._call_haiku",
               side_effect=RuntimeError("claude -p exit=1: auth missing")):
        r = classify_llm(_c(), state_path=tmp_path / "state.json", budget_usd=5.0)
    assert r.doc_type == DocType.NONE
    assert "RuntimeError" in r.rationale
    assert "auth missing" in r.rationale


def test_estimate_tokens_returns_at_least_one():
    assert _estimate_tokens("") == 1
    assert _estimate_tokens("hi") == 1
    assert _estimate_tokens("a" * 400) == 100


def test_call_haiku_via_subprocess_success_wraps_shape():
    fake = MagicMock()
    fake.returncode = 0
    fake.stdout = '{"doc_type": "spec"}\n'
    fake.stderr = ""
    with patch("lib.knowledge_watcher.commit_watcher.classifier_llm.subprocess.run",
               return_value=fake) as m_run:
        resp = _call_haiku_via_subprocess("the prompt")
    args, kwargs = m_run.call_args
    assert args[0][0:2] == ["claude", "-p"]
    assert "--model" in args[0]
    assert kwargs["input"] == "the prompt"
    assert kwargs["text"] is True
    assert resp.content[0].text == '{"doc_type": "spec"}'
    assert resp.usage.input_tokens >= 1
    assert resp.usage.output_tokens >= 1


def test_call_haiku_via_subprocess_filenotfound_raises_runtime():
    with patch("lib.knowledge_watcher.commit_watcher.classifier_llm.subprocess.run",
               side_effect=FileNotFoundError("claude not in PATH")):
        with pytest.raises(RuntimeError, match="claude CLI not in PATH"):
            _call_haiku_via_subprocess("p")


def test_call_haiku_via_subprocess_timeout_raises_runtime():
    with patch("lib.knowledge_watcher.commit_watcher.classifier_llm.subprocess.run",
               side_effect=subprocess.TimeoutExpired(cmd=["claude"], timeout=1)):
        with pytest.raises(RuntimeError, match="timeout"):
            _call_haiku_via_subprocess("p")


def test_call_haiku_via_subprocess_nonzero_exit_raises_with_stderr():
    fake = MagicMock()
    fake.returncode = 2
    fake.stdout = ""
    fake.stderr = "Authentication failed"
    with patch("lib.knowledge_watcher.commit_watcher.classifier_llm.subprocess.run",
               return_value=fake):
        with pytest.raises(RuntimeError, match="exit=2.*Authentication failed"):
            _call_haiku_via_subprocess("p")


def test_call_haiku_via_subprocess_empty_stdout_raises():
    fake = MagicMock()
    fake.returncode = 0
    fake.stdout = "   \n  "
    fake.stderr = ""
    with patch("lib.knowledge_watcher.commit_watcher.classifier_llm.subprocess.run",
               return_value=fake):
        with pytest.raises(RuntimeError, match="empty stdout"):
            _call_haiku_via_subprocess("p")


def test_call_haiku_routes_to_subprocess_when_no_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    sentinel = MagicMock()
    with patch("lib.knowledge_watcher.commit_watcher.classifier_llm._call_haiku_via_subprocess",
               return_value=sentinel) as m_sub, \
         patch("lib.knowledge_watcher.commit_watcher.classifier_llm._call_haiku_via_sdk") as m_sdk:
        result = _call_haiku("hello")
    assert result is sentinel
    m_sub.assert_called_once_with("hello")
    m_sdk.assert_not_called()


def test_call_haiku_routes_to_sdk_when_api_key_present(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake")
    sentinel = MagicMock()
    with patch("lib.knowledge_watcher.commit_watcher.classifier_llm._call_haiku_via_subprocess") as m_sub, \
         patch("lib.knowledge_watcher.commit_watcher.classifier_llm._call_haiku_via_sdk",
               return_value=sentinel) as m_sdk:
        result = _call_haiku("hello", max_tokens=500)
    assert result is sentinel
    m_sdk.assert_called_once_with("hello", max_tokens=500)
    m_sub.assert_not_called()
