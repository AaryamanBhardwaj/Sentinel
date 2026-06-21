# RootCause — Architecture

AI SRE agent that analyzes logs and stack traces, identifies root causes,
and suggests fixes. Built as a portfolio project to demonstrate agent design,
RAG without infrastructure overhead, and production-grade observability.

## System Overview

```
┌──────────────┐     HTTPS      ┌────────────────────┐     Gemini API
│  React SPA   │ ──────────────>│  API Gateway        │ ──────────────────>
│(S3+CloudFront)│               │  + Lambda (Python)  │
└──────────────┘                └────────┬───────────-┘
                                         │
                                    Agent Loop
                                    ┌────┴────┐
                                    │ Reason   │──> functionCall: search_kb
                                    │ Search   │<── top-k error patterns
                                    │ Synthesize│──> root cause + fix
                                    └─────────-┘
                                         │
                                    ┌────┴────┐
                                    │ Corpus   │  precomputed embeddings
                                    │ (.npy)   │  bundled in Lambda zip
                                    └─────────-┘
```

## Component Design

### 1. Agent Loop (`backend/agent/`)

**Pattern: ReAct-style with constrained tool use.**

The agent receives a log snippet or stack trace and runs a multi-step loop:

1. **Analyze** — Gemini reads the input and decides whether it can diagnose
   directly or needs more context from the error-pattern knowledge base.
2. **Search** (function call) — If needed, the agent calls `search_error_patterns`
   with a query string. This is the only tool available, keeping the agent
   focused and predictable.
3. **Synthesize** — Using retrieved patterns (if any) plus its own knowledge,
   the agent returns a structured response: root cause, confidence level,
   suggested fix, and relevant error pattern references.

The loop is capped at **max 3 tool calls** per request to bound cost and
latency. In practice, most diagnoses need 0–1 searches.

**Key decisions:**
- Single tool, not multiple: keeps the agent reliable and easy to eval.
  A "run SQL" or "check metrics" tool would be impressive but hard to
  sandbox in a portfolio project.
- Structured output via Gemini's function calling, not free-text parsing.
- System prompt includes SRE domain knowledge and output format instructions.

### 2. RAG Layer (`backend/rag/`)

**Pattern: Precomputed embeddings + cosine similarity at query time.**

Why no vector DB:
- The corpus is small (~20 error patterns). A vector DB adds cost,
  infra complexity, and a cold-start penalty — all for a problem that
  fits in memory.
- Embeddings are precomputed offline via scikit-learn TF-IDF and stored
  as a `.npy` file alongside a JSON manifest of the patterns.
- At query time: embed the query, compute cosine similarity against the
  matrix, return top-k. Total added latency: ~50ms.

**Corpus format** (`corpus/`):
```json
{
  "id": "OOM_JAVA_HEAP",
  "title": "Java OutOfMemoryError: Java heap space",
  "pattern": "java.lang.OutOfMemoryError: Java heap space",
  "root_cause": "JVM heap exhausted — usually a memory leak or undersized -Xmx",
  "category": "memory",
  "fix": "Profile with jmap/MAT, increase -Xmx, or fix the leak",
  "tags": ["java", "jvm", "memory", "oom"]
}
```

**Tradeoff to defend:** This doesn't scale to 100K patterns. That's fine —
the goal is to show you understand when NOT to over-engineer. If the corpus
grew, you'd swap in pgvector or Pinecone with zero changes to the agent
loop (the tool interface stays the same).

### 3. Eval Harness (`backend/eval/`)

**Pattern: Golden-set evals with LLM-as-judge.**

Each test case is a JSON object:
- `input`: a realistic log snippet or stack trace
- `expected_category`: e.g., "memory", "network", "config"
- `expected_keywords`: terms the root cause must mention
- `difficulty`: "easy" | "medium" | "hard"

Two scoring modes:
1. **Keyword match** — fast, deterministic, good for CI.
   Checks that `expected_keywords` appear in the agent's response.
2. **LLM-as-judge** — uses a second Gemini call to grade the response
   on accuracy, completeness, and actionability (1–5 scale).

Results are logged as JSON lines with cost and latency per case, making
it easy to track regressions and compare prompt versions.

### 4. Cost & Latency Logging (`backend/logging/`)

Every Gemini API call is wrapped to capture:
- `input_tokens`, `output_tokens`
- `latency_ms` (wall clock, not TTFB)
- `model`
- Computed `cost_usd` (currently $0 on Gemini free tier)

Logs go to **CloudWatch** (structured JSON) via Lambda's built-in
integration — no extra infra. A simple CloudWatch Insights query gives
you a cost dashboard.

**Why not a third-party observability tool:** For a portfolio project,
CloudWatch is free-tier-friendly and demonstrates you can build
observability without buying it. In production you'd likely use Datadog
or Honeycomb.

### 5. Frontend (`frontend/`)

Minimal React app (Vite + TypeScript):
- Paste-in textarea for logs/stack traces
- "Analyze" button → POST to API Gateway
- Response display (root cause, confidence, fix, references)
- History sidebar (localStorage, no auth)

Deployed to AWS (S3 + CloudFront). No auth — it's a demo. Rate limiting
is handled at the application level (in-memory per-IP limiter).

### 6. Infrastructure (`infra/`)

Terraform manages:
- Lambda function (Python deps uploaded to S3)
- API Gateway (HTTP API v2)
- S3 bucket + CloudFront distribution (frontend hosting)
- IAM roles (least-privilege)
- CloudWatch log groups

CloudFront proxies `/analyze` and `/health` to the API Gateway origin,
so the frontend makes same-origin requests with no CORS issues.

Designed to be created and torn down with `terraform apply` / `destroy`.

## Request Flow

```
1. User pastes stack trace in frontend
2. Frontend POST /analyze { "input": "..." }
3. API Gateway → Lambda
4. Lambda: agent loop starts
   a. Gemini analyzes input (system instruction + user message)
   b. Gemini may call search_error_patterns via function calling
   c. RAG layer embeds query, searches .npy matrix, returns top-3
   d. Gemini synthesizes root cause + fix
5. Lambda returns structured JSON
6. Frontend renders result
7. Cost/latency logged to CloudWatch
```

## Build Order

1. ~~Scaffold~~
2. ~~Agent loop~~ — core reasoning with Gemini function calling
3. ~~RAG layer~~ — corpus + TF-IDF embedding pipeline + search
4. ~~Eval harness~~ — golden test cases + scoring
5. ~~Backend integration~~ — Lambda handler, API contract
6. ~~Frontend~~ — UI + API integration
7. ~~Infra~~ — Terraform for Lambda + API Gateway
8. ~~Polish~~ — error handling, rate limiting, README

## Cost Estimate (Demo Usage)

| Component | Monthly cost |
|-----------|-------------|
| Gemini 2.5 Flash (~1000 requests) | Free tier |
| Lambda (512MB, <60s timeout) | Free tier |
| API Gateway (1000 requests) | Free tier |
| CloudWatch Logs | Free tier |
| S3 + CloudFront | AWS free tier |
| **Total** | **$0** |
