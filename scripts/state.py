#!/usr/bin/env python3
"""
state.py — Read/write the Job Scout state pointer.

The state pointer lives at ~/.job-scout/state.json and tells /scout-run
where the user's data directory is. /scout-setup writes it. /scout-run
reads it.

Without this pointer, the run command has to guess at the data directory
location, which is what caused the "files dropping in different directories"
problems.

Usage from prompt:
    python3 scripts/state.py read           # prints data_dir or empty string
    python3 scripts/state.py read-json      # prints full state json
    python3 scripts/state.py write <data_dir>
    python3 scripts/state.py resolve        # prints resolved data_dir, falling back through legacy paths
"""

import json
import os
import sys
from datetime import datetime

STATE_DIR = os.path.expanduser("~/.job-scout")
STATE_PATH = os.path.join(STATE_DIR, "state.json")

# Legacy fallback locations — checked in order if state.json is missing.
# The scout/ subdirectory pattern is preferred when the user keeps personal
# job-search materials (resumes, application folders) at the top level and
# wants scout's working data confined to a subfolder.
LEGACY_DATA_DIRS = [
    "~/Documents/JobSearch/scout",
    "~/Documents/JobSearch",
    "~/Documents/JobScout",
]


def read_state():
    """Return state dict, or empty dict if not present / unreadable."""
    if not os.path.exists(STATE_PATH):
        return {}
    try:
        with open(STATE_PATH, "r") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def write_state(data_dir, plugin_version=None):
    """Write the state pointer. Creates ~/.job-scout/ if needed."""
    os.makedirs(STATE_DIR, exist_ok=True)
    data_dir = os.path.expanduser(data_dir)
    state = {
        "data_dir": data_dir,
        "plugin_version": plugin_version or "",
        "last_setup_iso": datetime.utcnow().isoformat() + "Z",
    }
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)
    return state


def resolve_data_dir():
    """
    Return the user's data directory, in priority order:
      1. ~/.job-scout/state.json -> data_dir
      2. First legacy path that exists and contains config.json
      3. Empty string if nothing found (caller must prompt /scout-setup)
    """
    state = read_state()
    candidate = state.get("data_dir")
    if candidate:
        candidate = os.path.expanduser(candidate)
        if os.path.isdir(candidate):
            return candidate

    for legacy in LEGACY_DATA_DIRS:
        legacy_expanded = os.path.expanduser(legacy)
        if os.path.isfile(os.path.join(legacy_expanded, "config.json")):
            return legacy_expanded

    return ""


def main(argv):
    if len(argv) < 2:
        print("Usage: state.py {read|read-json|write <data_dir>|resolve}", file=sys.stderr)
        sys.exit(1)

    cmd = argv[1]

    if cmd == "read":
        print(read_state().get("data_dir", ""))
    elif cmd == "read-json":
        print(json.dumps(read_state(), indent=2))
    elif cmd == "write":
        if len(argv) < 3:
            print("Usage: state.py write <data_dir> [plugin_version]", file=sys.stderr)
            sys.exit(1)
        data_dir = argv[2]
        version = argv[3] if len(argv) > 3 else ""
        state = write_state(data_dir, version)
        print(json.dumps(state, indent=2))
    elif cmd == "resolve":
        resolved = resolve_data_dir()
        if not resolved:
            sys.exit(2)
        print(resolved)
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv)
