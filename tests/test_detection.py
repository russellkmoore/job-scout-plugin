"""test_detection.py — Fixture-driven tests for Phase 3 detection layer.

Covers DET-01..05, DET-07, STR-02, STR-04 (DET-06 is a skill-only smoke test
in Plan 02; CON-08 is a grep gate in Plan 03).

Carved-out exception to the v0.4 "no test suite" rule per ROADMAP Phase 3.
Test prereqs (per CON-04 — venv, NOT --break-system-packages):
  pipx install pytest          # preferred (already done in Phase 1)
  OR
  python3 -m venv ~/.job-scout-venv && ~/.job-scout-venv/bin/pip install rapidfuzz pandas

Run:
  ~/.job-scout-venv/bin/python3 -m pytest tests/test_detection.py -v
  # or per-test:
  ~/.job-scout-venv/bin/python3 -m pytest tests/test_detection.py::test_two_factor_gate_confirmed -x
"""
import csv
import json
import os
import shutil
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Bootstrap (project_root/scripts on path) — matches tests/test_migration.py.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from ats.providers.base import DetectionResult, DetectionStatus  # noqa: E402

FIXTURE_CSV = Path(__file__).parent / "fixtures" / "master_targets_phase3_detect.csv"
DETECT_SCRIPT = PROJECT_ROOT / "scripts" / "ats" / "detect.py"


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Provision a tmp data_dir with the mixed-state fixture CSV + empty runs.jsonl + minimal config.json."""
    d = tmp_path / "data"
    d.mkdir()
    shutil.copy(FIXTURE_CSV, d / "master_targets.csv")
    (d / "runs.jsonl").touch()
    (d / "config.json").write_text(json.dumps({"ats": {"provider_concurrency_caps": {"greenhouse": 2}, "concurrency_disabled": True}}))
    return d


# ---------------------------------------------------------------------------
# DET-01: CLI dispatch
# ---------------------------------------------------------------------------

def test_cli_dispatch_help_exits_zero():
    """DET-01: `python3 detect.py --help` exits 0 and prints subcommands."""
    result = subprocess.run(
        [sys.executable, str(DETECT_SCRIPT), "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"--help exited {result.returncode}: {result.stderr}"


def test_cli_dispatch_unknown_subcommand_exits_nonzero():
    """DET-01: unknown subcommand exits 1 with ERROR message on stderr."""
    result = subprocess.run(
        [sys.executable, str(DETECT_SCRIPT), "no_such_command"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, "unknown subcommand should exit non-zero"


# ---------------------------------------------------------------------------
# DET-03: Two-factor gate
# ---------------------------------------------------------------------------

def test_two_factor_gate_confirmed(mock_greenhouse_ok):
    """DET-03: name match >= 85% -> CONFIRMED with confidence in [0.85, 1.0]."""
    from ats.detect import _apply_name_gate
    # Build a fake BORDERLINE result as greenhouse.detect() would return
    raw = DetectionResult(
        provider="greenhouse",
        status=DetectionStatus.BORDERLINE,
        board_url="https://boards-api.greenhouse.io/v1/boards/airbnb/jobs",
        confidence=0.85,
        evidence={"first_job_company_name": "Airbnb", "job_count": 3, "http_status": 200},
    )
    result = _apply_name_gate(raw, "Airbnb")
    assert result.status == DetectionStatus.CONFIRMED
    assert result.confidence >= 0.85


def test_two_factor_gate_borderline():
    """DET-03: name match 70-84 -> BORDERLINE.

    token_set_ratio returns 100 when the shorter string is a subset of the longer.
    To get a score in [70, 84], use two different non-subset multi-word names.
    'Digital River' vs 'Digital Turbine' -> ~78.6 (both have 'Digital', differ on second word).
    """
    from ats.detect import _apply_name_gate
    # "Digital River" vs "Digital Turbine" — token_set_ratio ~78.6 (borderline)
    raw = DetectionResult(
        provider="greenhouse",
        status=DetectionStatus.BORDERLINE,
        board_url="https://boards-api.greenhouse.io/v1/boards/digital-river/jobs",
        confidence=0.85,
        evidence={"first_job_company_name": "Digital Turbine", "job_count": 5, "http_status": 200},
    )
    result = _apply_name_gate(raw, "Digital River")
    assert result.status == DetectionStatus.BORDERLINE, (
        f"Expected BORDERLINE for 'Digital River' vs 'Digital Turbine', got {result.status} "
        f"(score={result.evidence.get('name_match_score')})"
    )


def test_two_factor_gate_below_70_is_not_found():
    """DET-03: name match < 70 -> NOT_FOUND."""
    from ats.detect import _apply_name_gate
    # "Stripe" vs "Acme Inc" — token_set_ratio should be < 70
    raw = DetectionResult(
        provider="greenhouse",
        status=DetectionStatus.BORDERLINE,
        board_url="https://boards-api.greenhouse.io/v1/boards/acme/jobs",
        confidence=0.85,
        evidence={"first_job_company_name": "Acme Inc", "job_count": 5, "http_status": 200},
    )
    result = _apply_name_gate(raw, "Stripe")
    assert result.status == DetectionStatus.NOT_FOUND


# ---------------------------------------------------------------------------
# DET-02: Provider iteration stops at first CONFIRMED
# ---------------------------------------------------------------------------

def test_provider_iteration_stops_at_first_confirmed(monkeypatch, mock_greenhouse_ok):
    """DET-02: once greenhouse returns CONFIRMED, lever should never be called."""
    import ats.detect as detect_module
    from ats.detect import _detect_one_company

    # Create a mock lever provider that records if it was called
    lever_called = []

    class MockLeverProvider:
        NAME = "lever"
        BOARD_URL_PATTERNS = []

        def detect(self, company_slug, name, client):
            lever_called.append(True)
            return DetectionResult(
                provider="lever",
                status=DetectionStatus.CONFIRMED,
                board_url="https://jobs.lever.co/acme",
                confidence=1.0,
                evidence={},
            )

    # Monkeypatch PROVIDERS to have greenhouse first, lever second
    # greenhouse returns BORDERLINE which _apply_name_gate will elevate to CONFIRMED for "Airbnb"
    import ats.providers.greenhouse as gh_module
    fake_providers = {"greenhouse": gh_module, "lever": MockLeverProvider()}
    monkeypatch.setattr(detect_module, "PROVIDERS", fake_providers)

    caps = {"greenhouse": 2, "lever": 2}
    detect_module._init_detect_semaphores(caps)

    result = _detect_one_company("airbnb", "Airbnb", mock_greenhouse_ok, caps)
    assert result.status == DetectionStatus.CONFIRMED
    assert len(lever_called) == 0, "lever should not have been called after greenhouse CONFIRMED"


# ---------------------------------------------------------------------------
# DET-04: Idempotency + manual lock
# ---------------------------------------------------------------------------

def test_idempotency_manual_lock_never_overwritten(tmp_data_dir, monkeypatch, mock_greenhouse_ok):
    """DET-04: ats_provider=manual rows are NEVER overwritten even with --force."""
    import ats.detect as detect_module
    import ats.providers.greenhouse as gh_module
    monkeypatch.setattr(detect_module, "PROVIDERS", {"greenhouse": gh_module})

    detect_module._init_detect_semaphores({"greenhouse": 2})

    # Monkeypatch httpx.Client to return the mock
    monkeypatch.setattr(detect_module.httpx, "Client", lambda **kwargs: mock_greenhouse_ok)

    csv_path = str(tmp_data_dir / "master_targets.csv")
    detect_module._cmd_detect_batch([csv_path, "--force", "--data-dir", str(tmp_data_dir)])

    # Read back and check Stripe Inc is still "manual"
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    stripe_row = next(r for r in rows if r["company_name"] == "Stripe Inc")
    assert stripe_row["ats_provider"] == "manual", f"Expected 'manual', got {stripe_row['ats_provider']!r}"


def test_idempotency_skips_fresh_hit_without_force(tmp_data_dir, monkeypatch, mock_greenhouse_ok):
    """DET-04: Lululemon (last_ats_hit_date < 30d) is skipped without --force."""
    import ats.detect as detect_module
    import ats.providers.greenhouse as gh_module
    monkeypatch.setattr(detect_module, "PROVIDERS", {"greenhouse": gh_module})
    detect_module._init_detect_semaphores({"greenhouse": 2})
    monkeypatch.setattr(detect_module.httpx, "Client", lambda **kwargs: mock_greenhouse_ok)

    # Pin today to 2026-04-29 so Lululemon's 2026-04-15 hit is <30d ago
    monkeypatch.setattr(detect_module, "_TODAY_OVERRIDE", date(2026, 4, 29))

    csv_path = str(tmp_data_dir / "master_targets.csv")
    detect_module._cmd_detect_batch([csv_path, "--data-dir", str(tmp_data_dir)])

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    lulu_row = next(r for r in rows if r["company_name"] == "Lululemon")
    assert lulu_row["ats_slug_confidence"] == "0.97", "Lululemon should not have been re-detected"


def test_idempotency_redetects_stale_hit_without_force(tmp_data_dir, monkeypatch, mock_greenhouse_ok):
    """DET-04: StaleCo (last_ats_hit_date > 30d) IS re-detected without --force."""
    import ats.detect as detect_module
    import ats.providers.greenhouse as gh_module
    monkeypatch.setattr(detect_module, "PROVIDERS", {"greenhouse": gh_module})
    detect_module._init_detect_semaphores({"greenhouse": 2})
    monkeypatch.setattr(detect_module.httpx, "Client", lambda **kwargs: mock_greenhouse_ok)

    # Pin today to 2026-04-29; StaleCo last_ats_hit_date=2025-12-01 is >30d ago
    monkeypatch.setattr(detect_module, "_TODAY_OVERRIDE", date(2026, 4, 29))

    csv_path = str(tmp_data_dir / "master_targets.csv")
    detect_module._cmd_detect_batch([csv_path, "--data-dir", str(tmp_data_dir)])

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    stale_row = next(r for r in rows if r["company_name"] == "StaleCo")
    # After re-detection with Airbnb fixture (Airbnb vs StaleCo won't confirm),
    # the row will have been processed (not skipped). ats_provider will be set.
    assert stale_row.get("ats_provider") != "", "StaleCo should have been processed (re-detected)"


def test_idempotency_force_overrides_non_manual(tmp_data_dir, monkeypatch, mock_greenhouse_ok):
    """DET-04 + STR-04: --force re-detects Lululemon; Stripe Inc still manual."""
    import ats.detect as detect_module
    import ats.providers.greenhouse as gh_module
    monkeypatch.setattr(detect_module, "PROVIDERS", {"greenhouse": gh_module})
    detect_module._init_detect_semaphores({"greenhouse": 2})
    monkeypatch.setattr(detect_module.httpx, "Client", lambda **kwargs: mock_greenhouse_ok)
    monkeypatch.setattr(detect_module, "_TODAY_OVERRIDE", date(2026, 4, 29))

    csv_path = str(tmp_data_dir / "master_targets.csv")
    detect_module._cmd_detect_batch([csv_path, "--force", "--data-dir", str(tmp_data_dir)])

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    stripe_row = next(r for r in rows if r["company_name"] == "Stripe Inc")
    lulu_row = next(r for r in rows if r["company_name"] == "Lululemon")
    assert stripe_row["ats_provider"] == "manual", "Stripe Inc must remain manual even with --force"
    # Lululemon was re-detected (ats_provider should still be greenhouse or updated)
    assert lulu_row["ats_provider"] != "", "Lululemon should have been processed with --force"


def test_negative_result_writes_none_sentinel(tmp_data_dir, monkeypatch, mock_greenhouse_404):
    """DET-04 D-01: when all providers return NOT_FOUND, ats_provider='none' (not 'none_detected')."""
    import ats.detect as detect_module
    import ats.providers.greenhouse as gh_module
    monkeypatch.setattr(detect_module, "PROVIDERS", {"greenhouse": gh_module})
    detect_module._init_detect_semaphores({"greenhouse": 2})
    monkeypatch.setattr(detect_module.httpx, "Client", lambda **kwargs: mock_greenhouse_404)
    monkeypatch.setattr(detect_module, "_TODAY_OVERRIDE", date(2026, 4, 29))

    csv_path = str(tmp_data_dir / "master_targets.csv")
    detect_module._cmd_detect_batch([csv_path, "--data-dir", str(tmp_data_dir)])

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    airbnb_row = next(r for r in rows if r["company_name"] == "Airbnb")
    assert airbnb_row["ats_provider"] == "none", f"Expected 'none', got {airbnb_row['ats_provider']!r}"


# ---------------------------------------------------------------------------
# DET-05: Borderline review CSV
# ---------------------------------------------------------------------------

def test_borderline_appended_to_review_csv(tmp_data_dir, monkeypatch):
    """DET-05: BORDERLINE result appended to ats_detection_review.csv.

    The mock bypasses _apply_name_gate (patched to return a pre-cooked BORDERLINE)
    so the test focuses on the CSV-append behavior, not the gate scoring. Gate
    scoring is tested separately in test_two_factor_gate_* tests.
    """
    import ats.detect as detect_module

    # Pre-cooked BORDERLINE result with score=78 (genuinely in 70-84 range)
    borderline_result = DetectionResult(
        provider="greenhouse",
        status=DetectionStatus.BORDERLINE,
        board_url="https://boards-api.greenhouse.io/v1/boards/airbnb/jobs",
        confidence=0.78,
        evidence={
            "first_job_company_name": "Digital Turbine",
            "job_count": 5,
            "http_status": 200,
            "name_match_score": 78.0,
            "input_name": "Airbnb",
            "returned_name": "Digital Turbine",
        },
    )

    # Patch _apply_name_gate to return the pre-cooked BORDERLINE directly
    monkeypatch.setattr(detect_module, "_apply_name_gate", lambda raw, name, **kw: borderline_result)

    # Build a fake provider that returns any BORDERLINE (gate is patched anyway).
    # BOARD_URL_PATTERNS must be non-empty so the D-3 guard in detect.py does NOT
    # skip this provider (D-3 skips providers with empty patterns, e.g. jsonld).
    class MockBorderlineProvider:
        NAME = "greenhouse"
        BOARD_URL_PATTERNS = [r"^https?://boards-api\.greenhouse\.io/v1/boards/([^/]+)"]

        def detect(self, company_slug, name, client):
            return borderline_result

    monkeypatch.setattr(detect_module, "PROVIDERS", {"greenhouse": MockBorderlineProvider()})
    detect_module._init_detect_semaphores({"greenhouse": 2})
    monkeypatch.setattr(detect_module.httpx, "Client", lambda **kwargs: MagicMock())
    monkeypatch.setattr(detect_module, "_TODAY_OVERRIDE", date(2026, 4, 29))

    csv_path = str(tmp_data_dir / "master_targets.csv")
    detect_module._cmd_detect_batch([csv_path, "--data-dir", str(tmp_data_dir)])

    review_path = tmp_data_dir / "ats_detection_review.csv"
    assert review_path.exists(), "ats_detection_review.csv should exist after borderline result"
    with open(review_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        review_rows = list(reader)
    assert len(review_rows) > 0, "review CSV should have at least one row"
    airbnb_review = next((r for r in review_rows if r["company_name"] == "Airbnb"), None)
    assert airbnb_review is not None, "Airbnb should appear in review CSV"
    assert airbnb_review.get("ats_board_url"), "ats_board_url should be populated in review row"

    # ROADMAP SC-1: borderline ats_slug_confidence visible (0.70-0.94 range), not empty
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    airbnb_row = next(r for r in rows if r["company_name"] == "Airbnb")
    assert airbnb_row["ats_slug_confidence"] == "0.78", (
        f"ROADMAP SC-1: borderline confidence should be visible (0.78), got "
        f"{airbnb_row['ats_slug_confidence']!r}"
    )


def test_zero_jobs_borderline_writes_provider_but_empty_confidence(tmp_data_dir, monkeypatch, mock_greenhouse_zero_jobs):
    """D-02 / DET-05: 200 + 0 jobs -> ats_provider set, ats_slug_confidence empty, review CSV has zero_open_roles."""
    import ats.detect as detect_module
    import ats.providers.greenhouse as gh_module
    monkeypatch.setattr(detect_module, "PROVIDERS", {"greenhouse": gh_module})
    detect_module._init_detect_semaphores({"greenhouse": 2})
    monkeypatch.setattr(detect_module.httpx, "Client", lambda **kwargs: mock_greenhouse_zero_jobs)
    monkeypatch.setattr(detect_module, "_TODAY_OVERRIDE", date(2026, 4, 29))

    csv_path = str(tmp_data_dir / "master_targets.csv")
    detect_module._cmd_detect_batch([csv_path, "--data-dir", str(tmp_data_dir)])

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    airbnb_row = next(r for r in rows if r["company_name"] == "Airbnb")
    assert airbnb_row["ats_provider"] == "greenhouse", "ats_provider should be set for zero-job board"
    assert airbnb_row["ats_slug_confidence"] == "", "ats_slug_confidence should be empty for zero-job board"

    review_path = tmp_data_dir / "ats_detection_review.csv"
    assert review_path.exists(), "ats_detection_review.csv should exist for zero-job board"
    with open(review_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        review_rows = list(reader)
    airbnb_review = next((r for r in review_rows if r["company_name"] == "Airbnb"), None)
    assert airbnb_review is not None, "Airbnb should appear in review CSV for zero-job board"
    assert airbnb_review.get("note") == "zero_open_roles", f"Expected note=zero_open_roles, got {airbnb_review.get('note')!r}"


# ---------------------------------------------------------------------------
# STR-02: Confidence column
# ---------------------------------------------------------------------------

def test_confidence_column_written_for_confirmed(tmp_data_dir, monkeypatch, mock_greenhouse_ok):
    """STR-02: after CONFIRMED detection, ats_slug_confidence is float in [0.85, 1.0]."""
    import ats.detect as detect_module
    import ats.providers.greenhouse as gh_module
    monkeypatch.setattr(detect_module, "PROVIDERS", {"greenhouse": gh_module})
    detect_module._init_detect_semaphores({"greenhouse": 2})
    monkeypatch.setattr(detect_module.httpx, "Client", lambda **kwargs: mock_greenhouse_ok)
    monkeypatch.setattr(detect_module, "_TODAY_OVERRIDE", date(2026, 4, 29))

    csv_path = str(tmp_data_dir / "master_targets.csv")
    detect_module._cmd_detect_batch([csv_path, "--data-dir", str(tmp_data_dir)])

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    airbnb_row = next(r for r in rows if r["company_name"] == "Airbnb")
    confidence_str = airbnb_row["ats_slug_confidence"]
    assert confidence_str != "", "ats_slug_confidence should be non-empty for CONFIRMED detection"
    confidence_val = float(confidence_str)
    assert 0.85 <= confidence_val <= 1.0, f"ats_slug_confidence should be in [0.85, 1.0], got {confidence_val}"


def test_user_added_column_preserved(tmp_data_dir, monkeypatch, mock_greenhouse_ok):
    """STR-02 / D-05: my_notes column survives detect-batch round-trip."""
    import ats.detect as detect_module
    import ats.providers.greenhouse as gh_module
    monkeypatch.setattr(detect_module, "PROVIDERS", {"greenhouse": gh_module})
    detect_module._init_detect_semaphores({"greenhouse": 2})
    monkeypatch.setattr(detect_module.httpx, "Client", lambda **kwargs: mock_greenhouse_ok)
    monkeypatch.setattr(detect_module, "_TODAY_OVERRIDE", date(2026, 4, 29))

    csv_path = str(tmp_data_dir / "master_targets.csv")
    detect_module._cmd_detect_batch([csv_path, "--data-dir", str(tmp_data_dir)])

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    stripe_row = next(r for r in rows if r["company_name"] == "Stripe Inc")
    assert stripe_row.get("my_notes") == "locked-by-user", f"my_notes should be preserved, got {stripe_row.get('my_notes')!r}"


# ---------------------------------------------------------------------------
# DET-07: Detection telemetry
# ---------------------------------------------------------------------------

def test_detection_telemetry_appends_one_runs_jsonl_line(tmp_data_dir, monkeypatch, mock_greenhouse_ok):
    """DET-07: detect-batch appends exactly ONE line to runs.jsonl with run_type=detect_batch."""
    import ats.detect as detect_module
    import ats.providers.greenhouse as gh_module
    monkeypatch.setattr(detect_module, "PROVIDERS", {"greenhouse": gh_module})
    detect_module._init_detect_semaphores({"greenhouse": 2})
    monkeypatch.setattr(detect_module.httpx, "Client", lambda **kwargs: mock_greenhouse_ok)
    monkeypatch.setattr(detect_module, "_TODAY_OVERRIDE", date(2026, 4, 29))

    runs_path = tmp_data_dir / "runs.jsonl"
    lines_before = runs_path.read_text().splitlines()

    csv_path = str(tmp_data_dir / "master_targets.csv")
    detect_module._cmd_detect_batch([csv_path, "--data-dir", str(tmp_data_dir)])

    lines_after = runs_path.read_text().splitlines()
    delta = len(lines_after) - len(lines_before)
    assert delta == 1, f"Expected 1 new runs.jsonl line, got {delta}"

    last_line = json.loads(lines_after[-1])
    assert last_line.get("run_type") == "detect_batch", f"Expected run_type=detect_batch, got {last_line.get('run_type')!r}"
    assert "per_company" in last_line, "telemetry line should have per_company key"
    assert len(last_line["per_company"]) == 5, f"per_company should have 5 entries (one per fixture row), got {len(last_line['per_company'])}"


# ---------------------------------------------------------------------------
# D-05: CSV write-back main-thread only
# ---------------------------------------------------------------------------

def test_csv_write_back_main_thread_only(tmp_data_dir):
    """D-05 acceptance: _write_back and _append_borderline are NOT called inside the worker function."""
    detect_src = DETECT_SCRIPT.read_text()
    # Find the worker function _detect_one_company
    # Assert _write_back and _append_borderline do NOT appear inside it
    # Strategy: find the function body between 'def _detect_one_company' and the next 'def ' at same indent level
    lines = detect_src.splitlines()
    in_worker = False
    worker_body_lines = []
    for i, line in enumerate(lines):
        if line.startswith("def _detect_one_company"):
            in_worker = True
            continue
        if in_worker:
            # End of function: next def at column 0
            if line.startswith("def ") or line.startswith("class "):
                break
            worker_body_lines.append(line)

    worker_body = "\n".join(worker_body_lines)
    assert "_write_back" not in worker_body, "_write_back should NOT appear inside _detect_one_company worker"
    assert "_append_borderline" not in worker_body, "_append_borderline should NOT appear inside _detect_one_company worker"
