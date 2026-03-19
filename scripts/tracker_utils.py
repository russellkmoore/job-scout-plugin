#!/usr/bin/env python3
"""
tracker_utils.py — Deterministic tracker management for Job Scout.

Handles reading, deduplicating, formatting, and writing the JobScout_Tracker.xlsx.
The SKILL.md calls this script instead of reimplementing formatting logic each run.
This ensures identical colors, deduplication, and structure every single time.

Usage:
    # Load existing tracker and get dedup set (returns JSON list of existing job IDs)
    python3 tracker_utils.py dedup-set /path/to/JobScout_Tracker.xlsx

    # Append new rows from a JSON file (deduplicates automatically)
    python3 tracker_utils.py append /path/to/JobScout_Tracker.xlsx /path/to/new_rows.json

    # Rebuild formatting on existing tracker (fix colors, remove dupes)
    python3 tracker_utils.py rebuild /path/to/JobScout_Tracker.xlsx
"""

import sys
import os
import json
import re
from datetime import datetime

try:
    import openpyxl
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
except ImportError:
    print("ERROR: openpyxl not installed. Run: pip install openpyxl --break-system-packages", file=sys.stderr)
    sys.exit(1)


# === CONSTANTS ===
# These NEVER change. Every run uses exactly these values.

HEADERS = [
    "Date Found", "Job Title", "Company", "Location", "Comp Range",
    "Score", "Tier", "Connections", "Match Notes", "Job URL",
    "Resume Tailored", "Resume File", "Status", "Notes"
]

# Exact hex colors — same every run, no variation
HEADER_FILL = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
A_TIER_FILL = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")  # Green
B_TIER_FILL = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")  # Yellow
C_TIER_FILL = PatternFill(start_color="F2DCDB", end_color="F2DCDB", fill_type="solid")  # Pink
STALE_FILL = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")   # Gray
NO_FILL = PatternFill()

THIN_BORDER = Border(
    left=Side(style='thin'), right=Side(style='thin'),
    top=Side(style='thin'), bottom=Side(style='thin')
)

COL_WIDTHS = [12, 45, 20, 25, 20, 8, 6, 12, 40, 50, 14, 30, 16, 50]

# LinkedIn job IDs below this threshold are likely 6+ months old
STALE_JOB_ID_THRESHOLD = 4200000000


def extract_job_id(url):
    """Extract numeric LinkedIn job ID from a URL."""
    if not url:
        return None
    match = re.search(r'(\d{10,})', str(url))
    return int(match.group(1)) if match else None


def is_stale_by_id(url):
    """Check if a listing is likely stale based on LinkedIn job ID."""
    job_id = extract_job_id(url)
    if job_id and job_id < STALE_JOB_ID_THRESHOLD:
        return True, job_id
    return False, job_id


def get_row_fill(tier, status, notes):
    """Determine the fill color for a row. Deterministic — same inputs always produce same output."""
    status_str = str(status or "")
    notes_str = str(notes or "")

    if "Stale" in status_str or "STALE" in notes_str:
        return STALE_FILL
    elif tier == "A":
        return A_TIER_FILL
    elif tier == "B":
        return B_TIER_FILL
    elif tier == "C":
        return C_TIER_FILL
    return NO_FILL


def create_empty_tracker(filepath):
    """Create a new empty tracker with proper headers and formatting."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Job Tracker"

    for col, header in enumerate(HEADERS, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal='center', wrap_text=True)
        cell.border = THIN_BORDER

    for i, w in enumerate(COL_WIDTHS, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(HEADERS))}1"

    wb.save(filepath)
    return wb


def load_tracker(filepath):
    """Load existing tracker. Returns (workbook, list of row dicts, set of existing job IDs)."""
    if not os.path.exists(filepath):
        wb = create_empty_tracker(filepath)
        return wb, [], set()

    wb = openpyxl.load_workbook(filepath)
    ws = wb.active

    rows = []
    job_ids = set()

    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, values_only=True):
        row_list = list(row)
        if len(row_list) < len(HEADERS):
            row_list.extend([None] * (len(HEADERS) - len(row_list)))
        rows.append(row_list)

        url = row_list[9]  # Job URL column
        job_id = extract_job_id(url)
        if job_id:
            job_ids.add(job_id)

    return wb, rows, job_ids


def get_dedup_set(filepath):
    """Return JSON list of existing job IDs for the SKILL.md to use for pre-search deduplication."""
    _, _, job_ids = load_tracker(filepath)
    return sorted(list(job_ids))


def append_rows(filepath, new_rows_json_path):
    """
    Append new rows to the tracker. Deduplicates by job ID.
    new_rows.json format:
    [
        {
            "date_found": "2026-03-18",
            "job_title": "VP Engineering",
            "company": "Acme Corp",
            "location": "Seattle, WA",
            "comp_range": "$200K-$300K",
            "score": 78,
            "tier": "A",
            "connections": 3,
            "match_notes": "Strong commerce fit",
            "job_url": "https://linkedin.com/jobs/view/1234567890",
            "resume_tailored": "No",
            "resume_file": "",
            "status": "New",
            "notes": ""
        }
    ]
    """
    with open(new_rows_json_path, 'r') as f:
        new_rows = json.load(f)

    _, existing_rows, existing_ids = load_tracker(filepath)

    added = 0
    skipped_dupe = 0
    skipped_stale = 0

    for row_dict in new_rows:
        url = row_dict.get("job_url", "")
        job_id = extract_job_id(url)

        # Dedup check
        if job_id and job_id in existing_ids:
            skipped_dupe += 1
            continue

        # Stale check
        stale, _ = is_stale_by_id(url)
        if stale:
            row_dict["status"] = "Stale — Verify"
            row_dict["notes"] = f"LIKELY STALE — LinkedIn job ID {job_id} suggests old listing. {row_dict.get('notes', '')}".strip()
            skipped_stale += 1
            # Still add it, but flagged — user can decide

        row_list = [
            row_dict.get("date_found", datetime.now().strftime("%Y-%m-%d")),
            row_dict.get("job_title", ""),
            row_dict.get("company", ""),
            row_dict.get("location", ""),
            row_dict.get("comp_range", ""),
            row_dict.get("score", 0),
            row_dict.get("tier", "C"),
            row_dict.get("connections", 0),
            row_dict.get("match_notes", ""),
            row_dict.get("job_url", ""),
            row_dict.get("resume_tailored", "No"),
            row_dict.get("resume_file", ""),
            row_dict.get("status", "New"),
            row_dict.get("notes", ""),
        ]

        existing_rows.append(row_list)
        if job_id:
            existing_ids.add(job_id)
        added += 1

    # Rebuild the entire file with consistent formatting
    _write_tracker(filepath, existing_rows)

    result = {
        "added": added,
        "skipped_duplicate": skipped_dupe,
        "flagged_stale": skipped_stale,
        "total_rows": len(existing_rows)
    }
    return result


def rebuild(filepath):
    """Rebuild an existing tracker: remove dupes, fix colors, fix formatting."""
    _, rows, _ = load_tracker(filepath)

    # Deduplicate
    seen_ids = set()
    deduped = []
    dupes = 0

    for row in rows:
        url = row[9] if len(row) > 9 else None
        job_id = extract_job_id(url)

        if job_id and job_id in seen_ids:
            dupes += 1
            continue
        if job_id:
            seen_ids.add(job_id)
        deduped.append(row)

    _write_tracker(filepath, deduped)

    return {
        "original_rows": len(rows),
        "after_dedup": len(deduped),
        "duplicates_removed": dupes
    }


def _write_tracker(filepath, rows):
    """Write tracker with guaranteed consistent formatting."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Job Tracker"

    # Headers
    for col, header in enumerate(HEADERS, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal='center', wrap_text=True)
        cell.border = THIN_BORDER

    # Column widths
    for i, w in enumerate(COL_WIDTHS, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # Data rows
    for r_idx, row in enumerate(rows, 2):
        tier = str(row[6]).strip() if len(row) > 6 and row[6] else ""
        status = str(row[12]).strip() if len(row) > 12 and row[12] else ""
        notes = str(row[13]).strip() if len(row) > 13 and row[13] else ""
        row_fill = get_row_fill(tier, status, notes)

        for col, val in enumerate(row, 1):
            if col > len(HEADERS):
                break
            cell = ws.cell(row=r_idx, column=col, value=val)
            cell.fill = row_fill
            cell.border = THIN_BORDER
            cell.alignment = Alignment(wrap_text=True, vertical='top')

            if col == 6:  # Score — center
                cell.alignment = Alignment(horizontal='center', vertical='top')
            if col == 7:  # Tier — center + bold
                cell.alignment = Alignment(horizontal='center', vertical='top')
                cell.font = Font(bold=True)

    # Freeze + filter
    ws.freeze_panes = "A2"
    last_col = get_column_letter(len(HEADERS))
    ws.auto_filter.ref = f"A1:{last_col}{len(rows) + 1}"

    wb.save(filepath)


# === CLI ===

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 tracker_utils.py <command> <tracker_path> [args...]")
        print("Commands: dedup-set, append, rebuild")
        sys.exit(1)

    command = sys.argv[1]
    tracker_path = os.path.expanduser(sys.argv[2])

    if command == "dedup-set":
        ids = get_dedup_set(tracker_path)
        print(json.dumps(ids))

    elif command == "append":
        if len(sys.argv) < 4:
            print("Usage: python3 tracker_utils.py append <tracker_path> <new_rows.json>")
            sys.exit(1)
        result = append_rows(tracker_path, sys.argv[3])
        print(json.dumps(result, indent=2))

    elif command == "rebuild":
        result = rebuild(tracker_path)
        print(json.dumps(result, indent=2))

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
