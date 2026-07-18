"""
Database setup using SQLAlchemy.

Supports both SQLite (local dev, zero setup) and Postgres (production,
e.g. Neon/Railway/Supabase) via the DATABASE_URL environment variable.

Neon (and most providers) give you a URL starting with "postgresql://" or
"postgres://". SQLAlchemy needs "postgresql+psycopg://" to use the psycopg3
driver specifically, so we normalize that here rather than asking the
person setting this up to remember to edit the URL by hand.
"""

import os
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./feedback.db")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

# pool_pre_ping tests each connection before using it and transparently
# reconnects if it's gone stale. This matters specifically for Neon's
# serverless Postgres, which auto-suspends idle compute and can kill
# long-held connections - without this, the app would throw
# "AdminShutdown" errors instead of just quietly reconnecting.
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class FeedbackDB(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False)
    text = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)

    sentiment = Column(String, nullable=True)
    category = Column(String, nullable=True)
    issue_summary = Column(String, nullable=True)
    urgency = Column(String, nullable=True)
    processed_at = Column(DateTime, nullable=True)
    processing_failed = Column(Integer, default=0)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
