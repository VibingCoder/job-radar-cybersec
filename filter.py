"""
filter.py
Filters job postings to keep only US-based, entry-level (0-2 yrs)
cybersecurity / offensive security / AppSec roles. Excludes senior, staff, intern, etc.
"""

import html
import re
from typing import Optional

# ── Minimum posting date — ignore anything older than this ───────────────────
MIN_POSTED_DATE = "2026-02-15"

# ── Core title patterns — cybersecurity / offensive security / AppSec ────────
TITLE_INCLUDE = [
    # Core security engineering
    r"\bsecurity engineer\b",
    r"\bapplication security engineer\b",
    r"\bappsec engineer\b",
    r"\bproduct security engineer\b",
    r"\bcloud security engineer\b",
    r"\bcybersecurity engineer\b",
    r"\binformation security engineer\b",
    r"\binfosec engineer\b",
    r"\bcyber defense engineer\b",
    r"\bsecurity automation engineer\b",
    r"\bvulnerability management engineer\b",
    # Offensive security (broadened — catches engineer, consultant, researcher, operator)
    r"\boffensive security\b",
    # Penetration testing
    r"\bpenetration tester\b",
    r"\bpentester\b",
    r"\bpen tester\b",
    r"\bethical hacker\b",
    # Red team / purple team
    r"\bred team\b",
    r"\bpurple team\b",
    # Adversary simulation
    r"\badversary emulation\b",
    r"\badversary simulation\b",
    r"\bthreat emulation\b",
    r"\bbreach and attack simulation\b",
    r"\bbas engineer\b",
    # Research-oriented
    r"\bsecurity researcher\b",
    r"\bvulnerability researcher\b",
    r"\bthreat researcher\b",
    r"\bmalware analyst\b",
    r"\bmalware researcher\b",
    r"\breverse engineer\b",
    r"\bexploit developer\b",
    # Detection / hunting / response
    r"\bdetection engineer\b",
    r"\bdetection and response engineer\b",
    r"\bthreat hunter\b",
    r"\bthreat hunting\b",
    r"\bsecurity content engineer\b",
    r"\bsecurity content developer\b",
    r"\bincident response\b",
    r"\bdfir\b",
    # Threat intelligence
    r"\bthreat intelligence\b",
    r"\bcti analyst\b",
    # Consulting / assessment
    r"\bsecurity consultant\b",
    # Analyst catch-all (entry-level at Expel, Huntress, etc.)
    r"\bsecurity analyst\b",
]

# ── Seniority / role exclusions ──────────────────────────────────────────────
TITLE_EXCLUDE = [
    # Seniority levels
    r"\bsenior\b",
    r"\bsr\.?\b",   # "Sr." / "Sr" abbreviation for Senior
    r"\bstaff\b",
    r"\bprincipal\b",
    r"\blead\b",
    r"\bmanager\b",
    r"\bdirector\b",
    r"\bvp\b",
    r"\bvice president\b",
    r"\barchitect\b",
    r"\bhead\b",        # Head of Red Team, Head of Offensive Security
    r"\biii\b",         # L3+ (senior equiv at many companies)
    r"\biv\b",          # L4+
    r"\b[345]\b",       # L3, L4, L5
    # Non-SWE roles that may contain "engineer"
    r"\bmachine learning engineer\b",
    r"\bml engineer\b",
    r"\bdata engineer\b",
    r"\bdata scientist\b",
    r"\bdevops engineer\b",
    r"\bsite reliability\b",
    r"\bsre\b",
    r"\bnetwork engineer\b",
    r"\bsolutions engineer\b",
    r"\bsales engineer\b",
    r"\bsupport engineer\b",
    # Employment type exclusions
    r"\bintern(ship)?\b",
    r"\bco.?op\b",
    r"\bpart.?time\b",
    r"\bcontract(or)?\b",
    r"\bfreelance\b",
]

# ── US location signals (allowlist) ──────────────────────────────────────────
US_SIGNALS = [
    "united states", "usa", "us-remote", "us remote",
    "new york", "san francisco", "bay area",
    "seattle", "austin", "los angeles", "boston",
    "chicago", "denver", "atlanta", "washington", "raleigh",
    "houston", "miami", "phoenix", "san jose", "san diego",
    "portland", "minneapolis", "detroit", "pittsburgh",
    "palo alto", "menlo park", "mountain view", "sunnyvale",
    "redwood city", "bellevue", "kirkland", "cambridge",
]

# Country-level blocklist — catches "Remote in Canada", "UK Remote", etc.
COUNTRY_BLOCKLIST = [
    "canada", "uk", "united kingdom", "india", "australia",
    "singapore", "germany", "ireland", "france", "netherlands",
    "europe", "emea", "apac", "latam",
    "romania", "spain", "brazil", "japan", "china", "mexico", "poland",
    "italy", "sweden", "luxembourg", "belgium", "switzerland",
    "israel", "korea", "taiwan", "new zealand", "south africa",
    "denmark", "norway", "finland", "austria", "portugal",
]

# Placeholder strings Greenhouse/ATS systems use when no location is set
PLACEHOLDER_LOCATIONS = {"", "n/a", "na", "location", "tbd", "tbc", "null", "none"}

# ── Clearance / citizenship exclusion ────────────────────────────────────────
# Roles requiring security clearances or US citizenship disqualify OPT/STEM OPT holders.
# Checked against both title and description (when available).
_CLEARANCE_EXCLUDE = re.compile(
    r'\bts[/\-]?sci\b'
    r'|\btop\s+secret\b'
    r'|\bsecret\s+clearance\b'
    r'|\bactive\s+clearance\b'
    r'|\bsecurity\s+clearance\s+required\b'
    r'|\bmust\s+(hold|have|obtain)\s+a?\s*(security\s+)?clearance\b'
    r'|\bclearable\b'
    r'|\bpolygraph\b'
    r'|\bus\s+citizen(ship)?\s+(only|required)\b'
    r'|\bmust\s+be\s+a?\s+us\s+citizen\b'
    r'|\bcitizenship\s+required\b'
    r'|\beligible\s+to\s+obtain\s+a?\s*(security\s+)?clearance\b',
    re.IGNORECASE,
)


def _requires_clearance(job: dict) -> bool:
    """Returns True if the job requires a security clearance or US citizenship."""
    title = job.get("title", "")
    description = _strip_html(job.get("description", ""))
    return bool(
        _CLEARANCE_EXCLUDE.search(title)
        or _CLEARANCE_EXCLUDE.search(description)
    )


# ── Description-based experience filter ──────────────────────────────────────
# Catches: "5+ years of experience", "minimum 3 years", "3 years of software experience"
_SENIOR_EXP = re.compile(
    r'\b([3-9]|\d{2,})\+?\s*(?:or\s+more\s+)?years?\s+(?:of\s+)?(?:\w+\s+){0,3}experience'
    r'|\b(?:minimum|at\s+least)\s+([3-9]|\d{2,})\+?\s*years?',
    re.IGNORECASE,
)
# Override: if the posting explicitly says it's entry-level / new grad, keep it
# even if it also mentions years elsewhere (e.g. "0-3 years")
_ENTRY_LEVEL_SIGNAL = re.compile(
    r'\b(?:new\s+grad(?:uate)?|entry.?level|0\s*[-–]\s*[1-3]\s+years?|junior)\b',
    re.IGNORECASE,
)


def _strip_html(text: str) -> str:
    """Remove HTML tags and decode entities to get plain text."""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html.unescape(text)
    return re.sub(r'\s+', ' ', text).strip()


def is_entry_level_description(description: str) -> bool:
    """
    Returns False if the description explicitly requires 3+ years of experience
    AND contains no entry-level / new-grad override signals.
    Returns True when no description is available (don't filter blind).
    """
    if not description:
        return True
    text = _strip_html(description)
    if _SENIOR_EXP.search(text) and not _ENTRY_LEVEL_SIGNAL.search(text):
        return False
    return True


def _match_any(text: str, patterns: list[str]) -> bool:
    t = text.lower()
    return any(re.search(p, t) for p in patterns)


def is_us_location(location: Optional[str]) -> bool:
    if not location:
        return True  # null/empty = unspecified, treat as remote
    loc = location.strip().lower()
    if loc in PLACEHOLDER_LOCATIONS:
        return True  # placeholder = no real location set, treat as remote
    # Country blocklist first — catches "Remote in Canada", "UK Remote", etc.
    if any(c in loc for c in COUNTRY_BLOCKLIST):
        return False
    # Then allowlist: include if explicit US city/signal found
    if any(sig in loc for sig in US_SIGNALS):
        return True
    # "remote" alone (no country qualifier) counts as US-eligible
    if re.search(r"\bremote\b", loc):
        return True
    return False


def is_relevant_title(title: str) -> bool:
    if not title:
        return False
    # Hard excludes first
    if _match_any(title, TITLE_EXCLUDE):
        return False
    # Must match a core SWE title
    if not _match_any(title, TITLE_INCLUDE):
        return False
    return True


def is_recent_enough(posted_at) -> bool:
    if not posted_at:
        return True  # no date info — include it
    date_str = str(posted_at)[:10]  # take YYYY-MM-DD portion
    try:
        return date_str >= MIN_POSTED_DATE
    except Exception:
        return True


def passes_filter(job: dict) -> bool:
    return (
        is_relevant_title(job.get("title", ""))
        and is_us_location(job.get("location"))
        and is_recent_enough(job.get("posted_at"))
        and is_entry_level_description(job.get("description", ""))
        and not _requires_clearance(job)
    )
