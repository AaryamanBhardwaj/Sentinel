"""Scoring functions for the eval harness.

Two modes:
  - keyword: deterministic, fast, good for CI. Checks category match +
    keyword presence in the agent's output.
  - judge: LLM-as-judge via a second Gemini call. Grades on accuracy,
    completeness, and actionability (1-5 each). Slower but catches
    quality issues that keyword matching misses.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

JUDGE_PROMPT = """\
You are an SRE eval judge. You will be given:
1. An error log / stack trace (the INPUT)
2. The expected category and keywords
3. An agent's diagnosis (the RESPONSE)

Grade the response on three dimensions, each 1-5:

- accuracy: Does the root cause correctly identify the problem? (5 = exact match,
  1 = completely wrong)
- completeness: Does the explanation cover all relevant factors visible in the input?
  (5 = thorough, 1 = missing obvious signals)
- actionability: Is the fix specific and implementable? (5 = copy-paste ready,
  1 = vague/generic)

Respond with ONLY this JSON (no markdown):
{
  "accuracy": <int>,
  "completeness": <int>,
  "actionability": <int>,
  "rationale": "<one sentence explaining the grades>"
}
"""


@dataclass
class KeywordScore:
    category_match: bool
    keywords_found: list[str]
    keywords_missing: list[str]
    passed: bool

    def to_dict(self) -> dict:
        return {
            "mode": "keyword",
            "category_match": self.category_match,
            "keywords_found": self.keywords_found,
            "keywords_missing": self.keywords_missing,
            "passed": self.passed,
        }


@dataclass
class JudgeScore:
    accuracy: int
    completeness: int
    actionability: int
    rationale: str
    judge_cost_usd: float
    judge_latency_ms: float

    @property
    def average(self) -> float:
        return (self.accuracy + self.completeness + self.actionability) / 3

    @property
    def passed(self) -> bool:
        return self.average >= 3.0

    def to_dict(self) -> dict:
        return {
            "mode": "judge",
            "accuracy": self.accuracy,
            "completeness": self.completeness,
            "actionability": self.actionability,
            "average": round(self.average, 2),
            "rationale": self.rationale,
            "passed": self.passed,
            "judge_cost_usd": self.judge_cost_usd,
            "judge_latency_ms": self.judge_latency_ms,
        }


def score_keyword(case: dict, diagnosis: dict) -> KeywordScore:
    """Fast deterministic scoring: category match + keyword presence."""
    response_text = json.dumps(diagnosis).lower()

    category_match = diagnosis.get("category", "").lower() == case["expected_category"].lower()

    found = []
    missing = []
    for kw in case["expected_keywords"]:
        if kw.lower() in response_text:
            found.append(kw)
        else:
            missing.append(kw)

    passed = category_match and len(missing) == 0
    return KeywordScore(
        category_match=category_match,
        keywords_found=found,
        keywords_missing=missing,
        passed=passed,
    )


def score_judge(case: dict, diagnosis: dict) -> JudgeScore:
    """LLM-as-judge scoring via a second Gemini call."""
    import os
    import requests as req

    api_key = os.environ.get("GEMINI_API_KEY", "")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"

    user_msg = (
        f"INPUT:\n{case['input']}\n\n"
        f"EXPECTED CATEGORY: {case['expected_category']}\n"
        f"EXPECTED KEYWORDS: {', '.join(case['expected_keywords'])}\n\n"
        f"AGENT RESPONSE:\n{json.dumps(diagnosis, indent=2)}"
    )

    t0 = time.perf_counter()
    resp = req.post(url, json={
        "system_instruction": {"parts": [{"text": JUDGE_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": user_msg}]}],
        "generationConfig": {"maxOutputTokens": 256},
    }, timeout=30)
    latency_ms = (time.perf_counter() - t0) * 1000

    if resp.status_code != 200:
        return JudgeScore(1, 1, 1, f"Judge API error: {resp.status_code}", 0.0, latency_ms)

    data = resp.json()
    text = data["candidates"][0]["content"]["parts"][0].get("text", "").strip()
    if text.startswith("```"):
        first_nl = text.find("\n")
        if first_nl != -1:
            text = text[first_nl + 1:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    try:
        grades = json.loads(text)
    except json.JSONDecodeError:
        grades = {"accuracy": 1, "completeness": 1, "actionability": 1,
                  "rationale": f"Judge returned invalid JSON: {text[:100]}"}

    return JudgeScore(
        accuracy=grades.get("accuracy", 1),
        completeness=grades.get("completeness", 1),
        actionability=grades.get("actionability", 1),
        rationale=grades.get("rationale", ""),
        judge_cost_usd=0.0,
        judge_latency_ms=round(latency_ms, 1),
    )
