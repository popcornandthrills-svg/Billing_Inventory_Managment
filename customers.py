import json
import os
from utils import app_dir

BASE_DIR = app_dir()
DATA_DIR = os.path.join(BASE_DIR, "data")
CUSTOMER_FILE = os.path.join(DATA_DIR, "customers.json")
os.makedirs(DATA_DIR, exist_ok=True)


def load_customers():
    if not os.path.exists(CUSTOMER_FILE):
        return {}
    with open(CUSTOMER_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_customers(data):
    with open(CUSTOMER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def save_customer(name, phone, address):
    if not phone:
        return

    data = load_customers()
    data[phone] = {
        "name": name,
        "phone": phone,
        "address": address
    }
    save_customers(data)


def get_customer_by_phone(phone):
    return load_customers().get(phone)


def get_customer_by_name(name):
    for c in load_customers().values():
        if c["name"].lower() == name.lower():
            return c
    return None
