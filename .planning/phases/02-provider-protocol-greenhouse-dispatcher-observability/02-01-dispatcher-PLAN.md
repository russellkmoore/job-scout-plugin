---
phase: 02-provider-protocol-greenhouse-dispatcher-observability
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - scripts/ats/__init__.py
  - scripts/ats/providers/__init__.py
  - scripts/ats/providers/base.py
  - scripts/ats/normalize.py
  - scripts/ats/runs_log.py
  - scripts/ats/dispatcher.py
autonomous: true
requirements: [DSP-01, DSP-02, DSP-03, DSP-04, DSP-05, DSP-06, DSP-07, DSP-08]

must_haves:
  truths:
    - "scripts/ats/ exists as a Python package with an __init__.py exposing a PROVIDERS registry dict (Phase 2 fills it with 'greenhouse' in Plan 02-02; the dict is created here, empty)"
    - "scripts/ats/providers/base.py defines a `Provider` typing.Protocol (Python 3.8 compat) with NAME, BOARD_URL_PATTERNS, detect, board_url_from_url, fetch, to_listing — duck-typed conformance, no inheritance"
    - "scripts/ats/normalize.py defines a frozen @dataclass `Listing` with required fields (company, title, location, url, posted_date, source) and optional fields (description, department, employment_type, raw); per-provider mappers raise ValueError on missing required fields (no silent default-to-empty)"
    - "scripts/ats/dispatcher.py uses ONE shared httpx.Client (instantiated once per run, closed in `finally`) with httpx.Timeout(connect=5, read=15) on every request"
    - "scripts/ats/dispatcher.py uses concurrent.futures.ThreadPoolExecutor(max_workers=20) and a per-provider _SEMAPHORES dict[str, threading.Semaphore] populated from config.json (defaults: greenhouse=10, ashby=8, lever=5, smartrecruiters=5, workday=3)"
    - "Dispatcher returns three distinct per-(company, provider) outcomes — OK_WITH_RESULTS / OK_ZERO / ERROR — defined as enum.Enum values, all three logged to runs.jsonl"
    - "Worker exception wrapper around each executor.submit captures + logs + re-raises so the dispatcher caller sees real errors (no silent swallow)"
    - "scripts/ats/runs_log.py is an append-only JSONL writer: opens runs.jsonl in 'a' mode, writes one JSON line per run, flushes; never loads + rewrites the entire file. Each line carries timestamp (ISO8601), wall_clock_seconds (float), per-provider counts (ok_with_results, ok_zero, error), per-(company, provider) listing counts (nested dict), field-completion telemetry (per-provider % of returned listings missing each required Listing field)"
    - "config.json kill-switch: when ats.concurrency_disabled is true, dispatcher falls back to sequential per-provider fetches (no executor, no semaphores) — same code path otherwise; the flag-loader code lives in dispatcher.py"
    - "All 5 modules use the sibling-script bootstrap. Modules in scripts/ats/* call os.path.dirname twice (file → ats → scripts); modules in scripts/ats/providers/* call os.path.dirname THREE times (file → providers → ats → scripts). Documented in scripts/ats/__init__.py docstring."
  artifacts:
    - path: scripts/ats/__init__.py
      provides: package marker + PROVIDERS registry (empty in this plan; greenhouse added in Plan 02-02)
      exports: ["PROVIDERS"]
    - path: scripts/ats/providers/__init__.py
      provides: empty package marker
      min_lines: 1
    - path: scripts/ats/providers/base.py
      provides: Provider Protocol + DetectionResult + FetchResult dataclasses (canonical contracts)
      exports: ["Provider", "DetectionResult", "FetchResult"]
    - path: scripts/ats/normalize.py
      provides: canonical Listing dataclass + raise-loudly mapper helper
      exports: ["Listing", "REQUIRED_FIELDS"]
    - path: scripts/ats/runs_log.py
      provides: append-only JSONL writer with timestamp + wall_clock + per-(company, provider) counts + field-completion telemetry
      exports: ["RunOutcome", "append_run", "compute_field_completion"]
    - path: scripts/ats/dispatcher.py
      provides: concurrent fetch + per-provider semaphore + shared httpx.Client + 3-state error logging + kill-switch
      exports: ["Outcome", "fetch_all", "DEFAULT_PROVIDER_CAPS"]
  key_links:
    - from: scripts/ats/dispatcher.py
      to: scripts/ats/normalize.py
      via: "from normalize import Listing"
      pattern: "from normalize import"
    - from: scripts/ats/dispatcher.py
      to: scripts/ats/runs_log.py
      via: "from runs_log import append_run, RunOutcome"
      pattern: "from runs_log import"
    - from: scripts/ats/dispatcher.py
      to: scripts/ats/providers (registry)
      via: "from ats import PROVIDERS  # iterates registry, never names a provider"
      pattern: "from ats import PROVIDERS"
    - from: scripts/ats/providers/base.py
      to: scripts/ats/normalize.py
      via: "Provider.to_listing returns Listing"
      pattern: "Listing"
---

<objective>
Build the substrate for Phase 2's vertical slice: the Provider Protocol contract (DSP-01), the canonical Listing dataclass (DSP-02), the concurrent dispatcher (DSP-03 shared httpx.Client + timeouts; DSP-04 ThreadPoolExecutor + per-provider semaphores; DSP-05 three-state outcomes; DSP-06 exception surfacing; DSP-08 kill-switch), and the append-only runs.jsonl writer (DSP-07). No real provider is exercised yet — Plan 02-02 ships Greenhouse against this contract.

Purpose: Validate the highest-risk decisions of the milestone (Listing shape, dispatcher concurrency model, Protocol contract, runs.jsonl schema) BEFORE paying the cost of 5 providers. Per ARCHITECTURE.md: "if any of those need revision, doing it after one provider is ~1 day of refactor; after five providers it's ~3 days."

Output: 6 new files under scripts/ats/. The dispatcher is callable but has an empty PROVIDERS registry until Plan 02-02 lands greenhouse.py and registers it.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/research/SUMMARY.md
@.planning/research/STACK.md
@.planning/research/ARCHITECTURE.md
@.planning/research/PITFALLS.md
@.planning/codebase/CONVENTIONS.md
@scripts/schema.py
@scripts/validate_data.py

<interfaces>
<!-- Existing schema constants this plan consumes -->
<!-- These already exist in scripts/schema.py (Phase 1 v=4 ground state). Use as-is. -->

From scripts/schema.py:
```python
MASTER_TARGETS_COLUMNS = [
    "company_name", "industry", "career_page_url", "ats_provider", "ats_board_url",
    "connection_names", "linkedin_connection_count", "application_status",
    "fit_notes", "last_checked", "data_source",
    "ats_slug_confidence", "last_ats_hit_date",
]
MASTER_TARGETS_VERSION = 4
TRACKER_COLUMNS = [..., "Source", "ATS Provider"]  # 16 cols total post-Phase-1
```

Phase 2 does NOT modify schema.py. The dispatcher and normalize.py reference Listing fields that map TO `Source` and `ATS Provider` (16-col tracker rows) at the call site (Plan 02-03 wires the report; tracker write happens in a future phase, not this one).

<!-- Sibling-script bootstrap pattern from existing scripts/ -->

From scripts/validate_data.py (canonical 1-level bootstrap, scripts/<file>.py):
```python
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)
from schema import MASTER_TARGETS_COLUMNS, ...
```

For scripts/ats/<file>.py (2-level — file → ats → scripts):
```python
SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)
from schema import MASTER_TARGETS_COLUMNS, ...
```

For scripts/ats/providers/<file>.py (3-level — file → providers → ats → scripts):
```python
SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)
from schema import MASTER_TARGETS_COLUMNS, ...
```

This pattern is documented in scripts/ats/__init__.py module docstring (Task 1) so future contributors don't have to count dirname() calls themselves.

<!-- ImportError install hint (CON-04 from Phase 1, applied verbatim) -->

Pattern, applied to httpx (NEW dep for Phase 2):
```python
try:
    import httpx
except ImportError:
    print(
        "ERROR: httpx not installed. Install with: "
        "python3 -m venv ~/.job-scout-venv && source ~/.job-scout-venv/bin/activate && pip install 'httpx>=0.27,<0.29'"
        "  (or: pip install --user 'httpx>=0.27,<0.29')."
        "  Note: pipx is for standalone CLI tools; httpx is a library and belongs in a project venv or user-site install.",
        file=sys.stderr,
    )
    sys.exit(1)
```

Note: rapidfuzz is reserved for Phase 5 dedup. DO NOT add a rapidfuzz import in Phase 2.

<!-- file-contract.md commitments from Phase 1 -->
<!-- runs.jsonl row at file-contract.md:36 — owner is /scout-run; created by validate_runs_log -->
<!-- daily/<DATE>/ats_raw/ row at file-contract.md:52 — created by ensure_today_subdirs -->
<!-- runs_log.py is the canonical writer for runs.jsonl. Do NOT write runs.jsonl from any other module. -->
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 0: Install httpx into the verify venv (one-time phase prerequisite)</name>
  <files></files>
  <read_first>
    No reads required. This task is a one-time prerequisite for the entire Phase 2 verify pipeline — every subsequent verify in 02-01, 02-02, and 02-03 imports `ats.dispatcher`, which `sys.exit(1)`s if httpx is missing.
  </read_first>
  <action>
    Install httpx into the user's verify venv at `~/.job-scout-venv` (the same interpreter every verify command in this phase invokes via `~/.job-scout-venv/bin/python3`).

    ```bash
    # Confirm the venv exists (created during Phase 1 by validate_data.py's
    # ImportError install hint flow, or by the user manually).
    test -x ~/.job-scout-venv/bin/python3 || {
        echo "ERROR: ~/.job-scout-venv/bin/python3 not found. Create the venv first:" >&2
        echo "  python3 -m venv ~/.job-scout-venv" >&2
        echo "  ~/.job-scout-venv/bin/pip install --upgrade pip" >&2
        exit 1
    }

    # Install httpx pinned to the version range from PROJECT.md / research/STACK.md.
    ~/.job-scout-venv/bin/pip install 'httpx>=0.27,<0.29'
    ```

    This is a ONE-TIME prerequisite for the Phase 2 verify pipeline; it is NOT a runtime install for end users. Runtime users hit the `ImportError` handler in `dispatcher.py` (Task 3) and follow its on-screen instructions, which guide them through the same venv-based install or the `pip install --user` alternative.

    Phase 2 verify commands all use `~/.job-scout-venv/bin/python3` explicitly (matching the convention from Phase 1 Plan 01-04's `tests/test_migration.py` verify); they do NOT use the system `python3`. So installing httpx into this one venv unlocks every downstream verify in 02-01, 02-02, and 02-03 without polluting the user's global Python environment.
  </action>
  <verify>
    <automated>
~/.job-scout-venv/bin/python3 -c "import httpx; assert httpx.__version__.startswith('0.2'), f'expected httpx 0.2x, got {httpx.__version__}'; print(f'Task 0 OK: httpx {httpx.__version__} importable in verify venv')"
    </automated>
  </verify>
  <done>
    `~/.job-scout-venv/bin/python3 -c "import httpx"` exits 0 and prints the installed version (must be in the 0.27.x..0.28.x range). The verify venv is now ready for every Phase 2 verify command. NO commit (no source files changed; this is a phase-level setup step).
  </done>
</task>

<task type="auto">
  <name>Task 1: Create scripts/ats/ package skeleton + Provider Protocol + canonical Listing</name>
  <files>scripts/ats/__init__.py, scripts/ats/providers/__init__.py, scripts/ats/providers/base.py, scripts/ats/normalize.py</files>
  <read_first>
    Read in this order, ONCE each — do not re-read:
    1. scripts/schema.py (verify Phase-1 v=4 ground state: MASTER_TARGETS_VERSION=4, TRACKER_COLUMNS has Source + ATS Provider).
    2. scripts/validate_data.py (1-level bootstrap pattern reference at lines 38-46).
    3. .planning/research/ARCHITECTURE.md "Pattern 1: Provider Protocol + Registry" section (already in context above).
    4. .planning/research/STACK.md "Per-provider concurrency caps summary" table (already in context).

    Do NOT read scripts/ats/ — it does not exist yet. This task creates it.
  </read_first>
  <action>
    Create four files. Use the Write tool for each (never heredoc/cat).

    **File 1: scripts/ats/__init__.py** — package marker + PROVIDERS registry. Module docstring documents the sibling-bootstrap pattern (1/2/3-level dirname counts) so future contributors don't have to figure it out. Body declares `PROVIDERS: Dict[str, "Provider"] = {}` (typed empty dict; Plan 02-02 populates "greenhouse").

    Required content (verbatim — adjust only docstring prose):
    ```python
    """
    scripts/ats — ATS-first sourcing layer for v0.4.

    Package containing the Provider Protocol, canonical Listing, concurrent
    dispatcher, and append-only runs.jsonl writer. Per-provider modules live
    under scripts/ats/providers/ and are registered in PROVIDERS below.

    The dispatcher and detector iterate PROVIDERS.items() and never name a
    specific provider — adding Jobvite/Taleo in v0.5+ is one new file +
    one registry entry.

    Sibling-script bootstrap (used by every module in this package that
    imports from scripts/schema.py):

      For scripts/ats/<file>.py (e.g. dispatcher.py, normalize.py):
          SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
          # file → ats → scripts (2 dirname calls)

      For scripts/ats/providers/<file>.py (e.g. greenhouse.py):
          SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
          # file → providers → ats → scripts (3 dirname calls)

      Then:
          if SCRIPTS_DIR not in sys.path:
              sys.path.insert(0, SCRIPTS_DIR)
          from schema import MASTER_TARGETS_COLUMNS  # etc.
    """

    from typing import Dict, TYPE_CHECKING

    if TYPE_CHECKING:
        from .providers.base import Provider

    # Provider registry. Populated by per-provider modules at import time
    # (see scripts/ats/providers/__init__.py and individual provider modules).
    # Plan 02-01 ships this as empty; Plan 02-02 populates "greenhouse".
    PROVIDERS: Dict[str, "Provider"] = {}
    ```

    **File 2: scripts/ats/providers/__init__.py** — empty package marker. One-line module docstring is sufficient:
    ```python
    """scripts/ats/providers — one module per ATS, all conforming to the Provider Protocol in base.py."""
    ```

    **File 3: scripts/ats/providers/base.py** — Provider Protocol (typing.Protocol for Python 3.8+ duck-typed conformance) + DetectionResult + FetchResult dataclasses. NO inheritance — providers conform by shape.

    Required header (verbatim):
    ```python
    """
    base.py — Provider Protocol + canonical detection/fetch result shapes.

    Every provider module under scripts/ats/providers/ must conform to the
    `Provider` protocol below. Conformance is by shape (typing.Protocol, Python 3.8+
    `Protocol` runtime-checkable optional). The dispatcher and detector are
    written against this protocol — they never import a specific provider.

    DSP-01 (per D-01 Phase 2 locked decision): NO base class, NO inheritance.
    All 5 v0.4 providers (greenhouse, lever, ashby, smartrecruiters, workday)
    conform via duck typing.
    """
    from dataclasses import dataclass, field
    from enum import Enum
    from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
    ```

    Then define `class DetectionStatus(Enum)` with members `CONFIRMED`, `BORDERLINE`, `NOT_FOUND`, `ERROR` (Plan 02-02 + Phase 3 will use these; landing them now means provider modules don't have to re-invent the enum).

    Then define a frozen `@dataclass` `DetectionResult`:
    - `provider: str` (NAME of the provider, or "" on NOT_FOUND)
    - `status: DetectionStatus`
    - `board_url: Optional[str]`
    - `confidence: float` (0.0–1.0)
    - `evidence: Dict[str, Any] = field(default_factory=dict)` (e.g. job_count, returned_company_name; opaque to dispatcher)

    Then define a frozen `@dataclass` `FetchResult`:
    - `provider: str`
    - `company_slug: str`
    - `listings: List["Listing"]` (forward ref; the dataclass lives in normalize.py — use string ref to avoid circular import)
    - `raw: List[Dict[str, Any]]` (provider-shaped dicts; persisted to ats_raw/ for debuggability)
    - `http_status: int` (200, 404, 401, etc.; -1 if no response)

    Then define the Protocol verbatim:
    ```python
    @runtime_checkable
    class Provider(Protocol):
        """Duck-typed contract for an ATS provider module.

        Required class-level attributes:
            NAME: str — registry key, e.g. "greenhouse"
            BOARD_URL_PATTERNS: List[str] — regex strings matching that ATS's
                board URL shape (e.g. r"^https?://boards-api\\.greenhouse\\.io/v1/boards/([^/]+)").

        Required callables:
            detect(company_slug, name, client)
                Probe the provider's API. Returns DetectionResult. Caller
                supplies a shared httpx.Client.
            board_url_from_url(url)
                Given a career-page or detected URL, return the canonical board
                URL the dispatcher will fetch from, or None if not normalizable.
            fetch(slug, client, semaphore)
                Acquire `semaphore` for the duration of the HTTP call (the
                caller has chosen the per-provider semaphore from
                dispatcher._SEMAPHORES). Returns FetchResult.
                Raises httpx.HTTPError on transport failure; the dispatcher's
                worker wrapper will catch + log + bucket as ERROR.
            to_listing(payload)
                Map ONE provider-shaped dict to a canonical Listing. Raises
                ValueError on missing required Listing fields (no silent
                default-to-empty — DSP-02 locked decision).
        """
        NAME: str
        BOARD_URL_PATTERNS: List[str]

        def detect(self, company_slug: str, name: str, client: "httpx.Client") -> DetectionResult: ...
        def board_url_from_url(self, url: str) -> Optional[str]: ...
        def fetch(self, slug: str, client: "httpx.Client", semaphore: "threading.Semaphore") -> FetchResult: ...
        def to_listing(self, payload: Dict[str, Any]) -> "Listing": ...
    ```

    Use `if TYPE_CHECKING:` block to import `httpx` and `threading` and `Listing` (from `..normalize`) for forward references — DO NOT import them at module top (creates circular import with normalize.py and adds httpx as a hard import requirement of base.py, which Phase 3 detection logic doesn't need).

    Sibling bootstrap is NOT needed in base.py because base.py does NOT import from schema.py — it has no need for MASTER_TARGETS_COLUMNS. Add a comment at top of file noting this for future maintainers: `# NOTE: base.py does NOT import from scripts/schema.py — no sibling bootstrap needed.`

    **File 4: scripts/ats/normalize.py** — canonical Listing dataclass with raise-loudly mappers.

    Required header (verbatim):
    ```python
    """
    normalize.py — Canonical Listing dataclass + raise-loudly field validation.

    DSP-02 (locked decision): per-provider mappers raise ValueError on missing
    required fields. NO silent default-to-empty. This is what makes ATS schema
    drift (Pitfall 7) visible at the dispatcher's worker boundary instead of
    propagating empty-record garbage into scoring.

    Field-completion telemetry (DSP-07) reads REQUIRED_FIELDS to compute the
    per-provider missing-field rate written to runs.jsonl.
    """
    from dataclasses import dataclass, field, asdict
    from typing import Any, Dict, List, Optional
    ```

    Sibling bootstrap is NOT needed in normalize.py for this plan (no schema.py imports yet). Plan 02-02's greenhouse.py will use bootstrap; this file does not.

    Define the dataclass verbatim (using `frozen=True` for immutability — Python 3.8 supports `slots` only via `@dataclass(slots=True)` in 3.10+, so do NOT use slots; just frozen):
    ```python
    REQUIRED_FIELDS = ("company", "title", "location", "url", "posted_date", "source")
    OPTIONAL_FIELDS = ("description", "department", "employment_type", "raw")


    @dataclass(frozen=True)
    class Listing:
        """Canonical ATS listing — one shape for all 5 providers.

        Required fields (DSP-02): per-provider mappers raise ValueError if any
        of these is missing or empty-string. Empty optional fields are fine.

        `source` carries the source tag the report renders (e.g. "ats:greenhouse",
        "ats:lever", or "linkedin"). Per OUT-01 (Phase 6), every report row must
        carry a source= annotation; this is where it originates.

        `posted_date` is ISO 8601 (YYYY-MM-DD). Provider mappers normalize
        per-provider date shapes (e.g. Workday's "Posted 5 Days Ago") to ISO
        before constructing the Listing.

        `raw` is the per-provider dict the listing was built from — kept on the
        Listing for debug/replay. The dispatcher persists raw[] to
        daily/<DATE>/ats_raw/<provider>/<company>.json for SC-2 inspectability.
        """
        # Required (DSP-02 — raise loudly on absent)
        company: str
        title: str
        location: str
        url: str
        posted_date: str  # ISO 8601 date; "" is INVALID — raise in mapper
        source: str  # "ats:<provider>" or "linkedin"

        # Optional (empty string / None is valid)
        description: str = ""
        department: str = ""
        employment_type: str = ""
        raw: Optional[Dict[str, Any]] = None

        def __post_init__(self):
            # Raise loudly on missing required fields. The dispatcher worker
            # wrapper catches this as a per-(company, provider) ERROR and logs
            # it to runs.jsonl with the failing field name — DSP-06.
            for fname in REQUIRED_FIELDS:
                value = getattr(self, fname)
                if value is None or (isinstance(value, str) and not value.strip()):
                    raise ValueError(
                        f"Listing.{fname} is required but was empty/None "
                        f"(company={self.company!r}, source={self.source!r}). "
                        f"Per-provider mapper must populate this — DSP-02."
                    )

        def to_dict(self) -> Dict[str, Any]:
            return asdict(self)


    def compute_missing_fields(listing_dict: Dict[str, Any]) -> List[str]:
        """Return list of REQUIRED_FIELDS that are empty/missing in listing_dict.

        Used by runs_log.py for field-completion telemetry. Operates on a dict
        (not a Listing) because Listing.__post_init__ would raise — we want to
        count, not crash.
        """
        missing = []
        for fname in REQUIRED_FIELDS:
            v = listing_dict.get(fname)
            if v is None or (isinstance(v, str) and not v.strip()):
                missing.append(fname)
        return missing
    ```

    NO CLI for normalize.py or base.py — they are import-only libraries (matches schema.py's "import-only, no side effects" convention from CONVENTIONS.md).
  </action>
  <verify>
    <automated>
test -f scripts/ats/__init__.py && \
test -f scripts/ats/providers/__init__.py && \
test -f scripts/ats/providers/base.py && \
test -f scripts/ats/normalize.py && \
grep -q "PROVIDERS: Dict\[str" scripts/ats/__init__.py && \
grep -q "from typing import.*Protocol" scripts/ats/providers/base.py && \
grep -q "@runtime_checkable" scripts/ats/providers/base.py && \
grep -q "class Provider(Protocol)" scripts/ats/providers/base.py && \
grep -q "NAME: str" scripts/ats/providers/base.py && \
grep -q "BOARD_URL_PATTERNS: List\[str\]" scripts/ats/providers/base.py && \
grep -q "@dataclass" scripts/ats/normalize.py && \
grep -q "frozen=True" scripts/ats/normalize.py && \
grep -q "company: str" scripts/ats/normalize.py && \
grep -q "title: str" scripts/ats/normalize.py && \
grep -q "posted_date: str" scripts/ats/normalize.py && \
grep -q "source: str" scripts/ats/normalize.py && \
grep -q "REQUIRED_FIELDS" scripts/ats/normalize.py && \
grep -q "raise ValueError" scripts/ats/normalize.py && \
~/.job-scout-venv/bin/python3 -c "
import sys; sys.path.insert(0, 'scripts')
from ats import PROVIDERS
assert isinstance(PROVIDERS, dict), 'PROVIDERS must be a dict'
assert len(PROVIDERS) == 0, f'Plan 02-01 must ship empty PROVIDERS, got {list(PROVIDERS.keys())}'
from ats.providers.base import Provider, DetectionResult, FetchResult, DetectionStatus
assert hasattr(Provider, '__class_getitem__') or hasattr(Provider, '_is_protocol'), 'Provider must be a typing.Protocol'
from ats.normalize import Listing, REQUIRED_FIELDS, compute_missing_fields
# Construct valid Listing
ok = Listing(company='Stripe', title='SWE', location='SF', url='https://example/x', posted_date='2026-04-28', source='ats:greenhouse')
assert ok.company == 'Stripe'
# Missing required field must raise
try:
    bad = Listing(company='Stripe', title='', location='SF', url='https://x', posted_date='2026-04-28', source='ats:greenhouse')
    raise AssertionError('Listing must raise on empty title')
except ValueError as e:
    assert 'title' in str(e)
# compute_missing_fields counts (not crashes) on dict input
missing = compute_missing_fields({'company': 'Stripe', 'title': '', 'location': 'SF', 'url': 'x', 'posted_date': '', 'source': 'ats:greenhouse'})
assert set(missing) == {'title', 'posted_date'}, f'expected title+posted_date missing, got {missing}'
print('Task 1 OK')
"
    </automated>
  </verify>
  <done>
    Four files exist; Provider Protocol + Listing dataclass + REQUIRED_FIELDS + compute_missing_fields are importable from `scripts/`; PROVIDERS is an empty dict (greenhouse lands in Plan 02-02); Listing raises ValueError on missing required fields; compute_missing_fields returns a list (does not raise) on a dict with missing fields. Commit message: `feat(02-01): add scripts/ats package skeleton + Provider Protocol + Listing (DSP-01, DSP-02)`.
  </done>
</task>

<task type="auto">
  <name>Task 2: scripts/ats/runs_log.py — append-only JSONL writer with per-(company, provider) telemetry</name>
  <files>scripts/ats/runs_log.py</files>
  <read_first>
    Read ONCE:
    1. scripts/ats/normalize.py (just created in Task 1 — for `compute_missing_fields`, `REQUIRED_FIELDS`).
    2. .planning/research/PITFALLS.md "Pitfall 1" section (already in context above) — the trust-on-zero defensibility argument that requires per-(company, provider) hit history from day one.
    3. skills/job-scout/references/file-contract.md (already in context) — runs.jsonl row at line 36 declares this module as the canonical writer.
  </read_first>
  <action>
    Create scripts/ats/runs_log.py. Single concern: append-only JSONL writer.

    Module docstring (verbatim opener):
    ```python
    """
    runs_log.py — Append-only writer for <data_dir>/runs.jsonl.

    DSP-07 (locked Phase 2 decision): exactly one JSON line per /scout-run.
    Append-only — opens runs.jsonl in 'a' mode, writes one line, flushes.
    NEVER loads + rewrites the entire file (a 365-run file would balloon
    /scout-run wall-clock; rotation is a v0.5+ concern per OOS list).

    Per-line schema (the trust-on-zero defensibility — PITFALLS.md Pitfall 1):
        {
          "timestamp": "2026-04-28T13:55:00Z",
          "wall_clock_seconds": 234.7,
          "providers": {
            "greenhouse": {
              "ok_with_results": 12,
              "ok_zero": 3,
              "error": 1,
              "field_completion": {
                "company": 1.0, "title": 1.0, "location": 0.97,
                "url": 1.0, "posted_date": 0.94, "source": 1.0
              }
            }
          },
          "per_company_provider": {
            "stripe|greenhouse": {"outcome": "OK_WITH_RESULTS", "listing_count": 5},
            "lululemon|greenhouse": {"outcome": "OK_ZERO", "listing_count": 0}
          }
        }

    Without per_company_provider hit counts, "trust ATS on 0/error" silently
    zeroes out clusters of companies. With them, Phase 5's ATS-regression-suspect
    warnings have something to compare against.
    """
    import json
    import os
    import sys
    from dataclasses import dataclass, field
    from datetime import datetime, timezone
    from enum import Enum
    from typing import Any, Dict, List, Optional, Tuple
    ```

    Sibling bootstrap (2-level — file → ats → scripts) — needed because this module imports from `..normalize` (a sibling within the package), which is fine via direct package-relative path; we DO NOT need scripts/schema.py here. Skip the bootstrap; document the choice:
    ```python
    # NOTE: runs_log.py does NOT import from scripts/schema.py — no sibling
    # bootstrap needed. It DOES import from sibling normalize.py via
    # absolute path (`from ats.normalize import ...`) so callers running
    # the script as a module (python3 -m ats.runs_log) work; for direct
    # script invocation we'd need a 2-level bootstrap, but DSP-07 doesn't
    # require a CLI for this module — it's library-only.
    ```

    Wait — that's wrong. The CLI dispatcher calls runs_log.append_run() programmatically, but skill prompts may want a CLI entry point too (matches Pattern 3 from ARCHITECTURE.md). Decision (Claude's discretion within the locked decisions): provide a thin CLI subcommand `append-run <path-to-runs.jsonl> <stats.json>` so future skill prompts can drive it directly. This requires the 2-level sibling bootstrap so direct invocation works:
    ```python
    SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, SCRIPTS_DIR)
    # Sibling import within the package; bootstrap covers both direct script
    # invocation (python3 scripts/ats/runs_log.py) and module-style
    # (python3 -m ats.runs_log) — they resolve `from ats.normalize` identically.
    from ats.normalize import compute_missing_fields, REQUIRED_FIELDS
    ```

    Define an Enum for the 3-state outcome (DSP-05). The dispatcher imports this same enum:
    ```python
    class RunOutcome(Enum):
        OK_WITH_RESULTS = "OK_WITH_RESULTS"
        OK_ZERO = "OK_ZERO"
        ERROR = "ERROR"
    ```

    Provide a helper to compute field-completion telemetry given a list of listing dicts (per-provider call site supplies the dicts; raw Listing objects must be converted via .to_dict() at the call site to avoid Listing's required-field validation in compute_missing_fields):
    ```python
    def compute_field_completion(listing_dicts: List[Dict[str, Any]]) -> Dict[str, float]:
        """Per-required-field completion rate (% of listings WITH the field non-empty).

        Returns {field_name: 0.0..1.0}. Empty listing_dicts -> all 1.0
        (vacuous truth — no listings can't be missing fields).
        """
        if not listing_dicts:
            return {f: 1.0 for f in REQUIRED_FIELDS}
        n = len(listing_dicts)
        completion: Dict[str, float] = {}
        for fname in REQUIRED_FIELDS:
            present = sum(
                1 for d in listing_dicts
                if d.get(fname) and (not isinstance(d.get(fname), str) or d.get(fname).strip())
            )
            completion[fname] = round(present / n, 4)
        return completion
    ```

    Provide the main writer (DSP-07 — append-only, atomic, no rewrite):
    ```python
    def append_run(
        runs_log_path: str,
        wall_clock_seconds: float,
        per_provider_outcomes: Dict[str, Dict[str, int]],
        per_company_provider: Dict[str, Dict[str, Any]],
        per_provider_listings: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Append one JSON line to runs.jsonl.

        Args:
            runs_log_path: absolute path to <data_dir>/runs.jsonl. Caller has
                already expanded `~`. Phase 1 SCH-01 guarantees the file
                exists (validate_runs_log).
            wall_clock_seconds: total /scout-run wall clock (float).
            per_provider_outcomes: {"greenhouse": {"ok_with_results": 12,
                "ok_zero": 3, "error": 1}}. Keys are RunOutcome enum string
                values, values are counts.
            per_company_provider: {"stripe|greenhouse": {"outcome":
                "OK_WITH_RESULTS", "listing_count": 5}}. Compound key uses
                "|" separator (no slug should contain |). Used by Phase 5's
                ATS-regression-suspect detection.
            per_provider_listings: {"greenhouse": [listing_dict, ...]}.
                Used to compute field_completion telemetry per provider.
                Pass listing dicts (Listing.to_dict()), NOT Listing objects.
            timestamp: ISO 8601 (defaults to now()). Override for tests.

        Returns: the JSON-encoded line dict (also written to the file).
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        providers_block: Dict[str, Dict[str, Any]] = {}
        for provider, counts in per_provider_outcomes.items():
            providers_block[provider] = dict(counts)
            if per_provider_listings and provider in per_provider_listings:
                providers_block[provider]["field_completion"] = compute_field_completion(
                    per_provider_listings[provider]
                )

        line = {
            "timestamp": timestamp,
            "wall_clock_seconds": round(float(wall_clock_seconds), 3),
            "providers": providers_block,
            "per_company_provider": per_company_provider,
        }

        # Append-only: open in 'a' mode, write the JSON line + newline, flush.
        # Never read the file. Never rewrite. DSP-07 atomicity contract.
        with open(runs_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False, separators=(",", ":")) + "\n")
            f.flush()

        return line
    ```

    Provide the CLI subcommand (matches state.py / tracker_utils.py shape):
    ```python
    if __name__ == "__main__":
        if len(sys.argv) < 2:
            print("Usage: python3 scripts/ats/runs_log.py <command> [args...]", file=sys.stderr)
            print("Commands:", file=sys.stderr)
            print("  append-run <runs_log_path> <stats.json>", file=sys.stderr)
            print("    stats.json shape: {wall_clock_seconds, per_provider_outcomes,", file=sys.stderr)
            print("                       per_company_provider[, per_provider_listings]}", file=sys.stderr)
            sys.exit(1)
        cmd = sys.argv[1]
        if cmd == "append-run":
            if len(sys.argv) < 4:
                print("Usage: append-run <runs_log_path> <stats.json>", file=sys.stderr)
                sys.exit(1)
            runs_log_path = os.path.expanduser(sys.argv[2])
            stats_path = os.path.expanduser(sys.argv[3])
            with open(stats_path, "r", encoding="utf-8") as f:
                stats = json.load(f)
            line = append_run(
                runs_log_path=runs_log_path,
                wall_clock_seconds=stats["wall_clock_seconds"],
                per_provider_outcomes=stats["per_provider_outcomes"],
                per_company_provider=stats["per_company_provider"],
                per_provider_listings=stats.get("per_provider_listings"),
                timestamp=stats.get("timestamp"),
            )
            print(json.dumps({"appended": True, "line": line}, indent=2))
            sys.exit(0)
        print(f"ERROR: Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)
    ```

    Do NOT add httpx imports or threading imports — runs_log.py is purely a JSONL writer.
  </action>
  <verify>
    <automated>
test -f scripts/ats/runs_log.py && \
grep -q "class RunOutcome" scripts/ats/runs_log.py && \
grep -q "OK_WITH_RESULTS" scripts/ats/runs_log.py && \
grep -q "OK_ZERO" scripts/ats/runs_log.py && \
grep -qE "^\s*ERROR\s*=" scripts/ats/runs_log.py && \
grep -q "def append_run" scripts/ats/runs_log.py && \
grep -q "def compute_field_completion" scripts/ats/runs_log.py && \
grep -q 'open(runs_log_path, "a"' scripts/ats/runs_log.py && \
grep -q "f.flush()" scripts/ats/runs_log.py && \
~/.job-scout-venv/bin/python3 -c "
import sys, os, tempfile, json
sys.path.insert(0, 'scripts')
from ats.runs_log import append_run, compute_field_completion, RunOutcome
# Smoke 1: enum has all 3 outcomes
assert RunOutcome.OK_WITH_RESULTS.value == 'OK_WITH_RESULTS'
assert RunOutcome.OK_ZERO.value == 'OK_ZERO'
assert RunOutcome.ERROR.value == 'ERROR'
# Smoke 2: append_run actually appends and is idempotent (writes 2 lines after 2 calls)
with tempfile.TemporaryDirectory() as td:
    p = os.path.join(td, 'runs.jsonl')
    open(p, 'w').close()  # mimic Phase-1 validate_runs_log
    line1 = append_run(p, 1.5, {'greenhouse': {'ok_with_results': 1, 'ok_zero': 0, 'error': 0}}, {'stripe|greenhouse': {'outcome': 'OK_WITH_RESULTS', 'listing_count': 1}})
    line2 = append_run(p, 2.5, {'greenhouse': {'ok_with_results': 0, 'ok_zero': 1, 'error': 0}}, {'lululemon|greenhouse': {'outcome': 'OK_ZERO', 'listing_count': 0}})
    with open(p) as f:
        lines = [json.loads(L) for L in f if L.strip()]
    assert len(lines) == 2, f'expected 2 appended lines, got {len(lines)}'
    assert lines[0]['wall_clock_seconds'] == 1.5
    assert lines[1]['wall_clock_seconds'] == 2.5
    assert lines[0]['providers']['greenhouse']['ok_with_results'] == 1
    assert lines[1]['providers']['greenhouse']['ok_zero'] == 1
# Smoke 3: field_completion telemetry on listing dicts
fc = compute_field_completion([
    {'company': 'Stripe', 'title': 'SWE', 'location': 'SF', 'url': 'x', 'posted_date': '2026-04-28', 'source': 'ats:greenhouse'},
    {'company': 'Stripe', 'title': 'PM',  'location': '',   'url': 'y', 'posted_date': '2026-04-28', 'source': 'ats:greenhouse'},
])
assert fc['location'] == 0.5, f'expected 0.5, got {fc[\"location\"]}'
assert fc['title'] == 1.0
assert fc['posted_date'] == 1.0
print('Task 2 OK')
"
    </automated>
  </verify>
  <done>
    runs_log.py exists, exposes RunOutcome enum + append_run + compute_field_completion; append_run opens in 'a' mode and flushes (no read-rewrite); 2 sequential calls produce 2 JSONL lines; field_completion counts present-vs-missing correctly. CLI subcommand `append-run` invokable. Commit: `feat(02-01): add runs_log.py append-only JSONL writer with per-(company, provider) telemetry (DSP-05, DSP-07)`.
  </done>
</task>

<task type="auto">
  <name>Task 3: scripts/ats/dispatcher.py — concurrent fetch + per-provider semaphores + 3-state outcomes + kill-switch</name>
  <files>scripts/ats/dispatcher.py</files>
  <read_first>
    Read ONCE:
    1. scripts/ats/__init__.py, scripts/ats/normalize.py, scripts/ats/runs_log.py (just created — for PROVIDERS, Listing, RunOutcome, append_run).
    2. scripts/ats/providers/base.py (Provider Protocol — dispatcher's input shape).
    3. .planning/research/STACK.md "Concurrency Pattern (Recommended Implementation Sketch)" section (already in context).
    4. .planning/research/PITFALLS.md Pitfall 5 (concurrent HTTP shared-state bugs — already in context).
  </read_first>
  <action>
    Create scripts/ats/dispatcher.py. This is the heaviest file in Plan 02-01 (DSP-03 + DSP-04 + DSP-05 + DSP-06 + DSP-08 land here).

    Module docstring (verbatim opener):
    ```python
    """
    dispatcher.py — Concurrent ATS fetch with per-provider semaphores + 3-state outcomes.

    Locked Phase 2 decisions implemented here:
      DSP-03: ONE shared httpx.Client (instantiated once per run, closed in
              `finally`), with httpx.Timeout(connect=5, read=15) on every call.
      DSP-04: ThreadPoolExecutor(max_workers=20) + per-provider
              threading.Semaphore. Caps loaded from config.json
              (ats.provider_concurrency_caps); defaults match research/STACK.md.
      DSP-05: Three-state outcome per (company, provider): OK_WITH_RESULTS
              (n>=1 listings), OK_ZERO (200 + 0 jobs), ERROR (any non-200,
              network failure, parse failure). All three logged to runs.jsonl.
      DSP-06: Worker exception wrapper captures + logs + bucket-as-ERROR; the
              caller (skill code) sees aggregated outcomes instead of raw raises.
      DSP-08: ats.concurrency_disabled kill-switch — when true, falls back to
              sequential per-provider fetches (no executor, no semaphores).
              Same code path otherwise.

    Anti-features baked-in (locked):
      - NO retry-on-403/429 within a run. "Tomorrow's run" is the correct
        backoff. (PROJECT.md anti-feature.)
      - NO Chrome fallback on 0/error. (PROJECT.md milestone-defining decision.)
      - NO worker-thread tracker writes. The dispatcher returns aggregated
        outcomes; the skill (or future ats/dedupe.py) calls tracker_utils.append
        on the main thread. (PITFALLS Pitfall 5: shared-state bugs.)
    """
    import json
    import os
    import sys
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor, Future
    from contextlib import contextmanager
    from dataclasses import dataclass, field
    from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple
    ```

    httpx ImportError block (CON-04 install hint per the locked Phase-2 decision):
    ```python
    try:
        import httpx
    except ImportError:
        print(
            "ERROR: httpx not installed. Install with: "
            "python3 -m venv ~/.job-scout-venv && source ~/.job-scout-venv/bin/activate && pip install 'httpx>=0.27,<0.29'"
            "  (or: pip install --user 'httpx>=0.27,<0.29')."
            "  Note: pipx is for standalone CLI tools; httpx is a library and belongs in a project venv or user-site install.",
            file=sys.stderr,
        )
        sys.exit(1)
    ```

    Sibling bootstrap (2-level — file → ats → scripts):
    ```python
    SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, SCRIPTS_DIR)
    from ats.normalize import Listing
    from ats.runs_log import RunOutcome, append_run
    from ats.providers.base import FetchResult, DetectionResult
    from ats import PROVIDERS
    ```

    Constants (verbatim):
    ```python
    # Per-provider concurrency caps. From research/STACK.md (HIGH confidence,
    # derived from observed latency + tenant-isolation patterns). Caps live in
    # config.json under ats.provider_concurrency_caps; this dict is the FALLBACK
    # if config.json doesn't override (matches "single source of truth" but
    # tolerates a missing key).
    DEFAULT_PROVIDER_CAPS = {
        "greenhouse": 10,
        "ashby": 8,
        "lever": 5,
        "smartrecruiters": 5,
        "workday": 3,
    }

    # Total executor pool size. Matches sum of caps (31) + headroom; capped at
    # 20 because Phase 2 only exercises greenhouse (cap=10) and 20 still
    # honors the per-provider caps when Phase 4 ships the rest.
    DEFAULT_MAX_WORKERS = 20

    # httpx defaults — explicit timeout on every request (DSP-03).
    DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0)

    # User-Agent — some Workday tenants 403 on default Python UAs (per
    # research/STACK.md). Phase 4 hits this; setting it now is free.
    DEFAULT_USER_AGENT = "job-scout/0.4 (+claude-code-plugin)"

    # Module-level mutable: per-provider semaphores. Lazy-initialized on first
    # fetch_all() call so config.json overrides can take effect (the caller
    # passes the loaded caps).
    _SEMAPHORES: Dict[str, threading.Semaphore] = {}
    _SEMAPHORE_LOCK = threading.Lock()
    ```

    The 3-state Outcome wrapper. Use the same `RunOutcome` enum from runs_log.py — DON'T re-define. Plus a per-(company, provider) result struct:
    ```python
    @dataclass
    class FetchOutcome:
        """Per-(company, provider) outcome from one fetch attempt."""
        company_slug: str
        provider: str
        outcome: RunOutcome  # OK_WITH_RESULTS | OK_ZERO | ERROR
        listings: List[Listing] = field(default_factory=list)
        raw: List[Dict[str, Any]] = field(default_factory=list)
        http_status: int = -1
        error: Optional[str] = None  # populated on ERROR; (type, message) string
        elapsed_seconds: float = 0.0
    ```

    Config loader (DSP-04 + DSP-08 — both flag-readers live here):
    ```python
    def load_caps_and_kill_switch(config_path: str) -> Tuple[Dict[str, int], bool]:
        """Read config.json's ats.provider_concurrency_caps and ats.concurrency_disabled.

        Falls back to DEFAULT_PROVIDER_CAPS if the section is missing. The
        kill-switch defaults to False. Reads happen ONCE per /scout-run at
        the entry to fetch_all() — config changes mid-run are ignored.
        """
        caps = dict(DEFAULT_PROVIDER_CAPS)
        kill = False
        if os.path.isfile(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                ats = cfg.get("ats", {})
                user_caps = ats.get("provider_concurrency_caps", {})
                for k, v in user_caps.items():
                    if isinstance(v, int) and v > 0:
                        caps[k] = v
                kill = bool(ats.get("concurrency_disabled", False))
            except (OSError, json.JSONDecodeError) as e:
                print(f"WARNING: could not parse {config_path} (using defaults): {e}", file=sys.stderr)
        return caps, kill
    ```

    Semaphore initializer (Pitfall 5 — single global per-provider semaphore, NOT per-thread):
    ```python
    def _init_semaphores(caps: Dict[str, int]) -> None:
        global _SEMAPHORES
        with _SEMAPHORE_LOCK:
            _SEMAPHORES = {p: threading.Semaphore(n) for p, n in caps.items()}


    @contextmanager
    def _gate(provider: str) -> Iterator[None]:
        sem = _SEMAPHORES.get(provider)
        if sem is None:
            # Provider not in caps dict — fall back to a Semaphore(1) gate to
            # prevent unbounded concurrency on unknown providers. Logged so
            # operator knows config.json drifted.
            print(f"WARNING: no semaphore configured for provider {provider!r}; using Semaphore(1)", file=sys.stderr)
            sem = threading.Semaphore(1)
        sem.acquire()
        try:
            yield
        finally:
            sem.release()
    ```

    Per-task wrapper that surfaces exceptions (DSP-06):
    ```python
    def _execute_one(
        company_slug: str,
        provider_name: str,
        client: "httpx.Client",
    ) -> FetchOutcome:
        """Run one (company, provider) fetch. Catches all exceptions, buckets as ERROR.

        DSP-06 (two-tier handling per the updated REQUIREMENTS.md DSP-06 wording):

        Tier 1 — RE-RAISE: KeyboardInterrupt, MemoryError, SystemExit. These
        are unrecoverable signals (user Ctrl-C, OOM, sys.exit() inside a
        provider). Bucketing them as ERROR would silently swallow operator
        intent and OS conditions; instead we propagate them out of the worker
        thread, where ThreadPoolExecutor surfaces them via Future.result()
        in fetch_all and the run halts.

        Tier 2 — BUCKET AS ERROR: every other Exception subclass. These are
        recoverable per-fetch failures — httpx.HTTPError (transport),
        httpx.HTTPStatusError (4xx/5xx), JSONDecodeError, ValueError from
        Listing.__post_init__ (missing required field per DSP-02), provider
        parse errors. Each gets logged to stderr with (provider, company,
        error_type, error_message) context AND returned as a FetchOutcome with
        outcome=ERROR so it's visible in runs.jsonl. The Future returned by
        ThreadPoolExecutor.submit() is then always-successful from the
        executor's POV (no swallowed Future.exception()) — the caller iterates
        outcomes and sees ERROR explicitly with the message.
        """
        provider = PROVIDERS.get(provider_name)
        if provider is None:
            return FetchOutcome(
                company_slug=company_slug,
                provider=provider_name,
                outcome=RunOutcome.ERROR,
                error=f"unknown provider {provider_name!r} (not in PROVIDERS registry)",
            )
        sem = _SEMAPHORES.get(provider_name)
        if sem is None:
            return FetchOutcome(
                company_slug=company_slug,
                provider=provider_name,
                outcome=RunOutcome.ERROR,
                error=f"no semaphore for provider {provider_name!r} (config drift)",
            )

        t0 = time.monotonic()
        try:
            with _gate(provider_name):
                fetch_result = provider.fetch(company_slug, client, sem)
            elapsed = time.monotonic() - t0
            if not fetch_result.listings:
                return FetchOutcome(
                    company_slug=company_slug,
                    provider=provider_name,
                    outcome=RunOutcome.OK_ZERO,
                    listings=[],
                    raw=fetch_result.raw,
                    http_status=fetch_result.http_status,
                    elapsed_seconds=elapsed,
                )
            return FetchOutcome(
                company_slug=company_slug,
                provider=provider_name,
                outcome=RunOutcome.OK_WITH_RESULTS,
                listings=fetch_result.listings,
                raw=fetch_result.raw,
                http_status=fetch_result.http_status,
                elapsed_seconds=elapsed,
            )
        except (KeyboardInterrupt, MemoryError, SystemExit):
            # DSP-06 (locked) two-tier exception handling: truly unrecoverable
            # exceptions re-raise and halt the run. Bucketing these as ERROR
            # would silently lose Ctrl-C and OOM signals — the user expects
            # those to propagate.
            raise
        except Exception as exc:  # noqa: BLE001 — DSP-06 recoverable catch-all
            # All recoverable per-fetch exceptions (httpx.HTTPError subclasses,
            # ValueError from to_listing's missing-required-field, JSONDecodeError,
            # etc.) bucket as ERROR with full (provider, company, error_type,
            # error_message) context. The dispatcher caller sees them via
            # runs.jsonl + stderr per the updated DSP-06 wording in REQUIREMENTS.md.
            elapsed = time.monotonic() - t0
            err = f"{type(exc).__name__}: {exc}"
            print(f"ERROR: {provider_name}/{company_slug}: {err}", file=sys.stderr)
            return FetchOutcome(
                company_slug=company_slug,
                provider=provider_name,
                outcome=RunOutcome.ERROR,
                error=err,
                elapsed_seconds=elapsed,
            )
    ```

    The public entry point — DSP-03 + DSP-04 + DSP-08 land here:
    ```python
    def fetch_all(
        targets: List[Tuple[str, str]],
        config_path: str,
        client: Optional["httpx.Client"] = None,
        max_workers: int = DEFAULT_MAX_WORKERS,
    ) -> List[FetchOutcome]:
        """Concurrently fetch ATS listings for a list of (company_slug, provider_name) pairs.

        DSP-03: ONE shared httpx.Client. If the caller does not supply one, we
                instantiate it here and close it in `finally`. The Client is
                thread-safe (research/STACK.md HIGH confidence).
        DSP-04: ThreadPoolExecutor(max_workers=N) + per-provider semaphores
                from config.json. Semaphores are module-level so that
                near-simultaneous fetch_all() calls in the same process share
                the cap (matters for /scout-detect + /scout-run sharing this
                module in Phase 3+).
        DSP-08: When ats.concurrency_disabled is true in config.json, falls
                back to sequential per-task execution (no executor, no
                semaphores acquired beyond a Semaphore(1)). Same FetchOutcome
                shape returned. Same code path otherwise.

        The caller persists outcomes via runs_log.append_run (Plan 02-03 wires
        this into /scout-run; this module returns outcomes only).
        """
        caps, kill_switch = load_caps_and_kill_switch(config_path)
        if kill_switch:
            # Sequential fallback. Each provider gets a Semaphore(1) to keep
            # _gate() honest; the executor is replaced by a plain loop.
            _init_semaphores({p: 1 for p in caps})
            owned_client = client is None
            client = client or httpx.Client(
                timeout=DEFAULT_TIMEOUT,
                headers={"User-Agent": DEFAULT_USER_AGENT},
                follow_redirects=True,
            )
            try:
                return [_execute_one(slug, provider, client) for slug, provider in targets]
            finally:
                if owned_client:
                    client.close()

        _init_semaphores(caps)
        owned_client = client is None
        client = client or httpx.Client(
            timeout=DEFAULT_TIMEOUT,
            headers={"User-Agent": DEFAULT_USER_AGENT},
            limits=httpx.Limits(max_connections=max_workers, max_keepalive_connections=max_workers),
            follow_redirects=True,
        )
        try:
            outcomes: List[FetchOutcome] = []
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = [pool.submit(_execute_one, slug, provider, client) for slug, provider in targets]
                for fut in futures:
                    # _execute_one already catches all exceptions and returns
                    # FetchOutcome — Future.result() should never raise here.
                    # The .result() call IS DSP-06's defense against swallowed
                    # exceptions: if _execute_one ever does raise (it shouldn't),
                    # we surface it loudly.
                    outcomes.append(fut.result())
            return outcomes
        finally:
            if owned_client:
                client.close()
    ```

    Aggregator helper (used by the skill code in Plan 02-03):
    ```python
    def aggregate_outcomes(outcomes: List[FetchOutcome]) -> Tuple[Dict[str, Dict[str, int]], Dict[str, Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
        """Aggregate a list of FetchOutcome into the three dicts append_run() expects.

        Returns:
            per_provider_outcomes: {"greenhouse": {"ok_with_results": N, "ok_zero": N, "error": N}}
            per_company_provider:  {"stripe|greenhouse": {"outcome": "OK_WITH_RESULTS", "listing_count": N}}
            per_provider_listings: {"greenhouse": [listing_dict, ...]}  (for field_completion)
        """
        per_provider: Dict[str, Dict[str, int]] = {}
        per_cp: Dict[str, Dict[str, Any]] = {}
        per_pl: Dict[str, List[Dict[str, Any]]] = {}
        for o in outcomes:
            counts = per_provider.setdefault(o.provider, {"ok_with_results": 0, "ok_zero": 0, "error": 0})
            if o.outcome == RunOutcome.OK_WITH_RESULTS:
                counts["ok_with_results"] += 1
            elif o.outcome == RunOutcome.OK_ZERO:
                counts["ok_zero"] += 1
            else:
                counts["error"] += 1
            per_cp[f"{o.company_slug}|{o.provider}"] = {
                "outcome": o.outcome.value,
                "listing_count": len(o.listings),
                "http_status": o.http_status,
                "elapsed_seconds": round(o.elapsed_seconds, 3),
            }
            if o.listings:
                per_pl.setdefault(o.provider, []).extend(L.to_dict() for L in o.listings)
        return per_provider, per_cp, per_pl
    ```

    Add a thin CLI for direct invocation matching state.py / tracker_utils.py shape:
    ```python
    if __name__ == "__main__":
        # Smoke test entry point — useful for Plan 02-02 + Plan 02-03 integration.
        # Skill code does not call this CLI; it imports fetch_all directly.
        if len(sys.argv) < 4:
            print("Usage: python3 scripts/ats/dispatcher.py fetch-all <config.json> <targets.json>", file=sys.stderr)
            print("  targets.json: [{\"company_slug\": \"stripe\", \"provider\": \"greenhouse\"}, ...]", file=sys.stderr)
            sys.exit(1)
        if sys.argv[1] != "fetch-all":
            print(f"ERROR: unknown command {sys.argv[1]!r}", file=sys.stderr)
            sys.exit(1)
        config_path = os.path.expanduser(sys.argv[2])
        targets_path = os.path.expanduser(sys.argv[3])
        with open(targets_path, "r", encoding="utf-8") as f:
            targets_in = json.load(f)
        targets = [(t["company_slug"], t["provider"]) for t in targets_in]
        outcomes = fetch_all(targets, config_path)
        per_provider, per_cp, per_pl = aggregate_outcomes(outcomes)
        print(json.dumps({
            "outcome_count": len(outcomes),
            "per_provider_outcomes": per_provider,
            "per_company_provider": per_cp,
        }, indent=2))
        sys.exit(0)
    ```

    DO NOT add any provider-specific code (no `if provider == "greenhouse"` branches). The dispatcher iterates the registry; provider variation lives in scripts/ats/providers/<name>.py.
  </action>
  <verify>
    <automated>
test -f scripts/ats/dispatcher.py && \
grep -q "import httpx" scripts/ats/dispatcher.py && \
grep -q "from concurrent.futures import ThreadPoolExecutor" scripts/ats/dispatcher.py && \
grep -q "import threading" scripts/ats/dispatcher.py && \
grep -q "DEFAULT_PROVIDER_CAPS" scripts/ats/dispatcher.py && \
grep -q "greenhouse.*10" scripts/ats/dispatcher.py && \
grep -q "ashby.*8" scripts/ats/dispatcher.py && \
grep -q "lever.*5" scripts/ats/dispatcher.py && \
grep -q "workday.*3" scripts/ats/dispatcher.py && \
grep -q "httpx.Timeout(connect=5" scripts/ats/dispatcher.py && \
grep -q "ThreadPoolExecutor(max_workers=20)" scripts/ats/dispatcher.py && \
grep -q "threading.Semaphore" scripts/ats/dispatcher.py && \
grep -q "OK_WITH_RESULTS" scripts/ats/dispatcher.py && \
grep -q "OK_ZERO" scripts/ats/dispatcher.py && \
grep -E "RunOutcome\.ERROR" scripts/ats/dispatcher.py >/dev/null && \
grep -q "def fetch_all" scripts/ats/dispatcher.py && \
grep -q "def load_caps_and_kill_switch" scripts/ats/dispatcher.py && \
grep -q "def aggregate_outcomes" scripts/ats/dispatcher.py && \
grep -q "concurrency_disabled" scripts/ats/dispatcher.py && \
grep -q "client.close()" scripts/ats/dispatcher.py && \
grep -q "finally:" scripts/ats/dispatcher.py && \
~/.job-scout-venv/bin/python3 -c "
import sys, os, tempfile, json, threading
sys.path.insert(0, 'scripts')
# Verify import surface
from ats.dispatcher import (
    fetch_all, aggregate_outcomes, load_caps_and_kill_switch,
    DEFAULT_PROVIDER_CAPS, FetchOutcome, _init_semaphores, _SEMAPHORES,
)
from ats.runs_log import RunOutcome
# DSP-04: caps match locked decision
assert DEFAULT_PROVIDER_CAPS == {'greenhouse': 10, 'ashby': 8, 'lever': 5, 'smartrecruiters': 5, 'workday': 3}, DEFAULT_PROVIDER_CAPS
# DSP-08: kill-switch reads config.json
with tempfile.TemporaryDirectory() as td:
    cfg = os.path.join(td, 'config.json')
    with open(cfg, 'w') as f:
        json.dump({'ats': {'concurrency_disabled': True, 'provider_concurrency_caps': {'greenhouse': 99}}}, f)
    caps, kill = load_caps_and_kill_switch(cfg)
    assert kill is True, 'kill-switch true must propagate'
    assert caps['greenhouse'] == 99, 'config.json overrides defaults'
    assert caps['lever'] == 5, 'unspecified providers fall through to defaults'
    cfg2 = os.path.join(td, 'config2.json')
    with open(cfg2, 'w') as f:
        json.dump({}, f)
    caps2, kill2 = load_caps_and_kill_switch(cfg2)
    assert kill2 is False, 'kill-switch defaults to False'
    assert caps2 == DEFAULT_PROVIDER_CAPS, 'empty config falls back to defaults'
# Semaphore initialization
_init_semaphores({'greenhouse': 10, 'lever': 5})
assert 'greenhouse' in _SEMAPHORES
assert isinstance(_SEMAPHORES['greenhouse'], type(threading.Semaphore())), '_SEMAPHORES holds Semaphore objects'
# Aggregate empty outcomes
per_p, per_cp, per_pl = aggregate_outcomes([])
assert per_p == {} and per_cp == {} and per_pl == {}
# fetch_all with empty targets returns empty list (and doesn't crash on missing config)
with tempfile.TemporaryDirectory() as td:
    cfg = os.path.join(td, 'config.json')
    with open(cfg, 'w') as f:
        json.dump({'ats': {}}, f)
    out = fetch_all([], cfg)
    assert out == [], f'empty targets must return [], got {out}'
print('Task 3 OK')
"
    </automated>
  </verify>
  <done>
    dispatcher.py exists with all 5 DSP requirements baked in: shared httpx.Client (DSP-03), ThreadPoolExecutor + per-provider Semaphore (DSP-04), 3-state Outcome enum (DSP-05), exception-surfacing wrapper (DSP-06), config.json kill-switch (DSP-08). Empty-targets call returns []. Caps default + override behavior verified. Commit: `feat(02-01): add dispatcher with shared httpx.Client + per-provider semaphores + 3-state outcomes + kill-switch (DSP-03, DSP-04, DSP-05, DSP-06, DSP-08)`.
  </done>
</task>

<task type="auto">
  <name>Task 4: Semaphore stress test — verify per-provider cap is enforced under 30 concurrent calls (SC-5)</name>
  <files></files>
  <read_first>
    Read ONCE:
    1. scripts/ats/dispatcher.py (just created in Task 3) — for the public surface (`fetch_all`, `_init_semaphores`, `_SEMAPHORES`, `FetchOutcome`).
    2. scripts/ats/providers/base.py (Task 1) — for `FetchResult` shape (the stub provider returns one).

    No other reads needed. This task does NOT add a new source file; it adds an inline-Python verify that exercises the semaphore contract.
  </read_first>
  <action>
    No source file changes. This task is a SC-5 acceptance test embedded in the verify block — it stress-tests the per-provider semaphore cap by registering a synthetic provider that records peak concurrency, then submitting 30 fetches against a cap of 10.

    The test is purely an `~/.job-scout-venv/bin/python3 -c "..."` invocation in the verify block — it does NOT add a `tests/` file (per CLAUDE.md anti-feature: no general test suite). The synthetic provider lives entirely inside the inline-Python string and is registered into `PROVIDERS` for the duration of the test, then unregistered.

    The contract being tested:

    - `fetch_all` with a target list of 30 (slug, "stub") pairs and a per-provider cap of 10 must NEVER allow more than 10 stub.fetch() calls to be in their critical section simultaneously.
    - This proves DSP-04's "ThreadPoolExecutor(max_workers=20) + per-provider Semaphore" actually bounds load — not just claims to.
    - It also proves the executor pool's max_workers (20) is NOT the binding cap when the per-provider semaphore is tighter (10).

    The synthetic provider:
    - increments a module-level counter inside the semaphore-protected critical section;
    - tracks peak observed value via `max()` under a `threading.Lock`;
    - holds the semaphore for ~50ms (`time.sleep(0.05)`) so calls actually overlap;
    - decrements the counter on exit.

    After fetch_all returns, the test asserts `peak <= 10`. If the assertion fails, the cap is not being enforced and DSP-04 is broken.

    Use the verify block below verbatim — it's the SC-5 acceptance gate.
  </action>
  <verify>
    <automated>
~/.job-scout-venv/bin/python3 -c "
import sys, threading, time
sys.path.insert(0, 'scripts')
from ats import PROVIDERS
from ats.providers.base import FetchResult
from ats.dispatcher import fetch_all

# Synthetic provider — module-level surface so duck-typed Protocol conformance holds.
class _StubProvider:
    NAME = 'stub'
    BOARD_URL_PATTERNS = []
    _counter = 0
    _peak = 0
    _lock = threading.Lock()
    @classmethod
    def detect(cls, slug, name, client):
        raise NotImplementedError
    @classmethod
    def board_url_from_url(cls, url):
        return None
    @classmethod
    def fetch(cls, slug, client, semaphore):
        # Critical section is INSIDE the dispatcher's _gate context manager,
        # which has already acquired the per-provider semaphore by the time
        # this is called. We just record peak observed concurrency.
        with cls._lock:
            cls._counter += 1
            cls._peak = max(cls._peak, cls._counter)
        time.sleep(0.05)  # hold long enough that 30 calls overlap with cap=10
        with cls._lock:
            cls._counter -= 1
        return FetchResult(provider='stub', company_slug=slug, listings=[], raw=[], http_status=200)
    @classmethod
    def to_listing(cls, payload):
        raise NotImplementedError

# Register the stub into PROVIDERS for the duration of the test.
PROVIDERS['stub'] = _StubProvider

# Build a config.json with cap=10 for the stub provider.
import tempfile, os, json
with tempfile.TemporaryDirectory() as td:
    cfg = os.path.join(td, 'config.json')
    json.dump({'ats': {'provider_concurrency_caps': {'stub': 10}}}, open(cfg, 'w'))

    # 30 stub targets, cap=10 → peak must be <= 10.
    targets = [(f'company-{i:02d}', 'stub') for i in range(30)]
    outcomes = fetch_all(targets, cfg)

# Sanity: all 30 outcomes returned (proving the executor finished them all).
assert len(outcomes) == 30, f'expected 30 outcomes, got {len(outcomes)}'

# The contract: per-provider cap of 10 is enforced.
assert _StubProvider._peak <= 10, f'SC-5 FAIL: peak concurrent stub.fetch was {_StubProvider._peak}, cap was 10'

# Sanity: peak should also be > 1 — if it's 1, we accidentally serialized
# everything and the cap test is vacuous (it would pass trivially even on a
# broken dispatcher).
assert _StubProvider._peak > 1, f'SC-5 FAIL: peak concurrency was {_StubProvider._peak}; expected concurrent execution (> 1) — semaphore is over-restricting or executor is broken'

# Cleanup.
del PROVIDERS['stub']
print(f'Task 4 OK: semaphore enforces cap=10 against 30 concurrent calls (peak observed: {_StubProvider._peak})')
"
    </automated>
  </verify>
  <done>
    Inline-Python stress test passes: 30 (slug, 'stub') targets dispatched against cap=10 produces a peak observed concurrency between 2 and 10 (inclusive). DSP-04 semaphore enforcement verified by direct observation, not just inspection. Failure modes caught:
      - peak > 10 → semaphore is not bounding correctly (regression in `_gate` or `_init_semaphores`)
      - peak == 1 → all calls serialized; either pool size is 1 or semaphore acquired before submit (regression in `fetch_all`'s ThreadPoolExecutor wiring)
    NO commit (no source files changed; this is a SC-5 acceptance gate).
  </done>
</task>

</tasks>

<threat_model>

## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| dispatcher → external ATS API | HTTPS GET/POST to public unauthenticated endpoints. Untrusted response bodies cross this boundary. |
| dispatcher → runs.jsonl | Local file write inside `<data_dir>/runs.jsonl`. Trusted (same uid). |
| user config.json → dispatcher | User-edited JSON read at fetch_all() entry. Caps/kill-switch flag-loading parses untrusted ints/booleans. |
| Listing.__post_init__ → caller | Validation boundary. Required-field check raises ValueError into worker; worker buckets as ERROR. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-01 | Tampering | dispatcher response parsing | mitigate | Listing.__post_init__ raises ValueError on missing required fields — provider mappers (Plan 02-02 Greenhouse) cannot silently emit empty-record garbage from a tampered/drifted response. |
| T-02-02 | Information Disclosure | runs.jsonl PII leak | mitigate | runs_log.append_run() writes structured fields only (counts, timings, slugs, provider names). Never writes raw response bodies, never writes resume_path or candidate_profile contents. Pitfall research already documents this rule; runs_log.py's docstring restates it. |
| T-02-03 | Denial of Service | Provider abuse via runaway concurrency | mitigate | Per-provider Semaphore enforces caps from research/STACK.md (HIGH confidence). Even with Phase 4's 5 providers, no single provider sees more than its cap of in-flight requests. |
| T-02-04 | Denial of Service | httpx hang on unresponsive provider | mitigate | `httpx.Timeout(connect=5, read=15)` on every request. A single slow Workday tenant cannot blow the 5-min wall-clock budget — it ERRORs at 15s and the dispatcher proceeds. |
| T-02-05 | Elevation of Privilege | Worker-thread tracker xlsx write | mitigate | dispatcher.py NEVER calls tracker_utils. Outcomes return to the main thread; the skill (Plan 02-03 + later phases) calls tracker_utils.append serially. PITFALLS Pitfall 5 mitigation. |
| T-02-06 | Spoofing | Untrusted apply_url in Listing.url | accept | DSP-09 / OUT-01 design accepts that ATS-returned apply URLs may redirect. Hostname-allowlist validation deferred to v0.5+ (per PITFALLS Security Mistakes table — risk is "user clicks Apply from report and lands on phishing"; v0.4 OOS lists this as deferred to v0.5+). |
| T-02-07 | Repudiation | Silent provider regression (Pitfall 1) | mitigate | DSP-05's three-state OK_ZERO vs ERROR distinguishability + DSP-07's per-(company, provider) hit history make every regression auditable from runs.jsonl. Phase 5 surfaces this in the report's Honest notes. |
| T-02-08 | Tampering | config.json malformed by user | mitigate | load_caps_and_kill_switch() catches JSONDecodeError + OSError, prints WARNING, falls back to DEFAULT_PROVIDER_CAPS. A corrupt config can't crash the run; a too-aggressive cap can't be set silently below positive integers (validation `isinstance(v, int) and v > 0`). |

</threat_model>

<verification>
After all 3 tasks complete, run this phase-level check:

```bash
# Files exist
test -f scripts/ats/__init__.py && \
test -f scripts/ats/providers/__init__.py && \
test -f scripts/ats/providers/base.py && \
test -f scripts/ats/normalize.py && \
test -f scripts/ats/runs_log.py && \
test -f scripts/ats/dispatcher.py && \
echo "PLAN-LEVEL: 6 files OK"

# Frontmatter requirements check (DSP-01..08, no DSP-09/10)
grep -lE "DSP-(01|02|03|04|05|06|07|08)" .planning/phases/02-provider-protocol-greenhouse-dispatcher-observability/02-01-dispatcher-PLAN.md && \
echo "PLAN-LEVEL: requirements OK"

# Cross-cutting integration smoke (Plans 02-02 will exercise this against real Greenhouse fixture)
~/.job-scout-venv/bin/python3 -c "
import sys; sys.path.insert(0, 'scripts')
from ats import PROVIDERS
from ats.dispatcher import fetch_all, aggregate_outcomes, DEFAULT_PROVIDER_CAPS
from ats.runs_log import append_run, RunOutcome, compute_field_completion
from ats.normalize import Listing, REQUIRED_FIELDS
from ats.providers.base import Provider, DetectionResult, FetchResult
# Empty integration: dispatcher accepts empty targets, runs_log appends one line
import tempfile, os, json
with tempfile.TemporaryDirectory() as td:
    cfg = os.path.join(td, 'config.json')
    with open(cfg, 'w') as f: json.dump({'ats': {}}, f)
    runs_log = os.path.join(td, 'runs.jsonl')
    open(runs_log, 'w').close()
    outcomes = fetch_all([], cfg)
    per_p, per_cp, per_pl = aggregate_outcomes(outcomes)
    line = append_run(runs_log, 0.0, per_p, per_cp, per_pl)
    with open(runs_log) as f:
        n = sum(1 for L in f if L.strip())
    assert n == 1, f'expected 1 line, got {n}'
print('PLAN-LEVEL: end-to-end empty roundtrip OK')
"
```

All three lines must print. Failure on any line means the substrate is broken — must fix before Plan 02-02 can build greenhouse.py against it.
</verification>

<success_criteria>
- [ ] All 6 files exist under scripts/ats/
- [ ] Provider Protocol is a typing.Protocol (Python 3.8 compat); 5-method shape; runtime_checkable; no inheritance
- [ ] Listing dataclass is `frozen=True`; raises ValueError in __post_init__ on missing required field; REQUIRED_FIELDS tuple matches DSP-02 lock (company, title, location, url, posted_date, source)
- [ ] runs_log.py opens runs.jsonl in 'a' mode + flushes; never reads or rewrites; per-line schema includes timestamp, wall_clock_seconds, providers (with field_completion), per_company_provider
- [ ] dispatcher.py uses ONE shared httpx.Client (closed in `finally`); httpx.Timeout(connect=5, read=15); ThreadPoolExecutor(max_workers=20); module-level _SEMAPHORES dict initialized from config.json caps; defaults match {greenhouse: 10, ashby: 8, lever: 5, smartrecruiters: 5, workday: 3}
- [ ] DSP-05 enum (RunOutcome) shared between dispatcher.py and runs_log.py — single source of truth, exported from runs_log.py and imported by dispatcher.py
- [ ] DSP-06 worker wrapper catches all exceptions and buckets as ERROR with the (provider, company) context surfaced to stderr
- [ ] DSP-08 kill-switch (`ats.concurrency_disabled: true` in config.json) makes fetch_all sequential; same FetchOutcome shape returned
- [ ] Sibling-script bootstrap correctness: scripts/ats/*.py uses 2-level dirname; scripts/ats/providers/*.py uses 3-level dirname; pattern documented in scripts/ats/__init__.py docstring
- [ ] No CON-04 violation: every ImportError in this plan recommends pipx/venv (not --break-system-packages); httpx is the only third-party import added; rapidfuzz NOT imported in this plan
- [ ] Phase-level smoke (verification block above) prints all three OK lines
- [ ] PROVIDERS dict is empty in this plan (Plan 02-02 lands greenhouse)
</success_criteria>

<output>
After completion, create `.planning/phases/02-provider-protocol-greenhouse-dispatcher-observability/02-01-dispatcher-SUMMARY.md` with:
- 1-line summary
- Files modified table (path | change | commit)
- Tasks completed checklist
- Verify results (the three OK lines from `<verification>`)
- Decisions logged (DSP-01..08 reqs and how each landed)
- Any deviations from PLAN (e.g. naming choices not pinned in PLAN)
- Hand-off to Plan 02-02: PROVIDERS registry is empty; greenhouse.py imports `from ats.providers.base import Provider, FetchResult, DetectionResult` and `from ats.normalize import Listing` — contracts already published; no scavenger hunt needed.
</output>
