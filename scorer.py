"""
scorer.py — Step 3 of JobRadar.

Scores each unscored job against your resume using Claude API.
Stores a 0-100 match score + 2-line reasoning back in jobs.db.

Only scores jobs where score IS NULL (new jobs from this run).
Safe to re-run — already-scored jobs are skipped.

Run standalone:
    export ANTHROPIC_API_KEY="sk-ant-..."
    python scorer.py
"""

import os
import re
import json
import sqlite3
import time
from storage import DB_PATH, get_connection

# ─── Your resume (plain text summary for the prompt) ─────────────────────────
# Keeping this inline so the scorer works without reading a file.
# Update this if your resume changes.

RESUME_SUMMARY = """
Name: Ritika Neema
Current: MS Applied Data Intelligence @ SJSU (graduating May 2027)
Prior: Data Engineer @ TCS / AWS (Eli Lilly client) — 3 years

Core skills:
- Data Engineering: Apache Spark, AWS Glue, Redshift, Athena, Airflow, dbt, Snowflake, Kafka, ETL/ELT
- ML & AI: Scikit-learn, XGBoost, TensorFlow, MLflow, Feature Engineering, SHAP
- Generative AI: RAG, LangChain, LangGraph, Gemini, OpenAI APIs, Agentic Workflows, Pinecone
- Cloud: AWS (S3, Lambda, Glue, Redshift, IAM, EC2, CloudWatch), Docker, CI/CD
- Languages: Python, SQL
- Databases: MySQL, BigQuery, Snowflake

Key projects:
- Self-Healing RAG Platform (FAISS + BM25 + RRF fusion, DeepEval drift monitoring, FastAPI)
- FraudLens: PySpark + Kafka + MLflow + XGBoost + LangChain agentic auditor (ROC-AUC 0.845)
- SkillSync: 15 Docker microservices, Ollama, Redis caching, AWS EC2 (5x latency improvement)
- PaySim fraud detection: CatBoost, PR-AUC 0.9986, SHAP explainability, isotonic calibration
- Real-Time Traffic Analytics: Airflow + Snowflake + dbt + Streamlit + ML forecasting
- Job Application Agent: LangGraph + Claude API + MongoDB tracker

Target roles: Data Engineer, ML Engineer, AI Engineer, Analytics Engineer
Preferred: FAANG and FAANG-adjacent companies, remote-friendly or Bay Area
"""

# ─── Scoring prompt ───────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a precise job-resume matcher. Given a job description and a candidate resume, 
output ONLY valid JSON with no preamble, no markdown, no explanation outside the JSON.

Scoring rubric (0-100):
- 85-100: Strong match — candidate meets 80%+ of requirements, background directly relevant
- 65-84:  Good match — candidate meets core requirements, some gaps are learnable
- 45-64:  Partial match — relevant background but significant gaps or seniority mismatch
- 0-44:   Weak match — fundamentally different role, stack, or experience level required

Be strict. A "Senior Staff" role requiring 8+ years should score low for a candidate with 3 years."""

def build_user_prompt(title: str, company: str, description: str) -> str:
    # Truncate description to avoid token overflow — first 2000 chars is enough
    desc_trimmed = description[:2000].strip() if description else "No description available."
    return f"""
RESUME:
{RESUME_SUMMARY}

JOB:
Company: {company}
Title: {title}
Description:
{desc_trimmed}

Return ONLY this JSON (no markdown, no extra text):
{{
  "score": <integer 0-100>,
  "reason": "<one sentence why this is or isn't a good match>",
  "key_match": "<the single strongest matching skill or experience>",
  "key_gap": "<the single most significant missing requirement, or 'None' if strong match>"
}}
"""

# ─── Claude API call ──────────────────────────────────────────────────────────

def score_job(title: str, company: str, description: str) -> dict:
    """Call Claude API and return parsed score dict. Returns None on failure."""
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",  # fast + cheap for batch scoring
            max_tokens=256,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": build_user_prompt(title, company, description)}
            ],
        )
        raw = message.content[0].text.strip()

        # Strip markdown fences if model adds them despite instructions
        raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
        return json.loads(raw)

    except json.JSONDecodeError as e:
        print(f"    JSON parse error for [{company}] {title}: {e}")
        return None
    except Exception as e:
        print(f"    API error for [{company}] {title}: {e}")
        return None


# ─── Update DB with score ─────────────────────────────────────────────────────

def save_score(job_id: str, score: int, reason: str, key_match: str, key_gap: str):
    conn = get_connection()
    conn.execute(
        """UPDATE jobs
           SET score = ?, score_reason = ?
           WHERE id = ?""",
        (score, f"{reason} | Match: {key_match} | Gap: {key_gap}", job_id),
    )
    conn.commit()
    conn.close()


# ─── Main ─────────────────────────────────────────────────────────────────────

def score_unscored_jobs(batch_size: int = 50):
    """
    Score all jobs where score IS NULL.
    batch_size: max jobs to score per run (cost control).
    At ~$0.0003/job with Haiku, 131 jobs = ~$0.04 total.
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, company, title, description FROM jobs WHERE score IS NULL LIMIT ?",
        (batch_size,)
    ).fetchall()
    conn.close()

    if not rows:
        print("No unscored jobs found.")
        return []

    print(f"Scoring {len(rows)} jobs...")
    scored = []

    for i, row in enumerate(rows, 1):
        result = score_job(row["title"], row["company"], row["description"] or "")

        if result:
            save_score(
                row["id"],
                result["score"],
                result["reason"],
                result.get("key_match", ""),
                result.get("key_gap", ""),
            )
            scored.append({**dict(row), **result})
            print(f"  [{i}/{len(rows)}] {row['company']:12} | {result['score']:3}/100 | {row['title'][:50]}")
        else:
            print(f"  [{i}/{len(rows)}] {row['company']:12} | FAILED | {row['title'][:50]}")

        # Polite rate limiting — Haiku is fast but don't hammer the API
        time.sleep(0.3)

    print(f"\n✓ Scored {len(scored)}/{len(rows)} jobs")
    return scored


def get_top_jobs(min_score: float = 70, limit: int = 20) -> list[dict]:
    """Return top-scored jobs — used by notifier."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT company, title, location, url, score, score_reason
           FROM jobs
           WHERE score >= ?
           ORDER BY score DESC
           LIMIT ?""",
        (min_score, limit),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ─── Standalone test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: Set ANTHROPIC_API_KEY environment variable first.")
        print("  export ANTHROPIC_API_KEY='sk-ant-...'")
        exit(1)

    # Score up to 20 jobs for the test run (don't burn the whole batch)
    scored = score_unscored_jobs(batch_size=20)

    print("\n── Top matches (score ≥ 70) ────────────────────")
    top = get_top_jobs(min_score=70)
    if top:
        for job in top:
            print(f"\n  {job['score']}/100 — [{job['company'].upper()}] {job['title']}")
            print(f"  {job['location']}")
            print(f"  {job['score_reason']}")
            print(f"  {job['url']}")
    else:
        print("  No jobs scored ≥ 70 yet (run with larger batch_size to score more)")
