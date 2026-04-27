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
]

MASTER_TARGETS_VERSION = 3  # v3: trimmed dead-weight cols (pipeline_tier, location, warm_path, already_applied, roles_applied_for, fit_score, what_they_do). Keeps `notes` as user free-form column outside schema.


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
]

# Column widths in the same order as TRACKER_COLUMNS. Adjust here if a
# column needs more room — don't fiddle with widths in tracker_utils.py.
TRACKER_COL_WIDTHS = [12, 45, 20, 25, 20, 8, 6, 12, 40, 50, 14, 30, 16, 50]


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
