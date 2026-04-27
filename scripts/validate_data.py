#!/usr/bin/env python3
"""
validate_data.py — Health-check and auto-migrate a Job Scout data directory.

Run at the top of every /scout-run (and at the end of /scout-setup) to:
  1. Confirm config.json exists and is well-formed.
  2. Confirm master_targets.csv has every column declared in schema.py
     (auto-add missing columns, fill with defaults — never deletes data).
  3. Confirm JobScout_Tracker.xlsx exists with the right header row,
     creating it if not.
  4. Confirm the daily/ subdirectory exists.

Idempotent. Safe to run on every invocation.

Usage:
    python3 scripts/validate_data.py <data_dir>

Exits 0 on success (with migrations applied silently); exits 1 only if the
data directory is unrecoverable (e.g. config.json missing entirely).
"""

import json
import os
import sys

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas not installed. Run: pip install pandas --break-system-packages", file=sys.stderr)
    sys.exit(1)

# Allow running this script directly from the plugin root.
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from schema import (
    MASTER_TARGETS_COLUMNS,
    TRACKER_COLUMNS,
    empty_master_target_row,
)


def validate_config(data_dir):
    config_path = os.path.join(data_dir, "config.json")
    if not os.path.isfile(config_path):
        return False, f"config.json missing at {config_path} — run /scout-setup"

    try:
        with open(config_path, "r") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        return False, f"config.json is malformed: {e}"

    required_top_keys = ["data_dir", "preferences", "search", "scoring"]
    missing = [k for k in required_top_keys if k not in config]
    if missing:
        return False, f"config.json missing required keys: {missing}"

    return True, "ok"


def validate_master_targets(data_dir):
    """Add any missing columns; never delete or reorder existing ones."""
    path = os.path.join(data_dir, "master_targets.csv")

    if not os.path.isfile(path):
        # Create an empty one with the full schema.
        pd.DataFrame(columns=MASTER_TARGETS_COLUMNS).to_csv(path, index=False)
        return True, "created empty master_targets.csv"

    try:
        df = pd.read_csv(path)
    except Exception as e:
        return False, f"could not read master_targets.csv: {e}"

    existing_cols = list(df.columns)
    added = []

    for col in MASTER_TARGETS_COLUMNS:
        if col not in existing_cols:
            df[col] = ""
            added.append(col)

    if added:
        # Reorder so canonical columns come first, then any extras the user added
        # at the end (we never drop user columns).
        extras = [c for c in df.columns if c not in MASTER_TARGETS_COLUMNS]
        df = df[MASTER_TARGETS_COLUMNS + extras]
        df.to_csv(path, index=False)
        return True, f"added missing columns: {added}"

    return True, "ok"


def validate_tracker(data_dir):
    """Ensure JobScout_Tracker.xlsx exists with the correct header row."""
    path = os.path.join(data_dir, "JobScout_Tracker.xlsx")
    if os.path.isfile(path):
        return True, "ok"

    # Defer to tracker_utils to create with proper formatting.
    try:
        from tracker_utils import create_empty_tracker
        create_empty_tracker(path)
        return True, "created empty JobScout_Tracker.xlsx"
    except Exception as e:
        return False, f"could not create tracker: {e}"


def validate_daily_dir(data_dir):
    daily = os.path.join(data_dir, "daily")
    os.makedirs(daily, exist_ok=True)
    return True, "ok"


def main(argv):
    if len(argv) < 2:
        print("Usage: validate_data.py <data_dir>", file=sys.stderr)
        sys.exit(1)

    data_dir = os.path.expanduser(argv[1])
    if not os.path.isdir(data_dir):
        print(f"ERROR: data_dir does not exist: {data_dir}", file=sys.stderr)
        sys.exit(1)

    results = {}
    overall_ok = True

    for name, fn in [
        ("config", validate_config),
        ("master_targets", validate_master_targets),
        ("tracker", validate_tracker),
        ("daily_dir", validate_daily_dir),
    ]:
        ok, msg = fn(data_dir)
        results[name] = {"ok": ok, "message": msg}
        if not ok:
            overall_ok = False

    print(json.dumps({"data_dir": data_dir, "ok": overall_ok, "checks": results}, indent=2))
    sys.exit(0 if overall_ok else 1)


if __name__ == "__main__":
    main(sys.argv)
