"""Test setup: a throwaway SQLite database and template mode, so tests never call a real LLM."""

import os
import tempfile
from pathlib import Path

# Set before the app is imported: real environment variables win over backend/.env.
_TMP = Path(tempfile.mkdtemp(prefix="leadops-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["LLM_PROVIDER"] = "none"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:  # runs startup, which creates the tables
        yield test_client
