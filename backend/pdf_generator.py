"""
PDF generation for individual tenders and batch exports.
Uses ReportLab for reliable cross-platform PDF output.
"""

import io
from datetime import date, datetime
from typing import List, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    PageTemplate,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from models import Tender

# ---------------------------------------------------------------------------
# Color palette (Jamaican government palette)
# ---------------------------------------------------------------------------
GOV_GREEN = colors.HexColor("#007A33")
GOV_GOLD = colors.HexColor("#FFC72C")
GOV_BLACK = colors.HexColor("#1A1A1A")
LIGHT_GRAY = colors.HexColor("#F5F5F5")
MID_GRAY = colors.HexColor("#CCCCCC")


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

def _build_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        "GovTitle",
        parent=styles["Title"],
        fontSize=18,
        textColor=GOV_GREEN,
        spaceAfter=6,
        alignment=TA_CENTER,
    ))

    styles.add(ParagraphStyle(
        "SectionHeader",
        parent=styles["Heading2"],
        fontSize=11,
        textColor=GOV_GREEN,
        spaceBefore=10,
        spaceAfter=4,
        borderPad=2,
    ))

    styles.add(ParagraphStyle(
        "FieldLabel",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.gray,
        spaceAfter=1,
    ))

    styles.add(ParagraphStyle(
        "FieldValue",
        parent=styles["Normal"],
        fontSize=10,
        textColor=GOV_BLACK,
        spaceAfter=6,
    ))

    styles.add(ParagraphStyle(
        "BodyBlock",
        parent=styles["Normal"],
        fontSize=9,
        textColor=GOV_BLACK,
        leading=14,
        spaceAfter=8,
    ))

    styles.add(ParagraphStyle(
        "Footer",
        parent=styles["Normal"],
        fontSize=7,
        textColor=colors.gray,
        alignment=TA_CENTER,
    ))

    return styles


# ---------------------------------------------------------------------------
# Header / Footer callbacks
# ---------------------------------------------------------------------------

def _header_footer(canvas, doc):
    canvas.saveState()
    width, height = A4

    # Header bar
    canvas.setFillColor(GOV_GREEN)
    canvas.rect(0, height - 2 * cm, width, 1.6 * cm, fill=1, stroke=0)

    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 13)
    canvas.drawCentredString(width / 2, height - 1.2 * cm, "Government of Jamaica – GOJEP Procurement Notice")

    # Gold rule
    canvas.setFillColor(GOV_GOLD)
    canvas.rect(0, height - 2 * cm - 4, width, 4, fill=1, stroke=0)

    # Footer
    canvas.setFillColor(colors.gray)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(2 * cm, 1 * cm, f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC")
    canvas.drawRightString(width - 2 * cm, 1 * cm, f"Page {doc.page}")
    canvas.restoreState()


# ---------------------------------------------------------------------------
# Single-tender PDF
# ---------------------------------------------------------------------------

def _field(label: str, value: Optional[str], styles) -> List:
    if not value or str(value).strip() == "None":
        return []
    return [
        Paragraph(label.upper(), styles["FieldLabel"]),
        Paragraph(str(value).replace("\n", "<br/>"), styles["FieldValue"]),
    ]


def generate_tender_pdf(tender: Tender) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=3 * cm,
        bottomMargin=2.5 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
    )
    styles = _build_styles()
    story = []

    # Title
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(tender.title, styles["GovTitle"]))
    story.append(HRFlowable(width="100%", thickness=2, color=GOV_GOLD, spaceAfter=10))

    # Key info table
    key_data = [
        ["Reference", tender.reference_number or "N/A", "Status", tender.status or "N/A"],
        ["Agency", tender.buyer_agency or "N/A", "Category", tender.category or "N/A"],
        [
            "Deadline",
            str(tender.deadline) if tender.deadline else "N/A",
            "Estimated Amount",
            (
                f"{tender.currency} {tender.estimated_amount:,.2f}"
                if tender.estimated_amount else "N/A"
            ),
        ],
    ]
    tbl = Table(key_data, colWidths=[3.5 * cm, 7 * cm, 3.5 * cm, 4.5 * cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GRAY),
        ("BACKGROUND", (0, 0), (0, -1), GOV_GREEN),
        ("BACKGROUND", (2, 0), (2, -1), GOV_GREEN),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.white),
        ("TEXTCOLOR", (2, 0), (2, -1), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, MID_GRAY),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [LIGHT_GRAY, colors.white]),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 0.5 * cm))

    # Description
    if tender.description:
        story.append(Paragraph("Description", styles["SectionHeader"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=MID_GRAY, spaceAfter=4))
        story.append(Paragraph(
            tender.description.replace("\n", "<br/>"),
            styles["BodyBlock"],
        ))

    # Instructions
    if tender.instructions:
        story.append(Paragraph("Submission Instructions", styles["SectionHeader"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=MID_GRAY, spaceAfter=4))
        story.append(Paragraph(
            tender.instructions.replace("\n", "<br/>"),
            styles["BodyBlock"],
        ))

    # Contact
    if tender.contact_details:
        story.append(Paragraph("Contact Information", styles["SectionHeader"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=MID_GRAY, spaceAfter=4))
        story.append(Paragraph(
            tender.contact_details.replace("\n", "<br/>"),
            styles["BodyBlock"],
        ))

    # Source
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(
        f'<font color="gray" size="8">Source: <a href="{tender.source_url}">{tender.source_url}</a></font>',
        styles["FieldValue"],
    ))

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Batch PDF (multiple tenders → single PDF document)
# ---------------------------------------------------------------------------

def generate_batch_pdf(tenders: List[Tender]) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=3 * cm,
        bottomMargin=2.5 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
    )
    styles = _build_styles()
    story = []

    # Cover page title
    story.append(Spacer(1, 2 * cm))
    story.append(Paragraph("GOJEP Procurement Notices", styles["GovTitle"]))
    story.append(Paragraph(
        f"Batch Export – {len(tenders)} Notice(s)",
        ParagraphStyle("Sub", parent=styles["Normal"], alignment=TA_CENTER, fontSize=11),
    ))
    story.append(Paragraph(
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC",
        ParagraphStyle("Sub2", parent=styles["Normal"], alignment=TA_CENTER, fontSize=9, textColor=colors.gray),
    ))
    story.append(Spacer(1, 1 * cm))
    story.append(HRFlowable(width="100%", thickness=2, color=GOV_GOLD))
    story.append(Spacer(1, 0.5 * cm))

    for i, tender in enumerate(tenders, 1):
        if i > 1:
            story.append(HRFlowable(width="100%", thickness=1, color=GOV_GREEN, spaceBefore=16, spaceAfter=16))

        story.append(Paragraph(f"{i}. {tender.title}", styles["SectionHeader"]))

        rows = [
            ["Agency", tender.buyer_agency or "N/A"],
            ["Deadline", str(tender.deadline) if tender.deadline else "N/A"],
            ["Amount", f"{tender.currency} {tender.estimated_amount:,.2f}" if tender.estimated_amount else "N/A"],
            ["Status", tender.status or "N/A"],
            ["Reference", tender.reference_number or "N/A"],
        ]
        tbl = Table(rows, colWidths=[4 * cm, 14 * cm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), GOV_GREEN),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.white),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, MID_GRAY),
            ("ROWBACKGROUNDS", (1, 0), (1, -1), [LIGHT_GRAY, colors.white]),
            ("PADDING", (0, 0), (-1, -1), 5),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(tbl)

        if tender.description:
            story.append(Spacer(1, 4))
            desc = tender.description[:800] + ("…" if len(tender.description) > 800 else "")
            story.append(Paragraph(desc.replace("\n", " "), styles["BodyBlock"]))

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buf.getvalue()
