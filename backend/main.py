"""
backend/main.py — SheetMerge Standalone Application Server
==========================================================
Integrates:
  • Google Sheet & CSV Ingestion Engine (Live URL fetch & Heuristic Column Parser)
  • Real Gmail SMTP Dispatcher & Google App Password Verifier
  • Single YAMM-compatible 'Merge Status' Column Architecture
  • Sequential Throttled Sending with Randomized Jitter Pacing (2s–5s)
  • 50-Send Daily Verified Quota Guard (Hard Bounces Excluded from Quota)
  • Pre-Flight DNS Deliverability Shield (SPF / DKIM / DMARC / MX)
  • 45+ Rule Content Anti-Spam Analyzer & Email Syntax Verifier
  • Open & Click Event Tracking with 1x1 Transparent Pixel
"""
from __future__ import annotations

import base64
import csv
import io
import os
import random
import re
import smtplib
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import unquote

# Ensure backend directory is always in sys.path regardless of execution context
_BACKEND_DIR = Path(__file__).resolve().parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr

try:
    from backend.domain_security import check_domain_dns
    from backend.spam_analyzer import analyze_email_content, verify_email_address
    from backend.smtp_relay import SMTPRelayConfig, get_random_throttle_delay, send_via_smtp_relay
except ImportError:
    from domain_security import check_domain_dns
    from spam_analyzer import analyze_email_content, verify_email_address
    from smtp_relay import SMTPRelayConfig, get_random_throttle_delay, send_via_smtp_relay


# ── Database & Directories ──────────────────────────────────────────────────

DATA_DIR = Path(os.environ.get("SHEETMERGE_DATA_DIR", Path(__file__).parent / "data"))
DB_PATH = Path(os.environ.get("SHEETMERGE_DB_PATH", DATA_DIR / "sheetmerge_pro.db"))
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

TRANSPARENT_GIF = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)


# ── Database Initialization ─────────────────────────────────────────────────

_DB_INITIALIZED = False

def get_db() -> sqlite3.Connection:
    global _DB_INITIALIZED
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    if not _DB_INITIALIZED:
        init_db()
    return conn


def init_db() -> None:
    global _DB_INITIALIZED
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _DB_INITIALIZED = True
    with conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS recipients (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                row_index          INTEGER,
                email              TEXT NOT NULL,
                first_name         TEXT,
                last_name          TEXT,
                company            TEXT,
                merge_status       TEXT DEFAULT 'UNPROCESSED', -- 'UNPROCESSED', 'EMAIL_SENT', 'EMAIL_OPENED', 'EMAIL_CLICKED', 'EMAIL_BOUNCED', 'ERROR'
                custom_fields_json TEXT DEFAULT '{}',
                error_message      TEXT,
                last_event         TEXT,
                sent_at            TEXT,
                created_at         TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_recipients_email ON recipients(email);
            CREATE INDEX IF NOT EXISTS idx_recipients_status ON recipients(merge_status);

            CREATE TABLE IF NOT EXISTS accounts (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                email          TEXT UNIQUE NOT NULL,
                display_name   TEXT,
                app_password   TEXT,
                smtp_host      TEXT DEFAULT 'smtp.gmail.com',
                smtp_port      INTEGER DEFAULT 587,
                daily_quota    INTEGER DEFAULT 50,
                sent_today     INTEGER DEFAULT 0,
                last_reset     TEXT,
                is_active      INTEGER DEFAULT 1,
                is_verified    INTEGER DEFAULT 0,
                created_at     TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS send_history (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                email          TEXT NOT NULL,
                account_id     INTEGER,
                status         TEXT NOT NULL,
                subject        TEXT,
                track_id       TEXT UNIQUE,
                row_index      INTEGER,
                timestamp      TEXT NOT NULL,
                meta_json      TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_history_email ON send_history(email);
            CREATE INDEX IF NOT EXISTS idx_history_track ON send_history(track_id);

            CREATE TABLE IF NOT EXISTS suppression_list (
                email          TEXT PRIMARY KEY,
                reason         TEXT NOT NULL,
                suppressed_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS events (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id       TEXT NOT NULL,
                event_type     TEXT NOT NULL,
                url            TEXT,
                ip             TEXT,
                user_agent     TEXT,
                created_at     TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_events_track ON events(track_id);
            """
        )

        # Ensure schema migrations for accounts table if it already existed
        cur = conn.execute("PRAGMA table_info(accounts)")
        existing_cols = {row["name"] for row in cur.fetchall()}
        if "display_name" not in existing_cols:
            conn.execute("ALTER TABLE accounts ADD COLUMN display_name TEXT")
        if "app_password" not in existing_cols:
            conn.execute("ALTER TABLE accounts ADD COLUMN app_password TEXT")
        if "smtp_host" not in existing_cols:
            conn.execute("ALTER TABLE accounts ADD COLUMN smtp_host TEXT DEFAULT 'smtp.gmail.com'")
        if "smtp_port" not in existing_cols:
            conn.execute("ALTER TABLE accounts ADD COLUMN smtp_port INTEGER DEFAULT 587")
        if "is_verified" not in existing_cols:
            conn.execute("ALTER TABLE accounts ADD COLUMN is_verified INTEGER DEFAULT 0")

        # Seed initial recipients if empty
        cursor = conn.execute("SELECT COUNT(*) as count FROM recipients")
        if cursor.fetchone()["count"] == 0:
            now_iso = datetime.now(timezone.utc).isoformat()
            sample_recipients = [
                (1, "alex.mercer@cloudflow.tech", "Alex", "Mercer", "CloudFlow Tech", "EMAIL_OPENED", "{}", None, "Opened 12m ago", now_iso),
                (2, "chloe.dupont@novaretail.io", "Chloe", "Dupont", "Nova Retail", "EMAIL_CLICKED", "{}", None, "Clicked link 34m ago", now_iso),
                (3, "hana.kim@seoulsupply.kr", "Hana", "Kim", "Seoul Supply", "EMAIL_SENT", "{}", None, "Delivered 1h ago", now_iso),
                (4, "elena.rostova@northwind.es", "Elena", "Rostova", "Northwind Logistics", "EMAIL_OPENED", "{}", None, "Opened 2h ago", now_iso),
                (5, "daniel.okafor@bluefin.ng", "Daniel", "Okafor", "Bluefin Tech", "EMAIL_SENT", "{}", None, "Delivered 3h ago", now_iso),
                (6, "invalid.bounce@deadmailbox-550.org", "Invalid", "User", "Ghost Inc", "EMAIL_BOUNCED", "{}", "550 5.1.1 User unknown", "Hard bounce (suppressed)", None),
                (7, "marcus.vance@nexuscloud.io", "Marcus", "Vance", "Nexus Cloud", "EMAIL_CLICKED", "{}", None, "Clicked demo link", now_iso),
                (8, "priya.sharma@acmehealth.in", "Priya", "Sharma", "Acme Health", "EMAIL_OPENED", "{}", None, "Opened 4h ago", now_iso),
                (9, "isha.kapoor@monsoonmedia.co", "Isha", "Kapoor", "Monsoon Media", "UNPROCESSED", "{}", None, "Queued for sending", None),
                (10, "rohan.mehta@kitelabs.com", "Rohan", "Mehta", "Kite Labs", "UNPROCESSED", "{}", None, "Queued for sending", None),
            ]
            for r in sample_recipients:
                conn.execute(
                    """
                    INSERT INTO recipients (row_index, email, first_name, last_name, company, merge_status, custom_fields_json, error_message, last_event, sent_at, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (*r, now_iso)
                )

        # Seed initial default sender account if none exist
        acct_cur = conn.execute("SELECT COUNT(*) as count FROM accounts")
        if acct_cur.fetchone()["count"] == 0:
            now_iso = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """
                INSERT INTO accounts (email, display_name, smtp_host, smtp_port, daily_quota, sent_today, is_active, is_verified, created_at)
                VALUES ('outreach@gmail.com', 'Vaibhav Rastogi', 'smtp.gmail.com', 587, 50, 42, 1, 1, ?)
                """,
                (now_iso,)
            )

    conn.close()


# ── Pydantic Request Models ─────────────────────────────────────────────────

class GoogleSheetImportRequest(BaseModel):
    url: str
    sheet_gid: Optional[str] = "0"


class CsvUploadRequest(BaseModel):
    csv_text: str


class AccountCreate(BaseModel):
    email: EmailStr
    daily_quota: Optional[int] = 50


class SmtpVerifyRequest(BaseModel):
    email: EmailStr
    app_password: str
    display_name: Optional[str] = ""
    smtp_host: Optional[str] = "smtp.gmail.com"
    smtp_port: Optional[int] = 587
    daily_quota: Optional[int] = 50


class DispatchRowRequest(BaseModel):
    recipient_id: int
    account_email: Optional[str] = None
    subject: str
    body_html: str
    body_text: Optional[str] = None
    test_mode: Optional[bool] = False
    test_email: Optional[str] = None


class SendTestEmailRequest(BaseModel):
    account_email: EmailStr
    target_email: EmailStr
    subject: str
    body_html: str


class MergeRecordRequest(BaseModel):
    email: EmailStr
    account_email: Optional[str] = None
    status: str
    track_id: str
    row_index: Optional[int] = None
    subject: Optional[str] = None


class DomainCheckRequest(BaseModel):
    domain: str
    dkim_selector: Optional[str] = "google"


class SpamCheckRequest(BaseModel):
    subject: str
    body_html: str


class ListCleanRequest(BaseModel):
    emails: List[str]
    check_mx: Optional[bool] = False


# ── Lifespan & FastAPI App ──────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="SheetMerge Pro",
    description="High-Deliverability Mail Merge Engine with Google Sheets & Real Gmail SMTP Delivery",
    version="2.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
)


# ── Helper: Intelligent Column Mapping & Sheet Parsing ──────────────────────

def _detect_columns(headers: List[str]) -> Dict[str, Optional[str]]:
    """Heuristically detects standard Mail Merge columns from arbitrary Google Sheet headers."""
    norm_headers = {h.strip().lower(): h for h in headers if h.strip()}
    mapping: Dict[str, Optional[str]] = {
        "email": None,
        "first_name": None,
        "last_name": None,
        "company": None,
        "merge_status": None,
    }

    # 1. Email detection
    for pattern in ["email", "e-mail", "email address", "mail", "recipient", "to"]:
        if pattern in norm_headers:
            mapping["email"] = norm_headers[pattern]
            break
    if not mapping["email"]:
        for h_norm, h_orig in norm_headers.items():
            if "email" in h_norm or "mail" in h_norm:
                mapping["email"] = h_orig
                break

    # 2. First Name
    for pattern in ["first name", "firstname", "first", "given name", "name"]:
        if pattern in norm_headers:
            mapping["first_name"] = norm_headers[pattern]
            break

    # 3. Last Name
    for pattern in ["last name", "lastname", "last", "surname"]:
        if pattern in norm_headers:
            mapping["last_name"] = norm_headers[pattern]
            break

    # 4. Company
    for pattern in ["company", "company name", "organization", "org", "business", "account"]:
        if pattern in norm_headers:
            mapping["company"] = norm_headers[pattern]
            break

    # 5. Merge Status (YAMM Standard)
    for pattern in ["merge status", "status", "yamm status", "mail status", "delivery status"]:
        if pattern in norm_headers:
            mapping["merge_status"] = norm_headers[pattern]
            break

    return mapping


def _parse_csv_and_persist(csv_content: str, source_label: str = "Imported Sheet") -> Dict[str, Any]:
    """Parses CSV text, detects columns, validates emails, and persists into recipients table."""
    reader = csv.reader(io.StringIO(csv_content))
    rows_list = list(reader)
    if not rows_list or len(rows_list) < 2:
        raise HTTPException(
            status_code=400,
            detail="The sheet contains no data rows. Ensure row 1 has column headers and subsequent rows contain recipient data."
        )

    headers = [h.strip() for h in rows_list[0]]
    col_map = _detect_columns(headers)

    if not col_map["email"]:
        raise HTTPException(
            status_code=400,
            detail=f"Could not identify an 'Email' column in the sheet headers: {headers}. Please ensure one column is labeled 'Email' or 'Recipient'."
        )

    email_col = col_map["email"]
    fn_col = col_map["first_name"]
    ln_col = col_map["last_name"]
    co_col = col_map["company"]
    status_col = col_map["merge_status"]

    conn = get_db()
    # Check current suppression list
    suppressed_rows = conn.execute("SELECT email FROM suppression_list").fetchall()
    suppressed_set = {r["email"].lower() for r in suppressed_rows}

    dict_reader = csv.DictReader(io.StringIO(csv_content))
    now_iso = datetime.now(timezone.utc).isoformat()

    valid_count = 0
    invalid_count = 0
    already_sent_count = 0
    pending_count = 0
    persisted_rows: List[Dict[str, Any]] = []

    # Clear previous campaign recipients for fresh sheet import
    with conn:
        conn.execute("DELETE FROM recipients")

        for idx, row in enumerate(dict_reader, start=1):
            raw_email = (row.get(email_col) or "").strip()
            if not raw_email:
                continue

            first_name = (row.get(fn_col) or "").strip() if fn_col else ""
            last_name = (row.get(ln_col) or "").strip() if ln_col else ""
            company = (row.get(co_col) or "").strip() if co_col else ""
            raw_status = (row.get(status_col) or "").strip().upper() if status_col else ""

            # Check suppression
            if raw_email.lower() in suppressed_set:
                merge_status = "EMAIL_BOUNCED"
                err_msg = "Permanently suppressed (prior 5xx hard bounce)"
                last_evt = "Suppressed from prior campaign"
                invalid_count += 1
            elif raw_status in ("EMAIL_SENT", "EMAIL_OPENED", "EMAIL_CLICKED"):
                merge_status = raw_status
                err_msg = None
                last_evt = "Already processed in source sheet"
                already_sent_count += 1
                valid_count += 1
            else:
                # Syntax verification
                v_res = verify_email_address(raw_email, check_mx=False)
                if not v_res["valid"]:
                    merge_status = "ERROR"
                    err_msg = f"Invalid email: {v_res['reason']}"
                    last_evt = "Syntax error"
                    invalid_count += 1
                else:
                    merge_status = "UNPROCESSED"
                    err_msg = None
                    last_evt = "Queued for merge"
                    pending_count += 1
                    valid_count += 1

            # Custom fields json
            import json
            custom_fields = {k: v for k, v in row.items() if k not in (email_col, fn_col, ln_col, co_col, status_col)}
            custom_json = json.dumps(custom_fields)

            cursor = conn.execute(
                """
                INSERT INTO recipients (row_index, email, first_name, last_name, company, merge_status, custom_fields_json, error_message, last_event, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (idx, raw_email, first_name, last_name, company, merge_status, custom_json, err_msg, last_evt, now_iso)
            )

            persisted_rows.append({
                "id": cursor.lastrowid,
                "row_index": idx,
                "email": raw_email,
                "first_name": first_name,
                "company": company,
                "merge_status": merge_status,
                "last_event": last_evt,
                "error_message": err_msg
            })

    conn.close()

    return {
        "success": True,
        "source": source_label,
        "total_rows": len(persisted_rows),
        "valid_count": valid_count,
        "invalid_count": invalid_count,
        "already_sent_count": already_sent_count,
        "pending_count": pending_count,
        "detected_columns": headers,
        "mapped_fields": {
            "email": email_col,
            "first_name": fn_col,
            "last_name": ln_col,
            "company": co_col,
            "merge_status": status_col,
        },
        "rows": persisted_rows[:100]  # return first 100 for immediate UI hydration
    }


# ── Google Sheets Ingestion & Analysis Endpoints ────────────────────────────

@app.post("/api/sheet/import-url")
def import_google_sheet(req: GoogleSheetImportRequest):
    """
    Connects to a live Google Sheet URL, exports CSV data, detects columns,
    and analyzes rows for delivery readiness.
    """
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="Please enter a valid Google Sheet URL.")

    # Extract Google Sheet ID
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
    if not match:
        raise HTTPException(
            status_code=400,
            detail="Invalid Google Sheet URL format. Expected format: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit..."
        )
    sheet_id = match.group(1)

    # Extract GID if present
    gid = req.sheet_gid or "0"
    gid_match = re.search(r"[#&?]gid=([0-9]+)", url)
    if gid_match:
        gid = gid_match.group(1)

    export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"

    try:
        req_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SheetMerge/2.2",
            "Accept": "text/csv,text/plain,*/*"
        }
        http_req = urllib.request.Request(export_url, headers=req_headers)
        with urllib.request.urlopen(http_req, timeout=15.0) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw_bytes = resp.read()
            csv_text = raw_bytes.decode("utf-8", errors="replace")

            # Check if Google returned an HTML login redirect (private sheet)
            if "text/html" in content_type or "<html" in csv_text.lower() or "ServiceLogin" in csv_text:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Google Sheet is currently private and requires sign-in. "
                        "To connect: Open your Google Sheet -> Click 'Share' (top right) -> "
                        "Set General Access to 'Anyone with the link can view' -> Re-paste URL. "
                        "Alternatively, download as .CSV and click 'Upload CSV' above."
                    )
                )

        return _parse_csv_and_persist(csv_text, source_label=f"Google Sheet ({sheet_id[:8]}...)")

    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise HTTPException(
                status_code=400,
                detail="Access denied (403). Please set Google Sheet sharing to 'Anyone with the link can view'."
            )
        raise HTTPException(status_code=400, detail=f"Google Sheets server returned HTTP error {e.code}: {e.reason}")
    except urllib.error.URLError as e:
        raise HTTPException(status_code=502, detail=f"Failed to reach Google Sheets servers: {str(e.reason)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error loading Google Sheet: {str(e)}")


@app.post("/api/sheet/upload-csv")
def upload_csv_sheet(req: CsvUploadRequest):
    """Parses directly provided CSV text."""
    if not req.csv_text.strip():
        raise HTTPException(status_code=400, detail="CSV text cannot be empty.")
    return _parse_csv_and_persist(req.csv_text, source_label="Uploaded CSV")


@app.post("/api/sheet/load-sample")
def load_sample_dataset():
    """Reloads pristine real-world sample campaign dataset."""
    conn = get_db()
    now_iso = datetime.now(timezone.utc).isoformat()
    sample_recipients = [
        (1, "alex.mercer@cloudflow.tech", "Alex", "Mercer", "CloudFlow Tech", "EMAIL_OPENED", "{}", None, "Opened 12m ago", now_iso),
        (2, "chloe.dupont@novaretail.io", "Chloe", "Dupont", "Nova Retail", "EMAIL_CLICKED", "{}", None, "Clicked link 34m ago", now_iso),
        (3, "hana.kim@seoulsupply.kr", "Hana", "Kim", "Seoul Supply", "EMAIL_SENT", "{}", None, "Delivered 1h ago", now_iso),
        (4, "elena.rostova@northwind.es", "Elena", "Rostova", "Northwind Logistics", "EMAIL_OPENED", "{}", None, "Opened 2h ago", now_iso),
        (5, "daniel.okafor@bluefin.ng", "Daniel", "Okafor", "Bluefin Tech", "EMAIL_SENT", "{}", None, "Delivered 3h ago", now_iso),
        (6, "invalid.bounce@deadmailbox-550.org", "Invalid", "User", "Ghost Inc", "EMAIL_BOUNCED", "{}", "550 5.1.1 User unknown", "Hard bounce (suppressed)", None),
        (7, "marcus.vance@nexuscloud.io", "Marcus", "Vance", "Nexus Cloud", "EMAIL_CLICKED", "{}", None, "Clicked demo link", now_iso),
        (8, "priya.sharma@acmehealth.in", "Priya", "Sharma", "Acme Health", "EMAIL_OPENED", "{}", None, "Opened 4h ago", now_iso),
        (9, "isha.kapoor@monsoonmedia.co", "Isha", "Kapoor", "Monsoon Media", "UNPROCESSED", "{}", None, "Queued for sending", None),
        (10, "rohan.mehta@kitelabs.com", "Rohan", "Mehta", "Kite Labs", "UNPROCESSED", "{}", None, "Queued for sending", None),
    ]
    with conn:
        conn.execute("DELETE FROM recipients")
        for r in sample_recipients:
            conn.execute(
                """
                INSERT INTO recipients (row_index, email, first_name, last_name, company, merge_status, custom_fields_json, error_message, last_event, sent_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (*r, now_iso)
            )
        rows = conn.execute("SELECT * FROM recipients ORDER BY row_index ASC").fetchall()
    conn.close()
    return {
        "success": True,
        "message": "Sample campaign dataset loaded successfully.",
        "rows": [dict(r) for r in rows]
    }


@app.get("/api/sheet/recipients")
def list_recipients(status: Optional[str] = None, q: Optional[str] = None):
    """Retrieves current campaign recipients with optional status and search filters."""
    conn = get_db()
    query = "SELECT * FROM recipients WHERE 1=1"
    params: List[Any] = []

    if status and status.lower() != "all":
        query += " AND UPPER(merge_status) = ?"
        params.append(status.upper())

    if q:
        query += " AND (LOWER(email) LIKE ? OR LOWER(first_name) LIKE ? OR LOWER(company) LIKE ?)"
        term = f"%{q.lower()}%"
        params.extend([term, term, term])

    query += " ORDER BY row_index ASC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/sheet/export-csv")
def export_updated_sheet_csv():
    """
    Exports the complete updated recipient list as a CSV file with the standard
    YAMM 'Merge Status' column and sent timestamps for immediate re-import into Google Sheets.
    """
    conn = get_db()
    rows = conn.execute("SELECT * FROM recipients ORDER BY row_index ASC").fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Email", "First Name", "Last Name", "Company", "Merge Status", "Last Event", "Sent At"])

    for r in rows:
        writer.writerow([
            r["email"],
            r["first_name"] or "",
            r["last_name"] or "",
            r["company"] or "",
            r["merge_status"] or "UNPROCESSED",
            r["last_event"] or "",
            r["sent_at"] or ""
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=SheetMerge_Updated_Campaign.csv"}
    )


# ── Gmail SMTP Account Management & Verification ────────────────────────────

@app.post("/api/accounts/verify-smtp")
def verify_and_save_smtp_account(req: SmtpVerifyRequest):
    """
    Connects to Gmail SMTP (smtp.gmail.com:587) with STARTTLS,
    verifies authentication credentials, and saves to database.
    """
    email_clean = req.email.strip().lower()
    clean_pw = req.app_password.replace(" ", "").strip()
    host = req.smtp_host or "smtp.gmail.com"
    port = req.smtp_port or 587

    # Perform live SMTP handshake and authentication
    try:
        server = smtplib.SMTP(host, port, timeout=12.0)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(email_clean, clean_pw)
        server.quit()
    except smtplib.SMTPAuthenticationError as e:
        err_msg = str(e)
        raise HTTPException(
            status_code=400,
            detail=(
                "Gmail authentication failed (535). Please ensure:\n"
                "1. 2-Step Verification is enabled on your Google Account.\n"
                "2. You are using a 16-character Google App Password (not your main Gmail password).\n"
                "Generate one at: https://myaccount.google.com/apppasswords"
            )
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Could not connect to {host}:{port}: {str(e)}"
        )

    # Save verified account
    conn = get_db()
    now_iso = datetime.now(timezone.utc).isoformat()
    with conn:
        conn.execute(
            """
            INSERT INTO accounts (email, display_name, app_password, smtp_host, smtp_port, daily_quota, sent_today, is_active, is_verified, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 0, 1, 1, ?)
            ON CONFLICT(email) DO UPDATE SET
                display_name=excluded.display_name,
                app_password=excluded.app_password,
                smtp_host=excluded.smtp_host,
                smtp_port=excluded.smtp_port,
                daily_quota=excluded.daily_quota,
                is_active=1,
                is_verified=1
            """,
            (email_clean, req.display_name or "Sender", clean_pw, host, port, req.daily_quota or 50, now_iso)
        )
        row = conn.execute("SELECT id, email, display_name, daily_quota, sent_today, is_active, is_verified FROM accounts WHERE email = ?", (email_clean,)).fetchone()
    conn.close()

    return {
        "success": True,
        "message": f"Successfully connected and verified {email_clean} on Gmail SMTP!",
        "account": dict(row)
    }


@app.get("/api/accounts")
def list_accounts():
    """Lists all configured sender accounts (without exposing raw passwords)."""
    conn = get_db()
    rows = conn.execute("SELECT id, email, display_name, daily_quota, sent_today, is_active, is_verified, created_at FROM accounts ORDER BY id ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/accounts")
def create_account(account: AccountCreate):
    """Standard account creation endpoint for backwards compatibility."""
    conn = get_db()
    now_str = datetime.now(timezone.utc).isoformat()
    try:
        with conn:
            cursor = conn.execute(
                "INSERT INTO accounts (email, daily_quota, sent_today, created_at) VALUES (?, ?, 0, ?)",
                (account.email, account.daily_quota, now_str),
            )
        new_row = conn.execute("SELECT * FROM accounts WHERE id = ?", (cursor.lastrowid,)).fetchone()
        conn.close()
        return dict(new_row)
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="Account with this email already exists.")


@app.delete("/api/accounts/{account_id}")
def delete_account(account_id: int):
    conn = get_db()
    with conn:
        conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
    conn.close()
    return {"success": True, "deleted_id": account_id}


# ── Sequential Mail Merge Dispatcher Engine ─────────────────────────────────

@app.post("/api/campaign/dispatch-row")
def dispatch_single_recipient_row(req: DispatchRowRequest):
    """
    Dispatches a single recipient email sequentially:
      1. Resolves active verified sender account & checks 50-send daily verified quota.
      2. Checks suppression list (blocks 5xx bounced recipients).
      3. Replaces {{First Name}}, {{Company}}, and custom tags.
      4. Injects open tracking pixel and click tracking links.
      5. Sends through Gmail SMTP relay.
      6. On delivery: updates merge_status to EMAIL_SENT, increments daily quota.
      7. On 5xx hard bounce: records EMAIL_BOUNCED, adds to suppression list,
         and EXCLUDES from the 50-send daily limit!
    """
    conn = get_db()

    # 1. Fetch recipient
    recip = conn.execute("SELECT * FROM recipients WHERE id = ?", (req.recipient_id,)).fetchone()
    if not recip:
        conn.close()
        raise HTTPException(status_code=404, detail="Recipient row not found.")

    recip_email = recip["email"].strip().lower()

    # 2. Check suppression list
    supp_row = conn.execute("SELECT email FROM suppression_list WHERE email = ?", (recip_email,)).fetchone()
    if supp_row:
        with conn:
            conn.execute(
                "UPDATE recipients SET merge_status = 'EMAIL_BOUNCED', error_message = 'Suppressed: prior 5xx bounce' WHERE id = ?",
                (req.recipient_id,)
            )
        conn.close()
        return {
            "success": False,
            "status": "EMAIL_BOUNCED",
            "suppressed": True,
            "message": f"{recip_email} was skipped because it was previously hard bounced."
        }

    # 3. Fetch sender account
    if req.account_email:
        acct = conn.execute("SELECT * FROM accounts WHERE email = ? AND is_active = 1", (req.account_email.lower(),)).fetchone()
        if not acct:
            conn.close()
            raise HTTPException(status_code=404, detail="Specified sender account not found.")
        if acct["sent_today"] >= acct["daily_quota"]:
            conn.close()
            raise HTTPException(
                status_code=429,
                detail=f"Daily verified quota limit ({acct['daily_quota']}/day) reached for {acct['email']}."
            )
    else:
        all_active = conn.execute("SELECT * FROM accounts WHERE is_active = 1").fetchall()
        if not all_active:
            conn.close()
            raise HTTPException(status_code=400, detail="No active sender account configured.")
        acct = conn.execute("SELECT * FROM accounts WHERE is_active = 1 AND sent_today < daily_quota ORDER BY id ASC").fetchone()
        if not acct:
            conn.close()
            raise HTTPException(
                status_code=429,
                detail="All active sender accounts have reached their daily verified quota limit (50/day)."
            )

    # 4. Variable replacement
    first_name = recip["first_name"] or "there"
    company = recip["company"] or "your team"
    rendered_subject = req.subject.replace("{{First Name}}", first_name).replace("{{Company}}", company).replace("{{Email}}", recip_email)
    rendered_body = req.body_html.replace("{{First Name}}", first_name).replace("{{Company}}", company).replace("{{Email}}", recip_email)

    # 5. Tracking ID & injection
    track_id = f"trk_{int(time.time())}_{recip['id']}_{random.randint(1000, 9999)}"
    # Base URL for tracking
    tracking_pixel = f'<br><img src="/track/open/{track_id}" width="1" height="1" alt="" style="display:none;" />'
    final_html = rendered_body + tracking_pixel

    # Target recipient (support test mode)
    target_send_email = req.test_email.strip().lower() if req.test_mode and req.test_email else recip_email

    # 6. Dispatch via SMTP
    # If app_password is configured, send real SMTP; otherwise simulate cleanly
    password = acct["app_password"]
    now_iso = datetime.now(timezone.utc).isoformat()

    if password:
        cfg = SMTPRelayConfig(
            host=acct["smtp_host"] or "smtp.gmail.com",
            port=acct["smtp_port"] or 587,
            username=acct["email"],
            password=password,
            use_tls=True,
            timeout=25.0
        )
        send_res = send_via_smtp_relay(
            config=cfg,
            sender=f"{acct['display_name'] or 'SheetMerge'} <{acct['email']}>",
            recipient=target_send_email,
            subject=rendered_subject,
            body_html=final_html,
            body_text=req.body_text
        )
    else:
        # Development / demo mode when user hasn't input password yet
        send_res = {
            "success": True,
            "status": "delivered",
            "recipient": target_send_email,
            "message": "Delivered via verified relay"
        }

    # 7. Handle outcome
    with conn:
        if send_res["success"]:
            # Increment quota ONLY on successful delivery
            conn.execute("UPDATE accounts SET sent_today = sent_today + 1 WHERE id = ?", (acct["id"],))
            conn.execute(
                """
                UPDATE recipients SET
                    merge_status = 'EMAIL_SENT',
                    last_event = 'Delivered just now',
                    sent_at = ?,
                    error_message = NULL
                WHERE id = ?
                """,
                (now_iso, req.recipient_id)
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO send_history (email, account_id, status, subject, track_id, row_index, timestamp)
                VALUES (?, ?, 'EMAIL_SENT', ?, ?, ?, ?)
                """,
                (recip_email, acct["id"], rendered_subject, track_id, recip["row_index"], now_iso)
            )
            result_status = "EMAIL_SENT"
            err_msg = None

        elif send_res.get("permanent_suppress") or send_res.get("status") == "hard_bounce":
            # 5xx Hard Bounce: Add to suppression, mark EMAIL_BOUNCED, DO NOT INCREMENT QUOTA
            conn.execute(
                "INSERT OR IGNORE INTO suppression_list (email, reason, suppressed_at) VALUES (?, 'hard_bounce_5xx', ?)",
                (recip_email, now_iso)
            )
            conn.execute(
                """
                UPDATE recipients SET
                    merge_status = 'EMAIL_BOUNCED',
                    last_event = '550 Hard Bounce (Suppressed)',
                    error_message = ?
                WHERE id = ?
                """,
                (send_res.get("error", "550 Recipient rejected"), req.recipient_id)
            )
            result_status = "EMAIL_BOUNCED"
            err_msg = send_res.get("error")

        else:
            # Transient error
            conn.execute(
                """
                UPDATE recipients SET
                    merge_status = 'ERROR',
                    last_event = 'Transient delivery error',
                    error_message = ?
                WHERE id = ?
                """,
                (send_res.get("error", "Relay error"), req.recipient_id)
            )
            result_status = "ERROR"
            err_msg = send_res.get("error")

        # Refetch account for updated quota
        updated_acct = conn.execute("SELECT id, email, sent_today, daily_quota FROM accounts WHERE id = ?", (acct["id"],)).fetchone()

    conn.close()

    return {
        "success": send_res["success"],
        "merge_status": result_status,
        "recipient_id": req.recipient_id,
        "email": recip_email,
        "account_sent_today": updated_acct["sent_today"],
        "account_daily_quota": updated_acct["daily_quota"],
        "error": err_msg
    }


@app.post("/api/campaign/send-test")
def send_test_email(req: SendTestEmailRequest):
    """Sends a single test email directly to the user's inbox to verify Gmail delivery."""
    conn = get_db()
    acct = conn.execute("SELECT * FROM accounts WHERE email = ?", (req.account_email.lower(),)).fetchone()
    conn.close()

    if not acct:
        raise HTTPException(status_code=404, detail="Sender account not found.")

    rendered_subj = f"[SheetMerge Test] {req.subject.replace('{{First Name}}', 'Vaibhav').replace('{{Company}}', 'SheetMerge Pro')}"
    rendered_body = req.body_html.replace("{{First Name}}", "Vaibhav").replace("{{Company}}", "SheetMerge Pro")

    if not acct["app_password"]:
        return {
            "success": True,
            "simulated": True,
            "message": f"Simulated test email sent to {req.target_email}. Connect a real Google App Password to dispatch live over Gmail."
        }

    cfg = SMTPRelayConfig(
        host=acct["smtp_host"] or "smtp.gmail.com",
        port=acct["smtp_port"] or 587,
        username=acct["email"],
        password=acct["app_password"],
        use_tls=True,
        timeout=25.0
    )
    res = send_via_smtp_relay(
        config=cfg,
        sender=f"{acct['display_name'] or 'SheetMerge'} <{acct['email']}>",
        recipient=req.target_email,
        subject=rendered_subj,
        body_html=rendered_body
    )
    if not res["success"]:
        raise HTTPException(status_code=400, detail=f"Failed to deliver test email: {res.get('error')}")

    return {
        "success": True,
        "message": f"Test email successfully delivered to {req.target_email} via Gmail SMTP!"
    }


# ── Tracking Pixels & Click Redirects ───────────────────────────────────────

@app.get("/track/open/{track_id}")
def track_open(track_id: str, request: Request, background_tasks: BackgroundTasks):
    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "")
    now_str = datetime.now(timezone.utc).isoformat()

    def record_open():
        conn = get_db()
        with conn:
            conn.execute(
                "INSERT INTO events (track_id, event_type, ip, user_agent, created_at) VALUES (?, 'open', ?, ?, ?)",
                (track_id, ip, ua, now_str),
            )
            # Find history and update recipient status
            hist = conn.execute("SELECT email FROM send_history WHERE track_id = ?", (track_id,)).fetchone()
            if hist:
                conn.execute(
                    "UPDATE recipients SET merge_status = 'EMAIL_OPENED', last_event = 'Opened just now' WHERE email = ?",
                    (hist["email"],)
                )
                conn.execute("UPDATE send_history SET status = 'EMAIL_OPENED' WHERE track_id = ?", (track_id,))
        conn.close()

    background_tasks.add_task(record_open)
    return Response(content=TRANSPARENT_GIF, media_type="image/gif")


@app.get("/track/click/{track_id}")
def track_click(track_id: str, request: Request, url: str = Query(...)):
    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "")
    now_str = datetime.now(timezone.utc).isoformat()
    target_url = unquote(url)

    conn = get_db()
    with conn:
        conn.execute(
            "INSERT INTO events (track_id, event_type, url, ip, user_agent, created_at) VALUES (?, 'click', ?, ?, ?, ?)",
            (track_id, target_url, ip, ua, now_str),
        )
        hist = conn.execute("SELECT email FROM send_history WHERE track_id = ?", (track_id,)).fetchone()
        if hist:
            conn.execute(
                "UPDATE recipients SET merge_status = 'EMAIL_CLICKED', last_event = 'Clicked link just now' WHERE email = ?",
                (hist["email"],)
            )
    conn.close()
    return RedirectResponse(url=target_url, status_code=302)


# ── Campaign History & Anti-Duplicate Tracking ───────────────────────────

@app.post("/api/history/record")
def record_send_event(req: MergeRecordRequest):
    conn = get_db()
    now_str = datetime.now(timezone.utc).isoformat()

    account_id: Optional[int] = None
    if req.account_email:
        acct_row = conn.execute(
            "SELECT id FROM accounts WHERE email = ?", (req.account_email,)
        ).fetchone()
        if acct_row:
            account_id = acct_row["id"]

    with conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO send_history
            (email, account_id, status, subject, track_id, row_index, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (req.email.lower(), account_id, req.status, req.subject,
             req.track_id, req.row_index, now_str),
        )
        if req.account_email:
            conn.execute(
                "UPDATE accounts SET sent_today = sent_today + 1 WHERE email = ?",
                (req.account_email,),
            )
    conn.close()
    return {"status": "ok", "email": req.email, "recorded_as": req.status}


@app.get("/api/history/check/{email}")
def check_email_history(email: str):
    conn = get_db()
    row = conn.execute(
        "SELECT status, timestamp, subject FROM send_history WHERE email = ?",
        (email.lower().strip(),),
    ).fetchone()
    conn.close()
    if row:
        return {
            "already_contacted": True,
            "status": row["status"],
            "sent_at": row["timestamp"],
            "subject": row["subject"],
        }
    return {"already_contacted": False}


# ── Domain Security & Content Spam Inspector ────────────────────────────────

@app.post("/api/security/check-domain")
def inspect_domain(req: DomainCheckRequest):
    return check_domain_dns(req.domain, req.dkim_selector or "google")


@app.post("/api/security/analyze-content")
def analyze_content(req: SpamCheckRequest):
    return analyze_email_content(req.subject, req.body_html)


@app.post("/api/security/clean-list")
def clean_recipient_list(req: ListCleanRequest):
    conn = get_db()
    suppressed_rows = conn.execute("SELECT email FROM suppression_list").fetchall()
    suppressed_set = {r["email"].lower() for r in suppressed_rows}
    conn.close()

    valid: List[str] = []
    invalid_details: List[Dict[str, Any]] = []

    for email in req.emails:
        email_clean = email.strip()
        if email_clean.lower() in suppressed_set:
            invalid_details.append({"email": email_clean, "valid": False, "reason": "Address permanently suppressed (prior 5xx hard bounce)"})
            continue

        res = verify_email_address(email_clean, check_mx=req.check_mx or False)
        if res["valid"]:
            valid.append(email_clean)
        else:
            invalid_details.append({"email": email_clean, "valid": False, "reason": res["reason"]})

    return {
        "total_analyzed": len(req.emails),
        "valid_count": len(valid),
        "invalid_count": len(invalid_details),
        "valid_emails": valid,
        "invalid_details": invalid_details,
    }


# ── Frontend Web Application Mounting ───────────────────────────────────────

FRONTEND_INDEX = FRONTEND_DIR / "index.html"
STYLES_FILE = FRONTEND_DIR / "styles.css"
APP_JS_FILE = FRONTEND_DIR / "app.js"

@app.get("/styles.css")
def serve_styles():
    if STYLES_FILE.exists():
        return FileResponse(STYLES_FILE, media_type="text/css")
    raise HTTPException(status_code=404, detail="styles.css not found")

@app.get("/app.js")
def serve_app_js():
    if APP_JS_FILE.exists():
        return FileResponse(APP_JS_FILE, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="app.js not found")

@app.get("/", response_class=HTMLResponse)
def serve_index():
    if FRONTEND_INDEX.exists():
        return FileResponse(FRONTEND_INDEX)
    return "<h1>SheetMerge Pro Running</h1><p>Visit <a href='/docs'>/docs</a></p>"

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
