"""
reporting/pdf_generator.py
==========================
Generates a professional PDF assessment report using ReportLab.

Output: A multi-page PDF with:
  - Cover page
  - Executive summary
  - Dimension radar chart (as table — ReportLab doesn't do SVG natively)
  - Dimension-by-dimension analysis
  - Use case candidates table
  - Phased roadmap
"""

import os
from pathlib import Path
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY

from models import AssessmentReport, Dimension
from config import settings


# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------

BRAND_DARK   = colors.HexColor("#1e293b")
BRAND_BLUE   = colors.HexColor("#3b82f6")
BRAND_LIGHT  = colors.HexColor("#f1f5f9")
BRAND_GREEN  = colors.HexColor("#22c55e")
BRAND_ORANGE = colors.HexColor("#f97316")
BRAND_RED    = colors.HexColor("#ef4444")
BRAND_YELLOW = colors.HexColor("#eab308")

MATURITY_COLORS = {
    "red":    BRAND_RED,
    "orange": BRAND_ORANGE,
    "yellow": BRAND_YELLOW,
    "green":  BRAND_GREEN,
    "blue":   BRAND_BLUE,
}

SCORE_BAR_BG = colors.HexColor("#e2e8f0")


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

def build_styles():
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle("title", parent=base["Title"],
            fontSize=28, textColor=BRAND_DARK, spaceAfter=8, leading=34),
        "subtitle": ParagraphStyle("subtitle", parent=base["Normal"],
            fontSize=13, textColor=colors.HexColor("#64748b"), spaceAfter=4),
        "h1": ParagraphStyle("h1", parent=base["Heading1"],
            fontSize=16, textColor=BRAND_DARK, spaceBefore=16, spaceAfter=8,
            borderPadding=(0, 0, 4, 0)),
        "h2": ParagraphStyle("h2", parent=base["Heading2"],
            fontSize=13, textColor=BRAND_BLUE, spaceBefore=12, spaceAfter=6),
        "body": ParagraphStyle("body", parent=base["Normal"],
            fontSize=10, textColor=BRAND_DARK, leading=15, spaceAfter=6,
            alignment=TA_JUSTIFY),
        "bullet": ParagraphStyle("bullet", parent=base["Normal"],
            fontSize=10, textColor=BRAND_DARK, leading=14,
            leftIndent=12, spaceAfter=4),
        "caption": ParagraphStyle("caption", parent=base["Normal"],
            fontSize=8, textColor=colors.HexColor("#94a3b8"), spaceAfter=4),
        "score_big": ParagraphStyle("score_big", parent=base["Normal"],
            fontSize=42, textColor=BRAND_BLUE, alignment=TA_CENTER, leading=50),
        "center": ParagraphStyle("center", parent=base["Normal"],
            fontSize=10, alignment=TA_CENTER, textColor=BRAND_DARK),
    }
    return styles


# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------

def score_bar_table(score: float, color: str, width: float = 10 * cm):
    """Renders a visual score bar as a table."""
    filled = score / 10.0
    bar_color = MATURITY_COLORS.get(color, BRAND_BLUE)
    data = [[""]]
    t = Table(data, colWidths=[width * filled], rowHeights=[10])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bar_color),
        ("LINEABOVE", (0, 0), (-1, -1), 0, colors.white),
    ]))
    # Wrap in outer table with grey background
    outer = Table([[t, ""]], colWidths=[width * filled, width * (1 - filled)], rowHeights=[10])
    outer.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), bar_color),
        ("BACKGROUND", (1, 0), (1, 0), SCORE_BAR_BG),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return outer


def bullet_list(items: list[str], styles, prefix="•") -> list:
    """Returns a list of Paragraph flowables for a bullet list."""
    return [
        Paragraph(f"{prefix} {item}", styles["bullet"])
        for item in items if item
    ]


# ---------------------------------------------------------------------------
# Page sections
# ---------------------------------------------------------------------------

def cover_page(report: AssessmentReport, styles) -> list:
    elements = []
    elements.append(Spacer(1, 3 * cm))
    elements.append(Paragraph("AI Readiness Assessment", styles["title"]))
    elements.append(Paragraph(f"<b>{report.organisation_name}</b>", styles["h1"]))
    elements.append(Spacer(1, 0.5 * cm))
    elements.append(HRFlowable(width="100%", thickness=2, color=BRAND_BLUE))
    elements.append(Spacer(1, 1 * cm))

    # Score callout
    score_color = MATURITY_COLORS.get(report.overall_maturity_color, BRAND_BLUE)
    score_data = [[
        Paragraph(f"{report.overall_score}/10", styles["score_big"]),
        Paragraph(report.overall_maturity, ParagraphStyle(
            "mat", fontSize=20, textColor=score_color,
            alignment=TA_CENTER, leading=24,
        )),
    ]]
    score_table = Table(score_data, colWidths=[6 * cm, 6 * cm], rowHeights=[5 * cm])
    score_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (-1, -1), BRAND_LIGHT),
        ("ROUNDEDCORNERS", [8]),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
    ]))
    elements.append(score_table)
    elements.append(Spacer(1, 1 * cm))

    meta_data = [
        ["Report ID", report.report_id],
        ["Generated", datetime.fromisoformat(report.generated_at).strftime("%d %B %Y, %H:%M UTC")],
        ["Documents Analysed", str(len(report.documents_analysed))],
        ["Pages Reviewed", str(report.total_pages_analysed)],
    ]
    meta_table = Table(meta_data, colWidths=[5 * cm, 10 * cm])
    meta_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#64748b")),
        ("TEXTCOLOR", (1, 0), (1, -1), BRAND_DARK),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(meta_table)
    elements.append(PageBreak())
    return elements


def exec_summary_section(report: AssessmentReport, styles) -> list:
    elements = [Paragraph("Executive Summary", styles["h1"]),
                HRFlowable(width="100%", thickness=1, color=BRAND_LIGHT),
                Spacer(1, 0.3 * cm),
                Paragraph(report.executive_summary, styles["body"]),
                Spacer(1, 0.5 * cm)]

    # Quick wins + Blockers side by side
    qw = [Paragraph("⚡ Quick Wins (< 90 days)", styles["h2"])] + bullet_list(report.quick_wins, styles, "✓")
    cb = [Paragraph("🚧 Critical Blockers", styles["h2"])] + bullet_list(report.critical_blockers, styles, "✗")

    two_col = Table([[qw, cb]], colWidths=[9 * cm, 9 * cm])
    two_col.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(two_col)
    elements.append(PageBreak())
    return elements


def dimensions_summary_section(report: AssessmentReport, styles) -> list:
    elements = [Paragraph("Readiness Assessment — Dimension Scores", styles["h1"]),
                HRFlowable(width="100%", thickness=1, color=BRAND_LIGHT),
                Spacer(1, 0.4 * cm)]

    for ds in report.dimension_scores:
        # Dimension header row
        elements.append(Paragraph(f"<b>{ds.dimension.value}</b>  —  {ds.score}/10  ({ds.maturity_level})", styles["h2"]))
        elements.append(score_bar_table(ds.score, ds.maturity_color))
        elements.append(Spacer(1, 0.3 * cm))

        detail_data = [
            ["Strengths", "Gaps"],
            [
                "\n".join(f"• {s}" for s in ds.key_strengths) or "—",
                "\n".join(f"• {g}" for g in ds.key_gaps) or "—",
            ],
        ]
        detail_table = Table(detail_data, colWidths=[9 * cm, 9 * cm])
        detail_table.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_LIGHT),
            ("TEXTCOLOR", (0, 0), (0, 0), BRAND_GREEN),
            ("TEXTCOLOR", (1, 0), (1, 0), BRAND_RED),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        elements.append(detail_table)

        if ds.recommendations:
            elements.append(Spacer(1, 0.2 * cm))
            elements.append(Paragraph("<i>Recommendations:</i>", styles["caption"]))
            elements.extend(bullet_list(ds.recommendations, styles, "→"))

        elements.append(Spacer(1, 0.5 * cm))

    elements.append(PageBreak())
    return elements


def use_cases_section(report: AssessmentReport, styles) -> list:
    elements = [Paragraph("AI Use Case Candidates", styles["h1"]),
                HRFlowable(width="100%", thickness=1, color=BRAND_LIGHT),
                Spacer(1, 0.4 * cm)]

    headers = ["#", "Use Case", "AI Approach", "Complexity", "ROI Impact"]
    rows = [headers]
    for uc in sorted(report.use_case_candidates, key=lambda x: x.priority_rank):
        rows.append([
            str(uc.priority_rank),
            f"{uc.title}\n{uc.description[:120]}...",
            uc.ai_approach,
            uc.estimated_complexity,
            uc.estimated_roi_impact,
        ])

    complexity_colors = {"Low": BRAND_GREEN, "Medium": BRAND_ORANGE, "High": BRAND_RED}

    t = Table(rows, colWidths=[1*cm, 8*cm, 3.5*cm, 2.5*cm, 2.5*cm])
    style_cmds = [
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BRAND_LIGHT]),
    ]
    t.setStyle(TableStyle(style_cmds))
    elements.append(t)
    elements.append(PageBreak())
    return elements


def roadmap_section(report: AssessmentReport, styles) -> list:
    elements = [Paragraph("AI Adoption Roadmap", styles["h1"]),
                HRFlowable(width="100%", thickness=1, color=BRAND_LIGHT),
                Spacer(1, 0.4 * cm)]

    phase_colors = [BRAND_BLUE, BRAND_GREEN, colors.HexColor("#8b5cf6")]

    for phase in report.roadmap_phases:
        color = phase_colors[(phase.phase - 1) % len(phase_colors)]
        elements.append(Paragraph(
            f"<b>Phase {phase.phase}: {phase.title}</b>  ·  {phase.timeline}",
            ParagraphStyle("ph", fontSize=12, textColor=color, spaceBefore=8, spaceAfter=4),
        ))

        phase_data = [
            ["Key Initiatives", "Success Metrics"],
            [
                "\n".join(f"• {i}" for i in phase.key_initiatives),
                "\n".join(f"• {m}" for m in phase.success_metrics),
            ],
        ]
        pt = Table(phase_data, colWidths=[10 * cm, 8 * cm])
        pt.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_LIGHT),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        elements.append(pt)
        elements.append(Spacer(1, 0.4 * cm))

    return elements


# ---------------------------------------------------------------------------
# Main export function
# ---------------------------------------------------------------------------

def generate_pdf_report(report: AssessmentReport) -> str:
    """
    Generates a PDF report and saves it to the reports directory.
    Returns the file path.
    """
    os.makedirs(settings.reports_dir, exist_ok=True)
    filename = f"{settings.reports_dir}/{report.report_id}_{report.organisation_name.replace(' ', '_')}.pdf"
    styles = build_styles()

    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    elements = []
    elements += cover_page(report, styles)
    elements += exec_summary_section(report, styles)
    elements += dimensions_summary_section(report, styles)
    elements += use_cases_section(report, styles)
    elements += roadmap_section(report, styles)

    doc.build(elements)
    return filename
