import os
import json
from utils import app_dir

BASE_DIR = app_dir()
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

INV = os.path.join(DATA_DIR, "inventory.json")

# 🔹 inventory.json  create 
if not os.path.exists(INV):
    with open(INV, "w", encoding="utf-8") as f:
        json.dump({}, f)

with open(INV, "r", encoding="utf-8") as f:
    data = json.load(f)

for item, info in data.items():
    if info.get("rate", 0) == 0:
        info["rate"] = 1   # temporary safe value

with open(INV, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4)

print("Inventory rates repaired")
