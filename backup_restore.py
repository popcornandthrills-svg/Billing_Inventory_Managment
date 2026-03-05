import os
import zipfile
from datetime import datetime
from tkinter import filedialog, messagebox

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")


def backup_data():
    if not os.path.exists(DATA_DIR):
        messagebox.showerror("Error", "Data folder not found")
        return

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    default_name = f"backup_{timestamp}.zip"

    save_path = filedialog.asksaveasfilename(
        defaultextension=".zip",
        initialfile=default_name,
        filetypes=[("ZIP files", "*.zip")]
    )

    if not save_path:
        return

    try:
        with zipfile.ZipFile(save_path, "w", zipfile.ZIP_DEFLATED) as z:
            for file in os.listdir(DATA_DIR):
                full_path = os.path.join(DATA_DIR, file)
                if os.path.isfile(full_path):
                    z.write(full_path, arcname=f"data/{file}")

        messagebox.showinfo(
            "Backup Success",
            f"Backup created successfully:\n{save_path}"
        )

    except Exception as e:
        messagebox.showerror("Backup Failed", str(e))


def restore_data():
    if not os.path.exists(DATA_DIR):
        messagebox.showerror("Error", "Data folder not found")
        return

    zip_path = filedialog.askopenfilename(
        filetypes=[("ZIP files", "*.zip")]
    )

    if not zip_path:
        return

    confirm = messagebox.askyesno(
        "Confirm Restore",
        "Restoring backup will OVERWRITE existing data.\n\nContinue?"
    )

    if not confirm:
        return

    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(BASE_DIR)

        messagebox.showinfo(
            "Restore Complete",
            "Data restored successfully.\nPlease restart the application."
        )

    except Exception as e:
        messagebox.showerror("Restore Failed", str(e))
