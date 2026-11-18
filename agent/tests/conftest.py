import pytest
from fastapi.testclient import TestClient

from agent import main
from backend import db
from backend.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Point the agent at the backend on a freshly seeded database of its own."""
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "undercover.db"))
    db.init()
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    return TestClient(app)
