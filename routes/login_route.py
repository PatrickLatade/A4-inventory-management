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
            flash("Invalid username or password")
            return redirect("/login")

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

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        current_admin_id = session.get("user_id") # Get current admin ID
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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

    # JOIN with the users table itself to get the creator's name
    users = conn.execute("""
        SELECT 
            u.username, 
            u.role, 
            u.created_at, 
            creator.username AS creator_name
        FROM users u
        LEFT JOIN users creator ON u.created_by = creator.id
        ORDER BY u.created_at DESC
    """).fetchall()

    conn.close()
    return render_template("users/users.html", users=users)
