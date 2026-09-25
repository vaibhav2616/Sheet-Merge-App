# ⚡ SheetMerge Pro
> **The High-Performance Outreach CRM & Enterprise Deliverability Engine.**  
> Fluid Bento-Box architecture, responsive mobile bottom dock, single-column YAMM standard, and bulletproof anti-spam protection.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![Tests](https://img.shields.io/badge/Tests-48%2F48%20Passing-brightgreen?logo=pytest)](https://pytest.org)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## 🎨 Design Philosophy & UX Innovation

SheetMerge Pro brings modern software craftsmanship to outbound sales, recruitment, and email automation. Inspired by high-end dark bento interfaces, it combines dense utility with a distraction-free aesthetic:

* **Obsidian & Almond Contrast:** Deep dark surfaces (`#0a0c10`), warm almond card tiles (`#f4f3ef`), and burnt orange/coral accents (`#ff5722`).
* **Fluid Responsive Architecture:**
  * **Desktop:** Vertical left-side rail (`width: 76px`) with quick stage switchers and user profile avatar.
  * **Mobile / Phone:** Rail smoothly converts into a **floating bottom navigation bar**, stacking all bento cards into an intuitive single scrolling column.
* **Interactive Pillar Chart:** Live visual distribution of deals across pipeline stages (`New`, `Contacted`, `Qualified`, `Proposal Sent`, `Won`, `Lost`).
* **Slide-Out Lead Drawer:** Click any contact or deal to slide out an activity timeline, manage stage progression, and write notes.
* **Spotlight Command Palette (`⌘K` / `Ctrl+K`):** Instant keyboard-first search across all leads, companies, and actions.

---

## 🛡️ Enterprise Deliverability Shield

Unlike conventional merge extensions that risk domain burn by blasting unthrottled batches, SheetMerge Pro implements enterprise-grade sender protection:

1. **YAMM Single 'Merge Status' Column:**
   * Consolidates all delivery, open, click, and bounce indicators into a single standardized column (`EMAIL_SENT`, `EMAIL_OPENED`, `EMAIL_CLICKED`, `EMAIL_BOUNCED`).
   * Eliminates messy multi-column sprawl.

2. **50-Send Daily Quota Protection (Valid Sends Only):**
   * Hard bounces are excluded from your daily quota calculation.
   * Keeps sending until you achieve **50 verified successful deliveries** per day.

3. **Multi-Account Rotation:**
   * Automatically switches accounts when quota thresholds are reached (e.g. Account A sends 50, then Account B sends 50).

4. **Permanent 5xx Hard Bounce Suppression:**
   * Catches `550`, `551`, `553`, and `554` SMTP responses and instantly logs the address to a local suppression list.
   * Dead addresses are never contacted again, safeguarding your domain reputation.

5. **Humanized Delay & Randomized Jitter:**
   * Randomizes inter-message delays between 2.0s and 5.0s (`random.uniform(2.0, 5.0)`) to mimic human typing and pacing, preventing automated firewall blocks by Microsoft Exchange and Google Workspace.

6. **Pre-flight DNS Inspection (SPF, DKIM, DMARC):**
   * Live DNS diagnostics verify your domain records before campaign launch.

7. **45+ Rule Content Spam Analyzer:**
   * Scans subject lines and message bodies for high-risk spam triggers, excessive capitalization, exclamation marks, and dangerous link-to-text ratios.

---

## 📂 Project Architecture

```
SheetMerge-App/
├── backend/
│   ├── data/                   # SQLite database directory (auto-created)
│   ├── tests/                  # Pytest test suite (100% pass)
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
│   ├── app.js                  # Client state, bento renderers & Cmd+K palette
│   ├── index.html              # Bento grid structure & slide-out drawer
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
1. Install requirements via `pip`.
2. Launch the FastAPI server at `http://localhost:8000`.
3. Open the Bento-Box UI in your default browser.

### Option 2: Docker Compose (Recommended for Production)
```bash
git clone https://github.com/vaibhav2616/SheetMerge-App.git
cd SheetMerge-App
docker-compose up -d --build
```
Access the application at `http://localhost:8000`.

### Option 3: Manual Setup
```bash
# 1. Clone repository
git clone https://github.com/vaibhav2616/SheetMerge-App.git
cd SheetMerge-App

# 2. Install Python dependencies
pip install -r backend/requirements.txt

# 3. Start the application
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

---

## 🧪 Running the Automated Test Suite

SheetMerge Pro comes with comprehensive end-to-end unit and integration test coverage:

```bash
# Run the complete Pytest suite
python -m pytest backend/tests -v
```

**Results:**
* ✅ **48/48 Passing Tests** covering domain security, spam heuristics, SMTP error handling, bounce suppression, and REST APIs.

---

## 🔌 Core API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Serves the interactive Bento-Box UI |
| `GET` | `/api/leads` | Lists all leads and pipeline deals |
| `POST` | `/api/leads` | Creates a new outreach lead |
| `PATCH` | `/api/leads/{id}` | Updates lead stage and attributes |
| `POST` | `/api/leads/{id}/notes` | Appends a note to a lead's timeline |
| `POST` | `/api/security/check-domain` | Evaluates SPF, DKIM, DMARC, and MX records |
| `POST` | `/api/security/analyze-content` | Computes spam score and trigger warnings |
| `POST` | `/api/security/clean-list` | Validates recipient list against suppression DB |
| `POST` | `/api/relay/send` | Dispatches emails via humanized throttled relay |
| `GET` | `/track/open/{track_id}` | 1x1 transparent tracking pixel |
| `GET` | `/track/click/{track_id}` | Click redirect logger |

---

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

