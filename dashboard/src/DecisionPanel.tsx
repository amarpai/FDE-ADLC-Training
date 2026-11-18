import { useState, type SyntheticEvent } from "react";
import { postJson, type Claim, type Handler } from "./api";
import { OUTCOME_LABELS, dateTime, money } from "./format";

interface Props {
  claim: Claim;
  handlers: Handler[];
  onChange: () => void;
}

function SignOff({ claim, handlers, onChange }: Readonly<Props>) {
  const [handlerId, setHandlerId] = useState("");
  const [error, setError] = useState("");

  const submit = (event: SyntheticEvent) => {
    event.preventDefault();
    postJson(`/api/claims/${claim.claim_id}/sign-off`, {
      handler_id: handlerId,
    })
      .then(onChange)
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : "The sign-off failed.");
      });
  };

  return (
    <form className="sign-off" onSubmit={submit}>
      <label>
        Handler
        <select
          value={handlerId}
          onChange={(event) => {
            setHandlerId(event.target.value);
          }}
        >
          <option value="">Choose a handler</option>
          {handlers.map((handler) => (
            <option key={handler.handler_id} value={handler.handler_id}>
              {handler.name}
            </option>
          ))}
        </select>
      </label>
      <button type="submit" disabled={!handlerId}>
        Sign off and pay
      </button>
      {error && (
        <p className="notice" role="alert">
          {error}
        </p>
      )}
    </form>
  );
}

function PaymentLine({ claim, handlers }: Readonly<Omit<Props, "onChange">>) {
  const { decision, payment } = claim;
  const signer = handlers.find((h) => h.handler_id === decision?.signed_off_by);
  return (
    <>
      {signer && decision?.signed_off_at && (
        <p>
          Signed off by {signer.name} on {dateTime(decision.signed_off_at)}
        </p>
      )}
      {payment && (
        <p className="paid">
          Paid {money(payment.amount)} on {dateTime(payment.paid_at)}
        </p>
      )}
      {!payment && claim.status === "waiting_for_sign_off" && (
        <p>The payment waits for a handler's sign-off.</p>
      )}
      {!payment &&
        claim.status === "decided" &&
        decision?.outcome === "approve" && <p>Not paid</p>}
    </>
  );
}

/** The agent's decision and reasons, with the sign-off a large payout needs. */
export function DecisionPanel(props: Readonly<Props>) {
  const { decision } = props.claim;

  if (!decision) {
    return (
      <section className="panel" aria-label="The agent's decision">
        <h2>The agent's decision</h2>
        <p className="muted">The agent hasn't decided this claim yet.</p>
      </section>
    );
  }

  return (
    <section className="panel" aria-label="The agent's decision">
      <h2>The agent's decision</h2>
      <p className="outcome">
        <span className={`chip ${decision.outcome}`}>
          {OUTCOME_LABELS[decision.outcome]}
        </span>
        <span className="mono payout">{money(decision.payout)}</span>
      </p>
      <p className="reasons">{decision.reasons}</p>
      <p className="muted">
        {decision.policy_section} · decided {dateTime(decision.decided_at)}
      </p>
      <PaymentLine claim={props.claim} handlers={props.handlers} />
      {props.claim.status === "waiting_for_sign_off" && <SignOff {...props} />}
    </section>
  );
}
