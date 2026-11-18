import { expect, test, type APIRequestContext } from "@playwright/test";

const REASONS =
  "The suitcase was lost by the airline on a connecting flight. Section 5 covers it, less the deductible.";

// Each test plays the agent through the API on a claim of its own.
async function decide(
  request: APIRequestContext,
  claimId: string,
  payout: number,
) {
  expect((await request.post(`/api/claims/${claimId}/start`)).ok()).toBe(true);
  await request.post(`/api/claims/${claimId}/steps`, {
    data: { kind: "tool_call", content: `get_claim(claim_id="${claimId}")` },
  });
  await request.post(`/api/claims/${claimId}/steps`, {
    data: { kind: "tool_result", content: `{"claim_id": "${claimId}"}` },
  });
  const decision = await request.post(`/api/claims/${claimId}/decision`, {
    data: {
      outcome: "approve",
      payout,
      reasons: REASONS,
      policy_section: "Section 5, Baggage and Personal Effects",
    },
  });
  expect(decision.ok()).toBe(true);
  return request.post(`/api/claims/${claimId}/payment`, {
    data: { amount: payout },
  });
}

test("an approval of $1,000 or less is decided and paid", async ({
  page,
  request,
}) => {
  expect((await decide(request, "CLM-1002", 900)).ok()).toBe(true);
  await request.post("/api/claims/CLM-1002/steps", {
    data: { kind: "message", content: "Approved and paid: $900.00." },
  });

  await page.goto("/claims/CLM-1002");
  const decision = page.getByRole("region", { name: "The agent's decision" });
  await expect(page.getByText("Decided").first()).toBeVisible();
  await expect(decision).toContainText("Approved");
  await expect(decision).toContainText("$900.00");
  await expect(decision).toContainText(REASONS);
  await expect(decision).toContainText(
    "Section 5, Baggage and Personal Effects",
  );
  await expect(decision).toContainText("Paid $900.00");

  const steps = page.getByRole("region", { name: "The agent's steps" });
  await expect(steps.getByRole("listitem")).toHaveCount(3);
  await expect(steps).toContainText('get_claim(claim_id="CLM-1002")');
  await expect(steps).toContainText("Approved and paid: $900.00.");
});

test("an approval over $1,000 waits for a handler's sign-off", async ({
  page,
  request,
}) => {
  const payment = await decide(request, "CLM-1003", 1250);
  expect(payment.status()).toBe(409);
  expect(await payment.json()).toEqual({
    detail: "A payout over $1,000.00 needs a handler's sign-off first",
  });

  await page.goto("/claims/CLM-1003");
  const decision = page.getByRole("region", { name: "The agent's decision" });
  await expect(decision).toContainText(
    "The payment waits for a handler's sign-off.",
  );
  await decision
    .getByLabel("Handler")
    .selectOption({ label: "Dana Whitfield" });
  await decision.getByRole("button", { name: "Sign off and pay" }).click();

  await expect(decision).toContainText("Signed off by Dana Whitfield");
  await expect(decision).toContainText("Paid $1,250.00");
  await expect(page.locator(".claim-header")).toContainText("Decided");
  await expect(decision.getByRole("button")).toHaveCount(0);
});

test("a step appears while the page is open", async ({ page, request }) => {
  await request.post("/api/claims/CLM-1004/start");
  await page.goto("/claims/CLM-1004");
  const steps = page.getByRole("region", { name: "The agent's steps" });
  await expect(steps).toContainText("No steps yet.");

  await request.post("/api/claims/CLM-1004/steps", {
    data: { kind: "message", content: "Reading the policy wording." },
  });
  await expect(steps).toContainText("Reading the policy wording.");
});

test("a row in the queue opens its claim, and back returns", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("link", { name: "CLM-1005" }).click();
  await expect(page).toHaveURL(/\/claims\/CLM-1005$/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "Passport eaten by a giraffe",
  );
  await expect(page.getByRole("region", { name: "The policy" })).toBeVisible();
  await page.goBack();
  await expect(
    page.getByRole("heading", { name: "Claims queue" }),
  ).toBeVisible();
});
