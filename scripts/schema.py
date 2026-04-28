"""
schema.py — Single source of truth for Job Scout column schemas.

ALL Python scripts and prompt documents reference column names from here.
Do NOT inline column lists anywhere else. If you need to add or rename a column,
do it here and update validate_data.py to handle the migration.

This module is import-only — it has no side effects and no CLI.
"""

# =====================================================================
# master_targets.csv  — the company database
# =====================================================================
#
# Every company the scout knows about lives here, one row per company.
# /scout-setup populates this from LinkedIn connections + user-provided
# CSVs. /scout-run updates last_checked, application_status, and notes.
#
# DO NOT add columns without bumping MASTER_TARGETS_VERSION and adding
# a migration in validate_data.py.

MASTER_TARGETS_COLUMNS = [
    "company_name",            # Display name. Used as join key after normalization.
    "industry",                # Free-text industry tag (e-commerce, SaaS, retail, etc.)
    "career_page_url",         # Direct URL to careers page. Used in Pass 1 of /scout-run.
    "ats_provider",            # Detected ATS: greenhouse|lever|workday|ashby|smartrecruiters|other|unknown
    "ats_board_url",           # If ATS is detected, the board URL (e.g. boards.greenhouse.io/acme)
    "connection_names",        # "; "-joined list of named LinkedIn connections at the company.
    "linkedin_connection_count",  # Integer count.
    "application_status",      # Free text — "Applied 2026-03-12 / no response", "Dead", etc.
    "fit_notes",               # Why this company matters (or doesn't). Free text.
    "last_checked",            # ISO date the scout last looked at this company. Used to prioritize stale ones.
    "data_source",             # Where this row came from: linkedin_connections, user_csv, scout_discovered, etc.
    "ats_slug_confidence",     # v=4: float 0.0–1.0 (or empty) — populated by /scout-detect (Phase 3)
    "last_ats_hit_date",       # v=4: ISO date (or empty) — last day Pass 1 returned ≥1 listing for this company
]

# v4 (2026-04 v0.4): added ats_slug_confidence + last_ats_hit_date for ATS-first sourcing.
# Migration is column-by-column additive in validate_data.validate_master_targets()
# — version bump is a user-visible breadcrumb only, NOT a migration dispatch trigger.
MASTER_TARGETS_VERSION = 4


# =====================================================================
# Status enum — drives application_status validation on tracker append
# =====================================================================
#
# Eliminates magic-string drift (`Dead` vs `dead` vs `DEAD`). Validation runs
# in tracker_utils.append_rows; unknown values warn-and-coerce to "Active"
# (preserves the existing "never deletes user data" semantic from validate_data.py).
#
# "New" is the canonical default for freshly-found, untriaged rows — preserves the
# v=3 tracker_utils.append_rows() default of `row_dict.get("status", "New")`.

STATUS_VALUES = frozenset({
    "",                # not yet processed
    "New",             # freshly found, not yet triaged (default for absent status)
    "Active",          # currently considering
    "Applied",         # applied, awaiting response
    "Interviewing",    # interview in progress
    "Offer",           # offer extended
    "Rejected",        # explicit rejection
    "Dead",            # company is no longer hiring / role gone
    "Closed",          # we closed the loop ourselves (declined/withdrew)
})


def normalize_application_status(value):
    """
    Validate or coerce an application_status value against STATUS_VALUES.

    Returns (canonical_value, was_coerced).
      - None -> ("", False)
      - exact case match -> (canonical, False)
      - case-insensitive match -> (canonical, True)
      - unknown -> (s, True)  # warn-and-pass-through: never rewrite user data

    Locked decision: unknown values are preserved verbatim. The caller
    (tracker_utils.append_rows) emits a stderr warning so the user can
    decide whether to fix the typo or extend STATUS_VALUES — but we
    never silently destroy user annotations like "Stale — Verify"
    or "Pending follow-up" by rewriting them to a canonical default.
    """
    if value is None:
        return "", False
    s = str(value).strip()
    for canonical in STATUS_VALUES:
        if s.lower() == canonical.lower():
            return canonical, s != canonical
    return s, True


# =====================================================================
# JobScout_Tracker.xlsx  — the running per-listing tracker
# =====================================================================
#
# Append-only record of every job listing the scout has surfaced. Dedup is
# by LinkedIn job ID (extract_job_id in tracker_utils.py).
#
# The header row uses these EXACT strings — display formatting matters
# because the user filters/sorts in Excel.

TRACKER_COLUMNS = [
    "Date Found",
    "Job Title",
    "Company",
    "Location",
    "Comp Range",
    "Score",
    "Tier",
    "Connections",
    "Match Notes",
    "Job URL",
    "Resume Tailored",
    "Resume File",
    "Status",
    "Notes",
    # v0.4: source + ats_provider tracking — values are ats:greenhouse|ats:lever|...|linkedin or empty
    "Source",
    "ATS Provider",
]

# Lowercase keys used in the JSON payload passed to tracker_utils.py append.
# Order MUST mirror TRACKER_COLUMNS — append_rows depends on this alignment.
TRACKER_JSON_KEYS = [
    "date_found",
    "job_title",
    "company",
    "location",
    "comp_range",
    "score",
    "tier",
    "connections",
    "match_notes",
    "job_url",
    "resume_tailored",
    "resume_file",
    "status",
    "notes",
    # v0.4: source + ats_provider tracking — values are ats:greenhouse|ats:lever|...|linkedin or empty
    "source",
    "ats_provider",
]

# Column widths in the same order as TRACKER_COLUMNS. Adjust here if a
# column needs more room — don't fiddle with widths in tracker_utils.py.
TRACKER_COL_WIDTHS = [12, 45, 20, 25, 20, 8, 6, 12, 40, 50, 14, 30, 16, 50, 18, 16]


# =====================================================================
# Tier thresholds and stale detection — shared between scripts and prompts
# =====================================================================

# LinkedIn job IDs below this threshold tend to be 6+ months old. Used by
# tracker_utils.py to flag listings that LinkedIn is recycling in search.
STALE_LINKEDIN_JOB_ID_THRESHOLD = 4_200_000_000

# Default tier thresholds. Overridden by config.json at runtime — these are
# only used when config is missing.
DEFAULT_TIER_A_THRESHOLD = 75
DEFAULT_TIER_B_THRESHOLD = 55
DEFAULT_TIER_C_THRESHOLD = 40


# =====================================================================
# Helpers
# =====================================================================

def empty_master_target_row():
    """Return a dict with every master_targets column set to empty string."""
    return {col: "" for col in MASTER_TARGETS_COLUMNS}


def empty_tracker_row():
    """Return a dict with every tracker JSON key set to empty string."""
    return {key: "" for key in TRACKER_JSON_KEYS}
