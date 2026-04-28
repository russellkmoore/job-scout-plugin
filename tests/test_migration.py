"""
Migration round-trip test for the v3->v4 master_targets.csv schema bump.

Carved-out exception to the v0.4 "no test suite" rule. The fixture
tests/fixtures/master_targets_v3.csv represents a v=3-era user file with:
  - 3 realistic rows (mix of populated and sparse)
  - 11 canonical v=3 columns
  - 1 user-added column ("my_notes") at the end

After migration via validate_data.validate_master_targets(), we assert:
  1. All v3 rows are preserved (zero data loss)
  2. New v=4 columns (ats_slug_confidence, last_ats_hit_date) are present and empty
  3. The user-added column survived at the end
  4. A v=3-shape reader (only-canonical-cols) can still parse the v=4 CSV

Test prereqs: a Python environment with pandas + openpyxl + pytest installed.
Recommended setup (per CON-04 — venv, NOT --break-system-packages):
  pipx install pytest                                          # preferred
  # OR:
  python3 -m venv ~/.job-scout-venv && source ~/.job-scout-venv/bin/activate
  pip install pytest pandas openpyxl

Run:
  python3 -m pytest tests/test_migration.py -v
"""
import os
import shutil
import sys
from pathlib import Path

import pandas as pd
import pytest

# Bootstrap project scripts on sys.path (sibling-script pattern from CONVENTIONS)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from schema import MASTER_TARGETS_COLUMNS, MASTER_TARGETS_VERSION  # noqa: E402
from validate_data import validate_master_targets  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "master_targets_v3.csv"


@pytest.fixture
def migrated_data_dir(tmp_path):
    """Copy the v3 fixture into a tmp data_dir, run the migration, return the path."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    shutil.copy(FIXTURE, data_dir / "master_targets.csv")
    ok, msg = validate_master_targets(str(data_dir))
    assert ok, f"validate_master_targets failed: {msg}"
    return data_dir


def test_schema_version_is_v4():
    """Sanity: the schema constant is at v=4 (catches a Plan 01 regression)."""
    assert MASTER_TARGETS_VERSION == 4


def test_all_v3_rows_preserved(migrated_data_dir):
    """SCH-05 assertion (a): all v3 rows preserved."""
    df = pd.read_csv(migrated_data_dir / "master_targets.csv")
    fixture_df = pd.read_csv(FIXTURE)
    assert len(df) == len(fixture_df), "row count changed during migration"
    for name in fixture_df["company_name"]:
        assert (df["company_name"] == name).sum() == 1, f"company {name!r} lost or duplicated"


def test_new_v4_columns_present_and_empty(migrated_data_dir):
    """SCH-05 assertion (b): new columns present and empty."""
    df = pd.read_csv(migrated_data_dir / "master_targets.csv")
    assert "ats_slug_confidence" in df.columns
    assert "last_ats_hit_date" in df.columns
    # fillna("").eq("").all() defensive against pandas 2.x vs 3.x NA differences
    assert df["ats_slug_confidence"].fillna("").eq("").all()
    assert df["last_ats_hit_date"].fillna("").eq("").all()


def test_user_added_column_survives(migrated_data_dir):
    """User-added columns must survive at the end (validate_master_targets rule)."""
    df = pd.read_csv(migrated_data_dir / "master_targets.csv")
    assert "my_notes" in df.columns, "user-added column was dropped"
    assert df.columns[-1] == "my_notes", \
        f"my_notes should be last column; got {df.columns[-1]!r}"


def test_v3_reader_can_parse_v4_csv(migrated_data_dir):
    """SCH-05 assertion (c): v0.3 code path can still read the v=4 CSV without crash.

    Simulate v0.3 by reading only the v=3 canonical columns explicitly.
    pandas tolerates extra columns; this proves the contract.
    """
    v3_columns = [
        "company_name", "industry", "career_page_url", "ats_provider", "ats_board_url",
        "connection_names", "linkedin_connection_count", "application_status",
        "fit_notes", "last_checked", "data_source",
    ]
    df_v3_view = pd.read_csv(
        migrated_data_dir / "master_targets.csv",
        usecols=lambda c: c in v3_columns,
    )
    assert sorted(df_v3_view.columns) == sorted(v3_columns)
    fixture_df = pd.read_csv(FIXTURE)
    assert len(df_v3_view) == len(fixture_df)
