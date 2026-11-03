"""Shared helper: resolve Telegram routing for project notifiers.

Used by clarification-agent and dispatcher-agent notifiers (Phase 4).

Two helpers:

- resolve_thread_id(slug, topic)  → int | None
    Convenience for callers that already have token+chat_id and only need the
    per-project thread_id override.

- resolve_telegram_target(slug, topic)  → (token, chat_id, thread_id) | None
    Full resolution for callers that need to override the COMPLETE routing
    triple (used when posting to a project-owned bot/group instead of the
    legacy single-Vox bot/group). Returns None when the project either
    has no per-project topic OR is missing a runtime profile — caller
    should fall back to its env-var legacy routing in that case.

Handles both schemas defensively:
- dict keyed by slug:  meta['projects'][slug] = {...}   (production)
- list of objects:     meta['projects'] = [{'id': slug, ...}, ...]
"""
from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_META = Path(f"{Path.home()}/.openclaw/projects-meta.json")


def _find_project_entry(meta: dict, slug: str) -> dict | None:
    projects = meta.get("projects")
    if isinstance(projects, dict):
        entry = projects.get(slug)
        return entry if isinstance(entry, dict) else None
    if isinstance(projects, list):
        for proj in projects:
            if isinstance(proj, dict) and proj.get("id") == slug:
                return proj
    return None


def _load_meta(meta_path: Path) -> dict | None:
    try:
        with open(meta_path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _load_runtime_telegram(bot_id: str) -> tuple[str | None, int | None]:
    """Read ~/.openclaw-<bot_id>/openclaw.json:channels.telegram.

    Returns (token, chat_id). Either may be None on missing/invalid config.
    chat_id parsed from the first key under groups (single-group convention).
    """
    home = Path(os.environ.get("HOME", str(Path.home())))
    profile_path = home / f".openclaw-{bot_id}" / "openclaw.json"
    if not profile_path.is_file():
        return None, None
    try:
        cfg = json.loads(profile_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, None
    tg = (cfg.get("channels") or {}).get("telegram") or {}
    token = tg.get("botToken") if isinstance(tg.get("botToken"), str) else None
    chat_id: int | None = None
    groups = tg.get("groups") or {}
    if isinstance(groups, dict) and groups:
        first_key = next(iter(groups), None)
        if first_key is not None:
            try:
                chat_id = int(first_key)
            except (ValueError, TypeError):
                chat_id = None
    return token, chat_id


def resolve_thread_id(
    slug: str, topic: str, meta_path: Path = DEFAULT_META
) -> int | None:
    """Return telegram.topics[topic] for slug, or None if not configured.

    Env override: OPENCLAW_TELEGRAM_TOPICS=0 forces None (feature flag off).
    """
    if os.environ.get("OPENCLAW_TELEGRAM_TOPICS", "1") == "0":
        return None
    meta = _load_meta(meta_path)
    if meta is None:
        return None
    proj = _find_project_entry(meta, slug)
    if proj is None:
        return None
    topics = (proj.get("telegram", {}) or {}).get("topics", {}) or {}
    val = topics.get(topic)
    return int(val) if val else None


def resolve_telegram_target(
    slug: str, topic: str, meta_path: Path = DEFAULT_META
) -> tuple[str, int, int] | None:
    """Return (token, chat_id, thread_id) for posting to <slug>:<topic> via the
    project's own bot/group. Returns None when any piece is missing — caller
    should fall back to its legacy env-var routing.

    Resolution chain (in order):
    1. OPENCLAW_TELEGRAM_TOPICS=0 → None (feature flag off)
    2. meta.projects[slug].bot_id present?
    3. meta.projects[slug].telegram.topics[topic] present?
    4. ~/.openclaw-<bot_id>/openclaw.json has botToken + groups[<chat_id>]?

    All must be present, else returns None. This guarantees the triple is
    coherent (same bot owns same group with same thread).
    """
    if os.environ.get("OPENCLAW_TELEGRAM_TOPICS", "1") == "0":
        return None

    meta = _load_meta(meta_path)
    if meta is None:
        return None
    proj = _find_project_entry(meta, slug)
    if proj is None:
        return None

    bot_id = proj.get("bot_id")
    if not bot_id or not isinstance(bot_id, str):
        return None

    topics = (proj.get("telegram") or {}).get("topics") or {}
    thread_raw = topics.get(topic)
    if thread_raw is None:
        return None
    try:
        thread_id = int(thread_raw)
    except (ValueError, TypeError):
        return None

    token, chat_id = _load_runtime_telegram(bot_id)
    if not token or chat_id is None:
        return None

    return token, chat_id, thread_id
