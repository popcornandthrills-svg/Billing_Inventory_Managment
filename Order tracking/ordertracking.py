import sqlite3
from contextlib import closing
from datetime import datetime
import json
import csv
from pathlib import Path
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
try:
    from tkcalendar import DateEntry
except ImportError:
    DateEntry = None

if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent

DB_PATH = APP_DIR / "ordertracking.db"
SAMPLE_DATASET_PATH = APP_DIR / "sample_dataset.json"

STATUS_OPTIONS = ["In Progress", "Blocked", "Completed"]
QC_RESULTS = ["Pending", "Pass", "Fail", "Rework"]
DEFAULT_STAGES = [
    ("CAD Design", 1),
    ("Camera", 2),
    ("3D Printing", 3),
    ("Moulding", 4),
    ("Production", 5),
    ("Filing Unwanted Material", 6),
    ("Painting", 7),
    ("Stone Work (If Needed)", 8),
    ("Packing Finished Product", 9),
]


class OrderDB:
    def __init__(self, db_path: Path):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.init_db()

    def init_db(self):
        with closing(self.conn.cursor()) as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_code TEXT NOT NULL UNIQUE,
                    supplier_name TEXT,
                    customer_name TEXT NOT NULL,
                    order_category TEXT,
                    order_purpose TEXT,
                    order_note TEXT,
                    product_name TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    order_date TEXT,
                    order_placed_date TEXT,
                    due_date TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS stages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stage_name TEXT NOT NULL UNIQUE,
                    order_index INTEGER NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS order_stage_progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    stage_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    note TEXT,
                    updated_at TEXT NOT NULL,
                    UNIQUE(order_id, stage_id),
                    FOREIGN KEY(order_id) REFERENCES orders(id),
                    FOREIGN KEY(stage_id) REFERENCES stages(id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS quality_checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    qc_code TEXT,
                    order_id INTEGER NOT NULL,
                    order_article_id INTEGER,
                    stage_id INTEGER NOT NULL,
                    qc_result TEXT NOT NULL,
                    inspector TEXT,
                    defects_found INTEGER NOT NULL DEFAULT 0,
                    remarks TEXT,
                    checked_at TEXT NOT NULL,
                    FOREIGN KEY(order_id) REFERENCES orders(id),
                    FOREIGN KEY(stage_id) REFERENCES stages(id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS order_articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    article_number TEXT NOT NULL,
                    item_name TEXT,
                    material TEXT,
                    item_weight TEXT,
                    size TEXT,
                    colours TEXT,
                    quantity INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(order_id, article_number),
                    FOREIGN KEY(order_id) REFERENCES orders(id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS order_article_stage_progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_article_id INTEGER NOT NULL,
                    stage_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    note TEXT,
                    updated_at TEXT NOT NULL,
                    UNIQUE(order_article_id, stage_id),
                    FOREIGN KEY(order_article_id) REFERENCES order_articles(id),
                    FOREIGN KEY(stage_id) REFERENCES stages(id)
                )
                """
            )
            self.ensure_orders_table_migration(cur)
        self.conn.commit()
        self.seed_stages()

    def ensure_orders_table_migration(self, cur):
        cur.execute("PRAGMA table_info(orders)")
        columns = {row["name"] for row in cur.fetchall()}
        if "article_number" not in columns:
            cur.execute("ALTER TABLE orders ADD COLUMN article_number TEXT")
        if "order_placed_date" not in columns:
            cur.execute("ALTER TABLE orders ADD COLUMN order_placed_date TEXT")
        if "supplier_name" not in columns:
            cur.execute("ALTER TABLE orders ADD COLUMN supplier_name TEXT")
        if "order_category" not in columns:
            cur.execute("ALTER TABLE orders ADD COLUMN order_category TEXT")
        if "order_purpose" not in columns:
            cur.execute("ALTER TABLE orders ADD COLUMN order_purpose TEXT")
        if "order_note" not in columns:
            cur.execute("ALTER TABLE orders ADD COLUMN order_note TEXT")
        if "order_date" not in columns:
            cur.execute("ALTER TABLE orders ADD COLUMN order_date TEXT")
        cur.execute("PRAGMA table_info(quality_checks)")
        qc_columns = {row["name"] for row in cur.fetchall()}
        if "qc_code" not in qc_columns:
            cur.execute("ALTER TABLE quality_checks ADD COLUMN qc_code TEXT")
        if "order_article_id" not in qc_columns:
            cur.execute("ALTER TABLE quality_checks ADD COLUMN order_article_id INTEGER")
        cur.execute("PRAGMA table_info(order_articles)")
        article_columns = {row["name"] for row in cur.fetchall()}
        if "item_name" not in article_columns:
            cur.execute("ALTER TABLE order_articles ADD COLUMN item_name TEXT")
        if "material" not in article_columns:
            cur.execute("ALTER TABLE order_articles ADD COLUMN material TEXT")
        if "item_weight" not in article_columns:
            cur.execute("ALTER TABLE order_articles ADD COLUMN item_weight TEXT")
        if "size" not in article_columns:
            cur.execute("ALTER TABLE order_articles ADD COLUMN size TEXT")
        if "colours" not in article_columns:
            cur.execute("ALTER TABLE order_articles ADD COLUMN colours TEXT")
        self.ensure_article_migration(cur)
        cur.execute("SELECT id, order_id, stage_id FROM quality_checks WHERE qc_code IS NULL OR TRIM(qc_code) = ''")
        for row in cur.fetchall():
            qc_code = self.build_qc_code(row["order_id"], row["stage_id"], row["id"])
            cur.execute("UPDATE quality_checks SET qc_code = ? WHERE id = ?", (qc_code, row["id"]))
        self.normalize_quality_checks(cur)

    def ensure_article_migration(self, cur):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("SELECT id, article_number, quantity FROM orders")
        for row in cur.fetchall():
            article = (row["article_number"] or "").strip() or f"AUTO-{row['id']:04d}"
            qty = int(row["quantity"] or 1)
            cur.execute(
                """
                INSERT OR IGNORE INTO order_articles (order_id, article_number, item_name, material, item_weight, size, colours, quantity, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (row["id"], article, "", "", "", "", "", qty, now),
            )

        stage_rows = self.list_stages()
        cur.execute("SELECT id FROM order_articles")
        article_ids = [r["id"] for r in cur.fetchall()]
        for article_id in article_ids:
            for stage in stage_rows:
                cur.execute(
                    """
                    INSERT OR IGNORE INTO order_article_stage_progress (order_article_id, stage_id, status, note, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (article_id, stage["id"], STATUS_OPTIONS[0], "", now),
                )

        cur.execute(
            """
            SELECT qc.id, qc.order_id
            FROM quality_checks qc
            WHERE qc.order_article_id IS NULL
            """
        )
        for row in cur.fetchall():
            cur.execute("SELECT id FROM order_articles WHERE order_id = ? ORDER BY id LIMIT 1", (row["order_id"],))
            art = cur.fetchone()
            if art:
                cur.execute("UPDATE quality_checks SET order_article_id = ? WHERE id = ?", (art["id"], row["id"]))

    def normalize_quality_checks(self, cur):
        # Keep only the latest QC row per order-article-stage pair.
        cur.execute(
            """
            SELECT order_id, order_article_id, stage_id, MAX(id) AS keep_id
            FROM quality_checks
            GROUP BY order_id, order_article_id, stage_id
            """
        )
        keep_rows = cur.fetchall()
        keep_map = {(row["order_id"], row["order_article_id"], row["stage_id"]): row["keep_id"] for row in keep_rows}
        cur.execute("SELECT id, order_id, order_article_id, stage_id FROM quality_checks")
        for row in cur.fetchall():
            keep_id = keep_map.get((row["order_id"], row["order_article_id"], row["stage_id"]))
            if keep_id is not None and row["id"] != keep_id:
                cur.execute("DELETE FROM quality_checks WHERE id = ?", (row["id"],))

    def seed_stages(self):
        with closing(self.conn.cursor()) as cur:
            cur.execute("SELECT COUNT(*) AS c FROM stages")
            if cur.fetchone()["c"] > 0:
                return
            cur.executemany(
                "INSERT INTO stages (stage_name, order_index) VALUES (?, ?)",
                DEFAULT_STAGES,
            )
        self.conn.commit()

    def list_stages(self):
        with closing(self.conn.cursor()) as cur:
            cur.execute("SELECT id, stage_name, order_index FROM stages ORDER BY order_index")
            return cur.fetchall()

    def list_order_articles(self, order_id: int):
        with closing(self.conn.cursor()) as cur:
            cur.execute(
                """
                SELECT id, order_id, article_number, item_name, material, item_weight, size, colours, quantity, created_at
                FROM order_articles
                WHERE order_id = ?
                ORDER BY id
                """,
                (order_id,),
            )
            return cur.fetchall()

    def export_dataset_snapshot(self, output_path: Path = SAMPLE_DATASET_PATH):
        with closing(self.conn.cursor()) as cur:
            cur.execute(
                """
                SELECT id, order_code, supplier_name, customer_name, order_category, order_purpose, order_note, order_date, order_placed_date, due_date, created_at
                FROM orders
                ORDER BY id
                """
            )
            orders = cur.fetchall()

            stage_name_map = {s["id"]: s["stage_name"] for s in self.list_stages()}
            payload = {"orders": []}
            for order in orders:
                order_id = order["id"]
                cur.execute(
                    """
                    SELECT id, article_number, item_name, material, item_weight, size, colours, quantity
                    FROM order_articles
                    WHERE order_id = ?
                    ORDER BY id
                    """,
                    (order_id,),
                )
                articles = cur.fetchall()
                article_items = []
                for art in articles:
                    cur.execute(
                        """
                        SELECT stage_id, status, note, updated_at
                        FROM order_article_stage_progress
                        WHERE order_article_id = ?
                        ORDER BY stage_id
                        """,
                        (art["id"],),
                    )
                    stage_progress = [
                        {
                            "stage_name": stage_name_map.get(r["stage_id"], f"Stage-{r['stage_id']}"),
                            "status": r["status"],
                            "note": r["note"] or "",
                            "updated_at": r["updated_at"],
                        }
                        for r in cur.fetchall()
                    ]
                    cur.execute(
                        """
                        SELECT stage_id, qc_result, inspector, defects_found, remarks, checked_at, qc_code
                        FROM quality_checks
                        WHERE order_id = ? AND order_article_id = ?
                        ORDER BY checked_at DESC, id DESC
                        """,
                        (order_id, art["id"]),
                    )
                    qcs = [
                        {
                            "stage_name": stage_name_map.get(r["stage_id"], f"Stage-{r['stage_id']}"),
                            "qc_result": r["qc_result"],
                            "inspector": r["inspector"] or "",
                            "defects_found": int(r["defects_found"] or 0),
                            "remarks": r["remarks"] or "",
                            "checked_at": r["checked_at"],
                            "qc_code": r["qc_code"] or "",
                        }
                        for r in cur.fetchall()
                    ]
                    article_items.append(
                        {
                            "article_number": art["article_number"],
                            "item_name": art["item_name"] or "",
                            "material": art["material"] or "",
                            "item_weight": art["item_weight"] or "",
                            "size": art["size"] or "",
                            "colours": art["colours"] or "",
                            "quantity": int(art["quantity"] or 0),
                            "stage_progress": stage_progress,
                            "quality_checks": qcs,
                        }
                    )

                payload["orders"].append(
                    {
                        "order_code": order["order_code"],
                        "supplier_name": order["supplier_name"] or "",
                        "customer_name": order["customer_name"],
                        "order_category": order["order_category"] or "",
                        "order_purpose": order["order_purpose"] or "",
                        "order_note": order["order_note"] or "",
                        "order_date": order["order_date"] or "",
                        "order_placed_date": order["order_placed_date"] or "",
                        "due_date": order["due_date"] or "",
                        "created_at": order["created_at"],
                        "articles": article_items,
                    }
                )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as fp:
            json.dump(payload, fp, indent=2)

    def add_order(
        self,
        order_code: str,
        supplier_name: str,
        customer: str,
        order_category: str,
        order_purpose: str,
        order_note: str,
        order_date: str,
        order_placed_date: str,
        due_date: str,
        articles: list,
    ):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        first_article = articles[0]["article_number"] if articles else "NA"
        total_qty = sum(max(1, int(a.get("quantity", 1))) for a in articles) if articles else 1
        internal_product_name = f"Article-{first_article}"
        with closing(self.conn.cursor()) as cur:
            cur.execute(
                """
                INSERT INTO orders (order_code, supplier_name, article_number, customer_name, order_category, order_purpose, order_note, product_name, quantity, order_date, order_placed_date, due_date, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_code,
                    supplier_name,
                    first_article,
                    customer,
                    order_category,
                    order_purpose,
                    order_note,
                    internal_product_name,
                    total_qty,
                    order_date,
                    order_placed_date,
                    due_date or None,
                    now,
                ),
            )
            order_id = cur.lastrowid
            stages = self.list_stages()
            for article in articles:
                cur.execute(
                    """
                    INSERT INTO order_articles (order_id, article_number, item_name, material, item_weight, size, colours, quantity, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        order_id,
                        article["article_number"],
                        article.get("item_name", ""),
                        article.get("material", ""),
                        article.get("item_weight", ""),
                        article.get("size", ""),
                        article.get("colours", ""),
                        int(article["quantity"]),
                        now,
                    ),
                )
                order_article_id = cur.lastrowid
                cur.executemany(
                    """
                    INSERT INTO order_article_stage_progress (order_article_id, stage_id, status, note, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    [(order_article_id, s["id"], STATUS_OPTIONS[0], "", now) for s in stages],
                )
        self.conn.commit()
        self.export_dataset_snapshot()

    def update_order(
        self,
        order_id: int,
        order_code: str,
        supplier_name: str,
        customer: str,
        order_category: str,
        order_purpose: str,
        order_note: str,
        order_date: str,
        order_placed_date: str,
        due_date: str,
        articles: list,
    ):
        first_article = articles[0]["article_number"] if articles else "NA"
        total_qty = sum(max(1, int(a.get("quantity", 1))) for a in articles) if articles else 1
        internal_product_name = f"Article-{first_article}"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with closing(self.conn.cursor()) as cur:
            cur.execute(
                """
                UPDATE orders
                SET order_code = ?, supplier_name = ?, article_number = ?, customer_name = ?, order_category = ?, order_purpose = ?, order_note = ?, product_name = ?,
                    quantity = ?, order_date = ?, order_placed_date = ?, due_date = ?
                WHERE id = ?
                """,
                (
                    order_code,
                    supplier_name,
                    first_article,
                    customer,
                    order_category,
                    order_purpose,
                    order_note,
                    internal_product_name,
                    total_qty,
                    order_date,
                    order_placed_date,
                    due_date or None,
                    order_id,
                ),
            )
            cur.execute("SELECT id FROM order_articles WHERE order_id = ?", (order_id,))
            old_article_ids = [r["id"] for r in cur.fetchall()]
            if old_article_ids:
                marks = ",".join("?" for _ in old_article_ids)
                cur.execute(f"DELETE FROM quality_checks WHERE order_article_id IN ({marks})", old_article_ids)
                cur.execute(f"DELETE FROM order_article_stage_progress WHERE order_article_id IN ({marks})", old_article_ids)
            cur.execute("DELETE FROM order_articles WHERE order_id = ?", (order_id,))
            stages = self.list_stages()
            for article in articles:
                cur.execute(
                    """
                    INSERT INTO order_articles (order_id, article_number, item_name, material, item_weight, size, colours, quantity, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        order_id,
                        article["article_number"],
                        article.get("item_name", ""),
                        article.get("material", ""),
                        article.get("item_weight", ""),
                        article.get("size", ""),
                        article.get("colours", ""),
                        int(article["quantity"]),
                        now,
                    ),
                )
                order_article_id = cur.lastrowid
                cur.executemany(
                    """
                    INSERT INTO order_article_stage_progress (order_article_id, stage_id, status, note, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    [(order_article_id, s["id"], STATUS_OPTIONS[0], "", now) for s in stages],
                )
        self.conn.commit()
        self.export_dataset_snapshot()

    def list_orders(self):
        with closing(self.conn.cursor()) as cur:
            cur.execute(
                """
                SELECT
                    o.id,
                    o.order_code,
                    o.supplier_name,
                    o.customer_name,
                    o.order_category,
                    o.order_purpose,
                    o.order_note,
                    o.order_date,
                    o.quantity,
                    o.order_placed_date,
                    o.due_date,
                    o.created_at,
                    COUNT(oa.id) AS article_count,
                    GROUP_CONCAT(oa.article_number, ', ') AS article_numbers
                FROM orders o
                LEFT JOIN order_articles oa ON oa.order_id = o.id
                GROUP BY o.id, o.order_code, o.supplier_name, o.customer_name, o.order_category, o.order_purpose, o.order_note, o.order_date, o.quantity, o.order_placed_date, o.due_date, o.created_at
                ORDER BY o.id DESC
                """
            )
            return cur.fetchall()

    def get_order_by_id(self, order_id: int):
        with closing(self.conn.cursor()) as cur:
            cur.execute(
                """
                SELECT id, order_code, supplier_name, article_number, customer_name, order_category, order_purpose, order_note, order_date, quantity, order_placed_date, due_date, created_at
                FROM orders
                WHERE id = ?
                """,
                (order_id,),
            )
            return cur.fetchone()

    def order_progress(self, order_id: int, order_article_id: int | None = None):
        with closing(self.conn.cursor()) as cur:
            if order_article_id is None:
                cur.execute("SELECT id FROM order_articles WHERE order_id = ? ORDER BY id LIMIT 1", (order_id,))
                art = cur.fetchone()
                if not art:
                    return []
                order_article_id = art["id"]
            cur.execute(
                """
                SELECT s.id AS stage_id, s.stage_name, osp.status, osp.note, osp.updated_at
                FROM stages s
                JOIN order_article_stage_progress osp ON osp.stage_id = s.id
                WHERE osp.order_article_id = ?
                ORDER BY s.order_index
                """,
                (order_article_id,),
            )
            return cur.fetchall()

    def update_stage(self, order_id: int, stage_id: int, status: str, note: str, order_article_id: int | None = None):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with closing(self.conn.cursor()) as cur:
            if order_article_id is None:
                cur.execute("SELECT id FROM order_articles WHERE order_id = ? ORDER BY id LIMIT 1", (order_id,))
                art = cur.fetchone()
                if not art:
                    return
                order_article_id = art["id"]
            cur.execute(
                """
                UPDATE order_article_stage_progress
                SET status = ?, note = ?, updated_at = ?
                WHERE order_article_id = ? AND stage_id = ?
                """,
                (status, note, now, order_article_id, stage_id),
            )
        self.conn.commit()
        self.export_dataset_snapshot()

    def add_quality_check(
        self,
        order_id: int,
        stage_id: int,
        qc_result: str,
        inspector: str,
        defects_found: int,
        remarks: str,
        order_article_id: int | None = None,
    ):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with closing(self.conn.cursor()) as cur:
            if order_article_id is None:
                cur.execute("SELECT id FROM order_articles WHERE order_id = ? ORDER BY id LIMIT 1", (order_id,))
                art = cur.fetchone()
                if not art:
                    return
                order_article_id = art["id"]
            # Single latest QC row per order-stage: overwrite the previous entry.
            cur.execute(
                """
                SELECT id, qc_code
                FROM quality_checks
                WHERE order_id = ? AND order_article_id = ? AND stage_id = ?
                ORDER BY checked_at DESC, id DESC
                LIMIT 1
                """,
                (order_id, order_article_id, stage_id),
            )
            latest = cur.fetchone()
            if latest:
                cur.execute(
                    """
                    UPDATE quality_checks
                    SET qc_result = ?, inspector = ?, defects_found = ?, remarks = ?, checked_at = ?
                    WHERE id = ?
                    """,
                    (qc_result, inspector.strip(), defects_found, remarks.strip(), now, latest["id"]),
                )
                if not (latest["qc_code"] or "").strip():
                    qc_code = self.build_qc_code(order_id, stage_id, latest["id"])
                    cur.execute("UPDATE quality_checks SET qc_code = ? WHERE id = ?", (qc_code, latest["id"]))
                cur.execute(
                    "DELETE FROM quality_checks WHERE order_id = ? AND order_article_id = ? AND stage_id = ? AND id <> ?",
                    (order_id, order_article_id, stage_id, latest["id"]),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO quality_checks (order_id, order_article_id, stage_id, qc_result, inspector, defects_found, remarks, checked_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (order_id, order_article_id, stage_id, qc_result, inspector.strip(), defects_found, remarks.strip(), now),
                )
                qc_id = cur.lastrowid
                qc_code = self.build_qc_code(order_id, stage_id, qc_id)
                cur.execute("UPDATE quality_checks SET qc_code = ? WHERE id = ?", (qc_code, qc_id))
        self.conn.commit()
        self.export_dataset_snapshot()

    def build_qc_code(self, order_id: int, stage_id: int, qc_id: int):
        return f"QC-{order_id:04d}-{stage_id:02d}-{qc_id:05d}"

    def list_quality_checks(self, order_id: int, order_article_id: int | None = None):
        with closing(self.conn.cursor()) as cur:
            if order_article_id is None:
                cur.execute("SELECT id FROM order_articles WHERE order_id = ? ORDER BY id LIMIT 1", (order_id,))
                art = cur.fetchone()
                if not art:
                    return []
                order_article_id = art["id"]
            cur.execute(
                """
                SELECT qc.qc_code, qc.id, qc.stage_id, s.stage_name, qc.qc_result, qc.inspector, qc.defects_found, qc.remarks, qc.checked_at
                FROM quality_checks qc
                JOIN stages s ON s.id = qc.stage_id
                WHERE qc.order_id = ? AND qc.order_article_id = ?
                ORDER BY qc.checked_at DESC, qc.id DESC
                """,
                (order_id, order_article_id),
            )
            return cur.fetchall()

    def qc_summary(self):
        with closing(self.conn.cursor()) as cur:
            cur.execute(
                """
                SELECT
                    qc.qc_result,
                    COUNT(*) AS check_count
                FROM quality_checks qc
                GROUP BY qc.qc_result
                ORDER BY check_count DESC
                """
            )
            return cur.fetchall()

    def quality_check_log(self):
        with closing(self.conn.cursor()) as cur:
            cur.execute(
                """
                SELECT
                    qc.qc_code,
                    qc.id,
                    qc.order_id,
                    o.order_code,
                    oa.article_number,
                    s.stage_name,
                    qc.qc_result,
                    qc.inspector,
                    qc.defects_found,
                    qc.remarks,
                    qc.checked_at
                FROM quality_checks qc
                JOIN orders o ON o.id = qc.order_id
                LEFT JOIN order_articles oa ON oa.id = qc.order_article_id
                JOIN stages s ON s.id = qc.stage_id
                ORDER BY qc.checked_at DESC, qc.id DESC
                """
            )
            return cur.fetchall()

    def load_sample_dataset(self, dataset_path: Path):
        if not dataset_path.exists():
            raise FileNotFoundError(f"Sample dataset file not found: {dataset_path}")
        with dataset_path.open("r", encoding="utf-8-sig") as fp:
            data = json.load(fp)

        with closing(self.conn.cursor()) as cur:
            cur.execute("DELETE FROM quality_checks")
            cur.execute("DELETE FROM order_article_stage_progress")
            cur.execute("DELETE FROM order_articles")
            cur.execute("DELETE FROM order_stage_progress")
            cur.execute("DELETE FROM orders")
            cur.execute("DELETE FROM sqlite_sequence WHERE name IN ('orders', 'order_articles', 'order_stage_progress', 'order_article_stage_progress', 'quality_checks')")

            stage_map = {row["stage_name"]: row["id"] for row in self.list_stages()}
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            order_id_by_code = {}

            for order in data.get("orders", []):
                articles_data = order.get("articles", [])
                if not articles_data:
                    articles_data = [
                        {
                            "article_number": order.get("article_number", "").strip() or "NA",
                            "item_name": order.get("item_name", "").strip(),
                            "material": order.get("material", "").strip(),
                            "item_weight": str(order.get("item_weight", "")).strip(),
                            "size": str(order.get("size", "")).strip(),
                            "colours": str(order.get("colours", "")).strip(),
                            "quantity": int(order.get("quantity", 1)),
                            "stage_progress": order.get("stage_progress", []),
                            "quality_checks": order.get("quality_checks", []),
                        }
                    ]
                total_qty = sum(int(a.get("quantity", 1) or 1) for a in articles_data)
                first_article = (articles_data[0].get("article_number", "").strip() if articles_data else "NA") or "NA"
                cur.execute(
                    """
                    INSERT INTO orders (order_code, supplier_name, article_number, customer_name, order_category, order_purpose, order_note, product_name, quantity, order_date, order_placed_date, due_date, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        order.get("order_code", "").strip(),
                        order.get("supplier_name", "").strip(),
                        first_article,
                        order.get("customer_name", "").strip(),
                        order.get("order_category", "").strip(),
                        order.get("order_purpose", "").strip(),
                        order.get("order_note", "").strip(),
                        f"Article-{first_article}",
                        total_qty,
                        order.get("order_date", "").strip(),
                        order.get("order_placed_date", "").strip(),
                        order.get("due_date", "").strip() or None,
                        order.get("created_at", now),
                    ),
                )
                order_id_by_code[order.get("order_code", "").strip()] = cur.lastrowid

            for order in data.get("orders", []):
                code = order.get("order_code", "").strip()
                order_id = order_id_by_code.get(code)
                if not order_id:
                    continue
                articles_data = order.get("articles", [])
                if not articles_data:
                    articles_data = [
                        {
                            "article_number": order.get("article_number", "").strip() or "NA",
                            "item_name": order.get("item_name", "").strip(),
                            "material": order.get("material", "").strip(),
                            "item_weight": str(order.get("item_weight", "")).strip(),
                            "size": str(order.get("size", "")).strip(),
                            "colours": str(order.get("colours", "")).strip(),
                            "quantity": int(order.get("quantity", 1)),
                            "stage_progress": order.get("stage_progress", []),
                            "quality_checks": order.get("quality_checks", []),
                        }
                    ]
                for article in articles_data:
                    article_number = (article.get("article_number", "").strip() or "NA")
                    qty = int(article.get("quantity", 1) or 1)
                    cur.execute(
                        """
                        INSERT INTO order_articles (order_id, article_number, item_name, material, item_weight, size, colours, quantity, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            order_id,
                            article_number,
                            article.get("item_name", "").strip(),
                            article.get("material", "").strip(),
                            str(article.get("item_weight", "")).strip(),
                            str(article.get("size", "")).strip(),
                            str(article.get("colours", "")).strip(),
                            qty,
                            now,
                        ),
                    )
                    order_article_id = cur.lastrowid

                    stage_items = article.get("stage_progress", [])
                    stage_status_by_name = {s.get("stage_name", "").strip(): s for s in stage_items}
                    for stage in self.list_stages():
                        cfg = stage_status_by_name.get(stage["stage_name"], {})
                        cur.execute(
                            """
                            INSERT INTO order_article_stage_progress (order_article_id, stage_id, status, note, updated_at)
                            VALUES (?, ?, ?, ?, ?)
                            """,
                            (
                                order_article_id,
                                stage["id"],
                                cfg.get("status", "In Progress"),
                                cfg.get("note", ""),
                                cfg.get("updated_at", now),
                            ),
                        )

                    for qc in article.get("quality_checks", []):
                        stage_name = qc.get("stage_name", "").strip()
                        stage_id = stage_map.get(stage_name)
                        if not stage_id:
                            continue
                        cur.execute(
                            """
                            INSERT INTO quality_checks (order_id, order_article_id, stage_id, qc_result, inspector, defects_found, remarks, checked_at, qc_code)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                order_id,
                                order_article_id,
                                stage_id,
                                qc.get("qc_result", "Pending"),
                                qc.get("inspector", "").strip(),
                                int(qc.get("defects_found", 0)),
                                qc.get("remarks", "").strip(),
                                qc.get("checked_at", now),
                                qc.get("qc_code", "").strip() or None,
                            ),
                        )

            self.normalize_quality_checks(cur)
            cur.execute("SELECT id, order_id, stage_id FROM quality_checks WHERE qc_code IS NULL OR TRIM(qc_code) = ''")
            for row in cur.fetchall():
                qc_code = self.build_qc_code(row["order_id"], row["stage_id"], row["id"])
                cur.execute("UPDATE quality_checks SET qc_code = ? WHERE id = ?", (qc_code, row["id"]))
        self.conn.commit()
        self.export_dataset_snapshot()


class OrderTrackingApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Order Tracking & Management System")
        self.setup_display_adaptivity()
        self.configure(bg="#f2f6fb")

        self.db = OrderDB(DB_PATH)
        self.selected_order_id = None
        self.selected_order_article_id = None
        self.editing_order_id = None
        self.qc_popup = None
        self.expanded_order_ids = set()
        self.expanded_dashboard_order_ids = set()
        self.dashboard_row_context = {}

        self.setup_styles()
        self.build_ui()
        self.setup_enter_navigation()
        self.refresh_all()

    def setup_display_adaptivity(self):
        # Improve rendering consistency on mixed-DPI displays.
        try:
            import ctypes
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

        sw = max(1024, int(self.winfo_screenwidth()))
        sh = max(700, int(self.winfo_screenheight()))

        # Keep window within visible work area on small/medium screens.
        target_w = max(980, min(1500, int(sw * 0.92)))
        target_h = max(620, min(920, int(sh * 0.90)))
        x = max(0, (sw - target_w) // 2)
        y = max(0, (sh - target_h) // 2)
        self.geometry(f"{target_w}x{target_h}+{x}+{y}")
        self.minsize(860, 560)

        # On smaller screens, start maximized to avoid clipped sections.
        if sw <= 1366 or sh <= 768:
            try:
                self.state("zoomed")
            except Exception:
                pass
    def setup_styles(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        # Refined, colorful-but-professional palette.
        page_bg = "#f2f6fb"
        panel_bg = "#ffffff"
        panel_alt = "#eef3fb"
        ink = "#0f172a"
        muted = "#4b5563"
        accent = "#0b5ed7"
        accent_active = "#0a58ca"

        style.configure("TFrame", background=page_bg)
        style.configure("TLabel", background=page_bg, foreground=ink, font=("Segoe UI", 10))
        style.configure("TLabelframe", background=panel_bg, borderwidth=1, relief="solid")
        style.configure("TLabelframe.Label", background=panel_bg, foreground=ink, font=("Segoe UI", 10, "bold"))

        style.configure("TButton", font=("Segoe UI", 10), padding=(10, 6), background=panel_alt)
        style.map("TButton", background=[("active", "#dbe8fb")])

        style.configure(
            "Primary.TButton",
            font=("Segoe UI Semibold", 10),
            padding=(12, 7),
            background=accent,
            foreground="#ffffff",
            borderwidth=0,
        )
        style.map(
            "Primary.TButton",
            background=[("active", accent_active), ("pressed", accent_active)],
            foreground=[("active", "#ffffff"), ("pressed", "#ffffff")],
        )

        style.configure("Secondary.TButton", font=("Segoe UI", 10), padding=(10, 6), background=panel_alt, foreground=ink)
        style.map("Secondary.TButton", background=[("active", "#dde8f8"), ("pressed", "#d6e2f5")])

        style.configure("TEntry", padding=4, fieldbackground="#ffffff")
        style.configure("TCombobox", padding=3)

        style.configure(
            "Treeview",
            rowheight=29,
            font=("Segoe UI", 10),
            background="#ffffff",
            fieldbackground="#ffffff",
            foreground=ink,
            borderwidth=0,
        )
        style.configure(
            "Treeview.Heading",
            font=("Segoe UI", 10, "bold"),
            background="#d6e4fa",
            foreground="#0b254a",
            relief="flat",
        )

        style.configure("TNotebook", background=page_bg, borderwidth=0)
        style.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=(14, 9), background="#dbe7f9", foreground="#243b5e")
        style.map(
            "TNotebook.Tab",
            background=[("selected", "#0b5ed7"), ("active", "#bcd2f4")],
            foreground=[("selected", "#ffffff"), ("active", "#102a43")],
        )

        style.configure("Header.TLabel", background=page_bg, foreground="#0b254a", font=("Segoe UI", 16, "bold"))
        style.configure("Subtle.TLabel", background=page_bg, foreground=muted, font=("Segoe UI", 9))

    def create_date_input(self, parent, textvariable, width=34):
        if DateEntry is not None:
            return DateEntry(
                parent,
                textvariable=textvariable,
                date_pattern="dd-mm-yyyy",
                width=width,
                state="readonly",
                firstweekday="monday",
                showweeknumbers=False,
                background="#2563eb",
                foreground="#ffffff",
                borderwidth=1,
                headersbackground="#dbeafe",
                headersforeground="#0f172a",
                weekendbackground="#f8fafc",
                weekendforeground="#1f2937",
            )
        return ttk.Entry(parent, textvariable=textvariable, width=width)

    def format_timestamp_to_date(self, value: str):
        raw = (value or "").strip()
        if not raw:
            return "-"
        for fmt in ("%Y-%m-%d %H:%M:%S", "%d-%m-%Y", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(raw, fmt)
                return dt.strftime("%d-%m-%Y")
            except ValueError:
                continue
        return raw

    def clear_tree(self, tree):
        for item in tree.get_children():
            tree.delete(item)

    def insert_tree_row(self, tree, values, tags=()):
        count = len(tree.get_children())
        stripe = "row_even" if count % 2 == 0 else "row_odd"
        # If a semantic status color tag exists, keep it dominant for clear dashboard signaling.
        final_tags = tuple(tags) if tags else (stripe,)
        tree.insert("", "end", values=values, tags=final_tags)

    def parse_colours_quantity(self, colours_text: str) -> int:
        total = 0
        raw = (colours_text or "").strip()
        if not raw:
            return 0
        for part in raw.split(","):
            token = part.strip()
            if not token:
                continue
            if ":" in token:
                qty_raw = token.rsplit(":", 1)[1].strip()
            elif "-" in token:
                qty_raw = token.rsplit("-", 1)[1].strip()
            else:
                continue
            try:
                qty = int(qty_raw)
            except ValueError:
                continue
            if qty > 0:
                total += qty
        return total

    def add_article_row(
        self,
        art_no: str = "",
        qty: str = "",
        item_name: str = "",
        material: str = "",
        item_weight: str = "",
        size: str = "",
        colours: str = "",
    ):
        row_wrap = ttk.Frame(self.articles_frame)
        row_wrap.pack(fill="x", pady=2)
        art_var = tk.StringVar(value=art_no)
        item_name_var = tk.StringVar(value=item_name)
        material_var = tk.StringVar(value=material)
        weight_var = tk.StringVar(value=item_weight)
        size_var = tk.StringVar(value=size)
        colours_var = tk.StringVar(value=colours)
        qty_var = tk.StringVar(value=qty)
        art_entry = ttk.Entry(row_wrap, textvariable=art_var, width=14)
        item_entry = ttk.Entry(row_wrap, textvariable=item_name_var, width=12)
        material_entry = ttk.Entry(row_wrap, textvariable=material_var, width=12)
        weight_entry = ttk.Entry(row_wrap, textvariable=weight_var, width=9)
        size_entry = ttk.Entry(row_wrap, textvariable=size_var, width=7)
        colours_entry = ttk.Entry(row_wrap, textvariable=colours_var, width=20)
        qty_entry = ttk.Entry(row_wrap, textvariable=qty_var, width=7)
        art_entry.pack(side="left", padx=(0, 6))
        item_entry.pack(side="left", padx=(0, 6))
        material_entry.pack(side="left", padx=(0, 6))
        weight_entry.pack(side="left", padx=(0, 6))
        size_entry.pack(side="left", padx=(0, 6))
        colours_entry.pack(side="left", padx=(0, 6), fill="x", expand=True)
        qty_entry.pack(side="left")
        self.article_rows.append((row_wrap, art_var, item_name_var, material_var, weight_var, size_var, colours_var, qty_var))
        qty_entry.bind("<FocusOut>", self.on_article_qty_focus_out)
        qty_entry.bind("<Return>", self.on_article_qty_enter)
        colours_entry.bind("<FocusOut>", self.on_article_qty_focus_out)
        colours_entry.bind("<Return>", self.on_article_qty_enter)

    def on_article_qty_focus_out(self, _event):
        self.ensure_article_input_tail()

    def on_article_qty_enter(self, _event):
        self.ensure_article_input_tail()
        return "break"

    def ensure_article_input_tail(self):
        if not self.article_rows:
            self.add_article_row()
            return
        last = self.article_rows[-1]
        qty_or_colour = last[7].get().strip() or last[6].get().strip()
        if last[1].get().strip() and qty_or_colour:
            self.add_article_row()

    def collect_article_inputs(self):
        items = []
        for _row_wrap, art_var, item_name_var, material_var, weight_var, size_var, colours_var, qty_var in self.article_rows:
            art = art_var.get().strip()
            item_name = item_name_var.get().strip()
            material = material_var.get().strip()
            item_weight = weight_var.get().strip()
            size = size_var.get().strip()
            colours = colours_var.get().strip()
            qty_raw = qty_var.get().strip()
            if not art and not qty_raw and not any([item_name, material, item_weight, size, colours]):
                continue
            if not art:
                raise ValueError("Art No is missing in one article row.")
            if not size:
                raise ValueError(f"Size is required for Art No '{art}'.")
            if qty_raw:
                try:
                    qty = int(qty_raw)
                    if qty < 1:
                        raise ValueError
                except ValueError:
                    raise ValueError(f"Quantity for Art No '{art}' must be a positive integer.")
            else:
                qty = self.parse_colours_quantity(colours)
                if qty < 1:
                    raise ValueError(f"Enter quantity or parseable colours qty for Art No '{art}' (example: Gold:2, Copper:3).")
            items.append(
                {
                    "article_number": art,
                    "item_name": item_name,
                    "material": material,
                    "item_weight": item_weight,
                    "size": size,
                    "colours": colours,
                    "quantity": qty,
                }
            )
        if not items:
            raise ValueError("At least one Art No with quantity is required.")
        return items

    def setup_enter_navigation(self):
        self.bind_class("TEntry", "<Return>", self.focus_next_widget)
        self.bind_class("TCombobox", "<Return>", self.focus_next_widget)
        self.bind_class("DateEntry", "<Return>", self.focus_next_widget)
        self.bind_class("TEntry", "<Down>", self.focus_next_widget)
        self.bind_class("TCombobox", "<Down>", self.focus_next_widget)
        self.bind_class("DateEntry", "<Down>", self.focus_next_widget)
        self.bind_class("TButton", "<Down>", self.focus_next_widget)
        self.bind_class("TEntry", "<Up>", self.focus_prev_widget)
        self.bind_class("TCombobox", "<Up>", self.focus_prev_widget)
        self.bind_class("DateEntry", "<Up>", self.focus_prev_widget)
        self.bind_class("TButton", "<Up>", self.focus_prev_widget)

    def focus_next_widget(self, event):
        next_widget = event.widget.tk_focusNext()
        if next_widget is not None:
            next_widget.focus_set()
        return "break"

    def focus_prev_widget(self, event):
        prev_widget = event.widget.tk_focusPrev()
        if prev_widget is not None:
            prev_widget.focus_set()
        return "break"

    def on_add_order_enter(self, _event):
        self.handle_add_order()
        return "break"

    def on_update_stage_enter(self, _event):
        self.handle_update_stage()
        return "break"

    def on_save_qc_enter(self, _event):
        self.handle_save_qc()
        return "break"

    def on_show_stage_status_enter(self, _event):
        self.handle_dashboard_lookup()
        return "break"

    def on_save_stage_note_enter(self, _event):
        self.handle_save_stage_note()
        return "break"

    def build_ui(self):
        heading = ttk.Label(self, text="Order Tracking and Management", style="Header.TLabel")
        heading.pack(anchor="w", padx=14, pady=(10, 0))

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=10)

        self.orders_tab = ttk.Frame(self.notebook, padding=6)
        self.qc_tab = ttk.Frame(self.notebook, padding=6)
        self.dashboard_tab = ttk.Frame(self.notebook, padding=6)

        self.notebook.add(self.dashboard_tab, text="Dashboard")
        self.notebook.add(self.orders_tab, text="Orders & Stages")
        self.notebook.add(self.qc_tab, text="Quality Checks")

        self.build_dashboard_tab()
        self.build_orders_tab()
        self.build_qc_tab()
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

    def build_orders_tab(self):
        left = ttk.Frame(self.orders_tab)
        right = ttk.Frame(self.orders_tab)
        left.pack(side="left", fill="both", expand=True, padx=6, pady=6)
        right.pack(side="right", fill="both", expand=True, padx=6, pady=6)

        form = ttk.LabelFrame(left, text="Add / Edit Order")
        form.pack(fill="x", pady=(0, 8))

        self.order_code_var = tk.StringVar()
        self.supplier_var = tk.StringVar()
        self.customer_var = tk.StringVar()
        self.order_category_var = tk.StringVar(value="Regular")
        self.order_purpose_var = tk.StringVar(value="Stock Purpose")
        self.order_note_var = tk.StringVar()
        self.order_date_var = tk.StringVar()
        self.placed_date_var = tk.StringVar()
        self.due_var = tk.StringVar()

        fields = [
            ("Order Code", self.order_code_var),
            ("Supplier Name", self.supplier_var),
            ("Customer Name", self.customer_var),
            ("Order Category", self.order_category_var),
            ("Order Purpose", self.order_purpose_var),
            ("Order Date (DD-MM-YYYY)", self.order_date_var),
            ("Order Placed Date (DD-MM-YYYY)", self.placed_date_var),
            ("Required Date (DD-MM-YYYY)", self.due_var),
        ]
        self.order_form_entries = []
        for i, (label, var) in enumerate(fields):
            ttk.Label(form, text=label).grid(row=i, column=0, padx=6, pady=4, sticky="w")
            if "Date" in label:
                entry = self.create_date_input(form, var, width=34)
            elif label in ("Order Category", "Order Purpose"):
                entry = ttk.Combobox(form, textvariable=var, width=32)
                if label == "Order Category":
                    entry["values"] = ["Regular", "Urgent", "Custom", "Sample"]
                else:
                    entry["values"] = ["Stock Purpose", "Customer Order", "Rework", "Trial"]
            else:
                entry = ttk.Entry(form, textvariable=var, width=34)
            entry.grid(row=i, column=1, padx=6, pady=4, sticky="we")
            self.order_form_entries.append(entry)

        article_row = len(fields)
        ttk.Label(form, text="Order Note").grid(row=article_row, column=0, padx=6, pady=4, sticky="w")
        self.order_note_entry = ttk.Entry(form, textvariable=self.order_note_var, width=34)
        self.order_note_entry.grid(row=article_row, column=1, padx=6, pady=4, sticky="we")
        article_row += 1

        ttk.Label(
            form,
            text="Articles (Art No + Item + Material +\nWeight + Size + Colours + Qty)",
        ).grid(row=article_row, column=0, padx=6, pady=4, sticky="nw")
        self.articles_frame = ttk.Frame(form)
        self.articles_frame.grid(row=article_row, column=1, padx=6, pady=4, sticky="we")
        header = ttk.Frame(self.articles_frame)
        header.pack(fill="x", pady=(0, 2))
        for lbl, w in [
            ("Art No", 14),
            ("Item", 12),
            ("Material", 12),
            ("Weight", 9),
            ("Size", 7),
            ("Colours (Gold:2, ...)", 20),
            ("Qty", 7),
        ]:
            ttk.Label(header, text=lbl, width=w).pack(side="left", padx=(0, 6))
        self.article_rows = []
        self.add_article_row()
        ttk.Button(form, text="Add Art No", command=self.add_article_row, style="Secondary.TButton").grid(
            row=article_row + 1, column=1, padx=6, pady=(0, 4), sticky="w"
        )
        if DateEntry is None:
            ttk.Label(
                form,
                text="Install 'tkcalendar' for calendar picker: pip install tkcalendar",
                style="Subtle.TLabel",
            ).grid(row=article_row + 2, column=0, columnspan=2, padx=6, pady=(0, 2), sticky="w")
        form.columnconfigure(1, weight=1)

        self.add_order_btn = ttk.Button(form, text="Add Order", command=self.handle_add_order, style="Primary.TButton")
        self.add_order_btn.grid(
            row=article_row + 3, column=0, columnspan=2, padx=6, pady=8, sticky="we"
        )
        self.update_order_btn = ttk.Button(form, text="Update Order", command=self.handle_update_order, style="Primary.TButton")
        self.update_order_btn.grid(
            row=article_row + 4, column=0, padx=6, pady=(0, 8), sticky="we"
        )
        self.clear_form_btn = ttk.Button(form, text="Clear Form", command=self.clear_order_form, style="Secondary.TButton")
        self.clear_form_btn.grid(
            row=article_row + 4, column=1, padx=6, pady=(0, 8), sticky="we"
        )
        self.export_order_btn = ttk.Button(form, text="Export Production CSV", command=self.handle_export_production_csv, style="Secondary.TButton")
        self.export_order_btn.grid(
            row=article_row + 5, column=0, columnspan=2, padx=6, pady=(0, 8), sticky="we"
        )
        self.update_order_btn.state(["disabled"])
        if self.order_form_entries:
            self.order_form_entries[-1].bind("<Return>", self.on_add_order_enter)

        orders_box = ttk.LabelFrame(left, text="Orders")
        orders_box.pack(fill="both", expand=True)

        self.orders_tree = ttk.Treeview(
            orders_box,
            columns=("id", "code", "article", "customer", "qty", "placed", "due", "details"),
            show="headings",
            selectmode="browse",
        )
        for col, text, width in [
            ("id", "ID", 45),
            ("code", "Order Code", 110),
            ("article", "Article No", 200),
            ("customer", "Customer", 160),
            ("qty", "Qty", 60),
            ("placed", "Placed Date", 110),
            ("due", "Due", 110),
            ("details", "", 55),
        ]:
            self.orders_tree.heading(col, text=text)
            self.orders_tree.column(col, width=width, anchor="w")
        orders_scroll = ttk.Scrollbar(orders_box, orient="vertical", command=self.orders_tree.yview)
        self.orders_tree.configure(yscrollcommand=orders_scroll.set)
        self.orders_tree.tag_configure("row_even", background="#ffffff")
        self.orders_tree.tag_configure("row_odd", background="#f8fafc")
        self.orders_tree.tag_configure("detail_row", background="#eef4ff", foreground="#334155")
        self.orders_tree.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        orders_scroll.pack(side="right", fill="y", padx=(0, 4), pady=4)
        self.orders_tree.bind("<<TreeviewSelect>>", self.on_order_selected)
        self.orders_tree.bind("<ButtonRelease-1>", self.on_orders_tree_click)

        stage_box = ttk.LabelFrame(right, text="Stage Tracking")
        stage_box.pack(fill="both", expand=True)

        article_pick = ttk.Frame(stage_box)
        article_pick.pack(fill="x", padx=4, pady=(4, 2))
        ttk.Label(article_pick, text="Art No").pack(side="left")
        self.stage_article_var = tk.StringVar()
        self.stage_article_combo = ttk.Combobox(article_pick, textvariable=self.stage_article_var, state="readonly", width=28)
        self.stage_article_combo.pack(side="left", padx=6)
        self.stage_article_combo.bind("<<ComboboxSelected>>", self.on_stage_article_changed)
        ttk.Label(article_pick, text="Status Filter").pack(side="left", padx=(10, 4))
        self.stage_filter_var = tk.StringVar(value="All")
        self.stage_filter_combo = ttk.Combobox(
            article_pick,
            textvariable=self.stage_filter_var,
            state="readonly",
            width=14,
            values=["All", "In Progress", "Blocked", "Completed"],
        )
        self.stage_filter_combo.pack(side="left")
        self.stage_filter_combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh_stage_progress())

        self.stage_tree = ttk.Treeview(
            stage_box,
            columns=("stage_id", "stage_name", "status", "updated", "note"),
            show="headings",
            selectmode="browse",
        )
        for col, text, width in [
            ("stage_id", "Stage ID", 70),
            ("stage_name", "Stage", 220),
            ("status", "Status", 100),
            ("updated", "Updated Date", 145),
            ("note", "Note", 210),
        ]:
            self.stage_tree.heading(col, text=text)
            self.stage_tree.column(col, width=width, anchor="w")
        stage_scroll = ttk.Scrollbar(stage_box, orient="vertical", command=self.stage_tree.yview)
        self.stage_tree.configure(yscrollcommand=stage_scroll.set)
        self.stage_tree.tag_configure("row_even", background="#ffffff")
        self.stage_tree.tag_configure("row_odd", background="#f8fafc")
        self.stage_tree.tag_configure("stage_in_progress", foreground="#1d4ed8")
        self.stage_tree.tag_configure("stage_blocked", foreground="#b91c1c")
        self.stage_tree.tag_configure("stage_completed", foreground="#047857")
        self.stage_tree.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=(0, 4))
        stage_scroll.pack(side="right", fill="y", padx=(0, 4), pady=4)
        self.stage_tree.bind("<ButtonRelease-1>", self.on_stage_tree_click)
        self.stage_tree.bind("<<TreeviewSelect>>", self.on_stage_selected)

        detail_box = ttk.LabelFrame(stage_box, text="Stage Details")
        detail_box.pack(fill="x", padx=4, pady=(2, 4))
        note_edit = ttk.Frame(detail_box)
        note_edit.pack(fill="x", padx=4, pady=(4, 0))
        ttk.Label(note_edit, text="Edit Note").pack(side="left")
        self.stage_note_edit_var = tk.StringVar()
        self.stage_note_edit_entry = ttk.Entry(note_edit, textvariable=self.stage_note_edit_var, width=48)
        self.stage_note_edit_entry.pack(side="left", fill="x", expand=True, padx=6)
        self.stage_note_edit_entry.bind("<Return>", self.on_save_stage_note_enter)
        self.stage_note_save_btn = ttk.Button(
            note_edit,
            text="Save Note",
            command=self.handle_save_stage_note,
            style="Primary.TButton",
        )
        self.stage_note_save_btn.pack(side="left")

        self.stage_detail_text = tk.Text(
            detail_box,
            height=5,
            wrap="word",
            bg="#ffffff",
            fg="#1f2937",
            relief="solid",
            borderwidth=1,
            font=("Consolas", 10),
        )
        self.stage_detail_text.pack(fill="x", padx=4, pady=4)

    def build_qc_tab(self):
        self.qc_selected_order_label_var = tk.StringVar(value="Selected Order: None")
        context = ttk.Frame(self.qc_tab)
        context.pack(fill="x", padx=8, pady=(4, 6))
        ttk.Label(context, textvariable=self.qc_selected_order_label_var).pack(side="left")
        ttk.Button(context, text="Go to Orders Tab", command=self.go_to_orders_tab, style="Secondary.TButton").pack(side="right")

        top = ttk.LabelFrame(self.qc_tab, text="Record Quality Check")
        top.pack(fill="x", padx=8, pady=(8, 10))

        self.qc_stage_var = tk.StringVar()
        self.qc_article_var = tk.StringVar()
        self.qc_result_var = tk.StringVar(value=QC_RESULTS[0])
        self.inspector_var = tk.StringVar()
        self.defects_var = tk.StringVar(value="0")
        self.remarks_var = tk.StringVar()

        ttk.Label(top, text="Art No").grid(row=0, column=0, padx=6, pady=6)
        self.qc_article_combo = ttk.Combobox(top, textvariable=self.qc_article_var, state="readonly", width=24)
        self.qc_article_combo.grid(row=0, column=1, padx=6, pady=6, sticky="w")
        self.qc_article_combo.bind("<<ComboboxSelected>>", self.on_qc_article_changed)

        ttk.Label(top, text="Stage").grid(row=0, column=2, padx=6, pady=6)
        self.qc_stage_combo = ttk.Combobox(top, textvariable=self.qc_stage_var, state="readonly", width=30)
        self.qc_stage_combo.grid(row=0, column=3, padx=6, pady=6)

        ttk.Label(top, text="QC Result").grid(row=1, column=0, padx=6, pady=6)
        ttk.Combobox(top, textvariable=self.qc_result_var, values=QC_RESULTS, state="readonly", width=16).grid(
            row=1, column=1, padx=6, pady=6, sticky="w"
        )

        ttk.Label(top, text="Inspector").grid(row=1, column=2, padx=6, pady=6)
        ttk.Entry(top, textvariable=self.inspector_var, width=32).grid(row=1, column=3, padx=6, pady=6)

        ttk.Label(top, text="Defects Found").grid(row=2, column=0, padx=6, pady=6)
        ttk.Entry(top, textvariable=self.defects_var, width=18).grid(row=2, column=1, padx=6, pady=6, sticky="w")

        ttk.Label(top, text="Remarks").grid(row=2, column=2, padx=6, pady=6)
        self.qc_remarks_entry = ttk.Entry(top, textvariable=self.remarks_var, width=76)
        self.qc_remarks_entry.grid(row=2, column=3, padx=6, pady=6, sticky="we")

        self.save_qc_btn = ttk.Button(top, text="Save Quality Check", command=self.handle_save_qc, style="Primary.TButton")
        self.save_qc_btn.grid(
            row=3, column=0, columnspan=4, padx=6, pady=8, sticky="we"
        )
        self.qc_remarks_entry.bind("<Return>", self.on_save_qc_enter)

        table_box = ttk.LabelFrame(self.qc_tab, text="Quality Check History (Selected Order)")
        table_box.pack(fill="both", expand=True, padx=8, pady=8)

        self.qc_tree = ttk.Treeview(
            table_box,
            columns=("qc_id", "stage", "result", "inspector", "defects", "remarks", "checked"),
            show="headings",
        )
        for col, text, width in [
            ("qc_id", "QC ID", 140),
            ("stage", "Stage", 200),
            ("result", "Result", 90),
            ("inspector", "Inspector", 130),
            ("defects", "Defects", 70),
            ("remarks", "Remarks", 260),
            ("checked", "Checked At", 145),
        ]:
            self.qc_tree.heading(col, text=text)
            self.qc_tree.column(col, width=width, anchor="w")
        qc_scroll = ttk.Scrollbar(table_box, orient="vertical", command=self.qc_tree.yview)
        self.qc_tree.configure(yscrollcommand=qc_scroll.set)
        self.qc_tree.tag_configure("row_even", background="#ffffff")
        self.qc_tree.tag_configure("row_odd", background="#f8fafc")
        self.qc_tree.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        qc_scroll.pack(side="right", fill="y", padx=(0, 4), pady=4)

        ttk.Label(
            self.qc_tab,
            text="Select an order in 'Orders & Stages' first, then log QC checks at any stage.",
            foreground="#444",
        ).pack(anchor="w", padx=10, pady=(0, 8))

    def build_dashboard_tab(self):
        kpi_wrap = ttk.Frame(self.dashboard_tab)
        kpi_wrap.pack(fill="x", padx=8, pady=(8, 6))
        self.kpi_total_var = tk.StringVar(value="Total Orders: 0")
        self.kpi_in_progress_var = tk.StringVar(value="In Progress: 0")
        self.kpi_completed_var = tk.StringVar(value="Completed: 0")
        self.kpi_blocked_var = tk.StringVar(value="Blocked: 0")
        self.kpi_overdue_var = tk.StringVar(value="Overdue: 0")
        for idx, var in enumerate(
            [
                self.kpi_total_var,
                self.kpi_in_progress_var,
                self.kpi_completed_var,
                self.kpi_blocked_var,
                self.kpi_overdue_var,
            ]
        ):
            card = ttk.LabelFrame(kpi_wrap, text="KPI")
            card.grid(row=0, column=idx, padx=4, pady=4, sticky="nsew")
            ttk.Label(card, textvariable=var, font=("Segoe UI", 10, "bold")).pack(padx=10, pady=8)
            kpi_wrap.columnconfigure(idx, weight=1)

        self.dashboard_selected_order_label_var = tk.StringVar(value="Selected Order: None")
        context = ttk.Frame(self.dashboard_tab)
        context.pack(fill="x", padx=8, pady=(0, 6))
        ttk.Label(context, textvariable=self.dashboard_selected_order_label_var).pack(side="left")
        ttk.Button(
            context,
            text="Load Sample Dataset",
            command=self.handle_load_sample_dataset,
            style="Secondary.TButton",
        ).pack(side="right")
        ttk.Button(context, text="Use Selected Order", command=self.use_selected_order_in_dashboard, style="Secondary.TButton").pack(side="right")

        self.exc_blocked_var = tk.StringVar(value="Blocked: 0")
        self.exc_overdue_var = tk.StringVar(value="Overdue: 0")
        self.exc_due_today_var = tk.StringVar(value="Due Today: 0")
        exceptions_box = ttk.LabelFrame(self.dashboard_tab, text="Exception Panel")
        exceptions_box.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(
            exceptions_box,
            textvariable=self.exc_blocked_var,
            command=lambda: self.apply_dashboard_quick_filter("Blocked"),
        ).pack(side="left", padx=6, pady=6)
        ttk.Button(
            exceptions_box,
            textvariable=self.exc_overdue_var,
            command=lambda: self.apply_dashboard_quick_filter("Overdue"),
        ).pack(side="left", padx=6, pady=6)
        ttk.Button(
            exceptions_box,
            textvariable=self.exc_due_today_var,
            command=lambda: self.apply_dashboard_quick_filter("Due Today"),
        ).pack(side="left", padx=6, pady=6)
        ttk.Button(
            exceptions_box,
            text="Show All",
            command=lambda: self.apply_dashboard_quick_filter("All"),
        ).pack(side="left", padx=6, pady=6)

        filter_box = ttk.LabelFrame(self.dashboard_tab, text="Order Overview Filters")
        filter_box.pack(fill="x", padx=8, pady=(0, 8))
        self.dashboard_filter_var = tk.StringVar(value="All")
        self.dashboard_search_var = tk.StringVar()
        ttk.Label(filter_box, text="Status").grid(row=0, column=0, padx=6, pady=6)
        self.dashboard_filter_combo = ttk.Combobox(
            filter_box,
            textvariable=self.dashboard_filter_var,
            state="readonly",
            width=16,
            values=["All", "In Progress", "Completed", "Blocked", "Overdue", "Due Today"],
        )
        self.dashboard_filter_combo.grid(row=0, column=1, padx=6, pady=6)
        ttk.Label(filter_box, text="Search").grid(row=0, column=2, padx=6, pady=6)
        self.dashboard_search_entry = ttk.Entry(filter_box, textvariable=self.dashboard_search_var, width=36)
        self.dashboard_search_entry.grid(row=0, column=3, padx=6, pady=6, sticky="we")
        self.dashboard_search_entry.bind("<Return>", lambda _e: self.refresh_dashboard())
        ttk.Button(filter_box, text="Apply", command=self.refresh_dashboard, style="Primary.TButton").grid(row=0, column=4, padx=6, pady=6)
        ttk.Button(filter_box, text="Clear", command=self.clear_dashboard_filters, style="Secondary.TButton").grid(row=0, column=5, padx=6, pady=6)
        filter_box.columnconfigure(3, weight=1)

        overview_box = ttk.LabelFrame(self.dashboard_tab, text="All Orders Overview")
        overview_box.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.dashboard_tree = ttk.Treeview(
            overview_box,
            columns=(
                "id",
                "code",
                "supplier",
                "art",
                "customer",
                "category",
                "purpose",
                "qty",
                "placed",
                "due",
                "due_state",
                "current_stage",
                "stage_status",
                "blocked_summary",
                "progress",
                "blocked_view",
            ),
            show="headings",
            selectmode="browse",
        )
        for col, text, width in [
            ("id", "Order ID", 55),
            ("code", "Order Code", 70),
            ("supplier", "Supplier", 110),
            ("art", "Art No", 70),
            ("customer", "Customer", 115),
            ("category", "Category", 85),
            ("purpose", "Purpose", 95),
            ("qty", "Grand Qty", 75),
            ("placed", "Placed Date", 90),
            ("due", "Due Date", 85),
            ("due_state", "Due", 75),
            ("current_stage", "Current Stage", 135),
            ("stage_status", "Stage", 80),
            ("blocked_summary", "Blocked Info", 320),
            ("progress", "Progress %", 70),
            ("blocked_view", "View", 70),
        ]:
            self.dashboard_tree.heading(col, text=text)
            self.dashboard_tree.column(col, width=width, anchor="w")
        self.dashboard_tree.tag_configure("row_even", background="#ffffff")
        self.dashboard_tree.tag_configure("row_odd", background="#f8fafc")
        self.dashboard_tree.tag_configure("status_blocked", background="#fde2e2")
        self.dashboard_tree.tag_configure("status_overdue", background="#fff1d6")
        self.dashboard_tree.tag_configure("status_due_today", background="#fff9db")
        self.dashboard_tree.tag_configure("status_completed", background="#e6f6ea")
        self.dashboard_tree.tag_configure("status_in_progress", background="#e8f1ff")
        self.dashboard_tree.tag_configure("status_on_track", background="#edf7f0")
        self.dashboard_tree.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=(4, 0))
        self.dashboard_tree.bind("<<TreeviewSelect>>", self.on_dashboard_order_selected)
        self.dashboard_tree.bind("<Double-1>", self.on_dashboard_order_double_click)
        self.dashboard_tree.bind("<ButtonRelease-1>", self.on_dashboard_tree_click)

        lookup_box = ttk.LabelFrame(self.dashboard_tab, text="Track Order by Order ID")
        lookup_box.pack(fill="x", padx=8, pady=(0, 10))

        self.dashboard_order_id_var = tk.StringVar()
        ttk.Label(lookup_box, text="Order ID").grid(row=0, column=0, padx=6, pady=6)
        self.dashboard_order_id_entry = ttk.Entry(lookup_box, textvariable=self.dashboard_order_id_var, width=18)
        self.dashboard_order_id_entry.grid(row=0, column=1, padx=6, pady=6)
        self.show_stage_status_btn = ttk.Button(lookup_box, text="Show Stage Status", command=self.handle_dashboard_lookup, style="Primary.TButton")
        self.show_stage_status_btn.grid(
            row=0, column=2, padx=6, pady=6
        )
        self.dashboard_order_id_entry.bind("<Return>", self.on_show_stage_status_enter)

        self.order_lookup_text = tk.Text(
            self.dashboard_tab,
            height=9,
            wrap="word",
            bg="#ffffff",
            fg="#1f2937",
            relief="solid",
            borderwidth=1,
            font=("Consolas", 10),
        )
        self.order_lookup_text.pack(fill="x", padx=8, pady=(0, 6))

        ttk.Label(self.dashboard_tab, text="Quality Check Snapshot", font=("Segoe UI", 11, "bold")).pack(
            anchor="w", padx=8, pady=6
        )
        summary_wrap = ttk.Frame(self.dashboard_tab)
        summary_wrap.pack(fill="x", padx=8, pady=(0, 6))
        self.summary_text = tk.Text(
            summary_wrap,
            height=5,
            wrap="word",
            bg="#ffffff",
            fg="#1f2937",
            relief="solid",
            borderwidth=1,
            font=("Consolas", 10),
        )
        summary_scroll = ttk.Scrollbar(summary_wrap, orient="vertical", command=self.summary_text.yview)
        self.summary_text.configure(yscrollcommand=summary_scroll.set)
        self.summary_text.pack(side="left", fill="both", expand=True)
        summary_scroll.pack(side="right", fill="y")

        ttk.Button(self.dashboard_tab, text="Refresh Dashboard", command=self.refresh_dashboard, style="Secondary.TButton").pack(anchor="w", padx=8, pady=6)

    def refresh_orders(self):
        self.clear_tree(self.orders_tree)
        rows = self.db.list_orders()
        for row in rows:
            articles = self.db.list_order_articles(row["id"])
            if len(articles) <= 2:
                article_text = ", ".join(a["article_number"] for a in articles) if articles else "-"
            else:
                shown = ", ".join(a["article_number"] for a in articles[:2])
                article_text = f"{shown} ... +{len(articles) - 2} more"
            self.insert_tree_row(
                self.orders_tree,
                (
                    row["id"],
                    row["order_code"],
                    article_text,
                    row["customer_name"],
                    row["quantity"],
                    row["order_placed_date"] or "-",
                    row["due_date"] or "-",
                    "Hide <" if row["id"] in self.expanded_order_ids else "View >",
                ),
            )
            if row["id"] in self.expanded_order_ids:
                for art in articles:
                    self.insert_tree_row(
                        self.orders_tree,
                        (
                            "",
                            "Art Detail",
                            f"{art['article_number']} | {art['item_name'] or '-'} | {art['material'] or '-'} | Size {art['size'] or '-'}",
                            f"Colours: {art['colours'] or '-'}",
                            art["quantity"],
                            "",
                            "",
                            "",
                        ),
                        tags=("detail_row",),
                    )

    def on_orders_tree_click(self, event):
        row_id = self.orders_tree.identify_row(event.y)
        if not row_id:
            return
        col_id = self.orders_tree.identify_column(event.x)
        if col_id != "#8":
            return
        if "detail_row" in self.orders_tree.item(row_id, "tags"):
            return
        values = self.orders_tree.item(row_id, "values")
        if not values:
            return
        order_id = int(values[0])
        if order_id in self.expanded_order_ids:
            self.expanded_order_ids.remove(order_id)
        else:
            self.expanded_order_ids.add(order_id)
        self.refresh_orders()
        self.select_order_row_by_id(order_id)

    def refresh_article_selectors(self):
        if not self.selected_order_id:
            self.selected_order_article_id = None
            self.stage_article_combo["values"] = []
            self.qc_article_combo["values"] = []
            self.stage_article_var.set("")
            self.qc_article_var.set("")
            self.stage_article_map = {}
            self.qc_article_map = {}
            return
        articles = self.db.list_order_articles(self.selected_order_id)
        if not articles:
            self.selected_order_article_id = None
            self.stage_article_combo["values"] = []
            self.qc_article_combo["values"] = []
            self.stage_article_var.set("")
            self.qc_article_var.set("")
            self.stage_article_map = {}
            self.qc_article_map = {}
            return

        self.stage_article_map = {}
        display_values = []
        label_count = {}
        for a in articles:
            base_label = f"{a['article_number']} (Qty {a['quantity']})"
            label_count[base_label] = label_count.get(base_label, 0) + 1
            display_label = base_label if label_count[base_label] == 1 else f"{base_label} (duplicate {label_count[base_label]})"
            display_values.append(display_label)
            self.stage_article_map[display_label] = a["id"]
        self.qc_article_map = dict(self.stage_article_map)
        self.stage_article_combo["values"] = display_values
        self.qc_article_combo["values"] = display_values
        article_id_set = {a["id"] for a in articles}
        if self.selected_order_article_id not in article_id_set:
            self.selected_order_article_id = articles[0]["id"]
        selected_display = next((label for label, aid in self.stage_article_map.items() if aid == self.selected_order_article_id), display_values[0])
        self.stage_article_var.set(selected_display)
        self.qc_article_var.set(selected_display)

    def on_stage_article_changed(self, _event):
        value = self.stage_article_var.get().strip()
        if not value:
            return
        article_id = self.stage_article_map.get(value)
        if not article_id:
            return
        self.selected_order_article_id = article_id
        self.qc_article_var.set(value)
        self.refresh_stage_progress()
        self.refresh_qc_history()
        self.update_stage_detail_panel()

    def on_qc_article_changed(self, _event):
        value = self.qc_article_var.get().strip()
        if not value:
            return
        article_id = self.qc_article_map.get(value)
        if not article_id:
            return
        self.selected_order_article_id = article_id
        self.stage_article_var.set(value)
        self.refresh_stage_progress()
        self.refresh_qc_history()
        self.update_stage_detail_panel()

    def refresh_stage_progress(self):
        self.clear_tree(self.stage_tree)

        if not self.selected_order_id or not self.selected_order_article_id:
            if hasattr(self, "stage_detail_text"):
                self.stage_detail_text.delete("1.0", "end")
            return
        active_filter = (self.stage_filter_var.get().strip() if hasattr(self, "stage_filter_var") else "All")
        progress_rows = self.db.order_progress(self.selected_order_id, self.selected_order_article_id)
        prev_completed = True
        for row in progress_rows:
            unlocked = prev_completed
            display_status = row["status"] if unlocked else ""
            display_updated = self.format_timestamp_to_date(row["updated_at"]) if unlocked else ""
            display_note = (row["note"] or "") if unlocked else ""
            if active_filter != "All" and display_status != active_filter:
                prev_completed = unlocked and (row["status"] == "Completed")
                continue
            stage_tag = "stage_in_progress"
            if unlocked and row["status"] == "Blocked":
                stage_tag = "stage_blocked"
            elif unlocked and row["status"] == "Completed":
                stage_tag = "stage_completed"
            self.insert_tree_row(
                self.stage_tree,
                (
                    row["stage_id"],
                    row["stage_name"],
                    display_status,
                    display_updated,
                    display_note,
                ),
                tags=(stage_tag,),
            )
            prev_completed = unlocked and (row["status"] == "Completed")

        stages = self.db.list_stages()
        self.qc_stage_combo["values"] = [f"{s['id']} - {s['stage_name']}" for s in stages]
        if stages and not self.qc_stage_var.get():
            self.qc_stage_var.set(f"{stages[0]['id']} - {stages[0]['stage_name']}")
        self.update_stage_detail_panel()

    def refresh_qc_history(self):
        self.clear_tree(self.qc_tree)

        if not self.selected_order_id or not self.selected_order_article_id:
            return
        for row in self.db.list_quality_checks(self.selected_order_id, self.selected_order_article_id):
            self.insert_tree_row(
                self.qc_tree,
                (
                    row["qc_code"] or f"QC-{self.selected_order_id:04d}-00-{row['id']:05d}",
                    row["stage_name"],
                    row["qc_result"],
                    row["inspector"],
                    row["defects_found"],
                    row["remarks"],
                    row["checked_at"],
                ),
            )
        self.sync_selected_order_labels()

    def refresh_dashboard(self):
        orders = self.db.list_orders()
        self.dashboard_row_context = {}
        total_orders = len(orders)
        completed_orders = 0
        in_progress_orders = 0
        blocked_orders = 0
        overdue_orders = 0
        due_today_orders = 0
        today = datetime.now().date()
        dashboard_rows = []
        for order_row in orders:
            articles = self.db.list_order_articles(order_row["id"])
            order_has_completed = True
            order_has_blocked = False
            order_has_overdue = False
            order_due_today = False
            due_state = "On Track"
            days_left_display = "-"
            current_stage = "-"
            current_stage_status = "-"
            last_update = "-"
            last_qc_stage = "-"
            last_qc_result = "-"
            qc_checks_total = 0
            progress_points_total = 0
            progress_points_earned = 0
            current_stage_rank = {"Blocked": 3, "In Progress": 2, "Completed": 1, "-": 0}
            current_stage_best_rank = -1
            blocked_details = []

            for article in articles:
                progress_rows = self.db.order_progress(order_row["id"], article["id"])
                statuses = [row["status"] for row in progress_rows]
                art_completed = statuses and all(status == "Completed" for status in statuses)
                order_has_completed = order_has_completed and art_completed
                order_has_blocked = order_has_blocked or ("Blocked" in statuses)
                for stage_row in progress_rows:
                    if stage_row["status"] == "Blocked":
                        note = (stage_row["note"] or "").strip()
                        note_txt = f" | Note: {note}" if note else ""
                        blocked_details.append(
                            f"Art No {article['article_number']} -> {stage_row['stage_name']}{note_txt}"
                        )

                due_date_raw = (order_row["due_date"] or "").strip()
                due_state = "-"
                is_overdue = False
                days_left_display = "-"
                if due_date_raw:
                    try:
                        due_date = datetime.strptime(due_date_raw, "%d-%m-%Y").date()
                        days_left = (due_date - today).days
                        days_left_display = str(days_left)
                        if due_date < today and not art_completed:
                            due_state = "Overdue"
                            is_overdue = True
                            order_has_overdue = True
                        elif due_date == today and not art_completed:
                            if due_state != "Overdue":
                                due_state = "Due Today"
                            order_due_today = True
                        elif due_state not in ("Overdue", "Due Today"):
                            due_state = "On Track"
                    except ValueError:
                        pass

                placed_date_raw = (order_row["order_placed_date"] or "").strip()
                aging_display = "-"
                if placed_date_raw:
                    try:
                        placed_date = datetime.strptime(placed_date_raw, "%d-%m-%Y").date()
                        aging_display = str((today - placed_date).days)
                    except ValueError:
                        pass

                current_stage = "-"
                current_stage_status = "-"
                last_update = "-"
                if progress_rows:
                    current = next((r for r in progress_rows if r["status"] != "Completed"), progress_rows[-1])
                    rank = current_stage_rank.get(current["status"], 0)
                    if rank > current_stage_best_rank:
                        current_stage_best_rank = rank
                        current_stage = f"{current['stage_name']} ({article['article_number']})"
                        current_stage_status = current["status"]
                    candidate_last = max(progress_rows, key=lambda r: r["updated_at"])["updated_at"]
                    if candidate_last > last_update:
                        last_update = candidate_last

                qc_rows = self.db.list_quality_checks(order_row["id"], article["id"])
                qc_checks_total += len(qc_rows)
                if qc_rows:
                    latest_qc = qc_rows[0]
                    if latest_qc["checked_at"] >= last_update:
                        last_qc_stage = f"{latest_qc['stage_name']} ({article['article_number']})"
                        last_qc_result = latest_qc["qc_result"] or "-"

                total_stages = len(progress_rows)
                completed_stages = sum(1 for s in statuses if s == "Completed")
                qc_ok_count = sum(1 for q in qc_rows if q["qc_result"] in ("Pass", "Rework"))
                progress_points_total += total_stages * 2
                progress_points_earned += completed_stages + qc_ok_count

            placed_date_raw = (order_row["order_placed_date"] or "").strip()
            aging_display = "-"
            if placed_date_raw:
                try:
                    placed_date = datetime.strptime(placed_date_raw, "%d-%m-%Y").date()
                    aging_display = str((today - placed_date).days)
                except ValueError:
                    pass

            article_count = len(articles)
            art_text = f"{article_count} Art(s)"
            reference = f"ORD-{order_row['id']:04d} | ARTS:{article_count} | STG:{current_stage_status or '-'} | QC:{last_qc_result}"
            progress_pct = (progress_points_earned / progress_points_total * 100.0) if progress_points_total else 0.0
            dashboard_rows.append(
                {
                    "id": order_row["id"],
                    "ref": reference,
                    "code": order_row["order_code"],
                    "supplier": order_row["supplier_name"] or "-",
                    "art": art_text,
                    "customer": order_row["customer_name"],
                    "category": order_row["order_category"] or "-",
                    "purpose": order_row["order_purpose"] or "-",
                    "qty": order_row["quantity"],
                    "placed": order_row["order_placed_date"] or "-",
                    "due": order_row["due_date"] or "-",
                    "days_left": days_left_display,
                    "aging": aging_display,
                    "due_state": due_state,
                    "current_stage": current_stage,
                    "stage_status": current_stage_status,
                    "blocked_summary": blocked_details[0] if blocked_details else "",
                    "qc_checks": qc_checks_total,
                    "last_qc_stage": last_qc_stage,
                    "last_qc_result": last_qc_result,
                    "progress": f"{progress_pct:.1f}",
                    "last_update": last_update or "-",
                    "blocked_view": "View >" if blocked_details else "",
                    "blocked_details": blocked_details,
                    "is_completed": bool(order_has_completed),
                    "is_blocked": bool(order_has_blocked),
                    "is_overdue": bool(order_has_overdue),
                    "is_due_today": bool(order_due_today),
                }
            )
            self.dashboard_row_context[order_row["id"]] = dashboard_rows[-1]

            if order_has_completed:
                completed_orders += 1
            else:
                in_progress_orders += 1
            if order_has_blocked:
                blocked_orders += 1
            if order_has_overdue:
                overdue_orders += 1
            if order_due_today:
                due_today_orders += 1

        self.kpi_total_var.set(f"Total Orders: {total_orders}")
        self.kpi_in_progress_var.set(f"In Progress: {in_progress_orders}")
        self.kpi_completed_var.set(f"Completed: {completed_orders}")
        self.kpi_blocked_var.set(f"Blocked: {blocked_orders}")
        self.kpi_overdue_var.set(f"Overdue: {overdue_orders}")
        self.exc_blocked_var.set(f"Blocked: {blocked_orders}")
        self.exc_overdue_var.set(f"Overdue: {overdue_orders}")
        self.exc_due_today_var.set(f"Due Today: {due_today_orders}")

        for item in self.dashboard_tree.get_children():
            self.dashboard_tree.delete(item)
        active_filter = self.dashboard_filter_var.get().strip()
        search_text = self.dashboard_search_var.get().strip().lower()
        for row in dashboard_rows:
            if active_filter == "In Progress" and row["is_completed"]:
                continue
            if active_filter == "Completed" and not row["is_completed"]:
                continue
            if active_filter == "Blocked" and not row["is_blocked"]:
                continue
            if active_filter == "Overdue" and not row["is_overdue"]:
                continue
            if active_filter == "Due Today" and not row["is_due_today"]:
                continue
            if search_text:
                search_blob = (
                    f"{row['id']} {row['code']} {row['art']} {row['customer']} "
                    f"{row['supplier']} {row['category']} {row['purpose']} "
                    f"{row['current_stage']} {row['placed']} {row['due']} {row['due_state']} "
                    f"{row['last_qc_stage']} {row['last_qc_result']} {row['blocked_summary']} "
                    f"{' '.join(row['blocked_details'])}"
                ).lower()
                if search_text not in search_blob:
                    continue
            row_tags = ()
            if row["is_blocked"]:
                row_tags = ("status_blocked",)
            elif row["is_overdue"]:
                row_tags = ("status_overdue",)
            elif row["is_due_today"]:
                row_tags = ("status_due_today",)
            elif row["is_completed"]:
                row_tags = ("status_completed",)
            elif row["stage_status"] == "In Progress":
                row_tags = ("status_in_progress",)
            elif row["due_state"] == "On Track":
                row_tags = ("status_on_track",)

            self.insert_tree_row(
                self.dashboard_tree,
                (
                    row["id"],
                    row["code"],
                    row["supplier"],
                    row["art"],
                    row["customer"],
                    row["category"],
                    row["purpose"],
                    row["qty"],
                    row["placed"],
                    row["due"],
                    row["due_state"],
                    row["current_stage"],
                    row["stage_status"],
                    row["blocked_summary"],
                    row["progress"],
                    "Hide <" if row["id"] in self.expanded_dashboard_order_ids and row["blocked_details"] else row["blocked_view"],
                ),
                tags=row_tags,
            )
            if row["id"] in self.expanded_dashboard_order_ids and row["blocked_details"]:
                for detail in row["blocked_details"]:
                    self.insert_tree_row(
                        self.dashboard_tree,
                        ("", "", "", "", "", "", "", "", "", "", "", "", "", detail, "", ""),
                        tags=("detail_row",),
                    )

        self.summary_text.delete("1.0", "end")
        qc_rows = self.db.qc_summary()
        if not qc_rows:
            self.summary_text.insert("end", "No quality checks recorded yet.\n")
            return
        total_checks = sum(row["check_count"] for row in qc_rows)
        self.summary_text.insert(
            "end",
            f"QC Checks: {total_checks} | Due Today: {due_today_orders} | Overdue Orders: {overdue_orders}\n",
        )
        for row in qc_rows:
            pct = (row["check_count"] / total_checks * 100.0) if total_checks else 0.0
            self.summary_text.insert("end", f"{row['qc_result']}: {row['check_count']} ({pct:.1f}%)  ")
        self.summary_text.insert("end", "\nDouble-click an order in 'All Orders Overview' to view its QC log popup.\n")

    def clear_dashboard_filters(self):
        self.dashboard_filter_var.set("All")
        self.dashboard_search_var.set("")
        self.refresh_dashboard()

    def apply_dashboard_quick_filter(self, filter_name: str):
        self.dashboard_filter_var.set(filter_name)
        self.refresh_dashboard()

    def refresh_all(self):
        self.refresh_orders()
        self.refresh_article_selectors()
        self.refresh_stage_progress()
        self.refresh_qc_history()
        self.refresh_dashboard()
        self.sync_selected_order_labels()

    def on_order_selected(self, _event):
        selected = self.orders_tree.selection()
        if not selected:
            return
        if "detail_row" in self.orders_tree.item(selected[0], "tags"):
            return
        self.selected_order_id = int(self.orders_tree.item(selected[0], "values")[0])
        self.load_selected_order_into_form(self.selected_order_id)
        self.refresh_article_selectors()
        self.set_qc_stage_to_first()
        self.refresh_stage_progress()
        self.refresh_qc_history()
        self.sync_selected_order_labels()

    def handle_add_order(self):
        parsed = self.parse_order_form_inputs()
        if not parsed:
            return
        code, supplier, customer, category, purpose, order_note, order_date, placed_date, due, articles = parsed

        try:
            self.db.add_order(code, supplier, customer, category, purpose, order_note, order_date, placed_date, due, articles)
        except sqlite3.IntegrityError:
            messagebox.showerror("Duplicate", "Order code already exists.")
            return

        self.clear_order_form()
        self.refresh_orders()
        self.refresh_dashboard()

    def handle_update_order(self):
        target_order_id = self.editing_order_id or self.selected_order_id
        if not target_order_id:
            messagebox.showerror("Selection", "Select an order to update.")
            return

        parsed = self.parse_order_form_inputs()
        if not parsed:
            return
        code, supplier, customer, category, purpose, order_note, order_date, placed_date, due, articles = parsed

        try:
            self.db.update_order(target_order_id, code, supplier, customer, category, purpose, order_note, order_date, placed_date, due, articles)
        except sqlite3.IntegrityError:
            messagebox.showerror("Duplicate", "Order code already exists.")
            return

        self.refresh_orders()
        self.select_order_row_by_id(target_order_id)
        self.refresh_dashboard()
        messagebox.showinfo("Updated", f"Order ID {target_order_id} updated successfully.")

    def handle_export_production_csv(self):
        order_id = self.editing_order_id or self.selected_order_id
        if not order_id:
            messagebox.showerror("Selection", "Select an order to export.")
            return
        order_row = self.db.get_order_by_id(order_id)
        if not order_row:
            messagebox.showerror("Selection", "Order not found.")
            return
        articles = self.db.list_order_articles(order_id)
        default_name = f"production_order_{order_row['order_code']}.csv"
        output_path = filedialog.asksaveasfilename(
            title="Export Production Order CSV",
            defaultextension=".csv",
            initialfile=default_name,
            filetypes=[("CSV files", "*.csv")],
        )
        if not output_path:
            return
        with open(output_path, "w", newline="", encoding="utf-8") as fp:
            writer = csv.writer(fp)
            writer.writerow(["Company", "SILPA"])
            writer.writerow(["Order No", order_row["order_code"], "Order Date", order_row["order_date"] or "-"])
            writer.writerow(["Supplier", order_row["supplier_name"] or "-", "Required Date", order_row["due_date"] or "-"])
            writer.writerow(["Category", order_row["order_category"] or "-", "Purpose", order_row["order_purpose"] or "-"])
            writer.writerow(["Order Note", order_row["order_note"] or "-"])
            writer.writerow([])
            writer.writerow(["S No", "Art Number", "Item Name", "Material", "Item Weight", "Size", "Colours", "Line Qty"])
            grand_total = 0
            for idx, art in enumerate(articles, start=1):
                line_qty = int(art["quantity"] or 0)
                grand_total += line_qty
                writer.writerow(
                    [
                        idx,
                        art["article_number"],
                        art["item_name"] or "",
                        art["material"] or "",
                        art["item_weight"] or "",
                        art["size"] or "",
                        art["colours"] or "",
                        line_qty,
                    ]
                )
            writer.writerow([])
            writer.writerow(["Grand Total", grand_total])
        messagebox.showinfo("Exported", f"Production CSV exported to:\n{output_path}")

    def parse_order_form_inputs(self):
        code = self.order_code_var.get().strip()
        supplier = self.supplier_var.get().strip()
        customer = self.customer_var.get().strip()
        category = self.order_category_var.get().strip()
        purpose = self.order_purpose_var.get().strip()
        order_note = self.order_note_var.get().strip()
        order_date = self.order_date_var.get().strip()
        placed_date = self.placed_date_var.get().strip()
        due = self.due_var.get().strip()

        if not code or not supplier or not customer or not order_date or not placed_date:
            messagebox.showerror(
                "Validation",
                "Order code, supplier, customer, order date, and order placed date are required.",
            )
            return None

        try:
            articles = self.collect_article_inputs()
        except ValueError as exc:
            messagebox.showerror("Validation", str(exc))
            return None

        for label, value in [("Order date", order_date), ("Order placed date", placed_date)]:
            try:
                datetime.strptime(value, "%d-%m-%Y")
            except ValueError:
                messagebox.showerror("Validation", f"{label} must be in DD-MM-YYYY format.")
                return None

        if not due:
            messagebox.showerror("Validation", "Required date is mandatory.")
            return None
        try:
            datetime.strptime(due, "%d-%m-%Y")
        except ValueError:
            messagebox.showerror("Validation", "Required date must be in DD-MM-YYYY format.")
            return None

        if not category:
            category = "Regular"
        if not purpose:
            purpose = "Stock Purpose"

        return code, supplier, customer, category, purpose, order_note, order_date, placed_date, due, articles

    def load_selected_order_into_form(self, order_id: int):
        row = self.db.get_order_by_id(order_id)
        if not row:
            return
        self.order_code_var.set(row["order_code"] or "")
        self.supplier_var.set(row["supplier_name"] or "")
        self.customer_var.set(row["customer_name"] or "")
        self.order_category_var.set(row["order_category"] or "Regular")
        self.order_purpose_var.set(row["order_purpose"] or "Stock Purpose")
        self.order_note_var.set(row["order_note"] or "")
        self.order_date_var.set(row["order_date"] or "")
        self.placed_date_var.set(row["order_placed_date"] or "")
        self.due_var.set(row["due_date"] or "")
        for row_wrap, *_ in getattr(self, "article_rows", []):
            row_wrap.destroy()
        self.article_rows = []
        for art in self.db.list_order_articles(order_id):
            self.add_article_row(
                art["article_number"],
                str(art["quantity"]),
                art["item_name"] or "",
                art["material"] or "",
                art["item_weight"] or "",
                art["size"] or "",
                art["colours"] or "",
            )
        self.ensure_article_input_tail()
        self.editing_order_id = order_id
        self.update_order_btn.state(["!disabled"])

    def clear_order_form(self):
        self.order_code_var.set("")
        self.supplier_var.set("")
        self.customer_var.set("")
        self.order_category_var.set("Regular")
        self.order_purpose_var.set("Stock Purpose")
        self.order_note_var.set("")
        self.order_date_var.set("")
        self.placed_date_var.set("")
        self.due_var.set("")
        for row_wrap, *_ in getattr(self, "article_rows", []):
            row_wrap.destroy()
        self.article_rows = []
        self.add_article_row()
        self.editing_order_id = None
        self.update_order_btn.state(["disabled"])

    def build_default_sample_dataset(self):
        stage_names = [name for name, _ in DEFAULT_STAGES]

        def stage_rows(status_by_name, note_by_name=None, updated_at="2026-02-25 10:00:00"):
            notes = note_by_name or {}
            return [
                {
                    "stage_name": stage_name,
                    "status": status_by_name.get(stage_name, "In Progress"),
                    "note": notes.get(stage_name, ""),
                    "updated_at": updated_at,
                }
                for stage_name in stage_names
            ]

        return {
            "orders": [
                {
                    "order_code": "001",
                    "article_number": "A100",
                    "customer_name": "Aster Jewels",
                    "quantity": 120,
                    "order_placed_date": "05-02-2026",
                    "due_date": "24-02-2026",
                    "created_at": "2026-02-05 10:15:00",
                    "stage_progress": stage_rows({s: "Completed" for s in stage_names}, updated_at="2026-02-14 16:00:00"),
                    "quality_checks": [
                        {"stage_name": "CAD Design", "qc_result": "Pass", "inspector": "Isha", "defects_found": 0, "remarks": "OK", "checked_at": "2026-02-06 16:00:00"},
                        {"stage_name": "Production", "qc_result": "Pass", "inspector": "Noor", "defects_found": 0, "remarks": "OK", "checked_at": "2026-02-10 16:00:00"},
                        {"stage_name": "Packing Finished Product", "qc_result": "Pass", "inspector": "Ravi", "defects_found": 0, "remarks": "OK", "checked_at": "2026-02-14 16:00:00"},
                    ],
                },
                {
                    "order_code": "002",
                    "article_number": "A200",
                    "customer_name": "Blue Mint",
                    "quantity": 200,
                    "order_placed_date": "12-02-2026",
                    "due_date": "27-02-2026",
                    "created_at": "2026-02-12 09:30:00",
                    "stage_progress": stage_rows(
                        {
                            "CAD Design": "Completed",
                            "Camera": "Completed",
                            "3D Printing": "Completed",
                            "Moulding": "Completed",
                            "Production": "Completed",
                            "Filing Unwanted Material": "Completed",
                            "Painting": "Completed",
                            "Stone Work (If Needed)": "In Progress",
                            "Packing Finished Product": "In Progress",
                        },
                        {"Packing Finished Product": "Awaiting final audit"},
                        "2026-02-22 14:00:00",
                    ),
                    "quality_checks": [
                        {"stage_name": "Production", "qc_result": "Fail", "inspector": "Noor", "defects_found": 3, "remarks": "Polish issue", "checked_at": "2026-02-17 16:00:00"},
                        {"stage_name": "Packing Finished Product", "qc_result": "Rework", "inspector": "Isha", "defects_found": 1, "remarks": "Label fixed", "checked_at": "2026-02-22 17:00:00"},
                    ],
                },
                {
                    "order_code": "003",
                    "article_number": "A300",
                    "customer_name": "Craft Aura",
                    "quantity": 80,
                    "order_placed_date": "10-02-2026",
                    "due_date": "25-02-2026",
                    "created_at": "2026-02-10 08:40:00",
                    "stage_progress": stage_rows(
                        {
                            "CAD Design": "Completed",
                            "Camera": "Completed",
                            "3D Printing": "Completed",
                            "Moulding": "Completed",
                            "Production": "Completed",
                            "Filing Unwanted Material": "Completed",
                            "Painting": "Completed",
                            "Stone Work (If Needed)": "Completed",
                            "Packing Finished Product": "Blocked",
                        },
                        {"Packing Finished Product": "Courier hold"},
                        "2026-02-24 10:00:00",
                    ),
                    "quality_checks": [
                        {"stage_name": "Packing Finished Product", "qc_result": "Fail", "inspector": "Ravi", "defects_found": 2, "remarks": "Seal issue", "checked_at": "2026-02-24 16:00:00"},
                    ],
                },
            ]
        }

    def ensure_sample_dataset_file(self):
        if SAMPLE_DATASET_PATH.exists():
            return
        SAMPLE_DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)
        default_data = self.build_default_sample_dataset()
        with SAMPLE_DATASET_PATH.open("w", encoding="utf-8") as fp:
            json.dump(default_data, fp, indent=2)

    def handle_load_sample_dataset(self):
        self.ensure_sample_dataset_file()
        should_load = messagebox.askyesno(
            "Load Sample Dataset",
            "This will replace current orders, stages progress, and quality checks with sample data.\nContinue?",
        )
        if not should_load:
            return
        try:
            self.db.load_sample_dataset(SAMPLE_DATASET_PATH)
        except Exception as exc:
            messagebox.showerror("Load Failed", f"Unable to load sample dataset.\n{exc}")
            return
        self.selected_order_id = None
        self.clear_order_form()
        self.refresh_all()
        messagebox.showinfo("Loaded", f"Sample dataset loaded from:\n{SAMPLE_DATASET_PATH}")

    def handle_dashboard_lookup(self):
        raw_order_id = self.dashboard_order_id_var.get().strip()
        self.order_lookup_text.delete("1.0", "end")
        try:
            order_id = int(raw_order_id)
        except ValueError:
            self.order_lookup_text.insert("end", "Enter a valid numeric Order ID.\n")
            return

        order_row = self.db.get_order_by_id(order_id)
        if not order_row:
            self.order_lookup_text.insert("end", f"No order found for ID {order_id}.\n")
            return

        progress_rows = self.db.order_progress(order_id)
        if not progress_rows:
            self.order_lookup_text.insert("end", f"Order {order_id} has no stage records.\n")
            return

        current_stage_row = None
        for row in progress_rows:
            if row["status"] != "Completed":
                current_stage_row = row
                break
        if current_stage_row is None:
            current_stage_row = progress_rows[-1]

        last_updated_row = max(progress_rows, key=lambda r: r["updated_at"])

        self.order_lookup_text.insert(
            "end",
            (
                f"Order ID: {order_row['id']}\n"
                f"Order Code: {order_row['order_code']}\n"
                f"Art No: {order_row['article_number'] or '-'}\n"
                f"Customer: {order_row['customer_name']}\n"
                f"Due Date: {order_row['due_date'] or '-'}\n"
                f"Current Stage: {current_stage_row['stage_name']} ({current_stage_row['status']})\n"
                f"Last Update: {last_updated_row['updated_at']} at {last_updated_row['stage_name']}\n"
                f"Last Note: {last_updated_row['note'] or '-'}\n"
            ),
        )

    def sync_selected_order_labels(self):
        if not self.selected_order_id:
            text = "Selected Order: None"
        else:
            row = self.db.get_order_by_id(self.selected_order_id)
            if row:
                art_text = "-"
                if self.selected_order_article_id:
                    for art in self.db.list_order_articles(self.selected_order_id):
                        if art["id"] == self.selected_order_article_id:
                            art_text = art["article_number"]
                            break
                text = (
                    f"Selected Order: ID {row['id']} | Code: {row['order_code']} | "
                    f"Art No: {art_text} | Due: {row['due_date'] or '-'}"
                )
            else:
                text = "Selected Order: None"
        self.qc_selected_order_label_var.set(text)
        self.dashboard_selected_order_label_var.set(text)

    def go_to_orders_tab(self):
        self.notebook.select(self.orders_tab)

    def use_selected_order_in_dashboard(self):
        if not self.selected_order_id:
            messagebox.showerror("Selection", "Select an order in Orders & Stages first.")
            return
        self.dashboard_order_id_var.set(str(self.selected_order_id))
        self.handle_dashboard_lookup()

    def select_order_row_by_id(self, order_id: int):
        for item in self.orders_tree.get_children():
            values = self.orders_tree.item(item, "values")
            if values and int(values[0]) == order_id:
                self.orders_tree.selection_set(item)
                self.orders_tree.focus(item)
                self.orders_tree.see(item)
                self.selected_order_id = order_id
                self.load_selected_order_into_form(order_id)
                self.refresh_article_selectors()
                self.set_qc_stage_to_first()
                self.refresh_stage_progress()
                self.refresh_qc_history()
                self.sync_selected_order_labels()
                break

    def on_dashboard_order_selected(self, _event):
        selected = self.dashboard_tree.selection()
        if not selected:
            return
        if "detail_row" in self.dashboard_tree.item(selected[0], "tags"):
            return
        values = self.dashboard_tree.item(selected[0], "values")
        if not values or not values[0]:
            return
        order_id = int(values[0])
        self.select_order_row_by_id(order_id)

    def on_dashboard_order_double_click(self, _event):
        selected = self.dashboard_tree.selection()
        if not selected:
            return
        if "detail_row" in self.dashboard_tree.item(selected[0], "tags"):
            return
        values = self.dashboard_tree.item(selected[0], "values")
        if not values or not values[0]:
            return
        order_id = int(values[0])
        self.select_order_row_by_id(order_id)
        self.show_dashboard_qc_popup(order_id, None)

    def on_dashboard_tree_click(self, event):
        row_id = self.dashboard_tree.identify_row(event.y)
        if not row_id:
            return
        if "detail_row" in self.dashboard_tree.item(row_id, "tags"):
            return
        col_id = self.dashboard_tree.identify_column(event.x)
        blocked_col_index = list(self.dashboard_tree["columns"]).index("blocked_view") + 1
        if col_id != f"#{blocked_col_index}":
            return
        values = self.dashboard_tree.item(row_id, "values")
        if not values:
            return
        try:
            order_id = int(values[0])
        except (TypeError, ValueError):
            return
        row_data = self.dashboard_row_context.get(order_id, {})
        view_text = (row_data.get("blocked_view") or "").strip()
        if view_text == "":
            return
        if order_id in self.expanded_dashboard_order_ids:
            self.expanded_dashboard_order_ids.remove(order_id)
        else:
            self.expanded_dashboard_order_ids.add(order_id)
        self.refresh_dashboard()

    def select_article_by_number(self, order_id: int, article_number: str):
        for art in self.db.list_order_articles(order_id):
            if (art["article_number"] or "").strip() == (article_number or "").strip():
                self.selected_order_article_id = art["id"]
                display = next(
                    (label for label, aid in getattr(self, "stage_article_map", {}).items() if aid == art["id"]),
                    f"{art['article_number']} (Qty {art['quantity']})",
                )
                self.stage_article_var.set(display)
                self.qc_article_var.set(display)
                self.refresh_stage_progress()
                self.refresh_qc_history()
                self.sync_selected_order_labels()
                break

    def show_dashboard_qc_popup(self, order_id: int, order_article_id: int | None = None):
        order_row = self.db.get_order_by_id(order_id)
        if not order_row:
            return

        if self.qc_popup is not None and self.qc_popup.winfo_exists():
            self.qc_popup.destroy()

        popup = tk.Toplevel(self)
        popup.title(f"QC Log - Order {order_row['order_code']} (ID {order_row['id']})")
        popup.geometry("980x420")
        popup.minsize(860, 320)
        popup.configure(bg="#eef1f5")
        popup.transient(self)
        popup.grab_set()
        self.qc_popup = popup
        popup.protocol("WM_DELETE_WINDOW", self.close_qc_popup)

        header = ttk.LabelFrame(popup, text="Order Details")
        header.pack(fill="x", padx=10, pady=(10, 8))
        ttk.Label(
            header,
            text=(
                f"Order ID: {order_row['id']}   "
                f"Code: {order_row['order_code']}   "
                f"Art No: {order_row['article_number'] or '-'}   "
                f"Customer: {order_row['customer_name']}"
            ),
        ).pack(anchor="w", padx=8, pady=(6, 2))
        ttk.Label(
            header,
            text=f"Order Placed: {order_row['order_placed_date'] or '-'}   Due: {order_row['due_date'] or '-'}",
        ).pack(anchor="w", padx=8, pady=(0, 6))

        table_box = ttk.LabelFrame(popup, text="Quality Check Log")
        table_box.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        log_tree = ttk.Treeview(
            table_box,
            columns=("qc_id", "stage", "result", "inspector", "defects", "checked", "remarks"),
            show="headings",
        )
        for col, text, width in [
            ("qc_id", "QC ID", 150),
            ("stage", "Stage", 200),
            ("result", "Result", 90),
            ("inspector", "Inspector", 120),
            ("defects", "Defects", 70),
            ("checked", "Checked At", 145),
            ("remarks", "Remarks", 260),
        ]:
            log_tree.heading(col, text=text)
            log_tree.column(col, width=width, anchor="w")
        log_tree.tag_configure("row_even", background="#ffffff")
        log_tree.tag_configure("row_odd", background="#f8fafc")
        scroll = ttk.Scrollbar(table_box, orient="vertical", command=log_tree.yview)
        log_tree.configure(yscrollcommand=scroll.set)
        log_tree.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        scroll.pack(side="right", fill="y", padx=(0, 4), pady=4)

        if order_article_id is None:
            order_checks = [r for r in self.db.quality_check_log() if r["order_id"] == order_id]
        else:
            order_checks = self.db.list_quality_checks(order_id, order_article_id)
        if not order_checks:
            self.insert_tree_row(log_tree, ("-", "-", "-", "-", "-", "-", "No quality checks recorded yet."))
        else:
            for row in order_checks:
                stage_name = row["stage_name"]
                if order_article_id is None:
                    art_no = row["article_number"] or "-"
                    stage_name = f"{stage_name} ({art_no})"
                self.insert_tree_row(
                    log_tree,
                    (
                        row["qc_code"] or f"QC-{order_id:04d}-00-{row['id']:05d}",
                        stage_name,
                        row["qc_result"],
                        row["inspector"] or "-",
                        row["defects_found"],
                        row["checked_at"],
                        row["remarks"] or "-",
                    ),
                )

    def close_qc_popup(self):
        if self.qc_popup is not None and self.qc_popup.winfo_exists():
            self.qc_popup.destroy()
        self.qc_popup = None

    def on_tab_changed(self, _event):
        current_tab = self.notebook.select()
        if current_tab == str(self.dashboard_tab):
            self.refresh_dashboard()
            self.sync_selected_order_labels()
        elif current_tab == str(self.qc_tab):
            self.refresh_qc_history()
            self.sync_selected_order_labels()

    def get_next_stage_id(self, current_stage_id: int):
        stage_ids = [row["id"] for row in self.db.list_stages()]
        try:
            idx = stage_ids.index(current_stage_id)
        except ValueError:
            return None
        if idx + 1 < len(stage_ids):
            return stage_ids[idx + 1]
        return None

    def select_stage_row(self, stage_id: int):
        for item in self.stage_tree.get_children():
            values = self.stage_tree.item(item, "values")
            if values and int(values[0]) == stage_id:
                self.stage_tree.selection_set(item)
                self.stage_tree.focus(item)
                self.stage_tree.see(item)
                break

    def set_qc_stage_selection(self, stage_id: int):
        for stage in self.db.list_stages():
            if stage["id"] == stage_id:
                self.qc_stage_var.set(f"{stage['id']} - {stage['stage_name']}")
                break

    def set_qc_stage_to_first(self):
        stages = self.db.list_stages()
        if stages:
            first = stages[0]
            self.qc_stage_var.set(f"{first['id']} - {first['stage_name']}")

    def on_stage_tree_click(self, event):
        if not self.selected_order_id:
            return
        row_id = self.stage_tree.identify_row(event.y)
        if not row_id:
            return
        self.stage_tree.selection_set(row_id)
        self.stage_tree.focus(row_id)
        col_id = self.stage_tree.identify_column(event.x)
        if col_id != "#3":
            return

        values = self.stage_tree.item(row_id, "values")
        if not values:
            return
        stage_id = int(values[0])
        if not self.is_stage_unlocked(stage_id):
            messagebox.showerror("Locked Stage", "Complete previous stage first to unlock this stage.")
            return
        menu = tk.Menu(self, tearoff=0)
        for status in STATUS_OPTIONS:
            menu.add_command(
                label=status,
                command=lambda s=status, sid=stage_id: self.apply_stage_status_from_tree(sid, s),
            )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def on_stage_selected(self, _event):
        self.update_stage_detail_panel()

    def get_selected_stage_id(self):
        selected = self.stage_tree.selection()
        if not selected:
            return None
        values = self.stage_tree.item(selected[0], "values")
        if not values:
            return None
        try:
            return int(values[0])
        except (ValueError, TypeError):
            return None

    def apply_stage_status_to_selected(self, status: str):
        stage_id = self.get_selected_stage_id()
        if stage_id is None:
            messagebox.showerror("Selection", "Select a stage row first.")
            return
        if not self.is_stage_unlocked(stage_id):
            messagebox.showerror("Locked Stage", "Complete previous stage first to unlock this stage.")
            return
        self.apply_stage_status_from_tree(stage_id, status)

    def update_stage_detail_panel(self):
        if not hasattr(self, "stage_detail_text"):
            return
        self.stage_detail_text.delete("1.0", "end")
        if not self.selected_order_id or not self.selected_order_article_id:
            self.stage_detail_text.insert("end", "Select an order and Art No to view stage details.")
            if hasattr(self, "stage_note_edit_var"):
                self.stage_note_edit_var.set("")
            return
        stage_id = self.get_selected_stage_id()
        if stage_id is None:
            self.stage_detail_text.insert("end", "Select a stage row to view detailed status and latest QC.")
            if hasattr(self, "stage_note_edit_var"):
                self.stage_note_edit_var.set("")
            return
        progress_rows = self.db.order_progress(self.selected_order_id, self.selected_order_article_id)
        stage_row = None
        for row in progress_rows:
            if row["stage_id"] == stage_id:
                stage_row = row
                break
        if not stage_row:
            self.stage_detail_text.insert("end", "Stage details unavailable.")
            if hasattr(self, "stage_note_edit_var"):
                self.stage_note_edit_var.set("")
            return
        if not self.is_stage_unlocked(stage_id, progress_rows):
            self.stage_detail_text.insert("end", "This stage is locked. Complete previous stage first.")
            if hasattr(self, "stage_note_edit_var"):
                self.stage_note_edit_var.set("")
            return
        if hasattr(self, "stage_note_edit_var"):
            self.stage_note_edit_var.set(stage_row["note"] or "")
        latest_qc = None
        for qc in self.db.list_quality_checks(self.selected_order_id, self.selected_order_article_id):
            if qc["stage_id"] == stage_id:
                latest_qc = qc
                break
        self.stage_detail_text.insert(
            "end",
            (
                f"Stage: {stage_row['stage_name']}\n"
                f"Status: {stage_row['status']}\n"
                f"Last Updated: {self.format_timestamp_to_date(stage_row['updated_at'])}\n"
                f"Note: {stage_row['note'] or '-'}\n"
            ),
        )
        if latest_qc:
            self.stage_detail_text.insert(
                "end",
                (
                    f"Latest QC: {latest_qc['qc_result']} ({latest_qc['qc_code'] or '-'})\n"
                    f"Inspector: {latest_qc['inspector'] or '-'} | Defects: {latest_qc['defects_found']}\n"
                    f"QC Remarks: {latest_qc['remarks'] or '-'}\n"
                ),
            )
        else:
            self.stage_detail_text.insert("end", "Latest QC: No QC recorded for this stage.\n")

    def handle_save_stage_note(self):
        if not self.selected_order_id or not self.selected_order_article_id:
            messagebox.showerror("Selection", "Select an order and Art No first.")
            return
        stage_id = self.get_selected_stage_id()
        if stage_id is None:
            messagebox.showerror("Selection", "Select a stage row first.")
            return
        if not self.is_stage_unlocked(stage_id):
            messagebox.showerror("Locked Stage", "Complete previous stage first to unlock this stage.")
            return

        current_status = None
        for row in self.db.order_progress(self.selected_order_id, self.selected_order_article_id):
            if int(row["stage_id"]) == int(stage_id):
                current_status = row["status"]
                break
        if current_status is None:
            messagebox.showerror("Selection", "Unable to find selected stage.")
            return

        new_note = self.stage_note_edit_var.get().strip() if hasattr(self, "stage_note_edit_var") else ""
        self.db.update_stage(
            self.selected_order_id,
            stage_id,
            current_status,
            new_note,
            self.selected_order_article_id,
        )
        self.refresh_stage_progress()
        self.refresh_dashboard()
        self.update_stage_detail_panel()

    def apply_stage_status_from_tree(self, stage_id: int, status: str):
        if not self.selected_order_id or not self.selected_order_article_id:
            return
        if not self.is_stage_unlocked(stage_id):
            messagebox.showerror("Locked Stage", "Complete previous stage first to unlock this stage.")
            return
        progress_rows = self.db.order_progress(self.selected_order_id, self.selected_order_article_id)
        current_note = ""
        for row in progress_rows:
            if row["stage_id"] == stage_id:
                current_note = row["note"] or ""
                break
        if status == "Completed":
            for row in progress_rows:
                if int(row["stage_id"]) == int(stage_id):
                    break
                if row["status"] != "Completed":
                    messagebox.showerror(
                        "Dependency",
                        f"Cannot complete this stage before completing previous stage: {row['stage_name']}.",
                    )
                    return
        self.db.update_stage(self.selected_order_id, stage_id, status, current_note, self.selected_order_article_id)
        self.refresh_stage_progress()
        self.refresh_dashboard()
        next_stage_id = self.get_next_stage_id(stage_id)
        if next_stage_id is not None:
            self.select_stage_row(next_stage_id)
            self.set_qc_stage_selection(next_stage_id)
        self.update_stage_detail_panel()

    def is_stage_unlocked(self, stage_id: int, progress_rows=None) -> bool:
        if progress_rows is None:
            if not self.selected_order_id or not self.selected_order_article_id:
                return False
            progress_rows = self.db.order_progress(self.selected_order_id, self.selected_order_article_id)
        prev_completed = True
        for row in progress_rows:
            if int(row["stage_id"]) == int(stage_id):
                return prev_completed
            prev_completed = prev_completed and (row["status"] == "Completed")
        return False

    def handle_update_stage(self):
        if not self.selected_order_id:
            messagebox.showerror("Selection", "Select an order first.")
            return
        selected = self.stage_tree.selection()
        if not selected:
            messagebox.showerror("Selection", "Select a stage row to update.")
            return

        values = self.stage_tree.item(selected[0], "values")
        stage_id = int(values[0])
        status = values[2]
        self.apply_stage_status_from_tree(stage_id, status)

    def handle_save_qc(self):
        if not self.selected_order_id or not self.selected_order_article_id:
            messagebox.showerror("Selection", "Select an order first.")
            return

        stage_value = self.qc_stage_var.get().strip()
        if not stage_value:
            messagebox.showerror("Validation", "Select a stage for quality check.")
            return

        try:
            stage_id = int(stage_value.split(" - ", 1)[0])
        except (ValueError, IndexError):
            messagebox.showerror("Validation", "Invalid stage selection.")
            return

        result = self.qc_result_var.get().strip()
        inspector = self.inspector_var.get().strip()
        remarks = self.remarks_var.get().strip()

        try:
            defects = int(self.defects_var.get().strip() or "0")
            if defects < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Validation", "Defects found must be 0 or a positive integer.")
            return

        self.db.add_quality_check(
            self.selected_order_id,
            stage_id,
            result,
            inspector,
            defects,
            remarks,
            self.selected_order_article_id,
        )
        self.inspector_var.set("")
        self.defects_var.set("0")
        self.remarks_var.set("")
        self.refresh_qc_history()
        self.refresh_dashboard()
        next_stage_id = self.get_next_stage_id(stage_id)
        if next_stage_id is not None:
            self.set_qc_stage_selection(next_stage_id)
            self.select_stage_row(next_stage_id)


if __name__ == "__main__":
    app = OrderTrackingApp()
    app.mainloop()


