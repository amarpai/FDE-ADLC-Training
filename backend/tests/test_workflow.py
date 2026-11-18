import json
from contextlib import closing

import pytest

from backend import db

REASONS = "The delay was caused by a crew problem. Section 3 covers the costs."


def start(client, claim_id="CLM-1001"):
    return client.post(f"/api/claims/{claim_id}/start")


def decide(client, outcome, payout, claim_id="CLM-1001"):
    return client.post(
        f"/api/claims/{claim_id}/decision",
        json={
            "outcome": outcome,
            "payout": payout,
            "reasons": REASONS,
            "policy_section": "Section 3, Trip Delay",
        },
    )


def pay(client, amount, claim_id="CLM-1001"):
    return client.post(f"/api/claims/{claim_id}/payment", json={"amount": amount})


def sign_off(client, handler_id="HND-01", claim_id="CLM-1001"):
    return client.post(
        f"/api/claims/{claim_id}/sign-off", json={"handler_id": handler_id}
    )


def add_step(client, kind, content, claim_id="CLM-1001"):
    return client.post(
        f"/api/claims/{claim_id}/steps", json={"kind": kind, "content": content}
    )


def test_start_claim(client):
    response = start(client)
    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"


def test_start_again_clears_the_earlier_steps(client):
    start(client)
    add_step(client, "message", "First run")
    assert start(client).json()["status"] == "in_progress"
    assert client.get("/api/claims/CLM-1001/steps").json() == []


def test_start_a_decided_claim(client):
    start(client)
    decide(client, "decline", 0)
    response = start(client)
    assert response.status_code == 409
    assert response.json() == {"detail": "Claim CLM-1001 already has a decision"}


def test_start_an_unknown_claim(client):
    assert start(client, "CLM-9999").status_code == 404


def test_steps(client):
    start(client)
    add_step(client, "tool_call", "get_claim(claim_id='CLM-1001')")
    add_step(client, "tool_result", '{"claim_id": "CLM-1001"}')
    decide(client, "decline", 0)
    add_step(client, "message", "Declined.")
    steps = client.get("/api/claims/CLM-1001/steps").json()
    assert [s["kind"] for s in steps] == ["tool_call", "tool_result", "message"]
    assert steps[2]["content"] == "Declined."
    assert steps[0]["step_id"] < steps[1]["step_id"] < steps[2]["step_id"]


def test_step_of_an_unknown_kind(client):
    assert add_step(client, "thought", "Hmm").status_code == 422


def test_steps_of_an_unknown_claim(client):
    assert add_step(client, "message", "Hi", "CLM-9999").status_code == 404
    assert client.get("/api/claims/CLM-9999/steps").status_code == 404


def test_decide_a_waiting_claim(client):
    response = decide(client, "decline", 0)
    assert response.status_code == 409
    assert response.json() == {"detail": "Claim CLM-1001 is not in progress"}


def test_decide_twice(client):
    start(client)
    decide(client, "decline", 0)
    assert decide(client, "approve", 420).status_code == 409


@pytest.mark.parametrize("outcome", ["decline", "refer"])
def test_decline_or_refer(client, outcome):
    start(client)
    claim = decide(client, outcome, 0).json()
    assert claim["status"] == "decided"
    assert claim["decision"]["outcome"] == outcome
    assert claim["decision"]["reasons"] == REASONS
    assert claim["decision"]["policy_section"] == "Section 3, Trip Delay"
    assert claim["decision"]["signed_off_by"] is None
    assert claim["payment"] is None


@pytest.mark.parametrize(
    ("outcome", "payout"),
    [("approve", 0), ("decline", 50), ("refer", 50), ("approve", -5), ("pay", 0)],
)
def test_decision_with_a_bad_payout_or_outcome(client, outcome, payout):
    start(client)
    assert decide(client, outcome, payout).status_code == 422


def test_decision_without_reasons(client):
    start(client)
    response = client.post(
        "/api/claims/CLM-1001/decision",
        json={"outcome": "decline", "payout": 0, "reasons": "", "policy_section": ""},
    )
    assert response.status_code == 422


def test_approve_and_pay(client):
    start(client)
    assert decide(client, "approve", 420).json()["status"] == "decided"
    claim = pay(client, 420).json()
    assert claim["payment"]["amount"] == 420
    assert claim["status"] == "decided"
    listed = client.get("/api/claims").json()[0]
    assert listed["decision"]["payout"] == 420
    assert listed["payment"]["amount"] == 420


def test_pay_a_declined_claim(client):
    start(client)
    decide(client, "decline", 0)
    response = pay(client, 420)
    assert response.status_code == 409
    assert response.json() == {"detail": "Claim CLM-1001 is not approved"}


def test_pay_a_claim_with_no_decision(client):
    assert pay(client, 420).status_code == 409


def test_pay_the_wrong_amount(client):
    start(client)
    decide(client, "approve", 420)
    response = pay(client, 500)
    assert response.status_code == 409
    assert response.json() == {"detail": "The approved payout is $420.00"}


def test_pay_twice(client):
    start(client)
    decide(client, "approve", 420)
    pay(client, 420)
    response = pay(client, 420)
    assert response.status_code == 409
    assert response.json() == {"detail": "Claim CLM-1001 is already paid"}


def test_pay_an_unknown_claim(client):
    assert pay(client, 420, "CLM-9999").status_code == 404


def test_a_payout_over_the_limit_waits_for_sign_off(client):
    start(client)
    assert decide(client, "approve", 1250).json()["status"] == "waiting_for_sign_off"

    response = pay(client, 1250)
    assert response.status_code == 409
    assert response.json() == {
        "detail": "A payout over $1,000.00 needs a handler's sign-off first"
    }
    assert client.get("/api/claims/CLM-1001").json()["payment"] is None

    claim = sign_off(client).json()
    assert claim["status"] == "decided"
    assert claim["decision"]["signed_off_by"] == "HND-01"
    assert claim["payment"]["amount"] == 1250
    assert pay(client, 1250).json() == {"detail": "Claim CLM-1001 is already paid"}


@pytest.mark.parametrize(
    ("payout", "status"),
    [(1000.00, "decided"), (1000.01, "waiting_for_sign_off")],
)
def test_the_limit_is_for_payouts_over_1000(client, payout, status):
    start(client)
    assert decide(client, "approve", payout).json()["status"] == status


def test_a_payout_of_1000_pays_straight_away(client):
    start(client)
    decide(client, "approve", 1000)
    assert pay(client, 1000).status_code == 200


def test_sign_off_a_claim_that_does_not_need_it(client):
    start(client)
    decide(client, "approve", 420)
    response = sign_off(client)
    assert response.status_code == 409
    assert response.json() == {"detail": "Claim CLM-1001 is not waiting for sign-off"}


def test_sign_off_by_an_unknown_handler(client):
    start(client)
    decide(client, "approve", 1250)
    assert sign_off(client, "HND-99").status_code == 404
    assert client.get("/api/claims/CLM-1001").json()["status"] == "waiting_for_sign_off"


def test_sign_off_by_a_handler_without_the_authority(client):
    with closing(db.connect()) as conn, conn:
        handler = json.loads(
            conn.execute(
                "SELECT record FROM handlers WHERE handler_id = 'HND-03'"
            ).fetchone()[0]
        )
        handler["can_approve_over_limit"] = False
        conn.execute(
            "UPDATE handlers SET record = ? WHERE handler_id = 'HND-03'",
            [json.dumps(handler)],
        )
    start(client)
    decide(client, "approve", 1250)
    response = sign_off(client, "HND-03")
    assert response.status_code == 403
    assert response.json() == {"detail": "Priya Raman can't sign off this payout"}
