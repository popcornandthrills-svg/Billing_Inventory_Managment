from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import os


def _split_lines_by_width(c, text, max_width, font_name="Helvetica", font_size=9, max_lines=2):
    text = str(text or "").strip()
    if not text:
        return [""]
    c.setFont(font_name, font_size)
    words = text.split()
    lines = []
    line = ""
    for w in words:
        trial = (line + " " + w).strip()
        if c.stringWidth(trial, font_name, font_size) <= max_width:
            line = trial
        else:
            if line:
                lines.append(line)
            line = w
            if len(lines) >= max_lines - 1:
                break
    if line:
        lines.append(line)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    if len(lines) == max_lines and words:
        last = lines[-1]
        while c.stringWidth(last + "...", font_name, font_size) > max_width and len(last) > 1:
            last = last[:-1]
        if last != lines[-1]:
            lines[-1] = last + "..."
    return lines


def _fit_single_line(c, text, max_width, font_name="Helvetica", font_size=9):
    text = str(text or "")
    if c.stringWidth(text, font_name, font_size) <= max_width:
        return text
    out = text
    while out and c.stringWidth(out + "...", font_name, font_size) > max_width:
        out = out[:-1]
    return (out + "...") if out else ""


def _draw_text_in_box(c, text, x, y_top, w, h, font_name="Helvetica", font_size=9, line_gap=2, max_lines=None):
    line_h = font_size + line_gap
    allowed = max(1, int((h - 4) // line_h))
    if max_lines is not None:
        allowed = min(allowed, max_lines)
    lines = _split_lines_by_width(c, text, max(w - 6, 20), font_name, font_size, max_lines=allowed)
    c.setFont(font_name, font_size)
    y = y_top - font_size - 2
    for ln in lines:
        if y < (y_top - h + 2):
            break
        c.drawString(x + 3, y, ln)
        y -= line_h


def _num_to_words_upto_999(n):
    ones = [
        "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
        "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
        "Seventeen", "Eighteen", "Nineteen",
    ]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
    n = int(n)
    if n < 20:
        return ones[n]
    if n < 100:
        return (tens[n // 10] + (" " + ones[n % 10] if n % 10 else "")).strip()
    return (ones[n // 100] + " Hundred" + (" " + _num_to_words_upto_999(n % 100) if n % 100 else "")).strip()


def amount_in_words(amount):
    amount = max(float(amount or 0), 0.0)
    rupees = int(amount)
    paise = int(round((amount - rupees) * 100))

    if rupees == 0:
        words = "Zero"
    else:
        parts = []
        crore = rupees // 10000000
        rupees %= 10000000
        lakh = rupees // 100000
        rupees %= 100000
        thousand = rupees // 1000
        rupees %= 1000
        hundred_part = rupees
        if crore:
            parts.append(_num_to_words_upto_999(crore) + " Crore")
        if lakh:
            parts.append(_num_to_words_upto_999(lakh) + " Lakh")
        if thousand:
            parts.append(_num_to_words_upto_999(thousand) + " Thousand")
        if hundred_part:
            parts.append(_num_to_words_upto_999(hundred_part))
        words = " ".join(parts)

    if paise:
        return f"INR {words} and {paise:02d} Paise Only"
    return f"INR {words} Only"


def generate_gst_invoice_pdf(filepath, company, invoice_no, invoice_date, customer, items, summary):
    folder = os.path.dirname(filepath)
    if folder and not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)

    c = canvas.Canvas(filepath, pagesize=A4)
    page_w, page_h = A4

    left = 18
    right = page_w - 18
    top = page_h - 18
    bottom = 18
    inner_w = right - left

    c.setLineWidth(0.8)
    c.rect(left, bottom, inner_w, top - bottom)

    # Title row
    title_h = 30
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString((left + right) / 2, top - 19, "Estimate")
    y = top - title_h
    c.line(left, y, right, y)

    # Header block
    header_h = 160
    header_top = y
    header_bottom = header_top - header_h
    c.line(left, header_bottom, right, header_bottom)

    left_block_w = 300
    left_block_x2 = left + left_block_w
    c.line(left_block_x2, header_top, left_block_x2, header_bottom)

    # Right header grid
    right_left = left_block_x2
    right_mid = right_left + (right - right_left) * 0.52
    c.line(right_mid, header_top, right_mid, header_bottom)

    info_rows = [
        ("Invoice No.", str(invoice_no), True),
        ("Dated", str(invoice_date), True),
        ("Mode/Terms of Payment", "", False),
        ("Reference No. & Date", "", False),
        ("Buyer's Order No.", "", False),
        ("Dispatch Doc No.", "", False),
    ]
    row_h = header_h / len(info_rows)
    for i, (label, value, bold_value) in enumerate(info_rows):
        row_top = header_top - (i * row_h)
        row_bottom = row_top - row_h
        c.line(right_left, row_bottom, right, row_bottom)

        c.setFont("Helvetica", 9)
        c.drawString(right_left + 4, row_top - 14, _fit_single_line(c, label, (right_mid - right_left) - 8, "Helvetica", 9))

        val_font = "Helvetica-Bold" if bold_value else "Helvetica"
        val_size = 10 if bold_value else 9
        c.setFont(val_font, val_size)
        c.drawString(right_mid + 4, row_top - 14, _fit_single_line(c, value, (right - right_mid) - 8, val_font, val_size))

    # Left header content
    c.setFont("Helvetica-Bold", 12)
    c.drawString(left + 4, header_top - 16, _fit_single_line(c, company.get("name", ""), left_block_w - 8, "Helvetica-Bold", 12))

    c.setFont("Helvetica", 9)
    _draw_text_in_box(
        c,
        company.get("address", ""),
        left + 2,
        header_top - 24,
        left_block_w - 4,
        34,
        "Helvetica",
        9,
        max_lines=2,
    )
    c.drawString(left + 4, header_top - 70, "State Name: AP")

    c.setFont("Helvetica-Bold", 11)
    c.drawString(left + 4, header_top - 96, "Buyer (Bill To)")
    c.drawString(left + 4, header_top - 112, _fit_single_line(c, customer.get("name", ""), left_block_w - 8, "Helvetica-Bold", 11))

    c.setFont("Helvetica", 9)
    c.drawString(left + 4, header_top - 128, _fit_single_line(c, f"State Name: {customer.get('state', 'AP')}", left_block_w - 8, "Helvetica", 9))

    # Item table
    table_top = header_bottom
    table_header_h = 24
    table_header_bottom = table_top - table_header_h

    # strict fixed columns that exactly fill width
    # Sl | Desc | HSN | Qty | Rate | Amount
    col_w = [24, 240, 64, 66, 66, inner_w - (24 + 240 + 64 + 66 + 66)]
    x = [left]
    for wcol in col_w:
        x.append(x[-1] + wcol)

    table_bottom = bottom + 130

    c.line(left, table_header_bottom, right, table_header_bottom)
    for xv in x:
        c.line(xv, table_top, xv, table_bottom)

    headers = ["Sl", "Description of Goods", "HSN/SAC", "Quantity", "Rate", "Amount"]
    c.setFont("Helvetica", 9)
    for i, head in enumerate(headers):
        c.drawCentredString((x[i] + x[i + 1]) / 2, table_top - 15, head)

    # Rows
    row_h = 24
    y_row = table_header_bottom - 16
    max_rows = int((table_header_bottom - (table_bottom + 36)) // row_h)

    total_qty = 0.0
    gross_total = 0.0

    for idx, it in enumerate(items[:max_rows], start=1):
        item_name = str(it.get("name") or it.get("item") or "")
        qty = float(it.get("qty", 0) or 0)
        rate = float(it.get("rate", 0) or 0)
        hsn = str(it.get("hsn") or it.get("hsn_sac") or "")
        if not hsn:
            hsn = "-"
        amount = float(it.get("total", qty * rate) or 0)

        total_qty += qty
        gross_total += amount

        c.setFont("Helvetica", 9)
        c.drawString(x[0] + 3, y_row, str(idx))
        c.drawString(x[1] + 3, y_row, _fit_single_line(c, item_name, (x[2] - x[1]) - 6, "Helvetica", 9))
        c.drawRightString(x[3] - 4, y_row, _fit_single_line(c, hsn, (x[3] - x[2]) - 6, "Helvetica", 9))
        c.drawRightString(x[4] - 4, y_row, f"{qty:.2f}")
        c.drawRightString(x[5] - 4, y_row, f"{rate:.2f}")
        c.drawRightString(x[6] - 6, y_row, f"{amount:.2f}")

        y_row -= row_h

    # summary line inside table
    sum_y = max(y_row - 2, table_bottom + 40)
    c.line(left, sum_y, right, sum_y)

    discount_amount = float(summary.get("discount_amount", 0) or 0)
    gross_total = float(summary.get("gross_total", gross_total) or 0)
    grand_total = float(summary.get("grand_total", 0) or 0)
    round_off = grand_total - (gross_total - discount_amount)

    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(x[4] - 4, sum_y - 14, f"{total_qty:.2f}")
    c.drawRightString(x[5] - 4, sum_y - 14, "Total")
    c.drawRightString(x[6] - 6, sum_y - 14, f"{gross_total:.2f}")

    c.setFont("Helvetica", 9)
    c.drawRightString(x[5] - 4, sum_y - 34, "Less : Discount")
    c.drawRightString(x[6] - 6, sum_y - 34, f"-{discount_amount:.2f}")
    c.drawRightString(x[5] - 4, sum_y - 50, "Round Off")
    c.drawRightString(x[6] - 6, sum_y - 50, f"{round_off:.2f}")

    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(x[5] - 4, sum_y - 72, "Grand Total")
    c.drawRightString(x[6] - 6, sum_y - 72, f"Rs {grand_total:.2f}")

    # amount in words + tax section
    words_top = table_bottom + 34
    c.setFont("Helvetica", 8.5)
    c.drawString(left + 4, words_top, "Amount Chargeable (in words)")
    _draw_text_in_box(
        c,
        amount_in_words(grand_total),
        left + 2,
        words_top - 2,
        inner_w - 4,
        24,
        "Helvetica-Bold",
        10,
        max_lines=1,
    )

    tax_box_top = table_bottom + 8
    tax_box_h = 42
    c.rect(left + 2, tax_box_top - tax_box_h, inner_w - 4, tax_box_h)

    t1 = left + 130
    t2 = left + 260
    t3 = left + 390
    c.line(t1, tax_box_top, t1, tax_box_top - tax_box_h)
    c.line(t2, tax_box_top, t2, tax_box_top - tax_box_h)
    c.line(t3, tax_box_top, t3, tax_box_top - tax_box_h)

    taxable = float(summary.get("taxable", 0) or 0)
    cgst = float(summary.get("cgst", 0) or 0)
    sgst = float(summary.get("sgst", 0) or 0)
    igst = float(summary.get("igst", 0) or 0)
    total_tax = cgst + sgst + igst

    c.setFont("Helvetica", 8.5)
    c.drawString(left + 6, tax_box_top - 12, "Taxable Value")
    c.drawString(t1 + 6, tax_box_top - 12, "CGST")
    c.drawString(t2 + 6, tax_box_top - 12, "SGST/UTGST")
    c.drawString(t3 + 6, tax_box_top - 12, "Total Tax Amount")

    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(t1 - 8, tax_box_top - 30, f"{taxable:.2f}")
    c.drawRightString(t2 - 8, tax_box_top - 30, f"{cgst:.2f}")
    c.drawRightString(t3 - 8, tax_box_top - 30, f"{(sgst + igst):.2f}")
    c.drawRightString(right - 8, tax_box_top - 30, f"{total_tax:.2f}")

    # footer declaration/signature
    footer_top = tax_box_top - tax_box_h - 8
    c.setFont("Helvetica", 8.5)
    c.drawString(left + 4, footer_top, _fit_single_line(c, f"Tax Amount (in words): {amount_in_words(total_tax)}", inner_w - 8, "Helvetica", 8.5))

    c.setFont("Helvetica", 8)
    c.drawString(left + 4, footer_top - 22, "Declaration")
    _draw_text_in_box(
        c,
        "We declare that this invoice shows the actual price of the goods described and that all particulars are true and correct.",
        left + 2,
        footer_top - 24,
        inner_w * 0.68,
        28,
        "Helvetica",
        8,
        max_lines=2,
    )

    c.drawRightString(right - 6, footer_top - 22, _fit_single_line(c, f"for {company.get('name', '')}", 210, "Helvetica", 8))
    c.drawRightString(right - 6, footer_top - 36, "Authorised Signatory")

    c.showPage()
    c.save()
