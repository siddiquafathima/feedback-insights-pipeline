"""
Ingestion pipeline: CSV -> clean -> LLM extract -> store in DB.

Run standalone with: python -m app.ingestion sample_data.csv
"""

import csv
import sys
from datetime import datetime, timezone

from app.database import SessionLocal, FeedbackDB, init_db
from app.llm_service import extract_insight


def clean_text(text: str) -> str:
    """Basic normalization - strip whitespace, collapse newlines."""
    return " ".join(text.split())


def ingest_csv(filepath: str):
    init_db()
    db = SessionLocal()

    processed, failed = 0, 0

    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            feedback_id = int(row["id"])

            # Skip if already ingested (idempotent re-runs)
            existing = db.query(FeedbackDB).filter(FeedbackDB.id == feedback_id).first()
            if existing:
                continue

            cleaned_text = clean_text(row["text"])
            insight = extract_insight(cleaned_text)

            record = FeedbackDB(
                id=feedback_id,
                source=row["source"],
                text=cleaned_text,
                created_at=datetime.fromisoformat(row["created_at"]),
            )

            if insight:
                record.sentiment = insight.sentiment
                record.category = insight.category
                record.issue_summary = insight.issue_summary
                record.urgency = insight.urgency
                record.processed_at = datetime.now(timezone.utc)
                record.processing_failed = 0
                processed += 1
            else:
                record.processing_failed = 1
                failed += 1

            db.add(record)
            db.commit()

    db.close()
    print(f"Done. Processed: {processed}, Failed (flagged for review): {failed}")


if __name__ == "__main__":
    filepath = sys.argv[1] if len(sys.argv) > 1 else "sample_data.csv"
    ingest_csv(filepath)
