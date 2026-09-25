# ⚡ SheetMerge Pro
> **High-Deliverability Multi-Account Mail Merge & Google Sheets Suite.**  
> Real Google Sheets synchronization, Multi-Account Gmail sender pool, single-column YAMM standard, and sequential humanized dispatching.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## 🎨 Clean Architecture & Modern Workspace

SheetMerge Pro features a clean separation between **App User Authentication** and **Multi-Account Sender Pool**:

* **App User Workspace Access:**
  * **1-Click Google Sign-In (OAuth):** Instant access to your dashboard using Google Identity Services.
  * **Email + 6-Digit OTP Confirmation:** Passwordless, secure email sign-up/sign-in with 6-digit confirmation codes.
* **Multi-Account Google Sender Pool:**
  * Link multiple Google / Gmail accounts to pool daily delivery capacity (50 sends/day per account).
  * Load balances and auto-rotates across accounts with live quota tracking (`0 / 100 Sent Today`).
* **Live Google Sheets Ingestion & Status Sync:**
  * Ingest any Google Sheet via URL. Intelligent column heuristic detection maps `Email`, `First Name`, `Last Name`, `Company`, and single-status `Merge Status`.
  * Exports updated CSVs with real-time `Merge Status` (`EMAIL_SENT`, `EMAIL_OPENED`, `EMAIL_CLICKED`, `EMAIL_BOUNCED`) to reflect changes directly in Google Sheets.
* **Sequential Humanized Dispatcher:**
  * Randomized 2.0s–5.0s jitter pacing between dispatches to mimic natural human sending and bypass automated spam filters.
  * Automatic 5xx hard bounce suppression: permanently suppresses invalid addresses without consuming your daily quota.

---

## 📂 Project Structure

```
SheetMerge-App/
├── backend/
│   ├── data/                   # SQLite database (sheetmerge_pro.db)
│   ├── domain_security.py      # SPF / DKIM / DMARC verification engine
│   ├── main.py                 # FastAPI application, auth endpoints & dispatch engine
│   ├── requirements.txt        # Backend dependencies
│   ├── smtp_relay.py           # Humanized SMTP relay with 5xx bounce guard
│   └── spam_analyzer.py        # 45+ rule spam trigger engine
├── frontend/
│   ├── app.js                  # Client application engine & multi-account state
│   ├── index.html              # Modern dashboard, sender pool, sheet hub & walkthrough
│   └── styles.css              # Obsidian Dark & Cyber Cyan responsive design system
├── Dockerfile                  # Container deployment image
├── docker-compose.yml          # Container orchestration
├── run.bat                     # Windows one-click launcher
└── README.md
```

---

## 🚀 Quickstart Guide

### Option 1: Local Launch
```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```
Open `http://localhost:8000` in your browser.

### Option 2: Docker Compose (Production)
```bash
docker-compose up -d --build
```
Open `http://localhost:8000`.

---

## 📖 End-to-End Walkthrough

1. **Sign In:** Use 1-click Google OAuth or enter your email to receive a 6-digit verification code.
2. **Link Sender Accounts:** In Section 1, link 1 or more Google accounts. Each account adds 50 verified sends/day to your delivery pool.
3. **Connect Google Sheet:** In Section 2, paste your Google Sheet URL (ensure General Access is set to 'Anyone with the link can view').
4. **Draft & Preview:** Open the composer drawer to compose your email with `{{First Name}}` and `{{Company}}` tags. Inspect the real-time personalization preview for Row 1.
5. **Dispatch Campaign:** Click 'Dispatch Campaign' to send sequentially with humanized jitter.
6. **Sync Status:** Click 'Export Updated CSV' to re-import into Google Sheets with updated single-column `Merge Status`.
