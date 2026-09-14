# Docenta (backend)

Docenta turns documents into short learning videos. Upload a PDF, Word file,
PowerPoint, HTML page, or plain text, and Docenta extracts the content, turns
it into a scene-by-scene script, narrates it, and renders a video.

This repository (`docenta-be`) is the Python backend.

## Status

Built and working:

- FastAPI application, containerized with Docker, deployed on Render.
- PostgreSQL database on Supabase, schema managed with Alembic.
- Document ingestion: a column-aware extraction pipeline that turns PDF, DOCX,
  PPTX, HTML, and TXT into clean, reading-order text with structured regions.
- A live `POST /ingestion/extract` endpoint.

Planned next:

- Script generation (LLM via Groq) that turns extracted text into a script.
- Narration (text-to-speech) and video rendering.
- Authentication and persistence of documents, scripts, and jobs.

## Tech stack

- FastAPI and Uvicorn for the API.
- SQLAlchemy and Alembic for the database layer, against Supabase Postgres.
- pdfplumber, python-docx, python-pptx, beautifulsoup4, and lxml for document
  parsing (all permissively licensed).
- Groq for LLM script generation (planned).
- Docker for local and production parity; Render for hosting.

## Project layout

```
app/
  main.py              FastAPI app and startup
  core/
    config.py          typed settings loaded from the environment
    logging.py         central logging setup
  db/
    session.py         SQLAlchemy engine, session, Base, get_db
    models.py          ORM models: users, documents, scripts, jobs
  schemas/
    pipeline.py        pipeline data contracts (ExtractedDocument, Script, ...)
  model_clients/
    base.py            LLMClient interface (the provider swap point)
    groq_client.py     Groq implementation
  services/
    ingestion.py       stage 1: extract text from a document
    script.py          stage 2: text -> Script (stub)
    visuals.py         stage 3 (stub)
    narration.py       stage 4 (stub)
    rendering.py       stage 5 (stub)
  extraction/          the document extraction subsystem
    orchestrator.py    parse -> detect layout -> order -> ExtractedDocument
    detector.py        per-page layout classification
    extractor.py       reading-order extraction (XY-Cut)
    parsers/           one parser per format (pdf, docx, pptx, html, txt)
    algorithms/        projection, manhattan, xy_cut, bbox helpers
  api/
    routes/
      ingestion.py     POST /ingestion/extract
alembic/               database migrations
```

## Design notes

Each pipeline stage is a plain function with a fixed input and output contract
defined in `schemas/pipeline.py`. Stages depend on the contracts, not on each
other, so any single stage can be reworked without touching the rest. The LLM
is reached only through the `LLMClient` interface, so the provider can change by
adding a subclass rather than editing the services.

Extraction is fully deterministic: it makes no network calls and runs on modest
hardware. It detects columns from where words leave a vertical whitespace gutter,
reads two-column pages in the correct order, and filters out fragmentary noise
from rotated tables and charts.

## Configuration

All configuration comes from environment variables (loaded from a local `.env`
in development). Copy `.env.example` to `.env` and fill in real values. Never
commit `.env`.

| Variable              | Purpose                                             |
| --------------------- | --------------------------------------------------- |
| `ENVIRONMENT`         | `development` or `production`                        |
| `LOG_LEVEL`           | e.g. `INFO`, `DEBUG`                                 |
| `SUPABASE_URL`        | Supabase project URL                                |
| `SUPABASE_SECRET_KEY` | Supabase secret API key (backend only)              |
| `SUPABASE_JWKS_URL`   | Supabase JWKS URL, for verifying auth tokens        |
| `DATABASE_URL`        | Supabase Postgres session-pooler connection string  |
| `GROQ_API_KEY`        | Groq API key                                        |
| `GROQ_MODEL`          | Groq model id, e.g. `openai/gpt-oss-20b`            |

Note on `GROQ_MODEL`: Groq's model catalog changes often, so the model is kept
in an env var rather than hardcoded. The current production baseline is
`openai/gpt-oss-20b`. Confirm available models in the Groq console before
deploying.

## Running locally

With Docker (recommended, matches production):

```
docker compose up --build
```

The API is then at `http://localhost:8000`, with interactive docs at
`http://localhost:8000/docs` and a health check at `http://localhost:8000/health`.

Without Docker:

```
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Database migrations

The schema is version-controlled with Alembic and applied against Supabase.

Create a new migration after changing the ORM models:

```
python -m alembic revision --autogenerate -m "describe the change"
```

Apply migrations:

```
python -m alembic upgrade head
```

Because local and production share the same Supabase database, running
`alembic upgrade head` once creates the tables for both.

## API

`GET /health` — liveness check.

`POST /ingestion/extract` — upload a document (PDF, DOCX, PPTX, HTML, or TXT)
as `multipart/form-data` and receive structured, reading-order text back as an
`ExtractedDocument`.

## Deployment

Render builds from the `Dockerfile` and runs the container, binding to the port
it provides. Environment variables are set in the Render dashboard, not in the
repo. Auto-deploy is enabled from the `main` branch.