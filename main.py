"""
main.py — Run the full JobRadar pipeline manually.

    python main.py

Same sequence as GitHub Actions:
  1. Fetch jobs from all sources
  2. Store new ones (dedupe)
  3. Score unscored jobs
  4. Email digest if new top matches found
"""

from storage import init_db, save_jobs, log_run, fetch_all_jobs
from scorer  import score_unscored_jobs
from notifier import notify
from datetime import datetime, timezone

if __name__ == "__main__":
    print("=" * 50)
    print("  JobRadar Pipeline")
    print("=" * 50)

    init_db()

    print("\n[1/4] Fetching jobs...")
    jobs = fetch_all_jobs()

    print("\n[2/4] Storing + deduping...")
    new_jobs = save_jobs(jobs)
    ran_at = datetime.now(timezone.utc).isoformat()
    log_run(ran_at, len(jobs), len(new_jobs))
    print(f"  {len(new_jobs)} new jobs saved")

    print("\n[3/4] Scoring unscored jobs...")
    score_unscored_jobs(batch_size=50)

    print("\n[4/4] Sending email digest...")
    notify()

    print("\n✓ Pipeline complete.")