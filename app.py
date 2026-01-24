# ============================================================
# Flask app entry point
# This file should ONLY contain:
# - app creation
# - route definitions
# - wiring to services / importers
# ============================================================

from flask import Flask, render_template, request, redirect, Response

# ------------------------
# Database & initialization
# ------------------------
from db.database import get_db
from db.schema import init_db

# ------------------------
# Services (business logic)
# ------------------------
from services.inventory_service import get_items_with_stock
from services.transactions_service import add_transaction
from services.analytics_service import (
    get_dashboard_stats,
    get_hot_items,
    get_dead_stock,
    get_low_stock_items
)

# ------------------------
# Importers (CSV handling)
# ------------------------
from importers.items_importer import import_items_csv
from importers.sales_importer import import_sales_csv
from importers.inventory_importer import import_inventory_csv

# ------------------------
# API / blueprints
# ------------------------
from routes.routes_api import dashboard_api


# ============================================================
# App setup
# ============================================================
app = Flask(__name__)
init_db()  # Safe to call on startup (creates tables if missing)

# Register API routes (kept separate from UI routes)
app.register_blueprint(dashboard_api)


# ============================================================
# Core inventory UI
# ============================================================
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        action = request.form["action"]
        item_id = request.form["item_id"]
        quantity = int(request.form["quantity"])
        add_transaction(item_id, quantity, action)
        return redirect("/")

    conn = get_db()

    # 1️⃣ Get current stock using your original function
    items_stock = get_items_with_stock(snapshot_date="2026-01-18")

    # 2️⃣ Fetch all other fields from items table
    extras = conn.execute("""
        SELECT *
        FROM items
    """).fetchall()

    conn.close()

    # 3️⃣ Merge safely: convert Row objects to dicts
    extras_dict = {e["id"]: dict(e) for e in extras}
    items_merged = []
    for item in items_stock:
        merged = dict(item)  # item.id, item.name, current_stock
        merged.update(extras_dict.get(item["id"], {}))  # merge all other columns
        items_merged.append(merged)

    return render_template("index.html", items=items_merged)


# ============================================================
# Analytics / reporting views
# ============================================================
@app.route("/dashboard")
def dashboard():
    """
    High-level KPIs used for management overview.
    """
    (
        total_items,
        total_stock,
        low_stock_count,
        top_item,
        items
    ) = get_dashboard_stats()

    return render_template(
        "dashboard.html",
        total_items=total_items,
        total_stock=total_stock,
        low_stock_count=low_stock_count,
        top_item=top_item,
        items=items
    )


@app.route("/analytics")
def analytics():
    """
    Fast-moving items (last 30 days).
    """
    hot_items = get_hot_items()
    return render_template("analytics.html", hot_items=hot_items)


@app.route("/dead-stock")
def dead_stock():
    """
    Items with no sales for a long time (or never sold).
    """
    dead_items = get_dead_stock()
    return render_template("dead_stock.html", dead_items=dead_items)


@app.route("/low-stock")
def low_stock():
    """
    Items at or below reorder level.
    """
    low_stock_items = get_low_stock_items()
    return render_template("low_stock.html", low_stock_items=low_stock_items)


# ============================================================
# Item & transaction utilities
# ============================================================
@app.route("/add-item", methods=["POST"])
def add_item():
    """
    Add a new inventory item (basic fields only).
    """
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
    """
    Export all inventory transactions as CSV.
    Useful for audits and client handoff.
    """
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
        headers={
            "Content-Disposition": "attachment; filename=inventory_transactions.csv"
        }
    )


# ============================================================
# CSV import endpoints
# ============================================================
@app.route("/import/items", methods=["POST"])
def import_items():
    """
    Import item master list.
    """
    success = import_items_csv(request.files.get("file"))
    if not success:
        return "Invalid file", 400
    return redirect("/")


@app.route("/import/sales", methods=["POST"])
def import_sales():
    """
    Import historical sales (OUT transactions).
    """
    success, result = import_sales_csv(request.files.get("file"))
    if not success:
        return result, 400

    return (
        f"Sales import complete. "
        f"Imported: {result['imported']}, "
        f"Skipped: {result['skipped']}"
    )


@app.route("/import/inventory", methods=["POST"])
def import_inventory():
    """
    Import physical inventory count as baseline IN transactions.
    """
    success, result = import_inventory_csv(request.files.get("file"))
    if not success:
        return result, 400

    return (
        f"Inventory import complete.<br>"
        f"Imported: {result['imported']}<br>"
        f"Skipped: {result['skipped']}<br>"
        f"Missing fields: {result['skip_reasons']['missing_fields']}<br>"
        f"Bad quantity: {result['skip_reasons']['bad_quantity']}<br>"
        f"Item not found: {result['skip_reasons']['item_not_found']}"
    )


# ============================================================
# Experimental / alternate UI
# ============================================================
@app.route("/index2", methods=["GET", "POST"])
def index2():
    """
    Alternate inventory UI (design experiment).
    Logic intentionally duplicated to keep risk isolated.
    """
    conn = get_db()

    if request.method == "POST":
        action = request.form["action"]
        item_id = request.form["item_id"]
        quantity = int(request.form["quantity"])
        add_transaction(item_id, quantity, action)
        conn.commit()
        return redirect("/index2")

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

    conn.close()
    return render_template("index2.html", items=items)


# ============================================================
# Debug / integrity checks (temporary but intentional)
# ============================================================
@app.route("/debug-integrity")
def debug_integrity():
    """
    Data sanity checks during historical reconciliation.
    NOT meant for production use.
    """
    conn = get_db()

    totals = conn.execute("""
        SELECT
            SUM(CASE WHEN transaction_type = 'IN' THEN quantity ELSE 0 END) AS total_in,
            SUM(CASE WHEN transaction_type = 'OUT' THEN quantity ELSE 0 END) AS total_out
        FROM inventory_transactions
    """).fetchone()

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


# ============================================================
# App runner
# ============================================================
if __name__ == "__main__":
    app.run(debug=True)
