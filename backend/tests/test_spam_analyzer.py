"""
tests/test_spam_analyzer.py
============================
Unit and virtual-scenario tests for backend/spam_analyzer.py

Scenarios:
  SA-01  Clean professional email -> high score, no warnings
  SA-02  Subject with >40% uppercase -> penalty applied
  SA-03  Multiple trailing exclamation marks in subject -> penalty
  SA-04  Body containing known spam trigger words -> score drops
  SA-05  More than 6 links in body -> high-link penalty
  SA-06  Image-heavy with low word count -> image-ratio penalty
  SA-07  Score is clamped at 0 (never negative)
  SA-08  Score is clamped at 100 (never over 100)
  VE-01  Valid email address passes verification
  VE-02  Malformed email (no @) fails syntax check
  VE-03  Disposable domain (mailinator.com) is rejected
  VE-04  check_mx=True, domain resolves -> passes
  VE-05  check_mx=True, domain does NOT resolve -> fails
"""
from __future__ import annotations
import sys, os, unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from spam_analyzer import analyze_email_content, verify_email_address


class TestAnalyzeEmailContent(unittest.TestCase):

    def test_01_clean_email_high_score(self):
        r = analyze_email_content(
            "Following up on our conversation",
            "<p>Hi John, I wanted to share our case study with you. Best regards.</p>",
        )
        self.assertGreaterEqual(r["deliverability_score"], 80)
        self.assertFalse(r["is_spam_risk"])
        self.assertEqual(r["warnings"], [])

    def test_02_excessive_caps_in_subject(self):
        # ALLCAPS subject (100% uppercase letters among alpha)
        r = analyze_email_content(
            "URGENT ACTION REQUIRED NOW",
            "<p>Please read this important message.</p>",
        )
        self.assertLess(r["deliverability_score"], 100)
        self.assertTrue(any("uppercase" in w.lower() for w in r["warnings"]))

    def test_03_triple_exclamation_subject(self):
        r = analyze_email_content(
            "Limited time offer!!!",
            "<p>Act now to claim your prize.</p>",
        )
        self.assertTrue(any("exclamation" in w.lower() for w in r["warnings"]))

    def test_04_spam_trigger_words_in_body(self):
        r = analyze_email_content(
            "Hello",
            "<p>Click here to get a free gift and win cash bonus prizes today.</p>",
        )
        self.assertTrue(r["is_spam_risk"])
        self.assertTrue(any("trigger" in w.lower() for w in r["warnings"]))

    def test_05_too_many_links(self):
        links = " ".join(
            [f'<a href="https://example.com/page{i}">link</a>' for i in range(8)]
        )
        r = analyze_email_content("Update", f"<p>Check these out: {links}</p>")
        self.assertTrue(any("link count" in w.lower() for w in r["warnings"]))
        self.assertGreater(r["metrics"]["link_count"], 6)

    def test_06_image_heavy_low_text(self):
        imgs = "<img src='x.png'><img src='y.png'><img src='z.png'>"
        r = analyze_email_content("News", f"<p>See: {imgs}</p>")
        self.assertTrue(any("image" in w.lower() for w in r["warnings"]))

    def test_07_score_never_negative(self):
        # Stack many triggers
        bad = " ".join(["click here", "free gift", "act now", "win", "guaranteed",
                        "earn money", "discount", "urgent", "cash bonus",
                        "limited time", "special promotion"])
        r = analyze_email_content("CLICK NOW FREE MONEY!!!", f"<p>{bad}</p>")
        self.assertGreaterEqual(r["deliverability_score"], 0)

    def test_08_score_never_exceeds_100(self):
        r = analyze_email_content("Hello", "<p>Hi there.</p>")
        self.assertLessEqual(r["deliverability_score"], 100)

    def test_metrics_keys_always_present(self):
        r = analyze_email_content("", "")
        self.assertIn("link_count", r["metrics"])
        self.assertIn("word_count", r["metrics"])
        self.assertIn("spam_triggers_found", r["metrics"])


class TestVerifyEmailAddress(unittest.TestCase):

    def test_VE01_valid_email(self):
        r = verify_email_address("john.doe@company.com")
        self.assertTrue(r["valid"])
        self.assertEqual(r["domain"], "company.com")

    def test_VE02_malformed_no_at_sign(self):
        r = verify_email_address("notanemail")
        self.assertFalse(r["valid"])
        self.assertIn("syntax", r["reason"].lower())

    def test_VE03_disposable_domain(self):
        r = verify_email_address("temp@mailinator.com")
        self.assertFalse(r["valid"])
        self.assertIn("disposable", r["reason"].lower())

    def test_VE04_check_mx_resolves(self):
        with patch("spam_analyzer.socket.gethostbyname", return_value="1.2.3.4"):
            r = verify_email_address("u@realcompany.com", check_mx=True)
        self.assertTrue(r["valid"])

    def test_VE05_check_mx_no_resolution(self):
        import socket as _sock
        dns_err = _sock.gaierror("not found")
        with patch("spam_analyzer.socket.gethostbyname", side_effect=dns_err):
            r = verify_email_address("u@fakefake999.xyz", check_mx=True)
        self.assertFalse(r["valid"])
        self.assertIn("does not exist", r["reason"])

    def test_VE06_leading_trailing_whitespace_stripped(self):
        r = verify_email_address("  clean@example.com  ")
        self.assertTrue(r["valid"])


if __name__ == "__main__":
    unittest.main()
