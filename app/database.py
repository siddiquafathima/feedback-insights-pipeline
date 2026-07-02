"""
Database setup using SQLAlchemy.

Uses SQLite by default so you can run this with zero setup.
Swap DATABASE_URL to a Postgres connection string when you deploy
(e.g. postgresql://user:pass@host:5432/dbname) - the rest of the
code doesn't change.
"""

import os
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./feedback.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class FeedbackDB(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False)
    text = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)

    # Fields populated after LLM processing (nullable until processed)
    sentiment = Column(String, nullable=True)
    category = Column(String, nullable=True)
    issue_summary = Column(String, nullable=True)
    urgency = Column(String, nullable=True)
    processed_at = Column(DateTime, nullable=True)
    processing_failed = Column(Integer, default=0)  # 0 = ok, 1 = failed after retries


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
