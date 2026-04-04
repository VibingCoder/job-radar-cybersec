"""
providers/lever.py
Lever ATS — public JSON API, no auth needed.
API: https://api.lever.co/v0/postings/{company_id}?mode=json
"""

import json
import logging
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

BASE_URL = "https://api.lever.co/v0/postings/{company_id}?mode=json"


def _fetch(company_id: str) -> Optional[list]:
    url = BASE_URL.format(company_id=company_id)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "JobRadar/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        logger.warning(f"[lever] {company_id} → HTTP {e.code}")
    except Exception as e:
        logger.warning(f"[lever] {company_id} → {e}")
    return None


def fetch(company_cfg: dict) -> list[dict]:
    company_id = company_cfg.get("id", "")
    name = company_cfg.get("name", company_id)
    raw = _fetch(company_id)
    if not raw:
        return []

    jobs = []
    for posting in raw:
        if not isinstance(posting, dict):
            continue
        categories = posting.get("categories", {})
        location = categories.get("location", "") or posting.get("workplaceType", "")
        jobs.append({
            "job_id": f"lever-{posting.get('id', '')}",
            "company": name,
            "title": posting.get("text", ""),
            "location": location,
            "posted_at": datetime.fromtimestamp(posting["createdAt"] / 1000, tz=timezone.utc).date().isoformat() if posting.get("createdAt") else None,
            "apply_url": posting.get("hostedUrl", ""),
            "description": posting.get("description") or posting.get("descriptionPlain", ""),
            "provider": "lever",
        })

    logger.info(f"[lever] {name}: {len(jobs)} jobs")
    return jobs
