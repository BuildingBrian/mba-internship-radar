# Alerts: how the radar reaches you

The radar sends only when something new shows up (set `"send_when_quiet": true` in my-radar.json
if you also want a "nothing new" note). Pick one or more.

| Channel | What you get | Setup | Runs from GitHub | Runs from a Mac |
|---|---|---|---|---|
| **Email** | A short morning email | 5 min | Yes | Yes |
| **iMessage** | A text in Messages | 2 min | No | Yes, Mac must be on |
| **Google Sheets** | Each new match lands as a row with a Status column: your application tracker | 5 min | Yes | Yes |
| WhatsApp | A WhatsApp message (unofficial free service) | 5 min | Yes | Yes |
| Slack or Discord | A post in your own channel | 3 min | Yes | Yes |
| Phone push (ntfy app) | A notification, no account needed | 2 min | Yes | Yes |
| Just in Claude | You ask "run my radar" | none | | |

Plain SMS isn't offered: US carriers now require business registration for automated texts.
For a text-style alert use iMessage (Mac) or WhatsApp. Most people pick Email + Google Sheets.

## Where passwords go
Never put a password or token in `my-radar.json` or paste it into a chat. Put it in one of these:
- **GitHub:** your repository → Settings → Secrets and variables → Actions → New repository secret.
- **Your Mac:** a file named `radar.env` next to `my-radar.json`, one `NAME=value` per line (it is
  in `.gitignore`, so it never gets uploaded).

Then list the channel in my-radar.json → `"alerts": {"channels": [...]}` (names: email, imessage,
sheets, whatsapp, slack, discord, push) and check it:
`python3 scripts/radar.py channels`, then `python3 scripts/radar.py test-alert`.

## Email (Gmail as the sender)
1. Use a personal Gmail as the sender (school accounts often block app passwords). It needs
   2-Step Verification on.
2. Go to myaccount.google.com/apppasswords, create one called "Internship Radar", copy the 16 letters.
3. Secrets: `RADAR_SMTP_USER` = that Gmail · `RADAR_SMTP_PASSWORD` = the 16 letters, no spaces ·
   `RADAR_EMAIL_TO` = where the digest goes (your school address works; separate several with commas).
The same login also lets the radar read your LinkedIn, Handshake and CMG alert emails (SOURCES.md).

## iMessage (Mac only)
1. Your Mac must be signed in to Messages and on when the radar runs.
2. In `radar.env`: `RADAR_IMESSAGE_TO` = your phone number (+15105550123) or Apple ID email.
3. The first time, macOS asks whether Terminal (or Claude) may control Messages. Click OK.

## Google Sheets (your tracker)
1. Make a new Google Sheet, then Extensions → Apps Script.
2. Replace everything there with `templates/google-sheets-script.gs` and save.
3. Deploy → New deployment → type **Web app** → Execute as **Me** → Who has access **Anyone** → Deploy.
   Approve the access prompt (Google warns because you wrote the script yourself; that's expected).
4. Copy the Web app URL and save it as `RADAR_SHEETS_URL`. Treat it like a password: anyone with it
   can add rows.
5. Every new match becomes a row: date, score, company, role, location, link, source, and a
   Status menu (New, Interested, Applied, Interview, Offer, Not for me) plus a notes column.
   `radar.py track` adds anything else you find (CMG, referrals) to the same sheet.

## WhatsApp (unofficial)
CallMeBot is a free third-party service, not part of WhatsApp. Your digest passes through its
server and it can stop without notice, so keep email as a backup.
1. Follow the WhatsApp steps on callmebot.com (add their number, send the activation message).
2. Secrets: `RADAR_WHATSAPP_PHONE` (+15105550123) · `RADAR_CALLMEBOT_APIKEY`.

## Slack, Discord or phone push
- Slack: Apps → Incoming Webhooks → `RADAR_SLACK_WEBHOOK`. Discord: channel settings → Integrations →
  Webhooks → `RADAR_DISCORD_WEBHOOK`.
- Phone push: install the free ntfy app, subscribe to a long random topic name like
  `radar-alex-7q4m2x9k`, and save it as `RADAR_NTFY_TOPIC`.
