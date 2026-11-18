"""The UnderCover backend."""

import json
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException

from backend import db
from backend.models import (
    Claim,
    ClaimSummary,
    Decision,
    DecisionRequest,
    Handler,
    Payment,
    PaymentRequest,
    Policy,
    PreviousClaim,
    SignOffRequest,
    Status,
    Step,
    StepRequest,
    Text,
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    db.init()
    yield


app = FastAPI(title="UnderCover", lifespan=lifespan)
# "function" commits each request's changes before its response is sent.
Database = Annotated[sqlite3.Connection, Depends(db.database, scope="function")]

INSTRUCTIONS = Path(__file__).parent / "instructions.md"

CLAIMS = """
SELECT claims.status, claims.record,
    json_extract(customers.record, '$.name') AS customer_name,
    decisions.*, payments.amount, payments.paid_at
FROM claims
JOIN customers ON customers.customer_id = claims.customer_id
LEFT JOIN decisions ON decisions.claim_id = claims.claim_id
LEFT JOIN payments ON payments.claim_id = claims.claim_id
"""


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def record(conn: sqlite3.Connection, table: str, key: str, value: str) -> Any:
    """Return one record by its id, or raise a 404."""
    row = conn.execute(
        f"SELECT record FROM {table} WHERE {key} = ?",  # noqa: S608
        [value],
    ).fetchone()
    if row is None:
        raise HTTPException(404, f"No {key.removesuffix('_id')} {value}")
    return json.loads(row["record"])


def claim_fields(row: sqlite3.Row) -> dict[str, Any]:
    """Merge a claim's record with its status, customer, decision and payment."""
    fields = dict(row)
    return json.loads(row["record"]) | {
        "status": row["status"],
        "customer_name": row["customer_name"],
        "decision": Decision.model_validate(fields) if row["outcome"] else None,
        "payment": Payment.model_validate(fields) if row["paid_at"] else None,
    }


def status_of(conn: sqlite3.Connection, claim_id: str) -> Status:
    """Return where a claim stands, or raise a 404."""
    row = conn.execute(
        "SELECT status FROM claims WHERE claim_id = ?", [claim_id]
    ).fetchone()
    if row is None:
        raise HTTPException(404, f"No claim {claim_id}")
    return row["status"]


def set_status(conn: sqlite3.Connection, claim_id: str, status: Status) -> None:
    conn.execute("UPDATE claims SET status = ? WHERE claim_id = ?", [status, claim_id])


def payout_limit(conn: sqlite3.Connection) -> float:
    """The largest payout the agent can pay without a handler's sign-off."""
    return conn.execute(
        "SELECT json_extract(record, '$.payout_approval_limit') FROM company"
    ).fetchone()[0]


def pay(conn: sqlite3.Connection, claim_id: str, amount: float) -> None:
    conn.execute("INSERT INTO payments VALUES (?, ?, ?)", [claim_id, amount, now()])


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


@app.get("/api/claims", operation_id="list_claims")
def list_claims(conn: Database) -> list[ClaimSummary]:
    """List the claims queue in order, with where each claim stands."""
    rows = conn.execute(f"{CLAIMS} ORDER BY claims.claim_id").fetchall()
    return [ClaimSummary.model_validate(claim_fields(row)) for row in rows]


@app.get("/api/claims/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str, conn: Database) -> Claim:
    """Get one claim in full, with its decision and payment."""
    row = conn.execute(f"{CLAIMS} WHERE claims.claim_id = ?", [claim_id]).fetchone()
    if row is None:
        raise HTTPException(404, f"No claim {claim_id}")
    return Claim.model_validate(claim_fields(row))


@app.post("/api/claims/{claim_id}/start", operation_id="start_claim")
def start_claim(claim_id: str, conn: Database) -> Claim:
    """Start work on a waiting claim, or start an unfinished one again."""
    if status_of(conn, claim_id) not in ("waiting", "in_progress"):
        raise HTTPException(409, f"Claim {claim_id} already has a decision")
    conn.execute("DELETE FROM steps WHERE claim_id = ?", [claim_id])
    set_status(conn, claim_id, "in_progress")
    return get_claim(claim_id, conn)


@app.post("/api/claims/{claim_id}/steps", operation_id="add_step")
def add_step(claim_id: str, step: StepRequest, conn: Database) -> Step:
    """Record one step of the agent's work on a claim."""
    status_of(conn, claim_id)
    row = conn.execute(
        "INSERT INTO steps (claim_id, kind, content, created_at)"
        " VALUES (?, ?, ?, ?) RETURNING *",
        [claim_id, step.kind, step.content, now()],
    ).fetchone()
    return Step.model_validate(dict(row))


@app.get("/api/claims/{claim_id}/steps", operation_id="list_steps")
def list_steps(claim_id: str, conn: Database) -> list[Step]:
    """List the steps of the agent's work on a claim, in order."""
    status_of(conn, claim_id)
    rows = conn.execute(
        "SELECT * FROM steps WHERE claim_id = ? ORDER BY step_id", [claim_id]
    ).fetchall()
    return [Step.model_validate(dict(row)) for row in rows]


@app.post("/api/claims/{claim_id}/decision", operation_id="record_decision")
def record_decision(claim_id: str, decision: DecisionRequest, conn: Database) -> Claim:
    """Record the decision on a claim in progress: approve, decline or refer."""
    if status_of(conn, claim_id) != "in_progress":
        raise HTTPException(409, f"Claim {claim_id} is not in progress")
    conn.execute(
        "INSERT INTO decisions (claim_id, outcome, payout, reasons, policy_section,"
        " decided_at) VALUES (?, ?, ?, ?, ?, ?)",
        [
            claim_id,
            decision.outcome,
            decision.payout,
            decision.reasons,
            decision.policy_section,
            now(),
        ],
    )
    waits = decision.outcome == "approve" and decision.payout > payout_limit(conn)
    set_status(conn, claim_id, "waiting_for_sign_off" if waits else "decided")
    return get_claim(claim_id, conn)


@app.post("/api/claims/{claim_id}/payment", operation_id="pay_claim")
def pay_claim(claim_id: str, payment: PaymentRequest, conn: Database) -> Claim:
    """Pay an approved claim its payout, once any sign-off it needs is given."""
    claim = get_claim(claim_id, conn)
    decision = claim.decision
    limit = payout_limit(conn)
    if decision is None or decision.outcome != "approve":
        raise HTTPException(409, f"Claim {claim_id} is not approved")
    if claim.payment:
        raise HTTPException(409, f"Claim {claim_id} is already paid")
    if decision.payout > limit and decision.signed_off_by is None:
        raise HTTPException(
            409, f"A payout over ${limit:,.2f} needs a handler's sign-off first"
        )
    if round(payment.amount, 2) != round(decision.payout, 2):
        raise HTTPException(409, f"The approved payout is ${decision.payout:,.2f}")
    pay(conn, claim_id, payment.amount)
    return get_claim(claim_id, conn)


@app.post("/api/claims/{claim_id}/sign-off", operation_id="sign_off")
def sign_off(claim_id: str, request: SignOffRequest, conn: Database) -> Claim:
    """Sign off a payout over the approval limit, which releases its payment."""
    if status_of(conn, claim_id) != "waiting_for_sign_off":
        raise HTTPException(409, f"Claim {claim_id} is not waiting for sign-off")
    handler = Handler.model_validate(
        record(conn, "handlers", "handler_id", request.handler_id)
    )
    if not handler.can_approve_over_limit:
        raise HTTPException(403, f"{handler.name} can't sign off this payout")
    row = conn.execute(
        "UPDATE decisions SET signed_off_by = ?, signed_off_at = ?"
        " WHERE claim_id = ? RETURNING payout",
        [handler.handler_id, now(), claim_id],
    ).fetchone()
    pay(conn, claim_id, row["payout"])
    set_status(conn, claim_id, "decided")
    return get_claim(claim_id, conn)


@app.get("/api/policies/{policy_id}", operation_id="get_policy")
def get_policy(policy_id: str, conn: Database) -> Policy:
    """Get a policy with its plan's limits, add-ons, trip and travelers."""
    policy = record(conn, "policies", "policy_id", policy_id)
    plan = record(conn, "plans", "plan", policy["plan"])
    return Policy.model_validate(policy | {"plan": plan})


@app.get("/api/customers/{customer_id}/claims", operation_id="get_claim_history")
def get_claim_history(customer_id: str, conn: Database) -> list[PreviousClaim]:
    """List a customer's earlier claims and their outcomes."""
    customer = record(conn, "customers", "customer_id", customer_id)
    return [PreviousClaim.model_validate(c) for c in customer["previous_claims"]]


@app.get("/api/handlers", operation_id="list_handlers")
def list_handlers(conn: Database) -> list[Handler]:
    """List the claims handlers."""
    rows = conn.execute("SELECT record FROM handlers ORDER BY handler_id").fetchall()
    return [Handler.model_validate_json(row["record"]) for row in rows]


@app.get("/api/policy-wording", operation_id="get_policy_wording")
def get_policy_wording() -> Text:
    """Get the policy wording, the contract that decisions follow."""
    return Text(text=(db.DATA / "policy_wording.md").read_text(encoding="utf-8"))


@app.get("/api/instructions", operation_id="get_instructions")
def get_instructions() -> Text:
    """Get the UnderCover Agent's instructions."""
    return Text(text=INSTRUCTIONS.read_text(encoding="utf-8"))
