"""
providers/ashby.py
Ashby ATS — GET job board API, no auth needed.
API: https://api.ashbyhq.com/posting-api/job-board/{company_id}
"""

import json
import logging
import urllib.error
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)

BASE_URL = "https://api.ashbyhq.com/posting-api/job-board/{company_id}"


def _fetch(company_id: str) -> Optional[dict]:
    url = BASE_URL.format(company_id=company_id)
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "JobRadar/1.0"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        logger.warning(f"[ashby] {company_id} → HTTP {e.code}")
    except Exception as e:
        logger.warning(f"[ashby] {company_id} → {e}")
    return None


def fetch(company_cfg: dict) -> list[dict]:
    company_id = company_cfg.get("id", "")
    name = company_cfg.get("name", company_id)
    raw = _fetch(company_id)
    if not raw:
        return []

    jobs = []
    for posting in raw.get("jobs", []):
        if not isinstance(posting, dict):
            continue
        loc_data = posting.get("location") or posting.get("locationName") or ""
        if isinstance(loc_data, dict):
            location = loc_data.get("city") or loc_data.get("name") or ""
        else:
            location = str(loc_data)

        jobs.append({
            "job_id": f"ashby-{posting.get('id', '')}",
            "company": name,
            "title": posting.get("title", ""),
            "location": location,
            "posted_at": posting.get("publishedAt") or posting.get("updatedAt"),
            "apply_url": posting.get("jobUrl", ""),
            "description": posting.get("descriptionHtml") or posting.get("description", ""),
            "provider": "ashby",
        })

    logger.info(f"[ashby] {name}: {len(jobs)} jobs")
    return jobs
