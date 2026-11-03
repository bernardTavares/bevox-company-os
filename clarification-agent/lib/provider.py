"""Provider abstraction: ollama local + claude CLI cloud.

Padrão: receber prompt + model + timeout + provider name; retornar
dict com parsed JSON, raw, latency_ms, provider_used, error.

Zero pip install (stdlib apenas: subprocess, json, re, time).
"""
import json
import re
import subprocess
import time
from typing import Any, Dict, Optional


OLLAMA_BIN = "ollama"
CLAUDE_BIN = "claude"


def _extract_json(raw: str) -> Optional[Dict[str, Any]]:
    """Extrai bloco JSON do output; tolera ```json``` wrapping."""
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if m:
        block = m.group(1)
    else:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        block = raw[start:end + 1]
    try:
        parsed = json.loads(block)
    except json.JSONDecodeError:
        return None
    for field in ("answer", "sources", "confidence"):
        if field not in parsed:
            return None
    if not isinstance(parsed["sources"], list):
        parsed["sources"] = [str(parsed["sources"])]
    parsed.setdefault("escalation_reason", "")
    return parsed


def _run_ollama(prompt: str, model: str, timeout: int) -> (str, int):
    t0 = time.monotonic()
    r = subprocess.run(
        [OLLAMA_BIN, "run", model],
        input=prompt, capture_output=True, text=True,
        check=False, timeout=timeout,
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    if r.returncode != 0:
        raise RuntimeError(f"ollama exit={r.returncode} stderr={r.stderr[:200]}")
    return r.stdout, latency_ms


def _run_claude_cli(prompt: str, model: str, timeout: int) -> (str, int):
    t0 = time.monotonic()
    r = subprocess.run(
        [CLAUDE_BIN, "-p", prompt, "--model", model, "--allowedTools", ""],
        capture_output=True, text=True, check=False, timeout=timeout,
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    if r.returncode != 0:
        raise RuntimeError(f"claude exit={r.returncode} stderr={r.stderr[:200]}")
    return r.stdout, latency_ms


def run(
    *, prompt: str, model: str, timeout: int, provider: str,
) -> Dict[str, Any]:
    """Retorna: {raw, parsed (dict|None), latency_ms, provider_used, error (str|None)}."""
    assert provider in ("ollama", "claude_cli"), f"unknown provider: {provider}"
    runner = _run_ollama if provider == "ollama" else _run_claude_cli
    try:
        raw, latency_ms = runner(prompt, model, timeout)
    except subprocess.TimeoutExpired:
        return {"raw": "", "parsed": None, "latency_ms": timeout * 1000,
                "provider_used": provider, "error": "timeout"}
    except TimeoutError:  # for test mocking
        return {"raw": "", "parsed": None, "latency_ms": timeout * 1000,
                "provider_used": provider, "error": "timeout"}
    except Exception as e:
        return {"raw": "", "parsed": None, "latency_ms": 0,
                "provider_used": provider, "error": f"subprocess_error:{e}"}
    parsed = _extract_json(raw)
    if parsed is None:
        return {"raw": raw[:2000], "parsed": None, "latency_ms": latency_ms,
                "provider_used": provider, "error": "parse_failed"}
    return {"raw": raw[:2000], "parsed": parsed, "latency_ms": latency_ms,
            "provider_used": provider, "error": None}
