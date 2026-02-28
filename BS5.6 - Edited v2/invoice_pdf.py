from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from datetime import datetime
import os


def generate_gst_invoice_pdf(
    filepath,
    company,
    invoice_no,
    invoice_date,
    customer,
    items,
    summary
):
    # Ensure folder exists
    folder = os.path.dirname(filepath)
    if folder and not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)

    c = canvas.Canvas(filepath, pagesize=A4)
    width, height = A4

    left = 25
    right = width - 25
    y = height - 30

    # ================= COMPANY HEADER =================
    c.setFont("Helvetica-Bold", 16)
    c.drawString(left, y, company["name"])
    y -= 18

    c.setFont("Helvetica", 9)
    c.drawString(left, y, company["address"])
    y -= 12
    c.drawString(left, y, f"GSTIN: {company['gstin']}")

    # Invoice title
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(right, height - 30, "TAX INVOICE")

    y -= 25
    c.line(left, y, right, y)
    y -= 15

    # ================= INVOICE DETAILS =================
    c.setFont("Helvetica", 10)
    c.drawString(left, y, f"Invoice No : {invoice_no}")
    c.drawRightString(right, y, f"Date : {invoice_date}")
    y -= 18

    # ================= CUSTOMER =================
    c.setFont("Helvetica-Bold", 10)
    c.drawString(left, y, "Bill To:")
    y -= 14

    c.setFont("Helvetica", 10)
    c.drawString(left, y, customer["name"])
    y -= 12
    c.drawString(left, y, f"State: {customer['state']}")

    y -= 20
    c.line(left, y, right, y)
    y -= 15

    # ================= TABLE HEADER =================
    c.setFont("Helvetica-Bold", 9)
    headers = ["Item", "HSN", "Qty", "Rate", "Taxable", "CGST", "SGST", "IGST", "Total"]
    x = [left, 150, 200, 240, 300, 360, 410, 460, 520]

    for i, h in enumerate(headers):
        c.drawString(x[i], y, h)

    y -= 8
    c.line(left, y, right, y)
    y -= 12

    # ================= ITEMS =================
    c.setFont("Helvetica", 9)
    for it in items:
        c.drawString(x[0], y, it["name"])
        c.drawString(x[1], y, it.get("hsn", ""))
        c.drawRightString(x[2] + 20, y, str(it["qty"]))
        c.drawRightString(x[3] + 30, y, f"{it['rate']:.2f}")
        c.drawRightString(x[4] + 35, y, f"{it['taxable']:.2f}")
        c.drawRightString(x[5] + 30, y, f"{it['cgst']:.2f}")
        c.drawRightString(x[6] + 30, y, f"{it['sgst']:.2f}")
        c.drawRightString(x[7] + 30, y, f"{it['igst']:.2f}")
        c.drawRightString(x[8] + 35, y, f"{it['total']:.2f}")
        y -= 18

    y -= 20
    c.line(300, y, right, y)
    y -= 25

    # ================= TOTALS =================
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(500, y, "Taxable:")
    c.drawRightString(right, y, f"{summary['taxable']:.2f}")
    y -= 14

    if summary["cgst"] > 0:
        c.drawRightString(500, y, "CGST:")
        c.drawRightString(right, y, f"{summary['cgst']:.2f}")
        y -= 14

    if summary["sgst"] > 0:
        c.drawRightString(500, y, "SGST:")
        c.drawRightString(right, y, f"{summary['sgst']:.2f}")
        y -= 14

    if summary["igst"] > 0:
        c.drawRightString(500, y, "IGST:")
        c.drawRightString(right, y, f"{summary['igst']:.2f}")
        y -= 14

    discount_amount = float(summary.get("discount_amount", 0) or 0)
    if discount_amount > 0:
        c.drawRightString(500, y, "Gross Total:")
        c.drawRightString(right, y, f"{summary.get('gross_total', summary['grand_total'] + discount_amount):.2f}")
        y -= 14
        c.drawRightString(500, y, f"Discount ({summary.get('discount_percent', 0):.2f}%):")
        c.drawRightString(right, y, f"-{discount_amount:.2f}")
        y -= 14

    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(500, y, "Grand Total:")
    c.drawRightString(right, y, f"{summary['grand_total']:.2f}")

    c.showPage()
    c.save()
