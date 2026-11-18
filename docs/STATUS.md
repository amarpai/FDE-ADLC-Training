# Status

The pilot from `docs/SPEC.md` is built, following `docs/PLAN.md`.

## What's built

- `backend/`: FastAPI on SQLite. The database (`backend/undercover.db`, or the path in `UNDERCOVER_DB`) is created and seeded from `data/` on first start. It never reads `data/evals/`, `data/security/` or the claims manual.
  - A claim goes from `waiting` to `in_progress`, then to `waiting_for_sign_off` (an approval over $1,000) or `decided`.
  - Paying refuses a payout over $1,000 until a handler signs off, whatever the agent does. Signing off releases the payment.
  - The agent's instructions are in `backend/instructions.md`, served by the API.
- `agent/`: the UnderCover Agent, LangChain's `create_agent` on OpenRouter. `run(claim_id, thread_id)` starts the claim, builds its system prompt from the instructions and the policy wording (both from the API), and posts each step to the backend as it works. Its five tools each call one backend operation: `get_claim`, `get_policy`, `get_claim_history`, `record_decision` and `pay_claim`. It sees a customer's claim history but not their contact details.
- `dashboard/`: React and Vite with `react-router`, in the UnderCover brand, in light and dark mode. Three pages, which update every two seconds:
  - the queue: a count for each state, and every claim with its decision and payout
  - a claim (`/claims/<id>`): the story, items, documents, policy and earlier claims, the agent's decision and reasons, its steps as it works, and a sign-off for a payout over $1,000
  - the instructions (`/instructions`): the agent's instructions and the policy wording, read only
- `e2e/`: Playwright tests. They run their own backend on port 8001, on a fresh `e2e/undercover.db`, and their own dashboard on port 5174, so they can run alongside `npm run dev`. They play the agent through the API and never call a model.

## How to run it

- `npm run dev` starts the backend on port 8000 and the dashboard at http://localhost:5173
- `npm run agent` works every waiting claim in queue order, and `npm run agent -- CLM-1001` works one claim. The backend must be running. It uses `openai/gpt-6-luna`, or the model in `MODEL_NAME`, such as `openrouter/free`
- `npm run seed` deletes the database and seeds it again from `data/`, to start the pilot over
- `npm run check` runs every check

## The API

| Operation | Route |
|---|---|
| `health` | `GET /api/health` |
| `list_claims` | `GET /api/claims` |
| `get_claim` | `GET /api/claims/{claim_id}` |
| `start_claim` | `POST /api/claims/{claim_id}/start` |
| `add_step` | `POST /api/claims/{claim_id}/steps` |
| `list_steps` | `GET /api/claims/{claim_id}/steps` |
| `record_decision` | `POST /api/claims/{claim_id}/decision` |
| `pay_claim` | `POST /api/claims/{claim_id}/payment` |
| `sign_off` | `POST /api/claims/{claim_id}/sign-off` |
| `get_policy` | `GET /api/policies/{policy_id}` |
| `get_claim_history` | `GET /api/customers/{customer_id}/claims` |
| `list_handlers` | `GET /api/handlers` |
| `get_policy_wording` | `GET /api/policy-wording` |
| `get_instructions` | `GET /api/instructions` |

The full schema is at http://localhost:8000/docs while the backend runs.

## Not built

- The claims manual, sign-in, real payments and messages to customers, as `docs/SPEC.md` says
- Scoring the agent against `data/evals/`
- A button to start the agent from the dashboard, and a way for a handler to overrule a decision
