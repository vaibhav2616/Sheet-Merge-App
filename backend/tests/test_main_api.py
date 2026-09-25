"""
tests/test_main_api.py
=======================
Integration-level tests for backend/main.py FastAPI endpoints.

Scenarios:
  API-01  GET /  -> 200 HTML
  API-02  POST /api/security/analyze-content -> valid JSON with score and warnings
  API-03  POST /api/security/clean-list -> valid/invalid split returned
  API-04  GET /api/accounts -> list accounts
  API-05  POST /api/accounts -> account created
  API-06  POST /api/accounts (duplicate) -> 400 error
  API-08  GET /api/history/check/:email -> already_contacted=False initially
  API-09  POST /api/history/record -> records event; check returns True
  API-10  GET /track/open/:track_id -> returns transparent GIF
  API-11  GET /track/click/:track_id -> redirects to target URL
  API-12  POST /api/security/check-domain -> returns domain field
  API-13  POST /api/sheet/upload-csv -> parses CSV, detects columns, seeds recipients
  API-14  GET /api/sheet/export-csv -> returns downloadable CSV with Merge Status
  API-15  POST /api/sheet/load-sample -> loads sample dataset
  API-16  GET /api/sheet/recipients -> status filtering works
  API-17  POST /api/campaign/dispatch-row -> successful dispatch updates status to EMAIL_SENT and increments quota
  API-18  POST /api/campaign/dispatch-row -> 5xx hard bounce suppressed and NOT counted toward 50 daily quota
  API-19  POST /api/campaign/dispatch-row -> quota exceeded raises HTTP 429
  API-20  POST /api/accounts/verify-smtp -> handles auth check
"""
from __future__ import annotations
import sys, os, unittest
from unittest.mock import MagicMock, patch

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

    def test_API05_create_account(self):
        r = client.post("/api/accounts", json={"email": "test_acct@example.com", "daily_quota": 30})
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
        client.post("/api/history/record", json={
            "email": "recorded@test.com",
            "status": "sent",
            "track_id": track,
            "row_index": 5,
            "subject": "Test subject"
        })
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


class TestSheetMergeRealWorldFeatures(unittest.TestCase):

    def test_API13_upload_csv_sheet(self):
        sample_csv = (
            "Email,First Name,Company,Merge Status\n"
            "sarah@techcorp.io,Sarah,TechCorp,UNPROCESSED\n"
            "michael@finance.co,Michael,Finance Co,EMAIL_SENT\n"
            "invalid.syntax.email,Bad,NoCorp,UNPROCESSED\n"
        )
        r = client.post("/api/sheet/upload-csv", json={"csv_text": sample_csv})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["total_rows"], 3)
        self.assertEqual(data["mapped_fields"]["email"], "Email")
        self.assertEqual(data["mapped_fields"]["first_name"], "First Name")
        self.assertEqual(data["mapped_fields"]["company"], "Company")

    def test_API14_export_updated_csv(self):
        r = client.get("/api/sheet/export-csv")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r.headers["content-type"])
        self.assertIn("Merge Status", r.text)

    def test_API15_load_sample_dataset(self):
        r = client.post("/api/sheet/load-sample")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["success"])
        self.assertGreaterEqual(len(data["rows"]), 5)

    def test_API16_list_recipients_filtering(self):
        r_all = client.get("/api/sheet/recipients?status=all")
        self.assertEqual(r_all.status_code, 200)
        self.assertIsInstance(r_all.json(), list)

        r_sent = client.get("/api/sheet/recipients?status=EMAIL_SENT")
        self.assertEqual(r_sent.status_code, 200)
        for row in r_sent.json():
            self.assertEqual(row["merge_status"], "EMAIL_SENT")

    def test_API17_dispatch_single_row_success(self):
        # Insert a clean recipient
        conn = app_module.get_db()
        with conn:
            cur = conn.execute(
                "INSERT INTO recipients (row_index, email, first_name, company, merge_status, created_at) "
                "VALUES (101, 'john.dispatch@example.com', 'John', 'Acme', 'UNPROCESSED', '2026-10-25T00:00:00Z')"
            )
            recip_id = cur.lastrowid
            # Ensure sender account has quota
            conn.execute("UPDATE accounts SET sent_today = 10, daily_quota = 50 WHERE id = 1")
        conn.close()

        r = client.post("/api/campaign/dispatch-row", json={
            "recipient_id": recip_id,
            "subject": "Hello {{First Name}} at {{Company}}",
            "body_html": "<p>Hi {{First Name}}</p>"
        })
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["merge_status"], "EMAIL_SENT")
        self.assertEqual(data["account_sent_today"], 11)

    def test_API18_dispatch_hard_bounce_suppression_and_no_quota_increment(self):
        conn = app_module.get_db()
        with conn:
            cur = conn.execute(
                "INSERT INTO recipients (row_index, email, first_name, company, merge_status, created_at) "
                "VALUES (102, 'dead.user550@rejected.org', 'Dead', 'Bounce Corp', 'UNPROCESSED', '2026-10-25T00:00:00Z')"
            )
            recip_id = cur.lastrowid
            conn.execute("UPDATE accounts SET sent_today = 20, daily_quota = 50, app_password = 'mockpassword' WHERE id = 1")
        conn.close()

        # Mock SMTP to simulate 550 permanent bounce
        with patch("main.send_via_smtp_relay") as mock_send:
            mock_send.return_value = {
                "success": False,
                "recipient": "dead.user550@rejected.org",
                "status": "hard_bounce",
                "permanent_suppress": True,
                "error": "550 5.1.1 User unknown"
            }
            r = client.post("/api/campaign/dispatch-row", json={
                "recipient_id": recip_id,
                "subject": "Hello",
                "body_html": "<p>Hello</p>"
            })

        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertFalse(data["success"])
        self.assertEqual(data["merge_status"], "EMAIL_BOUNCED")
        # Quota MUST NOT be incremented for hard bounces
        self.assertEqual(data["account_sent_today"], 20)

        # Recipient must be in suppression list
        conn = app_module.get_db()
        supp = conn.execute("SELECT * FROM suppression_list WHERE email = 'dead.user550@rejected.org'").fetchone()
        conn.close()
        self.assertIsNotNone(supp)

    def test_API19_dispatch_quota_exceeded(self):
        conn = app_module.get_db()
        with conn:
            cur = conn.execute(
                "INSERT INTO recipients (row_index, email, first_name, company, merge_status, created_at) "
                "VALUES (103, 'quota.test@example.com', 'Quota', 'Test', 'UNPROCESSED', '2026-10-25T00:00:00Z')"
            )
            recip_id = cur.lastrowid
            # Set all accounts to quota full
            conn.execute("UPDATE accounts SET sent_today = daily_quota")
        conn.close()

        r = client.post("/api/campaign/dispatch-row", json={
            "recipient_id": recip_id,
            "subject": "Hello",
            "body_html": "<p>Hello</p>"
        })
        self.assertEqual(r.status_code, 429)

    @patch("main.smtplib.SMTP")
    def test_API20_verify_smtp_credentials(self, mock_smtp_cls):
        mock_server = MagicMock()
        mock_smtp_cls.return_value = mock_server

        # Test successful verification
        r = client.post("/api/accounts/verify-smtp", json={
            "email": "verified.outreach@gmail.com",
            "app_password": "abcd efgh ijkl mnop",
            "display_name": "Test Sender",
            "daily_quota": 50
        })
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["account"]["email"], "verified.outreach@gmail.com")
        mock_server.login.assert_called_once()


if __name__ == "__main__":
    unittest.main()
