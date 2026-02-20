from flask import Blueprint, render_template, request, jsonify, session, flash
from services.debt_service import get_all_debts, get_debt_detail, record_payment
from db.database import get_db

debt_bp = Blueprint('debt', __name__)

@debt_bp.route("/utang")
def utang_list():
    debts = get_all_debts()

    conn = get_db()
    # Only ACTIVE, and exclude Debt-category methods (you don't "pay" debt using Utang)
    # NOTE (future branches): add branch_id filter here later.
    payment_methods = conn.execute("""
        SELECT id, name, category
        FROM payment_methods
        WHERE is_active = 1
        AND category != 'Debt'
        ORDER BY category ASC, name ASC
    """).fetchall()
    conn.close()

    return render_template("transactions/utang.html", debts=debts, payment_methods=payment_methods)

@debt_bp.route("/api/debt/<int:sale_id>")
def debt_detail_api(sale_id):
    data = get_debt_detail(sale_id)
    if not data:
        return jsonify({"error": "Sale not found"}), 404
    return jsonify(data)

@debt_bp.route("/api/debt/<int:sale_id>/pay", methods=["POST"])
def pay_debt(sale_id):
    data = request.get_json()

    try:
        result = record_payment(
            sale_id=sale_id,
            amount_paid=data.get('amount_paid'),
            payment_method_id=data.get('payment_method_id'),
            reference_no=data.get('reference_no', ''),
            notes=data.get('notes', ''),
            paid_by=session.get('user_id'),
        )

        if result['new_status'] == 'Paid':
            flash("Debt fully settled!", "success")
        else:
            flash(
                f"Payment of ₱{result['amount_paid']:,.2f} recorded. Balance: ₱{result['new_remaining']:,.2f}",
                "success"
            )

        return jsonify({"status": "success", **result}), 200

    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": "Server error: " + str(e)}), 500

@debt_bp.route("/api/debt/audit")
def debt_audit_api():
    from utils.formatters import format_date
    conn = get_db()
    rows = conn.execute("""
        SELECT
            dp.id,
            dp.paid_at,
            dp.amount_paid,
            dp.reference_no,
            s.sales_number,
            s.id        AS sale_id,
            s.total_amount,
            s.customer_name,
            u.username  AS paid_by,
            pm.name     AS payment_method,
            SUM(dp.amount_paid) OVER (
                PARTITION BY dp.sale_id
                ORDER BY dp.paid_at
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS running_total
        FROM debt_payments dp
        JOIN sales s                  ON s.id = dp.sale_id
        LEFT JOIN users u             ON u.id = dp.paid_by
        LEFT JOIN payment_methods pm  ON pm.id = dp.payment_method_id
        ORDER BY dp.paid_at DESC
        LIMIT 100
    """).fetchall()
    conn.close()

    formatted = []
    for r in rows:
        d = dict(r)
        d['paid_at'] = format_date(d['paid_at'], show_time=True)
        d['fully_paid'] = round(d['running_total'], 2) >= round(d['total_amount'], 2)
        formatted.append(d)

    return jsonify({"payments": formatted})
