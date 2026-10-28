"""PDF and CSV renderers fed exclusively by verified report data."""

import csv
import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.reports.service import MonthlyReport


def _money(value: int) -> str:
    return f"NGN {value / 100:,.2f}"


def _footer(canvas, document) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#53696B"))
    canvas.drawString(18 * mm, 9 * mm, "Fetch - consented financial data")
    canvas.drawRightString(A4[0] - 18 * mm, 9 * mm, f"Page {document.page}")
    canvas.restoreState()


def render_csv(report: MonthlyReport) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["Fetch monthly report", report.month, "Currency", report.currency])
    writer.writerow(["Income", report.income_minor])
    writer.writerow(["Expenses", report.expenses_minor])
    writer.writerow(["Net cash flow", report.net_cash_flow_minor])
    writer.writerow(["Business expenses", report.business_expenses_minor])
    writer.writerow(["Personal expenses", report.personal_expenses_minor])
    writer.writerow(["Unsure expenses", report.unsure_expenses_minor])
    writer.writerow([])
    writer.writerow(
        [
            "transaction_id",
            "posted_at",
            "direction",
            "amount_minor",
            "merchant",
            "category",
            "use_label",
            "confidence_bps",
        ]
    )
    for item in report.transactions:
        writer.writerow(
            [
                item.transaction_id,
                item.posted_at.isoformat(),
                item.direction,
                item.amount_minor,
                item.merchant,
                item.category,
                item.use_label,
                item.confidence_bps,
            ]
        )
    return output.getvalue().encode("utf-8-sig")


def render_pdf(report: MonthlyReport) -> bytes:
    output = io.BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Fetch monthly report {report.month}",
        author="Fetch",
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Fetch monthly financial report", styles["Title"]),
        Paragraph(f"Reporting month: {report.month}", styles["Heading2"]),
        Paragraph(
            "All figures are computed from consented ledger data. Unsure and low-confidence "
            "items are labelled for review.",
            styles["BodyText"],
        ),
        Spacer(1, 6 * mm),
    ]
    summary = Table(
        [
            ["Measure", "Amount"],
            ["Income", _money(report.income_minor)],
            ["Expenses", _money(report.expenses_minor)],
            ["Net cash flow", _money(report.net_cash_flow_minor)],
            ["Business expenses", _money(report.business_expenses_minor)],
            ["Personal expenses", _money(report.personal_expenses_minor)],
            ["Unsure expenses", _money(report.unsure_expenses_minor)],
        ],
        colWidths=[105 * mm, 55 * mm],
    )
    summary.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#173B3F")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B7C5C7")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F4")]),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.extend(
        (summary, Spacer(1, 7 * mm), Paragraph("Transaction evidence", styles["Heading2"]))
    )
    transaction_rows = [["Date", "Merchant", "Use", "Confidence", "Amount"]]
    for item in report.transactions:
        label = item.use_label
        if item.confidence_bps < 7000:
            label += " (low confidence)"
        transaction_rows.append(
            [
                item.posted_at.strftime("%Y-%m-%d"),
                item.merchant[:28],
                label,
                f"{item.confidence_bps / 100:.0f}%",
                _money(item.amount_minor),
            ]
        )
    if len(transaction_rows) == 1:
        transaction_rows.append(["-", "No transactions", "-", "-", _money(0)])
    transactions = Table(
        transaction_rows,
        repeatRows=1,
        colWidths=[24 * mm, 48 * mm, 37 * mm, 25 * mm, 35 * mm],
    )
    transactions.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCE8E6")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (-2, 1), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#B7C5C7")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(transactions)
    if report.uncertain_items:
        story.extend(
            (
                Spacer(1, 6 * mm),
                Paragraph("Items requiring review", styles["Heading2"]),
                Paragraph(
                    f"{len(report.uncertain_items)} item(s) are unsure or low confidence and "
                    "should not be treated as confirmed classifications.",
                    styles["BodyText"],
                ),
            )
        )
    document.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return output.getvalue()
