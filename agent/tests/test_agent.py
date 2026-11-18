import json

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, ToolMessage

from agent import main


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    def bind_tools(self, tools, **kwargs):
        return self


def calls(*tool_calls):
    """A model reply that calls tools, given as (name, args) pairs."""
    return AIMessage(
        content="",
        tool_calls=[
            {"name": name, "args": args, "id": str(i)}
            for i, (name, args) in enumerate(tool_calls)
        ],
    )


def decision(claim_id, outcome, payout):
    return (
        "record_decision",
        {
            "claim_id": claim_id,
            "outcome": outcome,
            "payout": payout,
            "reasons": "The wording covers it. The documents support it.",
            "policy_section": "Section 3, Trip Delay",
        },
    )


def stub(*replies):
    return StubModel(messages=iter(replies))


def test_the_agent_has_five_tools():
    assert [t.name for t in main.TOOLS] == [
        "get_claim",
        "get_policy",
        "get_claim_history",
        "record_decision",
        "pay_claim",
    ]


def test_read_tools(client):
    claim = json.loads(main.get_claim.invoke({"claim_id": "CLM-1001"}))
    assert claim["policy_id"] == "POL-2001"
    policy = json.loads(main.get_policy.invoke({"policy_id": "POL-2001"}))
    assert policy["plan"]["plan"] == "premium"
    history = json.loads(main.get_claim_history.invoke({"customer_id": "CUS-3001"}))
    assert history[0]["claim_id"] == "CLM-0412"


def test_a_tool_returns_a_refusal_as_text(client):
    reply = main.pay_claim.invoke({"claim_id": "CLM-1001", "amount": 420})
    assert json.loads(reply) == {"detail": "Claim CLM-1001 is not approved"}


def test_system_prompt(client):
    prompt = main.system_prompt(client)
    assert prompt.startswith("# The UnderCover Agent")
    assert "## 10. How we work out your payment" in prompt


def test_steps():
    message = calls(("get_policy", {"policy_id": "POL-2001"}))
    message.content = "Reading the policy."
    assert main.steps(message) == [
        {"kind": "message", "content": "Reading the policy."},
        {"kind": "tool_call", "content": 'get_policy(policy_id="POL-2001")'},
    ]
    result = ToolMessage(content='{"plan": "premium"}', tool_call_id="1")
    assert main.steps(result) == [
        {"kind": "tool_result", "content": '{"plan": "premium"}'}
    ]


def test_run_approves_and_pays(client):
    replies = [
        calls(("get_claim", {"claim_id": "CLM-1001"})),
        calls(
            ("get_policy", {"policy_id": "POL-2001"}),
            ("get_claim_history", {"customer_id": "CUS-3001"}),
        ),
        calls(decision("CLM-1001", "approve", 420)),
        calls(("pay_claim", {"claim_id": "CLM-1001", "amount": 420})),
        AIMessage(content="Approved, $420.00."),
    ]
    assert main.run("CLM-1001", "thread-1", stub(*replies)) == "Approved, $420.00."

    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "decided"
    assert claim["decision"]["outcome"] == "approve"
    assert claim["payment"]["amount"] == 420

    steps = client.get("/api/claims/CLM-1001/steps").json()
    assert [s["kind"] for s in steps] == [
        "tool_call",
        "tool_result",
        "tool_call",
        "tool_call",
        "tool_result",
        "tool_result",
        "tool_call",
        "tool_result",
        "tool_call",
        "tool_result",
        "message",
    ]
    assert steps[0]["content"] == 'get_claim(claim_id="CLM-1001")'
    assert steps[-1]["content"] == "Approved, $420.00."


def test_run_cannot_pay_over_the_limit(client):
    replies = [
        calls(decision("CLM-1003", "approve", 1250)),
        calls(("pay_claim", {"claim_id": "CLM-1003", "amount": 1250})),
        AIMessage(content="Approved, $1,250.00."),
    ]
    main.run("CLM-1003", "thread-1", stub(*replies))

    claim = client.get("/api/claims/CLM-1003").json()
    assert claim["status"] == "waiting_for_sign_off"
    assert claim["payment"] is None
    refusal = client.get("/api/claims/CLM-1003/steps").json()[3]
    assert refusal["kind"] == "tool_result"
    assert "needs a handler's sign-off" in refusal["content"]


def test_run_declines(client):
    replies = [
        calls(decision("CLM-1013", "decline", 0)),
        AIMessage(content="Declined."),
    ]
    main.run("CLM-1013", "thread-1", stub(*replies))
    claim = client.get("/api/claims/CLM-1013").json()
    assert claim["status"] == "decided"
    assert claim["decision"]["outcome"] == "decline"


def test_work_picks_only_waiting_claims(client, monkeypatch, capsys):
    client.post("/api/claims/CLM-1001/start")
    client.post(
        "/api/claims/CLM-1001/decision",
        json={
            "outcome": "decline",
            "payout": 0,
            "reasons": "Not covered.",
            "policy_section": "Section 9, General exclusions",
        },
    )
    worked = []
    monkeypatch.setattr(main, "run", lambda claim_id, _: worked.append(claim_id))
    main.work([])
    assert len(worked) == 24
    assert "CLM-1001" not in worked
    assert "CLM-1002 waiting: no decision recorded" in capsys.readouterr().out


def test_work_a_named_claim(client, monkeypatch, capsys):
    replies = [
        calls(decision("CLM-1001", "approve", 420)),
        calls(("pay_claim", {"claim_id": "CLM-1001", "amount": 420})),
        AIMessage(content="Approved."),
    ]
    run = main.run
    monkeypatch.setattr(
        main,
        "run",
        lambda claim_id, thread_id: run(claim_id, thread_id, stub(*replies)),
    )
    main.work(["CLM-1001"])
    assert capsys.readouterr().out == "CLM-1001 decided: approve $420.00, paid\n"


def test_model_name(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    assert main.model().model_name == "openai/gpt-6-luna"
    assert main.model().max_retries == main.MAX_RETRIES
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert main.model().model_name == "openrouter/free"
