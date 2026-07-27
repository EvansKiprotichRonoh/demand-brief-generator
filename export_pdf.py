"""
export_pdf.py
-------------
Render a one-page PDF of the weekly demand / decision brief — the kind you could
drop straight into an S&OP deck or attach to an email.

Usage (CLI):   python export_pdf.py sample_demand.csv brief.pdf
Programmatic:  build_pdf(facts, brief) -> bytes
"""
from __future__ import annotations

import io
from datetime import date
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

INK = colors.HexColor("#0f172a")      # slate-900
MUTED = colors.HexColor("#64748b")    # slate-500
ACCENT = colors.HexColor("#2563eb")   # blue-600
GOOD = colors.HexColor("#059669")     # emerald-600
BAD = colors.HexColor("#dc2626")      # red-600
CARD = colors.HexColor("#f1f5f9")     # slate-100
FLAG_BG = colors.HexColor("#fef2f2")  # red-50


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", parent=base["Title"], fontSize=20,
                                textColor=INK, spaceAfter=2, alignment=TA_LEFT),
        "sub": ParagraphStyle("sub", parent=base["Normal"], fontSize=8.5,
                              textColor=MUTED, spaceAfter=6),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontSize=11,
                             textColor=ACCENT, spaceBefore=8, spaceAfter=4),
        "tldr": ParagraphStyle("tldr", parent=base["Normal"], fontSize=11,
                               textColor=INK, leading=15),
        "body": ParagraphStyle("body", parent=base["Normal"], fontSize=10,
                               textColor=INK, leading=14, spaceAfter=3),
        "kpi_val": ParagraphStyle("kpi_val", parent=base["Normal"], fontSize=16,
                                  textColor=INK, alignment=1, leading=18),
        "kpi_lbl": ParagraphStyle("kpi_lbl", parent=base["Normal"], fontSize=7.5,
                                  textColor=MUTED, alignment=1),
        "flag": ParagraphStyle("flag", parent=base["Normal"], fontSize=9,
                               textColor=BAD, leading=13),
        "foot": ParagraphStyle("foot", parent=base["Normal"], fontSize=7.5,
                               textColor=MUTED),
    }


def _kpi_cards(dm: dict[str, Any], s: dict[str, ParagraphStyle]) -> Table | None:
    cards = []
    if dm.get("accuracy_pct") is not None:
        cards.append(("FORECAST ACCURACY", f"{dm['accuracy_pct']:.0f}%"))
    if dm.get("bias_pct") is not None:
        cards.append(("FORECAST BIAS", f"{dm['bias_pct']:+.0f}%"))
    if dm.get("days_of_cover") is not None:
        cards.append(("DAYS OF COVER", f"{dm['days_of_cover']:.1f}"))
    if dm.get("promo_uplift_pct") is not None:
        cards.append(("PROMO UPLIFT", f"{dm['promo_uplift_pct']:.0f}%"))
    if not cards:
        return None

    cells = [[Paragraph(v, s["kpi_val"]), ] for _, v in cards]
    row_val = [Paragraph(v, s["kpi_val"]) for _, v in cards]
    row_lbl = [Paragraph(lbl, s["kpi_lbl"]) for lbl, _ in cards]
    w = (A4[0] - 30 * mm) / len(cards)
    t = Table([row_val, row_lbl], colWidths=[w] * len(cards))
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CARD),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.white),
        ("INNERGRID", (0, 0), (-1, -1), 3, colors.white),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def build_pdf(facts: dict[str, Any], brief: dict[str, Any]) -> bytes:
    s = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=14 * mm, bottomMargin=12 * mm,
        title="Weekly Demand & S&OP Brief",
    )
    is_demand = facts.get("is_demand")
    title = "Weekly Demand &amp; S&amp;OP Brief" if is_demand else "Executive Decision Brief"

    flow: list[Any] = []
    flow.append(Paragraph(title, s["title"]))

    basis = f"Generated {date.today():%d %b %Y}"
    if facts.get("metric_col"):
        basis += f" &nbsp;·&nbsp; metric: {facts['metric_col']}"
    if facts.get("profile"):
        basis += f" &nbsp;·&nbsp; {facts['profile']['n_rows']:,} rows"
    if facts.get("dimension_col"):
        basis += f" &nbsp;·&nbsp; segment: {facts['dimension_col']}"
    flow.append(Paragraph(basis, s["sub"]))
    flow.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e2e8f0")))
    flow.append(Spacer(1, 8))

    # KPI row
    kpis = _kpi_cards(facts.get("demand", {}), s)
    if kpis is not None:
        flow.append(kpis)
        flow.append(Spacer(1, 10))

    # TL;DR
    flow.append(Paragraph(f"<b>TL;DR</b> — {brief['tldr']}", s["tldr"]))
    flow.append(Spacer(1, 4))

    # Takeaways
    flow.append(Paragraph("Three Key Takeaways", s["h2"]))
    for i, t in enumerate(brief["takeaways"], 1):
        flow.append(Paragraph(f"<b>{i}.</b> {t}", s["body"]))

    # Actions
    flow.append(Paragraph("Recommended Actions", s["h2"]))
    for a in brief["actions"]:
        flow.append(Paragraph(f"•&nbsp; {a}", s["body"]))

    # Risk flags
    if brief.get("risk_flags"):
        flow.append(Spacer(1, 8))
        flags = "&nbsp;&nbsp;·&nbsp;&nbsp;".join(brief["risk_flags"])
        rf = Table([[Paragraph(f"<b>Risk flags:</b> {flags}", s["flag"])]],
                   colWidths=[A4[0] - 30 * mm])
        rf.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), FLAG_BG),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        flow.append(rf)

    flow.append(Spacer(1, 14))
    flow.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0")))
    flow.append(Paragraph(
        "Generated by the Demand Brief Generator · numbers computed in code, "
        "narrative grounded on verified facts.", s["foot"]))

    doc.build(flow)
    return buf.getvalue()


if __name__ == "__main__":
    import sys
    import pandas as pd

    from brief_engine import analyze, generate_brief

    src = sys.argv[1] if len(sys.argv) > 1 else "sample_demand.csv"
    out = sys.argv[2] if len(sys.argv) > 2 else "demand_brief.pdf"
    df = pd.read_csv(src)
    facts = analyze(df)
    brief = generate_brief(facts)
    with open(out, "wb") as fh:
        fh.write(build_pdf(facts, brief))
    print(f"Wrote {out}")
