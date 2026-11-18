export type Status =
  "waiting" | "in_progress" | "waiting_for_sign_off" | "decided";
export type Outcome = "approve" | "decline" | "refer";
export type StepKind = "tool_call" | "tool_result" | "message";

export interface Decision {
  outcome: Outcome;
  payout: number;
  reasons: string;
  policy_section: string;
  decided_at: string;
  signed_off_by: string | null;
  signed_off_at: string | null;
}

export interface Payment {
  amount: number;
  paid_at: string;
}

export interface ClaimSummary {
  claim_id: string;
  customer_name: string;
  claim_type: string;
  summary: string;
  amount_claimed: number;
  submitted_on: string;
  status: Status;
  decision: Decision | null;
  payment: Payment | null;
}

export interface Item {
  description: string;
  category: string;
  amount: number;
}

export interface ClaimDocument {
  name: string;
  type: string;
  content: string;
}

export interface Claim extends ClaimSummary {
  policy_id: string;
  customer_id: string;
  incident_date: string;
  incident_location: string;
  story: string;
  items: Item[];
  documents: ClaimDocument[];
}

export interface Plan {
  plan: string;
  name: string;
  deductible: number;
}

export interface Policy {
  policy_id: string;
  plan: Plan;
  add_ons: string[];
  purchased_on: string;
  sold_through: string;
  trip: {
    destination: string;
    departs_on: string;
    returns_on: string;
    trip_cost: number;
  };
  travelers: string[];
}

export interface PreviousClaim {
  claim_id: string;
  filed_on: string;
  claim_type: string;
  summary: string;
  outcome: string;
  amount_paid: number;
}

export interface Handler {
  handler_id: string;
  name: string;
  role: string;
}

export interface Step {
  step_id: number;
  kind: StepKind;
  content: string;
  created_at: string;
}

export interface Text {
  text: string;
}

async function reply<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const { detail } = (await response.json()) as { detail: string };
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export async function getJson<T>(path: string): Promise<T> {
  return reply<T>(await fetch(path));
}

export async function postJson<T>(path: string, body: object): Promise<T> {
  return reply<T>(
    await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  );
}
