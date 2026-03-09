from flask import Blueprint, request, jsonify, render_template
from db.database import get_db
from utils.formatters import format_date

customer_bp = Blueprint('customer', __name__)


# ─────────────────────────────────────────────
# API: Search customers (used in out.html autocomplete)
# ─────────────────────────────────────────────
@customer_bp.route("/api/search/customers")
def search_customers():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({"customers": []})

    conn = get_db()
    rows = conn.execute("""
        SELECT id, customer_no, customer_name
        FROM customers
        WHERE (customer_no LIKE ? OR customer_name LIKE ?)
        AND is_active = 1
        ORDER BY customer_name ASC
        LIMIT 10
    """, (f'%{query}%', f'%{query}%')).fetchall()
    conn.close()

    return jsonify({"customers": [dict(r) for r in rows]})


# ─────────────────────────────────────────────
# API: Add new customer
# ─────────────────────────────────────────────
@customer_bp.route("/api/customers/add", methods=["POST"])
def add_customer():
    data = request.get_json()
    customer_no = (data.get('customer_no') or '').strip()
    customer_name = (data.get('customer_name') or '').strip()
    vehicle_name = (data.get('vehicle_name') or '').strip()

    if not customer_no or not customer_name or not vehicle_name:
        return jsonify({"status": "error", "message": "Customer number, name, and vehicle are required."}), 400

    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO customers (customer_no, customer_name) VALUES (?, ?)",
            (customer_no, customer_name)
        )
        new_customer_id = cursor.lastrowid

        vehicle_cursor = conn.execute(
            "INSERT INTO vehicles (customer_id, vehicle_name, is_active) VALUES (?, ?, 1)",
            (new_customer_id, vehicle_name)
        )
        new_vehicle_id = vehicle_cursor.lastrowid

        conn.commit()
        return jsonify({
            "status": "success",
            "customer": {
                "id": new_customer_id,
                "customer_no": customer_no,
                "customer_name": customer_name
            },
            "vehicle": {
                "id": new_vehicle_id,
                "vehicle_name": vehicle_name
            }
        })
    except Exception as e:
        # Most likely a UNIQUE constraint on customer_no
        conn.rollback()
        if "UNIQUE" in str(e):
            return jsonify({"status": "error", "message": "A customer with that number already exists."}), 409
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


@customer_bp.route("/api/customers/<int:customer_id>/vehicles")
def get_customer_vehicles(customer_id):
    conn = get_db()
    customer = conn.execute(
        "SELECT id FROM customers WHERE id = ? AND is_active = 1",
        (customer_id,)
    ).fetchone()

    if not customer:
        conn.close()
        return jsonify({"error": "Customer not found"}), 404

    vehicles = conn.execute("""
        SELECT id, vehicle_name, is_active
        FROM vehicles
        WHERE customer_id = ? AND is_active = 1
        ORDER BY vehicle_name ASC
    """, (customer_id,)).fetchall()

    conn.close()
    return jsonify({
        "customer_id": customer_id,
        "vehicles": [dict(v) for v in vehicles]
    })


@customer_bp.route("/api/customers/<int:customer_id>/vehicles/add", methods=["POST"])
def add_customer_vehicle(customer_id):
    data = request.get_json(silent=True) or {}
    vehicle_name = (data.get("vehicle_name") or "").strip()

    if not vehicle_name:
        return jsonify({"status": "error", "message": "Vehicle name is required."}), 400

    conn = get_db()
    try:
        customer = conn.execute(
            "SELECT id FROM customers WHERE id = ? AND is_active = 1",
            (customer_id,)
        ).fetchone()

        if not customer:
            return jsonify({"status": "error", "message": "Customer not found."}), 404

        cursor = conn.execute(
            "INSERT INTO vehicles (customer_id, vehicle_name, is_active) VALUES (?, ?, 1)",
            (customer_id, vehicle_name)
        )
        conn.commit()
        return jsonify({
            "status": "success",
            "vehicle": {
                "id": cursor.lastrowid,
                "vehicle_name": vehicle_name
            }
        })
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


# ─────────────────────────────────────────────
# PAGE: Customer list
# ─────────────────────────────────────────────
@customer_bp.route("/customers")
def customer_list():
    conn = get_db()

    customers = conn.execute("""
        SELECT
            c.id,
            c.customer_no,
            c.customer_name,
            c.created_at,
            COUNT(s.id) AS total_visits,
            MAX(s.transaction_date) AS last_visit,
            (
                SELECT GROUP_CONCAT(v.vehicle_name, ', ')
                FROM (SELECT vehicle_name FROM vehicles v2 WHERE v2.customer_id = c.id ORDER BY v2.vehicle_name) v
            ) AS vehicles
        FROM customers c
        LEFT JOIN sales s ON s.customer_id = c.id
        WHERE c.is_active = 1
        GROUP BY c.id
        ORDER BY c.customer_name ASC
    """).fetchall()

    customers = [
        {
            **dict(c),
            "last_visit_display": format_date(c["last_visit"]),
        }
        for c in customers
    ]

    conn.close()
    return render_template("customers/customers_list.html", customers=customers)


# ─────────────────────────────────────────────
# API: Get one customer's transaction history
# ─────────────────────────────────────────────
@customer_bp.route("/api/customers/<int:customer_id>/transactions")
def customer_transactions(customer_id):
    conn = get_db()

    customer = conn.execute("""
        SELECT id, customer_no, customer_name, created_at
        FROM customers WHERE id = ?
    """, (customer_id,)).fetchone()

    if not customer:
        return jsonify({"error": "Customer not found"}), 404

    sales = conn.execute("""
        SELECT
            s.id,
            s.sales_number,
            s.transaction_date,
        s.total_amount,
        s.status,
        v.vehicle_name,
        pm.name AS payment_method
        FROM sales s
        LEFT JOIN payment_methods pm ON pm.id = s.payment_method_id
        LEFT JOIN vehicles v ON v.id = s.vehicle_id
        WHERE s.customer_id = ?
        ORDER BY s.transaction_date DESC
    """, (customer_id,)).fetchall()

    result = []
    for sale in sales:
        # Get services for this sale
        services = conn.execute("""
            SELECT sv.name, ss.price
            FROM sales_services ss
            JOIN services sv ON sv.id = ss.service_id
            WHERE ss.sale_id = ?
        """, (sale['id'],)).fetchall()

        # Get items for this sale
        items = conn.execute("""
            SELECT i.name, si.quantity, si.final_unit_price
            FROM sales_items si
            JOIN items i ON i.id = si.item_id
            WHERE si.sale_id = ?
        """, (sale['id'],)).fetchall()

        result.append({
            "id": sale['id'],
            "sales_number": sale['sales_number'],
            "transaction_date": format_date(sale['transaction_date']),
            "total_amount": sale['total_amount'],
            "status": sale['status'],
            "vehicle_name": sale['vehicle_name'],
            "payment_method": sale['payment_method'],
            "services": [dict(s) for s in services],
            "items": [dict(i) for i in items],
        })

    conn.close()
    return jsonify({
        "customer": {
            **dict(customer),
            "created_at_display": format_date(customer["created_at"])
        },
        "transactions": result
    })
