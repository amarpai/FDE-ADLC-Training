# Status

The pilot is being built from `docs/PLAN.md`. Phases 1 to 5 of 6 are done.

## What's built

- `backend/`: FastAPI on SQLite. The database (`backend/undercover.db`, or the path in `UNDERCOVER_DB`) is created and seeded from `data/` on first start.
  - Read operations for the claims queue, a claim, a policy with its plan, a customer's claim history, the handlers and the policy wording.
  - The claim workflow: start a claim, record the agent's steps, record a decision, pay, and sign off. A claim goes from `waiting` to `in_progress`, then to `waiting_for_sign_off` (an approval over $1,000) or `decided`.
  - Paying refuses a payout over $1,000 until a handler signs off. Signing off releases the payment.
  - The agent's instructions are in `backend/instructions.md`, served by `GET /api/instructions`.
- `agent/`: the UnderCover Agent, LangChain's `create_agent` on OpenRouter. `run(claim_id, thread_id)` starts the claim, builds its system prompt from the instructions and the policy wording (both from the API), and posts each step to the backend as it works. Its five tools each call one backend operation: `get_claim`, `get_policy`, `get_claim_history`, `record_decision` and `pay_claim`.
- `dashboard/`: React and Vite with `react-router`, in the UnderCover brand, in light and dark mode. Three pages, which update every two seconds:
  - the queue: a count for each state, and every claim with its decision and payout
  - a claim (`/claims/<id>`): the story, items, documents, policy and earlier claims, the agent's decision and reasons, its steps as it works, and a sign-off for a payout over $1,000
  - the instructions (`/instructions`): the agent's instructions and the policy wording, read only
- `e2e/`: Playwright tests. They run their own backend on port 8001, on a fresh `e2e/undercover.db`, and their own dashboard on port 5174, so they can run alongside `npm run dev`.

## How to run it

- `npm run dev` starts the backend on port 8000 and the dashboard on port 5173
- `npm run seed` deletes the database and seeds it again from `data/`
- `npm run agent` works every waiting claim in queue order, and `npm run agent -- CLM-1001` works one claim. The backend must be running. It uses `openai/gpt-6-luna`, or the model in `MODEL_NAME`
- `npm run check` runs every check
