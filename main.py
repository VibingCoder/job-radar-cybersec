#!/usr/bin/env python3
"""
Job Radar - Stage 1
Fetches new grad SWE jobs from ATS providers, filters them, diffs against
last run, and saves new jobs to jobs.json.

Usage:
    python main.py                        # full run
    python main.py --dry-run             # run without saving state or notifying
    python main.py --company "Stripe"    # test a single company
    python main.py --provider greenhouse # test all greenhouse companies
"""

import argparse
import concurrent.futures
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure stdout handles Unicode (emojis) on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import yaml

from providers import get_provider
from providers.adzuna import fetch_jobs as adzuna_fetch
from filter import passes_filter
from diff import find_new_jobs, save_state
from notify import notify

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("job_radar")

COMPANIES_FILE = os.environ.get("COMPANIES_FILE", "companies.yaml")
STATE_FILE = os.environ.get("JOB_RADAR_STATE", "state/jobs_seen.json")
NEW_JOBS_FILE = os.environ.get("JOB_RADAR_OUTPUT", "state/new_jobs.json")
MAX_WORKERS = int(os.environ.get("JOB_RADAR_WORKERS", "10"))


def load_companies(path: str = COMPANIES_FILE) -> list[dict]:
    with open(path) as f:
        data = yaml.safe_load(f)
    return data.get("companies", [])


def fetch_company(company_cfg: dict) -> list[dict]:
    provider_name = company_cfg.get("provider")
    try:
        fetch_fn = get_provider(provider_name)
        return fetch_fn(company_cfg)
    except ValueError as e:
        logger.warning(str(e))
        return []
    except Exception as e:
        logger.error(f"Error fetching {company_cfg.get('name')}: {e}")
        return []


def save_new_jobs(jobs: list[dict], path: str = NEW_JOBS_FILE) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "count": len(jobs),
            "jobs": jobs,
        }, f, indent=2, default=str)
    logger.info(f"New jobs saved to {path}")


def run(dry_run: bool = False, filter_company: str = None, filter_provider: str = None):
    companies = load_companies()

    if filter_company:
        companies = [c for c in companies if c.get("name", "").lower() == filter_company.lower()]
        if not companies:
            logger.error(f"Company '{filter_company}' not found in companies.yaml")
            sys.exit(1)

    if filter_provider:
        companies = [c for c in companies if c.get("provider", "").lower() == filter_provider.lower()]
        if not companies:
            logger.error(f"No companies with provider '{filter_provider}' found")
            sys.exit(1)

    logger.info(f"Scanning {len(companies)} companies...")

    all_jobs: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(fetch_company, c): c for c in companies}
        for future in concurrent.futures.as_completed(futures):
            try:
                jobs = future.result()
                all_jobs.extend(jobs)
            except Exception as e:
                company = futures[future]
                logger.error(f"Unhandled error for {company.get('name')}: {e}")

    # Adzuna aggregator (runs unless filtering by a specific company)
    if not filter_company and not filter_provider:
        adzuna_jobs = adzuna_fetch()
        all_jobs.extend(adzuna_jobs)

    logger.info(f"Total fetched (pre-filter): {len(all_jobs)}")

    filtered = [j for j in all_jobs if passes_filter(j)]
    logger.info(f"After filter: {len(filtered)}")

    new_jobs, new_state = find_new_jobs(filtered, state_path=STATE_FILE)
    logger.info(f"New (not seen before): {len(new_jobs)}")

    if new_jobs:
        print(f"\n{'='*60}")
        print(f"  {len(new_jobs)} NEW JOB(S) FOUND")
        print(f"{'='*60}\n")
        for job in new_jobs:
            print(f"  {job['company']} — {job['title']}")
            print(f"  📍 {job.get('location') or 'N/A'}")
            print(f"  🔗 {job.get('apply_url') or 'N/A'}")
            posted = str(job.get('posted_at') or '')[:10]
            if posted:
                print(f"  📅 {posted}")
            print()

        if not dry_run:
            save_new_jobs(new_jobs)
            save_state(new_state, path=STATE_FILE)
            notify(new_jobs)
        else:
            logger.info("[DRY RUN] State not saved, no notification sent.")
    else:
        logger.info("No new jobs found.")
        if not dry_run:
            save_state(new_state, path=STATE_FILE)


def main():
    parser = argparse.ArgumentParser(description="Job Radar — ATS watcher for new grad SWE roles")
    parser.add_argument("--dry-run", action="store_true", help="Run without saving state or notifying")
    parser.add_argument("--company", type=str, default=None, help="Test a single company by name")
    parser.add_argument("--provider", type=str, default=None, help="Test all companies for a specific provider")
    args = parser.parse_args()
    run(dry_run=args.dry_run, filter_company=args.company, filter_provider=args.provider)


if __name__ == "__main__":
    main()
