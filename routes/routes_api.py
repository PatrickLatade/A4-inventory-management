from flask import Blueprint, request, jsonify
from db.database import get_db

dashboard_api = Blueprint("dashboard_api", __name__)

@dashboard_api.route("/dashboard/stock-movement")
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

@dashboard_api.route("/dashboard/item-movement")
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

@dashboard_api.route("/dashboard/top-items")
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