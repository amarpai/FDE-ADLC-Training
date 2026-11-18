import { act, cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, it, vi } from "vitest";
import { Queue } from "./Queue";
import { decided, stubFetch, waiting } from "./testing";
import { POLL_MS } from "./usePolling";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

function renderQueue() {
  render(
    <MemoryRouter>
      <Queue />
    </MemoryRouter>,
  );
}

it("lists the claims with where each one stands", async () => {
  stubFetch({ "/api/claims": [waiting, decided] });
  renderQueue();
  const link = await screen.findByRole("link", { name: "CLM-1001" });
  expect(link.getAttribute("href")).toBe("/claims/CLM-1001");
  const row = screen.getByRole("row", { name: /CLM-1002/ });
  expect(row.textContent).toContain("Jonah Reyes");
  expect(row.textContent).toContain("Baggage");
  expect(row.textContent).toContain("$1,150.00");
  expect(row.textContent).toContain("Jun 24, 2026");
  expect(row.textContent).toContain("Decided");
  expect(row.textContent).toContain("Approved");
  expect(row.textContent).toContain("$420.00");
});

it("counts the claims in each state", async () => {
  stubFetch({ "/api/claims": [waiting, decided, { ...waiting }] });
  renderQueue();
  const counts = await screen.findByRole("list", { name: "Claims by status" });
  const items = within(counts).getAllByRole("listitem");
  expect(items.map((item) => item.textContent)).toEqual([
    "Waiting2",
    "In progress0",
    "Waiting for sign-off0",
    "Decided1",
  ]);
});

it("says when it can't reach the backend", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  renderQueue();
  expect(await screen.findByText("Can't reach the backend.")).toBeDefined();
});

it("updates without a reload", async () => {
  vi.useFakeTimers();
  const fetch = stubFetch({ "/api/claims": [waiting] });
  renderQueue();
  await act(() => vi.advanceTimersByTimeAsync(0));
  expect(screen.getByRole("row", { name: /CLM-1001/ }).textContent).toContain(
    "Waiting",
  );

  fetch.mockResolvedValue(
    Response.json([{ ...waiting, status: "in_progress" }]),
  );
  await act(() => vi.advanceTimersByTimeAsync(POLL_MS));
  expect(screen.getByRole("row", { name: /CLM-1001/ }).textContent).toContain(
    "In progress",
  );
});
