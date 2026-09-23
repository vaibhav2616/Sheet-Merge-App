"""
backend/main.py — SheetMerge Enterprise Standalone API & Application Server
==========================================================================
Integrates:
  • High-end Bento-Box Dashboard Frontend
  • Contacts & Leads CRM Engine with Timeline, Follow-ups, and Notes
  • Single YAMM-compatible 'Merge Status' Column Architecture
  • SPF / DKIM / DMARC Domain Authentication Guard
  • 45+ Rule Content Anti-Spam Analyzer
  • 5xx Permanent Hard Bounce Interception & Suppression
  • Humanized Multi-Account SMTP Relay with Randomized Jitter Pacing
  • Open & Click Event Tracking
"""
from __future__ import annotations

import base64
import os
import sqlite3
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import unquote

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr

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

def get_db() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db()
    with conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS leads (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                name           TEXT NOT NULL,
                company        TEXT,
                email          TEXT UNIQUE NOT NULL,
                phone          TEXT,
                status         TEXT DEFAULT 'New', -- 'New', 'Contacted', 'Qualified', 'Proposal Sent', 'Won', 'Lost', 'Sent', 'Opened', 'Positive Reply', 'Bounced'
                value          REAL DEFAULT 0,
                source         TEXT DEFAULT 'Website',
                last_note      TEXT,
                follow_up_date TEXT,
                follow_up_time TEXT,
                is_completed   INTEGER DEFAULT 0,
                created_at     TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS lead_notes (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id        INTEGER NOT NULL,
                content        TEXT NOT NULL,
                follow_up_at   TEXT,
                created_at     TEXT NOT NULL,
                FOREIGN KEY(lead_id) REFERENCES leads(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS accounts (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                email          TEXT UNIQUE NOT NULL,
                daily_quota    INTEGER DEFAULT 50,
                sent_today     INTEGER DEFAULT 0,
                last_reset     TEXT,
                is_active      INTEGER DEFAULT 1,
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

        cursor = conn.execute("SELECT COUNT(*) as count FROM leads")
        if cursor.fetchone()["count"] == 0:
            now_iso = datetime.now(timezone.utc).isoformat()
            sample_leads = [
                ("Emma Novak", "Vista Travel", "emma.novak@vistatravel.com", "+1-555-0101", "Qualified", 83000, "Website form", "Budget confirmed, wants a demo", "2026-10-25", "10:00", 0),
                ("Chloe Martin", "Nova Retail", "chloe@novaretail.io", "+1-555-0102", "Contacted", 30500, "Cold email", "Sent product overview email", "2026-10-25", "11:30", 0),
                ("Hana Kim", "Seoul Supply", "hana.kim@seoulsupply.kr", "+82-2-555-0199", "New", 19500, "Website form", "Came through website form", "2026-10-25", "12:15", 0),
                ("Elena Ruiz", "Northwind", "elena@northwind.es", "+34-91-555-0188", "New", 45000, "LinkedIn", "Inbound lead from product post", "2026-10-25", "13:00", 0),
                ("Daniel Okafor", "Bluefin Tech", "daniel@bluefin.ng", "+234-1-555-0177", "Proposal Sent", 125000, "Referral", "Proposal sent, review next week", "2026-10-26", "15:15", 0),
                ("Aisha Bello", "Lagos Digital", "aisha@lagosdigital.com", "+234-1-555-0144", "Overdue", 49000, "Website form", "Needs a reply, was due 3 days ago", "2026-10-21", "09:30", 0),
                ("Marcus Thorne", "Nexus Financial", "marcus.t@nexusfin.com", "+1-555-0182", "Won", 260000, "Partner", "Contract signed, pilot active", None, None, 1),
                ("Priya Sharma", "Acme Health", "priya.sharma@acmehealth.in", "+91-22-555-0144", "Qualified", 159200, "Website form", "Finance approved 50 seats", "2026-10-25", "14:00", 0)
            ]
            for l in sample_leads:
                conn.execute(
                    """
                    INSERT INTO leads (name, company, email, phone, status, value, source, last_note, follow_up_date, follow_up_time, is_completed, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (*l, now_iso)
                )
    conn.close()


# ── Models ──────────────────────────────────────────────────────────────────

class LeadCreate(BaseModel):
    name: str
    company: Optional[str] = ""
    email: EmailStr
    phone: Optional[str] = ""
    status: Optional[str] = "New"
    value: Optional[float] = 0.0
    source: Optional[str] = "Direct"
    last_note: Optional[str] = ""
    follow_up_date: Optional[str] = None
    follow_up_time: Optional[str] = None


class LeadUpdate(BaseModel):
    name: Optional[str] = None
    company: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    status: Optional[str] = None
    value: Optional[float] = None
    source: Optional[str] = None
    last_note: Optional[str] = None
    follow_up_date: Optional[str] = None
    follow_up_time: Optional[str] = None
    is_completed: Optional[int] = None


class NoteCreate(BaseModel):
    content: str
    follow_up_at: Optional[str] = None


class AccountCreate(BaseModel):
    email: EmailStr
    daily_quota: Optional[int] = 50


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


class SmtpSendRequest(BaseModel):
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str
    smtp_password: str
    sender_email: EmailStr
    recipients: List[EmailStr]
    subject: str
    body_html: str
    body_text: Optional[str] = None
    min_delay_seconds: float = 2.0
    max_delay_seconds: float = 5.0
    socket_timeout: float = 30.0


# ── Lifespan & FastAPI App ──────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="SheetMerge Enterprise Pro",
    description="Anti-Spam Humanizer, Deliverability Suite, and Fluid Bento CRM",
    version="2.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
)


# ── Leads & Contacts Endpoints ──────────────────────────────────────────────

@app.get("/api/leads")
def list_leads(status: Optional[str] = None, q: Optional[str] = None):
    conn = get_db()
    query = "SELECT * FROM leads WHERE 1=1"
    params: List[Any] = []

    if status and status.lower() != "all":
        query += " AND LOWER(status) = ?"
        params.append(status.lower())

    if q:
        query += " AND (LOWER(name) LIKE ? OR LOWER(company) LIKE ? OR LOWER(email) LIKE ?)"
        term = f"%{q.lower()}%"
        params.extend([term, term, term])

    query += " ORDER BY id DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/leads/stats")
def get_pipeline_stats():
    conn = get_db()
    leads = conn.execute("SELECT status, value, is_completed FROM leads").fetchall()
    conn.close()

    total_leads = len(leads)
    open_value = sum(l["value"] or 0 for l in leads if l["status"] not in ("Won", "Lost"))
    won_value = sum(l["value"] or 0 for l in leads if l["status"] == "Won")

    by_status: Dict[str, int] = {}
    for l in leads:
        s = l["status"] or "New"
        by_status[s] = by_status.get(s, 0) + 1

    won_count = by_status.get("Won", 0)
    lost_count = by_status.get("Lost", 0)
    closed = won_count + lost_count
    win_rate = round((won_count / closed * 100), 1) if closed > 0 else 65.0

    return {
        "total_leads": total_leads,
        "open_value": open_value,
        "won_value": won_value,
        "conversion_rate": 32.0,
        "avg_response_hours": 4.4,
        "active_leads": total_leads - won_count - lost_count,
        "win_rate": win_rate,
        "by_status": by_status,
    }


@app.post("/api/leads")
def create_lead(lead: LeadCreate):
    conn = get_db()
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        cursor = conn.execute(
            """
            INSERT INTO leads (name, company, email, phone, status, value, source, last_note, follow_up_date, follow_up_time, is_completed, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (lead.name, lead.company, lead.email, lead.phone, lead.status or "New", lead.value or 0, lead.source or "Direct", lead.last_note, lead.follow_up_date, lead.follow_up_time, now_iso)
        )
        conn.commit()
        lead_id = cursor.lastrowid
        if lead.last_note:
            conn.execute(
                "INSERT INTO lead_notes (lead_id, content, created_at) VALUES (?, ?, ?)",
                (lead_id, lead.last_note, now_iso)
            )
            conn.commit()
        new_row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        conn.close()
        return dict(new_row)
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="A lead with this email address already exists.")


@app.get("/api/leads/{lead_id}")
def get_lead_details(lead_id: int):
    conn = get_db()
    lead = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if not lead:
        conn.close()
        raise HTTPException(status_code=404, detail="Lead not found")
    notes = conn.execute("SELECT * FROM lead_notes WHERE lead_id = ? ORDER BY id DESC", (lead_id,)).fetchall()
    events = conn.execute(
        """
        SELECT e.event_type, e.created_at, e.url
        FROM events e
        JOIN send_history h ON e.track_id = h.track_id
        WHERE h.email = ?
        ORDER BY e.id DESC
        """,
        (lead["email"],)
    ).fetchall()
    conn.close()
    return {
        "lead": dict(lead),
        "notes": [dict(n) for n in notes],
        "events": [dict(ev) for ev in events]
    }


@app.patch("/api/leads/{lead_id}")
def update_lead(lead_id: int, payload: LeadUpdate):
    conn = get_db()
    lead = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if not lead:
        conn.close()
        raise HTTPException(status_code=404, detail="Lead not found")

    fields: List[str] = []
    values: List[Any] = []
    for k, v in payload.model_dump(exclude_unset=True).items():
        fields.append(f"{k} = ?")
        values.append(v)

    if fields:
        values.append(lead_id)
        conn.execute(f"UPDATE leads SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()

    updated = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    conn.close()
    return dict(updated)


@app.post("/api/leads/{lead_id}/notes")
def add_lead_note(lead_id: int, note: NoteCreate):
    conn = get_db()
    lead = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if not lead:
        conn.close()
        raise HTTPException(status_code=404, detail="Lead not found")

    now_iso = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO lead_notes (lead_id, content, follow_up_at, created_at) VALUES (?, ?, ?, ?)",
        (lead_id, note.content, note.follow_up_at, now_iso)
    )
    conn.execute(
        "UPDATE leads SET last_note = ? WHERE id = ?",
        (note.content, lead_id)
    )
    conn.commit()
    notes = conn.execute("SELECT * FROM lead_notes WHERE lead_id = ? ORDER BY id DESC", (lead_id,)).fetchall()
    conn.close()
    return [dict(n) for n in notes]


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


# ── Multi-Account & SMTP Relay ──────────────────────────────────────────────

@app.get("/api/accounts")
def list_accounts():
    conn = get_db()
    rows = conn.execute("SELECT * FROM accounts ORDER BY id ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/accounts")
def create_account(account: AccountCreate):
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


@app.post("/api/relay/send")
def relay_send_email(req: SmtpSendRequest):
    config = SMTPRelayConfig(
        host=req.smtp_host,
        port=req.smtp_port,
        username=req.smtp_user,
        password=req.smtp_password,
        sender_email=req.sender_email,
        socket_timeout=req.socket_timeout,
        min_delay_seconds=req.min_delay_seconds,
        max_delay_seconds=req.max_delay_seconds,
    )
    result = send_via_smtp_relay(
        config=config,
        recipients=req.recipients,
        subject=req.subject,
        html_content=req.body_html,
        plain_content=req.body_text,
    )

    if result.bounced:
        conn = get_db()
        now_str = datetime.now(timezone.utc).isoformat()
        with conn:
            for b_email in result.bounced:
                conn.execute(
                    "INSERT OR IGNORE INTO suppression_list (email, reason, suppressed_at) VALUES (?, 'hard_bounce_5xx', ?)",
                    (b_email.lower(), now_str),
                )
        conn.close()

    return {
        "success": result.success,
        "sent_count": len(result.delivered),
        "bounced_count": len(result.bounced),
        "failed_count": len(result.failed),
        "delivered": result.delivered,
        "bounced": result.bounced,
        "failed": result.failed,
        "errors": result.errors,
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
            conn.execute("UPDATE send_history SET status = 'opened' WHERE track_id = ?", (track_id,))
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


# ── Frontend Web Application Mounting ───────────────────────────────────────


FRONTEND_INDEX = FRONTEND_DIR / "index.html"

@app.get("/", response_class=HTMLResponse)
def serve_index():
    if FRONTEND_INDEX.exists():
        return FileResponse(FRONTEND_INDEX)
    return "<h1>SheetMerge Pro Running</h1><p>Visit <a href='/docs'>/docs</a></p>"

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
