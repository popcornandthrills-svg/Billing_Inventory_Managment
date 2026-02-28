import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph
)
from reportlab.pdfgen import canvas
from utils import app_dir

from sales import load_sales
from purchase import load_purchases
from config import COMPANY


# ==================================================
# COMMON COMPANY HEADER (REUSABLE)
# ==================================================
def draw_company_header(c, w, y):
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(w / 2, y, COMPANY["name"])
    y -= 18

    c.setFont("Helvetica", 10)
    c.drawCentredString(
        w / 2,
        y,
        f'{COMPANY["address"]} | GSTIN: {COMPANY["gstin"]}'
    )
    y -= 15

    c.line(40, y, w - 40, y)
    return y - 25


def generate_due_report_pdf():
    BASE_DIR = app_dir()
    REPORT_DIR = os.path.join(BASE_DIR, "reports")
    os.makedirs(REPORT_DIR, exist_ok=True)

    pdf_path = os.path.join(REPORT_DIR, "Customer_Due_Report.pdf")

    doc = SimpleDocTemplate(pdf_path, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Customer Due Report", styles["Title"]))

    data = [["Invoice", "Date", "Customer", "Phone", "Total", "Paid", "Due"]]

    total_due = 0.0
    for s in load_sales():
        due = float(s.get("due", 0))
        if due > 0:
            data.append([
                s.get("invoice_no"),
                s.get("date"),
                s.get("customer_name"),
                s.get("phone"),
                f"{s.get('grand_total'):.2f}",
                f"{s.get('paid'):.2f}",
                f"{due:.2f}"
            ])
            total_due += due

    data.append(["", "", "TOTAL", "", "", "", f"{total_due:.2f}"])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 1, colors.black),
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("BACKGROUND", (0,-1), (-1,-1), colors.whitesmoke),
        ("FONT", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONT", (0,-1), (-1,-1), "Helvetica-Bold"),
    ]))

    elements.append(table)
    doc.build(elements)

    os.startfile(pdf_path)
    
def generate_purchase_due_pdf():
    base = app_dir()
    report_dir = os.path.join(base, "reports")
    os.makedirs(report_dir, exist_ok=True)

    pdf_path = os.path.join(report_dir, "purchase_due_report.pdf")

    doc = SimpleDocTemplate(pdf_path, pagesize=A4)
    styles = getSampleStyleSheet()

    data = [["Supplier", "Invoice", "Date", "Total", "Due"]]
    total_due = 0

    for p in load_purchases():
        total = float(p.get("grand_total", 0))
        paid = float(p.get("paid_amount", 0))
        due = round(total - paid, 2)

        if due > 0:
            data.append([
                p.get("supplier_name", ""),
                p.get("purchase_id", ""),
                p.get("created_on", ""),
                f"{total:.2f}",
                f"{due:.2f}"
            ])
            total_due += due

    data.append(["", "", "TOTAL", "", f"{total_due:.2f}"])

    table = Table(data, colWidths=[90, 70, 70, 60, 60])
    table.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 1, colors.black),
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("ALIGN", (3,1), (-1,-1), "RIGHT"),
        ("FONT", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONT", (0,-1), (-1,-1), "Helvetica-Bold"),
    ]))

    doc.build([
        Paragraph("Purchase Due Report", styles["Title"]),
        table
    ])

    os.startfile(pdf_path)
    return pdf_path


def generate_purchase_report_pdf(rows):
    out_dir = os.path.join(app_dir(), "reports")
    os.makedirs(out_dir, exist_ok=True)

    path = os.path.join(out_dir, "purchase_report.pdf")

    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4

    y = h - 40
    
    # ---------- COMPANY HEADER ----------
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(w / 2, y, COMPANY["name"])
    y -= 18

    c.setFont("Helvetica", 10)
    c.drawCentredString(
        w / 2,
        y,
        f'{COMPANY["address"]} | GSTIN: {COMPANY["gstin"]}'
    )
    y -= 15

    c.line(40, y, w - 40, y)
    y -= 25
    
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(w / 2, y, "Purchase Report")
    y -= 30

    c.setFont("Helvetica", 9)
    # Supports both legacy 6-column rows and current 4-column summary rows.
    is_summary = bool(rows) and len(rows[0]) == 4
    if is_summary:
        headers = ["Invoice", "Supplier", "Date", "Amount"]
        x = [40, 150, 380, 500]
    else:
        headers = ["Supplier", "Invoice", "Date", "Item", "Qty", "Amount"]
        x = [30, 120, 200, 270, 420, 460]

    for i, htxt in enumerate(headers):
        c.drawString(x[i], y, htxt)

    y -= 12
    c.line(25, y, w - 25, y)
    y -= 12
    
    c.setFont("Helvetica", 9)

    for r in rows:
        if is_summary:
            c.drawString(x[0], y, str(r[0]))   # invoice
            c.drawString(x[1], y, str(r[1]))   # supplier
            c.drawString(x[2], y, str(r[2]))   # date
            c.drawRightString(x[3] + 50, y, f"{float(r[3]):.2f}")  # amount
        else:
            c.drawString(x[0], y, str(r[0]))   # supplier
            c.drawString(x[1], y, str(r[1]))   # invoice
            c.drawString(x[2], y, str(r[2]))   # date
            c.drawString(x[3], y, str(r[3]))   # item
            c.drawRightString(x[4] + 20, y, str(r[4]))  # qty
            c.drawRightString(x[5] + 50, y, f"{float(r[5]):.2f}")  # amount

        y -= 12

        if y < 40:
            c.showPage()
            y = h - 40
            c.setFont("Helvetica", 9)

    c.save()
    os.startfile(path)
    return path


def generate_purchase_items_pdf(invoice, supplier, date, rows):
    out_dir = os.path.join(app_dir(), "reports")
    os.makedirs(out_dir, exist_ok=True)

    safe_invoice = str(invoice or "NA").replace("/", "-")
    safe_date = str(date or "NA").replace("/", "-")
    path = os.path.join(out_dir, f"purchase_items_{safe_invoice}_{safe_date}.pdf")

    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4
    y = h - 40

    y = draw_company_header(c, w, y)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(w / 2, y, "Purchase Items Detail")
    y -= 22

    c.setFont("Helvetica", 10)
    c.drawString(40, y, f"Invoice: {invoice}")
    y -= 14
    c.drawString(40, y, f"Supplier: {supplier}")
    y -= 14
    c.drawString(40, y, f"Date: {date}")
    y -= 18

    headers = ["Item", "Qty", "Unit", "Rate", "GST %", "Total"]
    x = [35, 285, 340, 405, 470, 540]
    c.setFont("Helvetica-Bold", 9)
    for i, htxt in enumerate(headers):
        c.drawString(x[i], y, htxt)
    y -= 10
    c.line(30, y, w - 30, y)
    y -= 12

    c.setFont("Helvetica", 9)
    total_amount = 0.0
    for row in rows:
        item = str(row.get("item", ""))
        qty = float(row.get("qty", 0) or 0)
        unit = str(row.get("unit", ""))
        rate = float(row.get("rate", 0) or 0)
        gst = float(row.get("gst", 0) or 0)
        total = float(row.get("total", 0) or 0)
        total_amount += total

        c.drawString(x[0], y, item[:42])
        c.drawRightString(x[1] + 35, y, f"{qty:.2f}")
        c.drawString(x[2], y, unit[:8])
        c.drawRightString(x[3] + 40, y, f"{rate:.2f}")
        c.drawRightString(x[4] + 30, y, f"{gst:.2f}")
        c.drawRightString(x[5] + 25, y, f"{total:.2f}")
        y -= 12

        if y < 50:
            c.showPage()
            y = h - 40
            c.setFont("Helvetica", 9)

    y -= 4
    c.line(400, y, w - 30, y)
    y -= 12
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(w - 35, y, f"Total: {total_amount:.2f}")

    c.save()
    os.startfile(path)
    return path
