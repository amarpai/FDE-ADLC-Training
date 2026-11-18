import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, expect, it, vi } from "vitest";
import { ClaimPage } from "./ClaimPage";
import { approval, claimRoutes, stubFetch } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function renderClaim() {
  render(
    <MemoryRouter initialEntries={["/claims/CLM-1001"]}>
      <Routes>
        <Route path="/claims/:claimId" element={<ClaimPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

async function panel(name: string) {
  return within(await screen.findByRole("region", { name }));
}

it("shows a waiting claim in full", async () => {
  stubFetch(claimRoutes({}, []));
  renderClaim();
  expect(await screen.findByRole("heading", { level: 1 })).toBeDefined();
  expect(screen.getByText("Waiting")).toBeDefined();

  const decision = await panel("The agent's decision");
  expect(
    decision.getByText("The agent hasn't decided this claim yet."),
  ).toBeDefined();
  expect(
    (await panel("The customer's story")).getByText(/Meridian Air/),
  ).toBeDefined();

  const items = await panel("Items claimed");
  expect(
    items.getByRole("row", { name: /Total claimed/ }).textContent,
  ).toContain("$420.00");
  expect(items.getByText("Accommodation")).toBeDefined();

  const documents = await panel("Documents");
  expect(documents.getByText("Meridian Air cancellation notice")).toBeDefined();
  expect(documents.getByText("Carrier report")).toBeDefined();

  const policy = await panel("The policy");
  expect(await policy.findByText("UnderCover Premium")).toBeDefined();
  expect(policy.getByText("Electronics plus")).toBeDefined();
  expect(
    policy.getByText("Rome, Italy, Jun 10, 2026 to Jun 18, 2026"),
  ).toBeDefined();

  const history = await panel("Earlier claims");
  expect(
    await history.findByText(/Checked bag arrived 30 hours late/),
  ).toBeDefined();
  expect(history.getByText("Approved, paid $140.00")).toBeDefined();

  const steps = await panel("The agent's steps");
  expect(await steps.findByText("No steps yet.")).toBeDefined();
});

it("shows the agent's steps in order", async () => {
  stubFetch(claimRoutes({ status: "in_progress" }));
  renderClaim();
  const steps = await panel("The agent's steps");
  const items = await steps.findAllByRole("listitem");
  expect(items).toHaveLength(4);
  expect(items[0]?.textContent).toContain('get_claim(claim_id="CLM-1001")');
  expect(items[1]?.querySelector("pre")?.textContent).toBe(
    '{\n  "claim_id": "CLM-1001"\n}',
  );
  expect(items[2]?.querySelector("pre")?.textContent).toBe(
    "Internal Server Error",
  );
  expect(items[3]?.textContent).toContain("Approved and paid: $420.00.");
});

it("shows a decision that was paid", async () => {
  stubFetch(
    claimRoutes({
      status: "decided",
      decision: approval,
      payment: { amount: 420, paid_at: "2026-11-18T20:57:13+00:00" },
    }),
  );
  renderClaim();
  const decision = await panel("The agent's decision");
  expect(await decision.findByText("Approved")).toBeDefined();
  expect(decision.getByText(approval.reasons)).toBeDefined();
  expect(decision.getByText(/Section 3, Trip Delay/)).toBeDefined();
  expect(decision.getByText(/Paid \$420\.00 on/)).toBeDefined();
  expect(decision.queryByRole("button")).toBeNull();
});

it("shows an approval that was never paid", async () => {
  stubFetch(claimRoutes({ status: "decided", decision: approval }));
  renderClaim();
  const decision = await panel("The agent's decision");
  expect(await decision.findByText("Not paid")).toBeDefined();
});

it("shows a decline with no payment", async () => {
  stubFetch(
    claimRoutes({
      status: "decided",
      decision: { ...approval, outcome: "decline", payout: 0 },
    }),
  );
  renderClaim();
  const decision = await panel("The agent's decision");
  expect(await decision.findByText("Declined")).toBeDefined();
  expect(decision.queryByText(/Paid|Not paid|sign-off/)).toBeNull();
});

it("lets a handler sign off a payout over $1,000", async () => {
  const signing = { ...approval, payout: 1250 };
  const fetch = stubFetch({
    ...claimRoutes({ status: "waiting_for_sign_off", decision: signing }),
    "POST /api/claims/CLM-1001/sign-off": {},
  });
  renderClaim();
  const decision = await panel("The agent's decision");
  expect(
    await decision.findByText("The payment waits for a handler's sign-off."),
  ).toBeDefined();
  const button = decision.getByRole("button", { name: "Sign off and pay" });
  expect(button.hasAttribute("disabled")).toBe(true);

  await decision.findByRole("option", { name: "Dana Whitfield" });
  fireEvent.change(decision.getByLabelText("Handler"), {
    target: { value: "HND-01" },
  });
  fireEvent.click(button);
  expect(fetch).toHaveBeenCalledWith(
    "/api/claims/CLM-1001/sign-off",
    expect.objectContaining({ body: '{"handler_id":"HND-01"}' }),
  );
});

it("shows who signed off and the payment", async () => {
  stubFetch(
    claimRoutes({
      status: "decided",
      decision: {
        ...approval,
        payout: 1250,
        signed_off_by: "HND-01",
        signed_off_at: "2026-11-18T21:10:00+00:00",
      },
      payment: { amount: 1250, paid_at: "2026-11-18T21:10:00+00:00" },
    }),
  );
  renderClaim();
  const decision = await panel("The agent's decision");
  expect(
    await decision.findByText(/Signed off by Dana Whitfield/),
  ).toBeDefined();
  expect(decision.getByText(/Paid \$1,250\.00/)).toBeDefined();
});

it("shows why a sign-off was refused", async () => {
  stubFetch(
    claimRoutes({
      status: "waiting_for_sign_off",
      decision: { ...approval, payout: 1250 },
    }),
  );
  renderClaim();
  const decision = await panel("The agent's decision");
  await decision.findByRole("option", { name: "Dana Whitfield" });
  fireEvent.change(decision.getByLabelText("Handler"), {
    target: { value: "HND-01" },
  });
  fireEvent.click(decision.getByRole("button", { name: "Sign off and pay" }));
  expect((await decision.findByRole("alert")).textContent).toBe(
    "No route POST /api/claims/CLM-1001/sign-off",
  );
});

it("says when a claim can't be loaded", async () => {
  stubFetch({});
  renderClaim();
  expect(await screen.findByText("Can't load claim CLM-1001.")).toBeDefined();
});
