from flask import Blueprint, render_template, request, redirect, session, url_for, flash, jsonify
from services.transactions_service import add_transaction
from services.inventory_service import get_unique_categories
from services.transactions_service import add_item_to_db, get_status_class
from utils.formatters import format_date
from db.database import get_db
from datetime import datetime

transaction_bp = Blueprint('transaction', __name__)

@transaction_bp.route("/transaction/out")
def transaction_out():
    conn = get_db()

    # Only ACTIVE payment methods
    payment_methods = conn.execute("""
        SELECT id, name, category
        FROM payment_methods
        WHERE is_active = 1
        ORDER BY category ASC, name ASC
    """).fetchall()

    # Default IDs for "simple categories" (no provider selection needed)
    # NOTE (future branches): add branch_id filter here later.
    cash_pm = conn.execute("""
        SELECT id
        FROM payment_methods
        WHERE category = 'Cash' AND is_active = 1
        ORDER BY id ASC
        LIMIT 1
    """).fetchone()

    debt_pm = conn.execute("""
        SELECT id
        FROM payment_methods
        WHERE category = 'Debt' AND is_active = 1
        ORDER BY id ASC
        LIMIT 1
    """).fetchone()

    others_pm = conn.execute("""
        SELECT id
        FROM payment_methods
        WHERE category = 'Others'
        AND is_active = 1
        ORDER BY id ASC
        LIMIT 1
    """).fetchone()


    mechanics = conn.execute("""
        SELECT id, name
        FROM mechanics
        WHERE is_active = 1
    """).fetchall()

    conn.close()

    return render_template(
        "transactions/out.html",
        payment_methods=payment_methods,
        mechanics=mechanics,
        cash_pm_id=cash_pm["id"] if cash_pm else None,
        debt_pm_id=debt_pm["id"] if debt_pm else None,
        others_pm_id=others_pm["id"] if others_pm else None,
    )

@transaction_bp.route("/transaction/in")
def transaction_in():
    prefilled_id = request.args.get('selected_id')
    return render_template("transactions/in.html", prefilled_id=prefilled_id)

@transaction_bp.route("/transaction/items")
def manage_items():
    categories = get_unique_categories()
    return render_template("transactions/items.html", categories=categories)

@transaction_bp.route("/items/add", methods=["POST"])
def add_item():
    form_data = {
        'name': request.form.get("name"),
        'category': request.form.get("category"),
        'description': request.form.get("description"),
        'pack_size': request.form.get("pack_size"),
        'vendor_price': request.form.get("vendor_price") or 0,
        'cost_per_piece': request.form.get("cost_per_piece") or 0,
        'selling_price': request.form.get("a4s_selling_price") or 0,
        'markup': request.form.get("markup") or 0,
        'reorder_level': request.form.get("reorder_level") or 0,
        'vendor': request.form.get("vendor"),
        'mechanic': request.form.get("mechanic")
    }

    new_item_id = add_item_to_db(form_data)
    return redirect(url_for('transaction.transaction_in', selected_id=new_item_id))

@transaction_bp.route("/inventory/in", methods=["POST"])
def process_transaction_in():
    item_id = request.form.get("item_id")
    quantity = request.form.get("quantity")

    current_user_id = session.get("user_id")
    current_username = session.get("username")

    if item_id and quantity:
        try:
            qty_int = int(quantity)
            add_transaction(
                item_id=item_id,
                quantity=qty_int,
                transaction_type='IN',
                user_id=current_user_id,
                user_name=current_username
            )
            flash(f"Stock updated! Received {qty_int} unit(s).", "success")

        except ValueError:
            flash("Invalid quantity. Please enter a number.", "danger")
        except Exception as e:
            flash(f"System Error: {str(e)}", "danger")
    else:
        flash("Missing item selection or quantity.", "danger")

    return redirect(url_for('transaction.transaction_in'))

@transaction_bp.route("/transaction/out/save", methods=["POST"])
def save_transaction_out():
    data = request.get_json()
    conn = get_db()

    # -----------------------------
    # 0) Normalize + validate payment_method_id
    # -----------------------------
    raw_payment_method_id = data.get("payment_method_id")

    try:
        payment_method_id = int(raw_payment_method_id)
    except (TypeError, ValueError):
        conn.close()
        return jsonify({
            "status": "error",
            "message": "Invalid payment method selected."
        }), 400

    # Safety: payment method must exist + be active
    # NOTE (future branches): add branch_id filter here later.
    pm = conn.execute("""
        SELECT id, category, is_active
        FROM payment_methods
        WHERE id = ?
    """, (payment_method_id,)).fetchone()

    if not pm or pm["is_active"] != 1:
        conn.close()
        return jsonify({
            "status": "error",
            "message": "Invalid or inactive payment method selected."
        }), 400

    payment_category = (pm["category"] or "").strip()

    # Status derived from CATEGORY (no magic numbers)
    # Debt feature relies on these statuses:
    # - 'Unresolved' initial debt
    # - 'Partial' for partial payments
    # - 'Paid' when settled
    sale_status = "Unresolved" if payment_category == "Debt" else "Paid"

    # -----------------------------
    # 1) TIME LOGIC
    # -----------------------------
    now_obj = datetime.now()
    raw_date = data.get('transaction_date')
    current_minute = now_obj.strftime("%Y-%m-%d %H:%M")

    if raw_date:
        clean_time = raw_date.replace('T', ' ')
        if clean_time[:16] == current_minute or not raw_date:
            clean_time = now_obj.strftime("%Y-%m-%d %H:%M:%S")
        elif len(clean_time) == 16:
            clean_time += ":00"
    else:
        clean_time = now_obj.strftime("%Y-%m-%d %H:%M:%S")

    try:
        conn.execute("BEGIN")

        # 2) Insert SALE
        cursor = conn.execute("""
            INSERT INTO sales (
                sales_number, customer_name, total_amount,
                payment_method_id, reference_no, status,
                notes, user_id, transaction_date, mechanic_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get('sales_number'),
            data.get('customer_name'),
            data.get('total_amount'),
            payment_method_id,
            data.get('reference_no'),
            sale_status,
            data.get('notes'),
            session.get('user_id'),
            clean_time,
            data.get('mechanic_id') or None
        ))

        new_sale_id = cursor.lastrowid

        # 3) Physical items (OUT)
        for item in data.get('items', []):
            original_price = float(item.get('original_price', 0))
            final_price = float(item.get('final_price', 0))
            discount_percent_whole = float(item.get('discount_percent', 0))

            discount_percent_decimal = discount_percent_whole / 100
            discount_amount = original_price - final_price

            add_transaction(
                item_id=item['item_id'],
                quantity=item['quantity'],
                transaction_type='OUT',
                user_id=session.get('user_id'),
                user_name=session.get('username'),
                reference_id=new_sale_id,
                reference_type='SALE',
                change_reason='CUSTOMER_PURCHASE',
                unit_price=original_price,
                transaction_date=clean_time,
                external_conn=conn
            )

            conn.execute("""
                INSERT INTO sales_items (
                    sale_id, item_id, quantity,
                    original_unit_price, discount_percent, discount_amount, final_unit_price,
                    discounted_by, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                new_sale_id,
                item['item_id'],
                item['quantity'],
                original_price,
                discount_percent_decimal,
                discount_amount,
                final_price,
                session.get('user_id') if discount_percent_whole > 0 else None,
                clean_time
            ))

        # 4) Services subtotal
        service_subtotal = 0
        for service in data.get('services', []):
            price = float(service.get('price', 0))
            service_subtotal += price

            conn.execute("""
                INSERT INTO sales_services (sale_id, service_id, price)
                VALUES (?, ?, ?)
            """, (
                new_sale_id,
                service['service_id'],
                price
            ))

        # 5) Update sale service_fee
        conn.execute("""
            UPDATE sales SET service_fee = ? WHERE id = ?
        """, (service_subtotal, new_sale_id))

        conn.commit()

        flash(f"Sale #{data.get('sales_number')} recorded successfully!", "success")
        return jsonify({"status": "success"}), 200

    except Exception as e:
        conn.rollback()
        print(f"DATABASE ERROR: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


# --- PURCHASE ORDER ROUTES ---

@transaction_bp.route("/transaction/order")
def create_order_page():
    return render_template("transactions/order.html")

@transaction_bp.route("/transaction/order/save", methods=["POST"])
def save_purchase_order():
    data = request.get_json()
    conn = get_db()

    now_obj = datetime.now()
    clean_time = now_obj.strftime("%Y-%m-%d %H:%M:%S")
    today_str = now_obj.strftime("%Y%m%d")

    try:
        conn.execute("BEGIN")

        count = conn.execute(
            "SELECT COUNT(*) FROM purchase_orders WHERE po_number LIKE ?",
            (f"PO-{today_str}%",)
        ).fetchone()[0]

        po_number = f"PO-{today_str}-{str(count + 1).zfill(3)}"

        cursor = conn.execute("""
            INSERT INTO purchase_orders (po_number, vendor_name, notes, status, created_by, created_at)
            VALUES (?, ?, ?, 'PENDING', ?, ?)
        """, (po_number, data.get('vendor_name'), data.get('notes'), session.get('user_id'), clean_time))

        new_po_id = cursor.lastrowid

        total_order_amount = 0
        for item in data.get('items', []):
            qty = int(item['qty'])
            cost = float(item['cost'])
            total_order_amount += (qty * cost)

            conn.execute("""
                INSERT INTO po_items (po_id, item_id, quantity_ordered, unit_cost)
                VALUES (?, ?, ?, ?)
            """, (new_po_id, item['id'], qty, cost))

            add_transaction(
                item_id=item['id'],
                quantity=qty,
                transaction_type='ORDER',
                user_id=session.get('user_id'),
                user_name=session.get('username'),
                reference_id=new_po_id,
                reference_type='PURCHASE_ORDER',
                change_reason='ORDER_PLACEMENT',
                unit_price=cost,
                transaction_date=clean_time,
                external_conn=conn
            )

        conn.execute(
            "UPDATE purchase_orders SET total_amount = ? WHERE id = ?",
            (total_order_amount, new_po_id)
        )

        conn.commit()
        flash(f"Purchase Order {po_number} saved and logged!", "success")
        return jsonify({"status": "success", "po_id": new_po_id}), 200

    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

@transaction_bp.route("/transaction/orders/list")
def list_orders():
    conn = get_db()
    orders = conn.execute("""
        SELECT po.*,
            (SELECT COUNT(*) FROM po_items WHERE po_id = po.id) as item_count
        FROM purchase_orders po
        ORDER BY created_at DESC
    """).fetchall()
    conn.close()
    return render_template("transactions/order_overview.html", orders=orders)

@transaction_bp.route("/api/order/<int:po_id>")
def get_order_details(po_id):
    conn = get_db()
    po = conn.execute("SELECT * FROM purchase_orders WHERE id = ?", (po_id,)).fetchone()
    items = conn.execute("""
        SELECT pi.*, i.name
        FROM po_items pi
        JOIN items i ON pi.item_id = i.id
        WHERE pi.po_id = ?
    """, (po_id,)).fetchall()
    conn.close()

    return jsonify({
        "po": dict(po),
        "items": [dict(ix) for ix in items]
    })

@transaction_bp.route("/transaction/receive/<int:po_id>")
def receive_order_page(po_id):
    conn = get_db()
    po = conn.execute("SELECT * FROM purchase_orders WHERE id = ?", (po_id,)).fetchone()

    if po['status'] == 'COMPLETED':
        flash("This order is already completed.", "info")
        return redirect(url_for('transaction.list_orders'))

    items = conn.execute("""
        SELECT pi.*, i.name, i.pack_size
        FROM po_items pi
        JOIN items i ON pi.item_id = i.id
        WHERE pi.po_id = ?
    """, (po_id,)).fetchall()
    conn.close()

    return render_template("transactions/receive.html", po=po, items=items)

@transaction_bp.route("/transaction/receive/confirm", methods=["POST"])
def confirm_reception():
    data = request.get_json()
    po_id = data.get('po_id')
    received_items = data.get('items')

    clean_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db()
    try:
        conn.execute("BEGIN")

        all_completed = True

        for entry in received_items:
            item_id = entry['item_id']
            qty_in = int(entry['qty_received'])
            item_notes = entry.get('notes', '').strip()

            if qty_in <= 0:
                continue

            # Fetch ordered/received counts and unit cost from the PO
            po_item = conn.execute("""
                SELECT quantity_ordered, quantity_received, unit_cost
                FROM po_items
                WHERE po_id = ? AND item_id = ?
            """, (po_id, item_id)).fetchone()

            if not po_item:
                conn.rollback()
                return jsonify({"status": "error", "message": f"Item ID {item_id} not found in this PO."}), 400

            already_received = po_item['quantity_received']
            qty_ordered = po_item['quantity_ordered']
            remaining = qty_ordered - already_received
            unit_cost = po_item['unit_cost']

            is_over_receive = qty_in > remaining

            # Server-side enforcement: notes mandatory for over-receives
            # Cannot be bypassed even via direct API calls
            if is_over_receive and not item_notes:
                conn.rollback()
                return jsonify({
                    "status": "error",
                    "message": f"A reason note is required for over-receiving item ID {item_id}."
                }), 400

            if is_over_receive:
                # Split into two ledger entries for clean audit trail:
                # 1. Normal PO_ARRIVAL for the expected quantity
                # 2. BONUS_STOCK for the excess units

                if remaining > 0:
                    add_transaction(
                        item_id=item_id,
                        quantity=remaining,
                        transaction_type='IN',
                        user_id=session.get('user_id'),
                        user_name=session.get('username'),
                        reference_id=po_id,
                        reference_type='PURCHASE_ORDER',
                        change_reason='PO_ARRIVAL',
                        unit_price=unit_cost,
                        transaction_date=clean_time,
                        external_conn=conn
                    )

                excess = qty_in - remaining
                add_transaction(
                    item_id=item_id,
                    quantity=excess,
                    transaction_type='IN',
                    user_id=session.get('user_id'),
                    user_name=session.get('username'),
                    reference_id=po_id,
                    reference_type='PURCHASE_ORDER',
                    change_reason='BONUS_STOCK',
                    unit_price=unit_cost,  # Inherits original PO unit cost
                    transaction_date=clean_time,
                    external_conn=conn,
                    notes=item_notes
                )

            else:
                # PO_ARRIVAL = full receive for this item
                # PARTIAL_ARRIVAL = this item still has outstanding quantity after this receive
                will_still_have_remaining = (already_received + qty_in) < qty_ordered
                arrival_reason = 'PARTIAL_ARRIVAL' if will_still_have_remaining else 'PO_ARRIVAL'
                add_transaction(
                    item_id=item_id,
                    quantity=qty_in,
                    transaction_type='IN',
                    user_id=session.get('user_id'),
                    user_name=session.get('username'),
                    reference_id=po_id,
                    reference_type='PURCHASE_ORDER',
                    change_reason=arrival_reason,
                    unit_price=unit_cost,
                    transaction_date=clean_time,
                    external_conn=conn
                )

            conn.execute("""
                UPDATE po_items
                SET quantity_received = quantity_received + ?
                WHERE po_id = ? AND item_id = ?
            """, (qty_in, po_id, item_id))

            # Re-check after update — over-receives count as completed
            updated = conn.execute("""
                SELECT quantity_ordered, quantity_received
                FROM po_items
                WHERE po_id = ? AND item_id = ?
            """, (po_id, item_id)).fetchone()

            if updated['quantity_received'] < updated['quantity_ordered']:
                all_completed = False

        new_status = 'COMPLETED' if all_completed else 'PARTIAL'
        conn.execute("""
            UPDATE purchase_orders
            SET status = ?, received_at = ?
            WHERE id = ?
        """, (new_status, clean_time, po_id))

        conn.commit()
        flash("Stock received and added successfully!", "success")
        return jsonify({"status": "success"})
    except ValueError as e:
        conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "message": str(e)})
    finally:
        conn.close()

@transaction_bp.route("/purchase-order/details/<int:po_id>")
def get_po_details(po_id):
    conn = get_db()
    po = conn.execute("""
        SELECT po_number, vendor_name, status, total_amount, created_at, received_at
        FROM purchase_orders
        WHERE id = ?
    """, (po_id,)).fetchone()

    if not po:
        conn.close()
        return jsonify({"error": "Order not found"}), 404

    mode = 'IN' if po['received_at'] else 'ORDER'
    display_created_at = format_date(po['created_at'], show_time=True)
    display_received_at = format_date(po['received_at'], show_time=True)

    items = conn.execute("""
        SELECT i.name,
            pi.quantity_ordered,
            pi.unit_cost AS unit_price,
            (pi.quantity_ordered * pi.unit_cost) AS subtotal
        FROM po_items pi
        JOIN items i ON pi.item_id = i.id
        WHERE pi.po_id = ?
    """, (po_id,)).fetchall()
    conn.close()

    return jsonify({
        "po_number": po['po_number'],
        "vendor_name": po['vendor_name'],
        "status": po['status'] or "Pending",
        "status_class": get_status_class(po['status']),
        "total_amount": po['total_amount'],
        "mode": mode,
        "created_at": display_created_at,
        "received_at": display_received_at,
        "items": [
            {
                "name": item['name'],
                "quantity_ordered": item['quantity_ordered'],
                "unit_price": float(item['unit_price']),
                "subtotal": float(item['subtotal'])
            }
            for item in items
        ]
    })