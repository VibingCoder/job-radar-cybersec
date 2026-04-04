"""
providers/__init__.py
Registry mapping provider name → fetch function.
Each fetch(company_cfg) returns list[dict] of normalized job dicts.

Normalized schema:
    job_id      str   — unique ID (provider-prefixed)
    company     str   — company name
    title       str   — job title
    location    str   — location string
    posted_at   str   — ISO date or None
    apply_url   str   — direct apply link
    provider    str   — which ATS provider
"""

from providers.greenhouse import fetch as greenhouse_fetch
from providers.lever import fetch as lever_fetch
from providers.ashby import fetch as ashby_fetch
from providers.smartrecruiters import fetch as smartrecruiters_fetch
from providers.workday import fetch as workday_fetch
from providers.uber import fetch as uber_fetch

REGISTRY: dict = {
    "greenhouse": greenhouse_fetch,
    "lever": lever_fetch,
    "ashby": ashby_fetch,
    "smartrecruiters": smartrecruiters_fetch,
    "workday_url": workday_fetch,
    "uber": uber_fetch,
}


def get_provider(name: str):
    fn = REGISTRY.get(name)
    if fn is None:
        raise ValueError(f"Unknown provider: {name!r}. Available: {list(REGISTRY)}")
    return fn
