"""
diff.py
Compares freshly fetched jobs against the last saved snapshot.
Returns only jobs not seen before.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_STATE_FILE = "state/jobs_seen.json"


def load_state(path: str = DEFAULT_STATE_FILE) -> dict[str, dict]:
    p = Path(path)
    if not p.exists():
        logger.info(f"No state file found at {path} — treating all jobs as new.")
        return {}
    with open(p) as f:
        return json.load(f)


def save_state(jobs: dict[str, dict], path: str = DEFAULT_STATE_FILE) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(jobs, f, indent=2, default=str)
    logger.info(f"State saved: {len(jobs)} total jobs tracked in {path}")


def find_new_jobs(
    current_jobs: list[dict],
    state_path: str = DEFAULT_STATE_FILE,
) -> tuple[list[dict], dict[str, dict]]:
    """
    Returns:
        new_jobs   — jobs not in the previous snapshot
        new_state  — updated state dict to persist
    """
    seen = load_state(state_path)
    new_jobs = []
    updated_state = dict(seen)

    for job in current_jobs:
        jid = job.get("job_id")
        if not jid:
            continue
        if jid not in seen:
            new_jobs.append(job)
        updated_state[jid] = job

    return new_jobs, updated_state
