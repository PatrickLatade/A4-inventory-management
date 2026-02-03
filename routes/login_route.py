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

    # --- 1. HANDLE FORM SUBMISSION (Creating a New User) ---
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        current_admin_id = session.get("user_id") 
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            conn.execute("""
                INSERT INTO users (username, password_hash, role, created_at, created_by)
                VALUES (?, ?, 'staff', ?, ?)
            """, (
                username,
                generate_password_hash(password),
                now,
                current_admin_id
            ))
            conn.commit()
            conn.close()
            flash(f"Account for {username} created successfully!", "success")
            return redirect(url_for('auth.manage_users'))
        except Exception as e:
            flash(f"Error creating user: {str(e)}", "danger")

    # --- 2. FETCH ALL USERS (For the top table) ---
    users = conn.execute("""
        SELECT
            u.id,
            u.username, 
            u.role, 
            u.created_at,
            u.is_active,
            creator.username AS creator_name
        FROM users u
        LEFT JOIN users creator ON u.created_by = creator.id
        ORDER BY u.created_at DESC
    """).fetchall()

    # --- 3. FETCH TRANSACTION HISTORY (For the bottom table) ---
    # We JOIN with 'items' so we can show the name of the product, not just the ID number
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
    # We pass BOTH 'users' and 'history' to the HTML template
    return render_template("users/users.html", users=users, history=history)

@auth_bp.route("/users/toggle/<int:user_id>", methods=["POST"])
def toggle_user(user_id):
    conn = get_db()
    
    # 1. Fetch the user to check their role
    user = conn.execute("SELECT role, is_active, username FROM users WHERE id = ?", (user_id,)).fetchone()
    
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for('auth.manage_users'))

    # 2. Protection: Don't allow disabling Admins
    if user['role'] == 'admin':
        flash("Cannot disable an Administrator account for security reasons.", "danger")
    else:
        # Toggle: If 1, make 0. If 0, make 1.
        new_status = 0 if user['is_active'] == 1 else 1
        conn.execute("UPDATE users SET is_active = ? WHERE id = ?", (new_status, user_id))
        conn.commit()
        
        status_text = "activated" if new_status == 1 else "disabled"
        flash(f"User {user['username']} has been {status_text}.", "success")

    conn.close()
    return redirect(url_for('auth.manage_users'))
