"""
GOJEP Procurement Scraper – ePPS platform edition.

The GOJEP portal runs European Dynamics ePPS. Tender data is behind an image
CAPTCHA.  This scraper solves it automatically with Tesseract OCR.

Flow:
  1. Open headless Chromium and navigate to the Advanced Search form.
  2. Download the CAPTCHA image (same session → bound to session cookie).
  3. OCR the image with pytesseract (psm 7, alphanumeric whitelist).
  4. POST the search form with the solved CAPTCHA and empty filters.
  5. If "Code mismatch" → reload page, get fresh CAPTCHA, retry (up to 8×).
  6. Parse the results table (table#T01), extract title + detail URL per row.
  7. Follow pagination by extracting the next-page URL from <button href=...>.
  8. Visit each detail page and extract fields from <dl class="Grid"> dt/dd pairs.
  9. Upsert into the database; emit SSE progress events.

Run `python scraper.py --inspect` to save the live HTML for selector debugging.
Run `python scraper.py --test` to scrape 1 page and print results without saving.
"""

import asyncio
import io
import json
import logging
import re
import sys
from datetime import date, datetime
from typing import AsyncGenerator, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse, parse_qs, urlencode

from bs4 import BeautifulSoup
from PIL import Image
from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    TimeoutError as PlaywrightTimeout,
)

try:
    import pytesseract
    _TESSERACT_AVAILABLE = True
except ImportError:
    _TESSERACT_AVAILABLE = False

import config as cfg
from config import (
    BASE_URL,
    SEARCH_FORM_URL,
    SEARCH_ACTION_URL,
    CAPTCHA_IMAGE_PATH,
    DETAIL_URL_BASE,
    REQUEST_DELAY,
    MAX_CAPTCHA_ATTEMPTS,
    PAGE_TIMEOUT,
    MAX_CONCURRENT_DETAIL,
    MAX_LISTING_PAGES,
    SCRAPE_STATUS,
    LISTING_SELECTORS as LS,
    DETAIL_LABELS as DL,
)
from schemas import TenderCreate

logger = logging.getLogger("scraper")

# ---------------------------------------------------------------------------
# CAPTCHA solver
# ---------------------------------------------------------------------------

def _ocr_captcha(img_bytes: bytes) -> str:
    """
    Convert the CAPTCHA image to text using Tesseract.
    The GOJEP CAPTCHA is dark gothic/serif text on a white background –
    psm 7 (single text line) with alphanumeric whitelist gives the best results.
    """
    if not _TESSERACT_AVAILABLE:
        raise RuntimeError(
            "pytesseract is not installed. Run: pip install pytesseract  "
            "and ensure Tesseract is on your PATH."
        )
    img = Image.open(io.BytesIO(img_bytes)).convert("L")
    raw = pytesseract.image_to_string(
        img,
        config=(
            "--psm 7 "
            "-c tessedit_char_whitelist=abcdefghijklmnopqrstuvwxyz0123456789"
        ),
    ).strip()
    # Strip anything that's not alphanumeric
    return re.sub(r"[^a-z0-9]", "", raw.lower())


async def _download_captcha(page: Page) -> bytes:
    """Fetch the CAPTCHA image using the current Playwright session cookies."""
    raw = await page.evaluate(
        """() => fetch('/epps/genCaptcha/captcha.jpg')
               .then(r => r.arrayBuffer())
               .then(buf => Array.from(new Uint8Array(buf)))"""
    )
    return bytes(raw)


# ---------------------------------------------------------------------------
# Search form submission
# ---------------------------------------------------------------------------

async def _submit_search(
    page: Page,
    captcha: str,
    status: str = SCRAPE_STATUS,
    page_num: int = 1,
    table_id: str = "",
) -> str:
    """
    POST to the GOJEP search action endpoint.
    Returns the raw HTML of the results page.
    Raises ValueError if the CAPTCHA was rejected.
    """
    params = {
        "mode": "search",
        "isFTS": "true",
        "isPopup": "false",
        "popupMode": "",
        "title": "",
        "uniqueId": "",
        "contractAuthority": "",
        "description": "",
        "status": status,
        "contractType": "",
        "procedure": "",
        "submissionFromDate": "",
        "submissionUntilDate": "",
        "CPVCodes": "",
        "cpvLabels": "",
        "estimatedValueMin": "",
        "estimatedValueMax": "",
        "tenderOpeningFromDate": "",
        "tenderOpeningUntilDate": "",
        "captcha": captcha,
    }
    # Add DisplayTag pagination parameter if we're past page 1
    if page_num > 1 and table_id:
        params[f"d-{table_id}-p"] = str(page_num)

    body = "&".join(f"{k}={v}" for k, v in params.items())
    js = f"""() => fetch('/epps/viewCFTSAction.do', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
        body: {json.dumps(body)}
    }}).then(r => r.text())"""

    html = await page.evaluate(js)

    # "Code" is wrapped in an <a> tag in the actual HTML, so check parsed text
    from bs4 import BeautifulSoup as _BS
    _soup = _BS(html, "html.parser")
    _page_text = _soup.get_text(" ", strip=True)
    if "code mismatch" in _page_text.lower():
        raise ValueError("CAPTCHA mismatch")
    # Also confirm the results table is present as an additional guard
    if "table" not in html.lower() or "T01" not in html:
        if "error has occurred" in _page_text.lower():
            raise ValueError("Server error – retrying")
    return html


# ---------------------------------------------------------------------------
# CAPTCHA solve + search: combined with retry
# ---------------------------------------------------------------------------

async def _solve_and_search(
    page: Page,
    status: str = SCRAPE_STATUS,
    page_num: int = 1,
    table_id: str = "",
) -> str:
    """
    Solve the CAPTCHA, submit the search, and return the results HTML.
    Retries up to MAX_CAPTCHA_ATTEMPTS times on mismatch.
    """
    for attempt in range(1, MAX_CAPTCHA_ATTEMPTS + 1):
        # Always reload the form to get a fresh CAPTCHA bound to the session
        await page.goto(SEARCH_FORM_URL, wait_until="networkidle", timeout=PAGE_TIMEOUT)
        await asyncio.sleep(0.5)

        img_bytes = await _download_captcha(page)
        captcha_text = _ocr_captcha(img_bytes)
        logger.debug("CAPTCHA OCR attempt %d: %r", attempt, captcha_text)

        if not captcha_text or len(captcha_text) < 4:
            logger.warning("OCR result too short (%r), retrying…", captcha_text)
            continue

        try:
            html = await _submit_search(page, captcha_text, status, page_num, table_id)
            logger.info("CAPTCHA solved on attempt %d (%r)", attempt, captcha_text)
            return html
        except ValueError:
            logger.warning("CAPTCHA wrong on attempt %d (%r), retrying…", attempt, captcha_text)
            await asyncio.sleep(REQUEST_DELAY)

    raise RuntimeError(
        f"Failed to solve CAPTCHA after {MAX_CAPTCHA_ATTEMPTS} attempts. "
        "Check that Tesseract is installed and the CAPTCHA URL hasn't changed."
    )


# ---------------------------------------------------------------------------
# Amount & date parsing
# ---------------------------------------------------------------------------

_AMOUNT_RE = re.compile(
    r"(?:J\$|JMD|USD|US\$|\$)?\s*([\d,]+(?:\.\d{1,2})?)",
    re.IGNORECASE,
)
_MULTIPLIERS = [
    (re.compile(r"\bbillion\b", re.I), 1_000_000_000),
    (re.compile(r"\bmillion\b", re.I), 1_000_000),
    (re.compile(r"\bthousand\b", re.I), 1_000),
    (re.compile(r"\d\s*[Mm]\b(?!D)"), 1_000_000),
    (re.compile(r"\d\s*[Bb]\b"), 1_000_000_000),
    (re.compile(r"\d\s*[Kk]\b"), 1_000),
]
_DATE_FORMATS = [
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
    "%m/%d/%Y %H:%M",
    "%m/%d/%Y",
    "%d %B %Y",
    "%B %d, %Y",
    "%d-%m-%Y",
    "%Y-%m-%d",
    # ePPS format: "Thu Jul 02 16:00:00 COT 2026"
    "%a %b %d %H:%M:%S COT %Y",
    "%a %b %d %H:%M:%S %Z %Y",
]


def _parse_amount(text: str) -> Optional[float]:
    if not text:
        return None
    m = _AMOUNT_RE.search(text)
    if not m:
        return None
    try:
        value = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    for pattern, mult in _MULTIPLIERS:
        if pattern.search(text):
            value *= mult
            break
    return value


def _parse_date(text: str) -> Optional[date]:
    if not text:
        return None
    # Strip timezone suffix like "UTC-5" or "COT"
    cleaned = re.sub(r"\s+UTC[-+]\d+|\s+COT|\s+EST|\s+EDT", "", text).strip()
    # Strip ordinal suffixes
    cleaned = re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", cleaned, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    logger.debug("Could not parse date: %r → %r", text, cleaned)
    return None


def _detect_currency(text: str) -> str:
    if "USD" in text.upper() or "US$" in text:
        return "USD"
    return "JMD"


# ---------------------------------------------------------------------------
# Listing page parser
# ---------------------------------------------------------------------------

def _extract_table_id(html: str) -> str:
    """Extract the DisplayTag numeric table ID from pagination button hrefs."""
    m = re.search(r"d-(\d+)-p=", html)
    return m.group(1) if m else ""


def _parse_listing_page(html: str) -> Tuple[List[Dict], str, int, Optional[str]]:
    """
    Parse one results page.
    Returns:
        (rows, table_id, total_count, next_page_url)
    Where each row is a dict with: url, title, agency, deadline, status,
                                    procedure, amount
    """
    soup = BeautifulSoup(html, "html.parser")

    # Extract DisplayTag table ID for pagination
    table_id = _extract_table_id(html)

    # Total count
    total_count = 0
    count_el = soup.select_one(LS.total_count)
    if count_el:
        m = re.search(r"([\d,]+)", count_el.get_text())
        if m:
            total_count = int(m.group(1).replace(",", ""))

    # Parse data rows
    table = soup.select_one(LS.results_table)
    rows = []
    if table:
        data_rows = table.select("tr:not(:first-child)")
        for tr in data_rows:
            cells = tr.find_all("td")
            if not cells:
                continue

            # Cell indices (1-based in CSS, 0-based in Python)
            title_cell = cells[1] if len(cells) > 1 else None
            agency_cell = cells[2] if len(cells) > 2 else None
            deadline_cell = cells[4] if len(cells) > 4 else None
            procedure_cell = cells[5] if len(cells) > 5 else None
            status_cell = cells[6] if len(cells) > 6 else None
            amount_cell = cells[9] if len(cells) > 9 else None

            link_el = title_cell.find("a", href=True) if title_cell else None
            if not link_el:
                continue

            href = link_el.get("href", "")
            detail_url = urljoin(BASE_URL, href) if href else None
            if not detail_url:
                continue

            rows.append({
                "url": detail_url,
                "title": link_el.get_text(" ", strip=True),
                "agency": agency_cell.get_text(" ", strip=True) if agency_cell else "",
                "deadline_raw": deadline_cell.get_text(" ", strip=True) if deadline_cell else "",
                "status": status_cell.get_text(" ", strip=True) if status_cell else "",
                "procedure": procedure_cell.get_text(" ", strip=True) if procedure_cell else "",
                "amount_raw": amount_cell.get_text(" ", strip=True) if amount_cell else "",
            })

    # Next-page URL: look for <button class="SearchBtn" title="Next" href="...">
    next_url = None
    next_btn = soup.select_one('button.SearchBtn[title="Next"]')
    if next_btn:
        href = next_btn.get("href", "")
        if href:
            next_url = urljoin(SEARCH_ACTION_URL, href)

    return rows, table_id, total_count, next_url


# ---------------------------------------------------------------------------
# Detail page parser
# ---------------------------------------------------------------------------

def _dl_to_dict(soup: BeautifulSoup) -> Dict[str, str]:
    """
    Extract all dt/dd pairs from the first dl.Grid element.
    Returns a dict mapping lowercased label → value text.
    """
    dl = soup.select_one(DL.grid_selector)
    if not dl:
        return {}

    result = {}
    dts = dl.find_all("dt")
    for dt in dts:
        label = dt.get_text(" ", strip=True).rstrip(":").strip().lower()
        dd = dt.find_next_sibling("dd")
        if dd:
            result[label] = dd.get_text(" ", strip=True)
    return result


def _match_label(fields: Dict[str, str], label: str) -> str:
    """Case-insensitive prefix match of label against extracted fields."""
    label_lower = label.lower()
    for key, value in fields.items():
        if key.startswith(label_lower) or label_lower in key:
            return value
    return ""


def parse_detail_page(html: str, url: str) -> TenderCreate:
    """
    Extract a TenderCreate from a detail page HTML.
    The detail page uses <dl class="Grid"> with <dt>Label:</dt><dd>Value</dd>.
    """
    soup = BeautifulSoup(html, "html.parser")
    fields = _dl_to_dict(soup)

    # Title from dl.Grid, fall back to context menu header
    title = (
        _match_label(fields, DL.title)
        or _match_label(fields, "competition unique id")
        or ""
    )
    if not title:
        cm = soup.select_one(DL.context_menu)
        if cm:
            title = cm.get_text(" ", strip=True)
    if not title:
        title = "Untitled"

    description = _match_label(fields, DL.description)
    agency = _match_label(fields, DL.agency)

    # Deadline: prefer "Deadline for bid submission" over "Original deadline..."
    deadline_raw = (
        _match_label(fields, DL.deadline)
        or _match_label(fields, DL.original_deadline)
    )
    deadline = _parse_date(deadline_raw)

    # Amount
    amount_raw = _match_label(fields, DL.amount)
    amount = _parse_amount(amount_raw)
    currency = _detect_currency(amount_raw)

    # Category: PPC-NCC first, then Procurement Type
    category = (
        _match_label(fields, DL.category)
        or _match_label(fields, DL.procurement_type)
    )

    # Reference: project reference number or competition unique ID
    reference = (
        _match_label(fields, DL.reference)
        or _match_label(fields, DL.unique_id)
    )

    # Procedure / funding as instructions fallback
    procedure = _match_label(fields, DL.procedure)
    funding = _match_label(fields, DL.funding)
    cpv = _match_label(fields, DL.cpv)
    bid_opening = _match_label(fields, DL.bid_opening)

    # Build a structured instructions block from available metadata
    instructions_parts = []
    if procedure:
        instructions_parts.append(f"Procurement Method: {procedure}")
    if funding:
        instructions_parts.append(f"Funding Source: {funding}")
    if cpv:
        instructions_parts.append(f"CPV Codes: {cpv}")
    if bid_opening:
        instructions_parts.append(f"Bid Opening Date: {bid_opening}")
    instructions = "\n".join(instructions_parts) or None

    # Status from dl fields (may not be there; listing page provides it)
    status_raw = _match_label(fields, "status") or None

    return TenderCreate(
        title=title.strip(),
        description=description or None,
        buyer_agency=agency or None,
        deadline=deadline,
        estimated_amount=amount,
        currency=currency,
        status=status_raw,
        category=category or None,
        instructions=instructions,
        contact_details=None,
        source_url=url,
        reference_number=reference or None,
        raw_html=html[:50_000],
    )


# ---------------------------------------------------------------------------
# Main scrape coroutine
# ---------------------------------------------------------------------------

async def run_scrape(
    progress_queue: asyncio.Queue,
    db_session_factory,
    triggered_by: str = "manual",
) -> Dict:
    """
    Full scrape: solve CAPTCHA → walk listing pages → scrape details → upsert DB.
    Posts progress events to `progress_queue`.
    """
    from crud import upsert_tender, create_scrape_run, update_scrape_run

    db = db_session_factory()
    run = create_scrape_run(db, triggered_by=triggered_by)
    run_id = run.id
    db.close()

    summary = {
        "run_id": run_id,
        "pages_scraped": 0,
        "tenders_found": 0,
        "tenders_new": 0,
        "tenders_updated": 0,
        "error": None,
    }

    try:
        async with async_playwright() as pw:
            browser: Browser = await pw.chromium.launch(headless=True)
            ctx: BrowserContext = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (compatible; GojepScraper/1.0; "
                    "https://github.com/your-repo/gojep-scraper)"
                )
            )

            # One page for all listing fetches (maintains session / cookies)
            search_page: Page = await ctx.new_page()

            # ── Step 1: CAPTCHA + initial search ──────────────────────────
            await progress_queue.put({"type": "status", "msg": "Solving CAPTCHA…"})
            listing_html = await _solve_and_search(search_page)

            rows, table_id, total_count, next_url = _parse_listing_page(listing_html)
            pages_done = 1
            summary["pages_scraped"] = 1

            if total_count:
                await progress_queue.put({
                    "type": "total_urls",
                    "count": total_count,
                    "msg": f"Found {total_count:,} notices across all pages",
                })

            all_rows = list(rows)
            await progress_queue.put({
                "type": "page",
                "page": 1,
                "found": len(rows),
                "url": SEARCH_FORM_URL,
            })
            logger.info("Page 1: %d rows (total: %d)", len(rows), total_count)

            # ── Step 2: Walk pagination ────────────────────────────────────
            max_pages = MAX_LISTING_PAGES if MAX_LISTING_PAGES else 9999
            while next_url and pages_done < max_pages:
                await asyncio.sleep(REQUEST_DELAY)
                pages_done += 1
                await progress_queue.put({
                    "type": "page",
                    "page": pages_done,
                    "url": next_url,
                })
                logger.info("Fetching page %d: %s", pages_done, next_url)

                try:
                    page_html = await search_page.evaluate(
                        f"""() => fetch({json.dumps(next_url)}).then(r => r.text())"""
                    )
                except Exception as exc:
                    logger.warning("Error fetching page %d: %s", pages_done, exc)
                    break

                page_rows, _, _, next_url = _parse_listing_page(page_html)
                all_rows.extend(page_rows)
                summary["pages_scraped"] = pages_done

                await progress_queue.put({
                    "type": "urls_found",
                    "count": len(page_rows),
                    "total": len(all_rows),
                })

            logger.info(
                "Collected %d tender rows across %d pages", len(all_rows), pages_done
            )
            summary["tenders_found"] = len(all_rows)

            # ── Step 3: Scrape detail pages ───────────────────────────────
            sem = asyncio.Semaphore(MAX_CONCURRENT_DETAIL)
            new_count = 0
            updated_count = 0

            async def scrape_detail(row: Dict, idx: int):
                nonlocal new_count, updated_count
                async with sem:
                    url = row["url"]
                    detail_page = await ctx.new_page()
                    try:
                        await asyncio.sleep(REQUEST_DELAY)
                        await detail_page.goto(
                            url, wait_until="networkidle", timeout=PAGE_TIMEOUT
                        )
                        html = await detail_page.content()
                        tender_data = parse_detail_page(html, url)

                        # Merge listing-level data (status, procedure)
                        # that may not appear on the detail page
                        if not tender_data.status and row.get("status"):
                            tender_data.status = row["status"]
                        if not tender_data.buyer_agency and row.get("agency"):
                            tender_data.buyer_agency = row["agency"]
                        if not tender_data.deadline and row.get("deadline_raw"):
                            tender_data.deadline = _parse_date(row["deadline_raw"])
                        if not tender_data.estimated_amount and row.get("amount_raw"):
                            tender_data.estimated_amount = _parse_amount(row["amount_raw"])

                        db = db_session_factory()
                        try:
                            _, created = upsert_tender(db, tender_data)
                            if created:
                                new_count += 1
                            else:
                                updated_count += 1
                        finally:
                            db.close()

                        await progress_queue.put({
                            "type": "upserted",
                            "idx": idx + 1,
                            "total": len(all_rows),
                            "created": created,
                            "title": tender_data.title[:60],
                        })

                    except Exception as exc:
                        logger.error("Failed detail page %s: %s", url, exc)
                        await progress_queue.put({
                            "type": "error",
                            "url": url,
                            "msg": str(exc),
                        })
                    finally:
                        await detail_page.close()

            await asyncio.gather(
                *(scrape_detail(row, i) for i, row in enumerate(all_rows))
            )
            await browser.close()

        summary.update({"tenders_new": new_count, "tenders_updated": updated_count})

        db = db_session_factory()
        update_scrape_run(
            db,
            run_id,
            status="done",
            finished_at=datetime.utcnow(),
            pages_scraped=pages_done,
            tenders_found=len(all_rows),
            tenders_new=new_count,
            tenders_updated=updated_count,
        )
        db.close()

    except Exception as exc:
        logger.exception("Scrape run %d failed: %s", run_id, exc)
        summary["error"] = str(exc)
        db = db_session_factory()
        update_scrape_run(
            db,
            run_id,
            status="failed",
            finished_at=datetime.utcnow(),
            error_message=str(exc),
        )
        db.close()

    await progress_queue.put({"type": "done", **summary})
    return summary


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------

async def _inspect():
    """Save the live search form HTML for selector inspection."""
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(SEARCH_FORM_URL, wait_until="networkidle", timeout=PAGE_TIMEOUT)
        html = await page.content()
        await browser.close()

    with open("gojep_inspect.html", "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"Saved {len(html):,} chars → gojep_inspect.html")
    print("Open this file in your browser, then use DevTools to find selectors.")


async def _test_scrape():
    """Scrape exactly 1 page and print results without saving to the database."""
    print("=== GOJEP Scraper test run (1 page, no DB write) ===")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context()
        page = await ctx.new_page()

        print("Solving CAPTCHA…")
        html = await _solve_and_search(page)
        rows, _, total, next_url = _parse_listing_page(html)

        print(f"Total notices on site: {total:,}")
        print(f"Rows on page 1: {len(rows)}")
        print(f"Next page URL: {next_url}")
        print()

        for i, row in enumerate(rows, 1):
            print(f"[{i}] {row['title'][:70]}")
            print(f"     Agency:   {row['agency']}")
            print(f"     Deadline: {row['deadline_raw']}")
            print(f"     Status:   {row['status']}")
            print(f"     URL:      {row['url']}")
            print()

        # Scrape first detail page
        if rows:
            print("Fetching detail for first tender…")
            detail_page = await ctx.new_page()
            await detail_page.goto(rows[0]["url"], wait_until="networkidle", timeout=PAGE_TIMEOUT)
            detail_html = await detail_page.content()
            tender = parse_detail_page(detail_html, rows[0]["url"])
            print(f"  Title:        {tender.title}")
            print(f"  Agency:       {tender.buyer_agency}")
            print(f"  Deadline:     {tender.deadline}")
            print(f"  Amount:       {tender.estimated_amount} {tender.currency}")
            print(f"  Category:     {tender.category}")
            print(f"  Reference:    {tender.reference_number}")
            print(f"  Description:  {(tender.description or '')[:120]}")
            await detail_page.close()

        await browser.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if "--inspect" in sys.argv:
        asyncio.run(_inspect())
    elif "--test" in sys.argv:
        asyncio.run(_test_scrape())
    else:
        print("Usage:")
        print("  python scraper.py --inspect   Save listing page HTML for inspection")
        print("  python scraper.py --test      Scrape 1 page and print results")
