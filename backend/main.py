"""
FastAPI backend for the GOJEP Procurement Dashboard.

Endpoints:
  GET  /api/tenders            – paginated list with filters
  GET  /api/tenders/{id}       – single tender detail
  DELETE /api/tenders/{id}     – remove a tender
  POST /api/scrape             – start a scrape run (returns SSE stream)
  GET  /api/scrape/runs        – history of scrape runs
  GET  /api/stats              – dashboard statistics
  GET  /api/filters/agencies   – distinct agencies for filter dropdown
  GET  /api/filters/categories – distinct categories
  GET  /api/export/csv         – CSV export with filters
  GET  /api/export/excel       – Excel export with filters
  GET  /api/tenders/{id}/pdf   – PDF for one tender
  POST /api/export/pdf/batch   – PDF for multiple tenders
"""

import asyncio
import csv
import io
import json
import logging
import logging.config
import math
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import config as cfg
import crud
from database import SessionLocal, create_tables, get_db
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pdf_generator import generate_batch_pdf, generate_tender_pdf
from schemas import (
    BatchPDFRequest,
    ScrapeRunOut,
    StatsOut,
    TenderListOut,
    TenderOut,
)
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, cfg.LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s – %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(cfg.LOG_FILE),
    ],
)
logger = logging.getLogger("api")

# ---------------------------------------------------------------------------
# Shared scrape state (single-process; good enough for standalone tool)
# ---------------------------------------------------------------------------
_scrape_task: Optional[asyncio.Task] = None
# Each connected SSE client registers a queue here; the scraper broadcasts to all.
_sse_clients: list[asyncio.Queue] = []


async def _broadcast(msg: dict):
    """Put a progress message into every connected SSE client queue."""
    for q in list(_sse_clients):
        await q.put(msg)


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    logger.info("Database tables ready.")

    # Optional background scheduler
    if cfg.ENABLE_SCHEDULER:
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from apscheduler.triggers.cron import CronTrigger

            scheduler = AsyncIOScheduler()
            parts = cfg.SCRAPE_CRON.split()
            trigger = CronTrigger(
                minute=parts[1] if len(parts) > 1 else "*",
                hour=parts[2] if len(parts) > 2 else "*",
                day=parts[3] if len(parts) > 3 else "*",
                month=parts[4] if len(parts) > 4 else "*",
                day_of_week=parts[5] if len(parts) > 5 else "*",
            )
            scheduler.add_job(_scheduled_scrape, trigger)
            scheduler.start()
            logger.info("Scheduler started with cron: %s", cfg.SCRAPE_CRON)
        except ImportError:
            logger.warning("apscheduler not installed – scheduled scraping disabled.")

    yield


app = FastAPI(
    title="GOJEP Procurement Dashboard API",
    description="Scrape and query Jamaican government procurement notices.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _scheduled_scrape():
    """Called by APScheduler."""
    await _start_scrape(triggered_by="scheduler")


async def _start_scrape(triggered_by: str = "manual"):
    global _scrape_task

    if _scrape_task and not _scrape_task.done():
        logger.warning("Scrape already running – ignoring duplicate request.")
        return

    from scraper import run_scrape

    # Wrap _broadcast so the scraper gets a plain asyncio.Queue-like interface
    # but messages actually fan out to all connected SSE clients.
    broadcast_queue: asyncio.Queue = asyncio.Queue()

    async def _fan_out():
        """Forward every item from broadcast_queue to all SSE client queues."""
        while True:
            msg = await broadcast_queue.get()
            await _broadcast(msg)
            if msg.get("type") == "done":
                break

    async def _run():
        fan_task = asyncio.create_task(_fan_out())
        try:
            await run_scrape(broadcast_queue, SessionLocal, triggered_by=triggered_by)
        finally:
            await fan_task

    _scrape_task = asyncio.create_task(_run())


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/api/tenders", response_model=TenderListOut)
def list_tenders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    agency: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    amount_min: Optional[float] = Query(None),
    amount_max: Optional[float] = Query(None),
    deadline_from: Optional[str] = Query(None),
    deadline_to: Optional[str] = Query(None),
    sort_by: str = Query("last_updated_at"),
    sort_dir: str = Query("desc"),
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
):
    items, total = crud.list_tenders(
        db,
        page=page,
        page_size=page_size,
        search=search,
        agency=agency,
        status=status,
        category=category,
        amount_min=amount_min,
        amount_max=amount_max,
        deadline_from=deadline_from,
        deadline_to=deadline_to,
        sort_by=sort_by,
        sort_dir=sort_dir,
        active_only=active_only,
    )
    return TenderListOut(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, math.ceil(total / page_size)),
    )


@app.get("/api/tenders/{tender_id}", response_model=TenderOut)
def get_tender(tender_id: int, db: Session = Depends(get_db)):
    tender = crud.get_tender(db, tender_id)
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    return tender


@app.delete("/api/tenders/{tender_id}")
def delete_tender(tender_id: int, db: Session = Depends(get_db)):
    if not crud.delete_tender(db, tender_id):
        raise HTTPException(status_code=404, detail="Tender not found")
    return {"ok": True}


@app.get("/api/stats", response_model=StatsOut)
def get_stats(db: Session = Depends(get_db)):
    return crud.get_stats(db)


@app.get("/api/filters/agencies")
def get_agencies(db: Session = Depends(get_db)):
    return crud.get_distinct_agencies(db)


@app.get("/api/filters/categories")
def get_categories(db: Session = Depends(get_db)):
    return crud.get_distinct_categories(db)


@app.get("/api/scrape/runs", response_model=list[ScrapeRunOut])
def get_scrape_runs(
    limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)
):
    return crud.get_scrape_runs(db, limit=limit)


# ---------------------------------------------------------------------------
# Scrape trigger + SSE progress stream
# ---------------------------------------------------------------------------


@app.post("/api/scrape")
async def trigger_scrape():
    global _scrape_task
    if _scrape_task and not _scrape_task.done():
        return {"status": "already_running"}
    await _start_scrape(triggered_by="manual")
    return {"status": "started"}


@app.get("/api/scrape/stream")
async def scrape_stream(request: Request):
    """
    Server-Sent Events stream.  Every connected browser tab gets a queue that
    receives broadcast messages from the running scraper.
    """
    queue: asyncio.Queue = asyncio.Queue()
    _sse_clients.append(queue)

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(msg)}\n\n"
                    if msg.get("type") == "done":
                        break
                except asyncio.TimeoutError:
                    yield 'data: {"type": "heartbeat"}\n\n'
        finally:
            if queue in _sse_clients:
                _sse_clients.remove(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Export endpoints
# ---------------------------------------------------------------------------


def _get_all_matching(db, **filters) -> list:
    items, _ = crud.list_tenders(db, page=1, page_size=10_000, **filters)
    return items


@app.get("/api/export/csv")
def export_csv(
    search: Optional[str] = Query(None),
    agency: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    amount_min: Optional[float] = Query(None),
    amount_max: Optional[float] = Query(None),
    deadline_from: Optional[str] = Query(None),
    deadline_to: Optional[str] = Query(None),
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
):
    tenders = _get_all_matching(
        db,
        search=search,
        agency=agency,
        status=status,
        category=category,
        amount_min=amount_min,
        amount_max=amount_max,
        deadline_from=deadline_from,
        deadline_to=deadline_to,
        active_only=active_only,
    )

    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=[
            "id",
            "reference_number",
            "title",
            "buyer_agency",
            "category",
            "status",
            "deadline",
            "estimated_amount",
            "currency",
            "first_scraped_at",
            "last_updated_at",
            "source_url",
        ],
    )
    writer.writeheader()
    for t in tenders:
        writer.writerow(
            {
                "id": t.id,
                "reference_number": t.reference_number,
                "title": t.title,
                "buyer_agency": t.buyer_agency,
                "category": t.category,
                "status": t.status,
                "deadline": t.deadline,
                "estimated_amount": t.estimated_amount,
                "currency": t.currency,
                "first_scraped_at": t.first_scraped_at,
                "last_updated_at": t.last_updated_at,
                "source_url": t.source_url,
            }
        )

    filename = f"gojep_tenders_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/export/excel")
def export_excel(
    search: Optional[str] = Query(None),
    agency: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    amount_min: Optional[float] = Query(None),
    amount_max: Optional[float] = Query(None),
    deadline_from: Optional[str] = Query(None),
    deadline_to: Optional[str] = Query(None),
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
):
    try:
        import openpyxl
        from openpyxl.styles import Alignment, Font, PatternFill
    except ImportError:
        raise HTTPException(
            status_code=501, detail="openpyxl not installed. Run: pip install openpyxl"
        )

    tenders = _get_all_matching(
        db,
        search=search,
        agency=agency,
        status=status,
        category=category,
        amount_min=amount_min,
        amount_max=amount_max,
        deadline_from=deadline_from,
        deadline_to=deadline_to,
        active_only=active_only,
    )

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "GOJEP Tenders"

    headers = [
        "ID",
        "Reference",
        "Title",
        "Agency",
        "Category",
        "Status",
        "Deadline",
        "Amount",
        "Currency",
        "First Scraped",
        "Last Updated",
        "URL",
    ]
    header_fill = PatternFill(fill_type="solid", fgColor="007A33")
    header_font = Font(bold=True, color="FFFFFF")
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    for row_num, t in enumerate(tenders, 2):
        ws.append(
            [
                t.id,
                t.reference_number,
                t.title,
                t.buyer_agency,
                t.category,
                t.status,
                str(t.deadline) if t.deadline else None,
                t.estimated_amount,
                t.currency,
                str(t.first_scraped_at),
                str(t.last_updated_at),
                t.source_url,
            ]
        )
        if row_num % 2 == 0:
            for col in range(1, len(headers) + 1):
                ws.cell(row=row_num, column=col).fill = PatternFill(
                    fill_type="solid", fgColor="F5F5F5"
                )

    # Auto column widths
    for col in ws.columns:
        max_len = max((len(str(cell.value or "")) for cell in col), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 60)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f"gojep_tenders_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# PDF endpoints
# ---------------------------------------------------------------------------


@app.get("/api/tenders/{tender_id}/pdf")
def tender_pdf(tender_id: int, db: Session = Depends(get_db)):
    tender = crud.get_tender(db, tender_id)
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    pdf_bytes = generate_tender_pdf(tender)
    safe_title = "".join(c if c.isalnum() else "_" for c in tender.title[:40])
    filename = f"tender_{tender_id}_{safe_title}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/export/pdf/batch")
def batch_pdf(req: BatchPDFRequest, db: Session = Depends(get_db)):
    tenders = [crud.get_tender(db, tid) for tid in req.tender_ids]
    tenders = [t for t in tenders if t is not None]
    if not tenders:
        raise HTTPException(status_code=404, detail="No valid tenders found")
    pdf_bytes = generate_batch_pdf(tenders)
    filename = f"gojep_batch_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Dev server entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
