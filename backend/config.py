"""
Central configuration for the GOJEP ePPS scraper.

The GOJEP portal (www.gojep.gov.jm) runs the European Dynamics ePPS platform.
Tender data is accessed via an Advanced Search form that requires an image CAPTCHA.
The CAPTCHA is solved automatically using pytesseract OCR.

To update selectors if the site changes:
    cd backend && ../.venv/bin/python scraper.py --inspect
This saves gojep_inspect.html which you can open in a browser to inspect the DOM.
"""

from dataclasses import dataclass
import os

# ---------------------------------------------------------------------------
# Network – ePPS platform endpoints
# ---------------------------------------------------------------------------
BASE_URL = os.getenv("GOJEP_BASE_URL", "https://www.gojep.gov.jm")

# Search form page (loads CAPTCHA image)
SEARCH_FORM_URL = os.getenv(
    "GOJEP_SEARCH_FORM_URL",
    "https://www.gojep.gov.jm/epps/prepareAdvancedSearch.do?type=cftFTS",
)

# POST endpoint – submit the search form to this URL
SEARCH_ACTION_URL = os.getenv(
    "GOJEP_SEARCH_ACTION_URL",
    "https://www.gojep.gov.jm/epps/viewCFTSAction.do",
)

# CAPTCHA image (fetched with same session cookie)
CAPTCHA_IMAGE_PATH = "/epps/genCaptcha/captcha.jpg"

# Detail page for a single tender (resourceId appended as query param)
DETAIL_URL_BASE = os.getenv(
    "GOJEP_DETAIL_URL_BASE",
    "https://www.gojep.gov.jm/epps/cft/prepareViewCfTWS.do",
)

# Seconds between requests (be polite – GOJEP servers are not powerful)
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "1.5"))

# Max CAPTCHA solve attempts before giving up
MAX_CAPTCHA_ATTEMPTS = int(os.getenv("MAX_CAPTCHA_ATTEMPTS", "8"))

# Playwright timeout in milliseconds
PAGE_TIMEOUT = int(os.getenv("PAGE_TIMEOUT", "30000"))

# How many detail pages to fetch concurrently (keep ≤ 3 to be polite)
MAX_CONCURRENT_DETAIL = int(os.getenv("MAX_CONCURRENT_DETAIL", "3"))

# Max listing pages to scrape per run (10 results/page; None = no limit)
# Default: 20 pages = ~200 tenders. Set to 0 or None for full historical scrape.
MAX_LISTING_PAGES = int(os.getenv("MAX_LISTING_PAGES", "20"))

# ---------------------------------------------------------------------------
# Search filters sent in the POST body
# Restrict to open/upcoming tenders by default so each run is fast.
# Set SCRAPE_STATUS="" to get all statuses (7,000+ historical records).
# ---------------------------------------------------------------------------

# ePPS status codes:
#   cft.status.tender.submission  → Bid submission (open for bidding)
#   cft.status.established        → Established (upcoming)
#   cft.status.evaluation         → Under evaluation
#   cft.status.award              → Awarded
#   (empty string)                → all statuses
SCRAPE_STATUS = os.getenv("GOJEP_STATUS", "")

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./procurement.db")

# ---------------------------------------------------------------------------
# Selectors – listing results page (table#T01)
# ---------------------------------------------------------------------------

@dataclass
class ListingSelectors:
    # The results table (DisplayTag rendered, id="T01")
    results_table: str = "table#T01"

    # Data rows inside the table (skip the header row)
    data_rows: str = "table#T01 tr:not(:first-child)"

    # Inside each data row:
    title_link: str = "td:nth-child(2) a"       # tender title + detail URL
    agency_cell: str = "td:nth-child(3)"         # Procuring Entity name
    deadline_cell: str = "td:nth-child(5)"       # Bid submission deadline
    procedure_cell: str = "td:nth-child(6)"      # Procurement procedure
    status_cell: str = "td:nth-child(7)"         # Competition status
    amount_cell: str = "td:nth-child(10)"        # Estimated total contract value

    # Pagination: next-page button uses a non-standard <button href="..."> element
    # The href attribute on button[title="Next"] contains the next-page URL.
    next_button: str = 'button.SearchBtn[title="Next"]'
    last_button: str = 'button.SearchBtn[title="Last"]'
    total_count: str = "p.Results"    # "7,893 results in total."
    page_nav: str = "p.PageNav"       # "Page 1 of 790"


# ---------------------------------------------------------------------------
# Selectors – tender detail page (dl.Grid with dt/dd pairs)
# The detail page uses a definition list <dl class="Grid"> where:
#   <dt>Label:</dt><dd>Value</dd>
# We match by label text (case-insensitive prefix).
# ---------------------------------------------------------------------------

@dataclass
class DetailLabels:
    """Label strings to look for in the dl.Grid on the detail page."""
    title: str = "Title"
    description: str = "Description"
    agency: str = "Name of procuring entity"
    deadline: str = "Deadline for bid submission"
    original_deadline: str = "Original deadline for bid submission"
    amount: str = "Estimated total contract value"
    category: str = "PPC-NCC Categories"
    procurement_type: str = "Procurement Type"
    reference: str = "Project reference number"
    unique_id: str = "Competition unique ID"
    resource_id: str = "Resource ID"
    procedure: str = "Procurement Method"
    funding: str = "Funding Source"
    cpv: str = "Common Procurement Vocabulary"
    bid_opening: str = "Bid opening date"

    # The main data list selector on the detail page
    grid_selector: str = "dl.Grid"
    # Title fallback (competition header)
    context_menu: str = "div.ContextMenu strong"


LISTING_SELECTORS = ListingSelectors()
DETAIL_LABELS = DetailLabels()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "scraper.log")

# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------
ENABLE_SCHEDULER = os.getenv("ENABLE_SCHEDULER", "true").lower() == "true"
SCRAPE_CRON = os.getenv("SCRAPE_CRON", "0 6 * * *")
