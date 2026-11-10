"""Offline tests: python3 -m unittest discover tests   (no network needed)."""
import email
import email.policy
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import radar  # noqa: E402

LINKEDIN_TEXT = """Your job alert for MBA intern product
New jobs match your preferences.

Product Manager Intern (MBA), Summer 2027
Stripe
San Francisco, CA

This company is actively hiring
Apply with resume & profile
View job: https://www.linkedin.com/comm/jobs/view/4477880246/?trackingId=abc&refId=def

---------------------------------------------------------

Strategy & Operations MBA Intern
Pinterest
United States
View job: https://www.linkedin.com/comm/jobs/view/4477867202/?trackingId=ghi

---------------------------------------------------------

See all jobs on LinkedIn: https://www.linkedin.com/comm/jobs/search-results/?keywords=MBA
"""

HANDSHAKE_HTML = """<html><body><table>
<tr><td><a href="https://app.joinhandshake.com/stu/jobs/9876543?ref=email">MBA Summer Associate, Brand Management</a></td></tr>
<tr><td><a href="https://app.joinhandshake.com/stu/jobs/9876543?ref=email">View job</a></td></tr>
<tr><td><a href="https://mba-haas-berkeley.12twenty.com/jobPostings#/jobPostings/35006705625972/details">Product Management Intern</a></td></tr>
<tr><td><a href="https://example.com/unsubscribe">Unsubscribe</a></td></tr>
</table></body></html>"""


class AlertEmails(unittest.TestCase):
    def test_linkedin_text_layout(self):
        jobs = radar.parse_alert_text(LINKEDIN_TEXT, "linkedin")
        self.assertEqual([j["title"] for j in jobs], ["Product Manager Intern (MBA), Summer 2027", "Strategy & Operations MBA Intern"])
        self.assertEqual([j["company"] for j in jobs], ["Stripe", "Pinterest"])
        self.assertEqual(jobs[0]["location"], "San Francisco, CA")
        self.assertEqual(jobs[0]["url"], "https://www.linkedin.com/jobs/view/4477880246")

    def test_html_links_from_handshake_and_cmg(self):
        jobs = radar.parse_alert_html(HANDSHAKE_HTML, "handshake")
        self.assertEqual([j["title"] for j in jobs], ["MBA Summer Associate, Brand Management", "Product Management Intern"])
        self.assertEqual(jobs[0]["url"], "https://app.joinhandshake.com/jobs/9876543")
        self.assertIn("35006705625972", jobs[1]["url"])

    def test_multipart_email(self):
        msg = email.message.EmailMessage(policy=email.policy.default)
        msg["From"] = "LinkedIn Job Alerts <jobalerts-noreply@linkedin.com>"
        msg.set_content(LINKEDIN_TEXT)
        msg.add_alternative("<p>html part</p>", subtype="html")
        plain, htm = radar._body_text(email.message_from_bytes(msg.as_bytes(), policy=email.policy.default))
        self.assertIn("View job", plain)
        self.assertIn("html part", htm)


class Scoring(unittest.TestCase):
    def setUp(self):
        ind = radar.load_industries()
        self.prof = {"looking_for": "internship", "term": "Summer 2027", "degree": "MBA", "roles": ["strategy", "product management"],
                     "locations": ["San Francisco Bay Area"], "needs_sponsorship": True}
        self.ctx = {"year": "2027", "roles": radar.role_patterns(self.prof["roles"], ind), "avoid": None,
                    "locs": radar.expand_locations(self.prof["locations"], ind)}

    def s(self, title, loc="San Francisco, CA", desc="MBA students"):
        return radar.score(radar.job("1", title, loc, "u", "", desc), {"name": "X"}, self.prof, self.ctx)

    def test_good_match(self):
        self.assertGreaterEqual(self.s("MBA Intern, Corporate Strategy (Summer 2027)")[0], 85)

    def test_last_year_dropped(self):
        self.assertIsNone(self.s("Strategy MBA Intern, Summer 2026"))

    def test_full_time_role_not_an_internship(self):
        self.assertIsNone(self.s("Senior Product Manager"))

    def test_visa_flag(self):
        self.assertIn("no visa sponsorship", self.s("MBA Strategy Intern 2027", desc="MBA. We are unable to sponsor visas.")[1])

    def test_foreign_location_penalized(self):
        self.assertLess(self.s("MBA Strategy Intern 2027", loc="Tokyo, Japan")[0], 55)


class Sheets(unittest.TestCase):
    def test_rows(self):
        rows = radar.sheet_rows([{"score": 90, "company": "Stripe", "title": "MBA Intern", "url": "u", "flags": ["deadline Nov 21"]}])
        self.assertEqual(rows[0]["company"], "Stripe")
        self.assertEqual(rows[0]["flags"], "deadline Nov 21")


if __name__ == "__main__":
    unittest.main()
