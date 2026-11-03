"""LLM-driven persona extractor via `claude` CLI subprocess.

Calls Claude Haiku 4.5 through the local `claude` CLI (which uses
claude.ai subscription auth — same pattern as tester-agent). Produces
IDENTITY.md, SOUL.md, and memory/projects/<slug>.md content. Validates
output structure; on any failure returns a status describing why so the
caller can fall back gracefully.

Spec: bevox-knowledge/35_specs/openclaw/2026-04-28-mc-projects-factory-wave-2-vox-clone.md §3.1 (T+5s)
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Dict


REQUIRED_KEYS = ("identity", "soul", "memory_projects")
# Matches a fenced block like ```json\n...\n``` or ```\n...\n```. Used to
# unwrap LLM output when it ignores "no prose around the JSON" and emits a
# code fence anyway (very common Claude behavior).
_FENCE_RE = re.compile(
    r"^\s*```(?:json|JSON)?\s*\n(.*?)\n```\s*$",
    re.DOTALL,
)


def _strip_code_fence(raw: str) -> str:
    """Remove leading/trailing markdown code fence if present.

    Claude often wraps JSON output in ```json ... ``` despite instructions
    to the contrary. This is a defensive unwrap. Returns raw unchanged if
    no fence is found.
    """
    m = _FENCE_RE.match(raw)
    if m:
        return m.group(1).strip()
    return raw
PROMPT_PATH = Path(__file__).parent.parent / "PROMPTS" / "persona-extractor.md"
DEFAULT_MODEL = "claude-haiku-4-5"


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
    timeout_s: int = 300,
    model: str = DEFAULT_MODEL,
) -> Dict[str, Any]:
    """Generate persona files from PRD via `claude -p` subprocess.

    Returns dict with:
      - status: "generated" | "invalid" | "error"
      - identity, soul, memory_projects: str (only when status == "generated")
      - error: str (when status != "generated")
    """
    prompt = _render_prompt(
        slug=slug,
        project_display_name=project_display_name,
        domain=domain,
        date_str=date_str,
        prd_text=prd_text,
    )

    cmd = ["claude", "-p", "--model", model]

    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": f"timeout after {timeout_s}s"}
    except FileNotFoundError as e:
        return {"status": "error", "error": f"claude CLI not found: {e}"}
    except Exception as e:
        return {"status": "error", "error": f"subprocess: {e}"}

    if result.returncode != 0:
        return {
            "status": "error",
            "error": (result.stderr or result.stdout or "").strip()
                     or f"non-zero exit {result.returncode}",
        }

    raw = (result.stdout or "").strip()
    unwrapped = _strip_code_fence(raw)

    try:
        payload = json.loads(unwrapped)
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
