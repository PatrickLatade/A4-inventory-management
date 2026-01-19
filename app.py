from flask import Flask, render_template, request, redirect
from flask import Response
from flask import jsonify
import sqlite3
import csv

app = Flask(__name__)

def get_db():
    conn = sqlite3.connect("inventory.db")
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/", methods=["GET", "POST"])
def index():
    conn = get_db()

    # Create table if not exists
    conn.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        description TEXT,
        pack_size TEXT,
        cost_per_piece REAL,
        selling_price REAL,
        category TEXT,
        reorder_level INTEGER DEFAULT 0,
        vendor TEXT,
        mechanic TEXT
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS inventory_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        transaction_type TEXT CHECK(transaction_type IN ('IN', 'OUT')),
        transaction_date DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (item_id) REFERENCES items(id)
    )
    """)

    if request.method == "POST":
        action = request.form["action"]
        item_id = request.form["item_id"]
        quantity = int(request.form["quantity"])

        conn.execute("""
            INSERT INTO inventory_transactions (item_id, quantity, transaction_type)
            VALUES (?, ?, ?)
        """, (item_id, quantity, action))

        conn.commit()
        return redirect("/")

    items = conn.execute("""
    SELECT 
        items.id,
        items.name,
        COALESCE(SUM(
            CASE 
                WHEN inventory_transactions.transaction_type = 'IN'
                THEN inventory_transactions.quantity
                WHEN inventory_transactions.transaction_type = 'OUT'
                AND inventory_transactions.transaction_date >= '2026-01-18'
                THEN -inventory_transactions.quantity
                ELSE 0
            END
        ), 0) AS current_stock
    FROM items
    LEFT JOIN inventory_transactions
        ON items.id = inventory_transactions.item_id
    GROUP BY items.id;
    """).fetchall()

    return render_template("index.html", items=items)

@app.route("/analytics")
def analytics():
    conn = get_db()

    hot_items = conn.execute("""
        SELECT 
            items.name,
            SUM(inventory_transactions.quantity) AS total_sold_last_30_days
        FROM inventory_transactions
        JOIN items ON items.id = inventory_transactions.item_id
        WHERE inventory_transactions.transaction_type = 'OUT'
        AND inventory_transactions.transaction_date >= datetime('now', '-30 days')
        GROUP BY items.id
        ORDER BY total_sold_last_30_days DESC
        LIMIT 5
    """).fetchall()

    conn.close()
    return render_template("analytics.html", hot_items=hot_items)

@app.route("/dead-stock")
def dead_stock():
    conn = get_db()

    dead_items = conn.execute("""
        SELECT 
            items.name,
            MAX(inventory_transactions.transaction_date) AS last_sold
        FROM items
        LEFT JOIN inventory_transactions 
            ON items.id = inventory_transactions.item_id
            AND inventory_transactions.transaction_type = 'OUT'
        GROUP BY items.id
        HAVING 
            last_sold IS NULL
            OR last_sold <= datetime('now', '-60 days')
    """).fetchall()

    conn.close()
    return render_template("dead_stock.html", dead_items=dead_items)

@app.route("/low-stock")
def low_stock():
    conn = get_db()

    low_stock_items = conn.execute("""
        SELECT 
            items.name,
            items.reorder_level,
            COALESCE(SUM(
                CASE 
                    WHEN inventory_transactions.transaction_type = 'IN'
                    THEN inventory_transactions.quantity
                    ELSE -inventory_transactions.quantity
                END
            ), 0) AS current_stock
        FROM items
        LEFT JOIN inventory_transactions
            ON items.id = inventory_transactions.item_id
        GROUP BY items.id
        HAVING current_stock <= items.reorder_level
        ORDER BY current_stock ASC
    """).fetchall()

    conn.close()
    return render_template("low_stock.html", low_stock_items=low_stock_items)

@app.route("/dashboard")
def dashboard():
    conn = get_db()

    # Total items
    total_items = conn.execute(
        "SELECT COUNT(*) FROM items"
    ).fetchone()[0]

    # Total stock across all items
    total_stock = conn.execute("""
        SELECT COALESCE(SUM(
            CASE 
                WHEN transaction_type = 'IN' THEN quantity
                ELSE -quantity
            END
        ), 0)
        FROM inventory_transactions
    """).fetchone()[0]

    # Low stock count
    low_stock_count = conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT items.id,
            COALESCE(SUM(
                CASE 
                    WHEN inventory_transactions.transaction_type = 'IN'
                    THEN inventory_transactions.quantity
                    ELSE -inventory_transactions.quantity
                END
            ), 0) AS current_stock
            FROM items
            LEFT JOIN inventory_transactions
                ON items.id = inventory_transactions.item_id
            GROUP BY items.id
            HAVING current_stock <= items.reorder_level
        )
    """).fetchone()[0]

    # Top moving item (last 30 days)
    top_item = conn.execute("""
        SELECT items.name, SUM(inventory_transactions.quantity) AS total_sold
        FROM inventory_transactions
        JOIN items ON items.id = inventory_transactions.item_id
        WHERE inventory_transactions.transaction_type = 'OUT'
        AND inventory_transactions.transaction_date >= datetime('now', '-30 days')
        GROUP BY items.id
        ORDER BY total_sold DESC
        LIMIT 1
    """).fetchone()

    items = conn.execute("SELECT id, name FROM items").fetchall()

    conn.close()

    return render_template(
        "dashboard.html",
        total_items=total_items,
        total_stock=total_stock,
        low_stock_count=low_stock_count,
        top_item=top_item,
        items=items
    )

@app.route("/dashboard/stock-movement")
def stock_movement():
    days = request.args.get("days", default=30, type=int)

    conn = get_db()
    rows = conn.execute("""
        SELECT 
            DATE(transaction_date) AS date,
            SUM(
                CASE 
                    WHEN transaction_type = 'IN' THEN quantity
                    ELSE -quantity
                END
            ) AS net_change
        FROM inventory_transactions
        WHERE transaction_date >= datetime('now', ?)
        GROUP BY DATE(transaction_date)
        ORDER BY DATE(transaction_date)
    """, (f"-{days} days",)).fetchall()

    conn.close()

    return {
        "labels": [row["date"] for row in rows],
        "values": [row["net_change"] for row in rows]
    }

@app.route("/dashboard/item-movement")
def item_movement():
    item_id = request.args.get("item_id", type=int)
    days = request.args.get("days", default=30, type=int)

    conn = get_db()

    rows = conn.execute("""
        SELECT 
            DATE(transaction_date) AS date,
            SUM(
                CASE 
                    WHEN transaction_type = 'IN' THEN quantity
                    ELSE -quantity
                END
            ) AS net_change
        FROM inventory_transactions
        WHERE item_id = ?
        AND transaction_date >= datetime('now', ?)
        GROUP BY DATE(transaction_date)
        ORDER BY DATE(transaction_date)
    """, (item_id, f"-{days} days")).fetchall()

    conn.close()

    return {
        "labels": [row["date"] for row in rows],
        "values": [row["net_change"] for row in rows]
    }

@app.route("/dashboard/top-items")
def top_items_chart():
    days = request.args.get("days", default=30, type=int)
    conn = get_db()

    rows = conn.execute("""
        SELECT 
            items.name,
            SUM(inventory_transactions.quantity) AS total_out
        FROM inventory_transactions
        JOIN items ON items.id = inventory_transactions.item_id
        WHERE inventory_transactions.transaction_type = 'OUT'
        AND inventory_transactions.transaction_date >= datetime('now', ?)
        GROUP BY items.id
        ORDER BY total_out DESC
        LIMIT 5
    """, (f"-{days} days",)).fetchall()

    conn.close()

    return {
        "labels": [row["name"] for row in rows],
        "values": [row["total_out"] for row in rows]
    }

@app.route("/add-item", methods=["POST"])
def add_item():
    name = request.form["name"]
    reorder_level = int(request.form["reorder_level"])

    conn = get_db()
    conn.execute(
        "INSERT INTO items (name, reorder_level) VALUES (?, ?)",
        (name, reorder_level)
    )
    conn.commit()
    conn.close()

    return redirect("/")

@app.route("/export/transactions")
def export_transactions():
    conn = get_db()
    rows = conn.execute("""
        SELECT 
            items.name AS item,
            inventory_transactions.transaction_type,
            inventory_transactions.quantity,
            inventory_transactions.transaction_date
        FROM inventory_transactions
        JOIN items ON items.id = inventory_transactions.item_id
        ORDER BY inventory_transactions.transaction_date DESC
    """).fetchall()
    conn.close()

    def generate():
        yield "Item,Type,Quantity,Date\n"
        for row in rows:
            yield f"{row['item']},{row['transaction_type']},{row['quantity']},{row['transaction_date']}\n"

    return Response(
        generate(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=inventory_transactions.csv"}
    )

@app.route("/import/items", methods=["POST"])
def import_items():
    file = request.files.get("file")

    if not file or not file.filename.endswith(".csv"):
        return "Invalid file", 400

    conn = get_db()

    # Read CSV lines and decode
    lines = file.stream.read().decode("utf-8").splitlines()
    reader = csv.DictReader(lines)

    for row in reader:
        # Normalize headers: strip spaces and lowercase
        normalized_row = {k.strip().lower(): v for k, v in row.items()}

        # Helper function to safely get values
        def get_value(key, default=None, cast=str):
            raw_value = normalized_row.get(key.lower(), default) or default

            if cast == float and isinstance(raw_value, str):
                # Remove any non-numeric characters except dot and minus
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

    return redirect("/")

@app.route("/import/sales", methods=["POST"])
def import_sales():
    file = request.files.get("file")

    if not file or not file.filename.endswith(".csv"):
        return "Invalid file", 400

    conn = get_db()

    lines = file.stream.read().decode("utf-8", errors="ignore").splitlines()
    reader = csv.DictReader(lines)

    imported = 0
    skipped = 0

    skip_reasons = {
        "non_inventory_sale": 0,
        "missing_fields": 0,
        "bad_quantity": 0,
        "item_not_found": 0,
        "other": 0
    }

    skipped_rows = []

    # 🔹 Preload items once (performance + fuzzy matching)
    items = conn.execute("SELECT id, name FROM items").fetchall()
    item_lookup = {
        item["name"].strip().lower(): item["id"]
        for item in items
    }

    def find_item_id(item_name):
        key = item_name.strip().lower()

        # Exact match
        if key in item_lookup:
            return item_lookup[key]

        # Fuzzy match
        import difflib
        matches = difflib.get_close_matches(
            key,
            item_lookup.keys(),
            n=1,
            cutoff=0.85
        )

        if matches:
            return item_lookup[matches[0]]

        return None

    for row in reader:
        try:
            # Normalize headers
            normalized = {k.strip().lower(): v for k, v in row.items()}

            sales_type = (normalized.get("sales type") or "").strip().lower()
            if sales_type != "inventory":
                skip_reasons["non_inventory_sale"] += 1
                skipped += 1
                continue

            item_name = (normalized.get("part number") or "").strip()
            qty_raw = normalized.get("qty pc")
            date_raw = normalized.get("tr date")

            if not item_name or not qty_raw or not date_raw:
                skip_reasons["missing_fields"] += 1
                skipped_rows.append({**row, "skip_reason": "Missing required fields"})
                skipped += 1
                continue

            try:
                quantity = int(float(qty_raw))
            except:
                skip_reasons["bad_quantity"] += 1
                skipped_rows.append({**row, "skip_reason": "Invalid quantity"})
                skipped += 1
                continue

            if quantity <= 0:
                skip_reasons["bad_quantity"] += 1
                skipped_rows.append({**row, "skip_reason": "Zero or negative quantity"})
                skipped += 1
                continue

            item_id = find_item_id(item_name)

            if not item_id:
                skip_reasons["item_not_found"] += 1
                skipped_rows.append({**row, "skip_reason": "Item not found"})
                skipped += 1
                continue

            conn.execute("""
                INSERT INTO inventory_transactions
                (item_id, quantity, transaction_type, transaction_date)
                VALUES (?, ?, 'OUT', ?)
            """, (item_id, quantity, date_raw))

            imported += 1

        except Exception as e:
            skip_reasons["other"] += 1
            skipped_rows.append({**row, "skip_reason": str(e)})
            skipped += 1

    conn.commit()
    conn.close()

    # 🔹 Export skipped rows for audit / client review
    if skipped_rows:
        with open("skipped_sales_rows.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=skipped_rows[0].keys())
            writer.writeheader()
            writer.writerows(skipped_rows)

    # 🔹 Console summary (useful during demo prep)
    print("Sales import complete")
    print(f"Imported: {imported}")
    print(f"Skipped: {skipped}")
    print("Skip breakdown:")
    for reason, count in skip_reasons.items():
        print(f"  {reason}: {count}")

    return f"Sales import complete. Imported: {imported}, Skipped: {skipped}"

@app.route("/import/inventory", methods=["POST"])
def import_inventory():
    import csv, difflib
    from datetime import datetime

    file = request.files.get("file")
    if not file or not file.filename.endswith(".csv"):
        return "Invalid file", 400

    conn = get_db()

    # Load all items once for fast lookup
    items = conn.execute("SELECT id, name FROM items").fetchall()
    item_lookup = {
        i["name"].strip().lower(): i["id"]
        for i in items
    }

    def find_item_id(name):
        if not name:
            return None

        key = name.strip().lower()

        # Exact match
        if key in item_lookup:
            return item_lookup[key]

        # Fuzzy match
        matches = difflib.get_close_matches(
            key, item_lookup.keys(), n=1, cutoff=0.85
        )
        if matches:
            return item_lookup[matches[0]]

        return None

    # Read CSV
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
        # Normalize headers
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

        # Clean quantity
        try:
            qty_clean = qty_raw.replace(",", "")
            quantity = int(float(qty_clean))
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

        # Insert baseline stock as IN transaction
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

    return (
        f"Inventory import complete.<br>"
        f"Imported: {imported}<br>"
        f"Skipped: {skipped}<br><br>"
        f"Skip reasons:<br>"
        f"- Missing fields: {skip_reasons['missing_fields']}<br>"
        f"- Bad quantity: {skip_reasons['bad_quantity']}<br>"
        f"- Item not found: {skip_reasons['item_not_found']}"
    )

@app.route("/index2", methods=["GET", "POST"])
def index2():
    # We call the exact same index() function logic 
    # but we will manually render the other template at the end.
    conn = get_db()
    
    # Handle the POST (Form Submission) just like the main index
    if request.method == "POST":
        action = request.form["action"]
        item_id = request.form["item_id"]
        quantity = int(request.form["quantity"])
        conn.execute("""
            INSERT INTO inventory_transactions (item_id, quantity, transaction_type)
            VALUES (?, ?, ?)
        """, (item_id, quantity, action))
        conn.commit()
        return redirect("/index2") # Stay on the design 2 page after submitting

    # Fetch the same items list
    items = conn.execute("""
    SELECT 
        items.id,
        items.name,
        COALESCE(SUM(
            CASE 
                WHEN inventory_transactions.transaction_type = 'IN' 
                THEN inventory_transactions.quantity
                ELSE -inventory_transactions.quantity
            END
        ), 0) AS current_stock
    FROM items
    LEFT JOIN inventory_transactions
        ON items.id = inventory_transactions.item_id
    GROUP BY items.id
    """).fetchall()

    # THE ONLY DIFFERENCE: We render index2.html here
    return render_template("index2.html", items=items)

@app.route("/debug-integrity")
def debug_integrity():
    conn = get_db()

    # 1️⃣ Global totals
    totals = conn.execute("""
        SELECT
            SUM(CASE WHEN transaction_type = 'IN' THEN quantity ELSE 0 END) AS total_in,
            SUM(CASE WHEN transaction_type = 'OUT' THEN quantity ELSE 0 END) AS total_out
        FROM inventory_transactions
    """).fetchone()

    # 2️⃣ Items with negative stock
    negative_items = conn.execute("""
        SELECT 
            items.name,
            COALESCE(SUM(
                CASE 
                    WHEN inventory_transactions.transaction_type = 'IN'
                    THEN inventory_transactions.quantity
                    ELSE -inventory_transactions.quantity
                END
            ), 0) AS current_stock
        FROM items
        LEFT JOIN inventory_transactions
            ON items.id = inventory_transactions.item_id
        GROUP BY items.id
        HAVING current_stock < 0
    """).fetchall()

    # 3️⃣ Snapshot vs recent sales check
    snapshot_date = "2026-01-18"

    snapshot_check = conn.execute("""
        SELECT
            items.name,
            SUM(CASE 
                WHEN inventory_transactions.transaction_type = 'IN'
                     AND inventory_transactions.transaction_date = ?
                THEN inventory_transactions.quantity
                ELSE 0
            END) AS snapshot_qty,

            SUM(CASE
                WHEN inventory_transactions.transaction_type = 'OUT'
                     AND inventory_transactions.transaction_date >= ?
                THEN inventory_transactions.quantity
                ELSE 0
            END) AS recent_sales
        FROM items
        LEFT JOIN inventory_transactions
            ON items.id = inventory_transactions.item_id
        GROUP BY items.id
        HAVING snapshot_qty > 0
    """, (snapshot_date, snapshot_date)).fetchall()

    # 4️⃣ Date sanity check
    date_ranges = conn.execute("""
        SELECT
            MIN(transaction_date) AS earliest,
            MAX(transaction_date) AS latest
        FROM inventory_transactions
    """).fetchone()

    conn.close()

    return render_template(
        "debug_integrity.html",
        totals=totals,
        negative_items=negative_items,
        snapshot_check=snapshot_check,
        date_ranges=date_ranges
    )

if __name__ == "__main__":
    app.run(debug=True)
