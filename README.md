# RootCause

AI SRE agent that analyzes logs and stack traces, identifies root causes, and suggests fixes.

Built with Gemini 3.5 Flash (function calling), RAG over a precomputed error-pattern corpus, and a React frontend — fully hosted on AWS.

## Architecture

```
User → CloudFront (CDN) → S3 (static frontend)
                        → API Gateway → Lambda (Python backend) → Gemini API
                                              ↕
                                    Error-pattern KB (RAG)
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full design document.

## AWS Infrastructure

All infrastructure is defined as code using **Terraform** (`infra/` directory). A single `terraform apply` creates everything; `terraform destroy` tears it all down.

### Services Used

| AWS Service | What it does | Why it's used |
|-------------|-------------|---------------|
| **S3** | Stores the built React frontend (HTML, CSS, JS) as static files | Cheap, serverless static file hosting — no web server needed |
| **CloudFront** | CDN that sits in front of S3 and API Gateway | Serves the frontend globally with low latency, and proxies `/analyze` and `/health` requests to the API — so the frontend makes same-origin requests with no CORS issues |
| **API Gateway (HTTP API v2)** | Receives HTTP requests and routes them to Lambda | Lightweight, serverless HTTP endpoint — no server to manage, scales to zero |
| **Lambda** | Runs the Python backend (FastAPI wrapped with Mangum) | Serverless compute — only runs when a request comes in, no idle cost |
| **CloudWatch** | Stores Lambda and API Gateway logs | Built-in structured logging for debugging and monitoring |
| **IAM** | Least-privilege role for Lambda to write logs | Security — Lambda can only write to its own CloudWatch log group |

### How Terraform Manages It

```
infra/
├── main.tf        # All resource definitions (Lambda, API GW, S3, CloudFront, IAM)
├── variables.tf   # Input variables (API key, region, memory, timeout)
└── outputs.tf     # Output values (API URL, CloudFront URL, bucket name)
```

Terraform tracks the state of all resources. When you run `terraform apply`:
1. It compares desired state (your `.tf` files) with actual state (what exists in AWS)
2. It creates/updates/deletes only what changed
3. It outputs the live URLs

This means the entire infrastructure is reproducible — anyone with an AWS account can deploy their own copy.

### Request Flow (Production)

```
1. User opens https://d2r49pwqfms6ra.cloudfront.net
2. CloudFront serves index.html + JS/CSS from S3
3. User pastes a stack trace and clicks Analyze
4. Browser sends POST /analyze to CloudFront (same domain)
5. CloudFront forwards /analyze to API Gateway
6. API Gateway invokes Lambda
7. Lambda runs the agent loop:
   a. Gemini analyzes the input
   b. Gemini may call search_error_patterns (function calling)
   c. RAG layer searches the TF-IDF embedding matrix for matching patterns
   d. Gemini synthesizes root cause + fix using the retrieved patterns
8. Lambda returns structured JSON response
9. Frontend renders the diagnosis
```

## Prerequisites

- **Python 3.9+** with pip
- **Node.js 18+** with npm
- **Gemini API key** (free) — get one at https://aistudio.google.com/apikey

## Getting Started (Local Development)

### 1. Clone the repo

```bash
git clone https://github.com/AaryamanBhardwaj/Sentinel.git
cd Sentinel
```

### 2. Set up the backend

```bash
# Install Python dependencies
pip3 install -r backend/requirements.txt

# Build the RAG corpus embeddings (one-time setup)
python3 -m backend.rag.embed
```

### 3. Set up the frontend

```bash
cd frontend
npm install
cd ..
```

### 4. Get your Gemini API key

1. Go to https://aistudio.google.com/apikey
2. Click **Create API key**
3. Copy the key

### 5. Run the app

You need two terminals:

**Terminal 1 — Backend** (from the project root):
```bash
GEMINI_API_KEY=your-key-here python3 -m uvicorn backend.handler:app --reload --port 8000
```

**Terminal 2 — Frontend** (from the project root):
```bash
cd frontend && npm run dev
```

Open http://localhost:3000 in your browser. Paste a stack trace or error log and click **Analyze**.

### Example input to try

```
Exception in thread "main" java.lang.OutOfMemoryError: Java heap space
    at com.example.DataProcessor.loadAll(DataProcessor.java:142)
    at com.example.Main.main(Main.java:28)
Memory usage climbed from 512MB to 1.8GB over 30 minutes before crash
```

## Project Structure

```
Sentinel/
├── backend/
│   ├── agent/          # Agent loop, prompts, tool definitions
│   │   ├── loop.py     # ReAct agent loop with Gemini function calling
│   │   ├── prompts.py  # System prompt with SRE domain knowledge
│   │   ├── tools.py    # search_error_patterns tool definition
│   │   └── cli.py      # CLI test harness
│   ├── rag/            # Embedding pipeline + cosine similarity search
│   │   ├── embed.py    # Offline: build TF-IDF embeddings
│   │   └── search.py   # Runtime: cosine similarity search
│   ├── eval/           # Eval harness with golden test cases
│   │   ├── cases.json  # 10 golden test cases
│   │   ├── run.py      # CLI eval runner
│   │   └── scoring.py  # Keyword + LLM-as-judge scoring
│   ├── logging/        # Cost and latency tracker
│   ├── handler.py      # FastAPI app + Lambda entry point
│   └── models.py       # Pydantic request/response models
├── frontend/           # React + Vite + TypeScript
│   └── src/
│       ├── App.tsx
│       ├── components/ # InputPanel, ResultPanel, HistorySidebar
│       ├── hooks/      # useHistory (localStorage)
│       └── lib/        # API client
├── corpus/             # Error patterns + precomputed embeddings
│   └── patterns.json   # 20 SRE error patterns
├── infra/              # Terraform (Lambda, API Gateway, S3, CloudFront, IAM)
│   ├── main.tf         # All AWS resource definitions
│   ├── variables.tf    # Input variables
│   └── outputs.tf      # Output URLs and resource names
└── scripts/            # Package and deploy scripts
    ├── package-lambda.sh  # Bundles Python code + deps into lambda.zip
    └── deploy.sh          # Full deploy: package → terraform → build → upload
```

## Key Components

### Agent Loop
ReAct-style reasoning with a single tool (`search_error_patterns`). Capped at 3 tool calls per request. Every API call is wrapped with cost and latency tracking.

### RAG
Precomputed TF-IDF embeddings over 20 error patterns. No vector database — cosine similarity over a numpy matrix, sub-millisecond search. Swappable to Voyage AI embeddings for semantic search.

### Eval Harness
10 golden test cases (easy/medium/hard). Two scoring modes:
- **Keyword**: deterministic, fast, CI-friendly
- **LLM-as-judge**: Gemini grades accuracy, completeness, actionability (1-5)

```bash
# Run evals
GEMINI_API_KEY=your-key python3 -m backend.eval.run --mode keyword
GEMINI_API_KEY=your-key python3 -m backend.eval.run --mode both
GEMINI_API_KEY=your-key python3 -m backend.eval.run --cases eval_001,eval_003
```

### CLI Test (no frontend needed)

```bash
GEMINI_API_KEY=your-key python3 -m backend.agent.cli
```

## Deploy Your Own Copy

```bash
# 1. Install prerequisites
brew install awscli hashicorp/tap/terraform
aws configure  # enter your AWS access key, secret, region: us-east-1

# 2. Deploy everything to AWS
GEMINI_API_KEY=your-key ./scripts/deploy.sh

# 3. Tear down all AWS resources when done
cd infra && terraform destroy -var="gemini_api_key=$GEMINI_API_KEY"
```

## Cost

Everything runs within free tier limits:

| Component | Free tier limit | This project's usage |
|-----------|----------------|---------------------|
| Gemini 3.5 Flash | Free forever | ~30 requests/day max |
| Lambda | 1M requests + 400K GB-sec/month | Minimal |
| API Gateway | 1M requests/month | Minimal |
| S3 | 5 GB storage | ~64 MB |
| CloudFront | 1 TB transfer + 10M requests/month (always free) | Minimal |
| CloudWatch | 5 GB logs/month | Few KB |

## License

This project is proprietary. You may view the source code, but copying, modifying, or distributing it is not permitted. See [LICENSE](LICENSE) for details.

## Tech Stack

- **LLM**: Gemini 3.5 Flash via Google AI API (function calling)
- **Backend**: Python, FastAPI, Mangum
- **Frontend**: React, Vite, TypeScript
- **RAG**: scikit-learn TF-IDF, numpy, cosine similarity
- **Infra**: Terraform, AWS Lambda, API Gateway, S3, CloudFront
- **Deploy**: Fully hosted on AWS
