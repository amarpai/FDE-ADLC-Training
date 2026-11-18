"""The UnderCover Agent."""

import json
import os
import uuid
from typing import Any, Literal

import httpx
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

load_dotenv(override=True)

BACKEND_URL = "http://localhost:8000"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-6-luna"


def backend() -> httpx.Client:
    """Return a client for the UnderCover backend."""
    return httpx.Client(base_url=BACKEND_URL, timeout=30)


def call(method: str, path: str, body: dict[str, Any] | None = None) -> str:
    """Call the backend and return its reply as text, refusals included."""
    with backend() as client:
        return client.request(method, path, json=body).text


@tool
def get_claim(claim_id: str) -> str:
    """Get a claim in full: the story, the items claimed and the documents."""
    return call("GET", f"/api/claims/{claim_id}")


@tool
def get_policy(policy_id: str) -> str:
    """Get a policy: its plan and limits, add-ons, trip dates and travelers."""
    return call("GET", f"/api/policies/{policy_id}")


@tool
def get_claim_history(customer_id: str) -> str:
    """Get a customer's earlier claims and their outcomes."""
    return call("GET", f"/api/customers/{customer_id}/claims")


@tool
def record_decision(
    claim_id: str,
    outcome: Literal["approve", "decline", "refer"],
    payout: float,
    reasons: str,
    policy_section: str,
) -> str:
    """Record the decision on a claim, with its payout, reasons and policy section."""
    return call(
        "POST",
        f"/api/claims/{claim_id}/decision",
        {
            "outcome": outcome,
            "payout": payout,
            "reasons": reasons,
            "policy_section": policy_section,
        },
    )


@tool
def pay_claim(claim_id: str, amount: float) -> str:
    """Pay an approved claim its payout. Over $1,000 needs a handler's sign-off."""
    return call("POST", f"/api/claims/{claim_id}/payment", {"amount": amount})


TOOLS = [get_claim, get_policy, get_claim_history, record_decision, pay_claim]


def model() -> ChatOpenAI:
    """Return the model named in MODEL_NAME, or GPT-6 Luna by default."""
    name = os.getenv("MODEL_NAME")
    return ChatOpenAI(
        model=name or DEFAULT_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=None if name else "low",
    )


def system_prompt(client: httpx.Client) -> str:
    """Build the agent's system prompt: its instructions, then the policy wording."""
    instructions = client.get("/api/instructions").raise_for_status().json()
    wording = client.get("/api/policy-wording").raise_for_status().json()
    return f"{instructions['text']}\n\n{wording['text']}"


def steps(message: BaseMessage) -> list[dict[str, str]]:
    """Describe one message of the agent's work as steps for the dashboard."""
    if isinstance(message, ToolMessage):
        return [{"kind": "tool_result", "content": message.text}]
    found = [{"kind": "message", "content": message.text}] if message.text else []
    if isinstance(message, AIMessage):
        for tool_call in message.tool_calls:
            args = ", ".join(
                f"{k}={json.dumps(v)}" for k, v in tool_call["args"].items()
            )
            found.append(
                {"kind": "tool_call", "content": f"{tool_call['name']}({args})"}
            )
    return found


def run(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Work one claim through to a decision and return the agent's final reply."""
    reply = ""
    with backend() as client:
        client.post(f"/api/claims/{claim_id}/start").raise_for_status()
        agent = create_agent(
            llm or model(), tools=TOOLS, system_prompt=system_prompt(client)
        )
        updates = agent.stream(
            {"messages": [{"role": "user", "content": f"Work claim {claim_id}."}]},
            config={"configurable": {"thread_id": thread_id}},
            stream_mode="updates",
        )
        for update in updates:
            for value in update.values():
                for message in value["messages"]:
                    for step in steps(message):
                        client.post(f"/api/claims/{claim_id}/steps", json=step)
                    if isinstance(message, AIMessage):
                        reply = message.text
    return reply


def describe(claim: dict[str, Any]) -> str:
    """Summarize where a claim stands in one line."""
    decision = claim["decision"]
    if decision is None:
        return f"{claim['claim_id']} {claim['status']}: no decision recorded"
    paid = ", paid" if claim["payment"] else ""
    payout = f"${decision['payout']:,.2f}"
    return (
        f"{claim['claim_id']} {claim['status']}: {decision['outcome']} {payout}{paid}"
    )


def work(claim_ids: list[str]) -> None:
    """Work the claims named, or every waiting claim in queue order."""
    with backend() as client:
        if not claim_ids:
            claims = client.get("/api/claims").raise_for_status().json()
            claim_ids = [c["claim_id"] for c in claims if c["status"] == "waiting"]
        for claim_id in claim_ids:
            run(claim_id, str(uuid.uuid4()))
            claim = client.get(f"/api/claims/{claim_id}").raise_for_status().json()
            print(describe(claim), flush=True)
