from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import os
from utils import app_dir


def export_customer_ledger_pdf(sales):
    if not sales:
        return

    base = app_dir()
    pdf_dir = os.path.join(base, "reports")
    os.makedirs(pdf_dir, exist_ok=True)

    file_path = os.path.join(pdf_dir, "customer_ledger.pdf")

    c = canvas.Canvas(file_path, pagesize=A4)
    width, height = A4

    y = height - 50
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, "Customer Ledger")

    y -= 30
    c.setFont("Helvetica", 10)

    headers = ["Date", "Invoice", "Total", "Paid", "Due"]
    x_pos = [40, 120, 220, 300, 380]

    for i, h in enumerate(headers):
        c.drawString(x_pos[i], y, h)

    y -= 15

    total_due = 0

    for s in sales:
        if y < 50:
            c.showPage()
            y = height - 50

        c.drawString(40, y, s.get("date", ""))
        c.drawString(120, y, s.get("invoice_no", ""))
        c.drawString(220, y, f"{s.get('grand_total', 0):.2f}")
        c.drawString(300, y, f"{s.get('paid', 0):.2f}")
        c.drawString(380, y, f"{s.get('due', 0):.2f}")

        total_due += s.get("due", 0)
        y -= 15

    y -= 20
    c.setFont("Helvetica-Bold", 11)
    c.drawString(300, y, "Total Due:")
    c.drawString(380, y, f"₹ {total_due:.2f}")

    c.save()
    os.startfile(file_path)
