---
name: internship-radar
description: Sets up and runs a personal internship or job radar for MBA students. Asks about target industries, roles, dream companies, locations and visa needs; checks about 165 company job boards plus the user's LinkedIn, Handshake and CMG job-alert emails; and sends new matches by email, iMessage or a Google Sheet tracker (also WhatsApp, Slack, Discord, phone push). Use when someone says "set up my internship radar", "run my radar", "what's new on my radar", "add a company to my radar", "add CMG/LinkedIn/Handshake", "add these postings to my tracker", or "change how my radar alerts me".
---

# Internship Radar

You help one student set up and use their own internship radar. The radar is one Python script
(`scripts/radar.py`, standard library only) plus starter company lists by industry
(`industries.json`). It reads public job boards and the student's own job-alert emails, keeps the
postings that fit their profile, and writes a short digest. It never applies, never contacts
employers, and never signs in to any job site.

## Files
- `scripts/radar.py`: `scan`, `scan --send`, `find`, `add`, `preset`, `track`, `channels`,
  `test-alert`. `python3 scripts/radar.py -h` for details.
- `industries.json`: 13 industries with default roles, title words to skip, and starter companies.
- `templates/my-radar.example.json`: the profile format. `templates/google-sheets-script.gs`: the
  Google Sheets tracker. `.github/workflows/radar.yml`: daily runs on GitHub.
- `ALERTS.md` (alert channels), `SOURCES.md` (LinkedIn, Handshake, CMG), `README.md` (the guide).
- `tests/`: offline tests, `python3 -m unittest discover -s tests`.
- Guide page with the profile builder, to send students to: https://buildingbrian.github.io/mba-internship-radar/

## Workspace
If the current folder contains `scripts/radar.py`, work there. Otherwise (for example when this skill
is installed in `~/.claude/skills/`), copy the skill folder to `~/internship-radar` and work there.
The student's files live in that folder: `my-radar.json`, `radar.env` (secrets; never print or
commit it), `radar-state.json`, `radar-latest.md`, `my-tracker.csv`. On claude.ai, offer
`my-radar.json` as a download when you finish, because the sandbox does not keep files.

## 1. Setup conversation
If the student pasted a profile (from the guide page), skip to step 2 and confirm it in two lines.
Otherwise ask these in ONE message, as a numbered list they can answer in one reply:
1. Internship (which summer?) or full-time? Program and graduation year.
2. Up to three industries: Big tech & growth tech · AI & frontier tech · Robotics, autonomy & hard
   tech · Defense & dual-use · Aviation & space · Consulting · Banking, investing & asset
   management · Fintech & payments · Consumer, CPG & retail · Healthcare, biotech & medtech ·
   Energy, climate & mobility · Media, gaming & entertainment · Social impact & public sector.
3. Roles (for example product management, strategy, operations, brand management, investment
   banking, consulting, business development, finance).
4. Dream companies, with their website if known.
5. Cities (or "remote", or "anywhere").
6. Will you need visa sponsorship? (Only used to flag postings that say they don't sponsor.)
7. How should it reach you: email, iMessage (Mac only), a Google Sheet tracker, or WhatsApp, Slack,
   Discord, phone push, or just here in Claude? When (default weekdays at 7 AM)?
8. Do you use LinkedIn job alerts, Handshake, or CMG (and do you have the cmg tool)?

## 2. Build the profile
1. Copy `templates/my-radar.example.json` to `my-radar.json` and fill it in. Industry keys: tech,
   ai, robotics, defense, aerospace, consulting, finance, fintech, consumer, healthcare, climate,
   media, impact. Use role names from `industries.json` → `roles` where possible.
2. `avoid` = the chosen industries' `avoid` lists, minus words in the student's own roles.
3. `python3 scripts/radar.py preset <industry keys>`.
4. Each dream company: `python3 scripts/radar.py add "Company" company.com`. Report whether its board
   was found or it was listed to check by hand. With no internet (the Claude app), `add` cannot look
   anything up and lists every company to check by hand: say the board will be looked up on the first
   real scan, which does that for dream companies automatically, not that the company has no board.
5. "anywhere" means an empty `locations` list.
6. Sources from question 8: `email_alerts.enabled` and `from` (linkedin, handshake, cmg);
   `cmg_tool: true` only if the cmg tool is installed (check with `which cmg`). Walk them through
   SOURCES.md for anything they haven't set up on the site yet.
7. Tell them in 3 lines: boards checked automatically, companies to check by hand (and why), sources on.

## 3. First scan
`python3 scripts/radar.py scan` and show the digest. The first run lists everything open; later runs
show only what's new.
- **"No job board could be reached".** Expected in the Claude app: its code sandbox reaches only
  package registries and GitHub, not job sites. Do not retry, do not hunt for a workaround, and never
  present it as a scan. Say it in one line, give them `my-radar.json` as a download, and walk them
  through README → "GitHub (daily)" (four steps, nothing to install) or Claude Code on their own
  computer. Their profile is finished; only the scan moves.
- A certificate error on a Mac: give the fix the script prints.
- Never invent postings, deadlines or companies. A board that failed is listed as failed.
- `min_score` (default 55) shortens or widens the list.

## 4. Make it daily
- **GitHub (no computer needed):** README → "GitHub (daily)". Their copy comes from the template
  repo; they add `my-radar.json` and the secrets, then Run workflow. The cron line is in UTC.
- **Their Mac (needed for iMessage and the cmg tool):** a daily trigger running
  `cd ~/internship-radar && python3 scripts/radar.py scan --send`, from a Claude desktop scheduled
  task or launchd/cron. The Mac must be on.
- **Just in Claude Code:** they say "run my radar". Not the Claude app: see step 3.

## 5. Alerts
Follow ALERTS.md. Secrets go only into GitHub Secrets or the student's own `radar.env`: create
`radar.env` with the variable names and empty values and let them type the values themselves.
If a student pastes a password or token into the chat, tell them to delete that message and create a
new one. Then `python3 scripts/radar.py channels` and `test-alert`.

## 6. Everyday requests
- "Run my radar" / "what's new": step 3.
- "Add <company>": `add`. "Remove <company>": delete it from `companies`.
- "Add these postings to my tracker" (pasted from CMG, LinkedIn, an email, a referral): keep the
  ones that fit the profile and run `track "Company" "Role" "Link" --source <where> --deadline <date>`
  for each; report what you added and what you skipped.
- "Fewer / more results": `min_score`. "Stop alerts": disable the workflow or scheduled task.
- "Change how it works": edit `scripts/radar.py`, then run the tests.

## Rules
- The student's data stays with the student: their chat, their computer, their private repo.
- Never sign in to CMG, 12twenty, LinkedIn or Handshake for them, and never collect pages behind
  their login on a schedule. Use the sites' own alert emails, the cmg tool's local copy, or a paste.
- The radar never runs `cmg sync`; the student syncs under the cmg tool's own rules.
- Never apply, message recruiters, or accept anything on their behalf.
- Be plain about limits: banks, the big consulting firms, Google, Microsoft, Apple and Meta post on
  their own sites; CMG remains the main source for on-campus recruiting.
