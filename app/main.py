"""
FastAPI app - serves the processed insights.

Run with: uvicorn app.main:app --reload
Docs auto-generated at: http://localhost:8000/docs
"""

from fastapi import FastAPI, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from collections import Counter

import os
import threading
from app.database import get_db, FeedbackDB, init_db, SessionLocal
from app.models import InsightsSummary

app = FastAPI(title="Customer Feedback Insights API")


def _seed_in_background():
    """
    Runs the LLM ingestion pipeline in a separate thread so it doesn't
    block the app from starting up and accepting requests. Without this,
    Railway's health check can time out waiting for the app to respond
    while 15 sequential LLM calls are still running.
    """
    db = SessionLocal()
    try:
        count = db.query(FeedbackDB).count()
        if count == 0:
            csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sample_data.csv")
            if os.path.exists(csv_path):
                from app.ingestion import ingest_csv
                print("Database empty — auto-seeding from sample_data.csv in background...")
                ingest_csv(csv_path)
                print("Background seeding complete.")
    finally:
        db.close()


@app.on_event("startup")
def startup():
    init_db()
    thread = threading.Thread(target=_seed_in_background, daemon=True)
    thread.start()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/insights/summary", response_model=InsightsSummary)
def get_summary(days: int = Query(7, description="Look back this many days"), db: Session = Depends(get_db)):
    records = db.query(FeedbackDB).filter(FeedbackDB.processing_failed == 0).all()

    sentiment_counts = Counter(r.sentiment for r in records)
    category_counts = Counter(r.category for r in records)
    high_urgency = sum(1 for r in records if r.urgency == "high")

    top_category = category_counts.most_common(1)[0][0] if category_counts else None

    return InsightsSummary(
        total_reviews=len(records),
        positive=sentiment_counts.get("positive", 0),
        negative=sentiment_counts.get("negative", 0),
        neutral=sentiment_counts.get("neutral", 0),
        mixed=sentiment_counts.get("mixed", 0),
        high_urgency_count=high_urgency,
        top_category=top_category,
    )


@app.get("/insights/issues")
def get_issues(urgency: str | None = None, category: str | None = None, db: Session = Depends(get_db)):
    query = db.query(FeedbackDB).filter(FeedbackDB.processing_failed == 0)

    if urgency:
        query = query.filter(FeedbackDB.urgency == urgency)
    if category:
        query = query.filter(FeedbackDB.category == category)

    results = query.order_by(FeedbackDB.created_at.desc()).all()

    return [
        {
            "id": r.id,
            "source": r.source,
            "issue_summary": r.issue_summary,
            "category": r.category,
            "urgency": r.urgency,
            "sentiment": r.sentiment,
            "created_at": r.created_at,
        }
        for r in results
    ]


@app.get("/insights/failed")
def get_failed(db: Session = Depends(get_db)):
    """Records that failed LLM extraction after retries - for manual review."""
    results = db.query(FeedbackDB).filter(FeedbackDB.processing_failed == 1).all()
    return [{"id": r.id, "text": r.text, "source": r.source} for r in results]
