"""
providers/uber.py
Uber Careers — uses Playwright to fetch jobs via Uber's internal API.
Uber uses a custom careers page with session-based auth, so a real
browser is required to collect the correct cookies and CSRF tokens.

Normalized schema output matches the job_radar standard:
    job_id, company, title, location, posted_at, apply_url, provider, description
"""

import json
import logging
import re
import time

from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

UBER_API_URL = "https://www.uber.com/api/loadSearchJobsResults?localeCode=en"
UBER_CAREERS_BASE = "https://www.uber.com/global/en/careers/list"
LINE_OF_BUSINESS = "Corporate"
SEARCH_QUERY = "Security Engineer"
PAGE_LIMIT = 10

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}

INCLUDE_TITLE_KEYWORDS = [
    "security engineer",
    "application security",
    "appsec",
    "product security",
    "offensive security",
    "penetration tester",
    "red team",
    "detection engineer",
    "vulnerability researcher",
    "security researcher",
    "incident response",
    "malware",
    "reverse engineer",
    "cybersecurity",
]

EXCLUDE_TITLE_KEYWORDS = [
    "staff", "principal", "distinguished",
    "senior", "sr ", "sr.", "sr,", "- sr", "senior staff",
    "vp ", "vice president", "director", "manager", "head of", "lead",
    "machine learning", " ml ", "ml engineer", "ai ", "- ai", "/ ai",
    "artificial intelligence", "generative ai", "genai", "michelangelo", "llm",
    "intern", "internship", "co-op",
    "data engineer",
    "android", "ios", "frontend", "front-end", "front end", "operations",
]

US_INDICATORS = [
    "usa", "united states", "us ", " us,",
    "new york", "san francisco", "seattle", "austin", "chicago",
    "boston", "los angeles", "denver", "atlanta", "miami",
    "sunnyvale", "mountain view", "palo alto", "menlo park",
    "bellevue", "redmond", "portland", "phoenix", "dallas",
    "washington dc", "washington, dc", "remote",
    ", ca", ", ny", ", wa", ", tx", ", il", ", ma", ", co",
    ", ga", ", fl", ", or", ", az", ", nc", ", va", ", pa",
]

YOE_PATTERNS = [
    r"(\d+)\+\s*years?\s+(?:of\s+)?(?:experience|exp)",
    r"(\d+)\s*[-–]\s*\d+\s*years?\s+(?:of\s+)?(?:experience|exp)",
    r"(?:at least|minimum|min\.?)\s+(\d+)\s*years?\s+(?:of\s+)?(?:experience|exp)",
    r"(\d+)\s*years?\s+(?:of\s+)?(?:professional\s+)?(?:experience|exp)",
    r"(\d+)\s*\+\s*yrs",
    r"(\d+)\s*years?\s+(?:of\s+)?(?:relevant|industry|work)\s+(?:experience|exp)",
]

MAX_YEARS_EXPERIENCE = 2


# ── Helpers ──────────────────────────────────────────────────────────────────

def _parse_total(raw) -> int:
    """Uber encodes totals as protobuf-style dicts: {'low': N, 'high': 0}"""
    if isinstance(raw, dict):
        return raw.get("low", 0)
    return int(raw or 0)


def _passes_title(title: str) -> bool:
    t = title.lower()
    if not any(kw in t for kw in INCLUDE_TITLE_KEYWORDS):
        return False
    if any(kw in t for kw in EXCLUDE_TITLE_KEYWORDS):
        return False
    return True


def _passes_location(location: str) -> bool:
    loc = location.lower()
    if not loc or loc in ("", "unknown"):
        return True
    return any(indicator in loc for indicator in US_INDICATORS)


def _extract_min_yoe(description: str) -> int | None:
    text = description.lower()
    found = []
    for pattern in YOE_PATTERNS:
        for match in re.finditer(pattern, text):
            try:
                years = int(match.group(1))
                if 0 < years <= 20:
                    found.append(years)
            except (IndexError, ValueError):
                pass
    return min(found) if found else None


def _passes_yoe(description: str) -> bool:
    if not description:
        return True
    min_years = _extract_min_yoe(description)
    if min_years is None:
        return True
    return min_years <= MAX_YEARS_EXPERIENCE


# ── Playwright fetch ──────────────────────────────────────────────────────────

def _fetch_all_jobs(browser_context) -> list[dict]:
    """
    Loads Uber's careers page in a real browser, intercepts the page-0 API
    response, then POSTs subsequent pages via browser fetch() (so session
    cookies are automatically included).
    """
    careers_url = (
        f"https://www.uber.com/us/en/careers/list/"
        f"?query={SEARCH_QUERY.replace(' ', '%20')}"
        f"&lineOfBusinessName={LINE_OF_BUSINESS}"
    )

    all_results = []
    total_available = 0

    page = browser_context.new_page()

    def on_response(response):
        nonlocal total_available
        if "loadSearchJobsResults" not in response.url or response.status != 200:
            return
        try:
            body = response.json()
            data = body.get("data", {})
            results = data.get("results", [])
            raw_total = data.get("totalResults", 0)
            if raw_total:
                total_available = _parse_total(raw_total)
            all_results.extend(results)
            logger.info(f"[uber] page-0 intercept: +{len(results)} jobs, total={total_available}")
        except Exception as e:
            logger.warning(f"[uber] could not parse page-0 response: {e}")

    page.on("response", on_response)

    logger.info(f"[uber] loading careers page...")
    try:
        page.goto(careers_url, wait_until="networkidle", timeout=60_000)
    except Exception as e:
        logger.warning(f"[uber] page load warning: {e}")
    time.sleep(3)

    if not total_available:
        logger.error("[uber] no API response intercepted — careers page may have changed")
        page.close()
        return []

    total_pages = (total_available + PAGE_LIMIT - 1) // PAGE_LIMIT
    logger.info(f"[uber] {total_available} total jobs across {total_pages} page(s)")

    for pg in range(1, total_pages):
        if len(all_results) >= total_available:
            break

        post_body = json.dumps({
            "limit": PAGE_LIMIT,
            "page": pg,
            "params": {
                "lineOfBusinessName": [LINE_OF_BUSINESS],
                "query": SEARCH_QUERY,
            }
        })

        try:
            result = page.evaluate(f"""
                async () => {{
                    const resp = await fetch({json.dumps(UBER_API_URL)}, {{
                        method: "POST",
                        credentials: "include",
                        headers: {{
                            "content-type": "application/json",
                            "x-csrf-token": "x",
                            "x-uber-sites-page-edge-cache-enabled": "true"
                        }},
                        body: {json.dumps(post_body)}
                    }});
                    const ct = resp.headers.get("content-type") || "";
                    if (!ct.includes("json")) {{
                        const txt = await resp.text();
                        throw new Error("Non-JSON (" + resp.status + "): " + txt.substring(0, 120));
                    }}
                    return await resp.json();
                }}
            """)
            data = result.get("data", {})
            results = data.get("results", [])
            if not results:
                logger.info(f"[uber] no results on page {pg} — stopping early")
                break
            all_results.extend(results)
            logger.info(f"[uber] page {pg}: +{len(results)} (running: {len(all_results)}/{total_available})")
        except Exception as e:
            logger.error(f"[uber] failed on page {pg}: {e}")
            break

        time.sleep(0.3)

    page.close()

    # Deduplicate by id
    seen_ids: set[str] = set()
    unique = []
    for item in all_results:
        jid = str(item.get("id", ""))
        if jid and jid not in seen_ids:
            seen_ids.add(jid)
            unique.append(item)

    logger.info(f"[uber] {len(unique)} unique jobs fetched")
    return unique


def _parse_job(item: dict) -> dict:
    job_id = str(item.get("id", ""))
    title = item.get("title", "").strip()

    location_raw = item.get("location", "") or item.get("allLocations", "")
    if isinstance(location_raw, list):
        location = ", ".join(str(l) for l in location_raw)
    elif isinstance(location_raw, dict):
        location = location_raw.get("name") or location_raw.get("city") or str(location_raw)
    else:
        location = str(location_raw)

    return {
        "job_id": f"uber-{job_id}",
        "company": "Uber",
        "title": title,
        "location": location,
        "posted_at": None,
        "apply_url": f"{UBER_CAREERS_BASE}/{job_id}/",
        "provider": "uber",
        "description": item.get("description", ""),
        "_uber_id": job_id,
    }


def _scrape_description(job_id: str, browser_context) -> str:
    url = f"{UBER_CAREERS_BASE}/{job_id}/"
    page = browser_context.new_page()
    description = ""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        time.sleep(2)
        for sel in [
            "[data-testid='job-description']",
            "[class*='JobDescription']",
            "[class*='job-description']",
            "[class*='description']",
            "div[class*='content']",
            "main",
        ]:
            el = page.query_selector(sel)
            if el:
                text = el.inner_text().strip()
                if len(text) > 200:
                    description = text
                    break
        if not description:
            description = page.evaluate("() => document.body.innerText") or ""
    except Exception as e:
        logger.warning(f"[uber] could not scrape job {job_id}: {e}")
    finally:
        page.close()
    return description


# ── Provider entry point ──────────────────────────────────────────────────────

def fetch(company_cfg: dict) -> list[dict]:
    """
    job_radar provider interface. Launches a Playwright browser, fetches
    all Uber Software Engineer jobs, applies title + location + YOE filters,
    and returns normalized job dicts.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=HEADERS["User-Agent"],
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )

        raw_items = _fetch_all_jobs(context)
        if not raw_items:
            browser.close()
            return []

        jobs = [_parse_job(item) for item in raw_items if item.get("id") and item.get("title")]

        # Title + location pre-filter (before scraping to minimize page loads)
        candidates = [j for j in jobs if _passes_title(j["title"]) and _passes_location(j["location"])]
        logger.info(f"[uber] {len(candidates)} jobs pass title+location filter (from {len(jobs)} total)")

        # Scrape description for jobs where the API description is too short
        final = []
        for i, job in enumerate(candidates, 1):
            desc = job.get("description", "")
            if not desc or len(desc) < 100:
                logger.info(f"[uber] [{i}/{len(candidates)}] scraping: {job['title']}")
                desc = _scrape_description(job["_uber_id"], context)
                job["description"] = desc

            if _passes_yoe(desc):
                final.append(job)
            else:
                min_yoe = _extract_min_yoe(desc)
                logger.info(f"[uber] skip (requires {min_yoe}yr): {job['title']}")

        browser.close()

    # Clean up internal field before returning
    for job in final:
        job.pop("_uber_id", None)

    logger.info(f"[uber] {len(final)} jobs after all filters")
    return final
