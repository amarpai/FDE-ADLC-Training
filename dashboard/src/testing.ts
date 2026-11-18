import { vi } from "vitest";
import type {
  Claim,
  ClaimSummary,
  Decision,
  Handler,
  Policy,
  PreviousClaim,
  Step,
} from "./api";

/** Stub fetch with a reply for each path, or each "POST path". */
export function stubFetch(routes: Record<string, unknown>) {
  const fetch = vi.fn((path: string, init?: RequestInit) => {
    const key = init?.method === "POST" ? `POST ${path}` : path;
    const body = routes[key];
    return Promise.resolve(
      body === undefined
        ? Response.json({ detail: `No route ${key}` }, { status: 404 })
        : Response.json(body),
    );
  });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

export const approval: Decision = {
  outcome: "approve",
  payout: 420,
  reasons: "The flight was canceled for a crew problem. The costs are covered.",
  policy_section: "Section 3, Trip Delay",
  decided_at: "2026-11-18T20:57:09+00:00",
  signed_off_by: null,
  signed_off_at: null,
};

export const waiting: ClaimSummary = {
  claim_id: "CLM-1001",
  customer_name: "Maya Patel",
  claim_type: "trip_delay",
  summary: "Flight home canceled by the airline",
  amount_claimed: 420,
  submitted_on: "2026-06-24",
  status: "waiting",
  decision: null,
  payment: null,
};

export const decided: ClaimSummary = {
  ...waiting,
  claim_id: "CLM-1002",
  customer_name: "Jonah Reyes",
  claim_type: "baggage",
  amount_claimed: 1150,
  status: "decided",
  decision: approval,
  payment: { amount: 420, paid_at: "2026-11-18T20:57:13+00:00" },
};

export const claim: Claim = {
  ...waiting,
  policy_id: "POL-2001",
  customer_id: "CUS-3001",
  incident_date: "2026-06-18",
  incident_location: "Rome, Italy",
  story: "My flight home from Rome was canceled by Meridian Air.",
  items: [
    {
      description: "Airport hotel, one night",
      category: "accommodation",
      amount: 245,
    },
    { description: "Dinner and breakfast", category: "meals", amount: 175 },
  ],
  documents: [
    {
      name: "Meridian Air cancellation notice",
      type: "carrier_report",
      content: "Flight MA 611 was canceled because of crew availability.",
    },
  ],
};

export const policy: Policy = {
  policy_id: "POL-2001",
  plan: { plan: "premium", name: "UnderCover Premium", deductible: 50 },
  add_ons: ["electronics_plus"],
  purchased_on: "2026-04-22",
  sold_through: "Meridian Air checkout",
  trip: {
    destination: "Rome, Italy",
    departs_on: "2026-06-10",
    returns_on: "2026-06-18",
    trip_cost: 3100,
  },
  travelers: ["Maya Patel"],
};

export const history: PreviousClaim[] = [
  {
    claim_id: "CLM-0412",
    filed_on: "2024-08-19",
    claim_type: "baggage_delay",
    summary: "Checked bag arrived 30 hours late in Lisbon",
    outcome: "approved",
    amount_paid: 140,
  },
];

export const handlers: Handler[] = [
  {
    handler_id: "HND-01",
    name: "Dana Whitfield",
    role: "Senior Claims Handler",
  },
  { handler_id: "HND-02", name: "Marcus Oyelaran", role: "Claims Handler" },
];

export const steps: Step[] = [
  {
    step_id: 1,
    kind: "tool_call",
    content: 'get_claim(claim_id="CLM-1001")',
    created_at: "2026-11-18T20:57:01+00:00",
  },
  {
    step_id: 2,
    kind: "tool_result",
    content: '{"claim_id":"CLM-1001"}',
    created_at: "2026-11-18T20:57:02+00:00",
  },
  {
    step_id: 3,
    kind: "tool_result",
    content: "Internal Server Error",
    created_at: "2026-11-18T20:57:03+00:00",
  },
  {
    step_id: 4,
    kind: "message",
    content: "Approved and paid: $420.00.",
    created_at: "2026-11-18T20:57:14+00:00",
  },
];

/** Every route the claim page reads, for a claim in the given state. */
export function claimRoutes(overrides: Partial<Claim>, claimSteps = steps) {
  return {
    "/api/claims/CLM-1001": { ...claim, ...overrides },
    "/api/claims/CLM-1001/steps": claimSteps,
    "/api/policies/POL-2001": policy,
    "/api/customers/CUS-3001/claims": history,
    "/api/handlers": handlers,
  };
}
