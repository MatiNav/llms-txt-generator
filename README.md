# llms.txt Generator

Distributed pipeline that crawls websites and generates [llms.txt](https://llmstxt.org/) files -- structured metadata that helps LLMs understand site content.

## Architecture

The system is built as a distributed pipeline on AWS:

- **FastAPI server** (App Runner) -- API + SSE for real-time progress
- **Orchestrator** (ECS Fargate) -- URL dedup, robots.txt, fetch routing
- **HTTP fetcher** (Lambda) -- fast-path page fetching
- **Playwright fetcher** (ECS Fargate) -- JS-rendered page fetching
- **Processing pipeline** (Lambda) -- content extraction and llms.txt generation
- **PostgreSQL** (RDS) -- persistent state for sites, runs, and pages
- **SQS queues** -- decoupled message routing between stages
- **S3** -- HTML artifact and output storage

## Project Structure

```
app/
  shared/           Shared Python package (models, DB, pipeline)
    shared/
      models/       SQLAlchemy 2.0 models (Site, Run, RunPage, SitePage)
      db/           Async engine, session factory, migration runner
      pipeline/     Pure functions ported from POC (planned)
      storage/      S3 client (planned)
      queue/        SQS client (planned)
    migrations/     Alembic async migrations
  server/           FastAPI server (planned)
  handlers/         Lambda + ECS task handlers (planned)
infra/              CDK infrastructure (planned)
```

## Tech Stack

- Python 3.12
- SQLAlchemy 2.0 (async, declarative `mapped_column` style)
- asyncpg (PostgreSQL async driver)
- Alembic (async migrations)
- FastAPI + Pydantic v2 (planned)
- aioboto3 (async AWS SDK)
- AWS CDK (Python, planned)

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

## Database Schema

Four core tables:

| Table | Purpose |
|-------|---------|
| `sites` | Canonical site identity (root URL, normalized host) |
| `runs` | Run lifecycle (state machine, completion counters, output keys) |
| `run_pages` | Per-run URL tracking, fetch status, change detection |
| `site_pages` | Cross-run page memory (hash, etag, metadata) |

