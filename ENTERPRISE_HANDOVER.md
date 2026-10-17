# 🏛️ Senior Enterprise Architect Handover & System Manifest
**Author / Principal Architect:** Pawan Dharamthok  
**Acting Systems Architect:** Antigravity AI  
**Last Updated:** October 18, 2026  
**Status:** 100% Operational • Dual-Tier Cloud & Local DR Active  

---

## 🎯 1. Core Operating Principles (Non-Negotiables)
Every design choice, cloud deployment, and architectural refactoring across this portfolio strictly follows two foundational rules:

1. **Super Secure (Zero-Trust Standard)**:
   - **Zero Secret Exposure**: No credentials, API tokens, or session secrets hardcoded in git repositories or baked into Docker layers.
   - **Air-Gapped & PII Sanitized**: Client-side regex & classification sanitization (`security_router.py`) cleanses user inputs, account numbers, and secrets before contacting external LLM models.
   - **Front-Door Authentication Barrier**: Any public cloud endpoint must be protected by an authentication wall (e.g. Master Passcode / Cloudflare Zero Trust) to block unauthorized access to private models, Zerodha assets, and personal memory.
   - **Least Privilege**: Containers execute as unprivileged system users (`appuser`, UID 1001), not root.

2. **Always Free (₹0 TCO Cloud Cost)**:
   - **Zero Cloud Spend**: Built entirely on permanent Always-Free quotas, serverless runtimes, and Anycast CDN tiers.
   - **Zero Credit Card Lock-in**: Deployed on compute and hosting providers that do not require credit card linkage for core hosting (e.g., Render free tier, Firebase Spark plan, GitHub Actions free tiers).

---

## 🌐 2. Live Enterprise Fleet Architecture

```
                          [ GLOBAL USERS & ACCESS ]
                                      │
            ┌─────────────────────────┴─────────────────────────┐
            ▼                                                   ▼
┌──────────────────────────────────────┐     ┌──────────────────────────────────────┐
│       TIER 1: STATIC APPS & HUBS     │     │      TIER 2: 24/7 DYNAMIC ASSISTANT  │
│   Firebase Hosting (Google Global)   │     │         Render Serverless Cloud      │
│     • Latency: < 300ms Globally      │     │      • 512 MB Nano Docker Engine     │
│     • Project: family-apps-hub       │     │      • Master Passcode Gate          │
│     • Cost: ₹0.00 / month            │     │      • Cost: ₹0.00 / month           │
└──────────────────────────────────────┘     └──────────────────┬───────────────────┘
                                                                │
                                             ┌──────────────────┴───────────────────┐
                                             ▼                                      ▼
                                ┌─────────────────────────┐            ┌─────────────────────────┐
                                │   TIER 3: LOCAL STANDBY │            │  TIER 4: AUTOMATED DR   │
                                │   Desktop / Port 5000   │            │  GitHub Actions Nightly │
                                │ • SQLite (memory.db)    │            │ • GPG Encrypted Dumps   │
                                │ • Air-Gapped Fallback   │            │ • 1-Click Redeployment  │
                                └─────────────────────────┘            └─────────────────────────┘
```

---

## 📋 3. Fleet Registry & Endpoints Inventory

| # | Project Name | Category | Primary Live Endpoint | Hosting & Tech Stack |
|---|---|---|---|---|
| **1** | **Master Enterprise Registry** | Enterprise Hub | [pawan-dharamthok-projects.web.app](https://pawan-dharamthok-projects.web.app) | Firebase Hosting (Anycast CDN) |
| **2** | **AI Leadership Lab Assistant (Cloud)** | Private / AI | [ai-leadership-assistant.onrender.com](https://ai-leadership-assistant.onrender.com) | Render Docker (Python 3.12, Flask, Gunicorn, Gemini 2.0 Flash) |
| **2b**| **AI Leadership Lab Assistant (Local)** | Private Standby | `http://127.0.0.1:5000` | Local Python venv on Windows (Port 5000) |
| **3** | **Priority Dashboard & CIO Briefing** | Strategic | [priority-dashboard.web.app/cio-briefing.html](https://priority-dashboard.web.app/cio-briefing.html) | Firebase Hosting (3-Tier Agentic briefing) |
| **4** | **Pawan Vault** | Private / Secure | [pawan-vault.web.app](https://pawan-vault.web.app) | Firebase Hosting (Zero-Trust encrypted docs) |
| **5** | **Pawan Networth Engine** | Private / Finance | [pawan-networth.web.app](https://pawan-networth.web.app) | Client-side AES-256 wealth analytics |
| **6** | **Family Apps Hub** | Public Portal | [family-apps-hub.web.app](https://family-apps-hub.web.app) | Central learning and family management hub |
| **7** | **Yukti-Verse (Olympiad Universe)** | EdTech AI | [yukti-verse.web.app](https://yukti-verse.web.app) | IMO / NSO / IEO exam simulations |
| **8** | **Yukti Exam Prep** | EdTech | [yukti-exam-prep.web.app](https://yukti-exam-prep.web.app) | Structured question banks & timing engine |
| **9** | **Kaashwi English** | EdTech | [kaashwi-english.web.app](https://kaashwi-english.web.app) | Interactive grammar, phonics & vocabulary |
| **10**| **Curated Reading Library** | EdTech | [reading-library.web.app](https://reading-library.web.app) | Digital literature library & reading tracker |
| **11**| **Ledger Pomodoro Engine** | Productivity | [ledger-pomodoro.web.app](https://ledger-pomodoro.web.app) | Deep-work focus ledger & accountability timer |
| **12**| **Klozzle Puzzle Game** | Logic / Canvas | [klozzle-puzzle.web.app](https://klozzle-puzzle.web.app) | Spatial reasoning & logic game engine |
| **13**| **KS Home Interior & Management** | Private | [ks-home-interior.web.app](https://ks-home-interior.web.app) | HomeCanvas flat layout, vendor specifications |
| **14**| **Weekly Family Contract** | Private | [weekly-contract.web.app](https://weekly-contract.web.app) | Family goal agreements & habit ledger |
| **15**| **CareerWithAI Portfolio** | Public / AI | [github.com/pawandharamthok-collab/CareerWithAI](https://github.com/pawandharamthok-collab/CareerWithAI) | Enterprise AI strategic roadmap repository |

---

## 🔐 4. Executive Assistant Security & Authentication Topology

### A. Access Barrier (`templates/login.html` & `server.py`)
* The application intercepts all unauthenticated HTTP requests via `@app.before_request`.
* If a session does not have `session["authenticated"] = True`, the user is immediately redirected to `/login`.
* REST endpoints under `/api/*` reject unauthenticated calls with `401 Unauthorized`.
* **Password Validation**:
  * Evaluated dynamically on request: `passcode == os.getenv("MASTER_PASSCODE").strip()`.
  * Configured via **Render Dashboard ➔ Environment Variables ➔ `MASTER_PASSCODE`**.
  * No default fallbacks (e.g. `1983` has been stripped from the logic).
* **Session Persistence**: Stored via encrypted session cookies using `SESSION_SECRET`.
* **Logout Endpoint**: `/logout` destroys the session cookie and locks the front door.

### B. Environment Secrets Matrix (Render Vault)
These secrets are stored exclusively in Render's encrypted environment vault:
* `MASTER_PASSCODE`: User-defined access password.
* `GEMINI_API_KEY`: Google AI Studio production API key (`gemini-2.0-flash`).
* `PINECONE_API_KEY`: Pinecone serverless vector index key (`ai-leadership-kb`).
* `ZERODHA_MOCK_MODE`: `false` (enables live Kite Connect read-only portfolio analysis).
* `ZERODHA_API_KEY`, `ZERODHA_API_SECRET`, `ZERODHA_ACCESS_TOKEN`: Read-only trading tokens.
* `PORT`: `8080`.
* `APP_ENV`: `production`.

---

## 🛠️ 5. Key File Locations & Git Repositories

### Repositories:
* **Assistant Codebase**: [`https://github.com/pawandharamthok-collab/ai-leadership-lab`](https://github.com/pawandharamthok-collab/ai-leadership-lab) (Branch: `master`)
* **Fleet Codebase**: [`https://github.com/pawandharamthok-collab/family-apps-fleet`](https://github.com/pawandharamthok-collab/family-apps-fleet) (Branch: `master`)

### Critical Local Files:
* **Local Assistant Path**: `C:\Users\Pawan Dharamthok\Desktop\ai-leadership-lab`
  * [`Dockerfile`](file:///C:/Users/Pawan%20Dharamthok/Desktop/ai-leadership-lab/Dockerfile): Hardened non-root Python 3.12 container with Gunicorn WSGI.
  * [`render.yaml`](file:///C:/Users/Pawan%20Dharamthok/Desktop/ai-leadership-lab/render.yaml): Render Infrastructure-as-Code Blueprint.
  * [`server.py`](file:///C:/Users/Pawan%20Dharamthok/Desktop/ai-leadership-lab/server.py): Flask application engine with dynamic `DB_PATH`, PII sanitizer, Zerodha tools, and auth guard.
  * [`templates/login.html`](file:///C:/Users/Pawan%20Dharamthok/Desktop/ai-leadership-lab/templates/login.html): Dark-mode luxury Master Passcode login vault.
  * [`requirements.txt`](file:///C:/Users/Pawan%20Dharamthok/Desktop/ai-leadership-lab/requirements.txt): Sanitized cross-platform dependencies (Windows-only `pywin32` removed).
  * [`.github/workflows/cloud-run-deploy.yml`](file:///C:/Users/Pawan%20Dharamthok/Desktop/ai-leadership-lab/.github/workflows/cloud-run-deploy.yml): Automated zero-cost Cloud Run deployment pipeline.
  * [`.github/workflows/dr-backup.yml`](file:///C:/Users/Pawan%20Dharamthok/Desktop/ai-leadership-lab/.github/workflows/dr-backup.yml): Nightly cold-standby verification pipeline.
* **Local Fleet Directory Path**: `C:\Users\Pawan Dharamthok\family-apps-fleet`
  * `pawan-dharamthok-projects/public/index.html`: Master Registry frontend with dual-launch buttons for 24/7 Cloud and Local Standby.

---

## 🔄 6. Disaster Recovery (DR) & Redeployment Runbooks

### Runbook A: Update Assistant Code or Features
1. Modify code in `C:\Users\Pawan Dharamthok\Desktop\ai-leadership-lab`.
2. Commit and push:
   ```powershell
   git add .
   git commit -m "feat: your new feature"
   git push origin master
   ```
3. Render automatically rebuilds and deploys the update to [ai-leadership-assistant.onrender.com](https://ai-leadership-assistant.onrender.com) in ~45 seconds.

### Runbook B: Change Master Passcode
1. Open [dashboard.render.com](https://dashboard.render.com) ➔ `ai-leadership-assistant` ➔ **Environment**.
2. Update the value of `MASTER_PASSCODE`.
3. Click **Save, rebuild, and deploy**. The new password becomes active in ~20 seconds.

### Runbook C: Deploy / Update Any Firebase Web App
1. Navigate to the project directory:
   ```powershell
   cd 'C:\Users\Pawan Dharamthok\family-apps-fleet\<project-name>'
   ```
2. Deploy to production:
   ```powershell
   firebase deploy --only hosting
   ```

---

## 📌 7. Instructions for Future AI Assistant Sessions
When starting any new session with Pawan Dharamthok:
1. **Never suggest costly cloud alternatives**: Always uphold the **₹0 TCO** standard.
2. **Never suggest exposing credentials or opening unsecured endpoints**: Always verify zero-trust authentication boundaries.
3. **Recognize the dual setup**: The Executive Assistant lives 24/7 in the cloud on Render ([ai-leadership-assistant.onrender.com](https://ai-leadership-assistant.onrender.com)) protected by `MASTER_PASSCODE`, with a secondary local standby on port 5000.
4. **All 15 fleet sites are cataloged** at [pawan-dharamthok-projects.web.app](https://pawan-dharamthok-projects.web.app).
