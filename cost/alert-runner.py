#!/usr/bin/env python3
"""
E9 wave 2 — Cost alerts runner.

Reads cost-alerts.override.yml (host-local) or cost-alerts.example.yml
(canonical fallback) + ~/.openclaw/cost/usage-tracking.db (E9 wave 1
output, read-only), evaluates daily threshold instantly, writes
~/.openclaw/cost/cost-alerts-state.json atomically.

Single-file runner. stdlib + pyyaml. Matches E8/E11 runner pattern.
Runs via systemd timer (hourly, separate from the E9 wave 1 collector).

Spec: bevox-knowledge/35_specs/2026-04-15-e9-cost-usage-wave-2.md
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import traceback
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    print(
        "ERROR: pyyaml not installed. Reuse ~/.openclaw/health/health-venv/ which has it.",
        file=sys.stderr,
    )
    sys.exit(1)


HOME = Path(os.environ.get("HOME", f"{Path.home()}"))
OVERRIDE_PATH = HOME / ".openclaw" / "cost" / "cost-alerts.override.yml"
EXAMPLE_PATH = (
    HOME / "bevox-knowledge" / "20_architecture" / "cost-alerts.example.yml"
)
STATE_PATH = HOME / ".openclaw" / "cost" / "cost-alerts-state.json"
DEFAULT_COST_DB_PATH = HOME / ".openclaw" / "cost" / "usage-tracking.db"

REQUIRED_FIELDS = ("daily_threshold_usd",)


def resolve_snapshot_source(
    override_path: Path = OVERRIDE_PATH,
    example_path: Path = EXAMPLE_PATH,
) -> tuple[Optional[Path], str, list[str]]:
    """Resolve config source com precedencia override > example > missing.

    Duplicado inline do pattern E11 finance runner — sem _lib/ compartilhada
    (rule of three nao atingida).

    Returns (path, source_mode, warnings).
    """
    if override_path.exists():
        return (override_path, "override", [])
    if example_path.exists():
        return (example_path, "example", ["no_override_using_example"])
    return (None, "missing", ["no_canonical_yaml"])


def load_config_yaml(path: Path) -> tuple[Optional[dict], list[str]]:
    """Load YAML file, return (data, warnings)."""
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            return (None, [f"yaml_not_a_dict: {path}"])
        return (data, [])
    except yaml.YAMLError as e:
        return (None, [f"yaml_parse_error: {e}"])
    except OSError as e:
        return (None, [f"yaml_io_error: {e}"])


def validate_required_fields(data: dict) -> list[str]:
    """Return list of missing required field names."""
    missing = []
    for field in REQUIRED_FIELDS:
        if field not in data or data[field] is None:
            missing.append(field)
    return missing


def read_today_cost_usd(
    db_path: Path,
    today_utc: date,
) -> tuple[float, list[str]]:
    """Read sum of cost from usage_snapshots for today (UTC).

    `today_utc` is passed in explicitly to make the function testable
    and to make the UTC contract explicit at the caller layer. The
    caller is responsible for using `datetime.now(timezone.utc).date()`.

    Returns (cost_usd, warnings). Never raises.
    """
    if not db_path.exists():
        return (0.0, ["cost_db_missing"])

    today_iso = today_utc.isoformat()  # YYYY-MM-DD UTC, matches E9 wave 1 collector

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cur = conn.execute(
            "SELECT COALESCE(SUM(cost), 0) FROM usage_snapshots WHERE date = ?",
            (today_iso,),
        )
        row = cur.fetchone()
        conn.close()
    except sqlite3.Error as e:
        return (0.0, [f"cost_db_error: {e}"])

    cost = float(row[0]) if row and row[0] is not None else 0.0
    return (cost, [])


def compute_alert(
    enabled: bool,
    daily_threshold_usd: float,
    today_cost_usd: float,
) -> bool:
    """Pure function: decide if alert is active.

    Strictly greater than (not >=). Empate exato nao dispara.
    Guards: not enabled → False. threshold <= 0 → False (example mode).
    """
    if not enabled:
        return False
    if daily_threshold_usd <= 0:
        return False
    return today_cost_usd > daily_threshold_usd


def build_state(
    cost_db_path: Optional[Path] = None,
    today_utc: Optional[date] = None,
    override_path: Optional[Path] = None,
    example_path: Optional[Path] = None,
) -> dict:
    """Build the complete state dict. Fail-soft; never raises."""
    if cost_db_path is None:
        env = os.environ.get("USAGE_DB_PATH")
        cost_db_path = Path(env) if env else DEFAULT_COST_DB_PATH

    if today_utc is None:
        today_utc = datetime.now(timezone.utc).date()

    if override_path is None:
        override_path = OVERRIDE_PATH
    if example_path is None:
        example_path = EXAMPLE_PATH

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    state: dict = {
        "generated_at": generated_at,
        "status": "ok",
        "config_source": "missing",
        "config_path": None,
        "enabled": None,
        "daily_threshold_usd": None,
        "today_date": today_utc.isoformat(),
        "today_cost_usd": None,
        "today_cost_pct_of_threshold": None,
        "alert_active": False,
        "last_evaluated_at": generated_at,
        "inputs": {
            "config_yaml": None,
            "usage_db": str(cost_db_path),
        },
        "missing_fields": [],
        "warnings": [],
    }

    # Resolve config source
    path, source, resolve_warnings = resolve_snapshot_source(override_path, example_path)
    state["config_source"] = source
    state["config_path"] = str(path) if path else None
    state["inputs"]["config_yaml"] = str(path) if path else None
    state["warnings"].extend(resolve_warnings)

    if source == "missing":
        state["status"] = "no_config"
        return state

    # Load YAML
    data, load_warnings = load_config_yaml(path)
    state["warnings"].extend(load_warnings)
    if data is None:
        state["status"] = "error"
        return state

    # Validate required fields
    missing = validate_required_fields(data)
    if missing:
        state["status"] = "error"
        state["missing_fields"] = missing
        state["warnings"].append(f"missing_required_fields: {missing}")
        return state

    # Extract config
    daily_threshold_usd = float(data["daily_threshold_usd"])
    enabled = bool(data.get("enabled", True))
    state["daily_threshold_usd"] = daily_threshold_usd
    state["enabled"] = enabled

    # If disabled, suppress evaluation but still report cost
    cost_usd, cost_warnings = read_today_cost_usd(cost_db_path, today_utc)
    state["warnings"].extend(cost_warnings)
    state["today_cost_usd"] = round(cost_usd, 4)

    if daily_threshold_usd > 0:
        state["today_cost_pct_of_threshold"] = round(
            cost_usd / daily_threshold_usd * 100, 1
        )
    else:
        state["today_cost_pct_of_threshold"] = None

    if not enabled:
        state["status"] = "disabled"
        state["alert_active"] = False
        return state

    state["alert_active"] = compute_alert(
        enabled=enabled,
        daily_threshold_usd=daily_threshold_usd,
        today_cost_usd=cost_usd,
    )

    return state


def write_state_atomic(state: dict, path: Path = STATE_PATH) -> None:
    """Write state.json atomically via tmp + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="E9 wave 2 cost alerts runner")
    parser.add_argument("--build", action="store_true", help="Build and write state.json")
    parser.add_argument("--print", action="store_true", help="Print state to stdout (no write)")
    args = parser.parse_args(argv)

    if not (args.build or args.print):
        parser.print_help()
        return 0

    try:
        state = build_state()
    except Exception as e:
        # Should never reach here with fail-soft design, but belt-and-suspenders
        state = {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": "error",
            "warnings": [f"unexpected_exception: {e}", traceback.format_exc()],
        }

    if args.print:
        print(json.dumps(state, indent=2, ensure_ascii=False))

    if args.build:
        try:
            write_state_atomic(state)
        except Exception as e:
            print(f"ERROR writing state.json: {e}", file=sys.stderr)
            return 0  # still fail-soft

    return 0


if __name__ == "__main__":
    sys.exit(main())
