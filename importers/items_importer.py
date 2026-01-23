import csv
from db.database import get_db

def import_items_csv(file):
    if not file or not file.filename.endswith(".csv"):
        return False

    conn = get_db()

    lines = file.stream.read().decode("utf-8").splitlines()
    reader = csv.DictReader(lines)

    for row in reader:
        normalized_row = {k.strip().lower(): v for k, v in row.items()}

        def get_value(key, default=None, cast=str):
            raw_value = normalized_row.get(key.lower(), default) or default

            if cast == float and isinstance(raw_value, str):
                raw_value = "".join(c for c in raw_value if c.isdigit() or c in ".-")
                if raw_value == "":
                    return 0.0

            try:
                return cast(raw_value)
            except (ValueError, TypeError):
                return default

        conn.execute("""
            INSERT OR IGNORE INTO items (
                name,
                description,
                pack_size,
                cost_per_piece,
                selling_price,
                category,
                reorder_level,
                vendor,
                mechanic
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            get_value("item name", "", str).strip(),
            get_value("description", "", str),
            get_value("pack size", "", str),
            get_value("cost per piece", 0, float),
            get_value("a4s selling price", 0, float),
            get_value("pms/acc/svc", "", str),
            get_value("minimum inv level", 0, int),
            get_value("vendor list", "", str),
            get_value("mechanic", "", str)
        ))

    conn.commit()
    conn.close()
    return True
