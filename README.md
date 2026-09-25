# ⚡ SheetMerge Pro
> **High-Performance Mail Merge Application & Deliverability Shield.**  
> Real Google Sheets integration, Gmail SMTP delivery, single-column YAMM standard, and sequential humanized dispatching.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![Tests](https://img.shields.io/badge/Tests-56%2F56%20Passing-brightgreen?logo=pytest)](https://pytest.org)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## 🎨 Design Philosophy & Bento-Box UI

SheetMerge Pro brings modern software craftsmanship to outbound email campaigns, newsletters, and personalized outreach:

* **Midnight Obsidian & Cyber Cyan:** Deep obsidian backdrop (`#080c14`), electric indigo cards (`#6366f1`), and cyber cyan accents (`#06b6d4`).
* **Fluid Responsive Architecture:**
  * **Desktop:** Vertical navigation rail (`width: 76px`) with quick view switchers and account profile.
  * **Mobile / Phone:** Navigation smoothly converts into a **floating bottom dock**, stacking all bento cards into an intuitive single scrolling column.
* **Interactive Stage Pillar Chart:** Live visual distribution of merge recipients across stages (`Queue`, `Sent`, `Opened`, `Clicked`, `Bounced`).
* **Slide-Out Compose & Template Drawer:** Insert `{{First Name}}`, `{{Company}}`, and `{{Email}}` tags with live real-time preview and 1-click test email dispatch.
* **Spotlight Command Palette (`⌘K` / `Ctrl+K`):** Instant keyboard-first search across all recipients, connected Gmail accounts, and campaign actions.

---

## 🌐 Real-World Features & Built-In Tech

### 1. Live Google Sheets Ingestion & Analysis
* **Connect Public Google Sheet:** Paste any Google Sheet link (`https://docs.google.com/spreadsheets/d/.../edit`). SheetMerge Pro automatically queries the CSV export endpoint, parses rows, and hydrates the dashboard in seconds without requiring complex Google Cloud API keys.
* **Built-in Intelligent Column Detection:** Heuristically matches columns for `Email`, `First Name`, `Last Name`, `Company`, and `Merge Status`.
* **Private Sheet & CSV Fallback:** If a sheet is private, SheetMerge provides 1-click CSV/Excel upload and sample template loading.
* **YAMM Compatible CSV Export:** Download your updated spreadsheet anytime with the single standardized `Merge Status` column and sent timestamps.

### 2. Real Gmail SMTP Delivery & App Password Authentication
* **Direct Gmail Delivery:** Sends real emails using Google's secure SMTP relay (`smtp.gmail.com:587`) with STARTTLS encryption.
* **App Password Verification:** Instant connection testing verifies your 16-character Google App Password and confirms account status.
* **Live Test Email:** Send a 1-click test email to your personal inbox to verify formatting and inbox placement before launching.

### 3. Sequential Dispatch with Humanized Pacing
* **Randomized Jitter Delay (2.0s – 5.0s):** Mimics human sending intervals (`random.uniform(2.0, 5.0)`) between dispatches to avoid firewall connection spike detection by Google and Microsoft spam filters.
* **Live HUD Progress Modal:** Shows real-time percentage, current recipient, jitter countdown, and live counters for sent, bounced, and remaining sends.

### 4. 50-Send Daily Verified Quota Shield
* **Deliveries Only:** Hard bounces are automatically excluded from your daily quota calculation.
* **Auto-Rotation:** Automatically switches to the next connected sender account when an account reaches 50 valid sends.

### 5. Automatic 5xx Hard Bounce Suppression
* **Instant Interception:** Detects permanent SMTP `550`, `551`, `553`, and `554` responses and immediately records the recipient into a local suppression list.
* **Domain Reputation Guard:** Suppressed recipients are skipped in future campaigns, protecting your sender score.

### 6. Pre-Flight DNS Shield & 45-Rule Anti-Spam Analyzer
* **Pre-Flight DNS Scan:** Real-time lookup for SPF, DKIM (2048-bit), DMARC policy alignment, and MX resolution.
* **Heuristic Spam Engine:** Analyzes message subject and body for caps ratios, trigger keywords, and link density.

---

## 📂 Project Architecture

```
SheetMerge-App/
├── backend/
│   ├── data/                   # SQLite database directory (auto-created)
│   ├── tests/                  # Pytest test suite (56/56 passing)
│   │   ├── test_domain_security.py
│   │   ├── test_main_api.py
│   │   ├── test_smtp_relay.py
│   │   └── test_spam_analyzer.py
│   ├── domain_security.py      # SPF / DKIM / DMARC verification engine
│   ├── main.py                 # FastAPI application & REST endpoints
│   ├── pytest.ini              # Pytest configuration
│   ├── requirements.txt        # Backend dependencies
│   ├── smtp_relay.py           # Humanized SMTP relay with 5xx bounce guard
│   └── spam_analyzer.py        # 45+ rule spam trigger engine
├── frontend/
│   ├── app.js                  # Client engine, bento renderers & live dispatch HUD
│   ├── index.html              # Bento grid structure, Google Sheet hub & modals
│   └── styles.css              # Custom fluid Bento CSS design system
├── Dockerfile                  # Production container image
├── docker-compose.yml          # One-command orchestration
├── run.bat                     # Windows one-click launcher
└── README.md
```

---

## 🚀 Quickstart Guide

### Option 1: One-Click Launch (Windows)
Double-click `run.bat` in the repository root. It will:
1. Install dependencies via `pip`.
2. Launch the FastAPI server at `http://localhost:8000`.
3. Open the Bento-Box UI in your default browser.

### Option 2: Docker Compose (Production)
```bash
git clone https://github.com/vaibhav2616/Sheet-Merge-App.git
cd Sheet-Merge-App
docker-compose up -d --build
```
Access the application at `http://localhost:8000`.

### Option 3: Python Virtual Environment
```bash
git clone https://github.com/vaibhav2616/Sheet-Merge-App.git
cd Sheet-Merge-App/backend
pip install -r requirements.txt
python -m pytest tests/ -v
uvicorn main:app --reload --port 8000
```

---

## 🧪 Automated Test Suite (56/56 Passing)

Execute the full suite of integration and scenario tests:

```bash
python -m pytest backend/tests/ -v
```

```
======================= 56 passed in ~34s =======================
```

---

## 📄 License

Distributed under the MIT License. See [LICENSE](LICENSE) for more details.
