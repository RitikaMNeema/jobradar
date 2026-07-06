"""
storage.py — Step 2 of JobRadar.

SQLite layer. Handles:
  - Schema creation (idempotent — safe to run repeatedly)
  - Inserting new jobs (dedupes on job.id — no duplicates across runs)
  - Returning only NEW jobs from a batch (for the email step)
  - Feedback tracking (applied / not_interested / starred)

Run standalone to inspect the DB:
    python storage.py
"""

import sqlite3
from dataclasses import asdict
from typing import Optional
from fetcher import Job

DB_PATH = "jobs.db"

# ─── Schema ───────────────────────────────────────────────────────────────────

CREATE_JOBS_TABLE = """
CREATE TABLE IF NOT EXISTS jobs (
    id          TEXT PRIMARY KEY,   -- "gh_<id>" or "lv_<id>"
    company     TEXT NOT NULL,
    source      TEXT NOT NULL,      -- "greenhouse" | "lever"
    title       TEXT NOT NULL,
    location    TEXT,
    url         TEXT,
    description TEXT,
    posted_at   TEXT,
    fetched_at  TEXT NOT NULL,
    score       REAL,               -- LLM match score 0-100 (Step 3)
    score_reason TEXT,              -- LLM explanation (Step 3)
    feedback    TEXT DEFAULT NULL   -- "applied" | "starred" | "not_interested"
)
"""

CREATE_RUNS_TABLE = """
CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ran_at      TEXT NOT NULL,
    jobs_fetched INTEGER,
    jobs_new    INTEGER
)
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row   # lets you access columns by name
    return conn


def init_db():
    """Create tables if they don't exist. Safe to call on every run."""
    conn = get_connection()
    conn.execute(CREATE_JOBS_TABLE)
    conn.execute(CREATE_RUNS_TABLE)
    conn.commit()
    conn.close()


# ─── Insert ───────────────────────────────────────────────────────────────────

def save_jobs(jobs: list[Job]) -> list[Job]:
    """
    Insert jobs that don't already exist in the DB.
    Returns only the NEW jobs (not seen in previous runs).
    Uses INSERT OR IGNORE so duplicates are silently skipped.
    """
    conn = get_connection()
    new_jobs = []

    for job in jobs:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO jobs
                (id, company, source, title, location, url, description, posted_at, fetched_at)
            VALUES
                (:id, :company, :source, :title, :location, :url, :description, :posted_at, :fetched_at)
            """,
            asdict(job),
        )
        if cursor.rowcount == 1:   # rowcount=1 means it was actually inserted (new)
            new_jobs.append(job)

    conn.commit()
    conn.close()
    return new_jobs


# ─── Run logging ──────────────────────────────────────────────────────────────

def log_run(ran_at: str, jobs_fetched: int, jobs_new: int):
    conn = get_connection()
    conn.execute(
        "INSERT INTO runs (ran_at, jobs_fetched, jobs_new) VALUES (?, ?, ?)",
        (ran_at, jobs_fetched, jobs_new),
    )
    conn.commit()
    conn.close()


# ─── Query helpers (used by dashboard) ───────────────────────────────────────

def get_all_jobs(
    company: Optional[str] = None,
    min_score: Optional[float] = None,
    feedback: Optional[str] = None,
    limit: int = 500,
) -> list[dict]:
    """Flexible query for the Streamlit dashboard."""
    conn = get_connection()
    query = "SELECT * FROM jobs WHERE 1=1"
    params = []

    if company:
        query += " AND company = ?"
        params.append(company)
    if min_score is not None:
        query += " AND score >= ?"
        params.append(min_score)
    if feedback:
        query += " AND feedback = ?"
        params.append(feedback)

    query += " ORDER BY fetched_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_feedback(job_id: str, feedback: str):
    """Mark a job as applied / starred / not_interested from the dashboard."""
    conn = get_connection()
    conn.execute(
        "UPDATE jobs SET feedback = ? WHERE id = ?",
        (feedback, job_id),
    )
    conn.commit()
    conn.close()


def get_run_stats() -> list[dict]:
    """Last 10 runs — shown in dashboard."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM runs ORDER BY ran_at DESC LIMIT 10"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ─── Standalone test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    from fetcher import fetch_all_jobs
    from datetime import datetime, timezone

    print("Initializing DB...")
    init_db()

    print("Fetching jobs...")
    all_jobs = fetch_all_jobs()

    print("Saving to DB...")
    new_jobs = save_jobs(all_jobs)

    ran_at = datetime.now(timezone.utc).isoformat()
    log_run(ran_at, len(all_jobs), len(new_jobs))

    print(f"\n✓ Fetched : {len(all_jobs)}")
    print(f"✓ New     : {len(new_jobs)}  (first run = all jobs are new)")
    print(f"✓ Saved to: {DB_PATH}")

    print("\n── Sample from DB ──────────────────────────────")
    for job in get_all_jobs(limit=3):
        print(f"  [{job['company'].upper()}] {job['title']}  |  {job['location']}")

    print("\n── Run log ─────────────────────────────────────")
    for run in get_run_stats():
        print(f"  {run['ran_at']}  fetched={run['jobs_fetched']}  new={run['jobs_new']}")
