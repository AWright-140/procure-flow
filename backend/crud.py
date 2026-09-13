"""Database CRUD helpers – keep all SQL logic here, away from route handlers."""

from datetime import datetime, date
from typing import Optional, List, Tuple

from sqlalchemy import func, extract, desc, or_
from sqlalchemy.orm import Session

from models import Tender, ScrapeRun
from schemas import TenderCreate, TenderUpdate, StatsOut, AgencyCount, MonthlyCount


# ---------------------------------------------------------------------------
# Tenders
# ---------------------------------------------------------------------------

def get_tender(db: Session, tender_id: int) -> Optional[Tender]:
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if tender:
        tender.is_new = False
        db.commit()
        db.refresh(tender)
    return tender


def get_tender_by_url(db: Session, url: str) -> Optional[Tender]:
    return db.query(Tender).filter(Tender.source_url == url).first()


def list_tenders(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    agency: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    amount_min: Optional[float] = None,
    amount_max: Optional[float] = None,
    deadline_from: Optional[str] = None,
    deadline_to: Optional[str] = None,
    sort_by: str = "last_updated_at",
    sort_dir: str = "desc",
    active_only: bool = True,
) -> Tuple[List[Tender], int]:
    q = db.query(Tender)

    if active_only:
        today = date.today()
        # Show tenders whose deadline is today or in the future,
        # OR where no deadline was recorded (unknown → include by default).
        q = q.filter(
            or_(Tender.deadline.is_(None), Tender.deadline >= today)
        )

    if search:
        term = f"%{search}%"
        q = q.filter(
            Tender.title.ilike(term)
            | Tender.description.ilike(term)
            | Tender.buyer_agency.ilike(term)
            | Tender.reference_number.ilike(term)
        )
    if agency:
        q = q.filter(Tender.buyer_agency.ilike(f"%{agency}%"))
    if status:
        q = q.filter(Tender.status.ilike(f"%{status}%"))
    if category:
        q = q.filter(Tender.category.ilike(f"%{category}%"))
    if amount_min is not None:
        q = q.filter(Tender.estimated_amount >= amount_min)
    if amount_max is not None:
        q = q.filter(Tender.estimated_amount <= amount_max)
    if deadline_from:
        q = q.filter(Tender.deadline >= deadline_from)
    if deadline_to:
        q = q.filter(Tender.deadline <= deadline_to)

    total = q.count()

    col = getattr(Tender, sort_by, Tender.last_updated_at)
    q = q.order_by(desc(col) if sort_dir == "desc" else col)
    q = q.offset((page - 1) * page_size).limit(page_size)

    return q.all(), total


def upsert_tender(db: Session, data: TenderCreate) -> Tuple[Tender, bool]:
    """
    Insert or update a tender by source_url.
    Returns (tender, created) where created=True means it was a new record.
    """
    existing = get_tender_by_url(db, data.source_url)
    if existing is None:
        tender = Tender(**data.model_dump())
        db.add(tender)
        db.commit()
        db.refresh(tender)
        return tender, True

    changed = False
    update_data = data.model_dump(exclude={"source_url"})
    for field, value in update_data.items():
        if value is not None and getattr(existing, field) != value:
            setattr(existing, field, value)
            changed = True

    if changed:
        existing.last_updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
    return existing, False


def delete_tender(db: Session, tender_id: int) -> bool:
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        return False
    db.delete(tender)
    db.commit()
    return True


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def get_stats(db: Session) -> StatsOut:
    total = db.query(Tender).count()
    open_count = db.query(Tender).filter(Tender.status.ilike("%open%")).count()
    closed_count = db.query(Tender).filter(Tender.status.ilike("%close%")).count()
    with_amounts = db.query(Tender).filter(Tender.estimated_amount.isnot(None)).count()

    amounts = db.query(
        func.avg(Tender.estimated_amount),
        func.min(Tender.estimated_amount),
        func.max(Tender.estimated_amount),
    ).filter(Tender.estimated_amount.isnot(None)).one()

    # Top agencies
    agency_rows = (
        db.query(Tender.buyer_agency, func.count(Tender.id).label("cnt"))
        .filter(Tender.buyer_agency.isnot(None))
        .group_by(Tender.buyer_agency)
        .order_by(desc("cnt"))
        .limit(10)
        .all()
    )
    by_agency = [AgencyCount(agency=r[0] or "Unknown", count=r[1]) for r in agency_rows]

    # Tenders per month (last 12 months)
    month_rows = (
        db.query(
            func.strftime("%Y-%m", Tender.first_scraped_at).label("month"),
            func.count(Tender.id).label("cnt"),
        )
        .group_by("month")
        .order_by("month")
        .limit(12)
        .all()
    )
    by_month = [MonthlyCount(month=r[0] or "", count=r[1]) for r in month_rows]

    last_run = (
        db.query(ScrapeRun)
        .filter(ScrapeRun.status == "done")
        .order_by(desc(ScrapeRun.finished_at))
        .first()
    )

    new_count = db.query(Tender).filter(Tender.is_new == True).count()

    return StatsOut(
        total_tenders=total,
        open_tenders=open_count,
        closed_tenders=closed_count,
        tenders_with_amounts=with_amounts,
        average_amount=amounts[0],
        min_amount=amounts[1],
        max_amount=amounts[2],
        by_agency=by_agency,
        by_month=by_month,
        last_scraped=last_run.finished_at if last_run else None,
        new_since_last_visit=new_count,
    )


# ---------------------------------------------------------------------------
# Scrape runs
# ---------------------------------------------------------------------------

def create_scrape_run(db: Session, triggered_by: str = "manual") -> ScrapeRun:
    run = ScrapeRun(triggered_by=triggered_by)
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def update_scrape_run(db: Session, run_id: int, **kwargs) -> ScrapeRun:
    run = db.query(ScrapeRun).filter(ScrapeRun.id == run_id).first()
    if not run:
        raise ValueError(f"ScrapeRun {run_id} not found")
    for k, v in kwargs.items():
        setattr(run, k, v)
    db.commit()
    db.refresh(run)
    return run


def get_scrape_runs(db: Session, limit: int = 20) -> List[ScrapeRun]:
    return (
        db.query(ScrapeRun)
        .order_by(desc(ScrapeRun.started_at))
        .limit(limit)
        .all()
    )


def get_distinct_agencies(db: Session) -> List[str]:
    rows = (
        db.query(Tender.buyer_agency)
        .filter(Tender.buyer_agency.isnot(None))
        .distinct()
        .order_by(Tender.buyer_agency)
        .all()
    )
    return [r[0] for r in rows if r[0]]


def get_distinct_categories(db: Session) -> List[str]:
    rows = (
        db.query(Tender.category)
        .filter(Tender.category.isnot(None))
        .distinct()
        .order_by(Tender.category)
        .all()
    )
    return [r[0] for r in rows if r[0]]
