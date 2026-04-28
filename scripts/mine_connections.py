#!/usr/bin/env python3
"""
mine_connections.py — Extract LinkedIn connections and count them by company.

Reads a LinkedIn Connections.csv export and produces a company-level summary
with connection counts, names, and titles. Output can be merged into master_targets.csv.

Usage:
    python3 mine_connections.py /path/to/Connections.csv /path/to/output.csv

Notes:
    - LinkedIn's Connections.csv has 3 header/note rows before the actual data.
      This script automatically detects and skips them.
    - Encoding is handled (LinkedIn exports sometimes use latin-1).
"""

import sys
import os
import csv
from collections import defaultdict

try:
    import pandas as pd
except ImportError:
    print(
        "ERROR: pandas not installed. Install with: "
        "python3 -m venv ~/.job-scout-venv && source ~/.job-scout-venv/bin/activate && pip install pandas"
        "  (or: pip install --user pandas)",
        file=sys.stderr,
    )
    sys.exit(1)


def detect_header_rows(filepath):
    """Detect how many rows to skip in LinkedIn's Connections.csv."""
    encodings = ['utf-8', 'latin-1', 'cp1252']

    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                for i, line in enumerate(f):
                    # The real header row contains "First Name" or "Company"
                    if 'First Name' in line or 'Company' in line:
                        return i, enc
            # If we get here without finding it, try next encoding
        except UnicodeDecodeError:
            continue

    # CON-03: fallback to standard LinkedIn export shape — but warn loudly. The caller
    # validates after pd.read_csv that a recognizable column set survived; if not,
    # mine_connections aborts with a clear ERROR.
    print(
        f"WARNING: detect_header_rows fell through to (3, 'latin-1') default for "
        f"{filepath} — could not find 'First Name' or 'Company' header in any encoding. "
        f"This may indicate a non-English LinkedIn export or a format change.",
        file=sys.stderr,
    )
    return 3, 'latin-1'


def mine_connections(connections_path, output_path):
    """
    Read Connections.csv and produce a company summary CSV.

    Output columns:
        company_name, linkedin_connection_count, connection_names, connection_titles
    """
    skip_rows, encoding = detect_header_rows(connections_path)

    df = pd.read_csv(
        connections_path,
        skiprows=skip_rows,
        encoding=encoding,
        on_bad_lines='skip'
    )

    # Normalize column names (LinkedIn sometimes changes casing)
    df.columns = [c.strip().lower().replace(' ', '_') for c in df.columns]

    # CON-03: post-skip column validation. If neither a company column nor a
    # recognizable name column survived, the header-detection fallback almost
    # certainly produced garbage. Abort loudly rather than write a corrupt
    # connections_summary.csv that consolidate_targets.py will silently consume.

    # Find the company column
    company_col = None
    for candidate in ['company', 'company_name', 'organization']:
        if candidate in df.columns:
            company_col = candidate
            break

    # Find a recognizable name column (used downstream for connection_names output)
    has_name_col = (
        any('first' in c and 'name' in c for c in df.columns)
        or any('last' in c and 'name' in c for c in df.columns)
    )

    if not company_col or not has_name_col:
        print(
            f"ERROR: mine_connections could not resolve LinkedIn export columns. "
            f"company_col={company_col!r}, has_name_col={has_name_col}. "
            f"Available columns: {list(df.columns)}. "
            f"This usually means detect_header_rows fell through (see prior WARNING) "
            f"on a non-English export or a LinkedIn format change. "
            f"Verify the input file or open an issue with a sanitized sample.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Find name columns
    first_name_col = next((c for c in df.columns if 'first' in c and 'name' in c), None)
    last_name_col = next((c for c in df.columns if 'last' in c and 'name' in c), None)
    position_col = next((c for c in df.columns if c in ['position', 'title', 'headline']), None)

    # Group by company
    companies = defaultdict(lambda: {"count": 0, "names": [], "titles": []})

    for _, row in df.iterrows():
        company = str(row.get(company_col, "")).strip()
        if not company or company == 'nan':
            continue

        companies[company]["count"] += 1

        name_parts = []
        if first_name_col and pd.notna(row.get(first_name_col)):
            name_parts.append(str(row[first_name_col]).strip())
        if last_name_col and pd.notna(row.get(last_name_col)):
            name_parts.append(str(row[last_name_col]).strip())
        name = " ".join(name_parts)

        title = str(row.get(position_col, "")).strip() if position_col else ""
        if title == 'nan':
            title = ""

        if name:
            entry = f"{name} ({title})" if title else name
            companies[company]["names"].append(entry)

    # Sort by connection count descending
    sorted_companies = sorted(companies.items(), key=lambda x: x[1]["count"], reverse=True)

    # Write output
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["company_name", "linkedin_connection_count", "connection_names", "connection_titles"])

        for company, data in sorted_companies:
            names = "; ".join(data["names"][:10])  # Cap at 10 names per company
            titles = "; ".join([n.split("(")[-1].rstrip(")") for n in data["names"][:10] if "(" in n])
            writer.writerow([company, data["count"], names, titles])

    print(f"Processed {len(df)} connections across {len(sorted_companies)} companies")
    print(f"Top 10 by connection count:")
    for company, data in sorted_companies[:10]:
        print(f"  {company}: {data['count']}")
    print(f"Output written to: {output_path}")

    return sorted_companies


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 mine_connections.py <Connections.csv> <output.csv>")
        sys.exit(1)

    mine_connections(
        os.path.expanduser(sys.argv[1]),
        os.path.expanduser(sys.argv[2])
    )
