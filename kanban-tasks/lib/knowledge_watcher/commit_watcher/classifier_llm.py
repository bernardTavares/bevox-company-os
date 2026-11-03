"""classifier_llm.py — Layer 2 Haiku LLM classifier with monthly budget cap."""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from lib.knowledge_watcher.commit_watcher import (
    ClassifierLayer, ClassifierResult, Commit, DocType,
)
from lib.knowledge_watcher.state import read_state, write_state

_HAIKU_INPUT_USD_PER_M = 1.0
_HAIKU_OUTPUT_USD_PER_M = 5.0
_HAIKU_MODEL = "claude-haiku-4-5-20251001"
_SUBPROCESS_TIMEOUT_S = 120


class LLMBudgetExceeded(Exception):
    pass


def build_prompt(commit: Commit) -> str:
    files_listing = "\n".join(f"- {f}" for f in commit.files_changed[:30])
    return f"""Classify this git commit by which canonical doc-type a Bevox project should likely create or update for it. Output JSON only.

Subject: {commit.subject}
Files changed:
{files_listing}

Diffstat (truncated):
{commit.diffstat[:1500]}

Rules:
- "release-note" if release/tag commit
- "spec" if new feature/service introducing new behavior
- "adr" if architectural decision (schema, auth, integration choice)
- "architecture" if cross-module refactor changing system shape
- "prd" if user-facing product change introducing new product capability
- "roadmap" if multi-week milestone or platform shift
- "none" if nothing doc-worthy (tests-only, CI, dependency bump, typo)

Output JSON: {{"doc_type": "<one of above>", "confidence": <0.0-1.0>, "rationale": "<≤200 chars>"}}
"""


def _check_budget(state_path: Path, budget_usd: float) -> bool:
    state = read_state(state_path)
    usage = state.get("llm_usage_month", {})
    now_month = datetime.now(timezone.utc).strftime("%Y-%m")
    if usage.get("month") != now_month:
        return True
    return usage.get("spent_usd", 0.0) < budget_usd


def _record_usage(state_path: Path, input_tokens: int, output_tokens: int) -> None:
    state = read_state(state_path)
    now_month = datetime.now(timezone.utc).strftime("%Y-%m")
    usage = state.get("llm_usage_month", {})
    if usage.get("month") != now_month:
        usage = {"month": now_month, "spent_usd": 0.0, "calls": 0}
    cost = (input_tokens / 1_000_000 * _HAIKU_INPUT_USD_PER_M
            + output_tokens / 1_000_000 * _HAIKU_OUTPUT_USD_PER_M)
    usage["spent_usd"] = round(usage.get("spent_usd", 0.0) + cost, 6)
    usage["calls"] = usage.get("calls", 0) + 1
    state["llm_usage_month"] = usage
    write_state(state_path, state)


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _call_haiku_via_subprocess(prompt: str):
    """Call Haiku via `claude -p` subprocess (uses Claude CLI OAuth/keychain).

    Returns SimpleNamespace mimicking anthropic Message shape: .content[0].text,
    .usage.input_tokens, .usage.output_tokens. Raises RuntimeError on failure
    with diagnostic detail (exit code, stderr excerpt).
    """
    cmd = ["claude", "-p", "--model", _HAIKU_MODEL]
    try:
        result = subprocess.run(
            cmd, input=prompt, capture_output=True, text=True,
            timeout=_SUBPROCESS_TIMEOUT_S,
        )
    except FileNotFoundError as e:
        raise RuntimeError(f"claude CLI not in PATH: {e}") from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"claude -p timeout after {_SUBPROCESS_TIMEOUT_S}s") from e
    if result.returncode != 0:
        stderr_excerpt = (result.stderr or "").strip()[:200]
        raise RuntimeError(f"claude -p exit={result.returncode}: {stderr_excerpt}")
    text = (result.stdout or "").strip()
    if not text:
        raise RuntimeError("claude -p returned empty stdout")
    return SimpleNamespace(
        content=[SimpleNamespace(text=text)],
        usage=SimpleNamespace(
            input_tokens=_estimate_tokens(prompt),
            output_tokens=_estimate_tokens(text),
        ),
    )


def _call_haiku_via_sdk(prompt: str, *, max_tokens: int):
    import anthropic
    client = anthropic.Anthropic()
    return client.messages.create(
        model=_HAIKU_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )


def _call_haiku(prompt: str, *, max_tokens: int = 2000):
    """Real LLM call. Default uses `claude -p` subprocess (Claude CLI OAuth);
    if ANTHROPIC_API_KEY is set in env, uses anthropic SDK directly (faster).

    Mocked in tests.
    """
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _call_haiku_via_sdk(prompt, max_tokens=max_tokens)
    return _call_haiku_via_subprocess(prompt)


def classify_llm(
    commit: Commit, *, state_path: Path, budget_usd: float = 5.0,
) -> ClassifierResult:
    if not _check_budget(state_path, budget_usd):
        return ClassifierResult(
            doc_type=DocType.NONE, confidence=0.30,
            rationale="LLM budget exceeded for month, fallback heuristic",
            source=ClassifierLayer.LLM,
        )

    prompt = build_prompt(commit)
    try:
        resp = _call_haiku(prompt, max_tokens=300)
        text = resp.content[0].text.strip()
        _record_usage(state_path, resp.usage.input_tokens, resp.usage.output_tokens)
    except Exception as e:
        return ClassifierResult(
            doc_type=DocType.NONE, confidence=0.20,
            rationale=f"LLM call failed: {type(e).__name__}: {str(e)[:150]}",
            source=ClassifierLayer.LLM,
        )

    try:
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text)
        dt = DocType(data["doc_type"])
        conf = float(data["confidence"])
        rat = str(data.get("rationale", ""))[:200]
        return ClassifierResult(
            doc_type=dt, confidence=conf, rationale=rat,
            source=ClassifierLayer.LLM,
        )
    except (json.JSONDecodeError, KeyError, ValueError):
        return ClassifierResult(
            doc_type=DocType.NONE, confidence=0.30,
            rationale="LLM returned invalid JSON",
            source=ClassifierLayer.LLM,
        )
