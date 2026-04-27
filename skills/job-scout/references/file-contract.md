# File Contract

Every file the scout reads or writes lives at exactly one path. **No alternate paths. No fallbacks. No "or".** If the scout puts a file anywhere else, that's a bug.

`{data_dir}` resolves at runtime via `python3 scripts/state.py resolve`. If that fails, the scout MUST stop and tell the user to run `/scout-setup`.

---

## Setup pointer (machine-wide, not in data_dir)

| Purpose | Path | Written by | Read by |
|---|---|---|---|
| State pointer | `~/.job-scout/state.json` | `/scout-setup` | `/scout-run` |

Format:
```json
{
  "data_dir": "/Users/<user>/Documents/JobSearch",
  "plugin_version": "0.3.0",
  "last_setup_iso": "2026-04-26T12:34:56Z"
}
```

---

## Persistent files in `{data_dir}`

| File | Path | Owner |
|---|---|---|
| Config | `{data_dir}/config.json` | `/scout-setup` (created), user (edits) |
| Candidate profile | `{data_dir}/candidate_profile.json` | `/scout-setup` |
| Master targets | `{data_dir}/master_targets.csv` | `/scout-setup` (initial), `/scout-run` (updates `last_checked`, `application_status`, `notes`) |
| Tracker | `{data_dir}/JobScout_Tracker.xlsx` | `/scout-run` via `tracker_utils.py append` ONLY. Never write directly. |
| Honest assessment | `{data_dir}/assessment/Honest_Career_Assessment.md` | `/scout-setup` |
| Resume bank | `{data_dir}/Resumes/` | User-curated. Scout reads, never writes. |

**Schema for `master_targets.csv` and `JobScout_Tracker.xlsx` lives in `scripts/schema.py`.** Never inline column lists. If a column is referenced by name in a prompt, it must match `MASTER_TARGETS_COLUMNS` or `TRACKER_COLUMNS` exactly.

---

## Per-run output (always under `daily/`)

For run on date `<DATE>` (ISO `YYYY-MM-DD`):

| Artifact | Path |
|---|---|
| Daily report | `{data_dir}/daily/<DATE>/JobScout_Report_<DATE>.md` |
| Run log | `{data_dir}/daily/<DATE>/run_log.json` |
| New rows for tracker | `{data_dir}/daily/<DATE>/new_rows.json` (input to `tracker_utils.py append`) |
| Per-A-tier packets (on demand) | `{data_dir}/daily/<DATE>/packets/<Company>_<Role>/` |

**Per-A-tier packet contents** (when generated via the hybrid on-demand flow):
```
packets/<Company>_<Role>/
  ├─ jd.md                  # Full job description text
  ├─ tailored_resume.docx   # ATS-keyword-aligned version of selected base resume
  ├─ ats_diff.md            # The keyword diff (kept for traceability)
  └─ outreach_draft.md      # Pre-drafted message to the named warm-intro contact
```

The `daily/` folder structure is created by `scripts/validate_data.py` at the top of every run. Don't `mkdir` ad-hoc.

---

## Why this matters

The previous design had paths described in 3+ places (`SKILL.md`, `scout-run.md`, the README) and they had drifted apart. Outputs were landing in inconsistent locations and follow-on runs couldn't find them.

**Rule: when adding any new artifact to the scout, add it here first, then reference this doc from wherever it's written.** Do not describe paths in two places.
