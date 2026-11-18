"""The UnderCover database: SQLite, seeded from UnderCover's records in data/."""

import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path
from typing import Any

DATA = Path(__file__).parent.parent / "data"
DEFAULT_PATH = Path(__file__).parent / "undercover.db"

SCHEMA = """
CREATE TABLE company (id INTEGER PRIMARY KEY CHECK (id = 1), record TEXT NOT NULL);
CREATE TABLE plans (plan TEXT PRIMARY KEY, record TEXT NOT NULL);
CREATE TABLE handlers (handler_id TEXT PRIMARY KEY, record TEXT NOT NULL);
CREATE TABLE customers (customer_id TEXT PRIMARY KEY, record TEXT NOT NULL);
CREATE TABLE policies (policy_id TEXT PRIMARY KEY, record TEXT NOT NULL);
CREATE TABLE claims (
    claim_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers,
    status TEXT NOT NULL,
    record TEXT NOT NULL
);
CREATE TABLE decisions (
    claim_id TEXT PRIMARY KEY REFERENCES claims,
    outcome TEXT NOT NULL,
    payout REAL NOT NULL,
    reasons TEXT NOT NULL,
    policy_section TEXT NOT NULL,
    decided_at TEXT NOT NULL,
    signed_off_by TEXT REFERENCES handlers,
    signed_off_at TEXT
);
CREATE TABLE payments (
    claim_id TEXT PRIMARY KEY REFERENCES claims,
    amount REAL NOT NULL,
    paid_at TEXT NOT NULL
);
CREATE TABLE steps (
    step_id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id TEXT NOT NULL REFERENCES claims,
    kind TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def path() -> Path:
    """Return the database file, from UNDERCOVER_DB or the default."""
    return Path(os.getenv("UNDERCOVER_DB", str(DEFAULT_PATH)))


def connect() -> sqlite3.Connection:
    """Open a connection whose rows can be read by column name."""
    conn = sqlite3.connect(path())
    conn.row_factory = sqlite3.Row
    return conn


def database() -> Iterator[sqlite3.Connection]:
    """Open the database for one request, committing what it changes."""
    with closing(connect()) as conn, conn:
        yield conn


def load(name: str) -> Any:
    """Read one of UnderCover's JSON records from data/."""
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def seed(conn: sqlite3.Connection) -> None:
    """Create the tables and load the records into an empty database."""
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT INTO company VALUES (1, ?)", [json.dumps(load("company.json"))]
    )
    rows = {
        "plans": [(p["plan"], json.dumps(p)) for p in load("plans.json")["plans"]],
        "handlers": [(h["handler_id"], json.dumps(h)) for h in load("handlers.json")],
        "customers": [
            (c["customer_id"], json.dumps(c)) for c in load("customers.json")
        ],
        "policies": [(p["policy_id"], json.dumps(p)) for p in load("policies.json")],
    }
    for table, values in rows.items():
        conn.executemany(f"INSERT INTO {table} VALUES (?, ?)", values)  # noqa: S608
    conn.executemany(
        "INSERT INTO claims VALUES (?, ?, 'waiting', ?)",
        [(c["claim_id"], c["customer_id"], json.dumps(c)) for c in load("claims.json")],
    )


def init() -> None:
    """Create and seed the database if it doesn't exist yet."""
    if path().exists():
        return
    with closing(connect()) as conn, conn:
        seed(conn)


def reset() -> None:
    """Delete the database and seed it again from data/."""
    path().unlink(missing_ok=True)
    init()
