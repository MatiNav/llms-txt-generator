# llms.txt Generator (Challenge V3)

Implementation for the **Automated `llms.txt` Generator** challenge described in:

- `LLMs.txt-Generator-Version3.md`

This system crawls websites, generates `llms.txt` artifacts, and keeps sites refreshable through a distributed AWS pipeline.

## Demo / Walkthrough

- Loom video (challenge explanation): https://www.loom.com/share/16e4c0b2033844c89718de3d43bd5457

---

## What this repo contains

- **Frontend** (`app/frontend`): React + Vite UI
- **API** (`app/server`): FastAPI + SSE endpoints
- **Workers** (`app/handlers`):
  - Orchestrator (ECS Fargate)
  - HTTP fetcher (Lambda)
  - SPA/Playwright fetcher (ECS Fargate)
  - Processing (Lambda)
  - LLM generator (Lambda)
  - Site refresher cron handler (Lambda)
- **Shared package** (`app/shared`): models, DB, pipeline types/utilities
- **Infrastructure** (`infra`): AWS CDK stack for runtime + data + hosting

---

## Architecture (high level)

- **Frontend**: CloudFront + S3
- **API**: App Runner
- **Messaging**: SNS + SQS queues (discoverable/fetch/processing/llm)
- **Compute**: ECS Fargate + Lambda
- **Data**: RDS PostgreSQL + S3 (raw html + generated outputs)
- **External**: OpenAI API for enrichment phase

---

## Prerequisites

### Local tooling

- Python **3.12+**
- [uv](https://docs.astral.sh/uv/)
- Node.js **20+** and npm
- Docker

### AWS tooling

- AWS account + credentials configured locally
- AWS CDK v2 CLI (`cdk --version`)
- Route53 hosted zone for your root domain (if deploying custom domains)

---

## Local setup

Run all commands from repo root: `llms-txt-generator/`.

### 1) Start local Postgres

```bash
docker compose -f docker-compose.local.yml up -d
```

### 2) Create Python environment and install packages

```bash
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e ./app/shared
uv pip install -e ./app/server
```

### 3) Run DB migrations

```bash
DATABASE_URL="postgresql+asyncpg://llmstxt:llmstxt@localhost:5432/llmstxt" \
alembic -c app/shared/migrations/alembic.ini upgrade head
```

### 4) Run API server

Required environment variables:

```bash
export DATABASE_URL="postgresql+asyncpg://llmstxt:llmstxt@localhost:5432/llmstxt"
export AWS_REGION="us-east-1"
export DISCOVERABLE_TOPIC_ARN="arn:aws:sns:us-east-1:123456789012/llmstxt-discoverable-events"
export FRONTEND_ORIGIN="http://localhost:5173"
```

Start server:

```bash
uvicorn server.main:app --app-dir app/server --reload --port 8000
```

> Note: `POST /api/generate` publishes to SNS. For full end-to-end local behavior you need valid AWS credentials and real AWS resources.

### 5) Run frontend locally

```bash
cd app/frontend
npm install
cp .env.example .env
npm run dev
```

Frontend default: `http://localhost:5173`.

---

## API quick smoke checks

```bash
curl http://localhost:8000/health
```

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "content-type: application/json" \
  -d '{"url":"https://example.com","render_mode":"http"}'
```

Run status and download endpoints:

- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/events` (SSE)
- `GET /api/runs/{run_id}/downloads`

---

## Deploy to AWS (CDK)

### 1) Configure deployment values

Before deploy, review and adjust domain values in:

- `infra/stacks/llm_txt_generator_stack.py`

Current values are hardcoded (`root_domain_name`, frontend/api subdomains), so make sure they match your hosted zone.

### 2) Export required deploy env vars

`OPENAI_API_KEY` is required at synth/deploy time by the stack.

```bash
export OPENAI_API_KEY="<your-openai-api-key>"
export OPENAI_MODEL_NAME="gpt-4.1-mini" # optional override
```

### 3) Build frontend artifacts (used by infra deploy)

```bash
cd app/frontend
npm install
npm run build
cd ../..
```

### 4) Install infra deps and bootstrap

```bash
cd infra
uv venv --python 3.12
source .venv/bin/activate
uv pip install -r requirements.txt
cdk bootstrap aws://<ACCOUNT_ID>/<REGION>
```

### 5) Synthesize and deploy

```bash
cd infra
cdk synth
cdk deploy LlmTxtGeneratorStack \
  -c account=<ACCOUNT_ID> \
  -c region=<REGION> \
  --require-approval never
```

After deploy, use stack outputs for:

- Frontend public URL
- API public URL
- Queue and bucket names
- DB secret ARN

---

## Operational notes (challenge mode)

- Infrastructure favors challenge simplicity over production hardening.
- Networking and DB posture are challenge-oriented and should be tightened for production.

---

## Project structure

```text
app/
  frontend/     React + Vite app
  server/       FastAPI API and SSE endpoints
  handlers/     Lambda/ECS worker handlers
  shared/       Shared models, DB, queue and pipeline utilities
infra/
  components/   CDK constructs for each runtime/resource
  stacks/       Main stack composition + outputs
```
