# Adding CMG, LinkedIn and Handshake

These three sit behind logins, so the radar never signs in to them or scrapes them. It uses the
doors each site already gives you: the job-alert emails they send, and (for CMG) the cmg tool's
own copy or a quick paste. Turn on whichever you use.

| Source | Best way in | Works on GitHub | Works on a Mac |
|---|---|---|---|
| LinkedIn | Its job-alert emails | Yes | Yes |
| Handshake | Its job-alert emails | Yes | Yes |
| CMG (12twenty) | The cmg tool's copy (if you use it), CMG emails, or paste a list into Claude | Emails only | All three |

## Step 1: get the sites to email you
- **LinkedIn:** search jobs with your keywords (for example "MBA intern product"), filter by date
  and location, then switch on **Set alert**. Choose daily, and email. Make one alert per search.
- **Handshake:** run your job search with filters, then **Save search** and turn on its alerts
  (email). Handshake is used mostly by undergraduates, so it adds fewer MBA roles.
- **CMG:** if CMG offers saved-search or new-posting emails for your filters, turn them on. CMG
  newsletters that link to postings are read too.

## Step 2: let the radar read those emails
The radar reads alert emails from your own inbox, using the same Gmail app password as email alerts.
1. The alerts must land in the Gmail the radar uses. If LinkedIn or CMG emails your school address,
   add a filter there that forwards those senders (`jobalerts-noreply@linkedin.com`,
   `joinhandshake.com`, `12twenty.com`) to your personal Gmail. Or change LinkedIn's email to your
   personal Gmail.
2. In my-radar.json:
   ```json
   "email_alerts": {"enabled": true, "from": ["linkedin", "handshake", "cmg"], "days": 3}
   ```
3. If the alerts go to a different Gmail than the one that sends your digest, add
   `RADAR_IMAP_USER` and `RADAR_IMAP_PASSWORD` (that account's app password).
4. Run `python3 scripts/radar.py scan`. Jobs from your alerts show "via LinkedIn alert" and are
   scored against your profile like everything else. Any other site that emails you jobs can be
   added with `"extra_senders": ["jobs@example.com"]`.

## CMG through the cmg tool (Mac)
If you already use the cmg tool (it keeps a copy of CMG on your Mac), set `"cmg_tool": true` in
my-radar.json. The radar reads that copy (`cmg jobs --json`), sends nothing to CMG, skips postings
past their deadline, and shows each deadline. It is only as fresh as your last `cmg sync`; the
radar never syncs for you, so follow the cmg tool's own rules for how often to sync.

## CMG, LinkedIn or anything else by paste (no setup)
Open the CMG job postings list (or any page of jobs), select the list, copy it, and paste it into
Claude with this prompt:

> These are job postings I copied from CMG. Using my internship radar profile, keep the ones that
> fit my industries, roles and cities, and add each one to my tracker with
> `python3 scripts/radar.py track "Company" "Role" "Link" --source CMG --deadline YYYY-MM-DD`.
> Then show me what you added and why you skipped the rest.

`track` writes to `my-tracker.csv` and, if Google Sheets is set up, adds the row to your sheet.

## Prompts for Claude, one per source
- **LinkedIn:** "Turn on LinkedIn job alerts in my radar. Walk me through creating the alerts on
  LinkedIn for my roles and cities, then set email_alerts in my-radar.json and run a test scan."
- **Handshake:** "Add Handshake to my radar. Tell me what to save as a search in Handshake, then
  turn on Handshake in email_alerts and test it."
- **CMG:** "Add CMG to my radar. If the cmg tool is installed, turn on cmg_tool and run a scan;
  otherwise set up CMG emails in email_alerts and show me the paste prompt for the rest."
- **Forwarding:** "My LinkedIn alerts go to my school email. Write the Gmail filter that forwards
  them to my personal Gmail, step by step."

What stays off-limits: signing in to CMG, LinkedIn or Handshake on your behalf, or collecting pages
behind your login on a schedule. Those sites forbid it, and it can get an account locked.
