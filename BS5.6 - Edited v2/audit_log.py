import json
import os
from datetime import datetime
from utils import app_dir

BASE_DIR = app_dir()
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

AUDIT_FILE = os.path.join(DATA_DIR, "audit_log.json")
CURRENT_AUDIT_USER = None


def set_current_audit_user(user):
    global CURRENT_AUDIT_USER
    text = str(user or "").strip()
    CURRENT_AUDIT_USER = text or None


def write_audit_log(
    user=None,
    module=None,
    action=None,
    reference=None,
    before=None,
    after=None,
    extra=None
):
    effective_user = user
    # If caller passes no user or hardcoded "admin", prefer current logged-in user context.
    if CURRENT_AUDIT_USER and (not effective_user or str(effective_user).strip().lower() == "admin"):
        effective_user = CURRENT_AUDIT_USER

    log = {
        "timestamp": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
        "user": effective_user,
        "module": module,
        "action": action,
        "reference": reference,
        "before": before,
        "after": after
    }

    if extra:
        log.update(extra)

    logs = []
    if os.path.exists(AUDIT_FILE):
        try:
            with open(AUDIT_FILE, "r", encoding="utf-8") as f:
                logs = json.load(f)
        except:
            logs = []

    # Keep persisted log in reverse chronological order (latest first).
    logs.insert(0, log)

    with open(AUDIT_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2)
