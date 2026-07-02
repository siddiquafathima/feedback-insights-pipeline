"""
Pydantic schemas.

These do two jobs:
1. Define the exact shape of data we store in the DB.
2. Define the exact shape we FORCE the LLM to return, so its output
   is never "just text" - it's validated, structured data we can query.
"""

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class Sentiment(str, Enum):
    positive = "positive"
    negative = "negative"
    neutral = "neutral"
    mixed = "mixed"


class Category(str, Enum):
    bug = "bug"
    feature_request = "feature_request"
    praise = "praise"
    support_experience = "support_experience"
    billing = "billing"
    other = "other"


class Urgency(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class FeedbackInput(BaseModel):
    """Raw incoming feedback row, before LLM processing."""
    id: int
    source: str
    text: str
    created_at: datetime


class ExtractedInsight(BaseModel):
    """
    The exact JSON shape we require the LLM to return.
    If the LLM's response doesn't match this schema, Pydantic raises
    a validation error and our retry logic kicks in.
    """
    sentiment: Sentiment
    category: Category
    issue_summary: str = Field(..., max_length=200, description="One-line summary of the core issue or praise")
    urgency: Urgency

    class Config:
        use_enum_values = True


class FeedbackRecord(BaseModel):
    """Final stored record: raw input + extracted insight, merged."""
    id: int
    source: str
    text: str
    created_at: datetime
    sentiment: Sentiment
    category: Category
    issue_summary: str
    urgency: Urgency
    processed_at: datetime


class InsightsSummary(BaseModel):
    """Response shape for the /insights/summary endpoint."""
    total_reviews: int
    positive: int
    negative: int
    neutral: int
    mixed: int
    high_urgency_count: int
    top_category: str | None
