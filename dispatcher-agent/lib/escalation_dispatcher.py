"""UBN escalation_dispatcher — cria escalation file + envia Telegram.

Spec: bevox-knowledge/35_specs/openclaw/2026-04-30-universal-block-notifier.md §4-§5
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Reuse dispatcher notifier (já em main da wave anterior)
from . import notifier as _notifier
from .block_scanner import Candidate

UBN_ESCALATIONS_DIR = Path(f"{Path.home()}/.openclaw/clarification-agent/escalations")
_TM_LIB = f"{Path.home()}/.openclaw/scripts/lib"
if _TM_LIB not in sys.path:
    sys.path.insert(0, _TM_LIB)

# Kind → canonical Telegram topic mapping (legacy per-project path)
KIND_TO_TOPIC: dict[str, str] = {
    "block": "blocks",
    "doc-gap": "knowledge",        # F1/F2/F4 — skill V2 watcher / cross-project audit
    "doc-bootstrap": "knowledge",  # F3 — skill V2 greenfield doc generator
    "retirement-flag": "knowledge",  # NEW W3.5 — F4 retirement scanner
}

KIND_TO_ENV_PREFIX: dict[str, str] = {
    "block": "OPENCLAW_BLOCKS_TELEGRAM",
    "doc-gap": "OPENCLAW_KNOWLEDGE_TELEGRAM",
    "doc-bootstrap": "OPENCLAW_KNOWLEDGE_TELEGRAM",
    "retirement-flag": "OPENCLAW_KNOWLEDGE_TELEGRAM",  # NEW W3.5
}

# Kinds that route to dedicated bot-knowledge group (W3.5)
KNOWLEDGE_KINDS = {"doc-gap", "doc-bootstrap", "retirement-flag"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def render_escalation_file(candidate: Candidate, seq: int) -> Path:
    """Cria escalation file no UBN_ESCALATIONS_DIR. dispatched_at=null no
    momento da criação (Telegram dispatch separado)."""
    UBN_ESCALATIONS_DIR.mkdir(parents=True, exist_ok=True)
    escalation_id = f"{candidate.task_id}-blk-{seq}"
    path = UBN_ESCALATIONS_DIR / f"{escalation_id}.md"
    body = f"""---
escalation_id: {escalation_id}
task_id: {candidate.task_id}
project: {candidate.project or "(unknown)"}
detector: reaper
criterion: {candidate.criterion}
block_session_key: {candidate.block_session_key or "(none)"}
block_reason: {candidate.block_reason}
detected_at: {_now_iso()}
dispatched_at: null
token_alias: null
chat_id: null
thread_id: null
telegram_message_id: null
status: open
resolved_at: null
resolved_action: null
resolved_response: null
resolved_by: null
---

# Block escalation for {candidate.task_id}

**Block reason:** {candidate.block_reason}
**Criterion:** {candidate.criterion}

## Available actions (Telegram)

Vocabulário unificado `/unblock <task> <action>`:
- `/unblock {candidate.task_id} retry` — smart retry baseado em block_reason
- `/unblock {candidate.task_id} pass [nota]` — marca cumprido manual (move pra done)
- `/unblock {candidate.task_id} cancel [motivo]` — task inviável (move pra rejected)
- `/unblock {candidate.task_id} answer <texto>` — responde clarification original (texto livre)
"""
    path.write_text(body, encoding="utf-8")
    return path


_FRONTMATTER_FIELDS_TO_UPDATE = {
    "dispatched_at", "token_alias", "chat_id", "thread_id", "telegram_message_id",
}


def _update_frontmatter(path: Path, updates: dict) -> None:
    """Re-write apenas as keys do frontmatter passadas em updates.
    Mantém body intacto."""
    content = path.read_text(encoding="utf-8")
    m = re.match(r"(---\n)(.*?)(\n---\n)", content, re.DOTALL)
    if not m:
        return
    fm_lines = m.group(2).splitlines()
    new_lines = []
    for line in fm_lines:
        if ":" in line:
            k, _, _ = line.partition(":")
            k_clean = k.strip()
            if k_clean in updates:
                new_lines.append(f"{k_clean}: {updates[k_clean]}")
                continue
        new_lines.append(line)
    new_fm = "\n".join(new_lines)
    new_content = m.group(1) + new_fm + m.group(3) + content[m.end():]
    path.write_text(new_content, encoding="utf-8")


def _resolve_bot_knowledge_target(project: Optional[str]):
    """Route to dedicated bot-knowledge group. Reads projects-meta.bot_knowledge.

    When project=None (cross-project digests from F2/F4 cron), returns target
    with thread_id=None so the message lands in the group's General topic.
    Per-project digests (F1, F4 per-project) target the project's topic.

    Returns (token, chat_id, thread_id, alias) or None. thread_id may be None
    for cross-project digests (caller should omit message_thread_id key).
    """
    meta_path = Path(
        os.environ.get(
            "OPENCLAW_PROJECTS_META",
            f"{Path.home()}/.openclaw/projects-meta.json",
        )
    )
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    bot_kg = meta.get("bot_knowledge") or {}
    chat_id = bot_kg.get("chat_id")
    bot_id = bot_kg.get("bot_id") or "voz-knowledge"
    if not chat_id:
        return None
    token_env = "BOT_TOKEN_" + bot_id.upper().replace("-", "_")
    token = os.environ.get(token_env)
    if not token:
        return None

    if not project:
        # Cross-project digest: General topic (no thread_id).
        return token, chat_id, None, "bot-knowledge:_cross"

    topics = bot_kg.get("topics") or {}
    thread_id = topics.get(project)
    if thread_id is None:
        return None
    return token, chat_id, int(thread_id), f"bot-knowledge:{project}"


def _resolve_target(project: Optional[str], kind: str = "block"):
    """Per-project topic com fallback global. Mapeia kind → canonical topic.

    W3.5: kind ∈ {doc-gap, doc-bootstrap, retirement-flag} routes to dedicated
    bot-knowledge group (1 topic per project) via projects-meta.bot_knowledge.
    Legacy fallback via env var OPENCLAW_KNOWLEDGE_DISPATCH_LEGACY=true.

    Other kinds (block, etc) preserve legacy per-project topic resolution.

    kind values:
    - "block" (default): UBN escalations → topic "blocks"
    - "doc-gap": skill V2 commit watcher → bot-knowledge group
    - "doc-bootstrap": skill V2 greenfield doc generator → bot-knowledge group
    - "retirement-flag": skill V2 retirement scanner → bot-knowledge group

    Returns (token, chat_id, thread_id, alias) or None.
    """
    legacy = os.environ.get("OPENCLAW_KNOWLEDGE_DISPATCH_LEGACY", "").lower() == "true"

    if kind in KNOWLEDGE_KINDS and not legacy:
        # New W3.5 path: bot-knowledge group
        target = _resolve_bot_knowledge_target(project)
        if target is not None:
            return target
        # Bot-knowledge config absent → fail-fast if project was given
        if project is not None:
            return None

    # Legacy / non-knowledge path (block kind always comes here)
    topic = KIND_TO_TOPIC.get(kind, "blocks")
    env_prefix = KIND_TO_ENV_PREFIX.get(kind, "OPENCLAW_BLOCKS_TELEGRAM")

    if project:
        try:
            from telegram_meta import resolve_telegram_target  # type: ignore
            target = resolve_telegram_target(project, topic)
            if target is not None:
                token, chat_id, thread_id = target
                return token, chat_id, thread_id, project
        except (ImportError, Exception):
            pass
    # Global fallback (envs)
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get(f"{env_prefix}_CHAT_ID")
    thread_id_str = os.environ.get(f"{env_prefix}_THREAD_ID")
    if not all([token, chat_id, thread_id_str]):
        return None
    try:
        return token, chat_id, int(thread_id_str), "global"
    except (TypeError, ValueError):
        return None


TESTER_RUNS_DIR = Path(f"{Path.home()}/.openclaw/tester-agent/test_runs")


def _find_latest_test_run(task_id: str) -> Optional[dict]:
    """Find most recent test_run JSON pra task. Retorna None se nenhum/parse falha."""
    if not TESTER_RUNS_DIR.is_dir():
        return None
    candidates = sorted(
        TESTER_RUNS_DIR.glob(f"{task_id}-tr-*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        return None
    try:
        return json.loads(candidates[0].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


_AC_STATUS_ICON = {
    "pass": "✅",
    "fail": "❌",
    "inconclusive": "❓",
}


def _format_test_inconclusive_details(test_run: dict) -> str:
    """Formata per-AC status + evidence pro AC inconclusive. Retorna bloco
    multi-linha pra Telegram. Limite ~1500 chars (conservador vs 4096 limit
    do Telegram)."""
    checks = test_run.get("checks") or []
    if not checks:
        return ""
    inconclusive_count = sum(
        1 for c in checks if c.get("effective_status") == "inconclusive"
    )
    total = len(checks)
    lines = [f"\nACs ({inconclusive_count}/{total} inconclusive):"]
    for i, c in enumerate(checks, 1):
        status = c.get("effective_status", "?")
        icon = _AC_STATUS_ICON.get(status, "•")
        ac_text = (c.get("ac") or "?").replace("\n", " ")
        # AC text truncated for line readability
        if len(ac_text) > 90:
            ac_text = ac_text[:87] + "..."
        lines.append(f"  {icon} AC{i} {ac_text}")
        # Inline evidence for inconclusive AC (the actionable detail)
        if status == "inconclusive":
            evidence = (c.get("evidence") or "").replace("\n", " ").strip()
            if evidence:
                if len(evidence) > 400:
                    evidence = evidence[:397] + "..."
                lines.append(f"     → {evidence}")
    return "\n".join(lines)


def _format_message(candidate: Candidate, escalation_id: str) -> str:
    is_test_inconclusive = (
        candidate.criterion == "blocked"
        and candidate.block_reason.startswith("test_inconclusive:")
    )
    test_run = (
        _find_latest_test_run(candidate.task_id) if is_test_inconclusive else None
    )
    if is_test_inconclusive and test_run:
        details = _format_test_inconclusive_details(test_run)
        run_path = (
            f"\nrun: {candidate.task_id}-tr-"
            f"{test_run.get('test_run_id', '?').rsplit('-', 1)[-1]}.json"
        )
        return (
            f"⚠️ {candidate.task_id} BLOCKED — test inconclusive\n"
            f"project: {candidate.project or '(unknown)'}"
            f"{details}\n\n"
            f"→ /unblock {candidate.task_id} pass <nota>     se revisado e ok\n"
            f"→ /unblock {candidate.task_id} retry           re-roda executor\n"
            f"→ /unblock {candidate.task_id} cancel <motivo> task inviável\n"
            f"→ /unblock {candidate.task_id} answer <texto>  responder dúvida"
            f"{run_path}\n"
            f"escalation: {escalation_id}"
        )
    return (
        f"⚠️ {candidate.task_id} blocked\n"
        f"project: {candidate.project or '(unknown)'}\n"
        f"reason: {candidate.block_reason[:200]}\n"
        f"escalation: {escalation_id}\n\n"
        f"Reply: /unblock {candidate.task_id} retry"
        f" | /unblock {candidate.task_id} pass [nota]"
        f" | /unblock {candidate.task_id} cancel [motivo]"
        f" | /unblock {candidate.task_id} answer <texto>"
    )


def dispatch_telegram(escalation_path: Path, candidate: Candidate) -> dict:
    """Envia escalation via Telegram. Atualiza frontmatter com message_id.
    Retorna {sent: bool, message_id: int|None, reason: str|None}."""
    target = _resolve_target(candidate.project)
    if target is None:
        return {"sent": False, "message_id": None, "reason": "no_telegram_target"}
    token, chat_id, thread_id, alias = target
    escalation_id = escalation_path.stem
    text = _format_message(candidate, escalation_id)
    payload = json.dumps({
        "chat_id": chat_id,
        "message_thread_id": thread_id,
        "text": text,
    }).encode("utf-8")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    ok, result = _notifier._send_http(url, payload)
    if ok:
        _update_frontmatter(escalation_path, {
            "dispatched_at": _now_iso(),
            "token_alias": alias,
            "chat_id": str(chat_id),
            "thread_id": str(thread_id),
            "telegram_message_id": str(result.get("message_id", "")),
        })
        return {"sent": True, "message_id": result.get("message_id"), "reason": None}
    return {"sent": False, "message_id": None,
            "reason": result.get("error", "unknown")}
