"""test_runs_log_phase6.py — Wave 0 RED tests for OUT-07 (milestone-bar subcommand).

Wave 0 commits these RED. Wave 1 (Plan 06-02 runs_log.py) turns them GREEN.

D-1 lock: pass1_share = sum(ats over last N runs) / sum(ats + linkedin over last N runs).
D-2 lock: wall_clock_avg = mean of existing wall_clock_seconds (ATS-fetch only).

Run with:
    ~/.job-scout-venv/bin/python3 -m pytest tests/test_runs_log_phase6.py -x -q
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

SCRIPT = PROJECT_ROOT / "scripts" / "ats" / "runs_log.py"

# ---------------------------------------------------------------------------
# OUT-07 (D-1): Pass-1 share from ab_tier_counts
# ---------------------------------------------------------------------------


def test_milestone_bar_pass1_share():
    """OUT-07 D-1: compute_milestone_bar returns correct pass1_share from ab_tier_counts.

    5 runs each with ats=4, linkedin=2. Pass-1 share = 4/(4+2) = 66.67%.
    D-1 lock: pass1_share = sum(ats) / sum(ats + linkedin) across all lookback runs.
    """
    from ats.runs_log import compute_milestone_bar  # RED until Plan 06-02 lands

    lines = [
        {
            "timestamp": f"2026-04-2{i}T10:00:00Z",
            "wall_clock_seconds": 200.0,
            "ab_tier_counts": {"ats": 4, "linkedin": 2, "total_ab": 6},
        }
        for i in range(5)
    ]
    result = compute_milestone_bar(lines, lookback=5)

    assert result["pass1_share_pct"] == pytest.approx(66.7, abs=0.1), (
        f"Expected pass1_share_pct ~66.7, got {result['pass1_share_pct']!r}"
    )
    assert result["pass1_bar_met"] is True, (
        f"Expected pass1_bar_met=True (66.7 >= 60%), got {result['pass1_bar_met']!r}"
    )
    assert result["lookback_used"] == 5
    assert "bar_met" in result


# ---------------------------------------------------------------------------
# OUT-07 (D-2): Wall-clock average from existing wall_clock_seconds field
# ---------------------------------------------------------------------------


def test_milestone_bar_wall_clock():
    """OUT-07 D-2: compute_milestone_bar computes wall_clock_avg as mean of wall_clock_seconds.

    5 runs with wall_clock_seconds=[100, 200, 300, 400, 500]. Mean = 300.0.
    D-2 lock: uses the existing wall_clock_seconds field (ATS-fetch duration only).
    wall_clock_bar_met at exactly 300.0 seconds — boundary test for <= target.
    """
    from ats.runs_log import compute_milestone_bar  # RED until Plan 06-02 lands

    lines = [
        {
            "timestamp": f"2026-04-2{i}T10:00:00Z",
            "wall_clock_seconds": float(val),
            "ab_tier_counts": {"ats": 1, "linkedin": 0, "total_ab": 1},
        }
        for i, val in enumerate([100, 200, 300, 400, 500])
    ]
    result = compute_milestone_bar(lines, lookback=5)

    assert result["wall_clock_avg_seconds"] == pytest.approx(300.0, abs=0.1), (
        f"Expected wall_clock_avg_seconds ~300.0, got {result['wall_clock_avg_seconds']!r}"
    )
    # Boundary: 300.0 <= 300.0 target → wall_clock_bar_met should be True
    # If implementation uses strict <, this assertion goes RED and implementer must use <=
    assert result["wall_clock_bar_met"] is True, (
        f"Expected wall_clock_bar_met=True at boundary 300.0 <= 300.0, "
        f"got {result['wall_clock_bar_met']!r}"
    )
    assert result["lookback_used"] == 5


# ---------------------------------------------------------------------------
# OUT-07: milestone-bar CLI subcommand smoke test
# ---------------------------------------------------------------------------


def test_milestone_bar_cli(tmp_path):
    """OUT-07: milestone-bar CLI subcommand exits 0 and prints valid JSON.

    Uses subprocess to invoke runs_log.py milestone-bar <path>.
    Asserts exit code 0 and JSON output has all 6 required keys.
    """
    runs_log_path = tmp_path / "runs.jsonl"
    runs_log_path.write_text(
        json.dumps({
            "timestamp": "2026-04-29T10:00:00Z",
            "wall_clock_seconds": 200.0,
            "providers": {},
            "per_company_provider": {},
            "ab_tier_counts": {"ats": 4, "linkedin": 2, "total_ab": 6},
        }) + "\n"
    )

    # Use the venv interpreter if available (project convention); fall back to
    # sys.executable for CI portability.
    venv_python = Path.home() / ".job-scout-venv" / "bin" / "python3"
    python_exe = str(venv_python) if venv_python.exists() else sys.executable

    proc = subprocess.run(
        [python_exe, str(SCRIPT), "milestone-bar", str(runs_log_path)],
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0, (
        f"Expected exit 0, got {proc.returncode}.\nstdout: {proc.stdout}\nstderr: {proc.stderr}"
    )

    # The last line of stdout must be valid JSON (CONVENTIONS.md: JSON is final print)
    stdout_lines = [l for l in proc.stdout.strip().splitlines() if l.strip()]
    assert stdout_lines, "Expected non-empty stdout from milestone-bar"

    # Find the JSON output — last non-empty line may be part of a pretty-printed block
    # or all lines together form the JSON blob. Try parsing the full stdout.
    try:
        result = json.loads(proc.stdout.strip())
    except json.JSONDecodeError:
        # Try last line only
        result = json.loads(stdout_lines[-1])

    required_keys = {
        "lookback_used",
        "pass1_share_pct",
        "wall_clock_avg_seconds",
        "pass1_bar_met",
        "wall_clock_bar_met",
        "bar_met",
    }
    missing = required_keys - set(result.keys())
    assert not missing, (
        f"milestone-bar JSON missing required keys: {missing}. Got keys: {set(result.keys())}"
    )


# ---------------------------------------------------------------------------
# OUT-07: Short history edge case (<5 runs — do NOT error, use available)
# ---------------------------------------------------------------------------


def test_milestone_bar_short_history():
    """OUT-07: compute_milestone_bar with only 2 runs does not error.

    lookback_used must reflect actual available runs (2), not the requested lookback (5).
    pass1_share_pct must be computed from those 2 runs without raising.
    """
    from ats.runs_log import compute_milestone_bar  # RED until Plan 06-02 lands

    lines = [
        {
            "timestamp": f"2026-04-2{i}T10:00:00Z",
            "wall_clock_seconds": 180.0,
            "ab_tier_counts": {"ats": 3, "linkedin": 1, "total_ab": 4},
        }
        for i in range(2)
    ]
    result = compute_milestone_bar(lines, lookback=5)

    assert result["lookback_used"] == 2, (
        f"Expected lookback_used=2 (only 2 runs available), got {result['lookback_used']!r}"
    )
    # pass1_share from 2 runs: ats=3+3=6, linkedin=1+1=2, total=8 → 6/8 = 75%
    assert result["pass1_share_pct"] is not None, (
        "Expected pass1_share_pct to be computed from 2 available runs, got None"
    )
    assert result["pass1_share_pct"] == pytest.approx(75.0, abs=0.2), (
        f"Expected pass1_share_pct ~75.0 from 2 runs, got {result['pass1_share_pct']!r}"
    )
    assert "bar_met" in result


# ---------------------------------------------------------------------------
# OUT-07 (Pitfall 6): Missing ab_tier_counts field returns pass1_share_pct: None
# ---------------------------------------------------------------------------


def test_milestone_bar_missing_field():
    """OUT-07 Pitfall 6: absent ab_tier_counts returns pass1_share_pct=None (no crash).

    Pre-Phase-6 runs.jsonl lines don't have ab_tier_counts. When ALL lines lack
    the field, compute_milestone_bar must return pass1_share_pct=None.
    Wall-clock is still computable from the existing wall_clock_seconds field.

    Also verifies partial-missing: when SOME lines lack the field, missing lines
    are treated as {"ats": 0, "linkedin": 0} — they contribute zero but don't crash.
    """
    from ats.runs_log import compute_milestone_bar  # RED until Plan 06-02 lands

    # Case 1: ALL lines missing ab_tier_counts → pass1_share_pct must be None
    lines_all_missing = [
        {"timestamp": "2026-04-29T10:00:00Z", "wall_clock_seconds": 150.0}
    ]
    result = compute_milestone_bar(lines_all_missing, lookback=5)

    assert result["pass1_share_pct"] is None, (
        f"Expected pass1_share_pct=None when all lines lack ab_tier_counts, "
        f"got {result['pass1_share_pct']!r}"
    )
    assert result["lookback_used"] == 1, (
        f"Expected lookback_used=1 (1 run available), got {result['lookback_used']!r}"
    )
    assert result["wall_clock_avg_seconds"] == pytest.approx(150.0, abs=0.1), (
        f"Expected wall_clock_avg_seconds=150.0 (still computable), "
        f"got {result['wall_clock_avg_seconds']!r}"
    )

    # Case 2: SOME lines missing ab_tier_counts — partial coverage.
    # Missing lines treated as {"ats": 0, "linkedin": 0}: they don't crash, contribute 0.
    lines_partial = [
        {
            "timestamp": "2026-04-27T10:00:00Z",
            "wall_clock_seconds": 200.0,
            "ab_tier_counts": {"ats": 4, "linkedin": 2, "total_ab": 6},
        },
        {
            "timestamp": "2026-04-28T10:00:00Z",
            "wall_clock_seconds": 220.0,
            # no ab_tier_counts key
        },
    ]
    result_partial = compute_milestone_bar(lines_partial, lookback=5)

    # Should not crash. pass1_share_pct may be non-None (the line WITH ab_tier_counts
    # contributes; line without is skipped or treated as 0 — implementation choice).
    # We only assert no exception and that the key is present.
    assert "pass1_share_pct" in result_partial, (
        "compute_milestone_bar must return pass1_share_pct key even with partial missing fields"
    )
    assert "lookback_used" in result_partial
