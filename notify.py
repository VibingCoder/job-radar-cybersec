"""
notify.py
Sends new job alerts to Discord via webhook.
Set DISCORD_WEBHOOK_URL environment variable to enable.
"""

import json
import logging
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
DISCORD_CHAR_LIMIT = 2000

_HIGH_PRIORITY_PATTERNS = re.compile(
    r'\b(?:red\s+team|offensive\s+security|penetration\s+test(?:er|ing)?'
    r'|pentester|pen\s+tester|vulnerability\s+researcher|exploit'
    r'|reverse\s+engineer|malware)\b',
    re.IGNORECASE,
)


def _is_high_priority(job: dict) -> bool:
    return bool(_HIGH_PRIORITY_PATTERNS.search(job.get("title", "")))


def _format_job(job: dict) -> str:
    company = job.get("company", "?")
    title = job.get("title", "?")
    location = job.get("location") or "Location N/A"
    url = job.get("apply_url", "")
    posted = str(job.get("posted_at") or "")[:10]
    priority_tag = "🔴 **HIGH PRIORITY** " if _is_high_priority(job) else ""
    line = f"{priority_tag}**{company}** — {title}\n📍 {location}"
    if posted:
        line += f"  📅 {posted}"
    if url:
        line += f"\n🔗 {url}"
    return line


def _build_messages(jobs: list[dict]) -> list[str]:
    header = (
        f"🚨 **{len(jobs)} new cybersecurity role(s) detected!**\n"
        f"_{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_\n\n"
    )
    messages = []
    current = header
    for job in jobs:
        block = _format_job(job) + "\n\n"
        if len(current) + len(block) > DISCORD_CHAR_LIMIT:
            messages.append(current.strip())
            current = block
        else:
            current += block
    if current.strip():
        messages.append(current.strip())
    return messages


def send_discord(jobs: list[dict], webhook_url: str = "") -> None:
    url = webhook_url or DISCORD_WEBHOOK_URL
    if not url:
        logger.warning("DISCORD_WEBHOOK_URL not set — skipping Discord notification.")
        return
    for message in _build_messages(jobs):
        payload = json.dumps({"content": message}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "JobRadar/1.0"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status not in (200, 204):
                    logger.error(f"Discord returned {resp.status}")
                else:
                    logger.info("Discord notification sent.")
        except Exception as e:
            logger.error(f"Discord send failed: {e}")


def notify(jobs: list[dict]) -> None:
    if not jobs:
        return
    send_discord(jobs)
