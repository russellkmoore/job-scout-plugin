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

# Provider registry. Populated at package import time.
# The dispatcher and detector iterate PROVIDERS.items() and never name a
# specific provider — adding Jobvite/Taleo in v0.5+ is one new file +
# one registry entry here.
#
# Phase 2 ships only "greenhouse" (DSP-09). Phase 4 adds "lever", "ashby",
# "smartrecruiters", "workday" (PRV-01..04). Each provider's module
# exports the Protocol-required surface as MODULE-LEVEL functions/attrs
# (NAME, BOARD_URL_PATTERNS, detect, board_url_from_url, fetch, to_listing).
# We register the MODULE itself, not an instance — runtime_checkable
# Protocol with duck-typed module conformance.
# Provider modules registered as MODULES (not instances) — duck-typed
# Protocol conformance per DSP-01. Detection order matters (Phase 3
# detect.py iterates and stops at first CONFIRMED): greenhouse first
# because it covers the most companies; jsonld last because D-3's
# empty-BOARD_URL_PATTERNS guard skips it during detection.
from .providers import greenhouse as _greenhouse_module  # noqa: E402
from .providers import lever as _lever_module  # noqa: E402
from .providers import ashby as _ashby_module  # noqa: E402
from .providers import smartrecruiters as _smartrecruiters_module  # noqa: E402
from .providers import workday as _workday_module  # noqa: E402
from .providers import jsonld as _jsonld_module  # noqa: E402

PROVIDERS: Dict[str, "Provider"] = {
    _greenhouse_module.NAME: _greenhouse_module,
    _lever_module.NAME: _lever_module,
    _ashby_module.NAME: _ashby_module,
    _smartrecruiters_module.NAME: _smartrecruiters_module,
    _workday_module.NAME: _workday_module,
    _jsonld_module.NAME: _jsonld_module,
}
