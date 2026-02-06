from flask import Blueprint, render_template, request, redirect, session, flash, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from db.database import get_db
from datetime import datetime

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
            t.quantity, 
            t.user_name, 
            i.name as item_name
        FROM inventory_transactions t
        JOIN items i ON t.item_id = i.id
        ORDER BY t.transaction_date DESC
        LIMIT 50
    """).fetchall()

    conn.close()

    # --- 4. SERVE THE PAGE ---
    # Add sales_history=sales_history to the list of variables sent to the template
    return render_template("users/users.html", users=users, history=history, sales_history=sales_history, mechanics=mechanics)

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
