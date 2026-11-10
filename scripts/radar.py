#!/usr/bin/env python3
"""Internship Radar: watch company job boards for the internships or jobs you want, and get
a short digest by email, Telegram, phone push (ntfy), iMessage, WhatsApp, Slack or Discord.

  python3 radar.py scan                    check every board in my-radar.json, print the digest
  python3 radar.py scan --send             ...and send it on the channels you set up
  python3 radar.py scan --send --dry       show what would be sent, send nothing
  python3 radar.py find "Stripe" stripe.com    look up a company's job board
  python3 radar.py add "Stripe" stripe.com     look it up and add it to my-radar.json
  python3 radar.py preset tech consulting      add an industry's starter companies
  python3 radar.py track "Co" "Role" URL   add one posting to your tracker (CMG, referrals, anything)
  python3 radar.py channels                which alert channels are set up
  python3 radar.py test-alert              send a one-line test on every channel you set up

Besides company job boards, the radar can read the job-alert emails LinkedIn, Handshake and
CMG (12twenty) send you, and the local copy kept by the cmg tool. See SOURCES.md.

Standard library only (Python 3.9+). Passwords and tokens come from environment variables or
a radar.env file next to the profile (see ALERTS.md), never from my-radar.json.
"""
import argparse
import csv
import email
import email.policy
import gzip
import imaplib
import html
import json
import os
import re
import smtplib
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText

HERE = os.path.dirname(os.path.abspath(__file__))
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
NO_RETRY = {400, 401, 403, 404, 405, 410, 422}


# --- HTTP ---------------------------------------------------------------------

def _ssl_ctx():
    try:
        import certifi  # present on most Python installs; fixes python.org builds on a Mac
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        return ssl.create_default_context()


CTX = _ssl_ctx()
CERT_HELP = ("Python cannot verify HTTPS certificates on this computer. On a Mac, open your Python "
             "folder in Applications and double-click 'Install Certificates.command', or run "
             "'pip3 install certifi', then try again.")


def fetch(url, data=None, timeout=30, retries=2, headers=None):
    body = json.dumps(data).encode() if data is not None else None
    h = {"User-Agent": UA, "Accept": "application/json, text/html, */*", "Accept-Encoding": "gzip"}
    if body is not None:
        h["Content-Type"] = "application/json"
    h.update(headers or {})
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, data=body, headers=h, method="POST" if body else "GET")
            with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                return raw.decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            last = e
            if e.code in NO_RETRY:
                break
        except urllib.error.URLError as e:
            if isinstance(e.reason, ssl.SSLCertVerificationError):
                raise SystemExit(CERT_HELP) from None
            last = e
        except Exception as e:  # noqa: BLE001
            last = e
        time.sleep(1.5 * (attempt + 1))
    raise last


def get_json(url, **kw):
    return json.loads(fetch(url, **kw))


def text(s):
    if not s:
        return ""
    s = html.unescape(s)
    s = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</h\d>", "\n", s)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    return re.sub(r"\n\s*\n+", "\n", re.sub(r"[ \t\r\f\v]+", " ", s)).strip()


def day(s):
    s = re.sub(r"\s+", " ", (s or "").strip())
    for fmt in ("%Y-%m-%d", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(s[:10] if fmt == "%Y-%m-%d" else s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


def job(jid, title, location, url, posted="", desc=""):
    return {"id": str(jid), "title": (title or "").strip(), "location": (location or "").strip(),
            "url": url or "", "posted": day(posted), "desc": desc or ""}


# --- Job boards ---------------------------------------------------------------
# Each reader takes a company entry and returns a list of jobs. A reader that fails raises,
# so the digest can say "board failed" instead of quietly reporting zero jobs.

def greenhouse(c, q):
    d = get_json(f"https://boards-api.greenhouse.io/v1/boards/{c['token']}/jobs?content=true", timeout=60)
    return [job(j["id"], j.get("title"), (j.get("location") or {}).get("name"), j.get("absolute_url"),
                j.get("first_published") or j.get("updated_at") or "", text(j.get("content")))
            for j in d.get("jobs", [])]


def lever(c, q):
    d = get_json(f"https://api.lever.co/v0/postings/{c['token']}?mode=json", timeout=60)
    out = []
    for j in d:
        posted = ""
        if j.get("createdAt"):
            posted = datetime.fromtimestamp(j["createdAt"] / 1000, timezone.utc).strftime("%Y-%m-%d")
        parts = [j.get("descriptionPlain") or ""]
        for lst in j.get("lists") or []:
            parts += [lst.get("text", ""), text(lst.get("content", ""))]
        parts.append(j.get("additionalPlain") or "")
        out.append(job(j["id"], j.get("text"), (j.get("categories") or {}).get("location"),
                       j.get("hostedUrl"), posted, "\n".join(p for p in parts if p)))
    return out


def ashby(c, q):
    d = get_json(f"https://api.ashbyhq.com/posting-api/job-board/{c['token']}", timeout=60)
    out = []
    for j in d.get("jobs", []):
        if j.get("isListed") is False:
            continue
        locs = [j.get("location") or ""] + [s.get("location", "") for s in j.get("secondaryLocations") or []]
        out.append(job(j["id"], j.get("title"), "; ".join(x for x in locs if x), j.get("jobUrl"),
                       j.get("publishedAt") or "", j.get("descriptionPlain") or text(j.get("descriptionHtml"))))
    return out


def _wd(c):
    return f"https://{c['tenant']}.{c['pod']}.myworkdayjobs.com"


def workday(c, q):
    base, seen, out = _wd(c), set(), []
    api = f"{base}/wday/cxs/{c['tenant']}/{c['site']}/jobs"
    for term in c.get("queries") or q:
        for page in range(4):
            d = get_json(api, data={"appliedFacets": {}, "limit": 20, "offset": page * 20, "searchText": term}, timeout=45)
            if not isinstance(d.get("total"), int):
                raise ValueError("workday: unexpected response")
            posts = d.get("jobPostings") or []
            for j in posts:
                path = j.get("externalPath") or ""
                if path and path not in seen:
                    seen.add(path)
                    out.append(job(path, j.get("title"), j.get("locationsText"), f"{base}/en-US/{c['site']}{path}",
                                   ""))
            if len(posts) < 20:
                break
    return out


def workday_detail(c, j):
    d = get_json(f"{_wd(c)}/wday/cxs/{c['tenant']}/{c['site']}{j['id']}", timeout=45)
    info = d.get("jobPostingInfo") or {}
    j["posted"] = day(info.get("startDate"))
    return text(info.get("jobDescription"))


def smartrecruiters(c, q):
    api = f"https://api.smartrecruiters.com/v1/companies/{c['token']}/postings"
    seen, out = set(), []
    for term in c.get("queries") or q:
        d = get_json(f"{api}?limit=100&q={urllib.parse.quote(term)}", timeout=45)
        for j in d.get("content", []):
            if j["id"] in seen:
                continue
            seen.add(j["id"])
            loc = j.get("location") or {}
            where = ", ".join(x for x in (loc.get("city"), loc.get("region"), loc.get("country")) if x)
            out.append(job(j["id"], j.get("name"), where + (" (remote)" if loc.get("remote") else ""),
                           f"https://jobs.smartrecruiters.com/{c['token']}/{j['id']}", j.get("releasedDate", "")))
    return out


def smartrecruiters_detail(c, j):
    d = get_json(f"https://api.smartrecruiters.com/v1/companies/{c['token']}/postings/{j['id']}", timeout=45)
    secs = (d.get("jobAd") or {}).get("sections") or {}
    return "\n".join(text((secs.get(k) or {}).get("text")) for k in ("jobDescription", "qualifications", "additionalInformation"))


def amazon(c, q):
    seen, out = set(), []
    terms = c.get("queries") or ["MBA " + t for t in q if t.lower() != "mba"] or ["MBA"]
    for term in terms:
        d = get_json("https://www.amazon.jobs/en/search.json?result_limit=100&sort=recent&base_query="
                     + urllib.parse.quote(term), timeout=45)
        for j in d.get("jobs", []):
            jid = j.get("id_icims") or j.get("id")
            if jid in seen:
                continue
            seen.add(jid)
            desc = "\n".join(text(j.get(k)) for k in ("description", "basic_qualifications", "preferred_qualifications"))
            out.append(job(jid, j.get("title"), j.get("normalized_location") or j.get("location"),
                           "https://www.amazon.jobs" + (j.get("job_path") or ""), j.get("posted_date", ""), desc))
    return out


# --- Haas CMG through the cmg tool (Mac only) -------------------------------------
# Reads the local copy the cmg tool keeps (`cmg jobs --json`): zero requests to 12twenty.
# It is only as fresh as your last `cmg sync`, and the radar never runs a sync for you.

CMG_LINK = os.environ.get("RADAR_CMG_LINK", "https://mba-haas-berkeley.12twenty.com/jobPostings#/jobPostings/{id}/details")


def cmg_tool(c, q):
    import shutil
    exe = shutil.which("cmg") or os.path.expanduser("~/.local/bin/cmg")
    if not os.path.exists(exe):
        raise RuntimeError("the cmg tool is not installed on this computer")
    out = subprocess.run([exe, "jobs", "--json"], capture_output=True, text=True, timeout=120)
    if out.returncode:
        raise RuntimeError("cmg jobs --json failed: " + (out.stderr or "").strip()[:120])
    rows = json.loads(out.stdout or "[]")
    jobs = []
    for r in rows if isinstance(rows, list) else []:
        if "closed" in str(r.get("StatusName") or "").lower():
            continue
        j = job(r.get("Id"), r.get("TitleDisplay") or r.get("JobTitle"), r.get("LocationDisplay"),
                CMG_LINK.format(id=r.get("Id")), r.get("CreateDate") or "", "")
        j["company"] = r.get("CompanyName") or ""
        dl = day(r.get("ApplicationDeadlineDate"))
        if dl and dl < datetime.now().strftime("%Y-%m-%d"):
            continue  # deadline passed
        if dl:
            j["deadline"] = dl
        jobs.append(j)
    return jobs


# --- Job-alert emails (LinkedIn, Handshake, CMG/12twenty, or any sender you add) -------
# The sites email you; the radar reads those emails from your own inbox over IMAP with the
# same Gmail app password used for email alerts. Nothing logs into LinkedIn, Handshake or CMG.

ALERT_SENDERS = {
    "linkedin": ["jobalerts-noreply@linkedin.com", "jobs-noreply@linkedin.com"],
    "handshake": ["joinhandshake.com"],
    "cmg": ["12twenty.com"],
}
JOB_LINKS = [
    ("linkedin", re.compile(r"https?://(?:www\.)?linkedin\.com/(?:comm/)?jobs/view/(\d+)")),
    ("handshake", re.compile(r"https?://[a-z.]*joinhandshake\.com/(?:stu/|e/|job-search/)?(?:jobs|postings)/(\d+)")),
    ("cmg", re.compile(r"https?://[a-z0-9-]+\.12twenty\.com/[^\s\"'<>]*?jobPostings/(\d+)")),
]
CLEAN_LINK = {"linkedin": "https://www.linkedin.com/jobs/view/{id}",
              "handshake": "https://app.joinhandshake.com/jobs/{id}",
              "cmg": CMG_LINK}
NOT_TITLE = re.compile(r"^(view job|apply|see (all|more)|learn more|easy apply|this company|actively hiring|promoted|"
                       r"new jobs? match|your job alert|\$|https?://|-{3,})", re.I)


def _body_text(msg):
    plain, htm = "", ""
    for part in msg.walk():
        ct = part.get_content_type()
        try:
            payload = part.get_content()
        except Exception:  # noqa: BLE001
            continue
        if ct == "text/plain" and not plain:
            plain = payload
        elif ct == "text/html" and not htm:
            htm = payload
    return plain, htm


def parse_alert_text(plain, source):
    """Plain-text job alerts (LinkedIn's layout): title, company, location, then a job link."""
    jobs = []
    for block in re.split(r"\n-{5,}\n", plain):
        for kind, rx in JOB_LINKS:
            m = rx.search(block)
            if not m:
                continue
            before = block[:m.start()]
            lines = [l.strip() for l in before.splitlines() if l.strip() and not NOT_TITLE.search(l.strip())]
            lines = [l for l in lines if not l.lower().startswith(("view job", "apply with"))]
            if not lines:
                continue
            title = lines[0]
            company = lines[1] if len(lines) > 1 else ""
            where = lines[2] if len(lines) > 2 else ""
            j = job(f"{kind}-{m.group(1)}", title, where, CLEAN_LINK[kind].format(id=m.group(1)))
            j["company"] = company
            jobs.append(j)
            break
    return jobs


def parse_alert_html(htm, source):
    """Any HTML alert: each job link's anchor text is the title."""
    jobs, seen = [], set()
    for href, inner in re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', htm, re.S | re.I):
        href = html.unescape(href)
        for kind, rx in JOB_LINKS:
            m = rx.search(href)
            if not m or (kind, m.group(1)) in seen:
                continue
            title = re.sub(r"\s+", " ", text(inner)).strip()
            if len(title) < 4 or NOT_TITLE.search(title):
                continue
            seen.add((kind, m.group(1)))
            j = job(f"{kind}-{m.group(1)}", title, "", CLEAN_LINK[kind].format(id=m.group(1)))
            j["company"] = ""
            jobs.append(j)
    return jobs


def email_alerts(prof):
    """Jobs from alert emails in the last few days. Returns (jobs, error or None)."""
    cfg = prof.get("email_alerts") or {}
    if not cfg.get("enabled"):
        return [], None
    E = os.environ.get
    user, pw = E("RADAR_IMAP_USER") or E("RADAR_SMTP_USER"), E("RADAR_IMAP_PASSWORD") or E("RADAR_SMTP_PASSWORD")
    if not (user and pw):
        return [], "no email login set, see SOURCES.md"
    host = E("RADAR_IMAP_HOST", "imap.gmail.com")
    since = (datetime.now() - timedelta(days=int(cfg.get("days", 3)))).strftime("%d-%b-%Y")
    senders = {k: v for k, v in ALERT_SENDERS.items() if k in (cfg.get("from") or list(ALERT_SENDERS))}
    for extra in cfg.get("extra_senders") or []:
        senders.setdefault("other", []).append(extra)
    jobs = []
    try:
        box = imaplib.IMAP4_SSL(host, ssl_context=CTX)
        box.login(user, pw)
        if box.select('"[Gmail]/All Mail"', readonly=True)[0] != "OK":
            box.select("INBOX", readonly=True)
        for source, addrs in senders.items():
            for addr in addrs:
                typ, data = box.search(None, "SINCE", since, "FROM", f'"{addr}"')
                for num in (data[0].split() if typ == "OK" and data and data[0] else [])[-60:]:
                    typ, raw = box.fetch(num, "(BODY.PEEK[])")
                    if typ != "OK" or not raw or not isinstance(raw[0], tuple):
                        continue
                    msg = email.message_from_bytes(raw[0][1], policy=email.policy.default)
                    plain, htm = _body_text(msg)
                    found = parse_alert_text(plain, source) if plain else []
                    if not found and htm:
                        found = parse_alert_html(htm, source)
                    for j in found:
                        j["source"] = {"linkedin": "LinkedIn alert", "handshake": "Handshake alert", "cmg": "CMG email"}.get(source, "email alert")
                    jobs += found
        box.logout()
    except Exception as e:  # noqa: BLE001
        return jobs, f"{type(e).__name__}: {str(e)[:80]}"
    uniq = {}
    for j in jobs:
        uniq.setdefault(j["id"], j)
    return list(uniq.values()), None


READERS = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby, "workday": workday,
           "smartrecruiters": smartrecruiters, "amazon": amazon, "cmg": cmg_tool}
DETAIL = {"workday": workday_detail, "smartrecruiters": smartrecruiters_detail}


# --- Finding a company's board -----------------------------------------------------

ATS_LINKS = [
    ("greenhouse", re.compile(r"(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/(?:embed/job_board\?for=)?([A-Za-z0-9_-]+)")),
    ("lever", re.compile(r"jobs\.lever\.co/([A-Za-z0-9_.-]+)")),
    ("ashby", re.compile(r"jobs\.ashbyhq\.com/([A-Za-z0-9_.%-]+)")),
    ("smartrecruiters", re.compile(r"(?:jobs|careers)\.smartrecruiters\.com/([A-Za-z0-9_-]+)")),
    ("workday", re.compile(r"([a-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([A-Za-z0-9_-]+)")),
]
SKIP_SLUGS = {"embed", "v1", "api", "jobs", "careers", "job", "en-US", "wday", "search"}


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def verify(entry, name=""):
    """True when the board answers and (where the board says its owner) belongs to `name`."""
    a = entry["ats"]
    try:
        if a == "greenhouse":
            d = get_json(f"https://boards-api.greenhouse.io/v1/boards/{entry['token']}", retries=0, timeout=20)
            owner = _norm(d.get("name"))
            return not name or not owner or _norm(name)[:6] in owner or owner[:6] in _norm(name)
        if a == "lever":
            return isinstance(get_json(f"https://api.lever.co/v0/postings/{entry['token']}?mode=json&limit=1", retries=0, timeout=20), list)
        if a == "ashby":
            return "jobs" in get_json(f"https://api.ashbyhq.com/posting-api/job-board/{entry['token']}", retries=0, timeout=20)
        if a == "smartrecruiters":
            d = get_json(f"https://api.smartrecruiters.com/v1/companies/{entry['token']}/postings?limit=5", retries=0, timeout=20)
            owners = {_norm((p.get("company") or {}).get("name")) for p in d.get("content", [])}
            return d.get("totalFound", 0) > 0 and (not name or any(_norm(name)[:5] in o for o in owners))
        if a == "workday":
            d = get_json(f"{_wd(entry)}/wday/cxs/{entry['tenant']}/{entry['site']}/jobs",
                         data={"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""}, retries=0, timeout=20)
            return isinstance(d.get("total"), int)
    except (Exception, SystemExit):  # noqa: BLE001
        return False
    return False


def links_in(page):
    found = []
    for ats, rx in ATS_LINKS:
        for m in rx.finditer(page):
            if ats == "workday":
                e = {"ats": "workday", "tenant": m.group(1), "pod": m.group(2), "site": m.group(3)}
                if e["site"] in SKIP_SLUGS:
                    continue
            else:
                tok = urllib.parse.unquote(m.group(1))
                if tok in SKIP_SLUGS:
                    continue
                e = {"ats": ats, "token": tok}
            if e not in found:
                found.append(e)
    return found


def find_board(name, domain=""):
    """A company entry for my-radar.json: a verified board, or a manual link to check by hand."""
    careers = ""
    if domain:
        d = re.sub(r"^https?://", "", domain).strip("/").split("/")[0]
        bare = d[4:] if d.startswith("www.") else d
        for url in (f"https://{d}/careers", f"https://www.{bare}/careers", f"https://careers.{bare}",
                    f"https://jobs.{bare}", f"https://{d}/jobs", f"https://{d}"):
            try:
                page = fetch(url, retries=0, timeout=15, headers={"Accept": "text/html"})
            except (Exception, SystemExit):  # noqa: BLE001
                continue
            careers = careers or url
            for e in links_in(page):
                if verify(e):
                    return {"name": name, **e}
    words = re.findall(r"[a-z0-9]+", name.lower())
    stem = re.sub(r"^www\.", "", re.sub(r"^https?://", "", domain or "")).split(".")[0] if domain else ""
    guesses = []
    for s in ("".join(words), "-".join(words), words[0] if words else "", stem):
        if s and s not in guesses:
            guesses.append(s)
    found = []
    for s in guesses:
        for ats in ("greenhouse", "ashby", "lever"):
            e = {"ats": ats, "token": s}
            exact = s in ("".join(words), stem)
            if (ats == "greenhouse" or exact) and e not in found and verify(e, name):
                found.append(e)
    e = {"ats": "smartrecruiters", "token": "".join(w.capitalize() for w in words)}
    if verify(e, name):
        found.append(e)
    if found:
        def size(e):  # an old, abandoned board loses to the one the company uses now
            try:
                return len(READERS[e["ats"]](e, ["intern", "MBA"]))
            except (Exception, SystemExit):  # noqa: BLE001
                return -1
        return {"name": name, **max(found, key=size)}
    return {"name": name, "ats": "manual", "url": careers or (f"https://{domain}" if domain else "")}


PROBES = ("https://boards-api.greenhouse.io/v1/boards/stripe",
          "https://api.ashbyhq.com/posting-api/job-board/openai",
          "https://api.lever.co/v0/postings/palantir?mode=json&limit=1")


def online():
    """True when job boards can be reached from here (the Claude app's code sandbox cannot)."""
    for url in PROBES:
        try:
            fetch(url, retries=0, timeout=10)
            return True
        except (Exception, SystemExit):  # noqa: BLE001
            continue
    return False


def resolve_dreams(prof, limit=10, today=None):
    """Dream companies typed into the guide page (or added with no internet) start as links to
    check by hand. Look for each one's job board, so later scans read it. Changes the profile in
    place. Returns the names that now have a board, or None when nothing was looked up."""
    today = today or datetime.now()

    def due(c):
        if c.get("ats") != "manual" or not c.get("dream"):
            return False
        try:  # looked before and found nothing: try again after a month
            return today - datetime.strptime(c.get("looked", ""), "%Y-%m-%d") > timedelta(days=30)
        except ValueError:
            return True

    todo = [c for c in prof.get("companies", []) if due(c)][:limit]
    if not todo or not online():
        return None
    found = []
    for c in todo:
        e = find_board(c["name"], c.get("url", ""))
        if e["ats"] == "manual":
            c["looked"] = today.strftime("%Y-%m-%d")
            c["url"] = c.get("url") or e.get("url", "")
        else:
            c.clear()
            c.update({**e, "dream": True})
            found.append(e["name"])
    return found


# --- Matching -------------------------------------------------------------------

def load_industries():
    with open(os.path.join(HERE, "..", "industries.json"), encoding="utf-8") as fh:
        return json.load(fh)


INTERN = re.compile(r"\b(intern|interns|internships?|summer associate|summer analyst|co-?op|summer 20\d\d)\b", re.I)
UNDERGRAD = re.compile(r"\b(undergrad(uate)?s?|bachelor'?s?|b\.?s\.?/?b\.?a\.?|sophomores?|juniors?|rising seniors?|freshm[ae]n)\b", re.I)
GRAD = re.compile(r"\b(mba|graduate|master'?s|business school)\b", re.I)
PHD_TITLE = re.compile(r"\b(ph\.?d|ms/phd|bs/ms|m\.?s\.?|b\.?s\.?)\b", re.I)
NO_SPONSOR = re.compile(r"(not (be )?(able|eligible) to (provide |offer )?(visa )?sponsor|unable to sponsor|"
                        r"no (visa )?sponsorship|without (the need for )?(current or future )?(visa )?sponsorship|"
                        r"will not sponsor|does not sponsor|u\.?s\.? citizen(ship)? (is )?required|"
                        r"must be a u\.?s\.? citizen|security clearance)", re.I)
DEADLINE = re.compile(r"(?:deadline|apply by|applications? (?:close|are due|due)|accepting applications (?:until|through))"
                      r"[^.\n]{0,40}?((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.? \d{1,2}(?:, ?\d{4})?)", re.I)


def expand_locations(locs, industries):
    alias = {k.lower(): v for k, v in industries.get("locations", {}).items()}
    out = []
    for l in locs:
        key = l.lower().strip()
        out += [key] + [x.lower() for x in alias.get(key, [])]
    return out


def role_patterns(roles, industries):
    syn = industries.get("roles", {})
    pats = []
    for r in roles:
        key = r.lower().strip()
        words = syn.get(key) or [key]
        pats += [re.compile(r"\b" + w, re.I) if not w.startswith("\\") else re.compile(w, re.I) for w in words]
    return pats


def score(j, company, prof, ctx):
    title, desc = j["title"], j["desc"] or ""
    head = title + " " + desc[:600]
    want_intern = prof.get("looking_for", "internship") == "internship"
    year = ctx["year"]
    flags = []
    if want_intern and not (INTERN.search(title) or (re.search(r"\bmba\b", title, re.I) and INTERN.search(head))):
        return None
    if not want_intern and INTERN.search(title):
        return None
    if year:
        others = {str(y) for y in range(int(year) - 3, int(year))}
        if any(y in title for y in others) and year not in title:
            return None
    if ctx["avoid"] and ctx["avoid"].search(title):
        return None
    if UNDERGRAD.search(title) and not GRAD.search(title):
        return None
    if PHD_TITLE.search(title) and not re.search(r"\bmba\b", title, re.I) and prof.get("degree", "MBA").upper() == "MBA":
        return None
    s = 20
    if any(p.search(title) for p in ctx["roles"]):
        s += 35
    elif ctx["roles"] and not any(p.search(desc) for p in ctx["roles"]):
        s -= 15
    degree = prof.get("degree", "MBA")
    if re.search(rf"\b{re.escape(degree)}\b", title, re.I):
        s += 20
    elif re.search(rf"\b{re.escape(degree)}\b", desc, re.I) or GRAD.search(desc):
        s += 10
    elif UNDERGRAD.search(desc[:2000]):
        s -= 30
        flags.append("may be undergrad-only")
    elif desc:
        s -= 10  # no sign it is meant for graduate students
    if year and year in head:
        s += 10
    locs = ctx["locs"]
    jl = j["location"].lower()
    if locs:
        if any(l in jl for l in locs) or ("remote" in locs and "remote" in jl):
            s += 10
        elif jl and not re.search(r"\d+ locations|multiple locations|remote|^(united states|usa|us)$", jl.strip()):
            s -= 35
    if company.get("dream"):
        s += 10
    if prof.get("needs_sponsorship") and NO_SPONSOR.search(desc):
        s -= 25
        flags.append("no visa sponsorship")
    m = DEADLINE.search(desc)
    if m:
        flags.append("deadline " + m.group(1))
    return max(0, min(100, s)), flags


# --- Scan -----------------------------------------------------------------------

def scan(prof, state, workers=12):
    ind = load_industries()
    term = prof.get("term", "")
    ymatch = re.search(r"20\d\d", term)
    avoid = prof.get("avoid") or []
    ctx = {"year": ymatch.group(0) if ymatch else "",
           "roles": role_patterns(prof.get("roles") or [], ind),
           "avoid": re.compile("|".join(r"\b" + re.escape(a) for a in avoid), re.I) if avoid else None,
           "locs": expand_locations(prof.get("locations") or [], ind)}
    q = ["intern", prof.get("degree", "MBA")] if prof.get("looking_for", "internship") == "internship" \
        else [prof.get("degree", "MBA")] + (prof.get("roles") or [])[:2]
    auto = [c for c in prof.get("companies", []) if c.get("ats") in READERS]
    if prof.get("cmg_tool") and not any(c.get("ats") == "cmg" for c in auto):
        auto.append({"name": "Haas CMG", "ats": "cmg"})

    def one(c):
        try:
            jobs = READERS[c["ats"]](c, q)
        except (Exception, SystemExit) as e:  # noqa: BLE001
            return c, None, f"{type(e).__name__}"
        hits, details = [], 0
        for j in jobs:
            if c["ats"] in DETAIL and not j["desc"]:
                if not score(j, c, prof, ctx) or details >= 30:
                    continue  # the title alone rules it out; skip the extra request
                details += 1
                try:
                    j["desc"] = DETAIL[c["ats"]](c, j)
                except Exception:  # noqa: BLE001
                    pass
            r = score(j, c, prof, ctx)
            if r and r[0] >= prof.get("min_score", 55):
                flags = r[1] + ([f"deadline {j['deadline']}"] if j.get("deadline") else [])
                hits.append({**j, "company": j.get("company") or c["name"], "score": r[0], "flags": flags,
                             "desc": "", "source": j.get("source") or ("CMG" if c["ats"] == "cmg" else "job board")})
        return c, hits, None

    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(one, auto))
    boards = [err for c, _, err in results if c.get("ats") != "cmg"]  # cmg is a local copy, not a site
    unreachable = bool(boards) and all(boards)
    mail_jobs, mail_err = email_alerts(prof)
    if mail_jobs or mail_err:
        hits = []
        for j in mail_jobs:
            r = score(j, {"name": j.get("company") or ""}, prof, ctx)
            if r and r[0] >= (prof.get("email_alerts") or {}).get("min_score", prof.get("min_score", 55)):
                hits.append({**j, "company": j.get("company") or j["source"], "score": r[0], "flags": r[1], "desc": ""})
        results.append(({"name": "job-alert emails"}, hits if not mail_err or mail_jobs else None, mail_err if not mail_jobs else None))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    seen = state.setdefault("seen", {})
    matches, failed = [], []
    for c, hits, err in results:
        if err:
            failed.append(f"{c['name']} ({err})")
            continue
        for h in hits:
            key = f"{c['name']}|{h['id']}"
            h["new"] = key not in seen
            seen.setdefault(key, now)
            matches.append(h)
    matches.sort(key=lambda h: (not h["new"], -h["score"], h["company"]))
    manual = [c for c in prof.get("companies", []) if c.get("ats") == "manual"]
    return {"matches": matches, "failed": failed, "checked": len(auto), "manual": manual, "at": now,
            "emails": len(mail_jobs), "unreachable": unreachable}


def digest(prof, res, today=None, top_old=5, max_new=15):
    today = today or datetime.now()
    new = [m for m in res["matches"] if m["new"]]
    old = [m for m in res["matches"] if not m["new"]]
    who = prof.get("name", "").split(" ")[0]
    down = res.get("unreachable")
    lines = [f"Internship Radar{(' for ' + who) if who else ''} · {today:%a %b} {today.day}",
             (f"No job board could be reached (0 of {res['checked']}), so this is not a real scan." if down else
              f"{len(new)} new · {len(res['matches'])} open matches · {res['checked']} boards checked")
             + (f" · {res['emails']} jobs read from your alert emails" if res.get("emails") else ""), ""]
    if down:
        lines += ["This environment cannot reach job sites. The Claude app's code sandbox cannot, and",
                  "some office or campus networks block them.",
                  'Your profile is fine. Run the radar on GitHub (README: "GitHub (daily)") or on your',
                  "own computer.", ""]

    def row(i, m):
        tag = "".join(f" ⚠ {f}" for f in m["flags"])
        posted = f" · posted {m['posted']}" if m.get("posted") else ""
        via = f" · via {m['source']}" if m.get("source") not in (None, "job board") else ""
        return [f"{i}. [{m['score']}] {m['company']}: {m['title']}", f"   {m['location'] or 'location not listed'}{posted}{via}{tag}", f"   {m['url']}"]

    if new:
        lines.append("NEW")
        for i, m in enumerate(new[:max_new], 1):
            lines += row(i, m)
        if len(new) > max_new:
            lines.append(f"…and {len(new) - max_new} more new matches with lower scores (full list: radar-latest.md)")
        lines.append("")
    elif not down:
        lines += ["Nothing new since the last check.", ""]
    if old and top_old:
        lines.append("STILL OPEN (best first)")
        for i, m in enumerate(sorted(old, key=lambda m: -m["score"])[:top_old], 1):
            lines += row(i, m)
        lines.append("")
    if res["failed"] and not down:
        lines.append("Could not read: " + ", ".join(res["failed"][:8]))
    if res["manual"] and today.weekday() == 0:
        lines.append("Check by hand this week (own career sites):")
        lines += [f"• {c['name']}: {c.get('url') or 'search their careers page'}" for c in res["manual"][:8]]
    return "\n".join(lines).rstrip() + "\n"


# --- Alerts -----------------------------------------------------------------------
# Every channel reads its secrets from the environment (or radar.env). A channel is used when
# its secrets are present and the profile lists it under alerts.channels (or lists none).

CHANNELS = {
    "email": ["RADAR_EMAIL_TO", "RADAR_SMTP_USER", "RADAR_SMTP_PASSWORD"],
    "imessage": ["RADAR_IMESSAGE_TO"],
    "sheets": ["RADAR_SHEETS_URL"],
    "whatsapp": ["RADAR_WHATSAPP_PHONE", "RADAR_CALLMEBOT_APIKEY"],
    "slack": ["RADAR_SLACK_WEBHOOK"],
    "discord": ["RADAR_DISCORD_WEBHOOK"],
    "push": ["RADAR_NTFY_TOPIC"],
    "telegram": ["RADAR_TELEGRAM_BOT_TOKEN", "RADAR_TELEGRAM_CHAT_ID"],
}


def load_env(folder):
    p = os.path.join(folder, "radar.env")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def configured(prof):
    want = [c.lower() for c in (prof.get("alerts") or {}).get("channels") or []]
    return [ch for ch, keys in CHANNELS.items() if all(os.environ.get(k) for k in keys) and (not want or ch in want)]


def chunks(s, n):
    out, cur = [], ""
    for line in s.splitlines(keepends=True):
        if len(cur) + len(line) > n and cur:
            out.append(cur)
            cur = ""
        cur += line
    return out + ([cur] if cur else [])


def post(url, data=None, form=None, raw=None, headers=None):
    body = json.dumps(data).encode() if data is not None else (urllib.parse.urlencode(form).encode() if form else raw)
    h = {"User-Agent": UA, **(headers or {})}
    if data is not None:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=30, context=CTX) as r:
        return r.status


def sheet_rows(matches):
    return [{"found": datetime.now().strftime("%Y-%m-%d"), "score": m.get("score", ""), "company": m.get("company", ""),
             "title": m.get("title", ""), "location": m.get("location", ""), "posted": m.get("posted", ""),
             "flags": "; ".join(m.get("flags") or []), "url": m.get("url", ""), "source": m.get("source", "job board")}
            for m in matches]


def send(channel, subject, body, dry=False, rows=None):
    E = os.environ.get
    if dry:
        if channel == "sheets":
            return f"[dry] sheets: would add {len(rows or [])} rows to your Google Sheet"
        return f"[dry] {channel}: would send {len(body)} characters ({subject})"
    if channel == "sheets":
        if rows:
            post(E("RADAR_SHEETS_URL"), data={"rows": rows})
        return f"sent: sheets ({len(rows or [])} rows)"
    if channel == "email":
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"], msg["From"], msg["To"] = subject, E("RADAR_SMTP_USER"), E("RADAR_EMAIL_TO")
        host, port = E("RADAR_SMTP_HOST", "smtp.gmail.com"), int(E("RADAR_SMTP_PORT", "465"))
        with smtplib.SMTP_SSL(host, port, context=CTX, timeout=30) as s:
            s.login(E("RADAR_SMTP_USER"), E("RADAR_SMTP_PASSWORD"))
            s.sendmail(E("RADAR_SMTP_USER"), [a.strip() for a in E("RADAR_EMAIL_TO").split(",")], msg.as_string())
    elif channel == "telegram":
        for part in chunks(body, 3800):
            post(f"https://api.telegram.org/bot{E('RADAR_TELEGRAM_BOT_TOKEN')}/sendMessage",
                 data={"chat_id": E("RADAR_TELEGRAM_CHAT_ID"), "text": part, "disable_web_page_preview": True})
    elif channel == "push":
        server = E("RADAR_NTFY_SERVER", "https://ntfy.sh").rstrip("/")
        post(f"{server}/{E('RADAR_NTFY_TOPIC')}", raw=body[:3900].encode(), headers={"Title": subject.encode("ascii", "ignore").decode()})
    elif channel == "imessage":
        if sys.platform != "darwin":
            raise RuntimeError("iMessage only works on a Mac")
        script = ('on run {targetPhone, targetMessage}\n tell application "Messages"\n'
                  ' set s to 1st service whose service type = iMessage\n'
                  ' send targetMessage to buddy targetPhone of s\n end tell\nend run')
        for part in chunks(body, 1500):
            subprocess.run(["osascript", "-", E("RADAR_IMESSAGE_TO"), part], input=script, text=True, check=True, timeout=60)
    elif channel == "whatsapp":
        for part in chunks(body, 900):
            url = ("https://api.callmebot.com/whatsapp.php?" + urllib.parse.urlencode(
                {"phone": E("RADAR_WHATSAPP_PHONE"), "text": part, "apikey": E("RADAR_CALLMEBOT_APIKEY")}))
            fetch(url, retries=1, timeout=30)
            time.sleep(3)
    elif channel in ("slack", "discord"):
        key = "RADAR_SLACK_WEBHOOK" if channel == "slack" else "RADAR_DISCORD_WEBHOOK"
        field = "text" if channel == "slack" else "content"
        for part in chunks(body, 1900):
            post(E(key), data={field: part})
    return f"sent: {channel}"


# --- Files ------------------------------------------------------------------------

def read(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return default


def write(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="radar.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("cmd", choices=["scan", "find", "add", "preset", "track", "channels", "test-alert"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--profile", default=os.environ.get("RADAR_PROFILE", "my-radar.json"))
    ap.add_argument("--send", action="store_true", help="send the digest on your alert channels")
    ap.add_argument("--dry", action="store_true", help="show what would be sent, send nothing")
    ap.add_argument("--always", action="store_true", help="send even when nothing is new")
    ap.add_argument("--source", default="added by hand", help="track: where the posting came from (CMG, referral...)")
    ap.add_argument("--deadline", default="", help="track: application deadline, YYYY-MM-DD")
    a = ap.parse_args(argv)
    prof_path = os.path.abspath(a.profile)
    folder = os.path.dirname(prof_path)
    load_env(folder)
    prof = read(prof_path, None)

    if a.cmd == "find":
        print(json.dumps(find_board(a.args[0], a.args[1] if len(a.args) > 1 else ""), indent=1))
        return 0
    if prof is None:
        print(f"No profile at {prof_path}. Copy templates/my-radar.example.json to my-radar.json and fill it in "
              "(or ask Claude: 'set up my internship radar').", file=sys.stderr)
        return 1
    if a.cmd == "add":
        e = find_board(a.args[0], a.args[1] if len(a.args) > 1 else "")
        e["dream"] = True
        prof["companies"] = [c for c in prof.get("companies", []) if _norm(c["name"]) != _norm(e["name"])] + [e]
        write(prof_path, prof)
        print(json.dumps(e, indent=1))
        return 0
    if a.cmd == "preset":
        ind = load_industries()["industries"]
        have = {_norm(c["name"]) for c in prof.get("companies", [])}
        for key in a.args:
            if key not in ind:
                print(f"Unknown industry '{key}'. Choose from: {', '.join(ind)}", file=sys.stderr)
                return 1
            for c in ind[key]["companies"]:
                if _norm(c["name"]) not in have:
                    prof.setdefault("companies", []).append(c)
                    have.add(_norm(c["name"]))
        write(prof_path, prof)
        print(f"{len(prof['companies'])} companies in {os.path.basename(prof_path)}")
        return 0
    if a.cmd == "track":
        if len(a.args) < 2:
            print('usage: radar.py track "Company" "Role" [URL] [--source CMG] [--deadline 2026-11-21]', file=sys.stderr)
            return 1
        row = {"company": a.args[0], "title": a.args[1], "url": a.args[2] if len(a.args) > 2 else "", "score": "",
               "location": "", "posted": "", "flags": [f"deadline {a.deadline}"] if a.deadline else [], "source": a.source}
        path = os.path.join(folder, "my-tracker.csv")
        fresh = not os.path.exists(path)
        with open(path, "a", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            if fresh:
                w.writerow(["found", "company", "role", "link", "source", "deadline", "status", "notes"])
            w.writerow([datetime.now().strftime("%Y-%m-%d"), row["company"], row["title"], row["url"], a.source, a.deadline, "New", ""])
        msg = f"Added to my-tracker.csv: {row['company']}, {row['title']}"
        if "sheets" in configured(prof):
            print(send("sheets", "", "", a.dry, sheet_rows([row])))
        print(msg)
        return 0
    if a.cmd == "channels":
        ready = configured(prof)
        for ch, keys in CHANNELS.items():
            missing = [k for k in keys if not os.environ.get(k)]
            print(f"{'ready  ' if ch in ready else 'not set'} {ch:9} " + ("" if not missing else "needs " + ", ".join(missing)))
        return 0
    if a.cmd == "test-alert":
        for ch in configured(prof) or []:
            try:
                test_row = [{"found": datetime.now().strftime("%Y-%m-%d"), "score": "", "company": "Internship Radar",
                             "title": "Test row: alerts work (delete me)", "location": "", "posted": "", "flags": "",
                             "url": "", "source": "test"}]
                print(send(ch, "Internship Radar test", "Internship Radar test: alerts work.\n", a.dry, test_row))
            except Exception as e:  # noqa: BLE001
                print(f"FAILED {ch}: {type(e).__name__}: {e}")
        if not configured(prof):
            print("No channel is set up yet. See ALERTS.md.")
        return 0

    found = resolve_dreams(prof)
    if found is not None:
        write(prof_path, prof)
        if found:
            print("Found the job boards for " + ", ".join(found) + ": they are scanned from now on.\n")
    state_path = os.path.join(folder, "radar-state.json")
    state = read(state_path, {})
    res = scan(prof, state)
    body = digest(prof, res)
    with open(os.path.join(folder, "radar-latest.md"), "w", encoding="utf-8") as fh:
        fh.write(digest(prof, res, max_new=10**6, top_old=10**6))
    print(body)
    write(state_path, state)
    if res.get("unreachable"):
        return 1  # nothing was really checked: send nothing, and let a scheduled run show as failed
    if a.send:
        new = sum(1 for m in res["matches"] if m["new"])
        if new or a.always or (prof.get("alerts") or {}).get("send_when_quiet"):
            subject = f"Internship Radar: {new} new" if new else "Internship Radar: nothing new"
            new_rows = sheet_rows([m for m in res["matches"] if m["new"]])
            for ch in configured(prof):
                try:
                    print(send(ch, subject, body, a.dry, new_rows))
                except Exception as e:  # noqa: BLE001
                    print(f"FAILED {ch}: {type(e).__name__}: {e}", file=sys.stderr)
            if not configured(prof):
                print("No alert channel is set up yet, so nothing was sent. See ALERTS.md.", file=sys.stderr)
        else:
            print("Nothing new, so no alert was sent (set alerts.send_when_quiet to true to get one anyway).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
