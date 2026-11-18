import type { Step } from "./api";
import { dateTime } from "./format";
import { usePolling } from "./usePolling";

function pretty(content: string): string {
  try {
    return JSON.stringify(JSON.parse(content), null, 2);
  } catch {
    return content;
  }
}

function StepBody({ step }: Readonly<{ step: Step }>) {
  if (step.kind === "tool_result") {
    return (
      <details>
        <summary>Result</summary>
        <pre>{pretty(step.content)}</pre>
      </details>
    );
  }
  if (step.kind === "tool_call") {
    return <p className="mono call">{step.content}</p>;
  }
  return <p>{step.content}</p>;
}

const KIND_LABELS: Record<Step["kind"], string> = {
  tool_call: "Calls a tool",
  tool_result: "Gets a reply",
  message: "Says",
};

/** The agent's work on a claim, step by step, as it happens. */
export function Steps({ claimId }: Readonly<{ claimId: string }>) {
  const { data: steps } = usePolling<Step[]>(`/api/claims/${claimId}/steps`);

  return (
    <section className="panel" aria-label="The agent's steps">
      <h2>The agent's steps</h2>
      {steps?.length === 0 && <p className="muted">No steps yet.</p>}
      <ol className="steps">
        {steps?.map((step) => (
          <li key={step.step_id} className={step.kind}>
            <span className="muted step-label">
              {KIND_LABELS[step.kind]} · {dateTime(step.created_at)}
            </span>
            <StepBody step={step} />
          </li>
        ))}
      </ol>
    </section>
  );
}
