#!/usr/bin/env python3
"""
consolidate_targets.py — Merge multiple data sources into master_targets.csv.

Takes any combination of CSVs, XLSX files, and the output of mine_connections.py,
normalizes them to the master schema, deduplicates by company name, and produces
a single master_targets.csv.

Usage:
    python3 consolidate_targets.py --output /path/to/master_targets.csv \
        --connections /path/to/connections_summary.csv \
        --files /path/to/file1.csv /path/to/file2.xlsx

    python3 consolidate_targets.py --output /path/to/master_targets.csv \
        --scan-dir /path/to/JobSearch/
"""

import sys
import os
import argparse
import glob

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas not installed. Run: pip install pandas --break-system-packages", file=sys.stderr)
    sys.exit(1)


# Master schema — every output row has exactly these columns
MASTER_COLUMNS = [
    "company_name",
    "pipeline_tier",
    "industry",
    "location",
    "career_page_url",
    "connection_names",
    "linkedin_connection_count",
    "warm_path",
    "already_applied",
    "application_status",
    "roles_applied_for",
    "fit_notes",
    "fit_score",
    "what_they_do",
    "last_checked",
    "data_source"
]


def normalize_company_name(name):
    """Normalize company name for deduplication."""
    if pd.isna(name) or not name:
        return ""
    return str(name).strip().lower().replace(",", "").replace(".", "").replace(" inc", "").replace(" llc", "").replace(" ltd", "")


def read_file(filepath):
    """Read a CSV or XLSX file into a DataFrame."""
    ext = os.path.splitext(filepath)[1].lower()

    encodings = ['utf-8', 'latin-1', 'cp1252']

    if ext in ['.xlsx', '.xls']:
        try:
            return pd.read_excel(filepath)
        except Exception as e:
            print(f"  Warning: Could not read {filepath}: {e}", file=sys.stderr)
            return pd.DataFrame()

    for enc in encodings:
        try:
            return pd.read_csv(filepath, encoding=enc, on_bad_lines='skip')
        except UnicodeDecodeError:
            continue
        except Exception as e:
            print(f"  Warning: Could not read {filepath}: {e}", file=sys.stderr)
            return pd.DataFrame()

    return pd.DataFrame()


def detect_company_column(df):
    """Find the company name column in a DataFrame."""
    candidates = ['company_name', 'company', 'organization', 'employer', 'name']
    cols_lower = {c.strip().lower().replace(' ', '_'): c for c in df.columns}

    for candidate in candidates:
        if candidate in cols_lower:
            return cols_lower[candidate]

    # Fallback: first column that contains "company" or "name"
    for col in df.columns:
        if 'company' in col.lower() or 'organization' in col.lower():
            return col

    return None


def normalize_to_master(df, source_name):
    """Map arbitrary columns to the master schema."""
    col_map = {}
    cols_lower = {c.strip().lower().replace(' ', '_'): c for c in df.columns}

    # Try to map known columns
    mappings = {
        'company_name': ['company_name', 'company', 'organization', 'employer', 'name'],
        'pipeline_tier': ['pipeline_tier', 'tier', 'priority', 'rank'],
        'industry': ['industry', 'sector', 'vertical', 'category'],
        'location': ['location', 'hq', 'headquarters', 'city', 'office_location'],
        'career_page_url': ['career_page_url', 'careers_url', 'url', 'website', 'career_page'],
        'connection_names': ['connection_names', 'contacts', 'connections'],
        'linkedin_connection_count': ['linkedin_connection_count', 'connection_count', 'connections_count'],
        'warm_path': ['warm_path', 'warm_intro', 'referral'],
        'already_applied': ['already_applied', 'applied'],
        'application_status': ['application_status', 'status', 'app_status'],
        'roles_applied_for': ['roles_applied_for', 'roles', 'positions_applied'],
        'fit_notes': ['fit_notes', 'notes', 'comments', 'what_they_do'],
        'fit_score': ['fit_score', 'score', 'fit'],
        'what_they_do': ['what_they_do', 'description', 'about'],
        'last_checked': ['last_checked', 'last_check', 'checked_date'],
    }

    for master_col, candidates in mappings.items():
        for candidate in candidates:
            if candidate in cols_lower:
                col_map[master_col] = cols_lower[candidate]
                break

    # Build normalized rows
    rows = []
    for _, row in df.iterrows():
        normalized = {}
        for master_col in MASTER_COLUMNS:
            if master_col in col_map:
                val = row.get(col_map[master_col])
                normalized[master_col] = val if pd.notna(val) else ""
            elif master_col == "data_source":
                normalized[master_col] = source_name
            else:
                normalized[master_col] = ""
        rows.append(normalized)

    return pd.DataFrame(rows, columns=MASTER_COLUMNS)


def merge_duplicates(master_df):
    """
    Merge rows with the same company name.
    Priority: user-entered data > auto-generated data.
    Connection counts are summed/maxed.
    """
    master_df['_norm_name'] = master_df['company_name'].apply(normalize_company_name)

    # Remove rows with empty company names
    master_df = master_df[master_df['_norm_name'] != ''].copy()

    merged_rows = []
    for norm_name, group in master_df.groupby('_norm_name'):
        if len(group) == 1:
            row = group.iloc[0].to_dict()
            del row['_norm_name']
            merged_rows.append(row)
            continue

        # Merge multiple rows for the same company
        merged = {}
        for col in MASTER_COLUMNS:
            values = [str(v).strip() for v in group[col] if pd.notna(v) and str(v).strip() and str(v).strip() != 'nan']

            if col == 'linkedin_connection_count':
                # Take the max
                nums = []
                for v in group[col]:
                    try:
                        nums.append(int(float(v)))
                    except (ValueError, TypeError):
                        pass
                merged[col] = max(nums) if nums else 0

            elif col == 'connection_names':
                # Concatenate unique names
                all_names = set()
                for v in values:
                    for name in v.split(';'):
                        name = name.strip()
                        if name:
                            all_names.add(name)
                merged[col] = "; ".join(sorted(all_names)[:15])

            elif col == 'data_source':
                # Combine sources
                merged[col] = ", ".join(sorted(set(values)))

            elif col in ['already_applied', 'warm_path']:
                # Y wins over N
                merged[col] = 'Y' if 'Y' in [v.upper() for v in values] else ('N' if values else '')

            elif col in ['application_status', 'roles_applied_for', 'fit_notes']:
                # Take the longest/most detailed entry
                merged[col] = max(values, key=len) if values else ''

            elif col == 'pipeline_tier':
                # Take the lowest (highest priority) tier
                nums = []
                for v in values:
                    try:
                        nums.append(int(float(v)))
                    except (ValueError, TypeError):
                        pass
                merged[col] = min(nums) if nums else ''

            else:
                # Take first non-empty value
                merged[col] = values[0] if values else ''

        merged_rows.append(merged)

    result = pd.DataFrame(merged_rows, columns=MASTER_COLUMNS)

    # Sort by connection count descending, then by pipeline tier
    result['_sort_conns'] = pd.to_numeric(result['linkedin_connection_count'], errors='coerce').fillna(0)
    result['_sort_tier'] = pd.to_numeric(result['pipeline_tier'], errors='coerce').fillna(999)
    result = result.sort_values(['_sort_conns', '_sort_tier'], ascending=[False, True])
    result = result.drop(columns=['_sort_conns', '_sort_tier'])

    return result


def scan_directory(dir_path):
    """Find all CSV and XLSX files in a directory."""
    files = []
    for ext in ['*.csv', '*.xlsx', '*.xls']:
        files.extend(glob.glob(os.path.join(dir_path, ext)))
        files.extend(glob.glob(os.path.join(dir_path, '**', ext), recursive=True))
    # Deduplicate
    return sorted(set(files))


def consolidate(output_path, file_paths=None, connections_path=None, scan_dir=None):
    """Main consolidation logic."""
    all_frames = []

    # Scan directory if provided
    if scan_dir:
        found = scan_directory(scan_dir)
        print(f"Found {len(found)} data files in {scan_dir}")
        for f in found:
            # Skip the output file itself and tracker
            if os.path.abspath(f) == os.path.abspath(output_path):
                continue
            if 'Tracker' in os.path.basename(f):
                continue
            print(f"  Reading: {f}")
            df = read_file(f)
            if not df.empty and detect_company_column(df):
                normalized = normalize_to_master(df, os.path.basename(f))
                all_frames.append(normalized)
                print(f"    -> {len(normalized)} rows")
            else:
                print(f"    -> Skipped (no company column detected)")

    # Read explicitly provided files
    if file_paths:
        for f in file_paths:
            f = os.path.expanduser(f)
            print(f"Reading: {f}")
            df = read_file(f)
            if not df.empty:
                normalized = normalize_to_master(df, os.path.basename(f))
                all_frames.append(normalized)
                print(f"  -> {len(normalized)} rows")

    # Read connections summary
    if connections_path:
        connections_path = os.path.expanduser(connections_path)
        print(f"Reading connections: {connections_path}")
        df = read_file(connections_path)
        if not df.empty:
            normalized = normalize_to_master(df, "linkedin_connections")
            all_frames.append(normalized)
            print(f"  -> {len(normalized)} companies")

    if not all_frames:
        print("No data found. Creating empty master_targets.csv")
        pd.DataFrame(columns=MASTER_COLUMNS).to_csv(output_path, index=False)
        return

    # Combine and merge
    combined = pd.concat(all_frames, ignore_index=True)
    print(f"\nTotal rows before dedup: {len(combined)}")

    master = merge_duplicates(combined)
    print(f"Total companies after dedup: {len(master)}")

    # Write output
    master.to_csv(output_path, index=False)
    print(f"\nMaster targets written to: {output_path}")

    # Print summary
    has_connections = len(master[pd.to_numeric(master['linkedin_connection_count'], errors='coerce').fillna(0) > 0])
    has_applied = len(master[master['already_applied'].str.upper() == 'Y']) if 'already_applied' in master.columns else 0
    print(f"Companies with connections: {has_connections}")
    print(f"Companies already applied to: {has_applied}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Consolidate job search data into master_targets.csv")
    parser.add_argument("--output", required=True, help="Output path for master_targets.csv")
    parser.add_argument("--connections", help="Path to connections summary CSV (from mine_connections.py)")
    parser.add_argument("--files", nargs="*", help="Additional CSV/XLSX files to merge")
    parser.add_argument("--scan-dir", help="Scan directory for all CSV/XLSX files")

    args = parser.parse_args()
    consolidate(
        output_path=os.path.expanduser(args.output),
        file_paths=args.files,
        connections_path=args.connections,
        scan_dir=args.scan_dir
    )
