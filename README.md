# RootCause

AI SRE agent that analyzes logs and stack traces, identifies root causes, and suggests fixes.

**Live Demo**: https://d2r49pwqfms6ra.cloudfront.net

Built with Gemini 2.5 Flash (function calling), RAG over a precomputed error-pattern corpus, and a React frontend — fully hosted on AWS.

## Architecture

```
React SPA (S3 + CloudFront)  →  API Gateway + Lambda (Python)  →  Gemini API
                                            ↕
                                  Error-pattern KB (RAG)
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full design document.

## Prerequisites

- **Python 3.9+** with pip
- **Node.js 18+** with npm
- **Gemini API key** (free) — get one at https://aistudio.google.com/apikey

## Getting Started

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
├── infra/              # Terraform (Lambda, API Gateway, IAM)
└── scripts/            # Package and deploy scripts
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

## Deploy to AWS

```bash
# Prerequisites: AWS CLI + Terraform configured
brew install awscli hashicorp/tap/terraform
aws configure

# Full deploy (packages Lambda, applies Terraform, builds frontend, uploads to S3)
GEMINI_API_KEY=your-key ./scripts/deploy.sh

# Tear down all AWS resources
cd infra && terraform destroy -var="gemini_api_key=$GEMINI_API_KEY"
```

## Cost

| Component | Monthly (demo usage) |
|-----------|---------------------|
| Gemini 2.5 Flash | Free tier |
| Lambda + API Gateway | AWS free tier |
| S3 + CloudFront | AWS free tier |
| CloudWatch | AWS free tier |

## License

This project is proprietary. You may view the source code, but copying, modifying, or distributing it is not permitted. See [LICENSE](LICENSE) for details.

## Tech Stack

- **LLM**: Gemini 2.5 Flash via Google AI API (function calling)
- **Backend**: Python, FastAPI, Mangum
- **Frontend**: React, Vite, TypeScript
- **RAG**: scikit-learn TF-IDF, numpy, cosine similarity
- **Infra**: Terraform, AWS Lambda, API Gateway, S3, CloudFront
- **Deploy**: Fully hosted on AWS
