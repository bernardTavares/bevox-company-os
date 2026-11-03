#!/usr/bin/env python3
"""
E8 wave 3 — Health alert notifier.

Reads state.json (produced by the E8 health runner), detects
transitions in overall.level, sends Telegram messages via Bot API.
Recovery message when restored to ok. Heartbeat (alert-state.json
mtime) updated on every execution regardless of transition.

Separate from the health runner — 1 timer = 1 responsibility.
If this notifier fails, health checking continues unaffected.

Spec: bevox-knowledge/35_specs/2026-04-16-e8-health-alerts-wave-3.md
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


HOME = Path(os.environ.get("HOME", f"{Path.home()}"))
DEFAULT_HEALTH_STATE = HOME / ".openclaw" / "health" / "state.json"
DEFAULT_ALERT_STATE = HOME / ".openclaw" / "health" / "alert-state.json"
DEFAULT_HARDENING_STATE = HOME / ".openclaw" / "hardening" / "state.json"


def load_health_state(path: Path) -> Optional[dict]:
    """Read state.json from health runner. Returns None on error."""
    if not path.exists():
        print(f"WARNING: health state not found: {path}", file=sys.stderr)
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"WARNING: failed to read health state: {e}", file=sys.stderr)
        return None


def load_alert_state(path: Path) -> dict:
    """Read alert-state.json, or return default for first run."""
    if not path.exists():
        return {"last_level": None, "last_checked_at": None}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"last_level": None, "last_checked_at": None}


def detect_transition(
    previous_level: Optional[str],
    current_level: str,
    silent_first_run: bool = False,
) -> Optional[str]:
    """Detect state transition. Returns 'alert', 'recovery', or None.

    First run (previous=None): alert if current != ok, else None.
    If silent_first_run=True (E8/F5 hardening per spec §5.7), suppress
    first-run alert to avoid deploy noise.
    """
    if previous_level is None:
        if silent_first_run:
            return None
        return "alert" if current_level != "ok" else None
    if current_level == previous_level:
        return None
    if current_level == "ok":
        return "recovery"
    return "alert"


def format_message(
    transition: str,
    state: dict,
    prefix: Optional[str] = None,
) -> str:
    """Format Telegram message with level, counts, affected entries.

    Works for both health (services) and hardening (items) states by
    auto-detecting the shape. If `prefix` is provided (e.g. "[hardening]"),
    it is prepended to the message.
    """
    overall = state.get("overall", {})
    level = overall.get("level", "unknown")
    timestamp = state.get("generated_at", datetime.now(timezone.utc).isoformat())

    # Detect shape: hardening uses "items"+"items_*"; health uses "services"+"services_*"
    is_hardening = "items" in state and isinstance(state.get("items"), list)
    if is_hardening:
        ok = overall.get("items_ok", 0)
        total = overall.get("items_total", 0)
        items = state.get("items", [])
        affected = [
            it.get("id", "?") for it in items
            if it.get("status") not in ("ok", "not_applicable")
        ]
        kind = "Hardening"
        unit = "ok"
    else:
        ok = overall.get("services_up", 0)
        total = overall.get("services_total", 0)
        services = state.get("services", {})
        affected = [
            sid for sid, svc in services.items()
            if svc.get("status") != "up"
        ]
        kind = "Health"
        unit = "up"

    pfx = f"{prefix} " if prefix else ""

    if transition == "recovery":
        return f"{pfx}✓ {kind} restored ({ok}/{total} {unit})\nTimestamp: {timestamp}"

    if len(affected) > 5:
        shown = ", ".join(affected[:5])
        affected_str = f"{shown} +{len(affected) - 5} more"
    else:
        affected_str = ", ".join(affected) if affected else "unknown"

    return (
        f"{pfx}⚠ {kind} {level} ({ok}/{total} {unit}): {affected_str}\n"
        f"Timestamp: {timestamp}"
    )


def send_telegram(token: str, chat_id: str, message: str) -> bool:
    """Send message via Telegram Bot API. Returns True on success."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({
        "chat_id": chat_id,
        "text": message,
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read())
        if result.get("ok"):
            return True
        print(f"WARNING: Telegram API returned ok=false: {result}", file=sys.stderr)
        return False
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        print(f"WARNING: Telegram send failed: {e}", file=sys.stderr)
        return False


def write_alert_state(
    path: Path,
    current_level: str,
    sent: bool,
    transition: Optional[str],
    message: Optional[str],
    current_hardening_level: Optional[str] = None,
) -> None:
    """Write alert-state.json atomically. Updated EVERY execution (heartbeat).

    Preserves any pre-existing `last_hardening_level` if not provided
    (back-compat with legacy schema before E8/F5).
    """
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    existing = load_alert_state(path)

    state = {
        "last_checked_at": now_iso,
        "last_level": current_level,
        "last_alerted_at": now_iso if sent else existing.get("last_alerted_at"),
        "last_alert_type": transition if sent else existing.get("last_alert_type"),
        "last_message": message if sent else existing.get("last_message"),
        "last_hardening_level": (
            current_hardening_level if current_hardening_level is not None
            else existing.get("last_hardening_level")
        ),
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def run_check(
    health_state_path: Path = DEFAULT_HEALTH_STATE,
    alert_state_path: Path = DEFAULT_ALERT_STATE,
    hardening_state_path: Path = DEFAULT_HARDENING_STATE,
) -> dict:
    """Execute one check cycle for both health AND hardening. Returns summary.

    Hardening uses silent_first_run=True (E8/F5 spec §5.7) and prepends
    [hardening] prefix to messages. Hardening missing → continue with health.
    Reads/writes last_hardening_level in alert-state.json (default null).
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    no_credentials = not token or not chat_id

    health = load_health_state(health_state_path)
    if health is None:
        # Can't evaluate health — write heartbeat (preserve hardening level) and bail
        write_alert_state(alert_state_path, "unknown", False, None, None)
        return {"action": "skip", "reason": "health_state_unavailable"}

    current_level = health.get("overall", {}).get("level", "unknown")
    alert_state = load_alert_state(alert_state_path)
    previous_level = alert_state.get("last_level")

    transition = detect_transition(previous_level, current_level)

    sent = False
    message = None
    send_failed = False

    if transition:
        message = format_message(transition, health)
        if no_credentials:
            print(
                f"WARNING: transition detected ({previous_level} → {current_level}) "
                f"but TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID not set — skipping send",
                file=sys.stderr,
            )
        else:
            sent = send_telegram(token, chat_id, message)
            if sent:
                print(f"Sent {transition}: {previous_level} → {current_level}")
            else:
                send_failed = True
                print(
                    f"WARNING: failed to send {transition} "
                    f"({previous_level} → {current_level}), will retry next cycle",
                    file=sys.stderr,
                )

    # ── Hardening (E8/F5) ──────────────────────────────────────────
    hardening_level_to_store = alert_state.get("last_hardening_level")  # default: preserve
    hardening_action = "none"
    if hardening_state_path.exists():
        hardening = load_health_state(hardening_state_path)  # same json shape loader
        if hardening is not None:
            h_current = hardening.get("overall", {}).get("level", "unknown")
            h_previous = alert_state.get("last_hardening_level")
            h_transition = detect_transition(h_previous, h_current,
                                              silent_first_run=True)
            h_send_failed = False
            if h_transition:
                h_msg = format_message(h_transition, hardening, prefix="[hardening]")
                if no_credentials:
                    print(
                        f"WARNING: hardening transition ({h_previous} → {h_current}) "
                        f"but credentials not set — skipping send",
                        file=sys.stderr,
                    )
                else:
                    h_sent = send_telegram(token, chat_id, h_msg)
                    if h_sent:
                        print(f"Sent [hardening] {h_transition}: {h_previous} → {h_current}")
                        hardening_action = h_transition
                    else:
                        h_send_failed = True
                        print(
                            f"WARNING: failed to send hardening {h_transition}, "
                            f"will retry next cycle",
                            file=sys.stderr,
                        )
            # Always advance hardening level pointer when first-run-silent OR
            # when transition succeeded; on send failure preserve previous.
            if not h_send_failed:
                hardening_level_to_store = h_current

    # Write heartbeat (always)
    level_to_store = current_level if not send_failed else previous_level
    write_alert_state(
        alert_state_path,
        level_to_store,
        sent,
        transition if sent else None,
        message if sent else None,
        current_hardening_level=hardening_level_to_store,
    )

    return {
        "action": transition or "none",
        "previous_level": previous_level,
        "current_level": current_level,
        "sent": sent,
        "message": message,
        "hardening_action": hardening_action,
        "hardening_level": hardening_level_to_store,
    }


def show_status(alert_state_path: Path = DEFAULT_ALERT_STATE) -> None:
    """Print current alert state."""
    state = load_alert_state(alert_state_path)
    print(json.dumps(state, indent=2, ensure_ascii=False))


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="E8 wave 3 health alert notifier")
    parser.add_argument("--check", action="store_true", help="Run one check cycle")
    parser.add_argument("--status", action="store_true", help="Show alert state")
    parser.add_argument("--health-state", type=str, default=None,
                        help="Override health state.json path (for testing)")
    parser.add_argument("--alert-state", type=str, default=None,
                        help="Override alert-state.json path (for testing)")
    args = parser.parse_args(argv)

    health_path = Path(args.health_state) if args.health_state else DEFAULT_HEALTH_STATE
    alert_path = Path(args.alert_state) if args.alert_state else DEFAULT_ALERT_STATE

    if not (args.check or args.status):
        parser.print_help()
        return 0

    if args.status:
        show_status(alert_path)
        return 0

    if args.check:
        try:
            result = run_check(health_path, alert_path)
            if result.get("action") == "skip":
                print(f"Skipped: {result.get('reason')}")
        except Exception as e:
            print(f"FATAL (caught): {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
