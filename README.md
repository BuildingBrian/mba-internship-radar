# Internship Radar

A free radar for your MBA internship search. Tell it your industries, roles, dream companies and
cities. Each morning it checks about 250 company job boards, plus your LinkedIn, Handshake and CMG
alerts, and sends you only the new postings that fit: by email, iMessage, or straight into a
Google Sheet that doubles as your application tracker.

Your copy is yours. Your profile and passwords stay in your own Claude chat, your own computer, or
your own private GitHub repository.

**Build your profile first (2 minutes):** https://claude.ai/artifact/JsVz8ZxENeRrujLM47bYhx

## What a morning alert looks like
```
Internship Radar for Alex · Tue Nov 10
3 new · 14 open matches · 36 boards checked · 9 jobs read from your alert emails

NEW
1. [95] NVIDIA: Product Management MBA Intern, Laptop - Summer 2027
   US, CA, Santa Clara · posted 2026-10-30
   https://nvidia.wd5.myworkdayjobs.com/...
2. [85] Adobe: 2027 MBA Intern - Corporate Strategy
   San Francisco · posted 2026-10-06 ⚠ deadline November 21, 2026
3. [70] Stripe: Strategy & Operations MBA Intern
   San Francisco, CA · via LinkedIn alert
```
The number is a fit score from 0 to 100. ⚠ marks a stated deadline, "no visa sponsorship", or
"may be undergrad-only".

## Pick how you run it

| | Claude app (web or desktop) | Claude Code | GitHub (daily, in the cloud) |
|---|---|---|---|
| You need | Paid Claude plan | Claude Code | Free GitHub account |
| Setup | Upload the skill, chat | Open the folder, chat | Use this template, add your profile |
| Daily alerts | Ask "run my radar" | Schedule it on your Mac | Automatic, laptop can be closed |
| iMessage | No | Yes | No |
| Best for | Trying it out | Changing anything you like | Set it and forget it |

Many people do both: set it up and customize it in Claude Code, then run it daily on GitHub.

### Claude app
Download `internship-radar-skill.zip` from this repo's **Releases**. In Claude: Settings →
Capabilities → turn on code execution → Skills → Upload skill → choose the zip. Start a new chat:
**"Set up my internship radar"**, then paste your profile from the guide page.

### Claude Code
Download or clone this repo, open the folder in Claude Code, and say **"Set up my internship
radar."** Claude reads `CLAUDE.md` and `SKILL.md`, builds your profile, runs your first scan, and can
change anything: new alert channels, scoring, schedules, sources. To use it as a skill from any
folder, put the repo at `~/.claude/skills/internship-radar`.

### GitHub (daily)
1. Click **Use this template → Create a new repository**, name it `internship-radar`, choose
   **Private**.
2. In your new repo: **Add file → Create new file**, name it `my-radar.json`, paste the file from
   the guide page (the "my-radar.json" tab), commit.
3. Add your alert secrets: **Settings → Secrets and variables → Actions → New repository secret**
   (names in [ALERTS.md](ALERTS.md)).
4. **Actions → Internship Radar → Run workflow.** The first digest arrives in about a minute, then
   every weekday at 7 AM Pacific. Change the time in `.github/workflows/radar.yml` (it is in UTC).

## Alerts and sources
- **[ALERTS.md](ALERTS.md):** Email, iMessage and Google Sheets, plus WhatsApp, Slack, Discord and
  phone push.
- **[SOURCES.md](SOURCES.md):** adding LinkedIn, Handshake and CMG through their job-alert emails,
  the cmg tool, or a paste into Claude, with ready-made prompts.

## What it covers, and what it doesn't
- **Job boards:** 173 company boards checked automatically across 13 industries: tech, AI,
  robotics, defense, aerospace, fintech, climate, media, healthcare, consumer, consulting, finance
  and impact. Add any company with `python3 scripts/radar.py add "Company" company.com`.
- **Check by hand:** most banks, McKinsey, BCG and Bain, and Google, Microsoft, Apple and Meta post
  on their own sites. The radar lists them every Monday with links.
- **LinkedIn, Handshake, CMG:** through their own alert emails and the cmg tool, never by signing in.
- It never applies for you. CMG stays the main source for on-campus recruiting and firm deadlines.

## Changing it
- Ask Claude: "add Patagonia", "New York only", "fewer results", "switch alerts to iMessage",
  "add the consulting list", "add these CMG postings to my tracker".
- Or edit `my-radar.json`: roles, words to skip, cities, `min_score` (default 55), companies.
- The code is one file, `scripts/radar.py`, standard-library Python. Tests:
  `python3 -m unittest discover -s tests`.
- Share new companies with the class: open an issue or pull request on the template repo.

## Common questions
- **Cost?** Free. GitHub's free plan covers daily runs.
- **Too many or too few results?** Change `min_score`, or tell Claude "fewer results".
- **Need visa sponsorship?** Say so in your profile. Postings that say they don't sponsor get a ⚠.
- **Stop it?** GitHub → Actions → Internship Radar → ··· → Disable workflow.

Built by Brian Arévalo (Haas FTMBA '28). MIT license: copy it, change it, share it.
