import type { Outcome, Status } from "./api";

export const STATUSES: Status[] = [
  "waiting",
  "in_progress",
  "waiting_for_sign_off",
  "decided",
];

export const STATUS_LABELS: Record<Status, string> = {
  waiting: "Waiting",
  in_progress: "In progress",
  waiting_for_sign_off: "Waiting for sign-off",
  decided: "Decided",
};

export const OUTCOME_LABELS: Record<Outcome, string> = {
  approve: "Approved",
  decline: "Declined",
  refer: "Referred",
};

const dollars = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

// Dates like 2026-06-24 parse as midnight UTC, so they are shown in UTC.
const day = new Intl.DateTimeFormat("en-US", {
  dateStyle: "medium",
  timeZone: "UTC",
});

const moment = new Intl.DateTimeFormat("en-US", {
  dateStyle: "medium",
  timeStyle: "short",
});

export function money(amount: number): string {
  return dollars.format(amount);
}

export function date(value: string): string {
  return day.format(new Date(value));
}

export function dateTime(value: string): string {
  return moment.format(new Date(value));
}

export function label(code: string): string {
  const words = code.replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}
