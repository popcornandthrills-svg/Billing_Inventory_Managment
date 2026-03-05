from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import os
from utils import app_dir



# ledger_pdf.py (top or helpers section)

def draw_company_header(c, page_width, y):
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(
        page_width / 2,
        y,
        "Goldprince Trade Centre PVT LTD"
    )
    y -= 18

    c.setFont("Helvetica", 9)
    c.drawCentredString(
        page_width / 2,
        y,
        "Machilipatnam | GSTIN: 37XXXXXXXXXX"
    )
    y -= 20

    c.line(40, y, page_width - 40, y)
    y -= 20

    return y


def generate_customer_ledger_pdf(rows, customer_name="Customer"):
    if not rows:
        return None

    BASE_DIR = app_dir()
    REPORT_DIR = os.path.join(BASE_DIR, "reports")
    os.makedirs(REPORT_DIR, exist_ok=True)

    pdf_path = os.path.join(
        REPORT_DIR,
        f"customer_ledger_{customer_name}.pdf"
    )

    c = canvas.Canvas(pdf_path, pagesize=A4)
    w, height = A4

    y = height - 40
    #  COMPANY HEADER (THIS IS THE PLACE)
    y = draw_company_header(c, w, y)
    
        
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, f"Customer Ledger : {customer_name}")

    y -= 30
    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, y, "Date")
    c.drawString(120, y, "Invoice")
    c.drawString(200, y, "Total")
    c.drawString(260, y, "Paid")
    c.drawString(320, y, "Due")

    y -= 15
    c.setFont("Helvetica", 10)

    total_due = 0.0

    for r in rows:
        if y < 60:
            c.showPage()
            y = height - 40

        c.drawString(40, y, r["date"])
        c.drawString(120, y, r["invoice"])
        c.drawRightString(250, y, r["total"])
        c.drawRightString(310, y, r["paid"])
        c.drawRightString(370, y, r["due"])

        total_due += float(r["due"].replace("₹", ""))

        y -= 15

    y -= 20
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, f"TOTAL DUE : {total_due:,.2f}")

    c.save()
    os.startfile(pdf_path)

    return pdf_path
