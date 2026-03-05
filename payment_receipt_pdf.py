from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from datetime import datetime

def generate_supplier_payment_receipt(
    filename, supplier, amount, mode
):
    c = canvas.Canvas(filename, pagesize=A4)
    w, h = A4

    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, h-50, "Supplier Payment Receipt")

    c.setFont("Helvetica", 10)
    c.drawString(50, h-90, f"Date: {datetime.now().strftime('%d-%m-%Y')}")
    c.drawString(50, h-110, f"Supplier: {supplier['name']}")
    c.drawString(50, h-130, f"Phone: {supplier['phone']}")
    c.drawString(50, h-150, f"Payment Mode: {mode}")

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, h-190, f"Paid Amount: ₹{amount:.2f}")

    c.showPage()
    c.save()