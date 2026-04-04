"""
providers/smartrecruiters.py
SmartRecruiters ATS — paginated public API, no auth needed.
API: https://api.smartrecruiters.com/v1/companies/{company_id}/postings
"""

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)

BASE_URL = "https://api.smartrecruiters.com/v1/companies/{company_id}/postings"
PAGE_SIZE = 100


def _fetch_page(company_id: str, offset: int = 0) -> Optional[dict]:
    params = urllib.parse.urlencode({
        "limit": PAGE_SIZE,
        "offset": offset,
        "status": "PUBLISHED",
    })
    url = f"{BASE_URL.format(company_id=company_id)}?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "JobRadar/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        logger.warning(f"[smartrecruiters] {company_id} → HTTP {e.code}")
    except Exception as e:
        logger.warning(f"[smartrecruiters] {company_id} → {e}")
    return None


def fetch(company_cfg: dict) -> list[dict]:
    company_id = company_cfg.get("id", "")
    name = company_cfg.get("name", company_id)

    all_jobs = []
    offset = 0
    while True:
        page = _fetch_page(company_id, offset)
        if not page:
            break
        content = page.get("content", [])
        if not content:
            break
        for item in content:
            loc = item.get("location", {})
            if isinstance(loc, dict):
                parts = [loc.get("city"), loc.get("region"), loc.get("country")]
                location = ", ".join(p for p in parts if p)
            else:
                location = str(loc or "")
            all_jobs.append({
                "job_id": f"smartrecruiters-{item.get('id', '')}",
                "company": name,
                "title": item.get("name", ""),
                "location": location,
                "posted_at": item.get("releasedDate"),
                "apply_url": f"https://jobs.smartrecruiters.com/{company_id}/{item.get('id', '')}",
                "provider": "smartrecruiters",
            })
        total = page.get("totalFound", 0)
        offset += PAGE_SIZE
        if offset >= total:
            break

    logger.info(f"[smartrecruiters] {name}: {len(all_jobs)} jobs")
    return all_jobs
