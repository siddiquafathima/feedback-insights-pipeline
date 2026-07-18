"""
Analytical queries against the feedback table, written for Postgres.

These go beyond simple filters/aggregates (which the API endpoints already
do) to demonstrate genuinely useful SQL: window functions for ranking and
trend analysis, and CTEs for multi-step analysis in a single query.

Run standalone with: python -m app.analytics
"""

from sqlalchemy import text
from app.database import engine


def top_category_by_week():
    """
    For each week, find the most common feedback category using
    ROW_NUMBER() partitioned by week. Answers: "what's the #1 thing
    customers are complaining/praising about, and how does that shift
    week to week?"
    """
    query = text("""
        WITH weekly_counts AS (
            SELECT
                date_trunc('week', created_at) AS week,
                category,
                COUNT(*) AS category_count
            FROM feedback
            WHERE processing_failed = 0
            GROUP BY week, category
        ),
        ranked AS (
            SELECT
                week,
                category,
                category_count,
                ROW_NUMBER() OVER (
                    PARTITION BY week
                    ORDER BY category_count DESC
                ) AS rank_in_week
            FROM weekly_counts
        )
        SELECT week, category, category_count
        FROM ranked
        WHERE rank_in_week = 1
        ORDER BY week
    """)
    with engine.connect() as conn:
        return conn.execute(query).fetchall()


def sentiment_trend_moving_average():
    """
    Rolling 3-day average of the negative-sentiment ratio, using a window
    function frame (ROWS BETWEEN). Smooths day-to-day noise so you can see
    whether sentiment is genuinely trending worse or better, not just
    reacting to a single bad day.
    """
    query = text("""
        WITH daily_stats AS (
            SELECT
                created_at::date AS day,
                COUNT(*) AS total,
                SUM(CASE WHEN sentiment = 'negative' THEN 1 ELSE 0 END) AS negative_count
            FROM feedback
            WHERE processing_failed = 0
            GROUP BY day
        )
        SELECT
            day,
            total,
            negative_count,
            ROUND(1.0 * negative_count / total, 2) AS negative_ratio,
            ROUND(AVG(1.0 * negative_count / total) OVER (
                ORDER BY day
                ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
            ), 2) AS negative_ratio_3day_avg
        FROM daily_stats
        ORDER BY day
    """)
    with engine.connect() as conn:
        return conn.execute(query).fetchall()


def urgent_issues_needing_attention():
    """
    Surfaces high-urgency issues older than the average age of high-urgency
    issues - a "these have been sitting too long" flag. Uses a CTE to
    compute the baseline, then filters against it in the same query.
    """
    query = text("""
        WITH urgency_stats AS (
            SELECT
                AVG(EXTRACT(EPOCH FROM (now() - created_at)) / 86400.0) AS avg_age_days
            FROM feedback
            WHERE urgency = 'high' AND processing_failed = 0
        )
        SELECT
            f.id,
            f.source,
            f.issue_summary,
            f.category,
            ROUND((EXTRACT(EPOCH FROM (now() - f.created_at)) / 86400.0)::numeric, 1) AS age_days
        FROM feedback f, urgency_stats u
        WHERE f.urgency = 'high'
          AND f.processing_failed = 0
          AND (EXTRACT(EPOCH FROM (now() - f.created_at)) / 86400.0) > u.avg_age_days
        ORDER BY age_days DESC
    """)
    with engine.connect() as conn:
        return conn.execute(query).fetchall()


if __name__ == "__main__":
    print("=== Top category by week ===")
    for row in top_category_by_week():
        print(row)

    print("\n=== Sentiment trend (3-day moving average) ===")
    for row in sentiment_trend_moving_average():
        print(row)

    print("\n=== High-urgency issues older than average ===")
    for row in urgent_issues_needing_attention():
        print(row)
