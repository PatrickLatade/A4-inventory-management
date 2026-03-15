from flask import Blueprint, jsonify, request

from db.database import get_db


vendor_bp = Blueprint("vendor", __name__)


@vendor_bp.route("/api/search/vendors")
def search_vendors():
    query = (request.args.get("q") or "").strip()
    if not query:
        return jsonify({"vendors": []})

    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT id, vendor_name, address, contact_person, contact_no, email
            FROM vendors
            WHERE is_active = 1
              AND (
                    vendor_name ILIKE %s
                 OR contact_person ILIKE %s
                 OR contact_no ILIKE %s
                 OR email ILIKE %s
              )
            ORDER BY vendor_name ASC
            LIMIT 10
            """,
            (f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"),
        ).fetchall()
        return jsonify({"vendors": [dict(row) for row in rows]})
    finally:
        conn.close()


@vendor_bp.route("/api/vendors/<int:vendor_id>")
def get_vendor(vendor_id):
    conn = get_db()
    try:
        row = conn.execute(
            """
            SELECT id, vendor_name, address, contact_person, contact_no, email
            FROM vendors
            WHERE id = %s AND is_active = 1
            """,
            (vendor_id,),
        ).fetchone()

        if not row:
            return jsonify({"status": "error", "message": "Vendor not found."}), 404

        return jsonify({"status": "success", "vendor": dict(row)})
    finally:
        conn.close()


@vendor_bp.route("/api/vendors/add", methods=["POST"])
def add_vendor():
    data = request.get_json(silent=True) or {}
    vendor_name = (data.get("vendor_name") or "").strip()
    address = (data.get("address") or "").strip()
    contact_person = (data.get("contact_person") or "").strip()
    contact_no = (data.get("contact_no") or "").strip()
    email = (data.get("email") or "").strip()

    if not vendor_name or not address or not contact_person or not contact_no or not email:
        return jsonify({
            "status": "error",
            "message": "Vendor name, address, contact person, contact no, and email are required.",
        }), 400

    conn = get_db()
    try:
        existing = conn.execute(
            """
            SELECT id, vendor_name, address, contact_person, contact_no, email
            FROM vendors
            WHERE LOWER(TRIM(vendor_name)) = LOWER(TRIM(%s))
            LIMIT 1
            """,
            (vendor_name,),
        ).fetchone()
        if existing:
            return jsonify({
                "status": "error",
                "message": "A vendor with that name already exists.",
                "vendor": dict(existing),
            }), 409

        row = conn.execute(
            """
            INSERT INTO vendors (vendor_name, address, contact_person, contact_no, email, is_active)
            VALUES (%s, %s, %s, %s, %s, 1)
            RETURNING id, vendor_name, address, contact_person, contact_no, email
            """,
            (vendor_name, address, contact_person, contact_no, email),
        ).fetchone()
        conn.commit()
        return jsonify({"status": "success", "vendor": dict(row)})
    except Exception as exc:
        conn.rollback()
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        conn.close()
