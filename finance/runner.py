#!/usr/bin/env python3
"""
E11 wave 1 — Finance runway snapshot builder.

Reads override.yml (host-local) or example.yml (canonical fallback)
+ ~/.openclaw/cost/usage-tracking.db (E9 output), computes runway,
writes ~/.openclaw/finance/state.json atomically.

Single-file runner. stdlib + pyyaml. Matches E8 runner pattern.
Runs via systemd timer (hourly).

Spec: bevox-knowledge/35_specs/2026-04-14-e11-finance-runway-wave-1.md
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import traceback
from datetime import datetime, timezone, date, timedelta
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
OVERRIDE_PATH = HOME / ".openclaw" / "finance" / "finance-snapshot.override.yml"
EXAMPLE_PATH = (
    HOME / "bevox-knowledge" / "20_architecture" / "finance-snapshot.example.yml"
)
STATE_PATH = HOME / ".openclaw" / "finance" / "state.json"
DEFAULT_COST_DB_PATH = HOME / ".openclaw" / "cost" / "usage-tracking.db"

REQUIRED_FIELDS = ("as_of", "usd_brl", "cash_on_hand_brl", "mrr_brl")
AI_COST_WINDOW_DAYS = 30


def resolve_snapshot_source(
    override_path: Optional[Path] = None,
    example_path: Optional[Path] = None,
) -> tuple[Optional[Path], str, list[str]]:
    """Resolve SoT financeira com precedencia override > example > missing.

    Returns (path, source_mode, warnings).
    """
    if override_path is None:
        override_path = OVERRIDE_PATH
    if example_path is None:
        example_path = EXAMPLE_PATH
    if override_path.exists():
        return (override_path, "override", [])
    if example_path.exists():
        return (example_path, "example", ["no_override_using_example"])
    return (None, "missing", ["no_canonical_yaml"])


def load_snapshot_yaml(path: Path) -> tuple[Optional[dict], list[str]]:
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


def read_e9_cost_30d_usd(
    db_path: Path,
    today: Optional[date] = None,
) -> tuple[float, list[str]]:
    """Read sum of cost from usage_snapshots for last 30 days.

    Returns (cost_usd, warnings). Never raises.
    """
    if today is None:
        today = date.today()
    cutoff = (today - timedelta(days=AI_COST_WINDOW_DAYS)).isoformat()

    if not db_path.exists():
        return (0.0, ["e9_cost_db_missing"])

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cur = conn.execute(
            "SELECT COALESCE(SUM(cost), 0) FROM usage_snapshots WHERE date >= ?",
            (cutoff,),
        )
        row = cur.fetchone()
        conn.close()
    except sqlite3.Error as e:
        return (0.0, [f"e9_cost_db_error: {e}"])

    cost = float(row[0]) if row and row[0] is not None else 0.0
    warnings: list[str] = []
    if cost == 0.0:
        warnings.append("e9_cost_db_empty_or_zero")
    return (cost, warnings)


def compute_runway(
    cash_on_hand_brl: float,
    mrr_brl: float,
    recurring_costs_monthly_brl: float,
    ai_variable_cost_30d_brl: float,
) -> dict:
    """Pure function: compute burn/net/runway/is_profitable.

    Returns dict with keys:
      burn_monthly_brl, net_monthly_brl, is_profitable, runway_months,
      runway_warnings (list)
    """
    burn = round(recurring_costs_monthly_brl + ai_variable_cost_30d_brl, 2)
    net = round(mrr_brl - burn, 2)

    runway_warnings: list[str] = []

    if net > 0:
        is_profitable = True
        runway = None
    elif net == 0:
        is_profitable = False
        runway = None
        runway_warnings.append("break_even_no_runway_bound")
    else:
        is_profitable = False
        runway = round(cash_on_hand_brl / (-net), 1)

    return {
        "burn_monthly_brl": burn,
        "net_monthly_brl": net,
        "is_profitable": is_profitable,
        "runway_months": runway,
        "runway_warnings": runway_warnings,
    }


def build_state(
    cost_db_path: Optional[Path] = None,
    today: Optional[date] = None,
) -> dict:
    """Build the complete state dict. Fail-soft; never raises."""
    if cost_db_path is None:
        env = os.environ.get("USAGE_DB_PATH")
        cost_db_path = Path(env) if env else DEFAULT_COST_DB_PATH

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    state: dict = {
        "generated_at": generated_at,
        "as_of": None,
        "currency": "BRL",
        "status": "ok",
        "usd_brl_used": None,
        "cash_on_hand_brl": None,
        "mrr_brl": None,
        "recurring_costs_monthly_brl": None,
        "ai_variable_cost_30d_usd": None,
        "ai_variable_cost_30d_brl": None,
        "ai_variable_cost_window_days": AI_COST_WINDOW_DAYS,
        "burn_monthly_brl": None,
        "net_monthly_brl": None,
        "is_profitable": None,
        "runway_months": None,
        "recurring_costs_breakdown": [],
        "inputs": {
            "snapshot_source": "missing",
            "snapshot_path": None,
            "e9_cost_db": str(cost_db_path),
        },
        "missing_fields": [],
        "warnings": [],
    }

    # Resolve source
    path, source, resolve_warnings = resolve_snapshot_source(OVERRIDE_PATH, EXAMPLE_PATH)
    state["inputs"]["snapshot_source"] = source
    state["inputs"]["snapshot_path"] = str(path) if path else None
    state["warnings"].extend(resolve_warnings)

    if source == "missing":
        state["status"] = "no_canonical_yaml"
        return state

    # Load YAML
    data, load_warnings = load_snapshot_yaml(path)
    state["warnings"].extend(load_warnings)
    if data is None:
        state["status"] = "error"
        return state

    # Validate required fields
    missing = validate_required_fields(data)
    if missing:
        state["status"] = "incomplete_yaml"
        state["missing_fields"] = missing
        return state

    # All required present; populate
    # Handle YAML auto-conversion of dates to date objects
    as_of_raw = data["as_of"]
    state["as_of"] = as_of_raw.isoformat() if hasattr(as_of_raw, 'isoformat') else str(as_of_raw)
    usd_brl = float(data["usd_brl"])
    state["usd_brl_used"] = usd_brl
    state["cash_on_hand_brl"] = round(float(data["cash_on_hand_brl"]), 2)
    state["mrr_brl"] = round(float(data["mrr_brl"]), 2)

    # Recurring costs breakdown + total
    recurring_raw = data.get("recurring_costs_brl") or []
    breakdown: list[dict] = []
    recurring_total = 0.0
    for entry in recurring_raw:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name", "")
        category = entry.get("category", "")
        amount = float(entry.get("amount_brl") or 0)
        notes = entry.get("notes")
        breakdown.append(
            {
                "name": name,
                "category": category,
                "amount_brl": round(amount, 2),
                "notes": notes,
            }
        )
        recurring_total += amount

    state["recurring_costs_breakdown"] = breakdown
    state["recurring_costs_monthly_brl"] = round(recurring_total, 2)

    # AI variable cost (E9)
    cost_usd, cost_warnings = read_e9_cost_30d_usd(cost_db_path, today=today)
    state["warnings"].extend(cost_warnings)
    cost_brl = round(cost_usd * usd_brl, 2)
    state["ai_variable_cost_30d_usd"] = round(cost_usd, 4)
    state["ai_variable_cost_30d_brl"] = cost_brl

    # Compute runway
    runway = compute_runway(
        cash_on_hand_brl=state["cash_on_hand_brl"],
        mrr_brl=state["mrr_brl"],
        recurring_costs_monthly_brl=state["recurring_costs_monthly_brl"],
        ai_variable_cost_30d_brl=state["ai_variable_cost_30d_brl"],
    )
    state["burn_monthly_brl"] = runway["burn_monthly_brl"]
    state["net_monthly_brl"] = runway["net_monthly_brl"]
    state["is_profitable"] = runway["is_profitable"]
    state["runway_months"] = runway["runway_months"]
    state["warnings"].extend(runway["runway_warnings"])

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
    parser = argparse.ArgumentParser(description="E11 finance snapshot runner")
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
