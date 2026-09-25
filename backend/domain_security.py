"""
SheetMerge Domain Verification & Security Inspector
===================================================
Inspects SPF, DKIM, DMARC, MX records, and SMTP configurations
to verify compliance with Google, Microsoft 365, and Yahoo deliverability standards.
"""

from __future__ import annotations

import re
import socket
from typing import Any, Dict, List, Optional

try:
    import dns.resolver
    DNS_AVAILABLE = True
except ImportError:
    DNS_AVAILABLE = False


def check_domain_dns(domain: str, dkim_selector: str = "google") -> Dict[str, Any]:
    """
    Performs comprehensive DNS check for SPF, DKIM, DMARC, and MX records.
    Returns deliverability readiness score and actionable recommendations.
    """
    domain = domain.strip().lower()
    results: Dict[str, Any] = {
        "domain": domain,
        "mx": {"configured": False, "records": []},
        "spf": {"configured": False, "record": None, "valid": False, "details": ""},
        "dmarc": {"configured": False, "record": None, "policy": None, "details": ""},
        "dkim": {"configured": False, "record": None, "selector": dkim_selector, "details": ""},
        "enterprise_ready": False,
        "recommendations": []
    }

    if not DNS_AVAILABLE:
        # Fallback to standard socket for MX (save/restore global timeout to avoid state leaks)
        _orig_timeout = socket.getdefaulttimeout()
        try:
            socket.setdefaulttimeout(10.0)
            addr = socket.gethostbyname(domain)
            results["mx"]["configured"] = bool(addr)
            results["mx"]["records"] = [addr]
        except Exception as e:
            results["recommendations"].append(f"Domain lookup failed: {str(e)}")
        finally:
            socket.setdefaulttimeout(_orig_timeout)
        results["recommendations"].append("Install dnspython for full SPF/DKIM/DMARC deep inspection.")
        return results

    resolver = dns.resolver.Resolver()
    resolver.timeout = 2.0
    resolver.lifetime = 2.0

    # 1. MX Records
    try:
        mx_answers = resolver.resolve(domain, "MX")
        mx_list = [f"{r.preference} {r.exchange.to_text().rstrip('.')}" for r in mx_answers]
        results["mx"]["configured"] = len(mx_list) > 0
        results["mx"]["records"] = mx_list
    except Exception as e:
        results["recommendations"].append(f"Missing or invalid MX records: {str(e)}")

    # 2. SPF Record
    try:
        txt_answers = resolver.resolve(domain, "TXT")
        for r in txt_answers:
            txt_str = "".join([part.decode("utf-8", errors="ignore") for part in r.strings])
            if txt_str.startswith("v=spf1"):
                results["spf"]["configured"] = True
                results["spf"]["record"] = txt_str
                if "~all" in txt_str or "-all" in txt_str:
                    results["spf"]["valid"] = True
                    results["spf"]["details"] = "Strict/Soft-fail policy enforced."
                else:
                    results["spf"]["details"] = "SPF policy present but neutral (?all)."
                break
        if not results["spf"]["configured"]:
            results["recommendations"].append("Publish an SPF TXT record (e.g. 'v=spf1 include:_spf.google.com ~all').")
    except Exception as e:
        results["recommendations"].append("No SPF TXT record found.")

    # 3. DMARC Record
    try:
        dmarc_domain = f"_dmarc.{domain}"
        dmarc_answers = resolver.resolve(dmarc_domain, "TXT")
        for r in dmarc_answers:
            txt_str = "".join([part.decode("utf-8", errors="ignore") for part in r.strings])
            if txt_str.startswith("v=DMARC1"):
                results["dmarc"]["configured"] = True
                results["dmarc"]["record"] = txt_str
                # Extract policy
                match = re.search(r"p=(none|quarantine|reject)", txt_str)
                if match:
                    results["dmarc"]["policy"] = match.group(1)
                results["dmarc"]["details"] = f"DMARC policy is set to '{results['dmarc']['policy']}'."
                break
        if not results["dmarc"]["configured"]:
            results["recommendations"].append("Publish a DMARC TXT record on '_dmarc." + domain + "' (e.g. 'v=DMARC1; p=none; sp=none;').")
    except Exception as e:
        results["recommendations"].append("Missing DMARC record on _dmarc." + domain)

    # 4. DKIM Record
    try:
        dkim_domain = f"{dkim_selector}._domainkey.{domain}"
        dkim_answers = resolver.resolve(dkim_domain, "TXT")
        for r in dkim_answers:
            txt_str = "".join([part.decode("utf-8", errors="ignore") for part in r.strings])
            if "v=DKIM1" in txt_str or "k=rsa" in txt_str or "p=" in txt_str:
                results["dkim"]["configured"] = True
                results["dkim"]["record"] = txt_str[:60] + "..."
                results["dkim"]["details"] = f"Valid DKIM key found for selector '{dkim_selector}'."
                break
        if not results["dkim"]["configured"]:
            results["recommendations"].append(f"Verify DKIM key on '{dkim_selector}._domainkey.{domain}'.")
    except Exception:
        results["recommendations"].append(f"No DKIM record detected on '{dkim_selector}._domainkey.{domain}'.")

    # Enterprise Readiness Score
    is_ready = (
        results["mx"]["configured"]
        and results["spf"]["configured"]
        and results["dmarc"]["configured"]
    )
    results["enterprise_ready"] = is_ready
    return results
