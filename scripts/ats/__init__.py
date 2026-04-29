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
