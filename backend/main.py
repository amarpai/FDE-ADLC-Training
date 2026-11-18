"""The UnderCover backend."""

import json
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException

from backend import db
from backend.models import (
    Claim,
    ClaimSummary,
    Handler,
    Policy,
    PreviousClaim,
    Text,
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    db.init()
    yield


app = FastAPI(title="UnderCover", lifespan=lifespan)
Database = Annotated[sqlite3.Connection, Depends(db.database)]

CLAIMS = """
SELECT claims.status, claims.record, json_extract(customers.record, '$.name') AS name
FROM claims JOIN customers USING (customer_id)
"""


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
    """Merge a claim's record with its status and customer's name."""
    return json.loads(row["record"]) | {
        "status": row["status"],
        "customer_name": row["name"],
    }


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


@app.get("/api/claims", operation_id="list_claims")
def list_claims(conn: Database) -> list[ClaimSummary]:
    """List the claims queue in order, with where each claim stands."""
    rows = conn.execute(f"{CLAIMS} ORDER BY claim_id").fetchall()
    return [ClaimSummary.model_validate(claim_fields(row)) for row in rows]


@app.get("/api/claims/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str, conn: Database) -> Claim:
    """Get one claim in full: the story, the items and the documents."""
    row = conn.execute(f"{CLAIMS} WHERE claim_id = ?", [claim_id]).fetchone()
    if row is None:
        raise HTTPException(404, f"No claim {claim_id}")
    return Claim.model_validate(claim_fields(row))


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
