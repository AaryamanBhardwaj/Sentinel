"""Tool definitions for the RootCause agent.

Single tool: search_error_patterns. Intentionally constrained —
one well-defined tool is more reliable than many loose ones.
"""

import json

TOOLS = [
    {
        "name": "search_error_patterns",
        "description": (
            "Search the error-pattern knowledge base for patterns matching "
            "the query. Returns the top-k most similar error patterns with "
            "their root causes and suggested fixes. Use a concise query — "
            "the core error message or a few keywords, not the full log."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query — an error message, symptom, or keyword.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results to return (default 3).",
                    "default": 3,
                },
            },
            "required": ["query"],
        },
    }
]


async def handle_tool_call(name: str, tool_input: dict) -> str:
    """Dispatch a tool call to the appropriate handler.

    Returns a JSON string (tool results are always stringified for the API).
    """
    if name != "search_error_patterns":
        return json.dumps({"error": f"Unknown tool: {name}"})

    try:
        from backend.rag.search import search
        results = await search(
            query=tool_input["query"],
            top_k=tool_input.get("top_k", 3),
        )
        return json.dumps(results)
    except (NotImplementedError, FileNotFoundError):
        return json.dumps(_mock_search(tool_input["query"], tool_input.get("top_k", 3)))


def _mock_search(query: str, top_k: int) -> list[dict]:
    """Keyword-based fallback used before the real RAG layer is built."""
    import json as _json
    from pathlib import Path

    patterns_path = Path(__file__).resolve().parent.parent.parent / "corpus" / "patterns.json"
    with open(patterns_path) as f:
        patterns = _json.load(f)

    query_lower = query.lower()
    scored = []
    for p in patterns:
        searchable = f"{p['title']} {p['pattern']} {' '.join(p['tags'])}".lower()
        score = sum(1 for word in query_lower.split() if word in searchable)
        if score > 0:
            scored.append((score, p))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {
            "id": p["id"],
            "title": p["title"],
            "root_cause": p["root_cause"],
            "fix": p["fix"],
            "category": p["category"],
            "score": score,
        }
        for score, p in scored[:top_k]
    ]
