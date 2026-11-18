# Status

The pilot is being built from `docs/PLAN.md`. Phases 1 and 2 of 6 are done.

## What's built

- `backend/`: FastAPI on SQLite. The database (`backend/undercover.db`, or the path in `UNDERCOVER_DB`) is created and seeded from `data/` on first start.
  - Read operations for the claims queue, a claim, a policy with its plan, a customer's claim history, the handlers and the policy wording.
  - The claim workflow: start a claim, record the agent's steps, record a decision, pay, and sign off. A claim goes from `waiting` to `in_progress`, then to `waiting_for_sign_off` (an approval over $1,000) or `decided`.
  - Paying refuses a payout over $1,000 until a handler signs off. Signing off releases the payment.
- `agent/`: the skeleton's entry point `run(claim_id, thread_id)`, with one tool that calls the health route
- `dashboard/`: one page that shows whether the backend is up
- `e2e/`: one test of that page

## How to run it

- `npm run dev` starts the backend on port 8000 and the dashboard on port 5173
- `npm run seed` deletes the database and seeds it again from `data/`
- `npm run check` runs every check
