from contextlib import closing

from fastapi.testclient import TestClient

from backend import db
from backend.main import app


def count(table: str) -> int:
    with closing(db.connect()) as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608


def test_seed(client):
    assert count("claims") == 25
    assert count("policies") == 50
    assert count("customers") == 49
    assert count("handlers") == 3
    assert count("plans") == 3


def test_seed_holds_only_the_queue(client):
    ids = [c["claim_id"] for c in client.get("/api/claims").json()]
    assert ids == [c["claim_id"] for c in db.load("claims.json")]


def test_init_keeps_an_existing_database(client):
    with closing(db.connect()) as conn, conn:
        conn.execute("UPDATE claims SET status = 'decided'")
    db.init()
    assert client.get("/api/claims/CLM-1001").json()["status"] == "decided"
    db.reset()
    assert client.get("/api/claims/CLM-1001").json()["status"] == "waiting"


def test_startup_creates_the_database(tmp_path, monkeypatch):
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "new.db"))
    with TestClient(app) as client:
        assert len(client.get("/api/claims").json()) == 25


def test_list_claims(client):
    claims = client.get("/api/claims").json()
    assert len(claims) == 25
    assert {c["status"] for c in claims} == {"waiting"}
    assert claims[0] == {
        "claim_id": "CLM-1001",
        "customer_name": "Maya Patel",
        "claim_type": "trip_delay",
        "summary": "Flight home canceled by the airline, rebooked the next morning",
        "amount_claimed": 420.0,
        "submitted_on": "2026-06-24",
        "status": "waiting",
    }


def test_get_claim(client):
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["customer_name"] == "Maya Patel"
    assert claim["policy_id"] == "POL-2001"
    assert claim["story"].startswith("My flight home from Rome")
    assert len(claim["items"]) == 3
    assert len(claim["documents"]) == 4


def test_get_claim_unknown(client):
    response = client.get("/api/claims/CLM-9999")
    assert response.status_code == 404
    assert response.json() == {"detail": "No claim CLM-9999"}


def test_get_policy(client):
    policy = client.get("/api/policies/POL-2001").json()
    assert policy["plan"]["name"] == "UnderCover Premium"
    assert policy["plan"]["deductible"] == 50.0
    assert policy["plan"]["per_item_limit"] == 300.0
    assert policy["trip"]["returns_on"] == "2026-06-18"
    assert policy["travelers"] == ["Maya Patel"]


def test_get_policy_unknown(client):
    response = client.get("/api/policies/POL-9999")
    assert response.status_code == 404
    assert response.json() == {"detail": "No policy POL-9999"}


def test_get_claim_history(client):
    history = client.get("/api/customers/CUS-3001/claims").json()
    assert [c["claim_id"] for c in history] == ["CLM-0412"]
    assert "email" not in history[0]


def test_get_claim_history_unknown(client):
    assert client.get("/api/customers/CUS-9999/claims").status_code == 404


def test_list_handlers(client):
    handlers = client.get("/api/handlers").json()
    assert [h["name"] for h in handlers] == [
        "Dana Whitfield",
        "Marcus Oyelaran",
        "Priya Raman",
    ]


def test_get_policy_wording(client):
    text = client.get("/api/policy-wording").json()["text"]
    assert text == (db.DATA / "policy_wording.md").read_text(encoding="utf-8")
