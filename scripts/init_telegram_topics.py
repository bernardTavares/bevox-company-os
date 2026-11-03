#!/usr/bin/env python3
"""init_telegram_topics — create canonical forum topics for a project's group.

Reads bot token from env (BOT_TOKEN_<UPPER_SLUG>); reads chat_id from
projects-meta.json (key: 'projects' is a list of objects with 'id'). Calls
Telegram createForumTopic API per topic; persists message_thread_id back
into the same project's telegram.topics. Idempotent.

Modes:
    --slug <slug>    : per-project mode (default; canonical 4 topics em group do projeto)
    --bot-knowledge  : skill-V2 W3.5 mode (1 topic per opted-in project em grupo bot-knowledge)

Output: JSON to stdout: {"created": [...], "existing": [...], "failed": [...]}
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
from pathlib import Path

import requests


CANONICAL_TOPICS = (
    {"name": "clarifications", "icon_color": 16478047},  # red
    {"name": "dispatcher",     "icon_color": 7322096},   # blue
    {"name": "blocks",         "icon_color": 16766590},  # yellow — UBN escalations
    {"name": "knowledge",      "icon_color": 13338843},  # purple — knowledge watcher
)

DEFAULT_META = Path(f"{Path.home()}/.openclaw/projects-meta.json")


class InitTopicsError(Exception):
    pass


def _bot_token_env_name(bot_id: str) -> str:
    """BOT_TOKEN_<UPPER_BOT_ID_WITH_UNDERSCORES> — bot tokens are env-injected
    by systemd unit files; same convention as bootstrap-telegram-agent.sh.

    bot_id is typically 'voz-<slug>'; env becomes BOT_TOKEN_VOZ_<SLUG>.
    """
    return "BOT_TOKEN_" + bot_id.upper().replace("-", "_")


def _read_meta_locked(meta_path: Path) -> dict:
    """Read meta with shared lock; release immediately. Returns parsed dict."""
    with open(meta_path, "r") as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        try:
            return json.load(f)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _find_project(meta: dict, slug: str) -> dict | None:
    """Locate project entry by slug. Returns None if not found.

    Handles both schemas defensively:
    - dict keyed by slug:  meta['projects'][slug] = {...}   (production)
    - list of objects:     meta['projects'] = [{'id': slug, ...}, ...]
    """
    projects = meta.get("projects")
    if isinstance(projects, dict):
        entry = projects.get(slug)
        return entry if isinstance(entry, dict) else None
    if isinstance(projects, list):
        for proj in projects:
            if isinstance(proj, dict) and proj.get("id") == slug:
                return proj
    return None


def _update_meta_topic(
    meta_path: Path, slug: str, topic_name: str, thread_id: int
) -> None:
    """Atomic read+modify+write under EX lock."""
    with open(meta_path, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            meta = json.load(f)
            proj = _find_project(meta, slug)
            if proj is None:
                raise InitTopicsError(
                    f"project '{slug}' disappeared from meta during update"
                )
            # Normalize: telegram may be None or missing in legacy entries
            if not isinstance(proj.get("telegram"), dict):
                proj["telegram"] = {}
            if not isinstance(proj["telegram"].get("topics"), dict):
                proj["telegram"]["topics"] = {}
            proj["telegram"]["topics"][topic_name] = thread_id
            f.seek(0)
            f.truncate()
            json.dump(meta, f, indent=2, ensure_ascii=False)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _load_bot_runtime_config(bot_id: str) -> tuple[str | None, int | None]:
    """Read ~/.openclaw-<bot_id>/openclaw.json — source of truth for bot.

    Returns (token, chat_id). Either may be None if the profile is absent or
    the field is missing. chat_id is parsed from the first key under
    channels.telegram.groups (single-group convention; bots own one group).
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
    token = tg.get("botToken")
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


def _resolve_token_and_chat_id(
    bot_id: str, meta_proj: dict
) -> tuple[str | None, int | None]:
    """Resolve (token, chat_id) with fall-back order:

    1. token: env BOT_TOKEN_<UPPER_BOT_ID> (test override / explicit env)
    2. chat_id: meta.telegram.chat_id (legacy/explicit override)
    3. fall-back: ~/.openclaw-<bot_id>/openclaw.json (production SoT)
    """
    token = os.environ.get(_bot_token_env_name(bot_id))

    telegram_block = meta_proj.get("telegram") or {}
    chat_id_raw = telegram_block.get("chat_id") if isinstance(telegram_block, dict) else None
    chat_id: int | None = None
    if chat_id_raw is not None:
        try:
            chat_id = int(chat_id_raw)
        except (ValueError, TypeError):
            chat_id = None

    if token and chat_id is not None:
        return token, chat_id

    runtime_token, runtime_chat = _load_bot_runtime_config(bot_id)
    if not token:
        token = runtime_token
    if chat_id is None:
        chat_id = runtime_chat

    return token, chat_id


def _create_topic(token: str, chat_id: int, slug: str, topic: dict) -> dict:
    """Call Telegram createForumTopic. Returns parsed JSON or raises."""
    url = f"https://api.telegram.org/bot{token}/createForumTopic"
    name = f"{slug}:{topic['name']}"
    resp = requests.post(
        url,
        json={
            "chat_id": chat_id,
            "name": name,
            "icon_color": topic["icon_color"],
        },
        timeout=15,
    )
    return resp.json()


def run(*, slug: str, meta_path: Path = DEFAULT_META) -> dict:
    if not meta_path.is_file():
        raise InitTopicsError(f"meta file missing: {meta_path}")

    meta = _read_meta_locked(meta_path)
    proj = _find_project(meta, slug)
    if proj is None:
        raise InitTopicsError(f"project '{slug}' not found in meta")

    bot_id = proj.get("bot_id") or f"voz-{slug}"
    token, chat_id = _resolve_token_and_chat_id(bot_id, proj)
    if not token:
        raise InitTopicsError(
            f"bot token missing for '{bot_id}' "
            f"(checked env {_bot_token_env_name(bot_id)} and "
            f"~/.openclaw-{bot_id}/openclaw.json)"
        )
    if chat_id is None:
        raise InitTopicsError(
            f"chat_id missing for '{slug}' "
            f"(checked meta.telegram.chat_id and "
            f"~/.openclaw-{bot_id}/openclaw.json:channels.telegram.groups). "
            f"Connect bot to a group first."
        )

    telegram_block = proj.get("telegram") or {}
    existing_topics = (
        telegram_block.get("topics", {}) if isinstance(telegram_block, dict) else {}
    ) or {}
    created, existing, failed = [], [], []

    for topic in CANONICAL_TOPICS:
        name = topic["name"]
        if name in existing_topics:
            existing.append(name)
            continue
        payload = _create_topic(token, int(chat_id), slug, topic)
        if payload.get("ok"):
            thread_id = int(payload["result"]["message_thread_id"])
            _update_meta_topic(meta_path, slug, name, thread_id)
            created.append(name)
        else:
            failed.append(
                {"topic": name, "error": payload.get("description") or "unknown"}
            )

    return {"created": created, "existing": existing, "failed": failed}


BOT_KG_COLORS = (
    16766590,  # yellow
    13338843,  # purple
    7322096,   # blue
    16478047,  # red
    9367192,   # green-ish
)


def _bot_knowledge_targets(meta: dict) -> list[dict]:
    """Generate target topics for skill-V2 W3.5 bot-knowledge mode.

    1 topic per opted-in project. Same default-opt-in semantics as
    projects_meta.is_knowledge_watcher_opted_in: opted-in if entry.knowledge_watcher
    is None OR entry.knowledge_watcher.opt_in is not False.
    Topic name = project slug; color rotates 5 cores.
    """
    projects = meta.get("projects") or {}
    targets = []
    if isinstance(projects, dict):
        items = list(projects.items())
    elif isinstance(projects, list):
        items = [(p.get("id") or p.get("slug"), p) for p in projects if isinstance(p, dict)]
    else:
        items = []
    for i, (slug, entry) in enumerate(items):
        if not slug:
            continue
        kw = entry.get("knowledge_watcher")
        if kw is None:
            opted_in = True  # default-on backwards compat
        else:
            opted_in = bool(kw.get("opt_in", True))
        if not opted_in:
            continue
        targets.append({
            "name": slug,
            "icon_color": BOT_KG_COLORS[i % len(BOT_KG_COLORS)],
        })
    return targets


def _update_bot_knowledge_topics(
    meta_path: Path, topic_name: str, thread_id: int,
) -> None:
    """Atomic update of meta.bot_knowledge.topics[name] = thread_id."""
    with open(meta_path, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            meta = json.load(f)
            bot_kg = meta.get("bot_knowledge")
            if not isinstance(bot_kg, dict):
                raise InitTopicsError("meta.bot_knowledge ausente — popule chat_id+bot_id antes")
            topics = bot_kg.setdefault("topics", {})
            topics[topic_name] = thread_id
            f.seek(0)
            f.truncate()
            json.dump(meta, f, indent=2, ensure_ascii=False)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def run_bot_knowledge(*, meta_path: Path = DEFAULT_META) -> dict:
    """W3.5 mode: cria 1 topic por opted-in slug em grupo bot-knowledge.

    Reads meta.bot_knowledge.{chat_id, bot_id, topics}; persiste thread_ids
    back into meta.bot_knowledge.topics. Idempotent (skips existing).
    """
    if not meta_path.is_file():
        raise InitTopicsError(f"meta file missing: {meta_path}")

    meta = _read_meta_locked(meta_path)
    bot_kg = meta.get("bot_knowledge")
    if not isinstance(bot_kg, dict):
        raise InitTopicsError(
            "meta.bot_knowledge ausente — adicione seção com chat_id, bot_id antes"
        )
    chat_id_raw = bot_kg.get("chat_id")
    if chat_id_raw is None:
        raise InitTopicsError("meta.bot_knowledge.chat_id ausente")
    try:
        chat_id = int(chat_id_raw)
    except (ValueError, TypeError):
        raise InitTopicsError(f"meta.bot_knowledge.chat_id inválido: {chat_id_raw!r}")

    bot_id = bot_kg.get("bot_id") or "voz-knowledge"
    token = os.environ.get(_bot_token_env_name(bot_id))
    if not token:
        raise InitTopicsError(
            f"env {_bot_token_env_name(bot_id)} ausente — popule antes de rodar"
        )

    targets = _bot_knowledge_targets(meta)
    existing_topics = bot_kg.get("topics") or {}
    created, existing, failed = [], [], []

    for topic in targets:
        name = topic["name"]
        if name in existing_topics:
            existing.append(name)
            continue
        url = f"https://api.telegram.org/bot{token}/createForumTopic"
        resp = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "name": name,
                "icon_color": topic["icon_color"],
            },
            timeout=15,
        )
        payload = resp.json()
        if payload.get("ok"):
            thread_id = int(payload["result"]["message_thread_id"])
            _update_bot_knowledge_topics(meta_path, name, thread_id)
            created.append({"name": name, "thread_id": thread_id})
        else:
            failed.append(
                {"topic": name, "error": payload.get("description") or "unknown"}
            )

    return {"created": created, "existing": existing, "failed": failed}


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--slug", help="per-project mode: create 4 canonical topics in project's group")
    g.add_argument(
        "--bot-knowledge", action="store_true", dest="bot_knowledge",
        help="skill-V2 W3.5 mode: create 1 topic per opted-in slug in bot-knowledge group",
    )
    p.add_argument("--meta", default=str(DEFAULT_META))
    args = p.parse_args(argv)
    try:
        if args.bot_knowledge:
            result = run_bot_knowledge(meta_path=Path(args.meta))
        else:
            result = run(slug=args.slug, meta_path=Path(args.meta))
    except InitTopicsError as e:
        json.dump({"error": str(e)}, sys.stdout)
        sys.stdout.write("\n")
        return 2
    json.dump(result, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
