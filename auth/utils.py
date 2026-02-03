from functools import wraps
from flask import session, redirect, url_for, abort, flash
from db.database import get_db

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        # 1. Check if logged in
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        
        # 2. Check if still active in DB
        conn = get_db()
        user = conn.execute("SELECT is_active FROM users WHERE id = ?", (session["user_id"],)).fetchone()
        conn.close()

        if not user or user["is_active"] == 0:
            session.clear() # Wipe the session so they stay logged out
            flash("Your account has been deactivated.", "danger")
            return redirect(url_for("auth.login"))
            
        return f(*args, **kwargs)
    return wrapper

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        # 1. Check if logged in
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        
        # 2. Check if still active AND is admin
        conn = get_db()
        user = conn.execute("SELECT is_active, role FROM users WHERE id = ?", (session["user_id"],)).fetchone()
        conn.close()

        if not user or user["is_active"] == 0:
            session.clear()
            flash("Your account has been deactivated.", "danger")
            return redirect(url_for("auth.login"))

        if user["role"] != "admin":
            abort(403)

        return f(*args, **kwargs)
    return wrapper