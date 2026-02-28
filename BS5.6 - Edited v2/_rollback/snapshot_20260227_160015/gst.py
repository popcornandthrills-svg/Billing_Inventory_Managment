# gst.py

def calculate_gst_items(items, company_state, customer_state):
    """
    items = list of dicts with: qty, rate, gst_percent
    returns: updated items + summary
    """

    summary = {
        "taxable": 0.0,
        "cgst": 0.0,
        "sgst": 0.0,
        "igst": 0.0,
        "grand_total": 0.0
    }

    intra_state = (company_state == customer_state)

    for item in items:
        taxable = item["qty"] * item["rate"]
        gst_amt = taxable * item["gst_percent"] / 100

        cgst = sgst = igst = 0.0

        if intra_state:
            cgst = gst_amt / 2
            sgst = gst_amt / 2
        else:
            igst = gst_amt

        total = taxable + cgst + sgst + igst

        item.update({
            "taxable": round(taxable, 2),
            "cgst": round(cgst, 2),
            "sgst": round(sgst, 2),
            "igst": round(igst, 2),
            "total": round(total, 2)
        })

        summary["taxable"] += taxable
        summary["cgst"] += cgst
        summary["sgst"] += sgst
        summary["igst"] += igst
        summary["grand_total"] += total

    for k in summary:
        summary[k] = round(summary[k], 2)

    return items, summary
