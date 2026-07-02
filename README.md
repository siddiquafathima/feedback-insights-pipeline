# Customer feedback insights pipeline

Turns unstructured customer feedback (reviews, support tickets) into structured,
queryable business insights using an LLM with enforced schema validation.

## The problem

Companies collect thousands of reviews and support tickets. Nobody reads them all.
This pipeline reads them automatically, extracts sentiment/category/urgency, and
serves the results as structured data a product team can actually query and act on.

## Demo

![API docs](screenshots/docs.png)

Sentiment and category breakdown:
![Summary endpoint](screenshots/summary-endpoint.png)

Structured issue extraction from raw feedback text:
![Issues endpoint](screenshots/issues-endpoint.png)




## Architecture

```
CSV / raw feedback
      |
      v
[ingestion.py] --clean text-->
      |
      v
[llm_service.py] --prompt + schema--> Claude API
      |
      v (validate against Pydantic schema, retry up to 3x on failure)
      |
      v
[database.py] --store structured record--> SQLite / Postgres
      |
      v
[main.py] --FastAPI endpoints--> /insights/summary, /insights/issues
```


## The core engineering problem this solves

LLMs don't reliably return valid JSON on every call. This pipeline:
1. Prompts the model to return only JSON matching a strict schema
2. Validates the response with Pydantic
3. Retries with backoff (up to 3x) if the response is malformed or fails validation
4. Flags records that still fail after retries for manual review instead of
   crashing the whole batch

This is the part worth explaining in an interview: reliability engineering
around an inherently unreliable component (the LLM), not just "call the API."

## Running locally

```bash
pip install -r requirements.txt
cp .env.example .env   # add your ANTHROPIC_API_KEY
python -m app.ingestion sample_data.csv
uvicorn app.main:app --reload
```

Then visit `http://localhost:8000/docs` for interactive API docs.

## Endpoints

- `GET /insights/summary` - aggregate stats (sentiment breakdown, top category, high-urgency count)
- `GET /insights/issues?urgency=high&category=bug` - filtered list of extracted issues
- `GET /insights/failed` - records that failed extraction after retries

## Running with Docker

```bash
docker build -t feedback-pipeline .
docker run -p 8000:8000 --env-file .env feedback-pipeline
```

## What I'd change to scale this

- Swap SQLite for Postgres (already supported via `DATABASE_URL` env var)
- Move ingestion from a synchronous script to a queue (Kafka/SQS) so it can
  handle high-volume, real-time feedback streams instead of batch CSV imports
- Add async processing with `asyncio` + batched LLM calls to cut latency
- Add a scheduler (Airflow/cron) to run ingestion continuously against a live
  data source instead of a one-off script

## Tech stack

Python, FastAPI, SQLAlchemy, Pydantic, Anthropic API, Docker
