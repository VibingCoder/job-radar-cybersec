"""
discover_companies.py
Tests candidate companies against Greenhouse, Lever, and Ashby APIs.
Prints which ones are valid (return jobs) vs 404/error.

Usage:
    python discover_companies.py

Add the working ones to companies.yaml manually.
"""

import json
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Candidate companies to test ───────────────────────────────────────────────

GREENHOUSE_CANDIDATES = [
    # AI / ML
    ("Cohere", "cohere"),
    ("Inflection AI", "inflectionai"),
    ("Mistral", "mistral"),
    ("Adept", "adept"),
    ("Character AI", "characterai"),
    ("Stability AI", "stabilityai"),
    # Fintech
    ("Plaid", "plaid"),
    ("Affirm", "affirm"),
    ("Marqeta", "marqeta"),
    ("Nerdwallet", "nerdwallet"),
    ("SoFi", "sofi"),
    ("Braintree", "braintree"),
    ("Rippling", "rippling"),
    # Infrastructure / Cloud
    ("HashiCorp", "hashicorp"),
    ("Pulumi", "pulumi"),
    ("Temporal", "temporal"),
    ("Cockroach Labs", "cockroachlabs"),
    ("PlanetScale", "planetscale"),
    ("Supabase", "supabase"),
    ("Neon", "neon"),
    # Security
    ("Snyk", "snyk"),
    ("Lacework", "lacework"),
    ("Orca Security", "orcasecurity"),
    ("Drata", "drata"),
    ("Vanta", "vanta"),
    # Dev Tools / Productivity
    ("Grammarly", "grammarly"),
    ("Airtable", "airtable"),
    ("Webflow", "webflow"),
    ("Retool", "retool"),
    ("Coda", "coda"),
    ("Loom", "loom"),
    ("Miro", "miro"),
    ("Figma", "figma"),
    ("Canva", "canva"),
    ("Superhuman", "superhuman"),
    # Data / Analytics
    ("dbt Labs", "dbtlabs"),
    ("Looker", "looker"),
    ("Amplitude", "amplitude"),
    ("Segment", "segment"),
    ("Mixpanel", "mixpanel"),
    ("ThoughtSpot", "thoughtspot"),
    # E-commerce / Marketplace
    ("Shopify", "shopify"),
    ("Faire", "faire"),
    ("Stitch Fix", "stitchfix"),
    ("Poshmark", "poshmark"),
    ("Etsy", "etsy"),
    # Health / Bio
    ("Flatiron Health", "flatironhealth"),
    ("Tempus", "tempus"),
    ("Benchling", "benchling"),
    ("Oscar Health", "oscarhealth"),
    # Enterprise SaaS
    ("Zendesk", "zendesk"),
    ("HubSpot", "hubspot"),
    ("Intercom", "intercom"),
    ("Lattice", "lattice"),
    ("Gong", "gong"),
    ("Braze", "braze"),
    ("Pagerduty", "pagerduty"),
    ("Okta", "okta"),
    ("Contentful", "contentful"),
    ("Sprinklr", "sprinklr"),
    ("Salesloft", "salesloft"),
    # Transportation / Logistics
    ("Flexport", "flexport"),
    ("Convoy", "convoy"),
    ("Nuro", "nuro"),
    # Other
    ("Strava", "strava"),
    ("Duolingo", "duolingo"),
    ("Coursera", "coursera"),
    ("Quora", "quora"),
    ("Medium", "medium"),
    ("Crunchbase", "crunchbase"),
    ("Yelp", "yelp"),
    ("Thumbtack", "thumbtack"),
    ("Lime", "lime"),
    ("Bird", "bird"),
    ("Weights & Biases", "wandb"),
    ("Hugging Face", "huggingface"),
    ("Together AI", "togetherai"),
    ("Mistral AI", "mistralai"),
    ("Groq", "groq"),
]

LEVER_CANDIDATES = [
    ("Anduril", "anduril"),
    ("Verkada", "verkada"),
    ("Figma", "figma"),
    ("Carta", "carta"),
    ("Scale AI", "scaleai"),
    ("Waymo", "waymo"),
    ("Nuro", "nuro"),
    ("Cruise", "cruise"),
    ("Aurora", "aurora"),
    ("Rivian", "rivian"),
    ("Lucid Motors", "lucidmotors"),
    ("SpaceX", "spacex"),
    ("Relativity Space", "relativityspace"),
    ("Astra", "astra"),
    ("Planet Labs", "planetlabs"),
    ("Brex", "brex"),
    ("Gusto", "gusto"),
    ("Rippling", "rippling"),
    ("Deel", "deel"),
    ("Remote", "remote"),
    ("Loom", "loom"),
    ("Notion", "notion"),
    ("Linear", "linear"),
    ("Airtable", "airtable"),
    ("Retool", "retool"),
    ("Hex", "hex"),
    ("Posthog", "posthog"),
    ("Descript", "descript"),
    ("Weights & Biases", "wandb"),
]

ASHBY_CANDIDATES = [
    # AI
    ("Mistral AI", "mistralai"),
    ("Groq", "groq"),
    ("Exa AI", "exa"),
    ("Together AI", "togetherai"),
    ("Imbue", "imbue"),
    ("Letta", "letta"),
    ("Dust", "dust"),
    ("LangChain", "langchain"),
    ("Vapi", "vapi"),
    ("Sierra", "sierra"),
    ("Writer", "writer"),
    ("Glean", "glean"),
    # Dev Tools
    ("Posthog", "posthog"),
    ("Supabase", "supabase"),
    ("Neon", "neon"),
    ("Turso", "turso"),
    ("Deno", "deno"),
    ("Zed", "zed"),
    ("Warp", "warp"),
    ("Raycast", "raycast"),
    ("Fig", "fig"),
    ("Arc Browser", "thebrowser"),
    ("Framer", "framer"),
    # Fintech / Enterprise
    ("Rippling", "rippling"),
    ("Brex", "brex"),
    ("Ramp", "ramp"),
    ("Mercury", "mercury"),
    ("Fintual", "fintual"),
    ("Drata", "drata"),
    ("Vanta", "vanta"),
    ("Anduril", "anduril"),
    ("Shield AI", "shieldai"),
    # Other
    ("Hex", "hex"),
    ("Retool", "retool"),
    ("Webflow", "webflow"),
    ("Airtable", "airtable"),
    ("Temporal", "temporal"),
    ("incident.io", "incidentio"),
    ("Cortex", "cortexapp"),
    ("Clerk", "clerk"),
    ("Descript", "descript"),
    ("Watershed", "watershed"),
]


# ── Test functions ────────────────────────────────────────────────────────────

def test_greenhouse(name: str, slug: str) -> tuple[str, str, str, int]:
    url = f"https://api.greenhouse.io/v1/boards/{slug}/jobs"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "JobRadar/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
            count = len(data.get("jobs", []))
            return ("greenhouse", name, slug, count)
    except urllib.error.HTTPError as e:
        return ("greenhouse", name, slug, -e.code)
    except Exception:
        return ("greenhouse", name, slug, -1)


def test_lever(name: str, slug: str) -> tuple[str, str, str, int]:
    url = f"https://api.lever.co/v0/postings/{slug}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "JobRadar/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
            return ("lever", name, slug, len(data))
    except urllib.error.HTTPError as e:
        return ("lever", name, slug, -e.code)
    except Exception:
        return ("lever", name, slug, -1)


def test_ashby(name: str, slug: str) -> tuple[str, str, str, int]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "JobRadar/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
            count = len(data.get("jobs", []))
            return ("ashby", name, slug, count)
    except urllib.error.HTTPError as e:
        return ("ashby", name, slug, -e.code)
    except Exception:
        return ("ashby", name, slug, -1)


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    tasks = []
    tasks += [(test_greenhouse, n, s) for n, s in GREENHOUSE_CANDIDATES]
    tasks += [(test_lever, n, s) for n, s in LEVER_CANDIDATES]
    tasks += [(test_ashby, n, s) for n, s in ASHBY_CANDIDATES]

    results = {"greenhouse": [], "lever": [], "ashby": []}
    failed = {"greenhouse": [], "lever": [], "ashby": []}

    print(f"Testing {len(tasks)} candidates...\n")

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(fn, name, slug): (fn, name, slug) for fn, name, slug in tasks}
        for future in as_completed(futures):
            provider, name, slug, count = future.result()
            if count >= 0:
                results[provider].append((name, slug, count))
                print(f"  OK  [{provider:10}] {name} ({slug}) — {count} jobs")
            else:
                failed[provider].append((name, slug, count))
                code = abs(count)
                print(f"  --  [{provider:10}] {name} ({slug}) — HTTP {code if code != 1 else 'error'}")

    print("\n" + "=" * 60)
    print("WORKING COMPANIES (add these to companies.yaml)")
    print("=" * 60)

    for provider, entries in results.items():
        if not entries:
            continue
        entries.sort(key=lambda x: -x[2])
        print(f"\n# {provider.upper()}")
        for name, slug, count in entries:
            print(f"  - name: {name}")
            print(f"    provider: {provider}")
            print(f"    id: {slug}   # {count} jobs")


if __name__ == "__main__":
    run()
