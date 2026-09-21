"""
tests/test_smtp_relay.py
========================
Unit and virtual-scenario tests for backend/smtp_relay.py

Scenarios:
  SMTP-01  Successful delivery via authenticated relay
  SMTP-02  5xx hard bounce (SMTPRecipientsRefused 550) -> permanent_suppress=True
  SMTP-03  4xx transient bounce (SMTPResponseException 421) -> permanent_suppress=False
  SMTP-04  Socket timeout -> permanent_suppress=False, status='timeout'
  SMTP-05  SMTPResponseException 554 (permanent) -> permanent_suppress=True
  SMTP-06  Generic exception containing "550" -> treated as hard bounce
  SMTP-07  get_random_throttle_delay stays within [min, max] bounds
  SMTP-08  HTML-only body produces plain-text fallback in MIME
  SMTP-09  reply_to header is injected correctly
  SMTP-10  No-TLS path skips starttls()
"""
from __future__ import annotations
import smtplib, socket, sys, os, unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from smtp_relay import SMTPRelayConfig, get_random_throttle_delay, send_via_smtp_relay


def _cfg(**kw):
    d = dict(host="smtp.gmail.com", port=587, username="u@x.com",
             password="pw", use_tls=True, timeout=30.0)
    d.update(kw)
    return SMTPRelayConfig(**d)


class TestThrottleDelay(unittest.TestCase):
    def test_default_bounds(self):
        for _ in range(200):
            d = get_random_throttle_delay()
            self.assertGreaterEqual(d, 2.0)
            self.assertLessEqual(d, 5.0)

    def test_custom_bounds(self):
        for _ in range(200):
            d = get_random_throttle_delay(1.0, 2.0)
            self.assertGreaterEqual(d, 1.0)
            self.assertLessEqual(d, 2.0)

    def test_degenerate_min_equals_max(self):
        self.assertAlmostEqual(get_random_throttle_delay(3.0, 3.0), 3.0, places=5)


class TestSmtpSend(unittest.TestCase):

    @patch("smtp_relay.smtplib.SMTP")
    def test_01_successful_delivery(self, mSMTP):
        srv = MagicMock()
        mSMTP.return_value = srv
        r = send_via_smtp_relay(_cfg(), "f@x.com", "t@x.com", "Hi", "<p>Hi</p>")
        self.assertTrue(r["success"])
        self.assertEqual(r["status"], "delivered")
        srv.starttls.assert_called_once()
        srv.login.assert_called_once()
        srv.sendmail.assert_called_once()
        srv.quit.assert_called_once()

    @patch("smtp_relay.smtplib.SMTP")
    def test_02_550_hard_bounce(self, mSMTP):
        srv = MagicMock()
        mSMTP.return_value = srv
        srv.sendmail.side_effect = smtplib.SMTPRecipientsRefused(
            {"to@bad.com": (550, b"5.1.1 User unknown")})
        r = send_via_smtp_relay(_cfg(), "f@x.com", "to@bad.com", "Hi", "<p>Hi</p>")
        self.assertFalse(r["success"])
        self.assertEqual(r["status"], "hard_bounce")
        self.assertTrue(r["permanent_suppress"])
        self.assertEqual(r["code"], 550)

    @patch("smtp_relay.smtplib.SMTP")
    def test_03_421_transient_error(self, mSMTP):
        srv = MagicMock()
        mSMTP.return_value = srv
        srv.sendmail.side_effect = smtplib.SMTPResponseException(421, b"Temp unavailable")
        r = send_via_smtp_relay(_cfg(), "f@x.com", "t@x.com", "Hi", "<p>Hi</p>")
        self.assertFalse(r["success"])
        self.assertEqual(r["status"], "transient_error")
        self.assertFalse(r["permanent_suppress"])

    @patch("smtp_relay.smtplib.SMTP")
    def test_04_socket_timeout(self, mSMTP):
        mSMTP.side_effect = socket.timeout("timed out")
        r = send_via_smtp_relay(_cfg(timeout=1.0), "f@x.com", "t@x.com", "Hi", "<p>Hi</p>")
        self.assertFalse(r["success"])
        self.assertEqual(r["status"], "timeout")
        self.assertFalse(r["permanent_suppress"])

    @patch("smtp_relay.smtplib.SMTP")
    def test_05_554_permanent_smtpresponse(self, mSMTP):
        srv = MagicMock()
        mSMTP.return_value = srv
        srv.sendmail.side_effect = smtplib.SMTPResponseException(554, b"Transaction failed")
        r = send_via_smtp_relay(_cfg(), "f@x.com", "t@x.com", "Hi", "<p>Hi</p>")
        self.assertFalse(r["success"])
        self.assertTrue(r["permanent_suppress"])

    @patch("smtp_relay.smtplib.SMTP")
    def test_06_generic_exception_with_550_text(self, mSMTP):
        srv = MagicMock()
        mSMTP.return_value = srv
        srv.sendmail.side_effect = Exception("550 address does not exist")
        r = send_via_smtp_relay(_cfg(), "f@x.com", "t@x.com", "Hi", "<p>Hi</p>")
        self.assertFalse(r["success"])
        self.assertTrue(r["permanent_suppress"])
        self.assertEqual(r["status"], "hard_bounce")

    @patch("smtp_relay.smtplib.SMTP")
    def test_08_html_only_builds_plain_fallback(self, mSMTP):
        srv = MagicMock()
        mSMTP.return_value = srv
        send_via_smtp_relay(_cfg(), "f@x.com", "t@x.com", "Hi", "<p>Rich</p>", body_text=None)
        raw = srv.sendmail.call_args[0][2]
        self.assertIn("Rich", raw)
        self.assertIn("Please view this message", raw)

    @patch("smtp_relay.smtplib.SMTP")
    def test_09_reply_to_header_injected(self, mSMTP):
        srv = MagicMock()
        mSMTP.return_value = srv
        send_via_smtp_relay(_cfg(), "f@x.com", "t@x.com", "Hi", "<p>Hi</p>",
                            reply_to="reply@company.com")
        raw = srv.sendmail.call_args[0][2]
        self.assertIn("reply@company.com", raw)

    @patch("smtp_relay.smtplib.SMTP")
    def test_10_no_tls_skips_starttls(self, mSMTP):
        srv = MagicMock()
        mSMTP.return_value = srv
        send_via_smtp_relay(_cfg(use_tls=False), "f@x.com", "t@x.com", "Hi", "<p>Hi</p>")
        srv.starttls.assert_not_called()


if __name__ == "__main__":
    unittest.main()
