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
    python3 scripts/state.py resolve        # prints resolved data_dir from state.json (exits 2 if not configured)
"""

import json
import os
import sys
from datetime import datetime

STATE_DIR = os.path.expanduser("~/.job-scout")
STATE_PATH = os.path.join(STATE_DIR, "state.json")


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


# v0.4 (CON-05): Legacy fallback chain removed. file-contract.md mandates
# "no fallbacks." If state.json is missing, /scout-setup is responsible for
# detecting any pre-existing data dir and prompting the user. resolve_data_dir
# below now returns "" when state.json is missing — caller MUST run /scout-setup.


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
