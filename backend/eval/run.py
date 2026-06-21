"""Eval harness — run golden test cases against the agent.

Usage:
    python3 -m backend.eval.run                          # keyword scoring (no API needed for scoring)
    python3 -m backend.eval.run --mode judge              # LLM-as-judge scoring
    python3 -m backend.eval.run --mode both               # both modes
    python3 -m backend.eval.run --cases eval_001,eval_003 # run specific cases
    python3 -m backend.eval.run --dry-run                 # show cases without running

Results are written to backend/eval/results/ as JSON lines (one file per run).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from backend.agent.loop import analyze
from backend.eval.scoring import score_keyword, score_judge
from backend.logging.tracker import CostTracker

CASES_PATH = Path(__file__).parent / "cases.json"
RESULTS_DIR = Path(__file__).parent / "results"


def load_cases(filter_ids: list[str] | None = None) -> list[dict]:
    with open(CASES_PATH) as f:
        cases = json.load(f)
    if filter_ids:
        cases = [c for c in cases if c["id"] in filter_ids]
    return cases


async def run_case(case: dict, mode: str) -> dict:
    """Run a single eval case: agent diagnosis + scoring."""
    tracker = CostTracker()

    t0 = time.perf_counter()
    try:
        diagnosis = await analyze(case["input"], tracker)
        agent_error = None
    except Exception as e:
        diagnosis = {
            "root_cause": f"Agent error: {e}",
            "confidence": "low",
            "category": "other",
            "explanation": str(e),
            "fix": "",
            "references": [],
        }
        agent_error = str(e)
    wall_time_ms = (time.perf_counter() - t0) * 1000

    result = {
        "case_id": case["id"],
        "difficulty": case["difficulty"],
        "diagnosis": diagnosis,
        "agent_meta": tracker.summary(),
        "wall_time_ms": round(wall_time_ms, 1),
    }

    if agent_error:
        result["agent_error"] = agent_error

    if mode in ("keyword", "both"):
        result["keyword_score"] = score_keyword(case, diagnosis).to_dict()

    if mode in ("judge", "both"):
        result["judge_score"] = score_judge(case, diagnosis).to_dict()

    return result


async def run_eval(cases: list[dict], mode: str) -> dict:
    """Run all cases sequentially and aggregate results."""
    results = []
    for i, case in enumerate(cases):
        print(f"  [{i+1}/{len(cases)}] {case['id']} ({case['difficulty']})...", end=" ", flush=True)
        result = await run_case(case, mode)

        status = _result_status(result, mode)
        cost = result["agent_meta"]["total_cost_usd"]
        print(f"{status}  (${cost:.4f}, {result['wall_time_ms']:.0f}ms)")

        results.append(result)

    summary = _build_summary(results, mode)
    return {"summary": summary, "results": results}


def _result_status(result: dict, mode: str) -> str:
    parts = []
    if "keyword_score" in result:
        parts.append("KW:" + ("PASS" if result["keyword_score"]["passed"] else "FAIL"))
    if "judge_score" in result:
        avg = result["judge_score"]["average"]
        parts.append(f"JUDGE:{avg:.1f}/5")
    return " | ".join(parts) if parts else "DONE"


def _build_summary(results: list[dict], mode: str) -> dict:
    total = len(results)
    total_agent_cost = sum(r["agent_meta"]["total_cost_usd"] for r in results)
    total_wall_time = sum(r["wall_time_ms"] for r in results)

    summary = {
        "total_cases": total,
        "mode": mode,
        "total_agent_cost_usd": round(total_agent_cost, 4),
        "total_wall_time_ms": round(total_wall_time, 1),
        "avg_wall_time_ms": round(total_wall_time / total, 1) if total else 0,
    }

    if mode in ("keyword", "both"):
        kw_pass = sum(1 for r in results if r.get("keyword_score", {}).get("passed"))
        summary["keyword_pass_rate"] = f"{kw_pass}/{total} ({100*kw_pass/total:.0f}%)" if total else "N/A"

    if mode in ("judge", "both"):
        judge_results = [r for r in results if "judge_score" in r]
        if judge_results:
            avg_acc = sum(r["judge_score"]["accuracy"] for r in judge_results) / len(judge_results)
            avg_comp = sum(r["judge_score"]["completeness"] for r in judge_results) / len(judge_results)
            avg_act = sum(r["judge_score"]["actionability"] for r in judge_results) / len(judge_results)
            judge_cost = sum(r["judge_score"]["judge_cost_usd"] for r in judge_results)
            summary["judge_avg_accuracy"] = round(avg_acc, 2)
            summary["judge_avg_completeness"] = round(avg_comp, 2)
            summary["judge_avg_actionability"] = round(avg_act, 2)
            summary["judge_total_cost_usd"] = round(judge_cost, 4)

    by_difficulty = {}
    for r in results:
        d = r["difficulty"]
        if d not in by_difficulty:
            by_difficulty[d] = {"total": 0, "kw_pass": 0}
        by_difficulty[d]["total"] += 1
        if r.get("keyword_score", {}).get("passed"):
            by_difficulty[d]["kw_pass"] += 1
    summary["by_difficulty"] = by_difficulty

    return summary


def save_results(report: dict) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = RESULTS_DIR / f"eval_{ts}.json"
    with open(path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    return path


def main():
    parser = argparse.ArgumentParser(description="Run RootCause eval harness")
    parser.add_argument("--mode", default="keyword", choices=["keyword", "judge", "both"])
    parser.add_argument("--cases", type=str, help="Comma-separated case IDs to run")
    parser.add_argument("--dry-run", action="store_true", help="List cases without running")
    args = parser.parse_args()

    filter_ids = args.cases.split(",") if args.cases else None
    cases = load_cases(filter_ids)

    if not cases:
        print("No cases found.")
        sys.exit(1)

    if args.dry_run:
        print(f"Found {len(cases)} cases:")
        for c in cases:
            print(f"  {c['id']} [{c['difficulty']}] — {c['input'][:60]}...")
        sys.exit(0)

    print(f"Running {len(cases)} eval cases (mode={args.mode})")
    print("=" * 60)

    report = asyncio.run(run_eval(cases, args.mode))

    path = save_results(report)
    print("=" * 60)
    print(f"\nSummary:")
    print(json.dumps(report["summary"], indent=2))
    print(f"\nResults saved to: {path}")


if __name__ == "__main__":
    main()
