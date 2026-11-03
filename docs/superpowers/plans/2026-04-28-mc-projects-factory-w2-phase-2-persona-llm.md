# MC Projects Factory Wave 2 — Phase 2: Persona LLM Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add LLM-powered persona generation to `openclaw project create`. After step_3 clones the template, step_4 calls Claude Haiku 4.5 with the project's PRD and generates rich `IDENTITY.md`, `SOUL.md`, and `memory/projects/<slug>.md`. Adds `--prd` flag to CLI and a `regenerate-persona` subcommand.

> **REVISED 2026-04-27:** Persona extractor uses `claude -p` subprocess instead of Anthropic SDK. Reason: Bernard authenticates via claude.ai subscription (no direct API key). Same pattern as `tester-agent`. See spec amendment commit `a7ca629` in bevox-knowledge.

**Architecture:** New `persona_extractor.py` module shells out to `claude -p --model claude-haiku-4-5 --output-format json`, passes the rendered prompt via stdin, validates the LLM output (JSON with `identity`/`soul`/`memory_projects` keys), and writes 3 files. New `step_4_persona_llm` in `project_factory.py` runs after `step_3`. Failure (timeout, non-zero exit, invalid output) leaves PENDING markers in place and writes `PERSONA_PENDING.md` for human-driven regeneration. Feature flag `OPENCLAW_PERSONA_LLM` (default `1`) gates the whole step.

**Tech Stack:** Python 3.13 stdlib (subprocess, json, pathlib); pytest with `unittest.mock` for `subprocess.run` patching. **No new Python deps.**

**Spec:** `bevox-knowledge/35_specs/openclaw/2026-04-28-mc-projects-factory-wave-2-vox-clone.md` §2.2, §3.1 step T+5s, §6 (Phase 2).

**Pre-requisites:**
- Phase 1 merged (workspace-template exists, step_3 clones it)
- `claude` CLI installed and authenticated (`claude --version` works; subscription active)
- `~/.openclaw/workspace-template/IDENTITY.md`, `SOUL.md`, `memory/projects/{{SLUG}}.md`, `memory/context/business-context.md` carry `<!-- PERSONA: PENDING -->` markers (Phase 1)

---

## File Structure

| Path | Action | Responsibility |
|---|---|---|
| `~/.openclaw/kanban-tasks/lib/persona_extractor.py` | CREATE | Anthropic SDK wrapper; prompt; output validation; fallback |
| `~/.openclaw/kanban-tasks/lib/project_factory.py` | MODIFY | Add `step_4_persona_llm`; thread `prd_file` + `domain` through `create_project` |
| `~/.openclaw/kanban-tasks/lib/api.py` | MODIFY | Add `--prd` to `pcreate`; add `pregenerate` subcommand |
| `~/.openclaw/kanban-tasks/tests/test_persona_extractor.py` | CREATE | Unit tests with Anthropic mocked |
| `~/.openclaw/kanban-tasks/tests/test_project_factory.py` | MODIFY | Add tests for step_4 flow + fallback |
| `~/.openclaw/kanban-tasks/requirements.txt` (or pyproject) | MODIFY | Add `anthropic>=0.40.0` |
| `~/.openclaw/kanban-tasks/PROMPTS/persona-extractor.md` | CREATE | Externalized prompt for review/iteration |
| `bevox-knowledge/20_architecture/openclaw/persona-extractor-prompt.md` | CREATE | Canonical mirror of the prompt (committed in kb) |

---

## Task 1: Setup branch + add anthropic dependency

- [ ] **Step 1: Branch**

```bash
cd ~/.openclaw
git checkout main
git pull origin main
git checkout -b feat/mc-projects-factory-w2-phase-2-persona-llm
```

- [ ] **Step 2: Verify Phase 1 landed**

```bash
ls ~/.openclaw/workspace-template/IDENTITY.md
grep -l "PERSONA: PENDING" ~/.openclaw/workspace-template/IDENTITY.md
```

Expected: file exists, marker present.

- [ ] **Step 3: Add anthropic SDK to requirements**

Edit `~/.openclaw/kanban-tasks/requirements.txt`. Add a line:

```
anthropic>=0.40.0
```

(If `requirements.txt` doesn't exist, check for `pyproject.toml` or whatever dep manifest is used. If neither, install via `pip3 install anthropic` and document in the PR.)

- [ ] **Step 4: Install**

```bash
pip3 install --user "anthropic>=0.40.0"
python3 -c "import anthropic; print(anthropic.__version__)"
```

Expected: version >=0.40.0 printed.

---

## Task 2: Externalize persona prompt

**Files:**
- Create: `~/.openclaw/kanban-tasks/PROMPTS/persona-extractor.md`

- [ ] **Step 1: Write prompt**

```bash
mkdir -p ~/.openclaw/kanban-tasks/PROMPTS
cat > ~/.openclaw/kanban-tasks/PROMPTS/persona-extractor.md <<'EOF'
# Persona extractor prompt

You are a persona architect for an internal Company OS called OpenClaw, used
by a single human (Bernard Tavares, founder of Bevox). For each new project,
OpenClaw spawns a "Voz-like" agent — a Chief of Staff dedicated to that
specific project's domain.

Given the project PRD below, generate exactly THREE markdown files:

1. **IDENTITY.md** — defines who the agent is for this project. Sections:
   - Frontmatter: agent_name, project, project_display_name, domain, created, persona_status: generated
   - "# Voz {project_display_name}" header
   - One concise paragraph: "Eu sou o Voz {project_display_name}, agente Chief of Staff dedicado ao projeto {slug}..."
   - "## Missão" section: 2-3 sentences, derived from the PRD's stated goal
   - "## Como me chamar" section: short list of natural phrases
   - "## O que eu não sou" section: bounds (this agent does X, not Y)

2. **SOUL.md** — defines how the agent operates. Sections:
   - Frontmatter: project, persona_status: generated
   - "# Soul — Voz {project_display_name}" header
   - "## Tom" section: 2-4 lines describing voice (professional but warm, terse, direct, etc.)
   - "## Valores operacionais" section: 4-6 bullet points specific to this project's domain
   - "## Anti-patterns" section: 4-6 bullets — things this agent should NOT do
   - "## Quando discordar" section: 2-3 sentences on disagreement etiquette

3. **memory_projects.md** (will be saved as `memory/projects/{slug}.md`) — project context. Sections:
   - Frontmatter: project, created, persona_status: generated
   - "# {project_display_name}" header
   - "## Contexto" — 1-2 paragraphs summarizing the PRD
   - "## Objetivo principal" — 1-2 sentences
   - "## Stakeholders" — list, if PRD mentions
   - "## Estado atual" — 1 paragraph; mention "PRD canônico em `bevox-knowledge/10_prd/{slug}/`"
   - "## Próximos passos óbvios" — 3-5 bullets derived from PRD (don't invent priorities, just surface what the PRD already says)

CRITICAL constraints:
- Be **strictly faithful to the PRD**. Do not invent goals, stakeholders, or facts not stated.
- Tone: Brazilian Portuguese (pt-BR), direct, professional, terse. No emojis. No flowery prose.
- Use the project metadata exactly as provided (slug, project_display_name, domain).
- Do NOT include "PERSONA: PENDING" markers — those are placeholders this output replaces.
- Output format: a single JSON object with keys `identity`, `soul`, `memory_projects`, each value being the full markdown content of that file. No prose around the JSON.

Project metadata:
- slug: {SLUG}
- project_display_name: {PROJECT_NAME}
- domain: {DOMAIN}
- created: {DATE}

PRD:

---
{PRD_CONTENT}
---
EOF
```

- [ ] **Step 2: Mirror prompt in bevox-knowledge for canonical reference**

```bash
mkdir -p ~/bevox-knowledge/20_architecture/openclaw
cp ~/.openclaw/kanban-tasks/PROMPTS/persona-extractor.md \
   ~/bevox-knowledge/20_architecture/openclaw/persona-extractor-prompt.md
```

We'll commit the kb mirror in a separate kb commit.

---

## Task 3: TDD — Write failing tests for persona_extractor.py

**Files:**
- Create: `~/.openclaw/kanban-tasks/tests/test_persona_extractor.py`

- [ ] **Step 1: Write failing tests**

```bash
cat > ~/.openclaw/kanban-tasks/tests/test_persona_extractor.py <<'EOF'
"""Tests for persona_extractor — the Anthropic-backed persona generator."""
import json
from unittest.mock import MagicMock, patch

import pytest


PRD_FIXTURE = """# PRD: Test Project

The Test Project aims to build X for Y. Stakeholders include the founder
and the head of operations. Goal: ship a working prototype by Q3.
"""

VALID_LLM_RESPONSE = json.dumps({
    "identity": (
        "---\n"
        "agent_name: voz-test-proj\n"
        "project: test-proj\n"
        "project_display_name: Test Project\n"
        "domain: Produto\n"
        "created: 2026-04-28\n"
        "persona_status: generated\n"
        "---\n\n"
        "# Voz Test Project\n\n"
        "Eu sou o Voz Test Project, agente dedicado ao projeto test-proj.\n\n"
        "## Missão\nShip a working prototype by Q3.\n\n"
        "## Como me chamar\n- voz-test-proj\n\n"
        "## O que eu não sou\n- não sou o produto principal\n"
    ),
    "soul": (
        "---\n"
        "project: test-proj\n"
        "persona_status: generated\n"
        "---\n\n"
        "# Soul — Voz Test Project\n\n"
        "## Tom\nDireto, profissional.\n\n"
        "## Valores operacionais\n- entrega\n- clareza\n\n"
        "## Anti-patterns\n- inventar fatos\n\n"
        "## Quando discordar\nDigo claro com alternativa.\n"
    ),
    "memory_projects": (
        "---\n"
        "project: test-proj\n"
        "created: 2026-04-28\n"
        "persona_status: generated\n"
        "---\n\n"
        "# Test Project\n\n"
        "## Contexto\nSummary do PRD.\n\n"
        "## Objetivo principal\nShip protótipo Q3.\n\n"
        "## Stakeholders\n- founder\n- head of ops\n\n"
        "## Estado atual\nPRD em bevox-knowledge/10_prd/test-proj/.\n\n"
        "## Próximos passos óbvios\n- spec técnica\n- setup\n"
    ),
})


def _mock_anthropic_response(text: str) -> MagicMock:
    """Build a mock Anthropic Message response with one text block."""
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    return msg


def test_extract_persona_happy_path():
    """Valid LLM response → 3 files written with substitutions applied."""
    from lib.persona_extractor import extract_persona

    with patch("lib.persona_extractor.Anthropic") as anth_cls:
        client = MagicMock()
        client.messages.create.return_value = _mock_anthropic_response(VALID_LLM_RESPONSE)
        anth_cls.return_value = client

        result = extract_persona(
            slug="test-proj",
            project_display_name="Test Project",
            domain="Produto",
            date_str="2026-04-28",
            prd_text=PRD_FIXTURE,
            api_key="sk-test",
            timeout_s=30,
            model="claude-haiku-4-5",
        )

    assert result["status"] == "generated"
    assert "agent_name: voz-test-proj" in result["identity"]
    assert "Voz Test Project" in result["soul"]
    assert "test-proj" in result["memory_projects"]


def test_extract_persona_invalid_json_falls_back():
    """LLM returns non-JSON → status=invalid, no exception."""
    from lib.persona_extractor import extract_persona

    with patch("lib.persona_extractor.Anthropic") as anth_cls:
        client = MagicMock()
        client.messages.create.return_value = _mock_anthropic_response("not json at all")
        anth_cls.return_value = client

        result = extract_persona(
            slug="test-proj",
            project_display_name="Test Project",
            domain="Produto",
            date_str="2026-04-28",
            prd_text=PRD_FIXTURE,
            api_key="sk-test",
            timeout_s=30,
            model="claude-haiku-4-5",
        )

    assert result["status"] == "invalid"
    assert "error" in result


def test_extract_persona_missing_keys_falls_back():
    """LLM returns JSON but missing required keys → invalid status."""
    from lib.persona_extractor import extract_persona

    bad_response = json.dumps({"identity": "x"})  # missing soul, memory_projects

    with patch("lib.persona_extractor.Anthropic") as anth_cls:
        client = MagicMock()
        client.messages.create.return_value = _mock_anthropic_response(bad_response)
        anth_cls.return_value = client

        result = extract_persona(
            slug="test-proj",
            project_display_name="Test Project",
            domain="Produto",
            date_str="2026-04-28",
            prd_text=PRD_FIXTURE,
            api_key="sk-test",
            timeout_s=30,
            model="claude-haiku-4-5",
        )

    assert result["status"] == "invalid"


def test_extract_persona_api_error_falls_back():
    """API raises → status=error."""
    from lib.persona_extractor import extract_persona

    with patch("lib.persona_extractor.Anthropic") as anth_cls:
        client = MagicMock()
        client.messages.create.side_effect = RuntimeError("boom")
        anth_cls.return_value = client

        result = extract_persona(
            slug="test-proj",
            project_display_name="Test Project",
            domain="Produto",
            date_str="2026-04-28",
            prd_text=PRD_FIXTURE,
            api_key="sk-test",
            timeout_s=30,
            model="claude-haiku-4-5",
        )

    assert result["status"] == "error"
    assert "boom" in result["error"]
EOF
```

- [ ] **Step 2: Run tests, verify they all FAIL with ImportError**

```bash
cd ~/.openclaw/kanban-tasks
python3 -m pytest tests/test_persona_extractor.py -v
```

Expected: 4 errors / failures, all due to `lib.persona_extractor` not existing yet.

---

## Task 4: Implement persona_extractor.py

**Files:**
- Create: `~/.openclaw/kanban-tasks/lib/persona_extractor.py`

- [ ] **Step 1: Write module**

```bash
cat > ~/.openclaw/kanban-tasks/lib/persona_extractor.py <<'EOF'
"""LLM-driven persona extractor.

Calls Claude Haiku with the project PRD and produces IDENTITY.md, SOUL.md,
and memory/projects/<slug>.md content. Validates output structure; on any
failure returns a status describing why so the caller can fall back gracefully.

Spec: bevox-knowledge/35_specs/openclaw/2026-04-28-mc-projects-factory-wave-2-vox-clone.md §3.1 (T+5s)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

try:
    from anthropic import Anthropic
except ImportError:  # pragma: no cover
    Anthropic = None  # type: ignore[assignment]


REQUIRED_KEYS = ("identity", "soul", "memory_projects")
PROMPT_PATH = Path(__file__).parent.parent / "PROMPTS" / "persona-extractor.md"


def _load_prompt_template() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _render_prompt(
    *, slug: str, project_display_name: str, domain: str,
    date_str: str, prd_text: str,
) -> str:
    tmpl = _load_prompt_template()
    return (
        tmpl.replace("{SLUG}", slug)
        .replace("{PROJECT_NAME}", project_display_name)
        .replace("{DOMAIN}", domain)
        .replace("{DATE}", date_str)
        .replace("{PRD_CONTENT}", prd_text)
    )


def _validate_response(payload: Dict[str, Any]) -> None:
    """Raise ValueError if payload missing required keys or values aren't strings."""
    for key in REQUIRED_KEYS:
        if key not in payload:
            raise ValueError(f"missing required key: {key}")
        if not isinstance(payload[key], str) or not payload[key].strip():
            raise ValueError(f"key {key!r} must be non-empty string")


def extract_persona(
    *,
    slug: str,
    project_display_name: str,
    domain: str,
    date_str: str,
    prd_text: str,
    api_key: str,
    timeout_s: int = 30,
    model: str = "claude-haiku-4-5",
    max_tokens: int = 4000,
) -> Dict[str, Any]:
    """Generate persona files from PRD.

    Returns dict with:
      - status: "generated" | "invalid" | "error"
      - identity, soul, memory_projects: str (only when status=="generated")
      - error: str (when status != "generated")
    """
    if Anthropic is None:
        return {"status": "error", "error": "anthropic SDK not installed"}

    try:
        client = Anthropic(api_key=api_key, timeout=timeout_s)
    except Exception as e:
        return {"status": "error", "error": f"client init: {e}"}

    prompt = _render_prompt(
        slug=slug,
        project_display_name=project_display_name,
        domain=domain,
        date_str=date_str,
        prd_text=prd_text,
    )

    try:
        msg = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        return {"status": "error", "error": str(e)}

    raw = "".join(getattr(b, "text", "") for b in (msg.content or []))

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        return {"status": "invalid", "error": f"json decode: {e}", "raw": raw[:500]}

    try:
        _validate_response(payload)
    except ValueError as e:
        return {"status": "invalid", "error": str(e)}

    return {
        "status": "generated",
        "identity": payload["identity"],
        "soul": payload["soul"],
        "memory_projects": payload["memory_projects"],
    }
EOF
```

- [ ] **Step 2: Run tests, verify all PASS**

```bash
cd ~/.openclaw/kanban-tasks
python3 -m pytest tests/test_persona_extractor.py -v
```

Expected: 4 PASSED.

---

## Task 5: TDD — Write failing tests for step_4_persona_llm

**Files:**
- Modify: `~/.openclaw/kanban-tasks/tests/test_project_factory.py`

- [ ] **Step 1: Append tests**

Append to `~/.openclaw/kanban-tasks/tests/test_project_factory.py`:

```python
def _setup_workspace_with_pending_markers(tmp_path):
    """Helper: create workspace-foo/ with PERSONA: PENDING markers."""
    workspace = tmp_path / ".openclaw" / "workspace-foo"
    workspace.mkdir(parents=True)
    (workspace / "IDENTITY.md").write_text(
        "<!-- PERSONA: PENDING -->\nplaceholder identity\n"
    )
    (workspace / "SOUL.md").write_text(
        "<!-- PERSONA: PENDING -->\nplaceholder soul\n"
    )
    (workspace / "memory" / "projects").mkdir(parents=True)
    (workspace / "memory" / "projects" / "foo.md").write_text(
        "<!-- PERSONA: PENDING -->\nplaceholder project memory\n"
    )
    return workspace


def test_step_4_writes_persona_files_on_success(tmp_path):
    """step_4_persona_llm replaces PENDING content with LLM output."""
    from unittest.mock import patch
    from lib.project_factory import step_4_persona_llm

    workspace = _setup_workspace_with_pending_markers(tmp_path)

    fake_result = {
        "status": "generated",
        "identity": "real identity content\n",
        "soul": "real soul content\n",
        "memory_projects": "real project content\n",
    }

    with patch("lib.project_factory.persona_extractor.extract_persona",
               return_value=fake_result):
        out = step_4_persona_llm(
            slug="foo",
            name="Foo",
            domain="Produto",
            date_str="2026-04-28",
            prd_text="PRD here",
            workspace_dir=workspace,
            api_key="sk-test",
        )

    assert out["persona_status"] == "generated"
    assert (workspace / "IDENTITY.md").read_text() == "real identity content\n"
    assert (workspace / "SOUL.md").read_text() == "real soul content\n"
    assert (workspace / "memory" / "projects" / "foo.md").read_text() == \
        "real project content\n"
    assert not (workspace / "PERSONA_PENDING.md").exists()


def test_step_4_writes_pending_marker_on_failure(tmp_path):
    """When extract_persona returns error, step_4 writes PERSONA_PENDING.md."""
    from unittest.mock import patch
    from lib.project_factory import step_4_persona_llm

    workspace = _setup_workspace_with_pending_markers(tmp_path)
    pre_identity = (workspace / "IDENTITY.md").read_text()

    fake_result = {"status": "error", "error": "timeout"}

    with patch("lib.project_factory.persona_extractor.extract_persona",
               return_value=fake_result):
        out = step_4_persona_llm(
            slug="foo",
            name="Foo",
            domain="Produto",
            date_str="2026-04-28",
            prd_text="PRD here",
            workspace_dir=workspace,
            api_key="sk-test",
        )

    assert out["persona_status"] == "pending"
    assert out["error"] == "timeout"
    # Pending placeholders untouched
    assert (workspace / "IDENTITY.md").read_text() == pre_identity
    # Recovery hint file exists
    assert (workspace / "PERSONA_PENDING.md").exists()
    pending_md = (workspace / "PERSONA_PENDING.md").read_text()
    assert "regenerate-persona foo" in pending_md
    assert "timeout" in pending_md


def test_step_4_skips_when_already_generated(tmp_path):
    """If IDENTITY.md does NOT contain PENDING marker, step_4 skips (idempotent)."""
    from unittest.mock import patch
    from lib.project_factory import step_4_persona_llm

    workspace = _setup_workspace_with_pending_markers(tmp_path)
    # Mark IDENTITY as already generated
    (workspace / "IDENTITY.md").write_text(
        "---\npersona_status: generated\n---\nReal content already.\n"
    )

    with patch("lib.project_factory.persona_extractor.extract_persona") as mock_e:
        out = step_4_persona_llm(
            slug="foo",
            name="Foo",
            domain="Produto",
            date_str="2026-04-28",
            prd_text="PRD here",
            workspace_dir=workspace,
            api_key="sk-test",
        )

    mock_e.assert_not_called()
    assert out["persona_status"] == "already_generated"


def test_step_4_skipped_via_feature_flag(tmp_path, monkeypatch):
    """When OPENCLAW_PERSONA_LLM=0, step_4 is no-op."""
    from unittest.mock import patch
    from lib.project_factory import step_4_persona_llm

    workspace = _setup_workspace_with_pending_markers(tmp_path)
    monkeypatch.setenv("OPENCLAW_PERSONA_LLM", "0")

    with patch("lib.project_factory.persona_extractor.extract_persona") as mock_e:
        out = step_4_persona_llm(
            slug="foo",
            name="Foo",
            domain="Produto",
            date_str="2026-04-28",
            prd_text="PRD here",
            workspace_dir=workspace,
            api_key="sk-test",
        )

    mock_e.assert_not_called()
    assert out["persona_status"] == "skipped_flag"
```

- [ ] **Step 2: Run tests, verify they FAIL with ImportError or AttributeError**

```bash
cd ~/.openclaw/kanban-tasks
python3 -m pytest tests/test_project_factory.py::test_step_4_writes_persona_files_on_success tests/test_project_factory.py::test_step_4_writes_pending_marker_on_failure tests/test_project_factory.py::test_step_4_skips_when_already_generated tests/test_project_factory.py::test_step_4_skipped_via_feature_flag -v
```

Expected: 4 errors (`step_4_persona_llm` not defined yet).

---

## Task 6: Implement step_4_persona_llm in project_factory.py

**Files:**
- Modify: `~/.openclaw/kanban-tasks/lib/project_factory.py`

- [ ] **Step 1: Add import + new function**

At the top of `project_factory.py`, after existing imports, add:

```python
import os
from lib import persona_extractor
```

Then add the new function (after `step_3_create_workspace`):

```python
def step_4_persona_llm(
    *,
    slug: str,
    name: str,
    domain: str,
    date_str: str,
    prd_text: str,
    workspace_dir: Path,
    api_key: str | None,
) -> dict:
    """Generate persona files via LLM; fall back to PENDING marker on failure.

    Idempotent: skips if IDENTITY.md already shows persona_status: generated.
    Honors feature flag OPENCLAW_PERSONA_LLM (default 1).
    """
    if os.environ.get("OPENCLAW_PERSONA_LLM", "1") == "0":
        return {"persona_status": "skipped_flag"}

    identity_path = workspace_dir / "IDENTITY.md"
    if identity_path.exists():
        text = identity_path.read_text(encoding="utf-8")
        if "persona_status: generated" in text:
            return {"persona_status": "already_generated"}

    if not api_key:
        return _write_pending_marker(
            workspace_dir, slug, error="no api key configured"
        )

    result = persona_extractor.extract_persona(
        slug=slug,
        project_display_name=name,
        domain=domain,
        date_str=date_str,
        prd_text=prd_text,
        api_key=api_key,
    )

    if result["status"] != "generated":
        return _write_pending_marker(
            workspace_dir, slug,
            error=result.get("error", result["status"]),
        )

    # Write the 3 files
    identity_path.write_text(result["identity"], encoding="utf-8")
    (workspace_dir / "SOUL.md").write_text(result["soul"], encoding="utf-8")
    project_md = workspace_dir / "memory" / "projects" / f"{slug}.md"
    project_md.parent.mkdir(parents=True, exist_ok=True)
    project_md.write_text(result["memory_projects"], encoding="utf-8")

    # Remove any stale PENDING marker file
    pending = workspace_dir / "PERSONA_PENDING.md"
    if pending.exists():
        pending.unlink()

    return {"persona_status": "generated"}


def _write_pending_marker(
    workspace_dir: Path, slug: str, error: str
) -> dict:
    """Write PERSONA_PENDING.md with recovery instructions; return pending status."""
    pending_md = workspace_dir / "PERSONA_PENDING.md"
    pending_md.write_text(
        f"""# Persona pending — {slug}

Persona LLM generation did not complete.

**Reason:** {error}

To regenerate, run:

```bash
openclaw project regenerate-persona {slug}
```

(This requires `ANTHROPIC_API_KEY` in env and a PRD at
`bevox-knowledge/10_prd/{slug}/`.)
""",
        encoding="utf-8",
    )
    return {"persona_status": "pending", "error": error}
```

- [ ] **Step 2: Run failing tests, verify they pass**

```bash
cd ~/.openclaw/kanban-tasks
python3 -m pytest tests/test_project_factory.py::test_step_4_writes_persona_files_on_success tests/test_project_factory.py::test_step_4_writes_pending_marker_on_failure tests/test_project_factory.py::test_step_4_skips_when_already_generated tests/test_project_factory.py::test_step_4_skipped_via_feature_flag -v
```

Expected: 4 PASSED.

---

## Task 7: Wire step_4 into create_project orchestrator + thread `prd_file` and `domain`

**Files:**
- Modify: `~/.openclaw/kanban-tasks/lib/project_factory.py`

- [ ] **Step 1: Extend ProjectCreateConfig**

Find `@dataclass class ProjectCreateConfig`. Add fields:

```python
@dataclass
class ProjectCreateConfig:
    kb_dir: Path
    openclaw_dir: Path
    code_dir: Path
    meta_path: Path
    log_path: Path
    templates_dir: Path
    org: str = "bernardTavares"
    # NEW Phase 2 fields
    prd_file: Path | None = None  # path to PRD provided by caller
    domain: str = ""
    anthropic_api_key: str | None = None
```

- [ ] **Step 2: Update create_project to read PRD content + pass through**

In `create_project`, after the preflight, before the steps tuple, add:

```python
    # Read PRD text (Phase 2 — used by step_4 for persona LLM).
    prd_text = ""
    if config.prd_file and config.prd_file.is_file():
        prd_text = config.prd_file.read_text(encoding="utf-8")
```

Update the steps tuple to thread `domain` into step_3 and add step_4 between current steps 3 and 4 (renumbered):

```python
    steps = [
        (1, "knowledge_folders", lambda: step_1_create_kb_folders(
            slug, name, description, config.kb_dir,
            config.templates_dir, date_str,
            prd_text=prd_text)),  # PRD content baked in (replaces stub)
        (2, "kanban_bootstrap", lambda: step_2_kanban_bootstrap(slug, actor)),
        (3, "openclaw_workspace", lambda: step_3_create_workspace(
            slug, name, config.openclaw_dir,
            config.templates_dir, date_str,
            domain=config.domain)),
        (4, "persona_llm", lambda: step_4_persona_llm(
            slug=slug, name=name, domain=config.domain,
            date_str=date_str, prd_text=prd_text,
            workspace_dir=config.openclaw_dir / f"workspace-{slug}",
            api_key=config.anthropic_api_key)),
        (5, "meta_insert", lambda: step_4_meta_insert(  # function kept name
            slug, name, description,
            f"https://github.com/{config.org}/{slug}",
            config.meta_path, date_iso)),
        (6, "code_init", lambda: step_5_code_init(
            slug, name, description, config.code_dir,
            config.templates_dir, date_str, actor)),
        (7, "github_push", lambda: step_6_github_push(
            slug, config.org, config.code_dir / slug)),
    ]
```

(Step numbers in event log become 1..7. Update any test asserting `steps_completed == 6` to expect 7.)

- [ ] **Step 3: Update step_1 to write PRD content (if provided)**

In `step_1_create_kb_folders`, add a `prd_text=""` kwarg:

```python
def step_1_create_kb_folders(
    slug: str,
    name: str,
    description: str,
    kb_dir: Path,
    templates_dir: Path,
    date_str: str,
    prd_text: str = "",
) -> list[str]:
```

In the body, change PRD writing to use `prd_text` when provided:

```python
    if not prd_path.exists():
        if prd_text.strip():
            # Use real PRD content; prepend lightweight frontmatter
            prd_path.write_text(
                f"---\nproject: {slug}\ndate: {date_str}\nstatus: draft\n---\n\n"
                + prd_text
            )
        else:
            prd_path.write_text(render_template(
                prd_tmpl, name=name, description=description, date=date_str
            ))
```

- [ ] **Step 4: Run full test suite, fix any breakage**

```bash
cd ~/.openclaw/kanban-tasks
python3 -m pytest -v
```

If existing `test_create_project_*` tests assert `steps_completed == 6`, update them to `== 7`. Run again until green.

---

## Task 8: Add `--prd` flag and `regenerate-persona` subcommand to CLI

**Files:**
- Modify: `~/.openclaw/kanban-tasks/lib/api.py`

- [ ] **Step 1: Extend `cmd_project_create`**

In `api.py`, find `cmd_project_create` (around line 548). Update body:

```python
def cmd_project_create(args: argparse.Namespace) -> int:
    """Orchestrator: create project across 7 destinations (with persona LLM)."""
    from pathlib import Path
    import os
    from lib.project_factory import (
        create_project, slugify, ProjectCreateConfig,
    )
    slug = args.id or slugify(args.name)
    if not slug:
        _print({"error": "invalid_name"}, args.json,
               f"erro: nome inválido (id derivado vazio)")
        return EXIT_VALIDATION

    kb_dir = Path(os.environ.get(
        "BEVOX_KNOWLEDGE_DIR", "~/bevox-knowledge"))
    openclaw_dir = Path(os.environ.get(
        "OPENCLAW_DIR", "~/.openclaw"))
    code_dir = Path(os.environ.get(
        "BEVOX_CODE_DIR", "~/code"))
    org = os.environ.get("GITHUB_ORG", "bernardTavares")
    templates_dir = openclaw_dir / "kanban-tasks" / "templates"

    prd_file = Path(args.prd) if args.prd else None
    if prd_file and not prd_file.is_file():
        _print({"error": "prd_file_missing", "path": str(prd_file)},
               args.json, f"erro: --prd file não encontrado: {prd_file}")
        return EXIT_VALIDATION

    config = ProjectCreateConfig(
        kb_dir=kb_dir,
        openclaw_dir=openclaw_dir,
        code_dir=code_dir,
        meta_path=openclaw_dir / "projects-meta.json",
        log_path=openclaw_dir / "projects-create.jsonl",
        templates_dir=templates_dir,
        org=org,
        prd_file=prd_file,
        domain=args.domain or "",
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
    )

    result = create_project(
        name=args.name,
        slug=slug,
        description=args.description or "",
        config=config,
        actor=args.actor,
    )
    _print(result, args.json,
           f"{'ok' if result['success'] else 'failed'}: {slug}")
    return EXIT_OK if result["success"] else EXIT_RUNTIME
```

- [ ] **Step 2: Add `--prd` and `--domain` to subparser**

Find the `# project create` block (around line 1092). Add args:

```python
    pcreate.add_argument("--prd", default=None,
                         help="path to PRD .md file (used by persona LLM)")
    pcreate.add_argument("--domain", default="",
                         help="project domain (Produto, Ops, Tech, Growth, ...)")
```

- [ ] **Step 3: Add `regenerate-persona` subcommand**

Add a new function after `cmd_project_remove`:

```python
def cmd_project_regenerate_persona(args: argparse.Namespace) -> int:
    """Re-run step_4 (persona LLM) for an existing project."""
    from pathlib import Path
    import os
    from lib.project_factory import step_4_persona_llm

    openclaw_dir = Path(os.environ.get(
        "OPENCLAW_DIR", "~/.openclaw"))
    kb_dir = Path(os.environ.get(
        "BEVOX_KNOWLEDGE_DIR", "~/bevox-knowledge"))

    workspace = openclaw_dir / f"workspace-{args.id}"
    if not workspace.is_dir():
        _print({"error": "workspace_missing", "id": args.id},
               args.json, f"erro: workspace-{args.id} não existe")
        return EXIT_VALIDATION

    # Locate PRD
    prd_dir = kb_dir / "10_prd" / args.id
    prd_files = sorted(prd_dir.glob(f"*-{args.id}-prd.md")) if prd_dir.is_dir() else []
    if not prd_files:
        _print({"error": "prd_missing", "id": args.id},
               args.json, f"erro: PRD não encontrado em {prd_dir}")
        return EXIT_VALIDATION
    prd_text = prd_files[-1].read_text(encoding="utf-8")

    # Force regeneration: strip persona_status: generated marker so step_4 runs
    identity = workspace / "IDENTITY.md"
    if identity.exists() and args.force:
        text = identity.read_text(encoding="utf-8")
        text = text.replace("persona_status: generated",
                            "persona_status: pending")
        identity.write_text(text)

    import datetime as dt
    result = step_4_persona_llm(
        slug=args.id,
        name=args.name or args.id,
        domain=args.domain or "",
        date_str=dt.date.today().isoformat(),
        prd_text=prd_text,
        workspace_dir=workspace,
        api_key=os.environ.get("ANTHROPIC_API_KEY"),
    )
    _print(result, args.json,
           f"persona: {result['persona_status']}")
    return EXIT_OK if result["persona_status"] == "generated" else EXIT_RUNTIME
```

- [ ] **Step 4: Register subcommand in build_parser**

After `pcreate.set_defaults(...)` line, add:

```python
    # project regenerate-persona
    pregen = leaf(pr_sub, "regenerate-persona")
    pregen.add_argument("id", help="project id (kebab-case)")
    pregen.add_argument("--name", default=None,
                        help="display name (default: id)")
    pregen.add_argument("--domain", default="")
    pregen.add_argument("--force", action="store_true",
                        help="re-generate even if persona_status: generated")
    pregen.set_defaults(func=cmd_project_regenerate_persona)
```

- [ ] **Step 5: Smoke test the CLI**

```bash
cd ~/.openclaw/kanban-tasks
./cli.sh project regenerate-persona --help
```

Expected: argparse help output shows `--name`, `--domain`, `--force`, `id`.

---

## Task 9: Add ANTHROPIC_API_KEY preflight check

**Files:**
- Modify: `~/.openclaw/kanban-tasks/lib/project_factory.py`

- [ ] **Step 1: Add check function**

Add to `project_factory.py` (next to other `check_*` functions):

```python
def check_anthropic_api_key(prd_provided: bool) -> None:
    """Raise PreflightFailure if PRD was provided but ANTHROPIC_API_KEY missing.

    Skipped if no PRD (persona LLM will be no-op).
    """
    if not prd_provided:
        return
    if os.environ.get("OPENCLAW_PERSONA_LLM", "1") == "0":
        return
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise PreflightFailure(
            "anthropic_key_missing",
            "ANTHROPIC_API_KEY ausente no env (necessário para persona LLM); "
            "rode com OPENCLAW_PERSONA_LLM=0 para criar com stubs",
        )
```

- [ ] **Step 2: Wire into run_preflight**

In `run_preflight`, accept new param and call:

```python
def run_preflight(
    slug: str,
    org: str,
    kb_dir: Path,
    openclaw_dir: Path,
    code_dir: Path,
    projects_yml: Path,
    meta_json: Path,
    prd_provided: bool = False,
) -> None:
    if not is_valid_id(slug):
        raise PreflightFailure("invalid_id", f"id '{slug}' inválido")
    check_id_collision(slug, projects_yml, meta_json)
    check_filesystems_writable(kb_dir, openclaw_dir, code_dir)
    check_gh_auth()
    check_github_repo_free(org, slug)
    check_kb_clean_or_only_stubs(kb_dir, slug)
    check_anthropic_api_key(prd_provided)
```

In `create_project`, pass `prd_provided`:

```python
    run_preflight(
        slug=slug,
        org=config.org,
        kb_dir=config.kb_dir,
        openclaw_dir=config.openclaw_dir,
        code_dir=config.code_dir,
        projects_yml=projects_yml,
        meta_json=config.meta_path,
        prd_provided=bool(prd_text),
    )
```

- [ ] **Step 3: Add test**

```python
def test_preflight_fails_when_prd_provided_without_api_key(tmp_path, monkeypatch):
    import pytest
    from lib.project_factory import run_preflight, PreflightFailure

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # Create the dirs preflight expects so we hit the API-key check, not earlier ones
    (tmp_path / "openclaw").mkdir()
    (tmp_path / "kb").mkdir()
    (tmp_path / "code").mkdir()
    # We patch the gh checks to avoid real network calls
    from unittest.mock import patch
    with patch("lib.project_factory.check_gh_auth"), \
         patch("lib.project_factory.check_github_repo_free"), \
         patch("lib.project_factory.check_kb_clean_or_only_stubs"):
        with pytest.raises(PreflightFailure) as exc:
            run_preflight(
                slug="foo", org="bernardTavares",
                kb_dir=tmp_path / "kb",
                openclaw_dir=tmp_path / "openclaw",
                code_dir=tmp_path / "code",
                projects_yml=tmp_path / "projects.yml",
                meta_json=tmp_path / "meta.json",
                prd_provided=True,
            )
    assert exc.value.code == "anthropic_key_missing"
```

- [ ] **Step 4: Run all tests**

```bash
cd ~/.openclaw/kanban-tasks
python3 -m pytest -v
```

Expected: all green.

---

## Task 10: Smoke test — create project with real PRD via CLI

- [ ] **Step 1: Confirm ANTHROPIC_API_KEY set**

```bash
test -n "$ANTHROPIC_API_KEY" && echo "OK key present" || echo "MISSING — set it"
```

If missing, set it (do NOT commit) and continue.

- [ ] **Step 2: Write a small test PRD**

```bash
cat > /tmp/smoke-w2-p2-prd.md <<'EOF'
# PRD: Smoke W2 P2 — Test Project

## Objetivo
Validar o fluxo de geração de persona LLM no factory wave-2 phase-2.

## Stakeholders
- Bernard (founder)

## Estado atual
Apenas teste end-to-end. Nada será produzido além do workspace gerado.

## Próximos passos
- 1. Inspecionar IDENTITY.md gerada
- 2. Inspecionar SOUL.md gerada
- 3. Inspecionar memory/projects/<slug>.md gerada
- 4. Limpar via `project remove --skip-github`
EOF
```

- [ ] **Step 3: Create project with PRD**

```bash
cd ~/.openclaw/kanban-tasks
./cli.sh project create "Smoke W2 P2" \
    --id smoke-w2-p2 \
    --description "Persona LLM smoke test" \
    --domain "Tech" \
    --prd /tmp/smoke-w2-p2-prd.md \
    --json | jq
```

Expected: `success: true`, `steps_completed: 7`. Persona files written.

- [ ] **Step 4: Inspect generated persona**

```bash
cat ~/.openclaw/workspace-smoke-w2-p2/IDENTITY.md
cat ~/.openclaw/workspace-smoke-w2-p2/SOUL.md
cat ~/.openclaw/workspace-smoke-w2-p2/memory/projects/smoke-w2-p2.md
ls ~/.openclaw/workspace-smoke-w2-p2/PERSONA_PENDING.md 2>/dev/null \
    && echo "WARN: pending file exists" || echo "OK no pending"
```

Expected:
- IDENTITY.md has `persona_status: generated` in frontmatter
- SOUL.md is a coherent persona spec, in pt-BR, no "PENDING" markers
- memory/projects/smoke-w2-p2.md mentions the PRD's stated goal
- No PERSONA_PENDING.md

- [ ] **Step 5: Test fallback path (deliberate failure)**

```bash
ANTHROPIC_API_KEY="invalid-key" ./cli.sh project regenerate-persona smoke-w2-p2 --force --json | jq
```

Expected: `persona_status: pending`, error mentions auth/api. PERSONA_PENDING.md exists.

- [ ] **Step 6: Test recovery via regenerate-persona**

```bash
./cli.sh project regenerate-persona smoke-w2-p2 --force --json | jq
```

Expected: `persona_status: generated`. PERSONA_PENDING.md removed.

- [ ] **Step 7: Cleanup**

```bash
./cli.sh project remove smoke-w2-p2 --skip-github
```

---

## Task 11: Commit + open PR

- [ ] **Step 1: Stage & commit kb mirror in bevox-knowledge**

```bash
cd ~/bevox-knowledge
git add 20_architecture/openclaw/persona-extractor-prompt.md
git commit -m "docs(openclaw): mirror persona-extractor prompt for canonical reference"
git push origin main
```

- [ ] **Step 2: Stage & commit openclaw changes**

```bash
cd ~/.openclaw
git add kanban-tasks/lib/persona_extractor.py \
        kanban-tasks/lib/project_factory.py \
        kanban-tasks/lib/api.py \
        kanban-tasks/tests/test_persona_extractor.py \
        kanban-tasks/tests/test_project_factory.py \
        kanban-tasks/PROMPTS/persona-extractor.md \
        kanban-tasks/requirements.txt
git status
git commit -m "feat(project-factory): persona LLM step + regenerate-persona CLI

Phase 2 of mc-projects-factory wave-2. Adds Claude Haiku-backed
step_4_persona_llm that fills IDENTITY.md, SOUL.md, and
memory/projects/<slug>.md from the project PRD. Adds --prd and --domain
flags to project create; new project regenerate-persona subcommand.
Fallback writes PERSONA_PENDING.md with recovery instructions.

Feature flag: OPENCLAW_PERSONA_LLM (default 1)."
```

- [ ] **Step 3: Push + PR**

```bash
git push -u origin feat/mc-projects-factory-w2-phase-2-persona-llm
gh pr create --title "feat: persona LLM (Phase 2 of factory wave-2)" \
  --body "$(cat <<'EOF'
## Summary
- New `persona_extractor.py` wraps Claude Haiku 4.5 to generate IDENTITY/SOUL/project memory from PRD
- New `step_4_persona_llm` in factory; runs after workspace clone
- Fallback writes `PERSONA_PENDING.md` with recovery hint when LLM fails
- New `openclaw project create --prd <file> --domain <d>` flags
- New `openclaw project regenerate-persona <slug>` subcommand
- New preflight check for `ANTHROPIC_API_KEY` when PRD provided
- Feature flag `OPENCLAW_PERSONA_LLM` (default 1)

## Test plan
- [x] Unit tests with Anthropic mocked (extractor + step_4 + preflight)
- [x] Smoke E2E with real Anthropic call; persona generated, regenerate works, fallback marker correct

Spec: bevox-knowledge/35_specs/openclaw/2026-04-28-mc-projects-factory-wave-2-vox-clone.md
EOF
)"
```

---

## Phase 2 acceptance gate

- [ ] `persona_extractor.py` + 4 unit tests passing
- [ ] `step_4_persona_llm` added to factory + 4 unit tests passing
- [ ] `--prd`, `--domain` flags work in `project create`
- [ ] `regenerate-persona` subcommand works
- [ ] Preflight blocks creation with PRD when API key missing (unless feature-flagged off)
- [ ] Fallback writes `PERSONA_PENDING.md` with recovery command
- [ ] Smoke test green (real LLM, generated + regenerate + fallback verified)
- [ ] PR opened
