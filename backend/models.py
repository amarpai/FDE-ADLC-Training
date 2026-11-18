"""The shapes of the records the API reads and writes."""

from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

Status = Literal["waiting", "in_progress", "waiting_for_sign_off", "decided"]
Outcome = Literal["approve", "decline", "refer"]
StepKind = Literal["tool_call", "tool_result", "message"]


class DecisionRequest(BaseModel):
    outcome: Outcome
    payout: float = Field(ge=0)
    reasons: str = Field(min_length=1)
    policy_section: str = Field(min_length=1)

    @model_validator(mode="after")
    def payout_matches_outcome(self) -> Self:
        if (self.outcome == "approve") != (self.payout > 0):
            raise ValueError(
                "An approval needs a payout above $0, "
                "and a decline or referral a payout of $0"
            )
        return self


class Decision(DecisionRequest):
    decided_at: str
    signed_off_by: str | None
    signed_off_at: str | None


class PaymentRequest(BaseModel):
    amount: float


class Payment(PaymentRequest):
    paid_at: str


class SignOffRequest(BaseModel):
    handler_id: str


class StepRequest(BaseModel):
    kind: StepKind
    content: str


class Step(StepRequest):
    step_id: int
    created_at: str


class Item(BaseModel):
    description: str
    category: str
    amount: float


class Document(BaseModel):
    name: str
    type: str
    content: str


class ClaimSummary(BaseModel):
    claim_id: str
    customer_name: str
    claim_type: str
    summary: str
    amount_claimed: float
    submitted_on: str
    status: Status
    decision: Decision | None
    payment: Payment | None


class Claim(ClaimSummary):
    policy_id: str
    customer_id: str
    incident_date: str
    incident_location: str
    story: str
    items: list[Item]
    documents: list[Document]


class Plan(BaseModel):
    plan: str
    name: str
    trip_cancellation_max: float
    trip_delay_waiting_hours: int
    trip_delay_max: float
    baggage_delay_waiting_hours: int
    baggage_delay_max: float
    baggage_max: float
    per_item_limit: float
    passport_max: float
    emergency_medical_max: float
    deductible: float


class Trip(BaseModel):
    destination: str
    departs_on: str
    returns_on: str
    trip_cost: float


class Policy(BaseModel):
    policy_id: str
    customer_id: str
    plan: Plan
    add_ons: list[str]
    purchased_on: str
    sold_through: str
    trip: Trip
    travelers: list[str]
    status: str


class PreviousClaim(BaseModel):
    claim_id: str
    filed_on: str
    incident_date: str
    claim_type: str
    summary: str
    outcome: str
    amount_paid: float


class Handler(BaseModel):
    handler_id: str
    name: str
    role: str
    email: str
    can_approve_over_limit: bool


class Text(BaseModel):
    text: str
