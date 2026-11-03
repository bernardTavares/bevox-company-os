#!/usr/bin/env python3
"""
E8 wave 1 — Health runner.

Reads ~/bevox-knowledge/20_architecture/health-registry.yml, runs each
check, writes ~/.openclaw/health/state.json atomically.

Single-file runner. Uses stdlib + pyyaml.
Runs via systemd timer (2min cadence) or `openclaw-health-check --scan`.

Spec: bevox-knowledge/35_specs/2026-04-14-e8-infra-health-backup-wave-1.md
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml not installed. Run Task 0d first to create venv.", file=sys.stderr)
    sys.exit(2)


# ── Paths ──────────────────────────────────────────────────────────

HOME = Path.home()
HEALTH_DIR = HOME / ".openclaw" / "health"
STATE_PATH = HEALTH_DIR / "state.json"
REGISTRY_PATH = HOME / "bevox-knowledge" / "20_architecture" / "health-registry.yml"

VERSION = "0.1.0-wave1"

log = logging.getLogger("health-runner")


# ── Constants ──────────────────────────────────────────────────────

SYSTEMCTL_TIMEOUT_SEC = 2
DEFAULT_HTTP_TIMEOUT_SEC = 5
DEFAULT_ACCEPT_STATUS = [200]
ALLOWED_CHECK_TYPES = {"systemd_active", "http_url", "file_freshness"}


# ── Registry loading + schema validation ─────────────────────────


class RegistryError(Exception):
    """Raised when registry load or schema validation fails."""


def load_registry(path: Path) -> dict:
    """Load and validate health-registry.yml.

    Returns the parsed dict.
    Raises RegistryError on any parse or schema failure.
    """
    import re

    if not path.exists():
        raise RegistryError(f"registry file not found: {path}")

    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise RegistryError(f"malformed YAML: {e}")
    except OSError as e:
        raise RegistryError(f"cannot read registry: {e}")

    if not isinstance(data, dict):
        raise RegistryError("registry must be a dict at top level")
    if data.get("version") != 1:
        raise RegistryError(f"version must be 1, got {data.get('version')!r}")

    services = data.get("services")
    if not isinstance(services, dict):
        raise RegistryError("services must be a dict")
    if len(services) == 0:
        raise RegistryError("services dict must not be empty")

    epic_re = re.compile(r"^E[0-9]+(\.[0-9]+)?$")
    since_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    required_fields = ("name", "owner", "epic", "critical", "check", "since")

    for sid, sdef in services.items():
        if not isinstance(sdef, dict):
            raise RegistryError(f"service {sid!r}: must be dict")
        for field in required_fields:
            if field not in sdef:
                raise RegistryError(f"service {sid!r}: missing required field {field!r}")
        if not isinstance(sdef["name"], str) or not sdef["name"].strip():
            raise RegistryError(f"service {sid!r}: name must be non-empty string")
        if not isinstance(sdef["owner"], str) or not sdef["owner"].strip():
            raise RegistryError(f"service {sid!r}: owner must be non-empty string")
        if not isinstance(sdef["critical"], bool):
            raise RegistryError(f"service {sid!r}: critical must be bool")
        if not epic_re.match(str(sdef["epic"])):
            raise RegistryError(f"service {sid!r}: epic {sdef['epic']!r} invalid format")
        if not since_re.match(str(sdef["since"])):
            raise RegistryError(f"service {sid!r}: since {sdef['since']!r} must match YYYY-MM-DD")

        check = sdef["check"]
        if not isinstance(check, dict):
            raise RegistryError(f"service {sid!r}: check must be dict")
        ctype = check.get("type")
        if ctype not in ALLOWED_CHECK_TYPES:
            raise RegistryError(f"service {sid!r}: check.type {ctype!r} not in {ALLOWED_CHECK_TYPES}")

        if ctype == "systemd_active":
            unit = check.get("unit")
            if not isinstance(unit, str) or not unit:
                raise RegistryError(f"service {sid!r}: systemd_active requires non-empty unit string")
        elif ctype == "http_url":
            url = check.get("url")
            if not isinstance(url, str) or not url:
                raise RegistryError(f"service {sid!r}: http_url requires non-empty url")
            if not (url.startswith("http://") or url.startswith("https://")):
                raise RegistryError(f"service {sid!r}: http_url url must start with http:// or https://")
            ts = check.get("timeout_sec", DEFAULT_HTTP_TIMEOUT_SEC)
            if not isinstance(ts, int) or ts <= 0:
                raise RegistryError(f"service {sid!r}: timeout_sec must be positive int")
            acc = check.get("accept_status", DEFAULT_ACCEPT_STATUS)
            if not isinstance(acc, list) or len(acc) == 0:
                raise RegistryError(f"service {sid!r}: accept_status must be non-empty list")
            if not all(isinstance(c, int) for c in acc):
                raise RegistryError(f"service {sid!r}: accept_status must contain only ints")
        elif ctype == "file_freshness":
            fpath = check.get("path")
            if not isinstance(fpath, str) or not fpath:
                raise RegistryError(f"service {sid!r}: file_freshness requires non-empty path")
            mas = check.get("max_age_sec")
            if not isinstance(mas, int) or mas <= 0:
                raise RegistryError(f"service {sid!r}: max_age_sec must be positive int")

    return data


# ── Check type dispatchers ────────────────────────────────────────


def check_systemd_active(spec: dict) -> dict:
    """Check if a systemd user unit is active.

    Returns {'status', 'detail'}.
    Never raises.
    """
    unit = spec["unit"]
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", unit],
            capture_output=True, text=True, timeout=SYSTEMCTL_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired:
        return {"status": "unknown", "detail": "timeout"}
    except Exception as e:
        return {"status": "unknown", "detail": f"{type(e).__name__}: {str(e)[:200]}"}

    stdout_clean = result.stdout.strip()
    if stdout_clean == "active":
        return {"status": "up", "detail": "active"}
    return {"status": "down", "detail": stdout_clean or "inactive"}


def check_http_url(spec: dict) -> dict:
    """Check an HTTP URL endpoint.

    Returns {'status', 'detail'}. Never raises.
    """
    import urllib.request
    import urllib.error
    import socket

    url = spec["url"]
    timeout_sec = spec.get("timeout_sec", DEFAULT_HTTP_TIMEOUT_SEC)
    accept_status = set(spec.get("accept_status", DEFAULT_ACCEPT_STATUS))

    try:
        with urllib.request.urlopen(url, timeout=timeout_sec) as resp:
            code = resp.status
    except urllib.error.HTTPError as e:
        code = e.code
        if code in accept_status:
            return {"status": "up", "detail": str(code)}
        return {"status": "down", "detail": str(code)}
    except urllib.error.URLError as e:
        return {"status": "down", "detail": f"URLError: {str(e)[:200]}"}
    except socket.timeout:
        return {"status": "down", "detail": f"timeout after {timeout_sec}s"}
    except Exception as e:
        return {"status": "unknown", "detail": f"{type(e).__name__}: {str(e)[:200]}"}

    if code in accept_status:
        return {"status": "up", "detail": str(code)}
    return {"status": "down", "detail": str(code)}


def check_file_freshness(spec: dict) -> dict:
    """Check if a file is fresh (mtime within max_age_sec).

    Returns {'status', 'detail'}. Never raises.
    """
    path = Path(spec["path"]).expanduser()
    max_age = spec["max_age_sec"]

    if not path.exists():
        return {"status": "down", "detail": f"file not found: {path}"}

    try:
        age = int(time.time() - path.stat().st_mtime)
    except OSError as e:
        return {"status": "unknown", "detail": f"{type(e).__name__}: {str(e)[:200]}"}

    if age > max_age:
        return {"status": "degraded", "detail": f"age {age}s > max {max_age}s"}
    return {"status": "up", "detail": f"age {age}s"}


# ── Dispatcher + overall computation ──────────────────────────────


def run_check(service_def: dict) -> dict:
    """Dispatch to the appropriate check function based on check.type.

    Returns {'status', 'detail'}. Never raises — unknown type returns unknown.
    """
    check = service_def["check"]
    ctype = check["type"]

    if ctype == "systemd_active":
        return check_systemd_active(check)
    if ctype == "http_url":
        return check_http_url(check)
    if ctype == "file_freshness":
        return check_file_freshness(check)
    return {"status": "unknown", "detail": f"unknown check type: {ctype}"}


def compute_overall(services_state: dict, critical_ids: set[str]) -> dict:
    """Compute overall level + counters from per-service state dict.

    services_state: {service_id: {"status": ..., "critical": ...}}
    critical_ids: set of service_ids where critical=True
    """
    total = len(services_state)
    up = sum(1 for s in services_state.values() if s["status"] == "up")
    degraded = sum(1 for s in services_state.values() if s["status"] == "degraded")
    down = sum(1 for s in services_state.values() if s["status"] == "down")
    unknown = sum(1 for s in services_state.values() if s["status"] == "unknown")

    critical_total = len(critical_ids)
    critical_up = sum(
        1 for sid in critical_ids
        if services_state.get(sid, {}).get("status") == "up"
    )
    critical_not_up = critical_total - critical_up

    # Level calculation
    if critical_not_up > 0:
        level = "down"
    elif total > 0 and up < total:
        level = "degraded"
    else:
        level = "ok"

    return {
        "level": level,
        "detail": None,
        "critical_total": critical_total,
        "critical_up": critical_up,
        "critical_not_up": critical_not_up,
        "services_total": total,
        "services_up": up,
        "services_degraded": degraded,
        "services_down": down,
        "services_unknown": unknown,
    }


# ── State building + atomic write ─────────────────────────────────


def now_iso_utc() -> str:
    """Current UTC time as ISO 8601 ending in Z (millisecond precision)."""
    dt = datetime.now(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def build_state(
    *,
    run_id: str,
    registry_version: int,
    services_state: dict,
    overall: dict,
    total_duration_ms: int,
) -> dict:
    """Build the final state.json envelope."""
    return {
        "schema_version": 1,
        "generated_at": now_iso_utc(),
        "registry_version": registry_version,
        "run_id": run_id,
        "duration_ms": total_duration_ms,
        "overall": overall,
        "services": services_state,
    }


def build_unknown_state(*, run_id: str, error: str) -> dict:
    """Build a state.json for the registry-load-failure scenario."""
    return {
        "schema_version": 1,
        "generated_at": now_iso_utc(),
        "registry_version": None,
        "run_id": run_id,
        "duration_ms": 0,
        "overall": {
            "level": "unknown",
            "detail": error,
            "critical_total": None,
            "critical_up": None,
            "critical_not_up": None,
            "services_total": None,
            "services_up": None,
            "services_degraded": None,
            "services_down": None,
            "services_unknown": None,
        },
        "services": {},
    }


def write_state_atomic(state: dict, path: Path) -> None:
    """Atomically write state.json via tempfile + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    os.replace(tmp, path)


# ── Scan orchestration ────────────────────────────────────────────


def ms_since(start: float) -> int:
    return int((time.time() - start) * 1000)


def cmd_scan() -> int:
    """Run a full scan: load registry, check all services, write state.json.

    Never raises. Always returns 0 (fail-soft invariant).
    """
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    start_ts = time.time()

    try:
        registry = load_registry(REGISTRY_PATH)
    except RegistryError as e:
        state = build_unknown_state(
            run_id=run_id,
            error=f"{type(e).__name__}: {str(e)[:200]}",
        )
        try:
            write_state_atomic(state, STATE_PATH)
        except Exception as write_err:
            log.error("failed to write state.json after registry error: %s", write_err)
        log.warning("registry load failed: %s", e)
        return 0

    services_state = {}
    critical_ids: set[str] = set()
    for sid, sdef in registry["services"].items():
        if sdef["critical"]:
            critical_ids.add(sid)
        check_start = time.time()
        try:
            result = run_check(sdef)
        except Exception as e:
            result = {
                "status": "unknown",
                "detail": f"{type(e).__name__}: {str(e)[:200]}",
            }
        services_state[sid] = {
            "name": sdef["name"],
            "epic": sdef["epic"],
            "critical": sdef["critical"],
            "check_type": sdef["check"]["type"],
            "status": result["status"],
            "detail": result["detail"],
            "checked_at": now_iso_utc(),
            "duration_ms": ms_since(check_start),
        }

    overall = compute_overall(services_state, critical_ids)
    state = build_state(
        run_id=run_id,
        registry_version=registry["version"],
        services_state=services_state,
        overall=overall,
        total_duration_ms=ms_since(start_ts),
    )

    try:
        write_state_atomic(state, STATE_PATH)
    except Exception as write_err:
        log.error("failed to write state.json: %s", write_err)
        return 0  # still fail-soft

    log.info(
        "scan complete: %d services, %d up, %d down, %d degraded, %d unknown (%dms)",
        overall["services_total"],
        overall["services_up"],
        overall["services_down"],
        overall["services_degraded"],
        overall["services_unknown"],
        state["duration_ms"],
    )
    return 0


# ── Human-readable output commands ────────────────────────────────


def _read_state_file() -> Optional[dict]:
    if not STATE_PATH.exists():
        return None
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _format_age(generated_at: str) -> str:
    try:
        dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        age_sec = int((datetime.now(timezone.utc) - dt).total_seconds())
        return f"{age_sec}s"
    except Exception:
        return "?s"


def cmd_status() -> int:
    """Print human-readable summary of state.json."""
    state = _read_state_file()
    if state is None:
        print(f"error: state.json not found or unreadable at {STATE_PATH}", file=sys.stderr)
        return 2

    age = _format_age(state.get("generated_at", ""))
    run_id = state.get("run_id", "?")
    overall = state.get("overall", {})
    level = overall.get("level", "?").upper()

    print(f"OpenClaw Health Check — state age {age} ({run_id})")
    print()
    print(f"Overall: {level}")
    if overall.get("detail"):
        print(f"  detail: {overall['detail']}")
    ct = overall.get("critical_total", "?")
    cu = overall.get("critical_up", "?")
    cnu = overall.get("critical_not_up", "?")
    print(f"  {ct} critical · {cu} up · {cnu} not up")
    total = overall.get("services_total", "?")
    up = overall.get("services_up", "?")
    deg = overall.get("services_degraded", "?")
    down = overall.get("services_down", "?")
    unk = overall.get("services_unknown", "?")
    print(f"  {total} services · {up} up · {deg} degraded · {down} down · {unk} unknown")
    print()
    print("Services:")
    services = state.get("services", {})
    # Sort: critical first, then status (down → unknown → degraded → up), then alpha
    status_order = {"down": 0, "unknown": 1, "degraded": 2, "up": 3}

    def sort_key(item):
        sid, svc = item
        return (
            0 if svc.get("critical") else 1,
            status_order.get(svc.get("status"), 9),
            sid,
        )

    status_labels = {"up": "[UP]  ", "down": "[DOWN]", "degraded": "[DEG] ", "unknown": "[?]   "}
    for sid, svc in sorted(services.items(), key=sort_key):
        label = status_labels.get(svc.get("status"), "[?]   ")
        name = svc.get("name", sid)
        epic = svc.get("epic", "")
        detail = svc.get("detail", "")
        print(f"  {label}  {name:<40} ({sid}) {epic:<6} {detail}")

    return 0


def cmd_json() -> int:
    """Print state.json raw."""
    state = _read_state_file()
    if state is None:
        print(f"error: state.json not found or unreadable at {STATE_PATH}", file=sys.stderr)
        return 2
    print(json.dumps(state, indent=2))
    return 0


# ── Entry point ────────────────────────────────────────────────────


def main() -> int:
    p = argparse.ArgumentParser(
        prog="openclaw-health-check",
        description="E8 wave 1 health runner",
    )
    g = p.add_mutually_exclusive_group()
    g.add_argument("--scan", action="store_true", help="Run a scan now")
    g.add_argument("--status", action="store_true", help="Print human summary of state.json")
    g.add_argument("--json", action="store_true", help="Print state.json raw")
    g.add_argument("--version", action="store_true", help="Print version and exit")
    args = p.parse_args()

    if args.version:
        print(VERSION)
        return 0
    if args.status:
        return cmd_status()
    if args.json:
        return cmd_json()

    # default: scan
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    return cmd_scan()


if __name__ == "__main__":
    sys.exit(main())
