import type { Text } from "./api";
import { usePolling } from "./usePolling";

/** The agent's instructions and the policy wording it gets with them, read only. */
export function Instructions() {
  const { data: instructions } = usePolling<Text>("/api/instructions", false);
  const { data: wording } = usePolling<Text>("/api/policy-wording", false);

  return (
    <>
      <h1>The agent's instructions</h1>
      <p className="muted">
        What the UnderCover Agent is told on every claim. They're read only.
      </p>
      <section className="panel" aria-label="Instructions">
        <pre className="document-text">{instructions?.text}</pre>
      </section>
      <details className="panel">
        <summary>The policy wording, which the agent gets after these</summary>
        <pre className="document-text">{wording?.text}</pre>
      </details>
    </>
  );
}
