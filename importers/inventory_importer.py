import csv
import difflib
from datetime import datetime
from db.database import get_db

def import_inventory_csv(file):
    if not file or not file.filename.endswith(".csv"):
        return False, "Invalid file"

    conn = get_db()

    items = conn.execute("SELECT id, name FROM items").fetchall()
    item_lookup = {
        i["name"].strip().lower(): i["id"]
        for i in items
    }

    def find_item_id(name):
        if not name:
            return None

        key = name.strip().lower()
        if key in item_lookup:
            return item_lookup[key]

        matches = difflib.get_close_matches(
            key, item_lookup.keys(), n=1, cutoff=0.85
        )
        return item_lookup[matches[0]] if matches else None

    lines = file.stream.read().decode("utf-8", errors="ignore").splitlines()
    reader = csv.DictReader(lines)

    imported = 0
    skipped = 0

    skip_reasons = {
        "missing_fields": 0,
        "bad_quantity": 0,
        "item_not_found": 0
    }

    for row in reader:
        normalized = {k.strip().lower(): v for k, v in row.items()}

        item_name = (
            normalized.get("inventory id")
            or normalized.get("item name")
            or ""
        ).strip()

        qty_raw = (
            normalized.get("qty on hand")
            or normalized.get("quantity on hand")
            or ""
        ).strip()

        if not item_name or not qty_raw:
            skipped += 1
            skip_reasons["missing_fields"] += 1
            continue

        try:
            quantity = int(float(qty_raw.replace(",", "")))
        except ValueError:
            skipped += 1
            skip_reasons["bad_quantity"] += 1
            continue

        if quantity <= 0:
            skipped += 1
            skip_reasons["bad_quantity"] += 1
            continue

        item_id = find_item_id(item_name)
        if not item_id:
            skipped += 1
            skip_reasons["item_not_found"] += 1
            continue

        conn.execute("""
            INSERT INTO inventory_transactions
            (item_id, quantity, transaction_type, transaction_date)
            VALUES (?, ?, 'IN', ?)
        """, (
            item_id,
            quantity,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

        imported += 1

    conn.commit()
    conn.close()

    return True, {
        "imported": imported,
        "skipped": skipped,
        "skip_reasons": skip_reasons
    }
