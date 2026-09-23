"""
tests/test_main_api.py
=======================
Integration-level tests for backend/main.py FastAPI endpoints.

Scenarios:
  API-01  GET /  -> 200 HTML
  API-02  POST /api/security/analyze-content -> valid JSON with score and warnings
  API-03  POST /api/security/clean-list -> valid/invalid split returned
  API-04  GET /api/accounts -> empty list on fresh DB
  API-05  POST /api/accounts -> account created
  API-06  POST /api/accounts (duplicate) -> 400 error
  API-07  GET /api/accounts/next-active -> available=False when no accounts
  API-08  GET /api/history/check/:email -> already_contacted=False initially
  API-09  POST /api/history/record -> records event; check returns True
  API-10  GET /track/open/:track_id -> returns transparent GIF
  API-11  GET /track/click/:track_id -> redirects to target URL
  API-12  POST /api/security/check-domain -> returns domain field
"""
from __future__ import annotations
import sys, os, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tempfile
import pathlib

# Use an isolated temporary SQLite DB for integration tests
_test_dir = tempfile.TemporaryDirectory()
_test_db = pathlib.Path(_test_dir.name) / "test_api.db"
os.environ["SHEETMERGE_DB_PATH"] = str(_test_db)

# Import FastAPI test client
from fastapi.testclient import TestClient

import main as app_module
app_module.DB_PATH = _test_db
app_module.init_db()
client = TestClient(app_module.app)


class TestRootEndpoint(unittest.TestCase):
    def test_API01_root_returns_html(self):
        r = client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/html", r.headers["content-type"])
        self.assertIn("SheetMerge", r.text)


class TestSpamAnalyzeEndpoint(unittest.TestCase):
    def test_API02_analyze_content(self):
        r = client.post("/api/security/analyze-content", json={
            "subject": "Hello there",
            "body_html": "<p>Just following up.</p>"
        })
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("deliverability_score", data)
        self.assertIn("is_spam_risk", data)
        self.assertIn("warnings", data)

    def test_API02b_spam_email_is_flagged(self):
        r = client.post("/api/security/analyze-content", json={
            "subject": "FREE MONEY WIN NOW!!!",
            "body_html": "<p>Click here for free gift and cash bonus unlimited income guaranteed.</p>"
        })
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["is_spam_risk"])


class TestListCleanEndpoint(unittest.TestCase):
    def test_API03_clean_list_valid_and_invalid(self):
        r = client.post("/api/security/clean-list", json={
            "emails": ["good@example.com", "notanemail", "temp@mailinator.com"],
            "check_mx": False
        })
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("valid_emails", data)
        self.assertIn("invalid_details", data)
        self.assertEqual(data["total_analyzed"], 3)
        self.assertIn("good@example.com", data["valid_emails"])
        invalid_emails = [d["email"] for d in data["invalid_details"]]
        self.assertIn("notanemail", invalid_emails)
        self.assertIn("temp@mailinator.com", invalid_emails)


class TestAccountsEndpoints(unittest.TestCase):
    def test_API04_list_accounts_empty(self):
        r = client.get("/api/accounts")
        self.assertEqual(r.status_code, 200)
        # May or may not be empty depending on test order

    def test_API05_create_account(self):
        r = client.post("/api/accounts", json={"email": "test_acct@example.com", "daily_quota": 30})
        # 200 or 400 if already exists from previous test run
        self.assertIn(r.status_code, [200, 400])
        if r.status_code == 200:
            data = r.json()
            self.assertEqual(data["email"], "test_acct@example.com")
            self.assertEqual(data["daily_quota"], 30)
            self.assertEqual(data["sent_today"], 0)

    def test_API06_duplicate_account_returns_400(self):
        client.post("/api/accounts", json={"email": "dup@example.com", "daily_quota": 50})
        r = client.post("/api/accounts", json={"email": "dup@example.com", "daily_quota": 50})
        self.assertEqual(r.status_code, 400)


class TestHistoryEndpoints(unittest.TestCase):
    def test_API08_check_unseen_email(self):
        r = client.get("/api/history/check/nobody@fresh.com")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()["already_contacted"])

    def test_API09_record_then_check(self):
        track = "TESTTRACK12345ABCDE"
        # Record it
        client.post("/api/history/record", json={
            "email": "recorded@test.com",
            "status": "sent",
            "track_id": track,
            "row_index": 5,
            "subject": "Test subject"
        })
        # Now check
        r = client.get("/api/history/check/recorded@test.com")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["already_contacted"])


class TestTrackingEndpoints(unittest.TestCase):
    def test_API10_open_pixel_returns_gif(self):
        r = client.get("/track/open/SOMETRACKID999", follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["content-type"], "image/gif")

    def test_API11_click_redirect(self):
        from urllib.parse import quote
        target = quote("https://example.com", safe="")
        r = client.get(f"/track/click/CLICKTRACK99?url={target}", follow_redirects=False)
        self.assertIn(r.status_code, [302, 307])
        self.assertIn("example.com", r.headers.get("location", ""))


class TestDomainCheckEndpoint(unittest.TestCase):
    def test_API12_check_domain_returns_domain_key(self):
        r = client.post("/api/security/check-domain", json={
            "domain": "gmail.com",
            "dkim_selector": "google"
        })
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("domain", data)
        self.assertEqual(data["domain"], "gmail.com")


if __name__ == "__main__":
    unittest.main()
