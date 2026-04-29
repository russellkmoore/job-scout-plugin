"""conftest.py — Shared pytest fixtures for the job-scout-plugin test suite.

Bootstrap: scripts/ on sys.path so test modules can `from ats.* import ...`
using the same pattern as scripts/ats/dispatcher.py (2-level sibling-script).

Run hint:
  ~/.job-scout-venv/bin/python3 -m pytest tests/ --tb=short -q
"""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture
def mock_greenhouse_ok():
    """httpx.Client mock returning the airbnb fixture (200 + jobs).

    Use when a test needs greenhouse.detect() to return BORDERLINE
    (200 + >=1 jobs) without a live network call.
    """
    fixture_path = PROJECT_ROOT / "tests" / "fixtures" / "ats" / "greenhouse" / "airbnb.json"
    payload = json.loads(fixture_path.read_text())
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = payload
    client = MagicMock()
    client.get.return_value = mock_resp
    return client


@pytest.fixture
def mock_greenhouse_404():
    """httpx.Client mock returning 404 — used for NOT_FOUND assertions."""
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.json.side_effect = ValueError("404 has no JSON body")
    client = MagicMock()
    client.get.return_value = mock_resp
    return client


@pytest.fixture
def mock_greenhouse_zero_jobs():
    """httpx.Client mock returning 200 + 0 jobs — for D-02 empty-board case."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"jobs": []}
    client = MagicMock()
    client.get.return_value = mock_resp
    return client
