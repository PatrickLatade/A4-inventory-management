from flask import Blueprint, render_template, request, redirect, session, flash, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from db.database import get_db
from datetime import datetime
from utils.formatters import format_date

# 1. Initialize the Blueprint
auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        conn.close()

        if not user or not check_password_hash(user["password_hash"], password):
            flash("Invalid username or password", "danger")
            return redirect(url_for("auth.login"))
        
        if user["is_active"] == 0:
            flash("Your account has been disabled. Please contact an administrator.", "warning")
            return redirect(url_for("auth.login"))

        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["role"] = user["role"]

        if user["role"] == "admin":
            return redirect(url_for("auth.manage_users"))
        else:
            return redirect(url_for("index"))

    return render_template("users/login.html")

@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))

@auth_bp.route("/users", methods=["GET", "POST"])
def manage_users():
    conn = get_db()

    # --- 1. HANDLE FORM SUBMISSION ---
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        current_admin_id = session.get("user_id") 
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            conn.execute("""
                INSERT INTO users (username, password_hash, role, created_at, created_by)
                VALUES (?, ?, 'staff', ?, ?)
            """, (username, generate_password_hash(password), now, current_admin_id))
            conn.commit()
            flash(f"Account for {username} created successfully!", "success")
            return redirect(url_for('auth.manage_users'))
        except Exception as e:
            flash(f"Error creating user: {str(e)}", "danger")

    # --- 2. FETCH ALL USERS ---
    users = conn.execute("""
        SELECT u.id, u.username, u.role, u.created_at, u.is_active,
        creator.username AS creator_name
        FROM users u
        LEFT JOIN users creator ON u.created_by = creator.id
        ORDER BY u.created_at DESC
    """).fetchall()

    # --- 2.5 NEW: FETCH SALES HISTORY ---
    # Using your actual table name 'sales' and matching the schema columns
    sales_history = conn.execute("""
        SELECT
            s.id,
            s.transaction_date, 
            s.sales_number, 
            s.customer_name, 
            s.total_amount,
            p.name as payment_method_name
        FROM sales s
        JOIN payment_methods p ON s.payment_method_id = p.id
        ORDER BY s.transaction_date DESC
        LIMIT 20
    """).fetchall()

    # --- 3. NEW: FETCH MECHANICS (This was the missing piece!) ---
    mechanics = conn.execute("SELECT * FROM mechanics ORDER BY name ASC").fetchall()

    # --- 3. FETCH TRANSACTION HISTORY (The Audit Trail / Item Movements) ---
    history = conn.execute("""
        SELECT 
            t.transaction_date, 
            t.transaction_type, 
            SUM(t.quantity) as total_qty, 
            t.user_name,
            t.change_reason,
            t.reference_type,
            t.reference_id,
            s.sales_number,
            po.po_number,  -- Added this
            GROUP_CONCAT(i.name, ', ') as items_summary
        FROM inventory_transactions t
        JOIN items i ON t.item_id = i.id
        LEFT JOIN sales s ON t.reference_id = s.id AND t.reference_type = 'SALE'
        LEFT JOIN purchase_orders po ON t.reference_id = po.id AND t.reference_type = 'PURCHASE_ORDER' -- Added this
        GROUP BY t.reference_id, t.transaction_date, t.transaction_type
        ORDER BY t.transaction_date DESC
        LIMIT 50
    """).fetchall()

    services_list = conn.execute("SELECT * FROM services ORDER BY category ASC, name ASC LIMIT 20").fetchall()
    categories = conn.execute("SELECT DISTINCT category FROM services WHERE category IS NOT NULL").fetchall()

    conn.close()

    # --- 4. FORMAT DATES before passing to template ---
    users = [
        {**dict(u), "created_at": format_date(u["created_at"], show_time=True)}
        for u in users
    ]
    sales_history = [
        {**dict(s), "transaction_date": format_date(s["transaction_date"], show_time=True)}
        for s in sales_history
    ]
    history = [
        {**dict(h), "transaction_date": format_date(h["transaction_date"], show_time=True)}
        for h in history
    ]

    # --- 5. SERVE THE PAGE ---
    return render_template("users/users.html", users=users, history=history, sales_history=sales_history, mechanics=mechanics, services_list=services_list, categories=categories)

@auth_bp.route("/users/toggle/<int:user_id>", methods=["POST"])
def toggle_user(user_id):
    conn = get_db()

    user = conn.execute(
        "SELECT role, is_active, username FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    if not user:
        flash("User not found.", "danger")
        conn.close()
        return redirect(url_for('auth.manage_users'))

    if user['role'] == 'admin':
        flash("Administrator accounts cannot be disabled.", "danger")
        conn.close()
        return redirect(url_for('auth.manage_users'))

    was_active = user['is_active']
    new_status = 0 if was_active == 1 else 1

    conn.execute(
        "UPDATE users SET is_active = ? WHERE id = ?",
        (new_status, user_id)
    )
    conn.commit()

    # 🔔 Alerts
    if new_status == 0:
        flash(f"User {user['username']} has been disabled.", "danger")
    elif was_active == 0 and new_status == 1:
        flash(f"User {user['username']} has been re-enabled.", "warning")
    else:
        flash(f"User {user['username']} has been activated.", "success")

    conn.close()
    return redirect(url_for('auth.manage_users'))


@auth_bp.route("/mechanics/add", methods=["POST"])
def add_mechanic():
    name = request.form.get("name")
    commission = request.form.get("commission")
    phone = request.form.get("phone")
    
    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO mechanics (name, commission_rate, phone, is_active) 
            VALUES (?, ?, ?, 1)
        """, (name, commission, phone))
        conn.commit()
        flash(f"Mechanic {name} added successfully!", "success")
    except Exception as e:
        flash(f"Error adding mechanic: {str(e)}", "danger")
    finally:
        conn.close()
    
    return redirect(url_for('auth.manage_users'))

@auth_bp.route("/mechanics/toggle/<int:mechanic_id>", methods=["POST"])
def toggle_mechanic(mechanic_id):
    conn = get_db()

    mechanic = conn.execute(
        "SELECT is_active, name FROM mechanics WHERE id = ?",
        (mechanic_id,)
    ).fetchone()

    if not mechanic:
        flash("Mechanic not found.", "danger")
        conn.close()
        return redirect(url_for('auth.manage_users'))

    was_active = mechanic['is_active']

    # Toggle
    new_status = 0 if was_active == 1 else 1
    conn.execute(
        "UPDATE mechanics SET is_active = ? WHERE id = ?",
        (new_status, mechanic_id)
    )
    conn.commit()

    # 🔔 Alerts
    if new_status == 0:
        flash(f"Mechanic {mechanic['name']} has been disabled.", "danger")
    elif was_active == 0 and new_status == 1:
        flash(f"Mechanic {mechanic['name']} has been re-enabled.", "warning")
    else:
        flash(f"Mechanic {mechanic['name']} has been activated.", "success")

    conn.close()
    return redirect(url_for('auth.manage_users'))

# --- NEW ROUTE: Get Sale Details for the Modal ---
@auth_bp.route("/sales/details/<reference_id>")
def sale_details(reference_id):
    conn = get_db()
    try:
        # 1. Fetch Sale Metadata (Total, Mechanic, AND Payment Method)
        sale_info = conn.execute("""
            SELECT 
                s.total_amount, 
                m.name as mechanic_name,
                pm.name as payment_method
            FROM sales s
            LEFT JOIN mechanics m ON s.mechanic_id = m.id
            LEFT JOIN payment_methods pm ON s.payment_method_id = pm.id
            WHERE s.id = ?
        """, (reference_id,)).fetchone()

        # 2. Fetch Items
        items = conn.execute("""
            SELECT 
                i.name, 
                t.quantity, 
                t.unit_price as original_price,
                si.discount_amount,
                si.final_unit_price
            FROM inventory_transactions t
            JOIN items i ON t.item_id = i.id
            LEFT JOIN sales_items si ON (t.reference_id = si.sale_id AND t.item_id = si.item_id)
            WHERE CAST(t.reference_id AS TEXT) = ? 
            AND t.reference_type = 'SALE'
        """, (str(reference_id),)).fetchall()

        # 3. Fetch Services
        services = conn.execute("""
            SELECT s.name, ss.price
            FROM sales_services ss
            JOIN services s ON ss.service_id = s.id
            WHERE ss.sale_id = ?
        """, (reference_id,)).fetchall()
        
        return {
            "total_amount": sale_info["total_amount"] if sale_info else 0,
            "mechanic": sale_info["mechanic_name"] if sale_info else None,
            "payment_method": sale_info["payment_method"] if sale_info else "N/A",
            "items": [dict(ix) for ix in items],
            "services": [dict(sx) for sx in services]
        }
    except Exception as e:
        return {"error": str(e)}, 500
    finally:
        conn.close()

@auth_bp.route("/services/add", methods=["POST"])
def add_service():
    name = request.form.get("name", "").strip()
    existing_cat = request.form.get("existing_category")
    new_cat = request.form.get("new_category", "").strip()

    # --- CATEGORY LOGIC ---
    if existing_cat == "__OTHER__" and new_cat:
        conn = get_db()
        # Normalization: Check if what they typed exists in another casing
        match = conn.execute(
            "SELECT category FROM services WHERE LOWER(TRIM(category)) = ? LIMIT 1",
            (new_cat.lower(),)
        ).fetchone()
        category = match['category'] if match else new_cat
    else:
        # Fallback sequence: Selected Dropdown -> "Labor" if empty/invalid
        category = existing_cat if existing_cat and existing_cat != "__OTHER__" else "Labor"

    # --- DUPLICATE SERVICE CHECK ---
    conn = get_db()
    existing_service = conn.execute(
        "SELECT name FROM services WHERE LOWER(TRIM(name)) = ? LIMIT 1",
        (name.lower(),)
    ).fetchone()

    if existing_service:
        flash(f"Service '{name}' already exists!", "warning")
        conn.close()
        return redirect(url_for('auth.manage_users'))

    # --- SAVE ---
    try:
        conn.execute(
            "INSERT INTO services (name, category, is_active) VALUES (?, ?, 1)",
            (name, category)
        )
        conn.commit()
        flash(f"Success: '{name}' added to '{category}'.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
    finally:
        conn.close()

    return redirect(url_for('auth.manage_users'))

# NEW ROUTE: Toggle Service Status
@auth_bp.route("/services/toggle/<int:service_id>", methods=["POST"])
def toggle_service(service_id):
    conn = get_db()
    service = conn.execute("SELECT is_active, name FROM services WHERE id = ?", (service_id,)).fetchone()
    if service:
        new_status = 0 if service['is_active'] == 1 else 1
        conn.execute("UPDATE services SET is_active = ? WHERE id = ?", (new_status, service_id))
        conn.commit()
        flash(f"Service '{service['name']}' status updated.", "info")
    conn.close()
    return redirect(url_for('auth.manage_users'))