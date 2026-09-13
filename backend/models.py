from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean,
    DateTime, Date, UniqueConstraint, Index,
)
from database import Base


class Tender(Base):
    __tablename__ = "tenders"

    id = Column(Integer, primary_key=True, index=True)
    reference_number = Column(String(128), nullable=True)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    buyer_agency = Column(String(512), nullable=True)
    deadline = Column(Date, nullable=True)
    estimated_amount = Column(Float, nullable=True)
    currency = Column(String(8), default="JMD")
    status = Column(String(64), nullable=True)
    category = Column(String(256), nullable=True)
    instructions = Column(Text, nullable=True)
    contact_details = Column(Text, nullable=True)
    source_url = Column(Text, nullable=False)
    raw_html = Column(Text, nullable=True)  # stored for re-parsing
    first_scraped_at = Column(DateTime, default=datetime.utcnow)
    last_updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_new = Column(Boolean, default=True)  # cleared after user views it

    __table_args__ = (
        UniqueConstraint("source_url", name="uq_tender_source_url"),
        Index("ix_tender_deadline", "deadline"),
        Index("ix_tender_agency", "buyer_agency"),
        Index("ix_tender_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Tender id={self.id} title={self.title[:40]!r}>"


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id = Column(Integer, primary_key=True, index=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    status = Column(String(32), default="running")  # running | done | failed
    pages_scraped = Column(Integer, default=0)
    tenders_found = Column(Integer, default=0)
    tenders_new = Column(Integer, default=0)
    tenders_updated = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    triggered_by = Column(String(32), default="manual")  # manual | scheduler
