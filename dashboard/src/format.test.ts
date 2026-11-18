import { expect, it } from "vitest";
import { date, dateTime, label, money } from "./format";

it("formats money in US dollars", () => {
  expect(money(1250)).toBe("$1,250.00");
  expect(money(0)).toBe("$0.00");
});

it("formats a date as it is written, whatever the time zone", () => {
  expect(date("2026-06-24")).toBe("Jun 24, 2026");
});

it("formats a moment with its date and time", () => {
  expect(dateTime("2026-11-18T20:57:09+00:00")).toContain("Nov 18, 2026");
});

it("turns codes into labels", () => {
  expect(label("emergency_medical")).toBe("Emergency medical");
  expect(label("passport")).toBe("Passport");
});
