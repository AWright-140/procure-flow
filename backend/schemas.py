from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Tender
# ---------------------------------------------------------------------------

class TenderBase(BaseModel):
    title: str
    description: Optional[str] = None
    buyer_agency: Optional[str] = None
    deadline: Optional[date] = None
    estimated_amount: Optional[float] = None
    currency: str = "JMD"
    status: Optional[str] = None
    category: Optional[str] = None
    instructions: Optional[str] = None
    contact_details: Optional[str] = None
    source_url: str
    reference_number: Optional[str] = None


class TenderCreate(TenderBase):
    raw_html: Optional[str] = None


class TenderUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    buyer_agency: Optional[str] = None
    deadline: Optional[date] = None
    estimated_amount: Optional[float] = None
    currency: Optional[str] = None
    status: Optional[str] = None
    category: Optional[str] = None
    instructions: Optional[str] = None
    contact_details: Optional[str] = None
    raw_html: Optional[str] = None


class TenderOut(TenderBase):
    id: int
    first_scraped_at: datetime
    last_updated_at: datetime
    is_new: bool

    model_config = {"from_attributes": True}


class TenderListOut(BaseModel):
    items: List[TenderOut]
    total: int
    page: int
    page_size: int
    total_pages: int


# ---------------------------------------------------------------------------
# Scrape Run
# ---------------------------------------------------------------------------

class ScrapeRunOut(BaseModel):
    id: int
    started_at: datetime
    finished_at: Optional[datetime] = None
    status: str
    pages_scraped: int
    tenders_found: int
    tenders_new: int
    tenders_updated: int
    error_message: Optional[str] = None
    triggered_by: str

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class AgencyCount(BaseModel):
    agency: str
    count: int


class MonthlyCount(BaseModel):
    month: str
    count: int


class StatsOut(BaseModel):
    total_tenders: int
    open_tenders: int
    closed_tenders: int
    tenders_with_amounts: int
    average_amount: Optional[float]
    min_amount: Optional[float]
    max_amount: Optional[float]
    by_agency: List[AgencyCount]
    by_month: List[MonthlyCount]
    last_scraped: Optional[datetime]
    new_since_last_visit: int


# ---------------------------------------------------------------------------
# Batch PDF export
# ---------------------------------------------------------------------------

class BatchPDFRequest(BaseModel):
    tender_ids: List[int] = Field(..., min_length=1)
