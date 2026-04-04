"""
providers/adzuna.py
Adzuna Jobs API — aggregates jobs from many sources (Indeed, LinkedIn, etc.)
No company list needed. Searches by keyword + country.

Free tier: 250 calls/day, 50 results/page.
Register at: https://developer.adzuna.com/

Set environment variables:
    ADZUNA_APP_ID=your_app_id
    ADZUNA_APP_KEY=your_app_key
"""

import json
import logging
import os
import urllib.error
import urllib.request
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

ADZUNA_APP_ID = os.environ.get("ADZUNA_APP_ID", "")
ADZUNA_APP_KEY = os.environ.get("ADZUNA_APP_KEY", "")

# Search queries to run — each becomes one API call
SEARCH_QUERIES = [
    "security engineer",
    "penetration tester",
    "red team engineer",
    "offensive security",
    "application security engineer",
    "detection engineer new grad",
    "cybersecurity engineer entry level",
]

BASE_URL = "https://api.adzuna.com/v1/api/jobs/us/search/{page}"


def _fetch_page(query: str, page: int = 1, results_per_page: int = 50) -> list[dict]:
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        return []

    params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "results_per_page": results_per_page,
        "what": query,
        "where": "United States",
        "content-type": "application/json",
        "sort_by": "date",               # newest first
        "max_days_old": 5,               # only recent jobs
    }
    url = BASE_URL.format(page=page) + "?" + urlencode(params)

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "JobRadar/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
            return data.get("results", [])
    except urllib.error.HTTPError as e:
        logger.warning(f"Adzuna HTTP {e.code} for query '{query}': {e.reason}")
        return []
    except Exception as e:
        logger.warning(f"Adzuna error for query '{query}': {e}")
        return []


def _normalize(raw: dict) -> dict:
    """Convert Adzuna job format to our standard job dict."""
    company = raw.get("company", {}).get("display_name", "Unknown")
    location_parts = []
    loc = raw.get("location", {})
    if loc.get("display_name"):
        location_parts.append(loc["display_name"])
    location = ", ".join(location_parts) if location_parts else ""

    # Adzuna returns created date as ISO string e.g. "2026-02-17T12:00:00Z"
    created = raw.get("created", "")
    posted_at = created[:10] if created else None

    return {
        "id": f"adzuna_{raw.get('id', '')}",
        "company": company,
        "title": raw.get("title", ""),
        "location": location,
        "posted_at": posted_at,
        "apply_url": raw.get("redirect_url", ""),
        "source": "adzuna",
    }


def fetch_jobs() -> list[dict]:
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        logger.warning("Adzuna: ADZUNA_APP_ID / ADZUNA_APP_KEY not set — skipping.")
        return []

    seen_ids: set[str] = set()
    jobs: list[dict] = []

    for query in SEARCH_QUERIES:
        raw_jobs = _fetch_page(query)
        logger.info(f"Adzuna '{query}': {len(raw_jobs)} raw results")
        for raw in raw_jobs:
            job = _normalize(raw)
            if job["id"] not in seen_ids:
                seen_ids.add(job["id"])
                jobs.append(job)

    logger.info(f"Adzuna total (deduplicated): {len(jobs)} jobs")
    return jobs
