"""Cost and latency tracker for LLM API calls.

Wraps every API call to capture tokens, latency, and computed cost.
Emits structured JSON logs compatible with CloudWatch Insights.
"""

import json
import logging
from dataclasses import dataclass, field

logger = logging.getLogger("rootcause.cost")

PRICING = {
    "gemini-2.0-flash": {"input": 0.0, "output": 0.0},
    "gemini-2.5-flash": {"input": 0.0, "output": 0.0},
    "gemini-3.5-flash": {"input": 0.0, "output": 0.0},
}


@dataclass
class CostTracker:
    """Accumulates cost and latency across an agent loop invocation."""

    entries: list[dict] = field(default_factory=list)

    @property
    def total_cost_usd(self) -> float:
        return sum(e["cost_usd"] for e in self.entries)

    @property
    def total_latency_ms(self) -> float:
        return sum(e["latency_ms"] for e in self.entries)

    def record(self, model: str, usage: dict, latency_ms: float):
        prices = PRICING.get(model, {"input": 0.0, "output": 0.0})
        cost = (
            usage.get("input_tokens", 0) * prices["input"]
            + usage.get("output_tokens", 0) * prices["output"]
        )
        entry = {
            "model": model,
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "latency_ms": round(latency_ms, 1),
            "cost_usd": round(cost, 6),
        }
        self.entries.append(entry)
        logger.info(json.dumps(entry))

    def summary(self) -> dict:
        return {
            "api_calls": len(self.entries),
            "total_input_tokens": sum(e["input_tokens"] for e in self.entries),
            "total_output_tokens": sum(e["output_tokens"] for e in self.entries),
            "total_latency_ms": round(self.total_latency_ms, 1),
            "total_cost_usd": round(self.total_cost_usd, 6),
        }
