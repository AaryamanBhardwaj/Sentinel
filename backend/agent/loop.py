"""RootCause agent loop — ReAct-style reasoning with error-pattern KB search."""

from __future__ import annotations

import json
import os
import time
from typing import Optional

import requests

from backend.logging.tracker import CostTracker

MAX_TOOL_CALLS = 3
MODEL = "gemini-2.5-flash"
API_BASE = "https://generativelanguage.googleapis.com/v1beta"

TOOL_DECLARATION = {
    "function_declarations": [{
        "name": "search_error_patterns",
        "description": (
            "Search the error-pattern knowledge base for patterns matching "
            "the query. Returns the top-k most similar error patterns with "
            "their root causes and suggested fixes."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query — an error message, symptom, or keyword.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results to return (default 3).",
                },
            },
            "required": ["query"],
        },
    }]
}


async def analyze(input_text: str, tracker: Optional[CostTracker] = None) -> dict:
    """Run the agent loop on a log snippet / stack trace."""
    from backend.agent.prompts import SYSTEM_PROMPT
    from backend.agent.tools import handle_tool_call

    if tracker is None:
        tracker = CostTracker()

    api_key = os.environ.get("GEMINI_API_KEY", "")
    url = f"{API_BASE}/models/{MODEL}:generateContent?key={api_key}"

    contents = [{"role": "user", "parts": [{"text": input_text}]}]
    tool_calls_made = 0
    max_iterations = MAX_TOOL_CALLS + 2

    for _ in range(max_iterations):
        body = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": contents,
            "tools": [TOOL_DECLARATION],
            "generationConfig": {"maxOutputTokens": 2048},
        }

        t0 = time.perf_counter()
        resp = requests.post(url, json=body, timeout=60)
        latency_ms = (time.perf_counter() - t0) * 1000

        if resp.status_code != 200:
            raise RuntimeError(f"Gemini API error {resp.status_code}: {resp.text[:300]}")

        data = resp.json()
        usage = data.get("usageMetadata", {})
        tracker.record(
            model=MODEL,
            usage={
                "input_tokens": usage.get("promptTokenCount", 0),
                "output_tokens": usage.get("candidatesTokenCount", 0),
            },
            latency_ms=latency_ms,
        )

        candidate = data["candidates"][0]
        parts = candidate["content"]["parts"]

        # Check if there's a function call
        func_call = None
        for part in parts:
            if "functionCall" in part:
                func_call = part["functionCall"]
                break

        if func_call is None:
            break

        # Handle the tool call
        tool_calls_made += 1
        result_str = await handle_tool_call(
            func_call["name"],
            func_call.get("args", {}),
        )

        # Append assistant response + tool result to conversation
        contents.append({"role": "model", "parts": parts})
        contents.append({
            "role": "user",
            "parts": [{
                "functionResponse": {
                    "name": func_call["name"],
                    "response": {"result": json.loads(result_str)},
                }
            }],
        })

        if tool_calls_made >= MAX_TOOL_CALLS:
            contents.append({
                "role": "user",
                "parts": [{"text": "You have reached the maximum number of tool calls. "
                                   "Please provide your final diagnosis now."}],
            })

    # Extract text from the final response
    text = ""
    for part in parts:
        if "text" in part:
            text += part["text"]

    diagnosis = _parse_diagnosis(text)
    diagnosis["_meta"] = {
        **tracker.summary(),
        "tool_calls_made": tool_calls_made,
    }
    return diagnosis


def _parse_diagnosis(text: str) -> dict:
    """Parse the agent's JSON response, handling common formatting issues."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        if first_newline != -1:
            cleaned = cleaned[first_newline + 1:]
        else:
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {
            "root_cause": text,
            "confidence": "low",
            "category": "other",
            "explanation": "Agent returned non-JSON response.",
            "fix": "See root_cause field for raw agent output.",
            "references": [],
            "_parse_error": True,
        }
