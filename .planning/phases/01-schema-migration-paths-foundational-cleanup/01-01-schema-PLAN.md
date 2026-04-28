---
phase: 01-schema-migration-paths-foundational-cleanup
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - scripts/schema.py
  - scripts/validate_data.py
  - scripts/tracker_utils.py
autonomous: true
requirements: [SCH-01, SCH-02, SCH-03, SCH-04, CON-02, CON-04]

must_haves:
  truths:
    - "scripts/schema.py defines MASTER_TARGETS_VERSION = 4"
    - "scripts/schema.py exports STATUS_VALUES frozenset (8 members including 'New' as the default for newly-found, untriaged tracker rows) and normalize_application_status() helper"
    - "scripts/schema.py MASTER_TARGETS_COLUMNS contains 'ats_slug_confidence' and 'last_ats_hit_date'"
    - "scripts/schema.py TRACKER_COLUMNS / TRACKER_JSON_KEYS / TRACKER_COL_WIDTHS each grow from 14 to 16 entries (Source, ATS Provider appended)"
    - "validate_data.py exposes validate_runs_log() and ensure_today_subdirs() and registers them"
    - "tracker_utils.append_rows validates application_status against STATUS_VALUES (warn-and-coerce on unknown), and the row_list it builds includes source + ats_provider as positions 15 and 16"
    - "Tracker rows with absent `status` field continue to default to \"New\" (preserves v=3 behavior); only explicitly-set unrecognized values trigger the warn-and-pass-through coercion path"
    - "ImportError install hints in scripts/validate_data.py and scripts/tracker_utils.py no longer mention `--break-system-packages`; they recommend `python3 -m venv` (or `pip install --user`) per CON-04"
  artifacts:
    - path: scripts/schema.py
      provides: SSOT schema constants v=4 + STATUS_VALUES + helper
      contains: "MASTER_TARGETS_VERSION = 4"
    - path: scripts/validate_data.py
      provides: validate_runs_log + ensure_today_subdirs validators; venv-style install hint
      exports: ["validate_runs_log", "ensure_today_subdirs"]
    - path: scripts/tracker_utils.py
      provides: status validation on append + 16-column row construction; venv-style install hint
  key_links:
    - from: scripts/tracker_utils.py
      to: scripts/schema.py
      via: "from schema import normalize_application_status"
      pattern: "from schema import.*normalize_application_status"
    - from: scripts/validate_data.py
      to: main()'s validator list
      via: "registered as ('runs_log', validate_runs_log)"
      pattern: "validate_runs_log"
---

<objective>
Bump schema constants to v=4 in `scripts/schema.py` (MASTER_TARGETS_VERSION, two new master_targets columns, two new tracker columns, STATUS_VALUES enum + helper). Wire the new validators in `scripts/validate_data.py` (`validate_runs_log` ensures `runs.jsonl` exists; `ensure_today_subdirs` creates `daily/<DATE>/ats_raw/`). Extend `scripts/tracker_utils.py` to (a) validate `application_status` on append via `STATUS_VALUES` warn-and-coerce, and (b) emit two new fields per row (`source`, `ats_provider`) — relying on `_write_tracker`'s existing rebuild + `load_tracker`'s existing None-padding to handle v=3 xlsx files transparently. Also replace the `--break-system-packages` install hints in `validate_data.py` and `tracker_utils.py` with the locked-decision venv/--user one-liner (CON-04 — this plan owns 2 of the 4 sites; Plan 02 owns the other 2).

Purpose: This plan establishes the v=4 schema substrate every later phase consumes. SCH-01..04 + CON-02 + CON-04 (partial) land in a single Wave-1 plan because all three files are tightly coupled (`tracker_utils` imports `schema`; `validate_data` imports `schema`) and all three already carry the `--break-system-packages` hint that Phase 1's grep gate forbids.

Output: `scripts/schema.py`, `scripts/validate_data.py`, `scripts/tracker_utils.py` all at v=4 shape with venv-style install hints.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/01-schema-migration-paths-foundational-cleanup/01-RESEARCH.md
@CLAUDE.md
@scripts/schema.py
@scripts/validate_data.py
@scripts/tracker_utils.py

<interfaces>
<!-- Key existing contracts the executor will extend. -->

From scripts/schema.py (current v=3):
```python
MASTER_TARGETS_COLUMNS = [11 columns ending in "data_source"]
MASTER_TARGETS_VERSION = 3
TRACKER_COLUMNS = [14 entries ending in "Notes"]
TRACKER_JSON_KEYS = [14 entries ending in "notes"]
TRACKER_COL_WIDTHS = [14 entries]
def empty_master_target_row(): -> dict
def empty_tracker_row(): -> dict
```

From scripts/validate_data.py:
```python
# Existing validators all return (ok: bool, message: str)
def validate_config(data_dir): ...
def validate_master_targets(data_dir): ...   # column-by-column additive — UNCHANGED
def validate_tracker(data_dir): ...
def validate_daily_dir(data_dir): ...
def main(argv): ...   # iterates a [(name, fn), ...] list
```

From scripts/tracker_utils.py:
```python
from schema import (TRACKER_COLUMNS as HEADERS, TRACKER_COL_WIDTHS as COL_WIDTHS, STALE_LINKEDIN_JOB_ID_THRESHOLD as STALE_JOB_ID_THRESHOLD)

def append_rows(filepath, new_rows_json_path):
    # builds row_list with 14 .get() calls in TRACKER_JSON_KEYS order
    # rebuilds workbook via _write_tracker
def _write_tracker(filepath, rows):
    # if col > len(HEADERS): break  (line 293; CON-20 is deferred to Phase 5)
def load_tracker(filepath):
    # pads short rows: row_list.extend([None] * (len(HEADERS) - len(row_list)))
    # — guarantees v=3 14-col xlsx files survive the 16-col extension
```

Existing ImportError handlers (the CON-04 sites this plan owns):
```python
# scripts/validate_data.py:29
print("ERROR: pandas not installed. Run: pip install pandas --break-system-packages", file=sys.stderr)
# scripts/tracker_utils.py:31
print("ERROR: openpyxl not installed. Run: pip install openpyxl --break-system-packages", file=sys.stderr)
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Extend scripts/schema.py to v=4 (columns + STATUS_VALUES + helper)</name>
  <files>scripts/schema.py</files>
  <read_first>
    - scripts/schema.py (the entire file — only 117 lines)
    - .planning/phases/01-schema-migration-paths-foundational-cleanup/01-RESEARCH.md (Pattern 1 + Pattern 5 sections; Code Examples → STATUS_VALUES validator)
  </read_first>
  <behavior>
    - Test 1: After edit, `from schema import MASTER_TARGETS_VERSION` returns 4.
    - Test 2: `MASTER_TARGETS_COLUMNS` ends with `["...", "data_source", "ats_slug_confidence", "last_ats_hit_date"]` (length 13).
    - Test 3: `TRACKER_COLUMNS` ends with `["...", "Notes", "Source", "ATS Provider"]` (length 16); `TRACKER_JSON_KEYS` ends with `["...", "notes", "source", "ats_provider"]` (length 16); `TRACKER_COL_WIDTHS` length is 16 with 18 + 16 appended.
    - Test 4: `from schema import STATUS_VALUES; "Active" in STATUS_VALUES and "New" in STATUS_VALUES and "" in STATUS_VALUES and "Dead" in STATUS_VALUES`. STATUS_VALUES has 8 members.
    - Test 5: `normalize_application_status("dad") == ("Active", True)`; `normalize_application_status("DEAD") == ("Dead", True)`; `normalize_application_status("Dead") == ("Dead", False)`; `normalize_application_status("New") == ("New", False)`; `normalize_application_status(None) == ("", False)`; `normalize_application_status("") == ("", False)`.
  </behavior>
  <action>
    Make exactly these edits to `scripts/schema.py`:

    **Edit 1 — extend MASTER_TARGETS_COLUMNS** (currently 11 entries; add 2 at the end):

    Replace the closing `]` of `MASTER_TARGETS_COLUMNS` so the list reads:
    ```python
    MASTER_TARGETS_COLUMNS = [
        "company_name",
        "industry",
        "career_page_url",
        "ats_provider",
        "ats_board_url",
        "connection_names",
        "linkedin_connection_count",
        "application_status",
        "fit_notes",
        "last_checked",
        "data_source",
        "ats_slug_confidence",   # v=4: float 0.0–1.0 (or empty) — populated by /scout-detect (Phase 3)
        "last_ats_hit_date",     # v=4: ISO date (or empty) — last day Pass 1 returned ≥1 listing for this company
    ]
    ```

    **Edit 2 — bump version + add explanatory comment block above the constant.** Replace the existing single-line `MASTER_TARGETS_VERSION = 3 ...` with:
    ```python
    # v4 (2026-04 v0.4): added ats_slug_confidence + last_ats_hit_date for ATS-first sourcing.
    # Migration is column-by-column additive in validate_data.validate_master_targets()
    # — version bump is a user-visible breadcrumb only, NOT a migration dispatch trigger.
    MASTER_TARGETS_VERSION = 4
    ```

    **Edit 3 — extend the three tracker lists in lockstep** (currently 14 entries each; add 2 at the end of each):

    `TRACKER_COLUMNS` — append `"Source",` and `"ATS Provider",` after `"Notes",`.

    `TRACKER_JSON_KEYS` — append `"source",` and `"ats_provider",` after `"notes",`.

    `TRACKER_COL_WIDTHS` — change the trailing `[..., 50]` to `[..., 50, 18, 16]` (Source narrow display, ATS Provider narrow display).

    Add a one-line comment right above each new entry pair: `# v0.4: source + ats_provider tracking — values are ats:greenhouse|ats:lever|...|linkedin or empty`.

    **Edit 4 — add STATUS_VALUES + normalize_application_status helper.** Insert immediately AFTER the `MASTER_TARGETS_VERSION = 4` line (and its comment block) and BEFORE the `# === Tracker section ===` divider:

    ```python
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
          - unknown -> ("Active", True)
        """
        if value is None:
            return "", False
        s = str(value).strip()
        for canonical in STATUS_VALUES:
            if s.lower() == canonical.lower():
                return canonical, s != canonical
        return "Active", True
    ```

    Per D-CON-02 (locked decision): warn-and-pass-through (NOT reject) is the chosen behavior — the helper coerces, the caller (`tracker_utils.append_rows`) prints the WARNING and writes the row. STATUS_VALUES has 9 entries above (`""`, `"New"`, `"Active"`, `"Applied"`, `"Interviewing"`, `"Offer"`, `"Rejected"`, `"Dead"`, `"Closed"`); behavior tests reference 8 *non-empty* canonical statuses plus the empty-string entry for unprocessed-row handling.
  </action>
  <verify>
    <automated>cd /Users/rmoore/Workspaces/job-scout-plugin && python3 -c "import sys; sys.path.insert(0, 'scripts'); from schema import MASTER_TARGETS_VERSION, MASTER_TARGETS_COLUMNS, TRACKER_COLUMNS, TRACKER_JSON_KEYS, TRACKER_COL_WIDTHS, STATUS_VALUES, normalize_application_status; assert MASTER_TARGETS_VERSION == 4, f'version is {MASTER_TARGETS_VERSION}'; assert len(MASTER_TARGETS_COLUMNS) == 13, f'master cols={len(MASTER_TARGETS_COLUMNS)}'; assert MASTER_TARGETS_COLUMNS[-2:] == ['ats_slug_confidence', 'last_ats_hit_date']; assert len(TRACKER_COLUMNS) == 16 and len(TRACKER_JSON_KEYS) == 16 and len(TRACKER_COL_WIDTHS) == 16; assert TRACKER_COLUMNS[-2:] == ['Source', 'ATS Provider']; assert TRACKER_JSON_KEYS[-2:] == ['source', 'ats_provider']; assert {'Active','New','Dead',''} <= STATUS_VALUES; assert normalize_application_status('dad') == ('Active', True); assert normalize_application_status('DEAD') == ('Dead', True); assert normalize_application_status('Dead') == ('Dead', False); assert normalize_application_status('New') == ('New', False); assert normalize_application_status(None) == ('', False); print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -q "MASTER_TARGETS_VERSION = 4" scripts/schema.py` returns 0
    - `grep -q '"ats_slug_confidence"' scripts/schema.py` returns 0
    - `grep -q '"last_ats_hit_date"' scripts/schema.py` returns 0
    - `grep -q '"Source"' scripts/schema.py` returns 0
    - `grep -q '"ATS Provider"' scripts/schema.py` returns 0
    - `grep -q '"source"' scripts/schema.py` returns 0
    - `grep -q '"ats_provider"' scripts/schema.py` returns 0
    - `grep -q "STATUS_VALUES = frozenset" scripts/schema.py` returns 0
    - `grep -q '"New"' scripts/schema.py` returns 0 (the new canonical default)
    - `grep -q "def normalize_application_status" scripts/schema.py` returns 0
    - The verify command above prints `OK` (asserts version, list lengths, column ordering, STATUS_VALUES membership including "New", and four normalize_application_status cases)
  </acceptance_criteria>
  <done>
    `scripts/schema.py` is at v=4 shape: 13 master_targets columns, 16 tracker columns/keys/widths, STATUS_VALUES frozenset with `"New"` included as the canonical default for newly-found untriaged rows, and `normalize_application_status` helper exporting the (canonical, was_coerced) tuple per Pattern 5 of 01-RESEARCH.md. The verify one-liner exits 0.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add validate_runs_log + ensure_today_subdirs to scripts/validate_data.py</name>
  <files>scripts/validate_data.py</files>
  <read_first>
    - scripts/validate_data.py (the entire file — only 147 lines)
    - .planning/phases/01-schema-migration-paths-foundational-cleanup/01-RESEARCH.md ("runs.jsonl validator addition" + "daily/<DATE>/ats_raw/ directory creation" sections, lines 822-870)
  </read_first>
  <behavior>
    - Test 1: After running `python3 scripts/validate_data.py /tmp/td_test1` (with a minimal `config.json` placed there), the file `/tmp/td_test1/runs.jsonl` exists and is empty.
    - Test 2: Running `validate_data.py` a second time on the same dir does NOT raise and the existing `runs.jsonl` is preserved (idempotent).
    - Test 3: After running `python3 scripts/validate_data.py ensure-today /tmp/td_test1 2026-04-28`, the directory `/tmp/td_test1/daily/2026-04-28/ats_raw/` exists.
  </behavior>
  <action>
    Make exactly these edits to `scripts/validate_data.py`:

    **Edit 1 — add `validate_runs_log` validator.** Insert immediately AFTER the existing `validate_daily_dir` function (after the closing of its `def`, before `def main`):

    ```python
    def validate_runs_log(data_dir):
        """Ensure runs.jsonl exists; create empty if missing. Idempotent.

        v0.4 SCH-01: every /scout-run starts by ensuring this file is present so
        the dispatcher (Phase 2) can append unconditionally without an mkdir guard.
        Phase 1 only ensures presence — rotation policy is a v0.5+ concern.
        """
        path = os.path.join(data_dir, "runs.jsonl")
        if not os.path.isfile(path):
            open(path, "a").close()  # touch — empty file is valid JSONL
            return True, "created empty runs.jsonl"
        return True, "ok"
    ```

    **Edit 2 — add `ensure_today_subdirs` helper + CLI subcommand.** Insert immediately AFTER `validate_runs_log`:

    ```python
    def ensure_today_subdirs(data_dir, date_str):
        """Create daily/<DATE>/ and daily/<DATE>/ats_raw/ if missing. Idempotent.

        v0.4 SCH-02: called by /scout-run Step 0 once <TODAY> is known. NOT called
        by main()'s validate-everything sweep because that runs before date resolution.
        """
        today_dir = os.path.join(data_dir, "daily", date_str)
        os.makedirs(os.path.join(today_dir, "ats_raw"), exist_ok=True)
        return True, f"ensured {today_dir}/ats_raw/"
    ```

    **Edit 3 — register `validate_runs_log` in main()'s validator list.** Find the existing list literal in `main`:
    ```python
    for name, fn in [
        ("config", validate_config),
        ("master_targets", validate_master_targets),
        ("tracker", validate_tracker),
        ("daily_dir", validate_daily_dir),
    ]:
    ```
    Add `("runs_log", validate_runs_log),` as the new last entry — keeping the existing four in their existing order.

    **Edit 4 — extend main() to dispatch the `ensure-today` subcommand.** Refactor the top of `main(argv)` so that when `argv[1] == "ensure-today"`, it routes to `ensure_today_subdirs`. Replace the existing `if len(argv) < 2: ... data_dir = os.path.expanduser(argv[1])` block with:

    ```python
    def main(argv):
        if len(argv) < 2:
            print("Usage: validate_data.py <data_dir>", file=sys.stderr)
            print("       validate_data.py ensure-today <data_dir> <YYYY-MM-DD>", file=sys.stderr)
            sys.exit(1)

        # Subcommand dispatch (matches state.py / tracker_utils.py convention)
        if argv[1] == "ensure-today":
            if len(argv) < 4:
                print("Usage: validate_data.py ensure-today <data_dir> <YYYY-MM-DD>", file=sys.stderr)
                sys.exit(1)
            data_dir = os.path.expanduser(argv[2])
            date_str = argv[3]
            ok, msg = ensure_today_subdirs(data_dir, date_str)
            print(json.dumps({"data_dir": data_dir, "date": date_str, "ok": ok, "message": msg}, indent=2))
            sys.exit(0 if ok else 1)

        data_dir = os.path.expanduser(argv[1])
        if not os.path.isdir(data_dir):
            print(f"ERROR: data_dir does not exist: {data_dir}", file=sys.stderr)
            sys.exit(1)

        results = {}
        overall_ok = True

        for name, fn in [
            ("config", validate_config),
            ("master_targets", validate_master_targets),
            ("tracker", validate_tracker),
            ("daily_dir", validate_daily_dir),
            ("runs_log", validate_runs_log),
        ]:
            ok, msg = fn(data_dir)
            results[name] = {"ok": ok, "message": msg}
            if not ok:
                overall_ok = False

        print(json.dumps({"data_dir": data_dir, "ok": overall_ok, "checks": results}, indent=2))
        sys.exit(0 if overall_ok else 1)
    ```

    Do NOT touch `validate_master_targets` — it already handles the v=3→v=4 column addition automatically per Pattern 1 of 01-RESEARCH.md (lines 80-91 of the existing file: "for col in MASTER_TARGETS_COLUMNS: if col not in existing_cols: df[col] = ''"). Adding 2 cols to the constant in Task 1 is the entire migration.
  </action>
  <verify>
    <automated>cd /Users/rmoore/Workspaces/job-scout-plugin && rm -rf /tmp/td_test1 && mkdir -p /tmp/td_test1 && printf '{"data_dir":"/tmp/td_test1","preferences":{},"search":{},"scoring":{}}' > /tmp/td_test1/config.json && python3 scripts/validate_data.py /tmp/td_test1 > /tmp/td_test1.out 2>&1 && test -f /tmp/td_test1/runs.jsonl && python3 scripts/validate_data.py /tmp/td_test1 > /dev/null 2>&1 && test -f /tmp/td_test1/runs.jsonl && python3 scripts/validate_data.py ensure-today /tmp/td_test1 2026-04-28 > /dev/null 2>&1 && test -d /tmp/td_test1/daily/2026-04-28/ats_raw && grep -q '"runs_log"' /tmp/td_test1.out && echo OK</automated>
  </verify>
  <acceptance_criteria>
    - `grep -q "def validate_runs_log" scripts/validate_data.py` returns 0
    - `grep -q "def ensure_today_subdirs" scripts/validate_data.py` returns 0
    - `grep -q '("runs_log", validate_runs_log)' scripts/validate_data.py` returns 0
    - `grep -q 'argv\[1\] == "ensure-today"' scripts/validate_data.py` returns 0
    - The verify command above prints `OK` — runs.jsonl is created on first invocation, preserved on second invocation, and `ensure-today` produces `daily/<DATE>/ats_raw/`.
  </acceptance_criteria>
  <done>
    `scripts/validate_data.py` exposes `validate_runs_log` (registered in main) and `ensure_today_subdirs` (CLI subcommand). `validate_master_targets` is unchanged — relying on its existing column-by-column additive logic to migrate the user's v=3 master_targets.csv to v=4 on first run. The verify one-liner exits 0.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Wire status validation + extend row construction in scripts/tracker_utils.py</name>
  <files>scripts/tracker_utils.py</files>
  <read_first>
    - scripts/tracker_utils.py (the entire file — 347 lines; focus on append_rows lines 152-232 and _write_tracker lines 264-315)
    - scripts/schema.py (after Task 1 ran — to confirm STATUS_VALUES + normalize_application_status are exported AND that "New" is a member)
    - .planning/phases/01-schema-migration-paths-foundational-cleanup/01-RESEARCH.md (Pattern 2 + Pattern 5 sections; STATUS_VALUES validator code example lines 720-732)
  </read_first>
  <behavior>
    - Test 1: After this task ships, calling `append_rows` with a row whose `status` is `"dad"` writes the row with `status="Active"` AND prints `WARNING: ... application_status 'dad' not in STATUS_VALUES; coerced to 'Active'` to stderr.
    - Test 2: A row with `status="Dead"` (canonical) writes with no warning. A row with `status=""` writes with no warning.
    - Test 3: A row with `source="ats:greenhouse"` and `ats_provider="ats:greenhouse"` populates columns 15 and 16 of the tracker xlsx.
    - Test 4: An EXISTING 14-column xlsx is read by `load_tracker`, padded to 16 columns with `None`, then rewritten as a 16-column xlsx with empty strings in cols 15/16 — verifying the auto-migration path described in Pattern 2.
    - Test 5: A row dict with NO `status` key produces `status="New"` (preserves v=3 default behavior); no WARNING is emitted to stderr.
    - Test 6: `normalize_application_status("New") == ("New", False)` (sanity — "New" is now canonical, not coerced).
  </behavior>
  <action>
    Make exactly these edits to `scripts/tracker_utils.py`:

    **Edit 1 — extend the schema import.** Find:
    ```python
    from schema import (
        TRACKER_COLUMNS as HEADERS,
        TRACKER_COL_WIDTHS as COL_WIDTHS,
        STALE_LINKEDIN_JOB_ID_THRESHOLD as STALE_JOB_ID_THRESHOLD,
    )
    ```
    Add `normalize_application_status` and `TRACKER_JSON_KEYS` to the import:
    ```python
    from schema import (
        TRACKER_COLUMNS as HEADERS,
        TRACKER_COL_WIDTHS as COL_WIDTHS,
        TRACKER_JSON_KEYS,
        STALE_LINKEDIN_JOB_ID_THRESHOLD as STALE_JOB_ID_THRESHOLD,
        normalize_application_status,
    )
    ```

    **Edit 2 — add status validation inside `append_rows`'s `for row_dict in new_rows:` loop.** Locate the existing loop at line 184. Immediately after the `# Stale check` block (after line 199's `# Still add it, but flagged`) and BEFORE the `row_list = [...]` construction at line 201, insert:

    ```python
            # CON-02: validate application_status against STATUS_VALUES.
            # Warn-and-coerce per locked decision — never rejects a row.
            #
            # Default for absent `status` is "New" (preserves v=3 behavior — the original
            # row_dict.get("status", "New") fallback). "New" is now a canonical member of
            # STATUS_VALUES, so the normalize_application_status() call below treats it as
            # exact-case-match (no coercion, no warning). Only explicitly-set unrecognized
            # values trigger the warn-and-pass-through path.
            raw_status = row_dict.get("status", "New")
            canonical_status, status_coerced = normalize_application_status(raw_status)
            if status_coerced and raw_status:  # silent on empty -> "" coercion
                print(
                    f"WARNING: row {added}: application_status {raw_status!r} not in STATUS_VALUES; "
                    f"coerced to {canonical_status!r}",
                    file=sys.stderr,
                )
            row_dict["status"] = canonical_status
    ```

    Note: `raw_status = row_dict.get("status", "New")` — NOT `""`. This preserves the original v=3 default. Because Task 1 added `"New"` to STATUS_VALUES, `normalize_application_status("New")` returns `("New", False)` — no warning, no coercion, status written as `"New"`.

    **Edit 3 — extend the `row_list` literal in `append_rows`.** Find the existing 14-entry row_list (lines 201-216) and append two new `.get()` calls after `row_dict.get("notes", "")`:

    ```python
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
                row_dict.get("source", ""),         # v0.4 SCH-04: ats:greenhouse|...|linkedin
                row_dict.get("ats_provider", ""),   # v0.4 SCH-04: ats:greenhouse|... or empty
            ]
    ```

    Note the row construction is now 16 entries — matching the 16-entry HEADERS / COL_WIDTHS imported from `schema.py` after Task 1. The status `.get("status", "New")` here is still correct because Edit 2 already populated `row_dict["status"]` to the canonical value before this list is built.

    **Edit 4 — replace the ImportError install hint (CON-04 site 1 of 2 in this plan).** Find lines 28-32:
    ```python
    try:
        import openpyxl
        from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        print("ERROR: openpyxl not installed. Run: pip install openpyxl --break-system-packages", file=sys.stderr)
        sys.exit(1)
    ```
    Replace the print statement (the line with `--break-system-packages`) with the locked-decision multi-line version:
    ```python
        print(
            "ERROR: openpyxl not installed. Install with: "
            "python3 -m venv ~/.job-scout-venv && source ~/.job-scout-venv/bin/activate && pip install openpyxl"
            "  (or: pip install --user openpyxl)",
            file=sys.stderr,
        )
    ```
    Keep the `sys.exit(1)` line below unchanged.

    Do NOT change `_write_tracker`. Per Pattern 2 in 01-RESEARCH.md, `len(HEADERS)` is now 16 (because `schema.TRACKER_COLUMNS` is now 16), so the `if col > len(HEADERS): break` check at line 293 still works correctly. Do NOT change `load_tracker` — its existing line 134-135 padding (`row_list.extend([None] * (len(HEADERS) - len(row_list)))`) automatically widens v=3 14-col xlsx files to 16 cols on read. The CON-20 user-column-preservation fix is explicitly deferred to Phase 5.
  </action>
  <verify>
    <automated>cd /Users/rmoore/Workspaces/job-scout-plugin && python3 -c "
import sys, os, json, tempfile, io
sys.path.insert(0, 'scripts')
from tracker_utils import create_empty_tracker, append_rows, load_tracker

with tempfile.TemporaryDirectory() as td:
    tracker = os.path.join(td, 'JobScout_Tracker.xlsx')
    create_empty_tracker(tracker)

    # Test 1+3+5: append rows with bogus status, canonical status, and absent status
    rows_path = os.path.join(td, 'rows.json')
    with open(rows_path, 'w') as f:
        json.dump([
            {'job_title': 'VP Eng', 'company': 'Acme', 'job_url': 'https://example.com/j/9999999999', 'status': 'dad', 'tier': 'A', 'source': 'ats:greenhouse', 'ats_provider': 'ats:greenhouse'},
            {'job_title': 'CTO', 'company': 'Beta', 'job_url': 'https://example.com/j/8888888888', 'status': 'Dead', 'tier': 'B', 'source': 'linkedin', 'ats_provider': ''},
            {'job_title': 'Director', 'company': 'Gamma', 'job_url': 'https://example.com/j/7777777777', 'tier': 'C', 'source': '', 'ats_provider': ''},  # NO status key
        ], f)
    result = append_rows(tracker, rows_path)
    assert result['added'] == 3, result

    # Verify 16 columns + status coercion + source/ats_provider populated
    import openpyxl
    wb = openpyxl.load_workbook(tracker)
    ws = wb.active
    headers = [c.value for c in ws[1]]
    assert len(headers) == 16, f'headers len={len(headers)}: {headers}'
    assert headers[-2:] == ['Source', 'ATS Provider'], headers[-2:]

    rows_data = list(ws.iter_rows(min_row=2, values_only=True))
    # Find the Acme row (status was 'dad' -> coerced to 'Active')
    acme = [r for r in rows_data if r[2] == 'Acme'][0]
    assert acme[12] == 'Active', f'Acme status was {acme[12]!r} expected Active'
    assert acme[14] == 'ats:greenhouse', f'Acme source was {acme[14]!r}'
    assert acme[15] == 'ats:greenhouse', f'Acme ats_provider was {acme[15]!r}'

    beta = [r for r in rows_data if r[2] == 'Beta'][0]
    assert beta[12] == 'Dead', f'Beta status was {beta[12]!r}'
    assert beta[14] == 'linkedin', f'Beta source was {beta[14]!r}'
    assert beta[15] in ('', None), f'Beta ats_provider was {beta[15]!r}'

    # Test 5: Gamma had NO status key — must default to 'New'
    gamma = [r for r in rows_data if r[2] == 'Gamma'][0]
    assert gamma[12] == 'New', f'Gamma (absent status) was {gamma[12]!r} expected New'

print('OK')
" 2>&1 | tail -20</automated>
  </verify>
  <acceptance_criteria>
    - `grep -q "from schema import" scripts/tracker_utils.py` returns 0 AND that import block contains `normalize_application_status`
    - `grep -q "normalize_application_status" scripts/tracker_utils.py` matches at least twice (import + use)
    - `grep -q 'row_dict.get("status", "New")' scripts/tracker_utils.py` returns 0 (the v=3-preserving default; appears at the validation site AND in the row_list)
    - `grep -q "STATUS_VALUES" scripts/tracker_utils.py` returns 0 (referenced in WARNING string only — `STATUS_VALUES` itself isn't used directly, but the string `"not in STATUS_VALUES"` should appear)
    - `grep -q 'row_dict.get("source"' scripts/tracker_utils.py` returns 0
    - `grep -q 'row_dict.get("ats_provider"' scripts/tracker_utils.py` returns 0
    - `grep -c 'break-system-packages' scripts/tracker_utils.py` = `0`
    - `grep -q 'python3 -m venv ~/.job-scout-venv' scripts/tracker_utils.py` returns 0
    - `grep -q 'pip install --user openpyxl' scripts/tracker_utils.py` returns 0
    - The verify Python block above prints `OK`: 16 headers, status `'dad'` coerces to `'Active'`, `'Dead'` stays `'Dead'`, absent status defaults to `'New'`, source/ats_provider populate cols 15/16
  </acceptance_criteria>
  <done>
    `scripts/tracker_utils.py` validates `application_status` via `normalize_application_status` (warn-and-coerce, prints to stderr) before constructing the row, defaults absent `status` to `"New"` (v=3 behavior preserved — `"New"` is now a canonical STATUS_VALUES member so no warning fires), and emits 16-entry rows including `source` + `ats_provider`. The ImportError install hint no longer references `--break-system-packages`. `_write_tracker` and `load_tracker` are unchanged — they auto-handle the 14→16 widening per Pattern 2. The verify block exits 0.
  </done>
</task>

<task type="auto">
  <name>Task 4: Replace --break-system-packages install hint in scripts/validate_data.py (CON-04 site 2 of 2)</name>
  <files>scripts/validate_data.py</files>
  <read_first>
    - scripts/validate_data.py lines 25-30 (the existing ImportError handler)
    - .planning/phases/01-schema-migration-paths-foundational-cleanup/01-RESEARCH.md (Code Examples → Install-hint copy section)
  </read_first>
  <behavior>
    - Test 1: `grep -c "break-system-packages" scripts/validate_data.py` returns 0.
    - Test 2: The ImportError handler still mentions the package name (`pandas`) and recommends `python3 -m venv` AND `pip install --user pandas` as alternatives.
    - Test 3: The module still exits 1 on ImportError (existing semantic preserved).
  </behavior>
  <action>
    Per CON-04 locked decision, replace the `--break-system-packages` install hint with the venv/--user one-liner.

    **Edit — `scripts/validate_data.py` line 29.** Find the existing ImportError block (lines 26-30):
    ```python
    try:
        import pandas as pd
    except ImportError:
        print("ERROR: pandas not installed. Run: pip install pandas --break-system-packages", file=sys.stderr)
        sys.exit(1)
    ```
    Replace the print statement (the line with `--break-system-packages`) with:
    ```python
        print(
            "ERROR: pandas not installed. Install with: "
            "python3 -m venv ~/.job-scout-venv && source ~/.job-scout-venv/bin/activate && pip install pandas"
            "  (or: pip install --user pandas)",
            file=sys.stderr,
        )
    ```
    Keep the `sys.exit(1)` line below unchanged.

    Coordination: Plan 02 owns the parallel CON-04 sites in `consolidate_targets.py` and `mine_connections.py`. Plan 04's Task 3 phase-wide gate (`grep -rc 'break-system-packages' scripts/ = 0`) verifies all 4 sites are clean after both Wave-1 plans land.
  </action>
  <verify>
    <automated>cd /Users/rmoore/Workspaces/job-scout-plugin && test "$(grep -c break-system-packages scripts/validate_data.py)" = "0" && grep -q "python3 -m venv ~/.job-scout-venv" scripts/validate_data.py && grep -q "pip install --user pandas" scripts/validate_data.py && grep -A 8 'except ImportError' scripts/validate_data.py | grep -q "sys.exit(1)" && echo OK</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "break-system-packages" scripts/validate_data.py` = `0`
    - `grep -q "python3 -m venv ~/.job-scout-venv" scripts/validate_data.py` returns 0
    - `grep -q "pip install --user pandas" scripts/validate_data.py` returns 0
    - `grep -A 8 'except ImportError' scripts/validate_data.py | grep -q "sys.exit(1)"` returns 0 (existing exit semantic preserved)
    - The verify command prints `OK`
  </acceptance_criteria>
  <done>
    `scripts/validate_data.py` ImportError handler uses the venv/--user install hint with no `--break-system-packages` reference. Combined with Task 3's edit to `tracker_utils.py`, this plan's two CON-04 sites are clean.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| user-data → tracker_utils.append_rows | Untrusted application_status values from `new_rows.json` (could be a typo, a copy-paste mistake, or stale data from a v0.3 tracker) cross into the schema-validated tracker xlsx |
| schema.py → consumers (tracker_utils, validate_data, future scripts/ats/*) | Constants are imported by reference; a typo in MASTER_TARGETS_COLUMNS would silently propagate to every dependent script |
| user system Python → ImportError install hint | A stale `--break-system-packages` hint trains users to bypass PEP 668 protection on Python 3.12+, breaking system Python on macOS Homebrew installs |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-01 | Tampering (data integrity) | tracker_utils.append_rows on `application_status` | mitigate | STATUS_VALUES frozenset + normalize_application_status helper coerces unknowns to "Active" with stderr WARNING; case-insensitive match prevents `dead`/`DEAD`/`Dead` from being treated as separate statuses (CON-02). Default for absent `status` is "New" (now canonical) — preserves v=3 behavior so absent-status rows still get the well-known "freshly-found" marker. |
| T-01-02 | Tampering (schema drift) | scripts/schema.py constants | mitigate | All schema lists (MASTER_TARGETS_COLUMNS, TRACKER_COLUMNS, TRACKER_JSON_KEYS, TRACKER_COL_WIDTHS) live in one file; lockstep extension required by the comment block above each. Phase-1-04 migration test catches any future drift before it reaches users. |
| T-01-03 | Information Disclosure | runs.jsonl path leaks per-(company, provider) telemetry | accept | runs.jsonl lives in user's `<data_dir>` (already 0o700 once CON-07 lands in Plan 02); no PII in v0.4 — Phase 2 writer is the place to enforce that no candidate_profile fields leak. Phase 1 only ensures file existence. |
| T-01-04 | Denial-of-Service | malformed runs.jsonl from a crashed Phase-2 dispatcher write | accept | Phase 1 only touches the file (creates if missing); Phase 2 dispatcher is responsible for atomic-write semantics. Out of Phase-1 scope. |
| T-01-05 | Tampering (system Python) | --break-system-packages install hint | mitigate | Replace with venv-first, --user fallback hint per CON-04 in this plan's two sites (`validate_data.py`, `tracker_utils.py`); Plan 02 owns the other two (`consolidate_targets.py`, `mine_connections.py`). PEP 668 protection on Python 3.12+ is no longer bypassed by the plugin's recommendations. |
</threat_model>

<verification>
After all 4 tasks complete, run from repo root:

```bash
# 1. Schema constants verify (Task 1)
python3 -c "import sys; sys.path.insert(0, 'scripts'); from schema import MASTER_TARGETS_VERSION, MASTER_TARGETS_COLUMNS, TRACKER_COLUMNS, STATUS_VALUES; assert MASTER_TARGETS_VERSION == 4; assert len(MASTER_TARGETS_COLUMNS) == 13; assert len(TRACKER_COLUMNS) == 16; assert {'Active','New','Dead',''} <= STATUS_VALUES; print('schema OK')"

# 2. validate_data wire-up (Task 2)
rm -rf /tmp/p1_verify && mkdir -p /tmp/p1_verify
printf '{"data_dir":"/tmp/p1_verify","preferences":{},"search":{},"scoring":{}}' > /tmp/p1_verify/config.json
python3 scripts/validate_data.py /tmp/p1_verify > /dev/null
test -f /tmp/p1_verify/runs.jsonl && echo "runs.jsonl OK"
python3 scripts/validate_data.py ensure-today /tmp/p1_verify 2026-04-28 > /dev/null
test -d /tmp/p1_verify/daily/2026-04-28/ats_raw && echo "ats_raw OK"

# 3. tracker_utils status validation + 16-col extension (Task 3)
# (full smoke covered by Task 3's verify block; here just check imports and lengths)
python3 -c "import sys; sys.path.insert(0, 'scripts'); import tracker_utils; assert len(tracker_utils.HEADERS) == 16; assert callable(tracker_utils.normalize_application_status); print('tracker_utils OK')"

# 4. Install-hint cleanup (Tasks 3 + 4) — this plan's CON-04 sites
test "$(grep -c break-system-packages scripts/validate_data.py)" = "0"
test "$(grep -c break-system-packages scripts/tracker_utils.py)" = "0"
echo "install hints OK"
```

All five echo lines (`schema OK`, `runs.jsonl OK`, `ats_raw OK`, `tracker_utils OK`, `install hints OK`) must print.
</verification>

<success_criteria>
- `MASTER_TARGETS_VERSION == 4` and the two new master_targets columns are present
- `TRACKER_COLUMNS / TRACKER_JSON_KEYS / TRACKER_COL_WIDTHS` are all length 16 with `Source` + `ATS Provider` (and lower-case JSON keys) at the end
- `STATUS_VALUES` frozenset (with `"New"` included) and `normalize_application_status()` helper are exported from `schema.py`
- `validate_data.py` calls `validate_runs_log` from `main()`'s validator list and exposes `ensure-today` CLI subcommand
- `tracker_utils.append_rows` validates `application_status` and emits 16-entry rows; absent `status` defaults to `"New"` (v=3 behavior preserved, no warning)
- A v=3-shape 14-col xlsx round-trips through `load_tracker → append_rows → _write_tracker` without losing any rows (auto-widens to 16 cols)
- `scripts/validate_data.py` and `scripts/tracker_utils.py` ImportError handlers no longer reference `--break-system-packages`; both recommend venv + --user (CON-04, this plan's 2 of 4 sites)
- All grep-based acceptance criteria pass
- All four task verify blocks exit 0
</success_criteria>

<output>
After completion, create `.planning/phases/01-schema-migration-paths-foundational-cleanup/01-01-SUMMARY.md` summarizing the schema bump, the validator wiring, the tracker-row extension, the venv-style install hints in `validate_data.py` + `tracker_utils.py`, and the deferred concerns (CON-20 stays in Phase 5).
</output>
</content>
</invoke>