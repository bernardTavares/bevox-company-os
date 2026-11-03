"""Shared Telegram dispatch helper for knowledge watcher (F1/F2/F4).

Used by F1 commit-watcher digest, F2 gap-report cron digest, F4 retirement
scan cron digest. Routes via escalation_dispatcher kind=doc-gap → bot-knowledge
profile → topic (per-project or General when slug=None for cross-project).

Best-effort: never raises. Returns True iff sendMessage HTTP succeeded.

Implementation note: `dispatcher-agent/lib/` shares the package name `lib` with
`kanban-tasks/lib`, so plain `import lib.escalation_dispatcher` would resolve
to the kanban-tasks package. We use importlib to load by absolute file path.
"""
from __future__ import annotations

import importlib.util
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional


_DISPATCHER_LIB = Path(f"{Path.home()}/.openclaw/dispatcher-agent/lib")
_RESOLVE_TARGET_FN = None  # cached after first import


def _load_resolve_target():
    """Load `_resolve_target` from dispatcher-agent under an aliased package
    name to avoid colliding with kanban-tasks `lib`. Caches the function on
    first successful load.
    """
    global _RESOLVE_TARGET_FN
    if _RESOLVE_TARGET_FN is not None:
        return _RESOLVE_TARGET_FN
    if not (_DISPATCHER_LIB / "escalation_dispatcher.py").exists():
        return None
    import sys as _sys
    pkg_alias = "oc_dispatcher_lib"
    if pkg_alias not in _sys.modules:
        spec = importlib.util.spec_from_file_location(
            pkg_alias,
            str(_DISPATCHER_LIB / "__init__.py"),
            submodule_search_locations=[str(_DISPATCHER_LIB)],
        )
        if spec is None or spec.loader is None:
            return None
        pkg = importlib.util.module_from_spec(spec)
        _sys.modules[pkg_alias] = pkg
        try:
            spec.loader.exec_module(pkg)
        except Exception:
            _sys.modules.pop(pkg_alias, None)
            return None
    try:
        mod = importlib.import_module(f"{pkg_alias}.escalation_dispatcher")
    except Exception:
        return None
    _RESOLVE_TARGET_FN = getattr(mod, "_resolve_target", None)
    return _RESOLVE_TARGET_FN


def _send_one(token: str, chat_id, thread_id, text: str) -> bool:
    payload_obj = {"chat_id": chat_id, "text": text}
    if thread_id is not None:
        payload_obj["message_thread_id"] = thread_id
    payload = json.dumps(payload_obj).encode("utf-8")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError):
        return False
    except Exception:
        return False


def _chunk_text(text: str, max_chars: int) -> list[str]:
    """Split text into <=max_chars chunks at line boundaries.

    Falls back to hard slice when a single line exceeds max_chars.
    """
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in text.split("\n"):
        line_len = len(line) + 1  # +1 for '\n'
        if line_len > max_chars:
            if current:
                chunks.append("\n".join(current))
                current, current_len = [], 0
            for i in range(0, len(line), max_chars):
                chunks.append(line[i:i + max_chars])
            continue
        if current_len + line_len > max_chars:
            chunks.append("\n".join(current))
            current, current_len = [line], line_len
        else:
            current.append(line)
            current_len += line_len
    if current:
        chunks.append("\n".join(current))
    return chunks


# Telegram per-message hard limit is 4096; leave headroom for chunk header.
_TELEGRAM_CHUNK_CHARS = 3800


def dispatch_to_telegram(slug: Optional[str], text: str) -> bool:
    """Send text to Telegram via escalation_dispatcher kind=doc-gap.

    Splits messages exceeding ~3800 chars into multiple chunks with `[n/N]`
    headers, preserving line boundaries. `slug` is the project id for
    per-project digests; pass None for cross-project (lands in General topic).

    Returns True iff EVERY chunk send succeeded. Failures are swallowed.
    """
    resolve = _load_resolve_target()
    if resolve is None:
        return False

    target = resolve(slug, kind="doc-gap")
    if target is None:
        return False
    token, chat_id, thread_id, _alias = target

    chunks = _chunk_text(text, _TELEGRAM_CHUNK_CHARS)
    total = len(chunks)
    all_ok = True
    for idx, chunk in enumerate(chunks, start=1):
        if total > 1:
            header = f"[{idx}/{total}]\n"
            body = header + chunk
        else:
            body = chunk
        ok = _send_one(token, chat_id, thread_id, body)
        if not ok:
            all_ok = False
    return all_ok
