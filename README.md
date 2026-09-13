# GOJEP Procurement Dashboard

A production-ready scraper and dashboard for the **Government of Jamaica Electronic Procurement (GOJEP)** portal at [www.gojep.gov.jm](https://www.gojep.gov.jm).

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Browser  →  React + Vite + Tailwind (localhost:5173)       │
│               ↓  /api/* proxy                               │
│  FastAPI backend (localhost:8000)                           │
│    ├─ SQLite database  (backend/procurement.db)             │
│    ├─ Playwright scraper  (headless Chromium)               │
│    ├─ ReportLab PDF generator                               │
│    └─ APScheduler  (daily auto-scrape at 06:00)             │
└─────────────────────────────────────────────────────────────┘
```

| Component | Technology | Why |
|---|---|---|
| Scraper | Python + Playwright | Handles JS-rendered government portals; robust retry logic |
| Backend | FastAPI + SQLAlchemy | Automatic OpenAPI docs; async SSE for live scrape progress |
| Database | SQLite | Zero config, single-file, cross-platform |
| Frontend | React 18 + Vite + Tailwind | Fast dev iteration; Recharts for analytics |
| PDF | ReportLab | Reliable cross-platform PDF; no browser dependency |
| Export | openpyxl (Excel) + csv | Both formats built in |

---

## Quick Start (Local)

### Prerequisites

- Python 3.12 (not 3.13/3.14 — pydantic-core requires ≤ 3.12 currently)
- Node.js 18+ / npm
- **Tesseract OCR** (required for automatic CAPTCHA solving):
  - macOS: `brew install tesseract`
  - Ubuntu/Debian: `sudo apt-get install tesseract-ocr`
  - Windows: download installer from https://github.com/UB-Mannheim/tesseract/wiki

```bash
# 1. Clone / enter the repo
cd PrecurementFindScraper

# 2. Run the one-time setup
./setup.sh

# 3. Start the app
./start.sh
```

Open **http://localhost:5173** in your browser.

Click **Run Scraper Now** in the sidebar. Progress appears in real time.

---

## Manual Setup (step by step)

```bash
# Python environment
python3.12 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
.venv/bin/playwright install chromium

# Database
cd backend
../.venv/bin/python -c "from database import create_tables; create_tables()"
cd ..

# Frontend
cd frontend && npm install && cd ..

# Start backend (terminal 1)
cd backend
../.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Start frontend (terminal 2)
cd frontend
npm run dev
```

---

## Docker (optional)

```bash
docker compose up --build
```

Dashboard at **http://localhost:5173**, API docs at **http://localhost:8000/docs**.

---

## Features

### Dashboard
- Summary stats: total notices, open count, new-since-last-visit badge
- Top agencies bar chart, scrape run history

### Tender List (`/tenders`)
- **Search** across title, description, agency, reference number
- **Filter** by agency, category, status, deadline range, amount range
- **Sort** by any column
- **Multi-select** rows → batch PDF or export
- **NEW** badge on unread notices

### Tender Detail (`/tenders/:id`)
- Full extracted fields: title, reference, agency, deadline, amount, description,
  submission instructions, contact details
- **Download PDF** button (Jamaican government-styled layout)
- **View on GOJEP** link opens original page

### Reports (`/reports`)
- Notices over time (line chart)
- Top 10 agencies (horizontal bar chart + pie chart)
- Contract value min / avg / max

### Export
- **CSV** export (filtered or all)
- **Excel** export with styled headers
- **PDF** for single tender or batch

### Scraper
- Playwright (headless Chromium) — handles the JavaScript-rendered ePPS portal
- **Automatic CAPTCHA solving**: downloads the image CAPTCHA and OCRs it with Tesseract
- Retry logic: up to 8 CAPTCHA attempts per run with fresh image on each retry
- 1.5-second delay between requests (polite crawling)
- Incremental updates — only changed fields are overwritten
- Pagination: automatically walks all 790+ pages (configurable `MAX_LISTING_PAGES`)
- Daily auto-scrape at 06:00 (configurable via `SCRAPE_CRON` env var)

---

## Configuration

All settings are in `backend/config.py` and can be overridden with environment variables:

| Variable | Default | Description |
|---|---|---|
| `GOJEP_SEARCH_FORM_URL` | `https://www.gojep.gov.jm/epps/prepareAdvancedSearch.do?type=cftFTS` | Search form URL |
| `GOJEP_SEARCH_ACTION_URL` | `https://www.gojep.gov.jm/epps/viewCFTSAction.do` | POST endpoint |
| `GOJEP_DETAIL_URL_BASE` | `https://www.gojep.gov.jm/epps/cft/prepareViewCfTWS.do` | Tender detail base URL |
| `GOJEP_STATUS` | `""` (all) | ePPS status filter (e.g. `cft.status.tender.submission` for open only) |
| `MAX_LISTING_PAGES` | `20` | Pages per run (10 tenders/page); set to `0` for full historical |
| `MAX_CAPTCHA_ATTEMPTS` | `8` | Retry limit for CAPTCHA OCR |
| `REQUEST_DELAY` | `1.5` | Seconds between requests |
| `PAGE_TIMEOUT` | `30000` | Playwright timeout (ms) |
| `DATABASE_URL` | `sqlite:///./procurement.db` | SQLAlchemy DB URL |
| `ENABLE_SCHEDULER` | `true` | Enable daily auto-scrape |
| `SCRAPE_CRON` | `0 6 * * *` | Cron expression for scheduler |
| `LOG_LEVEL` | `INFO` | Python log level |

---

## How the Scraper Works (GOJEP ePPS platform)

The GOJEP portal (`www.gojep.gov.jm`) runs the **European Dynamics ePPS** platform,
a Java-based procurement system. Accessing tender data requires:

1. Navigating to the **Advanced Search** form (`/epps/prepareAdvancedSearch.do`)
2. Solving an **image CAPTCHA** (`/epps/genCaptcha/captcha.jpg`) via Tesseract OCR
3. **POSTing** the search form to `/epps/viewCFTSAction.do`
4. Parsing results from `<table id="T01">` (10 rows per page)
5. Navigating detail pages at `/epps/cft/prepareViewCfTWS.do?resourceId=XXXXX`
6. Extracting fields from `<dl class="Grid">` (definition list of label/value pairs)

### Updating Selectors if the Site Changes

```bash
cd backend
../.venv/bin/python scraper.py --inspect   # saves gojep_inspect.html
../.venv/bin/python scraper.py --test      # scrapes 1 page, prints results
```

Key config to update in `backend/config.py`:
- `ListingSelectors.results_table` — table ID containing tender rows
- `ListingSelectors.next_button` — selector for the next-page button
- `DetailLabels.*` — label text strings to match in `dl.Grid`

---

## API Reference

The backend auto-generates interactive docs at **http://localhost:8000/docs**.

Key endpoints:

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/tenders` | List with filters + pagination |
| `GET` | `/api/tenders/{id}` | Single tender detail |
| `DELETE` | `/api/tenders/{id}` | Remove tender |
| `POST` | `/api/scrape` | Trigger scrape |
| `GET` | `/api/scrape/stream` | SSE progress stream |
| `GET` | `/api/scrape/runs` | Scrape run history |
| `GET` | `/api/stats` | Dashboard statistics |
| `GET` | `/api/export/csv` | CSV export |
| `GET` | `/api/export/excel` | Excel export |
| `GET` | `/api/tenders/{id}/pdf` | PDF for one tender |
| `POST` | `/api/export/pdf/batch` | Batch PDF (body: `{"tender_ids": [1,2,3]}`) |
| `GET` | `/api/filters/agencies` | Agency filter options |
| `GET` | `/api/filters/categories` | Category filter options |

---

## Project Layout

```
PrecurementFindScraper/
├── backend/
│   ├── config.py          ← CSS selectors + all settings
│   ├── main.py            ← FastAPI app + all routes
│   ├── scraper.py         ← Playwright scraper
│   ├── models.py          ← SQLAlchemy ORM models
│   ├── database.py        ← DB connection
│   ├── schemas.py         ← Pydantic request/response models
│   ├── crud.py            ← Database helpers
│   ├── pdf_generator.py   ← ReportLab PDF generation
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── api.js          ← All API calls
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx
│   │   │   ├── TenderList.jsx
│   │   │   ├── TenderDetail.jsx
│   │   │   └── Reports.jsx
│   │   └── components/
│   │       ├── ScrapePanel.jsx   ← Run scraper + SSE progress
│   │       ├── FilterBar.jsx
│   │       └── StatCard.jsx
│   ├── package.json
│   ├── vite.config.js
│   └── tailwind.config.js
├── Dockerfile.backend
├── frontend/Dockerfile.frontend
├── docker-compose.yml
├── setup.sh
├── start.sh
└── README.md
```

---

## Troubleshooting

**Scraper finds 0 notices**
- Run `python scraper.py --inspect` and open `gojep_inspect.html`
- Check if GOJEP redirects to a login page or shows a CAPTCHA
- Update `LISTING_URL` in `config.py` to the correct opportunities page URL

**`pydantic-core` build fails**
- Use Python 3.12 exactly: `python3.12 -m venv .venv`

**`playwright install` fails**
- On Linux, run `playwright install-deps chromium` first

**Port 8000 already in use**
- `lsof -ti:8000 | xargs kill` then retry
