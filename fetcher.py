"""
fetcher.py — Step 1 of JobRadar.

Pulls open job listings from:
  - Greenhouse API  (boards-api.greenhouse.io)
  - Lever API       (api.lever.co)

Filters by keywords defined in config.py.
Returns a list of clean Job dicts ready for storage or scoring.

Run standalone to test:
    python fetcher.py
"""

import requests
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional

from config import GREENHOUSE_TOKENS, LEVER_TOKENS, KEYWORDS

# ─── Data model ───────────────────────────────────────────────────────────────

@dataclass
class Job:
    id: str               # unique: "{source}_{external_id}"
    company: str          # e.g. "databricks"
    source: str           # "greenhouse" | "lever"
    title: str
    location: str
    url: str
    description: str      # raw HTML/text from the API
    posted_at: Optional[str]
    fetched_at: str       # ISO timestamp of when we pulled it

# ─── Keyword filter ───────────────────────────────────────────────────────────

def matches_keywords(title: str) -> bool:
    title_lower = title.lower()
    return any(kw in title_lower for kw in KEYWORDS)

# ─── Greenhouse fetcher ───────────────────────────────────────────────────────

def fetch_greenhouse(token: str) -> list[Job]:
    """Fetch all open jobs for a Greenhouse board token."""
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        # 404 usually means the token is wrong or company removed their board
        print(f"  [greenhouse/{token}] HTTP error: {e}")
        return []
    except requests.exceptions.RequestException as e:
        print(f"  [greenhouse/{token}] Request failed: {e}")
        return []

    jobs = []
    now = datetime.now(timezone.utc).isoformat()
    for j in resp.json().get("jobs", []):
        if not matches_keywords(j.get("title", "")):
            continue
        jobs.append(Job(
            id=f"gh_{j['id']}",
            company=token,
            source="greenhouse",
            title=j["title"],
            location=j.get("location", {}).get("name", "Unknown"),
            url=j.get("absolute_url", ""),
            description=j.get("content", ""),
            posted_at=j.get("updated_at"),
            fetched_at=now,
        ))
    return jobs

# ─── Lever fetcher ────────────────────────────────────────────────────────────

def fetch_lever(token: str) -> list[Job]:
    """Fetch all open jobs for a Lever posting slug."""
    url = f"https://api.lever.co/v0/postings/{token}?mode=json"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(f"  [lever/{token}] HTTP error: {e}")
        return []
    except requests.exceptions.RequestException as e:
        print(f"  [lever/{token}] Request failed: {e}")
        return []

    jobs = []
    now = datetime.now(timezone.utc).isoformat()
    for j in resp.json():
        if not matches_keywords(j.get("text", "")):
            continue

        # Lever location can be a list or a string
        location_data = j.get("categories", {}).get("location", "Unknown")
        if isinstance(location_data, list):
            location = ", ".join(location_data)
        else:
            location = location_data or "Unknown"

        # Lever description lives in lists
        description_parts = j.get("descriptionBody", {}).get("body", "")

        jobs.append(Job(
            id=f"lv_{j['id']}",
            company=token,
            source="lever",
            title=j["text"],
            location=location,
            url=j.get("hostedUrl", ""),
            description=str(description_parts),
            posted_at=None,   # Lever doesn't expose posted date in v0 API
            fetched_at=now,
        ))
    return jobs

# ─── Main fetch orchestrator ──────────────────────────────────────────────────

def fetch_all_jobs() -> list[Job]:
    """Fetch from all configured companies. Returns all matching jobs."""
    all_jobs: list[Job] = []

    print("── Greenhouse ──────────────────────────────")
    for token in GREENHOUSE_TOKENS:
        jobs = fetch_greenhouse(token)
        print(f"  {token}: {len(jobs)} matching jobs")
        all_jobs.extend(jobs)

    print("\n── Lever ───────────────────────────────────")
    for token in LEVER_TOKENS:
        jobs = fetch_lever(token)
        print(f"  {token}: {len(jobs)} matching jobs")
        all_jobs.extend(jobs)

    print(f"\n✓ Total: {len(all_jobs)} jobs across all sources\n")
    return all_jobs


# ─── Standalone test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    jobs = fetch_all_jobs()

    # Pretty-print a sample
    print("── Sample results (first 5) ────────────────")
    for job in jobs[:5]:
        print(f"\n  [{job.company.upper()}] {job.title}")
        print(f"  Location : {job.location}")
        print(f"  URL      : {job.url}")
        print(f"  Source   : {job.source}")
