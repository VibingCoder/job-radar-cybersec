"""
providers/greenhouse.py
Greenhouse ATS — clean public JSON API, no auth needed.
API: https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs
"""

import json
import logging
import urllib.error
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)

BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"


def _fetch(token: str) -> Optional[dict]:
    url = BASE_URL.format(token=token)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "JobRadar/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        logger.warning(f"[greenhouse] {token} → HTTP {e.code}")
    except Exception as e:
        logger.warning(f"[greenhouse] {token} → {e}")
    return None


def fetch(company_cfg: dict) -> list[dict]:
    token = company_cfg.get("id", "")
    name = company_cfg.get("name", token)
    raw = _fetch(token)
    if not raw:
        return []

    jobs = []
    for job in raw.get("jobs", []):
        # `offices` is the authoritative region field; `location.name` is often
        # a free-text string like "N/A" that doesn't reliably indicate country.
        office_names = [o.get("name", "") for o in job.get("offices", []) if o.get("name")]
        if any(n == "US" for n in office_names):
            location = "United States"
        elif office_names:
            location = ", ".join(office_names)  # e.g. "Canada Locations"
        else:
            loc = job.get("location", {})
            location = loc.get("name", "") if isinstance(loc, dict) else str(loc or "")

        jobs.append({
            "job_id": f"greenhouse-{job.get('id', '')}",
            "company": name,
            "title": job.get("title", ""),
            "location": location,
            "posted_at": max(
                (job.get("first_published") or ""),
                (job.get("updated_at") or ""),
            ) or None,
            "apply_url": job.get("absolute_url", ""),
            "description": job.get("content", ""),   # HTML — stripped in filter.py
            "provider": "greenhouse",
        })

    logger.info(f"[greenhouse] {name}: {len(jobs)} jobs")
    return jobs
