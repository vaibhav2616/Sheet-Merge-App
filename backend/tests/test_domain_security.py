"""
tests/test_domain_security.py
==============================
Unit and virtual-scenario tests for backend/domain_security.py

All DNS calls are fully mocked — dnspython is NOT required to run these tests.
"""
from __future__ import annotations
import sys, os, unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import domain_security


def _dns_answer(txt_strings):
    answers = []
    for s in txt_strings:
        rec = MagicMock()
        rec.strings = [s]
        answers.append(rec)
    return answers


def _mx_answer(records):
    answers = []
    for pref, exchange in records:
        rec = MagicMock()
        rec.preference = pref
        exch = MagicMock()
        exch.to_text.return_value = exchange + "."
        rec.exchange = exch
        answers.append(rec)
    return answers


class _FakeNXDOMAIN(Exception):
    pass


def _make_resolver_side_effects(*, mx=None, spf=None, dmarc=None, dkim=None,
                                 mx_err=False, spf_err=False, dmarc_err=False, dkim_err=False):
    def _resolve(qname, rdtype):
        qname = str(qname)
        if rdtype == "MX":
            if mx_err: raise _FakeNXDOMAIN()
            return _mx_answer(mx or [])
        if rdtype == "TXT":
            if "_dmarc." in qname:
                if dmarc_err: raise _FakeNXDOMAIN()
                return _dns_answer(dmarc or [])
            if "._domainkey." in qname:
                if dkim_err: raise _FakeNXDOMAIN()
                return _dns_answer(dkim or [])
            if spf_err: raise _FakeNXDOMAIN()
            return _dns_answer(spf or [])
        raise _FakeNXDOMAIN()
    return _resolve


class TestDomainSecurity(unittest.TestCase):

    def _run(self, resolver_fn, domain="example.com"):
        mock_dns = MagicMock()
        mock_resolver_instance = MagicMock()
        mock_resolver_instance.resolve.side_effect = resolver_fn
        mock_dns.resolver.Resolver.return_value = mock_resolver_instance
        mock_dns.resolver.NXDOMAIN = _FakeNXDOMAIN

        with patch.object(domain_security, "DNS_AVAILABLE", True), \
             patch.object(domain_security, "dns", mock_dns, create=True):
            return domain_security.check_domain_dns(domain, dkim_selector="google")

    def test_01_all_records_enterprise_ready(self):
        fn = _make_resolver_side_effects(
            mx=[(10, "mail.example.com")],
            spf=[b"v=spf1 include:_spf.google.com -all"],
            dmarc=[b"v=DMARC1; p=reject; rua=mailto:dmarc@example.com;"],
            dkim=[b"v=DKIM1; k=rsa; p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQ"],
        )
        r = self._run(fn)
        self.assertTrue(r["enterprise_ready"])
        self.assertTrue(r["mx"]["configured"])
        self.assertTrue(r["spf"]["configured"])
        self.assertTrue(r["dmarc"]["configured"])
        self.assertTrue(r["dkim"]["configured"])

    def test_02_missing_mx_not_enterprise_ready(self):
        fn = _make_resolver_side_effects(
            mx_err=True,
            spf=[b"v=spf1 -all"],
            dmarc=[b"v=DMARC1; p=none;"],
            dkim=[b"v=DKIM1; k=rsa; p=abc"],
        )
        r = self._run(fn)
        self.assertFalse(r["enterprise_ready"])
        self.assertFalse(r["mx"]["configured"])
        self.assertTrue(any("MX" in rec for rec in r["recommendations"]))

    def test_03_spf_soft_fail_tilde_valid(self):
        fn = _make_resolver_side_effects(
            mx=[(10, "mail.x.com")],
            spf=[b"v=spf1 include:_spf.google.com ~all"],
            dmarc=[b"v=DMARC1; p=none;"],
            dkim=[b"v=DKIM1; k=rsa; p=abc"],
        )
        r = self._run(fn)
        self.assertTrue(r["spf"]["valid"])

    def test_04_spf_neutral_qall_not_valid(self):
        fn = _make_resolver_side_effects(
            mx=[(10, "mail.x.com")],
            spf=[b"v=spf1 ?all"],
            dmarc=[b"v=DMARC1; p=none;"],
            dkim=[b"v=DKIM1; k=rsa; p=abc"],
        )
        r = self._run(fn)
        self.assertFalse(r["spf"]["valid"])

    def test_05_dmarc_policy_reject_extracted(self):
        fn = _make_resolver_side_effects(
            mx=[(10, "m.x.com")],
            spf=[b"v=spf1 -all"],
            dmarc=[b"v=DMARC1; p=reject; sp=reject;"],
            dkim=[b"v=DKIM1; k=rsa; p=abc"],
        )
        r = self._run(fn)
        self.assertEqual(r["dmarc"]["policy"], "reject")

    def test_06_dmarc_policy_none_extracted(self):
        fn = _make_resolver_side_effects(
            mx=[(10, "m.x.com")],
            spf=[b"v=spf1 -all"],
            dmarc=[b"v=DMARC1; p=none;"],
            dkim=[b"v=DKIM1; k=rsa; p=abc"],
        )
        r = self._run(fn)
        self.assertEqual(r["dmarc"]["policy"], "none")

    def test_07_missing_dkim_recommendation_added(self):
        fn = _make_resolver_side_effects(
            mx=[(10, "m.x.com")],
            spf=[b"v=spf1 -all"],
            dmarc=[b"v=DMARC1; p=none;"],
            dkim_err=True,
        )
        r = self._run(fn)
        self.assertFalse(r["dkim"]["configured"])
        self.assertTrue(any("DKIM" in rec for rec in r["recommendations"]))

    def test_08_no_recommendations_when_all_ok(self):
        fn = _make_resolver_side_effects(
            mx=[(10, "mail.example.com")],
            spf=[b"v=spf1 -all"],
            dmarc=[b"v=DMARC1; p=quarantine;"],
            dkim=[b"v=DKIM1; k=rsa; p=abc"],
        )
        r = self._run(fn)
        self.assertEqual(r["recommendations"], [])

    def test_10_domain_normalized(self):
        with patch.object(domain_security, "DNS_AVAILABLE", False), \
             patch("domain_security.socket.gethostbyname", return_value="1.2.3.4"), \
             patch("domain_security.socket.getdefaulttimeout", return_value=None), \
             patch("domain_security.socket.setdefaulttimeout"):
            r = domain_security.check_domain_dns("  EXAMPLE.COM  ", "google")
        self.assertEqual(r["domain"], "example.com")


if __name__ == "__main__":
    unittest.main()
