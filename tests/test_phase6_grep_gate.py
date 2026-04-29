"""test_phase6_grep_gate.py — Phase 6 phase-wide gate.

Verifies all Phase 6 requirements via grep + JSON + CLI checks:
  OUT-03 (stdout summary mirror), OUT-04 (legacy deletion),
  OUT-05 (chrome-setup trim), OUT-06 (version + README),
  OUT-07 (milestone-bar CLI smoke), CON-16 (version lockstep),
  CON-17 (inline column list deleted), CON-18 (PII callout),
  CON-19 (.gitignore template), CON-21 (post-write validation).

Runs in ~5 seconds. Add to the full suite for regression protection.

Run with:
    ~/.job-scout-venv/bin/python3 -m pytest tests/test_phase6_grep_gate.py -x -q
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _grep_lines(pattern: str, paths: list, extra_args: list = None) -> list:
    """Run grep and return matching lines (for failure-message context).

    Returns empty list when grep finds 0 matches (exit 1 is 'no match').
    Raises RuntimeError for any grep exit code other than 0 or 1.
    """
    cmd = ["grep", "-rn", pattern]
    if extra_args:
        cmd.extend(extra_args)
    cmd.extend(paths)
    result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)
    if result.returncode == 1:
        # grep exit 1 = zero matches — that's the success condition for "should be 0" gates
        return []
    if result.returncode == 0:
        return [line for line in result.stdout.splitlines() if line.strip()]
    raise RuntimeError(f"grep error (exit {result.returncode}): {result.stderr}")


def _grep_count(pattern: str, paths: list, extra_args: list = None) -> int:
    """Run grep and return match count (number of lines matched)."""
    return len(_grep_lines(pattern, paths, extra_args))


# ---------------------------------------------------------------------------
# P2: [ATS-PREVIEW] brand cleanup
# ---------------------------------------------------------------------------

def test_phase6_gate_no_ats_preview_brand():
    """P2: No [ATS-PREVIEW] brand markers anywhere in skills/ + scripts/."""
    matches = _grep_lines(
        r"\[ATS-PREVIEW\]",
        ["skills/", "scripts/"],
        extra_args=["--include=*.md", "--include=*.py"],
    )
    assert matches == [], (
        "[ATS-PREVIEW] markers still present (Plan 06-04 should have deleted all 9+5+1):\n"
        + "\n".join(matches)
    )


# ---------------------------------------------------------------------------
# OUT-04: Marketing-page Chrome scraping prose deleted
# ---------------------------------------------------------------------------

def test_phase6_gate_no_marketing_page_prose():
    """OUT-04: Marketing-page Chrome scraping prose deleted from skills/ + scripts/.

    Filters:
    - Lines containing 'career_page_url' (legitimate schema column references — Pitfall 1).
    - Lines containing 'NO.*marketing' or 'no.*marketing-page' — these are documentation
      statements that the path was DELETED (e.g. "There are NO marketing-page Chrome calls"),
      not instructions to perform scraping. Such lines confirm the deletion, not undo it.
    """
    matches = _grep_lines(
        "marketing-page\\|marketing page",
        ["skills/", "scripts/"],
        extra_args=[
            "-i",
            "--exclude-dir=fixtures",
            "--exclude-dir=__pycache__",
        ],
    )
    # Filter out lines that document the ABSENCE of marketing-page calls (deletion confirmations).
    # Also filter out career_page_url column references (schema column — not a scraping path).
    offending = [
        line for line in matches
        if "career_page_url" not in line
        and not re.search(r"\bNO\b.*marketing.page|marketing.page.*\bNO\b", line, re.IGNORECASE)
        and not re.search(r"deletes.*marketing.page|marketing.page.*deleted", line, re.IGNORECASE)
    ]
    assert offending == [], (
        "marketing-page scraping prose still present (Plan 06-04 should have deleted it):\n"
        + "\n".join(offending)
    )


# ---------------------------------------------------------------------------
# OUT-04: career-page scraping prose deleted (Pitfall 1 — keep column refs)
# ---------------------------------------------------------------------------

def test_phase6_gate_no_career_page_scraping_prose():
    """OUT-04: career-page scraping prose deleted; column refs and source tags preserved (Pitfall 1).

    Filters legitimately kept references:
    - career_page_url — schema column name (scripts/schema.py, column mapping)
    - career_page — source tag in report format spec ("Source: <career_page | ats:...>")
      and column-name alias in consolidate_targets.py mapping
    - career page in search-config.md — documents the ATS detection flow (not scraping)
    Only `careers-html` (the old Chrome scraping selector) with no schema context is
    the true positive for this gate. All current matches are legitimate column/tag refs.
    """
    raw = _grep_lines(
        "career_page\\|careers-html",
        ["skills/", "scripts/"],
        extra_args=[
            "-i",
            "--exclude-dir=fixtures",
            "--exclude-dir=__pycache__",
        ],
    )
    # Filter out:
    # 1. Lines containing 'career_page_url' (schema column — Pitfall 1 guard)
    # 2. Lines containing 'career_page' as a source tag or column alias (not a scraping path)
    # 3. Lines containing 'careers-html' only matter if they're actual scraping instructions
    #    (not schema/column context); currently no careers-html matches exist post-Phase-6.
    offending = [
        line for line in raw
        if "career_page_url" not in line
        and not re.search(r"\bcareer_page\b", line)  # source tag & column alias refs
    ]
    assert offending == [], (
        "career-page scraping prose (excluding schema column and source tag refs) still present:\n"
        + "\n".join(offending)
    )


# ---------------------------------------------------------------------------
# OUT-04 + OUT-05: chrome-setup.md scoped to LinkedIn-only
# ---------------------------------------------------------------------------

def test_phase6_gate_chrome_setup_md_linkedin_only():
    """OUT-04 + OUT-05: chrome-setup.md contains no marketing or career-page scraping prose."""
    chrome_setup = (
        PROJECT_ROOT / "skills" / "job-scout" / "references" / "chrome-setup.md"
    )
    assert chrome_setup.exists(), f"chrome-setup.md not found at {chrome_setup}"
    content = chrome_setup.read_text()
    # Both patterns must be absent — marketing prose AND career-page scraping prose
    bad = re.findall(r"marketing|career.*page.*scrape", content, re.IGNORECASE)
    assert bad == [], (
        f"chrome-setup.md has marketing/career-page scraping prose that should be deleted: {bad}"
    )


# ---------------------------------------------------------------------------
# CON-16 + OUT-06: Version lockstep — 4 SKILL.md + plugin.json all at v0.4.0
# ---------------------------------------------------------------------------

def test_phase6_gate_version_lockstep():
    """CON-16 + OUT-06: Exactly 4 SKILL.md frontmatter version lines AND plugin.json all at 0.4.0."""
    skill_versions = []
    for skill_md in sorted((PROJECT_ROOT / "skills").glob("*/SKILL.md")):
        for line in skill_md.read_text().splitlines():
            if line.startswith("version:"):
                skill_versions.append((skill_md.parent.name, line.strip()))
                break

    assert len(skill_versions) == 4, (
        f"Expected exactly 4 SKILL.md files with 'version:' frontmatter, "
        f"got {len(skill_versions)}: {skill_versions}"
    )
    for skill_name, version_line in skill_versions:
        assert version_line == "version: 0.4.0", (
            f"skills/{skill_name}/SKILL.md: expected 'version: 0.4.0', "
            f"got '{version_line}'"
        )

    plugin_json_path = PROJECT_ROOT / ".claude-plugin" / "plugin.json"
    assert plugin_json_path.exists(), f"plugin.json not found at {plugin_json_path}"
    plugin = json.loads(plugin_json_path.read_text())
    assert plugin.get("version") == "0.4.0", (
        f"plugin.json version expected '0.4.0', got '{plugin.get('version')}'"
    )


# ---------------------------------------------------------------------------
# CON-17: Inline column list deleted; schema.py reference present
# ---------------------------------------------------------------------------

def test_phase6_gate_no_inline_column_list_in_job_scout_skill():
    """CON-17: Inline column list deleted from skills/job-scout/SKILL.md; schema.py reference present."""
    skill_path = PROJECT_ROOT / "skills" / "job-scout" / "SKILL.md"
    assert skill_path.exists(), f"skills/job-scout/SKILL.md not found at {skill_path}"
    text = skill_path.read_text()
    assert "Includes `company_name`" not in text, (
        "CON-17: inline column list (starting with 'Includes `company_name`') still present "
        "in skills/job-scout/SKILL.md — it should reference schema.py instead"
    )
    assert "scripts/schema.py:MASTER_TARGETS_COLUMNS" in text, (
        "CON-17: reference to 'scripts/schema.py:MASTER_TARGETS_COLUMNS' missing from "
        "skills/job-scout/SKILL.md — Plan 06-03 should have added this pointer"
    )


# ---------------------------------------------------------------------------
# CON-18 + CON-19: PII callout + .gitignore template in scout-setup/SKILL.md
# ---------------------------------------------------------------------------

def test_phase6_gate_pii_callout_and_gitignore_in_scout_setup_skill():
    """CON-18 + CON-19: PII callout and .gitignore template present in scout-setup/SKILL.md."""
    skill_path = PROJECT_ROOT / "skills" / "scout-setup" / "SKILL.md"
    assert skill_path.exists(), f"skills/scout-setup/SKILL.md not found at {skill_path}"
    text = skill_path.read_text()
    required_phrases = [
        "iCloud Drive",
        "Dropbox / OneDrive",
        "connections_summary.csv",
        "candidate.resume_path",
        "redact",
        "Job Scout data directory",
    ]
    missing = [phrase for phrase in required_phrases if phrase not in text]
    assert missing == [], (
        f"CON-18/CON-19: The following required PII callout / .gitignore phrases are "
        f"missing from skills/scout-setup/SKILL.md:\n  " + "\n  ".join(missing)
    )


# ---------------------------------------------------------------------------
# CON-21 + OUT-02 + OUT-03: Step 7.5 + Run Summary + stdout mirror
# ---------------------------------------------------------------------------

def test_phase6_gate_post_run_validation_in_scout_run_skill():
    """CON-21 + OUT-02 + OUT-03: Step 7.5 + post-run validation + Run Summary + milestone-bar."""
    skill_path = PROJECT_ROOT / "skills" / "scout-run" / "SKILL.md"
    assert skill_path.exists(), f"skills/scout-run/SKILL.md not found at {skill_path}"
    text = skill_path.read_text()

    required_phrases = [
        "## Step 7.5",
        "post-run validation failed",
        "Run Summary",
        "milestone-bar",
    ]
    missing = [phrase for phrase in required_phrases if phrase not in text]
    assert missing == [], (
        f"CON-21/OUT-02/OUT-03: The following required phrases are missing from "
        f"skills/scout-run/SKILL.md:\n  " + "\n  ".join(missing)
    )

    # P7 guard: A-tier count check MUST use the tier field from new_rows.json,
    # NOT grep -c "^### " on report headers (Pitfall 7).
    # Matches patterns like:  r.get('tier') == 'A'  OR  tier == 'A'  OR  tier == "A"
    assert re.search(r"""(?:get\(['"]tier['"]\)|tier)\s*==\s*['"]A['"]""", text), (
        "P7: skills/scout-run/SKILL.md should use the 'tier' field from new_rows.json "
        "for A-tier counting (e.g., r.get('tier') == 'A'), not grep on report headers"
    )
    # If grep -c "^### " appears, it MUST only appear as a negated Pitfall-7 warning
    # (i.e. preceded by "NOT"), never as an actual shell instruction to execute.
    # The positive tier-field check above is the real P7 guard; this is belt-and-suspenders.
    grep_header_lines = [
        line for line in text.splitlines()
        if 'grep -c "^### "' in line and " NOT " not in line and "— NOT" not in line
    ]
    assert grep_header_lines == [], (
        "P7: 'grep -c \"^### \"' appears as an INSTRUCTION (not a prohibition) in "
        "scout-run/SKILL.md — A-tier validation must use new_rows.json tier field:\n"
        + "\n".join(grep_header_lines)
    )


# ---------------------------------------------------------------------------
# OUT-07: milestone-bar CLI smoke test
# ---------------------------------------------------------------------------

def test_phase6_gate_milestone_bar_cli_smoke(tmp_path):
    """OUT-07: milestone-bar CLI exits 0 with valid JSON over a synthetic runs.jsonl."""
    runs_jsonl = tmp_path / "runs.jsonl"
    # Single run: ats=4, linkedin=2, wall_clock=200s → pass1_share=66.7% (≥60% bar met)
    line = {
        "timestamp": "2026-04-29T10:00:00Z",
        "wall_clock_seconds": 200.0,
        "providers": {},
        "per_company_provider": {},
        "ab_tier_counts": {"ats": 4, "linkedin": 2, "total_ab": 6},
    }
    runs_jsonl.write_text(json.dumps(line) + "\n")

    venv_py = Path.home() / ".job-scout-venv" / "bin" / "python3"
    py = str(venv_py) if venv_py.exists() else sys.executable

    result = subprocess.run(
        [py, "scripts/ats/runs_log.py", "milestone-bar", str(runs_jsonl)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"milestone-bar CLI exited {result.returncode}.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )

    # Parse JSON output (CONVENTIONS.md: JSON is the final print, may be whole stdout)
    try:
        data = json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        # Fallback: try last non-empty line
        lines_out = [l for l in result.stdout.splitlines() if l.strip()]
        assert lines_out, "milestone-bar CLI produced no output"
        data = json.loads(lines_out[-1])

    required_keys = {
        "lookback_used",
        "pass1_share_pct",
        "wall_clock_avg_seconds",
        "pass1_bar_met",
        "wall_clock_bar_met",
        "bar_met",
        "runs_examined",
    }
    missing_keys = required_keys - set(data.keys())
    assert not missing_keys, (
        f"milestone-bar JSON missing required keys: {missing_keys}. "
        f"Got: {set(data.keys())}"
    )

    # D-1 lock: pass1_share = 4/(4+2) * 100 = 66.7%
    assert data["pass1_share_pct"] == pytest.approx(66.7, abs=0.1), (
        f"Expected pass1_share_pct ≈ 66.7 (4 ATS / 6 total), "
        f"got {data['pass1_share_pct']!r}"
    )
    # 66.7% ≥ 60% AND 200s ≤ 300s → bar_met must be True
    assert data["bar_met"] is True, (
        f"Expected bar_met=True (66.7% ≥ 60% AND 200s ≤ 300s), got {data['bar_met']!r}"
    )
