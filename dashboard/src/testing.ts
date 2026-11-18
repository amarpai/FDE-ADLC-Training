import { vi } from "vitest";
import type { ClaimSummary, Decision } from "./api";

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
