---
name: scout-detect
description: Detect ATS providers for top-connection companies and populate ats_provider + ats_board_url + ats_slug_confidence in master_targets.csv. Triggers when the user types `/scout-detect` or asks to "detect job boards", "find which ATS my target companies use", "populate ATS fields", "scan for ATS coverage".
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion, TodoWrite
version: 0.4.0
---

Run a one-shot ATS provider detection sweep over the user's top-N connection-weighted companies in `master_targets.csv`. Populates `ats_provider`, `ats_board_url`, and `ats_slug_confidence` so subsequent `/scout-run` invocations can produce real ATS-sourced listings. Idempotent: re-running on the same CSV is a no-op unless `--force` is passed; rows with `ats_provider=manual` are NEVER overwritten regardless of `--force`.

Read these before starting:
- `${CLAUDE_PLUGIN_ROOT}/skills/job-scout/SKILL.md` (core skill knowledge)
- `${CLAUDE_PLUGIN_ROOT}/skills/job-scout/references/file-contract.md` (where every file lives — including the new `ats_detection_review.csv`)

---

## Step 1: Resolve `data_dir` and validate

1. **Resolve `data_dir`:**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state.py resolve
   ```
   - Exit code 0 → use the printed path as `<data_dir>`.
   - Exit code 2 → tell the user "No Job Scout state found. Run `/scout-setup` first." Stop.

2. **Validate and auto-migrate the data directory:**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate_data.py "<data_dir>"
   ```
   This is idempotent. It creates missing files (empty tracker, `daily/` dir) and migrates `master_targets.csv` to add any new schema columns (including the v0.4 `ats_provider`, `ats_board_url`, `ats_slug_confidence`, `last_ats_hit_date` columns). If it exits non-zero, surface the message to the user and stop — the data dir is broken and needs `/scout-setup` again.

---

## Step 2: Parse user arguments

Determine the effective flags for the `detect-batch` call based on how the user invoked `/scout-detect`. Use `AskUserQuestion` ONLY if the user's intent is genuinely ambiguous.

| Flag | Effect | Notes |
|---|---|---|
| (none — default) | Detect top 30 connection-weighted companies | Companies are sorted by `linkedin_connection_count` descending in `master_targets.csv` |
| `--limit N` | Detect top N companies instead of the default 30 | Pass `--limit N` to `detect-batch` |
| `--all` | Detect ALL companies in `master_targets.csv` | Omit `--limit` entirely; detect-batch processes every non-skipped row |
| `--force` | Re-detect rows that already have `ats_provider` populated (even if within freshness window) | Does NOT override `ats_provider=manual` rows — that lock is absolute |

Default behavior if the user types `/scout-detect` with no arguments: detect top 30, no force.

---

## Step 3: Run batch detection (ONE Bash call)

Call `detect-batch` with a single Bash invocation. Do NOT split this into multiple calls.

**Default (top 30, no force):**
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ats/detect.py detect-batch \
  "<data_dir>/master_targets.csv" \
  --limit 30 \
  --data-dir "<data_dir>"
```

**With `--force` (re-detect already-set rows, except manual):**
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ats/detect.py detect-batch \
  "<data_dir>/master_targets.csv" \
  --limit 30 \
  --force \
  --data-dir "<data_dir>"
```

**With `--all` (no limit):**
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ats/detect.py detect-batch \
  "<data_dir>/master_targets.csv" \
  --data-dir "<data_dir>"
```

**With `--all --force`:**
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ats/detect.py detect-batch \
  "<data_dir>/master_targets.csv" \
  --force \
  --data-dir "<data_dir>"
```

**With `--limit N` (custom N):**
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ats/detect.py detect-batch \
  "<data_dir>/master_targets.csv" \
  --limit <N> \
  --data-dir "<data_dir>"
```

Capture stdout. The JSON summary (the LAST line of stdout) contains:
- `total` — number of companies detected (excludes skipped)
- `confirmed` — companies with ats_slug_confidence ≥ 0.85 written to CSV
- `borderline` — matches with score 70–84 written to `ats_detection_review.csv` for review
- `not_found` — companies where no provider matched (ats_provider set to `"none"`)
- `error` — transient HTTP/network failures; ats_provider left empty
- `skipped` — rows skipped because already fresh or manual-locked
- `wall_clock_seconds` — elapsed time
- `companies` — per-company results dict

Exit codes:
- `0` → detection completed; parse JSON summary and proceed to Step 4
- `1` → misuse (bad arguments); surface the stderr message to the user and stop
- `2` → missing `config.json` at `<data_dir>/config.json`; tell the user to run `/scout-setup` first and stop

---

## Step 4: Surface results to the user

Parse the JSON summary from stdout and display a concise human-readable summary:

```
ATS detection complete in <wall_clock_seconds>s.

- Confirmed: <confirmed> companies (ats_provider populated, ats_slug_confidence ≥ 0.85)
- Borderline: <borderline> companies (review at <data_dir>/ats_detection_review.csv)
- Not found: <not_found> companies (ats_provider="none" — no provider matched)
- Errors: <error> companies (transient — try `/scout-detect --force` later)
- Skipped: <skipped> companies (already detected within last 30 days; pass --force to re-detect)
```

---

## Step 5: Borderline review (only if `borderline` count > 0)

If `borderline` > 0, tell the user:

```
<borderline> borderline matches need manual review.
Open <data_dir>/ats_detection_review.csv and for each row either:
  - Set the `action` column to "accept" and manually edit master_targets.csv to set
    ats_provider + ats_board_url for that company
  - Set the `action` column to "skip" if it looks like a wrong-company false positive

Borderline rows do NOT have ats_slug_confidence set — they need your judgement before
the next /scout-run picks them up.

Note: ats_detection_review.csv may also contain rows with note=zero_open_roles.
These are companies found on the ATS board (HTTP 200), but with 0 open roles right now.
The company IS on the provider; there are just no current openings.
```

---

## Step 6: Explain what changes and next steps

Tell the user what was updated and what to expect from the next `/scout-run`:

```
Your master_targets.csv now has ats_provider populated for the companies detected.
The next /scout-run will:
  - Run ATS Pass 1 against every row where ats_provider is populated —
    producing real ATS listings tagged source=ats:<provider>
  - Lazy-inline-detect any company in the daily slate that still has empty ats_provider (Step 2b)

Companies with ats_provider="none" are NOT re-detected on subsequent runs unless you
pass --force to /scout-detect.

Companies with ats_provider="manual" are NEVER overwritten — your manual lock is honored
regardless of --force.
```

---

## Failure modes detect.py already handles (no skill-side handling needed)

- `ats_provider=manual` rows → skipped silently regardless of `--force` (idempotency lock; STR-02).
- All providers return NOT_FOUND → company gets `ats_provider="none"` in master_targets.csv; run continues.
- HTTP 200 + 0 jobs → company gets `ats_provider="<provider>"` and `ats_board_url=<url>` BUT `ats_slug_confidence` stays empty AND a row is appended to `ats_detection_review.csv` with `note=zero_open_roles`. The company IS on the provider; just no current openings.
- Network timeout / HTTP error → bucketed as ERROR in the JSON summary; ats_provider stays empty; company eligible for re-detection on next run.
- rapidfuzz not installed → detect.py exits 1 with install hint; skill surfaces this to user.
- `<data_dir>/config.json` missing → detect.py exits 2; skill prompts user to run `/scout-setup` first.

---

## Idempotency

Re-running `/scout-detect` is a no-op for rows where:
- `ats_provider` is non-empty AND `last_ats_hit_date` is within the last 30 days (default freshness window)
- `ats_provider` is `manual` (user-locked — NEVER auto-overwritten, even with `--force`)

Pass `--force` to re-detect any non-manual row. Stale rows (`last_ats_hit_date` >30 days old) are re-detected automatically without `--force`.
