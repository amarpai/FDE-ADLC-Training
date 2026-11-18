import pytest
from fastapi.testclient import TestClient

from backend import db
from backend.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A client for the backend on a freshly seeded database of its own."""
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "undercover.db"))
    db.init()
    return TestClient(app)
