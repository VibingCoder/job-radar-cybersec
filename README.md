# Job Radar 🎯

Monitors ATS job boards for new grad SWE/SDE/Backend/Fullstack roles in the US.
Notifies via Discord when new roles are detected.

---

## Quick Start (Local)

```bash
# 1. Setup
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Test a single company (no Discord needed)
python main.py --company "Stripe" --dry-run

# 3. Test a full provider
python main.py --provider greenhouse --dry-run

# 4. Full run (all companies)
python main.py --dry-run
```

---

## Discord Setup

1. Create a Discord server (or use existing)
2. Create a channel → Edit → Integrations → Webhooks → New Webhook → Copy URL
3. Set the environment variable:

```bash
# Mac/Linux
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN"

# Windows
set DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN
```

Then run without `--dry-run` to get real notifications.

---

## GitHub Actions (Always-On, Free)

1. Push this repo to GitHub (public repo = unlimited Actions minutes)
2. Go to Settings → Secrets → Actions → New secret
3. Add `DISCORD_WEBHOOK_URL` with your webhook URL
4. Go to Actions tab → enable workflows
5. Run manually first to test: Actions → Job Radar → Run workflow

Runs every 30 minutes automatically after that.

---

## Adding Companies

Edit `companies.yaml`. Each entry:

```yaml
# Greenhouse
- name: Company Name
  provider: greenhouse
  id: board-token        # from boards.greenhouse.io/{token}

# Lever
- name: Company Name
  provider: lever
  id: company-slug       # from jobs.lever.co/{slug}

# Ashby
- name: Company Name
  provider: ashby
  id: company-slug       # from jobs.ashbyhq.com/{slug}

# Workday
- name: Company Name
  provider: workday_url
  url: https://tenant.wd5.myworkdayjobs.com/wday/cxs/tenant/Board/jobs
```

---

## Stage Roadmap

- [x] Stage 1 — Greenhouse, Lever, Ashby, SmartRecruiters, Workday providers
- [x] Stage 2 — Filter (US only, new grad, no senior/intern/staff)
- [x] Stage 3 — Diff engine (only alert on new jobs)
- [x] Stage 4 — Discord notifications
- [x] Stage 5 — GitHub Actions deployment
- [ ] Stage 6 — Amazon, Google, Microsoft custom providers
- [ ] Stage 7 — Meta GraphQL provider
- [ ] Stage 8 — HTML scraping for Intuit, Tesla, Apple

---

## File Structure

```
job_radar/
├── main.py               # orchestrator
├── filter.py             # title + location filtering  
├── diff.py               # new job detection
├── notify.py             # Discord notifications
├── companies.yaml        # company list
├── requirements.txt
├── state/
│   ├── jobs_seen.json    # auto-generated, tracks seen jobs
│   └── new_jobs.json     # auto-generated, latest new jobs found
└── providers/
    ├── __init__.py
    ├── greenhouse.py
    ├── lever.py
    ├── ashby.py
    ├── smartrecruiters.py
    └── workday.py
```
