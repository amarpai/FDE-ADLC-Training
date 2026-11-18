import { afterEach, expect, it, vi } from "vitest";
import { getJson, postJson } from "./api";
import { stubFetch } from "./testing";

afterEach(() => {
  vi.unstubAllGlobals();
});

it("reads JSON", async () => {
  stubFetch({ "/api/health": { status: "ok" } });
  expect(await getJson("/api/health")).toEqual({ status: "ok" });
});

it("throws the backend's reason for a refusal", async () => {
  stubFetch({});
  await expect(getJson("/api/claims/CLM-9999")).rejects.toThrow(
    "No route /api/claims/CLM-9999",
  );
});

it("posts JSON", async () => {
  const fetch = stubFetch({ "POST /api/claims/CLM-1001/start": { ok: true } });
  expect(await postJson("/api/claims/CLM-1001/start", {})).toEqual({
    ok: true,
  });
  expect(fetch).toHaveBeenCalledWith("/api/claims/CLM-1001/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}",
  });
});
