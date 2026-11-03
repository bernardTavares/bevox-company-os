#!/usr/bin/env python3
"""
E8 wave 1 (F5) — Hardening tracker runner.

Reads ~/bevox-knowledge/20_architecture/hardening-registry.yml, runs each
check, writes ~/.openclaw/hardening/state.json atomically.

Single-file runner. Uses stdlib + pyyaml (reuses ~/.openclaw/health/health-venv).
Runs via systemd timer (1h cadence) or invoked directly.

NEVER mutates the system. NEVER invokes sudo.

Spec: bevox-knowledge/35_specs/2026-04-18-e8-f5-hardening-tracker-wave-1.md
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ── Constants ──────────────────────────────────────────────────────

HOME = Path.home()
HARDENING_DIR = HOME / ".openclaw" / "hardening"
STATE_PATH = Path(os.environ.get("HARDENING_STATE_PATH",
                                  str(HARDENING_DIR / "state.json")))
REGISTRY_PATH = Path(os.environ.get(
    "HARDENING_REGISTRY_PATH",
    str(HOME / "bevox-knowledge" / "20_architecture" / "hardening-registry.yml"),
))

SCHEMA_VERSION = 1

VALID_CHECK_TYPES = (
    "systemd_active",
    "command_output_match",
    "file_mode_eq",
    "apt_security_updates_max",
    "file_content_match",
)

VALID_SEVERITIES = ("info", "warn", "critical")
VALID_STATUSES = ("ok", "degraded", "critical", "unknown", "not_applicable")

# Spec §5.3 priority order (first match wins for overall.level)
_OVERALL_PRIORITY = ("critical", "unknown", "degraded")


# ── Pure helpers ───────────────────────────────────────────────────


def _compute_overall_level(items: list[dict]) -> str:
    """Spec §5.3: compute overall.level by priority.

    Priority: critical > unknown > degraded > ok.
    not_applicable items NEVER contribute.
    """
    statuses = {it["status"] for it in items if it.get("status") != "not_applicable"}
    for level in _OVERALL_PRIORITY:
        if level in statuses:
            return level
    return "ok"


def _compute_overall_summary(items: list[dict]) -> dict:
    """Build overall.* counter dict from item list."""
    counts = {s: 0 for s in VALID_STATUSES}
    for it in items:
        status = it.get("status", "unknown")
        if status in counts:
            counts[status] += 1
    return {
        "items_total": len(items),
        "items_ok": counts["ok"],
        "items_degraded": counts["degraded"],
        "items_critical": counts["critical"],
        "items_unknown": counts["unknown"],
        "items_not_applicable": counts["not_applicable"],
    }


_REGEX_FLAG_MAP = {
    "multiline": re.MULTILINE,
    "ignorecase": re.IGNORECASE,
    "dotall": re.DOTALL,
}


def _parse_regex_flags(flags: list[str]) -> int:
    """Convert spec flag names → re.* int flags. Case-insensitive."""
    result = 0
    for name in flags:
        key = name.lower()
        if key not in _REGEX_FLAG_MAP:
            raise ValueError(f"unknown regex flag: {name!r}")
        result |= _REGEX_FLAG_MAP[key]
    return result


def _severity_to_failed_status(severity: str) -> str:
    """Spec §5.3: severity=critical → critical; warn|info → degraded."""
    return "critical" if severity == "critical" else "degraded"


# ── Check handlers ─────────────────────────────────────────────────
#
# Each handler returns dict {"status": <one of ok|failed|unknown|not_applicable>,
#                            "detail": <string>}.
# "failed" is later mapped to "critical" or "degraded" by the orchestrator
# based on the item's declared severity.


def _check_systemd_active(params: dict) -> dict:
    """Spec §5.2: systemd_active."""
    unit = params["unit"]
    scope = params.get("scope", "user")
    napp_if_missing = params.get("not_applicable_if_unit_missing", False)
    cmd = ["systemctl"]
    if scope == "user":
        cmd.append("--user")
    cmd.extend(["is-active", unit])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    except FileNotFoundError as e:
        return {"status": "unknown", "detail": f"systemctl not found: {e}"[:200]}
    except subprocess.TimeoutExpired:
        return {"status": "unknown", "detail": "systemctl timeout after 5s"}
    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()
    if r.returncode == 0:
        return {"status": "ok", "detail": out or "active"}
    # Detect "unit not found"
    err_l = err.lower()
    if napp_if_missing and ("could not be found" in err_l or "not loaded" in err_l):
        return {"status": "not_applicable",
                "detail": f"unit {unit} not found"}
    return {"status": "failed",
            "detail": f"{out or 'inactive'}: {err}"[:200]}


def _check_command_output_match(params: dict) -> dict:
    """Spec §5.2: command_output_match."""
    cmd = params["cmd"]
    expect = params["expect_regex"]
    flags = _parse_regex_flags(params.get("regex_flags", []))
    timeout = int(params.get("timeout_sec", 5))
    napp_exits = set(params.get("not_applicable_on_exit") or [])
    napp_if_cmd_missing = params.get("not_applicable_if_cmd_missing", False)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as e:
        if napp_if_cmd_missing:
            return {"status": "not_applicable",
                    "detail": f"{cmd[0]} not installed"}
        return {"status": "unknown", "detail": f"cmd not found: {e}"[:200]}
    except subprocess.TimeoutExpired:
        return {"status": "unknown",
                "detail": f"cmd timeout after {timeout}s"}
    if r.returncode in napp_exits:
        return {"status": "not_applicable",
                "detail": f"exit {r.returncode} in not_applicable_on_exit"}
    if r.returncode != 0:
        return {"status": "failed",
                "detail": f"exit {r.returncode}: {(r.stderr or '').strip()[:160]}"}
    if re.search(expect, r.stdout or "", flags):
        return {"status": "ok", "detail": "matched"}
    return {"status": "failed",
            "detail": f"no match for /{expect}/ in stdout"[:200]}


def _check_file_mode_eq(params: dict) -> dict:
    """Spec §5.2: file_mode_eq."""
    path_str = os.path.expanduser(params["path"])
    expected = params["mode"]
    napp_if_missing = params.get("not_applicable_if_missing", False)
    p = Path(path_str)
    if not p.exists():
        if napp_if_missing:
            return {"status": "not_applicable", "detail": f"{path_str} missing"}
        return {"status": "unknown", "detail": f"{path_str} missing"}
    actual = oct(p.stat().st_mode & 0o7777)
    # Normalize to 4 digits with leading 0
    actual_4 = "0" + actual[2:].rjust(3, "0") if not actual[2:].startswith("0") \
               else actual[2:].rjust(4, "0")
    expected_4 = expected if expected.startswith("0") else "0" + expected
    if actual_4 == expected_4:
        return {"status": "ok", "detail": f"mode {actual_4}"}
    return {"status": "failed",
            "detail": f"expected {expected_4}, got {actual_4}"}


def _check_file_content_match(params: dict) -> dict:
    """Spec §5.2: file_content_match."""
    path_patterns = params["paths"]
    expect = params["expect_regex"]
    flags = _parse_regex_flags(params.get("regex_flags", []))
    match_mode = params.get("match_mode", "any")
    forbid = params.get("forbid_regex")
    napp_if_no_files = params.get("not_applicable_if_no_files", False)
    max_bytes = int(params.get("max_total_bytes", 1048576))

    # Expand paths via glob (no shell)
    files: list[str] = []
    for pat in path_patterns:
        files.extend(glob.glob(os.path.expanduser(pat)))
    files = sorted(set(files))

    if not files:
        if napp_if_no_files:
            return {"status": "not_applicable",
                    "detail": f"no files matched {path_patterns}"}
        return {"status": "unknown",
                "detail": f"no files matched {path_patterns}"}

    # Read with byte budget
    contents: list[tuple[str, str]] = []
    total = 0
    for f in files:
        try:
            data = Path(f).read_bytes()
        except (OSError, PermissionError) as e:
            return {"status": "unknown", "detail": f"{f}: {e}"[:200]}
        total += len(data)
        if total > max_bytes:
            return {"status": "unknown",
                    "detail": f"exceeded byte budget ({max_bytes})"}
        contents.append((f, data.decode("utf-8", errors="replace")))

    # forbid_regex: if matches in any file → failed (overrides ok)
    if forbid:
        for f, text in contents:
            if re.search(forbid, text, flags):
                return {"status": "failed",
                        "detail": f"forbid_regex matched in {f}"[:200]}

    # expect_regex
    if match_mode == "all":
        for f, text in contents:
            if not re.search(expect, text, flags):
                return {"status": "failed",
                        "detail": f"no match for /{expect}/ in {f}"[:200]}
        return {"status": "ok", "detail": f"matched in all {len(files)} files"}
    # match_mode = any (default)
    for f, text in contents:
        if re.search(expect, text, flags):
            return {"status": "ok", "detail": f"matched in {f}"}
    return {"status": "failed",
            "detail": f"no match for /{expect}/ in any of {len(files)} files"[:200]}


def _check_apt_security_updates_max(params: dict) -> dict:
    """Spec §5.2: apt_security_updates_max."""
    threshold = int(params["threshold"])
    timeout = int(params.get("timeout_sec", 30))
    try:
        r = subprocess.run(
            ["apt-get", "-s", "upgrade"],
            capture_output=True, text=True, timeout=timeout,
        )
    except FileNotFoundError:
        return {"status": "not_applicable", "detail": "apt-get not installed"}
    except subprocess.TimeoutExpired:
        return {"status": "unknown",
                "detail": f"apt-get timeout after {timeout}s"}
    if r.returncode != 0:
        return {"status": "unknown",
                "detail": f"apt-get exit {r.returncode}: {(r.stderr or '').strip()[:160]}"}
    # Count lines starting with "Inst " that mention a *-security source
    count = 0
    for line in (r.stdout or "").splitlines():
        if line.startswith("Inst ") and re.search(r"-Security", line, re.IGNORECASE):
            count += 1
    if count <= threshold:
        return {"status": "ok",
                "detail": f"{count} security updates pending (threshold {threshold})"}
    return {"status": "failed",
            "detail": f"{count} security updates pending (>{threshold})"}


# ── Orchestrator ───────────────────────────────────────────────────


def _get_handler(check_type: str):
    """Resolve handler by name at call time (so unittest.mock.patch works)."""
    if check_type not in VALID_CHECK_TYPES:
        return None
    return globals().get(f"_check_{check_type}")


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") \
           + f"{datetime.now(timezone.utc).microsecond // 1000:03d}Z"


def _evaluate_item(item: dict) -> dict:
    """Run one item's check, map result to spec state-shape dict.

    Maps handler "failed" → severity-derived "critical" or "degraded".
    Catches handler exceptions → "unknown".
    """
    check = item["check"]
    check_type = check["type"]
    severity = item.get("severity", "warn")
    started = datetime.now(timezone.utc)
    handler = _get_handler(check_type)
    if handler is None:
        result = {"status": "unknown",
                  "detail": f"unknown check type: {check_type}"}
    else:
        try:
            result = handler(check)
        except Exception as e:
            result = {"status": "unknown",
                      "detail": f"handler exception: {e!r}"[:200]}
    duration_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    raw_status = result["status"]
    if raw_status == "failed":
        final_status = _severity_to_failed_status(severity)
    else:
        final_status = raw_status
    return {
        "id": item["id"],
        "name": item.get("name", item["id"]),
        "category": item.get("category", "other"),
        "severity": severity,
        "status": final_status,
        "detail": result.get("detail", ""),
        "check_type": check_type,
        "checked_at": _now_iso_utc(),
        "duration_ms": duration_ms,
    }


def _load_registry(path: Path) -> dict:
    """Load + validate hardening-registry.yml.

    Returns {version: int, items: [{id, ...item dict}, ...]}.
    Raises FileNotFoundError if file missing.
    Raises ValueError on schema violations (unknown check type, bad severity).
    """
    import yaml as _yaml
    if not Path(path).exists():
        raise FileNotFoundError(f"registry not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        raw = _yaml.safe_load(f)
    if not isinstance(raw, dict):
        raise ValueError(f"registry root must be mapping, got {type(raw).__name__}")
    version = raw.get("version", 1)
    items_raw = raw.get("items") or {}
    items: list[dict] = []
    for item_id, attrs in items_raw.items():
        if not isinstance(attrs, dict):
            raise ValueError(f"item {item_id!r}: must be mapping")
        check = attrs.get("check") or {}
        check_type = check.get("type")
        if check_type not in VALID_CHECK_TYPES:
            raise ValueError(
                f"item {item_id!r}: unknown check type {check_type!r}")
        severity = attrs.get("severity", "warn")
        if severity not in VALID_SEVERITIES:
            raise ValueError(
                f"item {item_id!r}: invalid severity {severity!r}")
        items.append({"id": item_id, **attrs})
    return {"version": version, "items": items}


def _write_state_atomic(state: dict, path: Path) -> None:
    """Write state.json via tmp + os.rename (atomic)."""
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    os.replace(tmp, path)


def run_scan(
    registry_path: Optional[Path] = None,
    state_path: Optional[Path] = None,
) -> dict:
    """Full scan: load registry → eval all items → write state.json atomic.

    Returns the state dict written.
    """
    registry_path = Path(registry_path) if registry_path else REGISTRY_PATH
    state_path = Path(state_path) if state_path else STATE_PATH
    started = datetime.now(timezone.utc)
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    reg = _load_registry(registry_path)
    items = [_evaluate_item(it) for it in reg["items"]]
    duration_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    summary = _compute_overall_summary(items)
    overall = {
        "level": _compute_overall_level(items),
        "detail": None,
        **summary,
    }
    state = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now_iso_utc(),
        "registry_version": reg["version"],
        "run_id": run_id,
        "duration_ms": duration_ms,
        "overall": overall,
        "items": items,
    }
    _write_state_atomic(state, state_path)
    return state


# ── CLI ────────────────────────────────────────────────────────────


def _read_state_for_status() -> Optional[dict]:
    if not STATE_PATH.exists():
        return None
    try:
        return json.loads(STATE_PATH.read_text())
    except Exception:
        return None


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="openclaw-hardening")
    parser.add_argument("--scan", action="store_true",
                        help="Run all checks and write state.json (default if no flag)")
    parser.add_argument("--status", action="store_true",
                        help="Print summary of current state.json")
    parser.add_argument("--json", action="store_true",
                        help="Print current state.json to stdout")
    parser.add_argument("--version", action="store_true",
                        help="Print version + registry version")
    args = parser.parse_args(argv)

    if args.version:
        reg = _load_registry(REGISTRY_PATH) if REGISTRY_PATH.exists() else None
        print(f"hardening-runner schema={SCHEMA_VERSION} "
              f"registry={reg['version'] if reg else 'missing'}")
        return 0
    if args.json:
        s = _read_state_for_status()
        if s is None:
            print("{}", file=sys.stderr)
            return 1
        print(json.dumps(s, indent=2))
        return 0
    if args.status:
        s = _read_state_for_status()
        if s is None:
            print("stale: state.json missing")
            return 1
        print(f"overall: {s['overall']['level']} "
              f"({s['overall']['items_ok']}/{s['overall']['items_total']} ok, "
              f"{s['overall']['items_critical']} critical, "
              f"{s['overall']['items_degraded']} degraded, "
              f"{s['overall']['items_unknown']} unknown, "
              f"{s['overall']['items_not_applicable']} n/a)")
        for it in s["items"]:
            print(f"  [{it['status']:14s}] {it['id']:30s} {it['detail']}")
        return 0
    # default: --scan
    state = run_scan()
    print(f"overall: {state['overall']['level']} "
          f"(items: {state['overall']['items_total']}, "
          f"duration: {state['duration_ms']}ms)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
