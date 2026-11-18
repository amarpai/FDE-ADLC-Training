import { Link } from "react-router";
import type { ClaimSummary } from "./api";
import { OUTCOME_LABELS, STATUSES, date, label, money } from "./format";
import { StatusChip } from "./StatusChip";
import { usePolling } from "./usePolling";

function Row({ claim }: Readonly<{ claim: ClaimSummary }>) {
  const { decision } = claim;
  return (
    <tr>
      <td>
        <Link className="mono" to={`/claims/${claim.claim_id}`}>
          {claim.claim_id}
        </Link>
      </td>
      <td>{claim.customer_name}</td>
      <td>{label(claim.claim_type)}</td>
      <td className="mono number">{money(claim.amount_claimed)}</td>
      <td>{date(claim.submitted_on)}</td>
      <td>
        <StatusChip status={claim.status} />
      </td>
      <td>{decision && OUTCOME_LABELS[decision.outcome]}</td>
      <td className="mono number">{decision && money(decision.payout)}</td>
    </tr>
  );
}

export function Queue() {
  const { data: claims, failed } = usePolling<ClaimSummary[]>("/api/claims");

  if (!claims) {
    return (
      <p className="notice">
        {failed ? "Can't reach the backend." : "Loading the queue..."}
      </p>
    );
  }

  return (
    <>
      <h1>Claims queue</h1>
      {failed && <p className="notice">Can't reach the backend.</p>}
      <ul className="counts" aria-label="Claims by status">
        {STATUSES.map((status) => (
          <li className="panel count" key={status}>
            <StatusChip status={status} />
            <span className="mono count-number">
              {claims.filter((c) => c.status === status).length}
            </span>
          </li>
        ))}
      </ul>
      <div className="panel table-panel">
        <table>
          <thead>
            <tr>
              <th scope="col">Claim</th>
              <th scope="col">Customer</th>
              <th scope="col">Type</th>
              <th scope="col" className="number">
                Claimed
              </th>
              <th scope="col">Submitted</th>
              <th scope="col">Status</th>
              <th scope="col">Decision</th>
              <th scope="col" className="number">
                Payout
              </th>
            </tr>
          </thead>
          <tbody>
            {claims.map((claim) => (
              <Row claim={claim} key={claim.claim_id} />
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
