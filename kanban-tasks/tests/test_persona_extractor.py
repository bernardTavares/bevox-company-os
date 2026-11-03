"""Tests for persona_extractor — claude CLI subprocess wrapper.

Mocks subprocess.run because the real claude CLI requires authentication
and consumes subscription quota. The integration test (separate file,
@pytest.mark.integration) hits the real CLI.
"""
import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest


PRD_FIXTURE = """# PRD: Test Project

The Test Project aims to build X for Y. Stakeholders include the founder
and the head of operations. Goal: ship a working prototype by Q3.
"""

VALID_LLM_OUTPUT = json.dumps({
    "identity": (
        "---\n"
        "agent_name: voz-test-proj\n"
        "project: test-proj\n"
        "project_display_name: Test Project\n"
        "domain: Produto\n"
        "created: 2026-04-28\n"
        "persona_status: generated\n"
        "---\n\n"
        "# Voz Test Project\n\nEu sou o Voz...\n"
    ),
    "soul": (
        "---\nproject: test-proj\npersona_status: generated\n---\n\n"
        "# Soul — Voz Test Project\n\n## Tom\nDireto.\n"
    ),
    "memory_projects": (
        "---\nproject: test-proj\ncreated: 2026-04-28\n"
        "persona_status: generated\n---\n\n"
        "# Test Project\n\n## Contexto\nResumo.\n"
    ),
})


def _completed(stdout: str, returncode: int = 0, stderr: str = "") -> MagicMock:
    """Build a mock CompletedProcess for subprocess.run."""
    cp = MagicMock(spec=subprocess.CompletedProcess)
    cp.stdout = stdout
    cp.stderr = stderr
    cp.returncode = returncode
    return cp


def test_extract_persona_happy_path():
    """Valid LLM output → status=generated; 3 files content returned."""
    from lib.persona_extractor import extract_persona

    with patch("lib.persona_extractor.subprocess.run",
               return_value=_completed(VALID_LLM_OUTPUT)):
        result = extract_persona(
            slug="test-proj",
            project_display_name="Test Project",
            domain="Produto",
            date_str="2026-04-28",
            prd_text=PRD_FIXTURE,
            timeout_s=30,
        )

    assert result["status"] == "generated"
    assert "agent_name: voz-test-proj" in result["identity"]
    assert "Voz Test Project" in result["soul"]
    assert "test-proj" in result["memory_projects"]


def test_extract_persona_strips_markdown_code_fence():
    """LLM wraps JSON in ```json ... ``` fence → still parses successfully.

    Real-world regression: Claude often wraps JSON in code fences despite
    explicit instructions not to. The extractor must defensively strip
    fences before parsing. Caught during E.2 smoke 2026-04-28.
    """
    from lib.persona_extractor import extract_persona

    fenced = "```json\n" + VALID_LLM_OUTPUT + "\n```"
    with patch("lib.persona_extractor.subprocess.run",
               return_value=_completed(fenced)):
        result = extract_persona(
            slug="test-proj",
            project_display_name="Test Project",
            domain="Produto",
            date_str="2026-04-28",
            prd_text=PRD_FIXTURE,
            timeout_s=30,
        )

    assert result["status"] == "generated"
    assert "voz-test-proj" in result["identity"]


def test_extract_persona_strips_bare_code_fence():
    """LLM wraps JSON in ``` ... ``` (no language tag) → still parses."""
    from lib.persona_extractor import extract_persona

    fenced = "```\n" + VALID_LLM_OUTPUT + "\n```"
    with patch("lib.persona_extractor.subprocess.run",
               return_value=_completed(fenced)):
        result = extract_persona(
            slug="test-proj",
            project_display_name="Test Project",
            domain="Produto",
            date_str="2026-04-28",
            prd_text=PRD_FIXTURE,
            timeout_s=30,
        )

    assert result["status"] == "generated"


def test_extract_persona_invalid_json_falls_back():
    """LLM returns non-JSON → status=invalid; no exception."""
    from lib.persona_extractor import extract_persona

    with patch("lib.persona_extractor.subprocess.run",
               return_value=_completed("not json at all")):
        result = extract_persona(
            slug="test-proj",
            project_display_name="Test Project",
            domain="Produto",
            date_str="2026-04-28",
            prd_text=PRD_FIXTURE,
            timeout_s=30,
        )

    assert result["status"] == "invalid"
    assert "json" in result["error"].lower() or "decode" in result["error"].lower()


def test_extract_persona_missing_keys_falls_back():
    """LLM returns JSON but missing required keys → invalid."""
    from lib.persona_extractor import extract_persona

    bad_output = json.dumps({"identity": "x"})  # missing soul, memory_projects
    with patch("lib.persona_extractor.subprocess.run",
               return_value=_completed(bad_output)):
        result = extract_persona(
            slug="test-proj",
            project_display_name="Test Project",
            domain="Produto",
            date_str="2026-04-28",
            prd_text=PRD_FIXTURE,
            timeout_s=30,
        )

    assert result["status"] == "invalid"


def test_extract_persona_nonzero_exit_falls_back():
    """claude CLI exits non-zero → status=error."""
    from lib.persona_extractor import extract_persona

    with patch("lib.persona_extractor.subprocess.run",
               return_value=_completed("", returncode=1, stderr="auth failed")):
        result = extract_persona(
            slug="test-proj",
            project_display_name="Test Project",
            domain="Produto",
            date_str="2026-04-28",
            prd_text=PRD_FIXTURE,
            timeout_s=30,
        )

    assert result["status"] == "error"
    assert "auth failed" in result["error"]


def test_extract_persona_timeout_falls_back():
    """subprocess.run raises TimeoutExpired → status=error."""
    from lib.persona_extractor import extract_persona

    with patch("lib.persona_extractor.subprocess.run",
               side_effect=subprocess.TimeoutExpired(cmd=["claude"], timeout=30)):
        result = extract_persona(
            slug="test-proj",
            project_display_name="Test Project",
            domain="Produto",
            date_str="2026-04-28",
            prd_text=PRD_FIXTURE,
            timeout_s=30,
        )

    assert result["status"] == "error"
    assert "timeout" in result["error"].lower()


def test_extract_persona_claude_not_installed_falls_back():
    """If `claude` not on PATH, subprocess.run raises FileNotFoundError."""
    from lib.persona_extractor import extract_persona

    with patch("lib.persona_extractor.subprocess.run",
               side_effect=FileNotFoundError("claude not found")):
        result = extract_persona(
            slug="test-proj",
            project_display_name="Test Project",
            domain="Produto",
            date_str="2026-04-28",
            prd_text=PRD_FIXTURE,
            timeout_s=30,
        )

    assert result["status"] == "error"
    assert "claude" in result["error"].lower()
