"""
providers/workday.py
Workday CXS REST API — reverse engineered from browser traffic.
Stable across tenants. Requires the full API URL in companies.yaml.

companies.yaml format:
  - name: Nvidia
    provider: workday_url
    url: https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/jobs
"""

import json
import logging
import re
import urllib.error
import urllib.request
from datetime import date, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

PAGE_SIZE = 20


def _parse_posted_on(posted_on: str) -> str:
    """Convert Workday's human date strings to ISO date."""
    if not posted_on:
        return None
    s = posted_on.lower()
    today = date.today()
    if "today" in s:
        return today.isoformat()
    if "30+" in s:
        return (today - timedelta(days=30)).isoformat()
    m = re.search(r"(\d+)\s+day", s)
    if m:
        return (today - timedelta(days=int(m.group(1)))).isoformat()
    return None


def _normalize_workday_location(loc: str) -> str:
    """Workday returns 'US, CA, Santa Clara' — normalize US prefix."""
    if not loc:
        return loc
    if re.match(r"^US[,\s]", loc, re.IGNORECASE):
        return "United States, " + loc.split(",", 1)[-1].strip()
    return loc


def _post_page(api_url: str, offset: int = 0) -> Optional[dict]:
    payload = json.dumps({
        "appliedFacets": {},
        "limit": PAGE_SIZE,
        "offset": offset,
        "searchText": "",
    }).encode("utf-8")
    try:
        req = urllib.request.Request(
            api_url,
            data=payload,
            headers={
                "User-Agent": "JobRadar/1.0",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        logger.warning(f"[workday] {api_url} → HTTP {e.code}")
    except Exception as e:
        logger.warning(f"[workday] {api_url} → {e}")
    return None


def fetch(company_cfg: dict) -> list[dict]:
    api_url = company_cfg.get("url", "")
    name = company_cfg.get("name", "Unknown")
    if not api_url:
        logger.warning(f"[workday] {name} missing url in companies.yaml")
        return []

    all_jobs = []
    offset = 0
    while True:
        page = _post_page(api_url, offset)
        if not page:
            break
        postings = page.get("jobPostings", [])
        if not postings:
            break

        base = api_url.split("/wday/")[0]
        for item in postings:
            ext_path = item.get("externalPath", "")
            slug = ext_path.split("/")[-1] if ext_path else str(offset)
            loc = item.get("locationsText") or item.get("locations") or ""
            if isinstance(loc, list):
                loc = ", ".join(loc)
            loc = _normalize_workday_location(loc)
            all_jobs.append({
                "job_id": f"workday-{name.lower().replace(' ', '-')}-{slug}",
                "company": name,
                "title": item.get("title", ""),
                "location": loc,
                "posted_at": _parse_posted_on(item.get("postedOn")),
                "apply_url": base + ext_path if ext_path else "",
                "provider": "workday",
            })

        total = page.get("total", 0)
        offset += PAGE_SIZE
        if offset >= total:
            break

    logger.info(f"[workday] {name}: {len(all_jobs)} jobs")
    return all_jobs
