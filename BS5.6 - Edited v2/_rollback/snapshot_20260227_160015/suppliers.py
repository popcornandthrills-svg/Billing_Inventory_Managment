import json
import os
from utils import app_dir

# -------------------------------
# Path setup
# -------------------------------
BASE_DIR = app_dir()
DATA_DIR = os.path.join(BASE_DIR, "data")
SUPPLIERS_FILE = os.path.join(DATA_DIR, "suppliers.json")

# -------------------------------
# File handling
# -------------------------------
def load_suppliers():
    if not os.path.exists(SUPPLIERS_FILE):
        return {}
    with open(SUPPLIERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_suppliers(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SUPPLIERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


# -------------------------------
# Supplier ID generator
# -------------------------------
def generate_supplier_id(suppliers):
    if not suppliers:
        return "S001"

    last = sorted(suppliers.keys())[-1]   # S005
    num = int(last.replace("S", ""))
    return f"S{num + 1:03d}"


# -------------------------------
# Core operations
# -------------------------------
# suppliers.py
from datetime import date
import json

def add_supplier(name, phone="", address="", gst=""):
    suppliers = load_suppliers()

    supplier_id = f"S{len(suppliers)+1:03d}"

    suppliers[supplier_id] = {
        "id": supplier_id,
        "name": name,
        "phone": phone,
        "address": address,
        "gst": gst
    }

    save_suppliers(suppliers)
    return suppliers[supplier_id]


    
def update_supplier(supplier_id, address="", phone="", gst=""):
    suppliers = load_suppliers()
    if supplier_id not in suppliers:
        return

    suppliers[supplier_id]["address"] = address
    suppliers[supplier_id]["phone"] = phone
    suppliers[supplier_id]["gst"] = gst

    save_suppliers(suppliers)

def get_all_suppliers():
    return load_suppliers()


def get_supplier(supplier_id):
    return load_suppliers().get(supplier_id)