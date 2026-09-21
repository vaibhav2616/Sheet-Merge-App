"""
SheetMerge SMTP Relay & Hard Bounce Handler
===========================================
Enterprise-grade SMTP dispatcher supporting:
- Authenticated relays (SendGrid, Mailgun, Postmark, Google Workspace Relay)
- Configured socket timeouts (timeout=30)
- Instant hard bounce (5xx) interception and permanent suppression
- Randomized throttling jitter (2-5s)
"""

from __future__ import annotations

import os
import random
import smtplib
import socket
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional


class SMTPRelayConfig:
    def __init__(
        self,
        host: str = "smtp.gmail.com",
        port: int = 587,
        username: str = "",
        password: str = "",
        use_tls: bool = True,
        timeout: float = 30.0,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.timeout = timeout


def send_via_smtp_relay(
    config: SMTPRelayConfig,
    sender: str,
    recipient: str,
    subject: str,
    body_html: str,
    body_text: Optional[str] = None,
    reply_to: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Sends an email using configured SMTP relay with explicit socket timeout,
    catching permanent 5xx hard bounces and transient 4xx errors.
    """
    # Create MIME message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    if reply_to:
        msg["Reply-To"] = reply_to

    # Plain text fallback
    plain_content = body_text or "Please view this message in an HTML-capable email client."
    msg.attach(MIMEText(plain_content, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    try:
        # Enforce explicit socket timeout to prevent indefinite hangs
        server = smtplib.SMTP(config.host, config.port, timeout=config.timeout)
        if config.use_tls:
            server.starttls()
        if config.username and config.password:
            server.login(config.username, config.password)

        server.sendmail(sender, [recipient], msg.as_string())
        server.quit()
        return {
            "success": True,
            "recipient": recipient,
            "status": "delivered",
            "message": "Accepted by relay server"
        }

    except smtplib.SMTPRecipientsRefused as e:
        # Hard bounce: Recipient server rejected immediately (e.g. 550 5.4.1 User unknown)
        code, err_msg = e.recipients.get(recipient, (550, b"Recipient rejected"))
        err_str = err_msg.decode("utf-8", errors="ignore") if isinstance(err_msg, bytes) else str(err_msg)
        is_permanent_5xx = 500 <= code < 600 or "550" in err_str
        return {
            "success": False,
            "recipient": recipient,
            "status": "hard_bounce" if is_permanent_5xx else "soft_bounce",
            "code": code,
            "error": f"Recipient Refused ({code}): {err_str}",
            "permanent_suppress": is_permanent_5xx
        }

    except smtplib.SMTPResponseException as e:
        is_permanent_5xx = 500 <= e.smtp_code < 600
        return {
            "success": False,
            "recipient": recipient,
            "status": "hard_bounce" if is_permanent_5xx else "transient_error",
            "code": e.smtp_code,
            "error": f"SMTP Error ({e.smtp_code}): {str(e.smtp_error)}",
            "permanent_suppress": is_permanent_5xx
        }

    except socket.timeout:
        return {
            "success": False,
            "recipient": recipient,
            "status": "timeout",
            "error": f"Connection timed out after {config.timeout}s",
            "permanent_suppress": False
        }

    except Exception as e:
        err_str = str(e)
        is_5xx = "550" in err_str or "554" in err_str or "permanent" in err_str.lower()
        return {
            "success": False,
            "recipient": recipient,
            "status": "hard_bounce" if is_5xx else "failed",
            "error": err_str,
            "permanent_suppress": is_5xx
        }


def get_random_throttle_delay(min_s: float = 2.0, max_s: float = 5.0) -> float:
    """Returns randomized throttling delay to avoid firewall connection spike detection."""
    return random.uniform(min_s, max_s)
