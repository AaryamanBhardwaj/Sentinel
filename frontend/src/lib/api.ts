const API_URL = import.meta.env.VITE_API_URL || "";

export interface Diagnosis {
  root_cause: string;
  confidence: "high" | "medium" | "low";
  category: string;
  explanation: string;
  fix: string;
  references: string[];
  _meta?: {
    api_calls: number;
    total_input_tokens: number;
    total_output_tokens: number;
    total_latency_ms: number;
    total_cost_usd: number;
    tool_calls_made: number;
  };
}

export interface AnalyzeError {
  detail: string;
}

export async function analyze(input: string): Promise<Diagnosis> {
  const res = await fetch(`${API_URL}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ input }),
  });

  if (!res.ok) {
    const err: AnalyzeError = await res.json().catch(() => ({
      detail: `HTTP ${res.status}`,
    }));
    if (res.status === 429) {
      throw new Error("Rate limit exceeded. Please wait a moment and try again.");
    }
    if (res.status === 503) {
      throw new Error("AI service is temporarily unavailable. Please try again later.");
    }
    throw new Error(err.detail);
  }

  return res.json();
}
