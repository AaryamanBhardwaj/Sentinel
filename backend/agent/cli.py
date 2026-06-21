"""Quick CLI to test the agent loop locally.

Usage: python -m backend.agent.cli "paste your stack trace here"
       python -m backend.agent.cli              (uses a built-in example)
"""

import asyncio
import json
import sys

from backend.agent.loop import analyze
from backend.logging.tracker import CostTracker

EXAMPLE_INPUT = """\
Exception in thread "main" java.lang.OutOfMemoryError: Java heap space
    at com.example.service.DataLoader.loadDataset(DataLoader.java:89)
    at com.example.service.AnalyticsEngine.run(AnalyticsEngine.java:42)
    at com.example.Main.main(Main.java:15)

Application logs show memory usage climbing from 512MB to 1.8GB over 30 minutes
before the crash. The JVM was started with -Xmx2g. This started happening after
deploying v2.4.1 which added batch processing for the new analytics pipeline.
"""


async def main():
    input_text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else EXAMPLE_INPUT
    tracker = CostTracker()

    print("=" * 60)
    print("RootCause Agent — Analyzing...")
    print("=" * 60)
    print(f"\nInput:\n{input_text[:200]}{'...' if len(input_text) > 200 else ''}\n")

    result = analyze(input_text, tracker)
    if asyncio.iscoroutine(result):
        result = await result

    print("=" * 60)
    print("Diagnosis:")
    print("=" * 60)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
