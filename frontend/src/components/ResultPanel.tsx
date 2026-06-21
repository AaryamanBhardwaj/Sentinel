import type { Diagnosis } from "../lib/api";

interface Props {
  diagnosis: Diagnosis | null;
  error: string | null;
  isLoading: boolean;
}

const CONFIDENCE_COLORS: Record<string, string> = {
  high: "#22c55e",
  medium: "#eab308",
  low: "#ef4444",
};

export function ResultPanel({ diagnosis, error, isLoading }: Props) {
  if (isLoading) {
    return (
      <div className="result-panel loading">
        <div className="spinner" />
        <p>Analyzing... this typically takes 3-8 seconds.</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="result-panel error">
        <h3>Error</h3>
        <p>{error}</p>
      </div>
    );
  }

  if (!diagnosis) {
    return (
      <div className="result-panel empty">
        <p>Paste a stack trace or error log above and click <strong>Analyze</strong>.</p>
      </div>
    );
  }

  return (
    <div className="result-panel">
      <div className="result-header">
        <span
          className="confidence-badge"
          style={{ backgroundColor: CONFIDENCE_COLORS[diagnosis.confidence] }}
        >
          {diagnosis.confidence}
        </span>
        <span className="category-badge">{diagnosis.category}</span>
      </div>

      <section>
        <h3>Root Cause</h3>
        <p className="root-cause">{diagnosis.root_cause}</p>
      </section>

      <section>
        <h3>Explanation</h3>
        <p>{diagnosis.explanation}</p>
      </section>

      <section>
        <h3>Suggested Fix</h3>
        <p className="fix">{diagnosis.fix}</p>
      </section>

      {diagnosis.references.length > 0 && (
        <section>
          <h3>References</h3>
          <ul className="references">
            {diagnosis.references.map((ref, i) => (
              <li key={i}><code>{ref}</code></li>
            ))}
          </ul>
        </section>
      )}

      {diagnosis._meta && <MetaPanel meta={diagnosis._meta} />}
    </div>
  );
}

function MetaPanel({ meta }: { meta: NonNullable<Diagnosis["_meta"]> }) {
  return (
    <details className="meta-panel">
      <summary>Cost &amp; Latency</summary>
      <div className="meta-grid">
        <div>
          <span className="meta-label">API Calls</span>
          <span className="meta-value">{meta.api_calls}</span>
        </div>
        <div>
          <span className="meta-label">Tool Calls</span>
          <span className="meta-value">{meta.tool_calls_made}</span>
        </div>
        <div>
          <span className="meta-label">Tokens</span>
          <span className="meta-value">
            {meta.total_input_tokens} in / {meta.total_output_tokens} out
          </span>
        </div>
        <div>
          <span className="meta-label">Latency</span>
          <span className="meta-value">{(meta.total_latency_ms / 1000).toFixed(1)}s</span>
        </div>
        <div>
          <span className="meta-label">Cost</span>
          <span className="meta-value">${meta.total_cost_usd.toFixed(4)}</span>
        </div>
      </div>
    </details>
  );
}
