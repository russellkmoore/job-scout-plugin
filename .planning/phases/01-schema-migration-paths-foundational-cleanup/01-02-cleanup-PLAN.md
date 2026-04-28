---
phase: 01-schema-migration-paths-foundational-cleanup
plan: 02
type: execute
wave: 1
depends_on: []
files_modified:
  - scripts/state.py
  - scripts/consolidate_targets.py
  - scripts/mine_connections.py
autonomous: true
requirements: [CON-01, CON-03, CON-04, CON-05, CON-07]

must_haves:
  truths:
    - "scripts/state.py defines no LEGACY_DATA_DIRS and no legacy fallback walk in resolve_data_dir"
    - "scripts/state.py write_state and read_state apply chmod 0o600 (file) + 0o700 (dir) best-effort"
    - "scripts/consolidate_targets.py no longer prints the dead 'already_applied' summary block"
    - "scripts/mine_connections.py prints WARNING to stderr when detect_header_rows falls through to the (3, 'latin-1') default AND aborts with ERROR if no recognizable name/company column survives"
    - "Every ImportError handler in consolidate_targets.py and mine_connections.py recommends venv/--user — not --break-system-packages"
  artifacts:
    - path: scripts/state.py
      provides: SSOT data_dir resolver hardened to 0o600/0o700; no legacy fallback chain
      exports: ["read_state", "write_state", "resolve_data_dir"]
    - path: scripts/consolidate_targets.py
      provides: consolidator with dead summary block deleted + new install hint
    - path: scripts/mine_connections.py
      provides: header-detection warning + post-skip column validation + new install hint
  key_links:
    - from: scripts/state.py:write_state
      to: chmod 0o600 / 0o700
      via: "_harden_perms helper, best-effort try/except OSError"
      pattern: "_harden_perms\\("
    - from: scripts/mine_connections.py:detect_header_rows
      to: stderr WARNING + post-skip column validation in mine_connections()
      via: "print(...WARNING:..., file=sys.stderr) AND ERROR-and-abort if no name/company column"
      pattern: "WARNING:.*detect_header_rows fell through"
---

<objective>
Foundational cleanup of three scripts (`state.py`, `consolidate_targets.py`, `mine_connections.py`) that aren't owned by Plan 01:

- **CON-05** — Delete `LEGACY_DATA_DIRS` (lines 32-36 of state.py) and the legacy fallback walk in `resolve_data_dir` (lines 78-81). The user-facing legacy-dir migration prompt lands in `skills/scout-setup/SKILL.md` Step 1 (Plan 03).
- **CON-07** — Add idempotent best-effort `_harden_perms` helper in state.py and call it from `write_state` and `read_state` (0o600 file, 0o700 dir). Wrap in try/except OSError so NFS/sandboxed environments warn but don't fail.
- **CON-01** — Delete the dead `already_applied` summary block at `consolidate_targets.py:269-272`. Per 01-RESEARCH.md, line 270 is already guarded — this is "delete dead code," not "fix a crash."
- **CON-03** — In `mine_connections.py`, emit a stderr WARNING when `detect_header_rows` returns the `(3, 'latin-1')` fallback AND validate after `pd.read_csv` that a recognizable name/company column survived; abort with a clear `ERROR:` if not.
- **CON-04 (partial — 2 of 4 sites)** — Replace the `ImportError` install hints in `consolidate_targets.py:26` and `mine_connections.py:25` with the locked-decision one-liner. Plan 01 owns the OTHER 2 sites (`validate_data.py:29` and `tracker_utils.py:31`) because those files are already in its `files_modified` set. CON-04 is shared across both Wave-1 plans by file partition.

Purpose: Plan 02 runs in parallel with Plan 01 on disjoint files. Together they finish all `scripts/`-tier work for Phase 1.

Output: Hardened `state.py` (no legacy chain, 0o600/0o700 perms), cleaned `consolidate_targets.py` (no dead block + new install hint), defensive `mine_connections.py` (warns + aborts on header confusion + new install hint).
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
@scripts/state.py
@scripts/consolidate_targets.py
@scripts/mine_connections.py

<interfaces>
<!-- Existing public API contracts the executor must preserve. -->

From scripts/state.py (current shape):
```python
STATE_DIR = os.path.expanduser("~/.job-scout")
STATE_PATH = os.path.join(STATE_DIR, "state.json")
LEGACY_DATA_DIRS = ["~/Documents/JobSearch/scout", "~/Documents/JobSearch", "~/Documents/JobScout"]   # DELETE

def read_state(): -> dict
def write_state(data_dir, plugin_version=None): -> dict
def resolve_data_dir(): -> str   # walks LEGACY chain; remove that walk
def main(argv): ...   # CLI: read | read-json | write | resolve
```

From scripts/consolidate_targets.py (lines 268-272 — the target):
```python
# Print summary
has_connections = len(master[pd.to_numeric(master['linkedin_connection_count'], errors='coerce').fillna(0) > 0])
has_applied = len(master[master['already_applied'].str.upper() == 'Y']) if 'already_applied' in master.columns else 0
print(f"Companies with connections: {has_connections}")
print(f"Companies already applied to: {has_applied}")
```
The `has_applied` line + its print are dead — `already_applied` was schema-trimmed in v=3, so the guard always evaluates to 0.

From scripts/mine_connections.py (lines 29-45 — detect_header_rows):
```python
def detect_header_rows(filepath):
    encodings = ['utf-8', 'latin-1', 'cp1252']
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                for i, line in enumerate(f):
                    if 'First Name' in line or 'Company' in line:
                        return i, enc
        except UnicodeDecodeError:
            continue
    return 3, 'latin-1'   # silent fallback — needs WARNING + post-skip validation
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Update ImportError install hints in consolidate_targets.py + mine_connections.py</name>
  <files>scripts/consolidate_targets.py, scripts/mine_connections.py</files>
  <read_first>
    - scripts/consolidate_targets.py (lines 18-30)
    - scripts/mine_connections.py (lines 17-26)
    - .planning/phases/01-schema-migration-paths-foundational-cleanup/01-RESEARCH.md (Code Examples → Install-hint copy section)
  </read_first>
  <behavior>
    - Test 1: `grep -c "break-system-packages" scripts/consolidate_targets.py` returns 0.
    - Test 2: `grep -c "break-system-packages" scripts/mine_connections.py` returns 0.
    - Test 3: Each ImportError handler still mentions the missing package by name and recommends `python3 -m venv` AND `pip install --user` as alternatives.
    - Test 4: Each module still exits 1 on ImportError (existing semantic preserved).
  </behavior>
  <action>
    Per CON-04 locked decision, replace the two `ImportError` handlers with the EXACT one-line stderr message format from planning_context.

    **Edit 1 — `scripts/consolidate_targets.py` line 26.** Replace the line:

    ```python
    print("ERROR: pandas not installed. Run: pip install pandas --break-system-packages", file=sys.stderr)
    ```

    With this multi-line print (still surfaces a single coherent stderr line via implicit string concatenation):

    ```python
    print(
        "ERROR: pandas not installed. Install with: "
        "python3 -m venv ~/.job-scout-venv && source ~/.job-scout-venv/bin/activate && pip install pandas"
        "  (or: pip install --user pandas)",
        file=sys.stderr,
    )
    ```

    **Edit 2 — `scripts/mine_connections.py` line 25.** Same replacement, same wording — the package name is `pandas` in both files.

    **Coordination with Plan 01:** Plan 01 owns `validate_data.py` and `tracker_utils.py`. Do NOT touch them in this plan. The Phase-1-04 verification grep confirms all four hints are updated after both Wave-1 plans land.
  </action>
  <verify>
    <automated>cd /Users/rmoore/Workspaces/job-scout-plugin && test "$(grep -c break-system-packages scripts/consolidate_targets.py)" = "0" && test "$(grep -c break-system-packages scripts/mine_connections.py)" = "0" && grep -q "python3 -m venv ~/.job-scout-venv" scripts/consolidate_targets.py && grep -q "python3 -m venv ~/.job-scout-venv" scripts/mine_connections.py && grep -q "pip install --user pandas" scripts/consolidate_targets.py && grep -q "pip install --user pandas" scripts/mine_connections.py && echo OK</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "break-system-packages" scripts/consolidate_targets.py` = `0`
    - `grep -c "break-system-packages" scripts/mine_connections.py` = `0`
    - `grep -q "python3 -m venv ~/.job-scout-venv" scripts/consolidate_targets.py` returns 0
    - `grep -q "python3 -m venv ~/.job-scout-venv" scripts/mine_connections.py` returns 0
    - `grep -q "pip install --user pandas" scripts/consolidate_targets.py` returns 0
    - `grep -q "pip install --user pandas" scripts/mine_connections.py` returns 0
    - Both scripts still call `sys.exit(1)` inside their `except ImportError` blocks (preserved exit semantic; `grep -A 8 'except ImportError' scripts/consolidate_targets.py | grep -q "sys.exit(1)"` returns 0)
    - The verify command prints `OK`
  </acceptance_criteria>
  <done>
    Both `consolidate_targets.py` and `mine_connections.py` use the locked-decision install-hint one-liner. No `--break-system-packages` references remain in either file.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Delete LEGACY_DATA_DIRS + add 0o600/0o700 perm hardening in scripts/state.py</name>
  <files>scripts/state.py</files>
  <read_first>
    - scripts/state.py (the entire file — only 116 lines)
    - .planning/phases/01-schema-migration-paths-foundational-cleanup/01-RESEARCH.md (Pattern 4 + Code Examples → state.py permission hardening + LEGACY_DATA_DIRS deletion sections, lines 736-803)
  </read_first>
  <behavior>
    - Test 1: After this task, `from state import LEGACY_DATA_DIRS` raises ImportError (the constant is gone).
    - Test 2: `state.write_state(/tmp/d, "0.4.0")` against a tempdir-overridden STATE_DIR creates `state.json` with mode `0o600` and STATE_DIR with mode `0o700` (verifiable via `stat`).
    - Test 3: A subsequent `state.read_state()` re-applies the chmod (idempotent on already-correct perms; works on existing 0o644 files from v0.3 — the "fix on first v0.4 read" path).
    - Test 4: If `os.chmod` raises `OSError` (caught inside `_harden_perms`), the script prints a `WARNING:` to stderr but does not abort.
    - Test 5: `resolve_data_dir()` returns the state.json `data_dir` value when present, OR `""` when state.json absent — NEVER walks a legacy chain.
  </behavior>
  <action>
    Make exactly these edits to `scripts/state.py`:

    **Edit 1 — delete `LEGACY_DATA_DIRS` constant (current lines 28-36).** Replace the entire comment block + list with this single comment block:

    ```python
    # v0.4 (CON-05): Legacy fallback chain removed. file-contract.md mandates
    # "no fallbacks." If state.json is missing, /scout-setup is responsible for
    # detecting any pre-existing data dir and prompting the user. resolve_data_dir
    # below now returns "" when state.json is missing — caller MUST run /scout-setup.
    ```

    **Edit 2 — add `_harden_perms` helper.** Insert immediately AFTER the `STATE_PATH = ...` line (and before `def read_state`):

    ```python
    def _harden_perms(path, mode):
        """Best-effort chmod; warn on failure but don't abort.

        Hardens local-state perms so other users on shared macOS systems cannot
        read the data_dir path. Sandboxed environments / NFS root_squash homes may
        reject the chmod — log and continue (the plugin still works at default perms).
        """
        try:
            os.chmod(path, mode)
        except OSError as e:
            print(
                f"WARNING: could not chmod {path} to {oct(mode)}: {e}. "
                f"State file remains at default permissions; consider hardening manually.",
                file=sys.stderr,
            )
    ```

    **Edit 3 — modify `write_state` to call `_harden_perms`.** Replace the existing `write_state` body so it becomes:

    ```python
    def write_state(data_dir, plugin_version=None):
        """Write the state pointer. Creates ~/.job-scout/ if needed.

        v0.4 CON-07: hardens perms to 0o700 (dir) + 0o600 (file) best-effort.
        """
        os.makedirs(STATE_DIR, exist_ok=True)
        _harden_perms(STATE_DIR, 0o700)
        data_dir = os.path.expanduser(data_dir)
        state = {
            "data_dir": data_dir,
            "plugin_version": plugin_version or "",
            "last_setup_iso": datetime.utcnow().isoformat() + "Z",
        }
        with open(STATE_PATH, "w") as f:
            json.dump(state, f, indent=2)
        _harden_perms(STATE_PATH, 0o600)
        return state
    ```

    **Edit 4 — modify `read_state` to idempotently re-harden perms.** Replace its body so it becomes:

    ```python
    def read_state():
        """Return state dict, or empty dict if not present / unreadable.

        v0.4 CON-07: idempotently re-applies chmod 0o600/0o700 to harden any
        existing v0.3 state.json files (default perms 0o644) on first v0.4 read.
        """
        if not os.path.exists(STATE_PATH):
            return {}
        _harden_perms(STATE_PATH, 0o600)
        _harden_perms(STATE_DIR, 0o700)
        try:
            with open(STATE_PATH, "r") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}
    ```

    **Edit 5 — simplify `resolve_data_dir()` to drop the legacy walk.** Replace the existing function body with:

    ```python
    def resolve_data_dir():
        """
        Return the user's data directory:
          1. ~/.job-scout/state.json -> data_dir (if dir exists)
          2. Empty string if not configured (caller MUST run /scout-setup)

        v0.4 CON-05: legacy fallback chain removed. /scout-setup detects pre-existing
        data dirs and prompts the user once on first v0.4 run.
        """
        state = read_state()
        candidate = state.get("data_dir")
        if candidate:
            candidate = os.path.expanduser(candidate)
            if os.path.isdir(candidate):
                return candidate
        return ""
    ```

    **Edit 6 — update the module docstring (current lines 1-18).** Specifically the `python3 scripts/state.py resolve` usage example. Change the trailing comment from `# prints resolved data_dir, falling back through legacy paths` to `# prints resolved data_dir from state.json (exits 2 if not configured)`.
  </action>
  <verify>
    <automated>cd /Users/rmoore/Workspaces/job-scout-plugin && python3 -c 'import sys, os, stat, tempfile; sys.path.insert(0, "scripts"); import state; assert not hasattr(state, "LEGACY_DATA_DIRS"), "LEGACY_DATA_DIRS still defined"; td = tempfile.mkdtemp(); state.STATE_DIR = os.path.join(td, ".job-scout"); state.STATE_PATH = os.path.join(state.STATE_DIR, "state.json"); dd = os.path.join(td, "JobSearch"); os.makedirs(dd); state.write_state(dd, "0.4.0"); fm = stat.S_IMODE(os.stat(state.STATE_PATH).st_mode); dm = stat.S_IMODE(os.stat(state.STATE_DIR).st_mode); assert fm == 0o600, f"file mode {oct(fm)}"; assert dm == 0o700, f"dir mode {oct(dm)}"; os.chmod(state.STATE_PATH, 0o644); os.chmod(state.STATE_DIR, 0o755); s = state.read_state(); assert s["data_dir"] == dd; fm = stat.S_IMODE(os.stat(state.STATE_PATH).st_mode); dm = stat.S_IMODE(os.stat(state.STATE_DIR).st_mode); assert fm == 0o600 and dm == 0o700, f"after read fm={oct(fm)} dm={oct(dm)}"; assert state.resolve_data_dir() == dd; os.remove(state.STATE_PATH); assert state.resolve_data_dir() == ""; print("OK")'</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "LEGACY_DATA_DIRS" scripts/state.py` = `0`
    - `grep -q "def _harden_perms" scripts/state.py` returns 0
    - `grep -q "_harden_perms(STATE_PATH, 0o600)" scripts/state.py` returns 0
    - `grep -q "_harden_perms(STATE_DIR, 0o700)" scripts/state.py` returns 0
    - `grep -q "for legacy in" scripts/state.py` returns NON-zero (no match — legacy walk gone). Verify with `! grep -q "for legacy in" scripts/state.py`.
    - The verify command prints `OK`: LEGACY_DATA_DIRS gone, write_state applies 0o600/0o700, read_state idempotently re-hardens (fixes v0.3 0o644 files), resolve_data_dir returns empty when state.json absent (no legacy walk).
  </acceptance_criteria>
  <done>
    `scripts/state.py` has no `LEGACY_DATA_DIRS`, no legacy walk in `resolve_data_dir`, and applies 0o600/0o700 best-effort on every `write_state` and idempotently on every `read_state`. The OSError catch ensures sandboxed/NFS environments warn but don't abort.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3a: Delete dead `already_applied` summary block in consolidate_targets.py (CON-01)</name>
  <files>scripts/consolidate_targets.py</files>
  <read_first>
    - scripts/consolidate_targets.py (lines 260-289 — the consolidate() summary print block + main entry)
    - .planning/phases/01-schema-migration-paths-foundational-cleanup/01-RESEARCH.md (CON-01 reframe at line 76)
  </read_first>
  <behavior>
    - Test 1: After this task, `grep -c "already_applied" scripts/consolidate_targets.py` = 0.
    - Test 2: `grep -c "Companies already applied to" scripts/consolidate_targets.py` = 0.
    - Test 3: `consolidate()` against a v=3 master_targets.csv runs end-to-end with no exception and prints `Companies with connections: <N>` (the OTHER summary line, retained).
  </behavior>
  <action>
    **Edit — `scripts/consolidate_targets.py` lines 268-272 (the dead summary block).** Find:
    ```python
        # Print summary
        has_connections = len(master[pd.to_numeric(master['linkedin_connection_count'], errors='coerce').fillna(0) > 0])
        has_applied = len(master[master['already_applied'].str.upper() == 'Y']) if 'already_applied' in master.columns else 0
        print(f"Companies with connections: {has_connections}")
        print(f"Companies already applied to: {has_applied}")
    ```
    Replace with (only the `has_applied` derivation + its print are deleted; the connections summary is retained):
    ```python
        # Print summary
        # CON-01: dead `already_applied` summary block deleted in v0.4 — the column was
        # removed in v=3 schema trim, so the guarded expression always evaluated to 0.
        has_connections = len(master[pd.to_numeric(master['linkedin_connection_count'], errors='coerce').fillna(0) > 0])
        print(f"Companies with connections: {has_connections}")
    ```

    Do NOT touch `mine_connections.py` in this task — Task 3b owns the CON-03 work there.
  </action>
  <verify>
    <automated>cd /Users/rmoore/Workspaces/job-scout-plugin && test "$(grep -c already_applied scripts/consolidate_targets.py)" = "0" && test "$(grep -c "Companies already applied to" scripts/consolidate_targets.py)" = "0" && grep -q "Companies with connections" scripts/consolidate_targets.py && echo OK</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "already_applied" scripts/consolidate_targets.py` = `0`
    - `grep -c "Companies already applied to" scripts/consolidate_targets.py` = `0`
    - `grep -q "Companies with connections" scripts/consolidate_targets.py` returns 0 (the retained summary line)
    - The verify command prints `OK`
  </acceptance_criteria>
  <done>
    `consolidate_targets.py` no longer references the schema-trimmed `already_applied` column or prints a dead summary line. The "Companies with connections" line is preserved.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3b: Add header-detection guard + post-skip column validation in mine_connections.py (CON-03)</name>
  <files>scripts/mine_connections.py</files>
  <read_first>
    - scripts/mine_connections.py (lines 29-77 — detect_header_rows + the start of mine_connections that uses it)
    - .planning/phases/01-schema-migration-paths-foundational-cleanup/01-RESEARCH.md (Pitfall 3 at lines 610-620: "warn-and-continue masks a fatal mismatch — error-and-abort on no-recognizable-columns")
  </read_first>
  <behavior>
    - Test 1: `mine_connections.py` against a Spanish-localized fixture (no "First Name" or "Company" anywhere) prints `WARNING: detect_header_rows fell through` to stderr.
    - Test 2: After the fallback skiprows=3 produces a column set with no recognizable name/company column, `mine_connections.py` prints `ERROR:` and exits 1.
  </behavior>
  <action>

    **Edit 1 — `scripts/mine_connections.py` `detect_header_rows` fallback warning.** Find lines 43-45:
    ```python
        # Default: skip 3 rows (standard LinkedIn export), try latin-1
        return 3, 'latin-1'
    ```
    Replace with:
    ```python
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
    ```

    **Edit 2 — `scripts/mine_connections.py` post-skip column validation.** Find the existing block at lines 67-76:
    ```python
        # Find the company column
        company_col = None
        for candidate in ['company', 'company_name', 'organization']:
            if candidate in df.columns:
                company_col = candidate
                break

        if not company_col:
            print(f"ERROR: Could not find company column. Available: {list(df.columns)}", file=sys.stderr)
            sys.exit(1)
    ```
    Replace with the strengthened version that ALSO checks for a recognizable name column (CON-03 Pitfall 3 mitigation):
    ```python
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
    ```

    The existing line-79 `first_name_col = next(...)` detection still runs after this guard passes — no regression.

    Do NOT touch `consolidate_targets.py` in this task — Task 3a owns the CON-01 work there.
  </action>
  <verify>
    <automated>cd /Users/rmoore/Workspaces/job-scout-plugin && grep -q "WARNING: detect_header_rows fell through" scripts/mine_connections.py && grep -q "has_name_col" scripts/mine_connections.py && grep -q "could not resolve LinkedIn export columns" scripts/mine_connections.py && echo OK</automated>
  </verify>
  <acceptance_criteria>
    - `grep -q "WARNING: detect_header_rows fell through" scripts/mine_connections.py` returns 0
    - `grep -q "has_name_col" scripts/mine_connections.py` returns 0
    - `grep -q "could not resolve LinkedIn export columns" scripts/mine_connections.py` returns 0
    - The verify command prints `OK`
  </acceptance_criteria>
  <done>
    `mine_connections.py` warns when `detect_header_rows` falls through AND aborts with ERROR if no recognizable name/company column survives — preventing a corrupt `connections_summary.csv` from poisoning `consolidate_targets.py`.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| local-other-users → ~/.job-scout/state.json | On a shared macOS system, other users could read state.json and discover the data_dir path (then read resume + connections.csv) |
| LinkedIn export → mine_connections.py | Untrusted CSV format (LinkedIn changes column names per locale; user could pass a wrong file) crosses into the data pipeline |
| User filesystem (legacy data dirs) → resolve_data_dir() | Pre-v0.4 the legacy chain could pick the WRONG data_dir on a multi-data-dir machine — silent information disclosure |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-01 | Information Disclosure | ~/.job-scout/state.json on shared macOS | mitigate | `_harden_perms(STATE_PATH, 0o600)` + `_harden_perms(STATE_DIR, 0o700)` in write_state and read_state (CON-07). Idempotent re-chmod in read_state hardens existing v0.3 0o644 files on first v0.4 read. |
| T-02-02 | Information Disclosure (wrong-dir write) | resolve_data_dir's legacy fallback chain | mitigate | Delete `LEGACY_DATA_DIRS` and the legacy walk; resolve_data_dir returns "" when state.json absent — forcing /scout-setup to ask the user explicitly (CON-05). |
| T-02-03 | Tampering (data integrity) | mine_connections.py header detection | mitigate | Stderr WARNING when fallback fires + post-skip column validation that aborts with ERROR if no recognizable name/company column survived (CON-03). Prevents garbage `connections_summary.csv` from being silently consumed by consolidate_targets.py. |
| T-02-04 | Denial-of-Service (against user's system Python) | --break-system-packages install hint | mitigate | Replace with venv/--user/pipx hint in all 4 ImportError handlers (CON-04 spans Plan 01 + Plan 02). |
| T-02-05 | DoS (NFS/sandboxed home dir) | _harden_perms chmod fails | accept | Wrapped in try/except OSError; emits WARNING and continues. The plugin still works at default perms — only the multi-user threat-model mitigation is reduced for this user. |
</threat_model>

<verification>
After all 4 tasks complete (Task 1, Task 2, Task 3a, Task 3b), run from repo root:

```bash
# 1. Install hints clean in this plan's files
test "$(grep -c break-system-packages scripts/consolidate_targets.py)" = "0"
test "$(grep -c break-system-packages scripts/mine_connections.py)" = "0"
echo "install hints OK"

# 2. state.py cleanup
test "$(grep -c LEGACY_DATA_DIRS scripts/state.py)" = "0"
grep -q "_harden_perms(STATE_PATH, 0o600)" scripts/state.py
grep -q "_harden_perms(STATE_DIR, 0o700)" scripts/state.py
echo "state.py OK"

# 3. consolidate_targets cleanup (Task 3a / CON-01)
test "$(grep -c already_applied scripts/consolidate_targets.py)" = "0"
test "$(grep -c "Companies already applied to" scripts/consolidate_targets.py)" = "0"
echo "consolidate_targets OK"

# 4. mine_connections guard (Task 3b / CON-03)
grep -q "WARNING: detect_header_rows fell through" scripts/mine_connections.py
grep -q "has_name_col" scripts/mine_connections.py
echo "mine_connections OK"

# 5. End-to-end perm check on the actual ~/.job-scout (only safe to run interactively;
#    skip in CI). Plan-level grep above is the gate; runtime verify is a smoke test.
```

All four `OK` lines must print.
</verification>

<success_criteria>
- `LEGACY_DATA_DIRS` constant + the legacy walk in `resolve_data_dir` are deleted from `scripts/state.py`
- `scripts/state.py` exports `_harden_perms` and calls it from both `write_state` and `read_state` (file 0o600, dir 0o700)
- `OSError` from chmod is caught and surfaces a WARNING (no abort)
- `scripts/consolidate_targets.py` no longer references `already_applied` or prints a "Companies already applied to" line
- `scripts/mine_connections.py` warns to stderr when `detect_header_rows` returns the silent default AND aborts with ERROR if neither a company col nor a name col survives
- Both `consolidate_targets.py` and `mine_connections.py` use the venv/--user install hint with NO `--break-system-packages` reference
- All grep-based acceptance criteria pass; all four task verify blocks exit 0
</success_criteria>

<output>
After completion, create `.planning/phases/01-schema-migration-paths-foundational-cleanup/01-02-SUMMARY.md` summarizing the legacy-chain deletion, perm hardening, dead-block removal (Task 3a), header-detection guard (Task 3b), and the install-hint partition with Plan 01.
</output>
</content>
</invoke>