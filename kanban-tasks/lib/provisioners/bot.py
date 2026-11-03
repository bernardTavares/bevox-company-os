"""provision_bot — wraps scripts/bootstrap-telegram-agent.sh.

Per ADR-014 §Amendment 4 the bot is openclaw-side (not skill-side); this
provisioner shells out to the existing bash bootstrapper in
`--non-interactive --json` mode. Reuses profile cleanup pattern of PR #21
implicitly (bash idempotência: re-run safe).

Detect (capability_detect.detect_bot) drives whether we run at all. The
caller (cmd_project_adopt) only invokes when state in (absent, partial,
drifted) AND user opted-in via --bot=yes / interactive prompt.

Failure modes:
- bootstrap script not found → BotResult(state=absent, error=...).
- script exit non-zero → BotResult(state=partial, error=stderr).
- non-interactive mode with missing token/chat-id → caller responsibility.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class BotResult:
    state: str  # provisioned | partial | absent
    bot_id: Optional[str] = None
    bot_port: Optional[int] = None
    profile_dir: Optional[str] = None
    error: Optional[str] = None
    stdout: Optional[str] = None


def provision_bot(
    slug: str,
    *,
    openclaw_dir: Path,
    bot_id: Optional[str] = None,
    bot_port: Optional[int] = None,
    token: Optional[str] = None,
    chat_id: Optional[str] = None,
    allow_from: Optional[str] = None,
    skills: Optional[str] = None,
    project_slug: Optional[str] = None,
    dry_run: bool = False,
    timeout: int = 60,
) -> BotResult:
    """Bootstrap a Telegram bot profile + systemd unit for slug.

    Args:
        slug: project id (used as bot area unless bot_id passed).
        openclaw_dir: ~/.openclaw root (locates bootstrap script).
        bot_id: explicit bot area name; defaults to slug.
        bot_port: gateway port (int); required for bootstrap.
        token, chat_id, allow_from: required for non-interactive mode.
        skills: comma-separated skill list (defaults inside script).
        project_slug: optional --project-slug arg for the bash script.
        dry_run: if True, pass --dry-run to the script.
        timeout: subprocess timeout seconds.

    Returns:
        BotResult.
    """
    script = openclaw_dir / "scripts" / "bootstrap-telegram-agent.sh"
    if not script.is_file():
        return BotResult(
            state="absent",
            error=f"bootstrap-telegram-agent.sh not found at {script}",
        )

    area = bot_id or slug
    if not bot_port:
        return BotResult(
            state="absent",
            bot_id=area,
            error="bot_port is required for provision_bot",
        )
    if not (token and chat_id and allow_from):
        return BotResult(
            state="absent",
            bot_id=area,
            error="provision_bot requires token + chat_id + allow_from",
        )

    cmd = [
        "bash", str(script),
        "--token", token,
        "--chat-id", str(chat_id),
        "--allow-from", allow_from,
        "--non-interactive",
        "--json",
    ]
    if skills:
        cmd.extend(["--skills", skills])
    if project_slug:
        cmd.extend(["--project-slug", project_slug])
    if dry_run:
        cmd.append("--dry-run")
    cmd.extend([area, str(bot_port)])

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
    except FileNotFoundError as e:
        return BotResult(
            state="absent",
            bot_id=area,
            error=f"bash not found: {e}",
        )
    except subprocess.TimeoutExpired:
        return BotResult(
            state="partial",
            bot_id=area,
            error=f"bootstrap timed out after {timeout}s",
        )

    profile_dir = str(Path.home() / f".openclaw-{area}")

    if result.returncode != 0:
        return BotResult(
            state="partial",
            bot_id=area,
            bot_port=bot_port,
            profile_dir=profile_dir,
            error=(result.stderr or "").strip()
                  or f"bootstrap exit {result.returncode}",
            stdout=(result.stdout or "").strip(),
        )

    return BotResult(
        state="provisioned",
        bot_id=area,
        bot_port=bot_port,
        profile_dir=profile_dir,
        stdout=(result.stdout or "").strip(),
    )
