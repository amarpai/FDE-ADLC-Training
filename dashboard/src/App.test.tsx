import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./App";
import { stubFetch, waiting } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("shows the queue with links to each page", async () => {
  stubFetch({ "/api/claims": [waiting] });
  render(
    <MemoryRouter>
      <App />
    </MemoryRouter>,
  );
  expect(
    await screen.findByRole("heading", { name: "Claims queue" }),
  ).toBeDefined();
  const nav = screen.getByRole("navigation", { name: "Main" });
  expect(nav.textContent).toBe("QueueInstructions");
});
