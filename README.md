# llms.txt Generator

Distributed pipeline that crawls websites and generates [llms.txt](https://llmstxt.org/) files -- structured metadata that helps LLMs understand site content.

## Architecture

Target architecture for the distributed pipeline on AWS:

- **FastAPI server** (App Runner) -- API + SSE for real-time progress
- **Orchestrator** (ECS Fargate) -- URL dedup, robots.txt, fetch routing
- **HTTP fetcher** (Lambda) -- fast-path page fetching
- **Playwright fetcher** (ECS Fargate) -- JS-rendered page fetching
- **Processing pipeline** (Lambda) -- content extraction and llms.txt generation
- **PostgreSQL** (RDS) -- persistent state for sites, runs, and pages
- **SQS queues** -- decoupled message routing between stages
- **S3** -- HTML artifact and output storage

## Current Status

Implemented now:
- Shared package (`app/shared`) with SQLAlchemy models, async DB layer, and Alembic migrations
- FastAPI server (`app/server`) with startup migrations, structured logging, health endpoint, and `POST /api/generate` coalescing behavior
- Integration/E2E-style tests for generate flow under `app/server/tests/e2e`
- CDK infra scaffold (`infra/`) with:
  - discoverable queue + DLQ
  - App Runner runtime IAM role with `sqs:SendMessage`
  - App Runner runtime stack wiring for server container + env injection (`AWS_REGION`, `DISCOVERABLE_QUEUE_URL`, `DATABASE_URL`)
  - Challenge-mode RDS PostgreSQL in public subnets for full endpoint validation

Still pending:
- Worker runtimes (orchestrator, fetchers, processing)
- Read APIs and SSE stream endpoints
- Full infra rollout and production hardening

## Project Structure

```
app/
  shared/           Shared Python package (models, DB, pipeline)
    shared/
      models/       SQLAlchemy 2.0 models (Site, Run, RunPage, SitePage)
      db/           Async engine, session factory, migration runner
      logging.py    Shared structured JSON logging utility
      queue/        SQS client wrapper
      pipeline/     Pure functions ported from POC (planned)
      storage/      S3 client (planned)
    migrations/     Alembic async migrations
  server/           FastAPI server (implemented: health + generate + coalescing)
  handlers/         Lambda + ECS task handlers (planned)
infra/              CDK infrastructure (implemented baseline + server runtime wiring)
```

## Tech Stack

- Python 3.12
- SQLAlchemy 2.0 (async, declarative `mapped_column` style)
- asyncpg (PostgreSQL async driver)
- Alembic (async migrations)
- FastAPI + Pydantic v2
- aioboto3 (async AWS SDK)
- AWS CDK (Python)

## Local Development

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (package manager)
- Docker

### Database

Start the local PostgreSQL instance:

```bash
docker compose -f docker-compose.local.yml up -d
```

Create a `.env.local` file:

```
DATABASE_URL=postgresql+asyncpg://llmstxt:llmstxt@localhost:5432/llmstxt
```

### Install shared package

```bash
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e ./app/shared
```

### Run API server

Install server package:

```bash
uv pip install -e ./app/server
```

Set required env vars:

```bash
export DATABASE_URL="postgresql+asyncpg://llmstxt:llmstxt@localhost:5432/llmstxt"
export AWS_REGION="us-east-1"
export DISCOVERABLE_QUEUE_URL="https://sqs.us-east-1.amazonaws.com/123456789012/llmstxt-discoverable"
```

Start server:

```bash
uvicorn server.main:app --app-dir app/server --reload --port 8000
```

Example request:

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "content-type: application/json" \
  -d '{"url":"https://example.com/docs"}'
```

### Run migrations

Apply migrations against the local database:

```bash
DATABASE_URL="postgresql+asyncpg://llmstxt:llmstxt@localhost:5432/llmstxt" \
  alembic -c app/shared/migrations/alembic.ini upgrade head
```

Verify tables exist:

```bash
docker exec llmstxt-db psql -U llmstxt -d llmstxt -c "\dt"
```

Expected output: `sites`, `runs`, `run_pages`, `site_pages`, `alembic_version`.

### Generate a new migration

After changing models, autogenerate the migration diff:

```bash
DATABASE_URL="postgresql+asyncpg://llmstxt:llmstxt@localhost:5432/llmstxt" \
  alembic -c app/shared/migrations/alembic.ini revision --autogenerate -m "description"
```

### Run server tests

```bash
uv pip install -e ./app/server[test]
DATABASE_URL="postgresql+asyncpg://llmstxt:llmstxt@localhost:5432/llmstxt" \
  AWS_REGION="us-east-1" \
  DISCOVERABLE_QUEUE_URL="https://sqs.us-east-1.amazonaws.com/123456789012/llmstxt-discoverable" \
  pytest app/server/tests/e2e -q
```

### Infra synth/deploy

```bash
uv pip install -r infra/requirements.txt
cd infra
cdk synth
cdk deploy LlmTxtGeneratorStack --require-approval never
```

## Database Schema

Four core tables:

| Table | Purpose |
|-------|---------|
| `sites` | Canonical site identity (root URL, normalized host) |
| `runs` | Run lifecycle (state machine, completion counters, output keys) |
| `run_pages` | Per-run URL tracking, fetch status, change detection |
| `site_pages` | Cross-run page memory (hash, etag, metadata) |
