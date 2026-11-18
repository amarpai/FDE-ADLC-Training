import { Link, useParams } from "react-router";
import type { Claim, Handler, Policy, PreviousClaim } from "./api";
import { DecisionPanel } from "./DecisionPanel";
import { date, label, money } from "./format";
import { StatusChip } from "./StatusChip";
import { Steps } from "./Steps";
import { usePolling } from "./usePolling";

function PolicyPanel({ policyId }: Readonly<{ policyId: string }>) {
  const { data: policy } = usePolling<Policy>(
    `/api/policies/${policyId}`,
    false,
  );
  if (!policy) return null;
  const { trip } = policy;
  return (
    <section className="panel" aria-label="The policy">
      <h2>The policy</h2>
      <dl>
        <dt>Policy</dt>
        <dd className="mono">{policy.policy_id}</dd>
        <dt>Plan</dt>
        <dd>{policy.plan.name}</dd>
        <dt>Add-ons</dt>
        <dd>{policy.add_ons.map(label).join(", ") || "None"}</dd>
        <dt>Trip</dt>
        <dd>
          {trip.destination}, {date(trip.departs_on)} to {date(trip.returns_on)}
        </dd>
        <dt>Trip cost</dt>
        <dd className="mono">{money(trip.trip_cost)}</dd>
        <dt>Travelers</dt>
        <dd>{policy.travelers.join(", ")}</dd>
        <dt>Bought</dt>
        <dd>
          {date(policy.purchased_on)}, through {policy.sold_through}
        </dd>
      </dl>
    </section>
  );
}

function HistoryPanel({ customerId }: Readonly<{ customerId: string }>) {
  const { data: history } = usePolling<PreviousClaim[]>(
    `/api/customers/${customerId}/claims`,
    false,
  );
  if (!history) return null;
  return (
    <section className="panel" aria-label="Earlier claims">
      <h2>Earlier claims</h2>
      {history.length === 0 && <p className="muted">No earlier claims.</p>}
      <ul className="history">
        {history.map((earlier) => (
          <li key={earlier.claim_id}>
            <span className="mono">{earlier.claim_id}</span> ·{" "}
            {date(earlier.filed_on)} · {label(earlier.claim_type)}
            <br />
            {earlier.summary}
            <br />
            <span className="muted">
              {label(earlier.outcome)}, paid {money(earlier.amount_paid)}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ClaimDetails({ claim }: Readonly<{ claim: Claim }>) {
  return (
    <>
      <section className="panel" aria-label="The customer's story">
        <h2>The customer's story</h2>
        <p>{claim.story}</p>
      </section>
      <section className="panel" aria-label="Items claimed">
        <h2>Items claimed</h2>
        <table>
          <tbody>
            {claim.items.map((item) => (
              <tr key={item.description}>
                <td>{item.description}</td>
                <td className="muted">{label(item.category)}</td>
                <td className="mono number">{money(item.amount)}</td>
              </tr>
            ))}
            <tr className="total">
              <td>Total claimed</td>
              <td />
              <td className="mono number">{money(claim.amount_claimed)}</td>
            </tr>
          </tbody>
        </table>
      </section>
      <section className="panel" aria-label="Documents">
        <h2>Documents</h2>
        {claim.documents.map((doc) => (
          <article className="document" key={doc.name}>
            <h3>
              {doc.name} <span className="muted">{label(doc.type)}</span>
            </h3>
            <p>{doc.content}</p>
          </article>
        ))}
      </section>
    </>
  );
}

function ClaimView({
  claim,
  reload,
}: Readonly<{ claim: Claim; reload: () => void }>) {
  const { data: handlers } = usePolling<Handler[]>("/api/handlers", false);
  return (
    <>
      <div className="claim-header">
        <Link to="/">Queue</Link>
        <h1>
          <span className="mono">{claim.claim_id}</span> {claim.summary}
        </h1>
        <p>
          <StatusChip status={claim.status} /> {claim.customer_name} ·{" "}
          {label(claim.claim_type)} · {claim.incident_location},{" "}
          {date(claim.incident_date)} · submitted {date(claim.submitted_on)}
        </p>
      </div>
      <div className="claim-grid">
        <div className="stack">
          <DecisionPanel
            claim={claim}
            handlers={handlers ?? []}
            onChange={reload}
          />
          <ClaimDetails claim={claim} />
        </div>
        <div className="stack">
          <Steps claimId={claim.claim_id} />
          <PolicyPanel policyId={claim.policy_id} />
          <HistoryPanel customerId={claim.customer_id} />
        </div>
      </div>
    </>
  );
}

/** One claim in full, with the agent's decision, its reasons and its steps. */
export function ClaimPage() {
  const { claimId = "" } = useParams();
  const {
    data: claim,
    failed,
    reload,
  } = usePolling<Claim>(`/api/claims/${claimId}`);

  if (!claim) {
    return (
      <p className="notice">
        {failed ? `Can't load claim ${claimId}.` : "Loading the claim..."}
      </p>
    );
  }
  return <ClaimView claim={claim} reload={reload} />;
}
