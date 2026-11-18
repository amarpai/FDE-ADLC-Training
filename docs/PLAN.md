# Plan: the claims pilot

This plan builds the pilot in `docs/SPEC.md`. It covers a backend that holds UnderCover's records and enforces the claim rules, the UnderCover Agent that decides claims through that backend, and a dashboard where the handlers watch the queue, read each decision and sign off large payouts.

## How it fits together

```
dashboard (React, :5173) ──/api──▶ backend (FastAPI, :8000) ◀──HTTP── agent (npm run agent)
                                         │
                                SQLite: backend/undercover.db, seeded from data/
```

- Only the backend touches the database. It owns each claim's status and blocks any payment that breaks the rules.
- The agent is a separate process and an ordinary client of the API. It has no tool that reads files, so it can't reach `data/evals/`.
- The dashboard reads from the API and polls it every two seconds, so the queue and the agent's steps update without a reload.

## Decisions and why

1. **SQLite through Python's built-in `sqlite3`, with each record stored as JSON.** The seed data is already JSON documents. The parts that change (status, decision, sign-off, payment, steps) get their own columns and tables. An ORM would add a layer we don't need yet.
2. **The database seeds itself on first start.** If the file doesn't exist, the backend creates it from `data/`. `npm run seed` wipes it and starts over. The database path comes from `UNDERCOVER_DB` (default `backend/undercover.db`, already ignored by git), so tests and end-to-end runs get their own. The seed reads only `claims.json`, `policies.json`, `customers.json`, `plans.json`, `handlers.json` and `company.json`. The policy wording is served from `data/policy_wording.md`. Nothing is read from `data/evals/`, `data/security/` or the claims manual.
3. **A claim moves through four states:**

   | State | Label | Gets there when |
   |---|---|---|
   | `waiting` | Waiting | seeded (the data's `open`) |
   | `in_progress` | In progress | the agent starts work on it |
   | `waiting_for_sign_off` | Waiting for sign-off | the agent approves a payout over $1,000 |
   | `decided` | Decided | the agent declines, refers or approves $1,000 or less, or a handler signs off |

4. **The backend enforces the $1,000 rule, not the agent.** Paying is its own operation that takes the amount. It refuses (409) unless the claim is approved, the amount matches the approved payout, the claim hasn't been paid, and either the payout is $1,000 or less or a handler has signed off. The limit comes from `company.json`. The agent's instructions mention the rule too, but whatever the agent does, the backend is what stops the payment. When a handler signs off on the dashboard, the backend releases the payment.
5. **The agent's instructions live in the backend** (`backend/instructions.md`) and are served by the API, as `docs/TECH_STACK.md` requires. The agent builds its system prompt from the instructions plus the policy wording, both fetched from the API. The wording goes in the prompt rather than behind a tool for three reasons: it's short, every claim needs it, and a long fixed start to a prompt can be cached by the model provider.
6. **The agent's steps come from streaming.** `run()` streams the agent's updates, one per model turn and one per tool result, and posts each one to the backend as a step. I checked this stream format against the installed LangChain 1.4.2. Polling every two seconds is the simplest live view that works for three handlers. WebSockets or server-sent events would add moving parts for no real gain.
7. **The agent runs from the command line.** `npm run agent` works through the waiting claims in queue order, and `npm run agent -- CLM-1001` works a single claim. The spec asks for the team to see the agent's work, not to start it, so the dashboard has no run button.
8. **The agent's tools map one to one to API operations.** The tools are `get_claim`, `get_policy`, `get_claim_history`, `record_decision` and `pay_claim`. The agent reads the customer's claim history but never their address, phone or date of birth, because it doesn't need personal data to decide a claim.

## The API

Every operation has an `operation_id`, a one-line docstring and only required inputs. A test checks all three against `/openapi.json`.

| operation_id | Route | Used by |
|---|---|---|
| `health` | `GET /api/health` | checks |
| `list_claims` | `GET /api/claims` | dashboard |
| `get_claim` | `GET /api/claims/{claim_id}` | agent, dashboard |
| `get_policy` | `GET /api/policies/{policy_id}`, with its plan's limits | agent, dashboard |
| `get_claim_history` | `GET /api/customers/{customer_id}/claims` | agent, dashboard |
| `list_handlers` | `GET /api/handlers` | dashboard |
| `get_policy_wording` | `GET /api/policy-wording` | agent, dashboard |
| `get_instructions` | `GET /api/instructions` | agent, dashboard |
| `start_claim` | `POST /api/claims/{claim_id}/start` | agent |
| `add_step` | `POST /api/claims/{claim_id}/steps` with `kind`, `content` | agent |
| `list_steps` | `GET /api/claims/{claim_id}/steps` | dashboard |
| `record_decision` | `POST /api/claims/{claim_id}/decision` with `outcome`, `payout`, `reasons`, `policy_section` | agent |
| `pay_claim` | `POST /api/claims/{claim_id}/payment` with `amount` | agent |
| `sign_off` | `POST /api/claims/{claim_id}/sign-off` with `handler_id` | dashboard |

Errors: 404 for an unknown id, 409 when the claim's state doesn't allow the operation (with the reason in `detail`), and 422 for bad input.

## Not in this plan

- The claims manual, sign-in, real payments and messages to customers, as the spec says.
- Scoring the agent against `data/evals/`. `docs/PROCESS.md` says not to open it unless asked, and the agent's instructions are written from the policy wording alone.
- A button to start the agent from the dashboard, and a way for a handler to overrule a decision.
- Recovering a run that fails partway through. `npm run agent -- <claim id>` starts that claim again from scratch.

---

## Phase 1: The database and the records API

**Builds:** `backend/db.py` (schema, connection, seeding), `backend/seed.py` with `npm run seed`, and the read operations: `list_claims`, `get_claim`, `get_policy`, `get_claim_history`, `list_handlers` and `get_policy_wording`. Responses are Pydantic models. `list_claims` returns one summary row per claim with the customer's name. Each test gets its own fresh database in a temporary folder.

**Why first:** everything else reads these records, and the test fixture built here is reused by every later phase.

- [x] `uv run pytest backend` passes, with tests for seeding and every read operation, including 404s for unknown ids
- [x] `npm run seed` creates `backend/undercover.db` with 25 claims (all `waiting`), 50 policies, 49 customers and 3 handlers
- [x] With `npm run dev` running, `curl -s http://localhost:8000/api/claims` returns 25 rows, each with `claim_id`, `customer_name`, `claim_type`, `amount_claimed`, `submitted_on` and status `waiting`
- [x] `curl -s http://localhost:8000/api/claims/CLM-1001` returns the story, 3 items and 4 documents, and `/api/claims/CLM-9999` returns 404
- [x] `curl -s http://localhost:8000/api/policies/POL-2001` returns the Premium plan with its limits
- [x] `curl -s http://localhost:8000/api/customers/CUS-3001/claims` returns CLM-0412 and no contact details
- [x] `curl -s http://localhost:8000/api/policy-wording` returns the text of `data/policy_wording.md`
- [x] A test walks `/openapi.json` and finds that every operation has an `operation_id` and a one-line description, with no optional parameters or body fields
- [x] A test checks that the claim ids in the database are exactly those in `data/claims.json`
- [x] `docs/STATUS.md` updated, and committed with the pre-commit hook passing

## Phase 2: The claim workflow and the sign-off rule

**Builds:** `start_claim`, `add_step`, `list_steps`, `record_decision`, `pay_claim` and `sign_off`, with the states and rules above:

- `start_claim` moves a waiting or in-progress claim to `in_progress` and clears any steps from an earlier run. Any other state gets a 409.
- `add_step` accepts a step in any state, because the agent's last message arrives after its decision.
- `record_decision` needs `in_progress`. The outcome is `approve`, `decline` or `refer`. An approval needs a payout above $0, and a decline or referral has a payout of $0. The reasons and the policy section can't be empty. An approval over $1,000 goes to `waiting_for_sign_off`, and everything else goes to `decided`.
- `pay_claim` follows the rule in decision 4.
- `sign_off` needs `waiting_for_sign_off` and a known handler with `can_approve_over_limit`. It records who signed off and when, pays the approved payout and moves the claim to `decided`.
- `get_claim` and `list_claims` now include the decision, the sign-off and the payment.

**Why now:** the rules belong in the backend, so they are built and tested before an agent exists that could get them wrong.

- [x] Tests cover every state change and every refusal: deciding a waiting claim, deciding twice, paying a declined claim, paying the wrong amount, paying twice, signing off a claim that doesn't need it, and an unknown handler
- [x] The key test passes: a claim approved at $1,250.00 refuses `pay_claim` with 409 and records no payment. After `sign_off` by HND-01 it is `decided` and paid $1,250.00
- [x] The boundary test passes: $1,000.00 pays straight away, and $1,000.01 waits for sign-off
- [x] Against the dev server, these curl calls do what they should: start CLM-1001, record an approval of $420.00 and pay $420.00, which leaves the claim `decided` and paid. Recording a decision on waiting CLM-1002 returns 409. `npm run seed` then resets the database
- [x] Python coverage is 80% or more, and `npm run check:python` passes
- [x] `docs/STATUS.md` updated, and committed with the pre-commit hook passing

## Phase 3: The UnderCover Agent

**Builds:**

- `backend/instructions.md` and `get_instructions`. The instructions tell the agent to:
  - read the claim, the policy and the claim history
  - check the incident against the trip dates, the cover, the documents the wording asks for, and the exclusions
  - work out the payout as section 10 of the wording says
  - refer the claim when a needed document is missing, the documents contradict the story, or the wording doesn't settle it
  - record the decision with two or three sentences of reasons and the section relied on
  - pay approved payouts of $1,000 or less, and leave larger ones for a handler's sign-off

  The instructions are written from the policy wording alone.
- `agent/main.py`: the five tools and `run(claim_id, thread_id)`. `run()` starts the claim, fetches the instructions and the wording, builds the agent with `create_agent`, posts each streamed step, and returns the final reply. Each tool returns the backend's response body even when the backend refuses, so the model sees why a payment was blocked.
- `agent/__main__.py` with `npm run agent`: with no argument it works the waiting claims in order, and with a claim id it works that one claim. It prints one line per claim.

**Why this shape:** the agent stays thin. The backend holds the rules and the records, and the agent reads, decides and records. That keeps the agent easy to test with a stub model.

- [x] `uv run pytest agent` passes, and no test calls a model. Stub-model tests cover these cases:
  - an approval under $1,000 is recorded and paid, with its steps posted in order
  - an approval over $1,000 where the stub tries to pay: the payment is refused, the tool reports the refusal, the claim is `waiting_for_sign_off`, and no payment is recorded
  - a decline
  - the command line picks only waiting claims
- [x] The agent's tool list is exactly the five tools, checked by a test
- [x] `curl -s http://localhost:8000/api/instructions` returns the instructions
- [x] Live check with the real model: `npm run agent -- CLM-1001` prints its decision, and `GET /api/claims/CLM-1001` shows `decided` or `waiting_for_sign_off`, with an outcome, a payout, reasons of two or three sentences and a policy section. `GET /api/claims/CLM-1001/steps` lists its tool calls in order. This costs one claim's worth of API spend
- [x] `npm run seed` resets the database, and `npm run check:python` passes
- [x] `docs/STATUS.md` updated, and committed with the pre-commit hook passing

## Phase 4: The dashboard and the queue

**Builds:**

- The brand: Instrument Sans, Instrument Serif and JetBrains Mono from Google Fonts. `dashboard/src/styles.css` holds the brand colors and surfaces as CSS variables, for light and dark mode. The four states use Marigold (Waiting), Cerulean (In progress), Coral (Waiting for sign-off) and Sea Green (Decided). Panels are rounded with no outlines.
- `react-router` for three pages, because it handles links and the back button without custom code. A header has the UnderCover name and links to Queue and Instructions.
- `api.ts` (typed fetch functions, never `any`), `format.ts` (US dollars as $1,250.00, state and claim-type labels) and a small `usePolling` hook.
- The queue page has a count for each of the four states and a table of claims: claim, customer, type, amount claimed, submitted, state, decision and payout. Each row links to its claim.
- End-to-end setup: Playwright runs its own backend on port 8001, which runs `uv run -m backend.seed` first so it starts on a fresh database, and its own dashboard on port 5174. The Vite proxy reads `BACKEND_URL`, so the tests never touch the dev data and can run while `npm run dev` is up. `e2e/queue.spec.ts` replaces `e2e/health.spec.ts`.

**Why polling the whole queue:** 25 claims is a small response, and refetching them every two seconds is simpler than tracking changes.

- [ ] Vitest tests cover the queue's rows, state labels, counts and money format against a stubbed `fetch`. TypeScript coverage is 80% or more
- [ ] `npm run e2e` passes: the queue shows 25 claims, with CLM-1001 Waiting
- [ ] In the browser, through the Playwright MCP server: `http://localhost:5173` shows the four counts and 25 rows in the brand fonts and colors, checked with screenshots in light and dark mode
- [ ] In the browser: after `curl -X POST http://localhost:8000/api/claims/CLM-1001/start`, the row changes to In progress within a few seconds without a reload. `npm run seed` then resets the database
- [ ] `npm run check:ts` passes
- [ ] `docs/STATUS.md` updated, and committed with the pre-commit hook passing

## Phase 5: The claim page and the instructions page

**Builds:**

- The claim page at `/claims/:claimId` has these sections:
  - the header: claim id, summary and state
  - the claim: story, items with their total, and the documents
  - the policy: plan, add-ons, trip dates, trip cost, travelers and purchase date
  - the customer's earlier claims
  - the agent's decision: outcome, payout, reasons and policy section, with the payment shown as Paid, Waits for sign-off or Not paid
  - the agent's steps, in order: each tool call with its arguments and each result folded away until opened. They poll while the claim is in progress
  - while the claim waits for sign-off, a handler picker and a "Sign off and pay" button
- The instructions page shows the agent's instructions, read only, with the policy wording the agent also receives in a folded section below.

**Why one page per claim:** a handler reviewing a decision needs the story, the documents, the policy and the agent's reasons side by side.

- [ ] Vitest tests cover the claim page in each state, the steps list, the sign-off control (shown only while waiting for sign-off) and the instructions page
- [ ] `e2e/claim.spec.ts` passes. It plays the agent through the API, so no model is called:
  - a claim approved and paid under $1,000 shows Decided, the reasons, the section, the steps and Paid
  - a claim approved at $1,250.00 has its payment refused through the API, shows Waiting for sign-off, and after Dana Whitfield signs off on the page shows Decided, Paid $1,250.00 and who signed off
  - a step posted while the page is open appears without a reload
- [ ] `e2e/instructions.spec.ts` passes: the page shows the instructions and has no way to edit them
- [ ] In the browser: clicking a row on the queue opens its claim page, and the back button returns to the queue
- [ ] `npm run check:ts` and `npm run e2e` pass
- [ ] `docs/STATUS.md` updated, and committed with the pre-commit hook passing

## Phase 6: Working the queue end to end

**Builds:** no new features. The real agent works the whole queue while the dashboard watches, and I fix whatever this turns up within the spec. I don't tune the instructions against `data/evals/`. The phase also finishes `docs/STATUS.md`: what's built, how to run it (`npm run dev`, `npm run seed`, `npm run agent`) and the API.

**Cost:** this phase runs the agent on all 25 claims, at a handful of model calls each, on `openai/gpt-6-luna`. To run it free, set `MODEL_NAME=openrouter/free` in `.env`, but expect it to be slower and to hit the free model's daily limits.

- [ ] After `npm run seed`, `npm run agent` works all 25 claims, printing one decision line per claim
- [ ] In the browser, a claim's steps appear one by one while the agent works on it
- [ ] Every claim ends `decided` or `waiting_for_sign_off`, each with reasons and a policy section, and the report lists how many were approved, declined and referred
- [ ] No claim with a payout over $1,000 has a payment without a sign-off, checked against `GET /api/claims`
- [ ] In the browser, signing off one claim that is waiting for sign-off makes it Decided and paid
- [ ] `docs/STATUS.md` describes the pilot as built and how to run it
- [ ] `npm run check` passes in full, and committed with the pre-commit hook passing
