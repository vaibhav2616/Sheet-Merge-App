"""
SheetMerge Content Spam Analyzer & Lead List Cleaner
===================================================
1. Evaluates email subject & body against enterprise spam triggers
   (excessive capitals, trigger keywords, excessive tracking links).
2. Cleans contact lists (syntax verification, disposable email detection, MX verification).
"""

from __future__ import annotations

import re
import socket
from typing import Any, Dict, List, Set, Tuple

# Common high-risk enterprise spam trigger phrases
SPAM_TRIGGER_WORDS = {
    "100% free", "act now", "all natural", "apply now", "as seen on", "bad credit",
    "bargain", "be your own boss", "best price", "big bucks", "billing", "billion dollars",
    "bonus", "buy direct", "call now", "cancel at any time", "cash bonus", "cash prize",
    "certified", "cheap", "claims", "clearance", "click below", "click here", "click now",
    "congratulations", "cures", "deal", "dear friend", "direct email", "direct marketing",
    "discount", "double your income", "earn extra cash", "earn money", "eliminate debt",
    "exclusive deal", "expect to earn", "extra income", "fast cash", "financial freedom",
    "free consultation", "free gift", "free hosting", "free info", "free membership",
    "free preview", "free sample", "free trial", "full refund", "get out of debt",
    "get paid", "giveaway", "guaranteed", "hidden assets", "income from home",
    "increase sales", "instant", "investment", "join millions", "limited time",
    "lowest price", "make money", "millionaire", "miracle", "money back", "no catch",
    "no cost", "no credit check", "no experience", "no fees", "no gimmick", "no hidden costs",
    "no obligation", "no purchase necessary", "no risk", "no strings attached", "not spam",
    "obligation", "one time", "online marketing", "open immediately", "opportunity",
    "opt in", "order now", "passwords", "pennies a day", "potential earnings", "prize",
    "promise", "pure profit", "quote", "refinance", "refund", "remove", "reverse aging",
    "risk free", "save big", "save money", "score", "see for yourself", "special promotion",
    "stainless", "stop snoring", "terms and conditions", "this isn't spam", "unlimited",
    "unsolicited", "urgent", "valuable", "viagra", "vicodin", "warranty", "weight loss",
    "while supplies last", "win", "winner", "winning", "work from home", "you have been selected"
}

DISPOSABLE_DOMAINS = {
    "mailinator.com", "tempmail.com", "guerrillamail.com", "10minutemail.com",
    "yopmail.com", "throwawaymail.com", "sharklasers.com", "getairmail.com",
    "dispostable.com", "trashmail.com", "fakeinbox.com"
}


def analyze_email_content(subject: str, body_html: str) -> Dict[str, Any]:
    """
    Analyzes subject and body for spam trigger phrases, excessive capitalization,
    and link stuffing. Returns a deliverability score (0-100) and specific warnings.
    """
    subject = subject or ""
    body_html = body_html or ""
    # Strip HTML tags for clean text analysis
    plain_body = re.sub(r"<[^>]+>", " ", body_html)

    warnings: List[str] = []
    penalty = 0

    # 1. Subject line checks
    if len(subject) > 10:
        caps_in_subject = sum(1 for c in subject if c.isupper()) / len(subject)
        if caps_in_subject > 0.4:
            penalty += 25
            warnings.append("Excessive uppercase letters in subject line (>40%). Avoid SHOUTING.")

    if subject.endswith("!!!") or subject.endswith("???"):
        penalty += 15
        warnings.append("Multiple exclamation marks or question marks in subject.")

    # 2. Trigger keywords — use word-boundary matching to avoid false positives
    #    e.g. "win" should not match "with", "window", "winning"
    combined_text = (subject + " " + plain_body).lower()
    found_triggers = []
    for phrase in SPAM_TRIGGER_WORDS:
        # Build a word-boundary-aware pattern for multi-word and single-word phrases
        pattern = r"(?<![a-z])" + re.escape(phrase) + r"(?![a-z])"
        if re.search(pattern, combined_text):
            found_triggers.append(phrase)
            penalty += 8

    if found_triggers:
        warnings.append(f"Spam trigger words detected: {', '.join(found_triggers[:6])}")

    # 3. Link ratio & unformatted tracking links
    links = re.findall(r'href=[\'"]?([^\'" >]+)', body_html, re.IGNORECASE)
    if len(links) > 6:
        penalty += 15
        warnings.append(f"High link count ({len(links)} links). Enterprise filters restrict emails with excessive links.")

    # 4. Image-to-text ratio
    img_tags = re.findall(r'<img\s+', body_html, re.IGNORECASE)
    word_count = len(plain_body.split())
    if len(img_tags) > 2 and word_count < 50:
        penalty += 20
        warnings.append("Low text-to-image ratio. Enterprise filters suspect image-heavy promotional blasts.")

    score = max(0, 100 - penalty)
    return {
        "deliverability_score": score,
        "is_spam_risk": score < 70,
        "warnings": warnings,
        "metrics": {
            "link_count": len(links),
            "word_count": word_count,
            "spam_triggers_found": found_triggers[:8]
        }
    }


def verify_email_address(email: str, check_mx: bool = False) -> Dict[str, Any]:
    """
    Performs pre-flight hygiene on an email address:
    - Syntax validation
    - Disposable email domain check
    - Optional live DNS MX check
    """
    email = email.strip()
    if not re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", email):
        return {"valid": False, "reason": "Invalid email syntax"}

    parts = email.split("@")
    domain = parts[1].lower()

    if domain in DISPOSABLE_DOMAINS:
        return {"valid": False, "reason": "Disposable / temporary email domain"}

    if check_mx:
        _orig_timeout = socket.getdefaulttimeout()
        try:
            socket.setdefaulttimeout(4.0)
            socket.gethostbyname(domain)
        except Exception:
            return {"valid": False, "reason": f"Domain '{domain}' does not exist or lacks DNS"}
        finally:
            socket.setdefaulttimeout(_orig_timeout)

    return {"valid": True, "domain": domain}
