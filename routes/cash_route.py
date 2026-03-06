from flask import Blueprint, render_template, request, jsonify, session
from services.cash_service import (
    get_cash_summary,
    get_cash_entries,
    get_cash_entry_count,
    add_cash_entry,
    delete_cash_entry,
    CASH_IN_CATEGORIES,
    CASH_OUT_CATEGORIES,
)

cash_bp = Blueprint('cash', __name__)
LEDGER_PAGE_SIZE = 20


# ─────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────

def _get_branch_id():
    """
    Central branch resolution.
    Today: always returns 1 (single branch).
    Future: return session.get('branch_id') once multi-branch is live.
    """
    return 1


# ─────────────────────────────────────────────
# PAGE ROUTE
# ─────────────────────────────────────────────

@cash_bp.route("/cash-ledger")
def cash_ledger():
    branch_id  = _get_branch_id()
    entry_type = request.args.get("type") or None
    start_date = request.args.get("start_date") or None
    end_date   = request.args.get("end_date") or None

    if entry_type not in {"CASH_IN", "CASH_OUT", None}:
        entry_type = None

    total_entries = get_cash_entry_count(
        branch_id=branch_id,
        entry_type=entry_type,
        start_date=start_date,
        end_date=end_date,
    )
    total_pages = max(1, (total_entries + LEDGER_PAGE_SIZE - 1) // LEDGER_PAGE_SIZE)

    page   = request.args.get("page", default=1, type=int) or 1
    page   = max(1, min(page, total_pages))
    offset = (page - 1) * LEDGER_PAGE_SIZE

    summary = get_cash_summary(branch_id=branch_id)
    entries = get_cash_entries(
        branch_id=branch_id,
        limit=LEDGER_PAGE_SIZE,
        offset=offset,
        entry_type=entry_type,
        start_date=start_date,
        end_date=end_date,
    )

    start_entry = offset + 1 if total_entries else 0
    end_entry   = offset + len(entries)

    return render_template(
        "cash/cash_ledger.html",
        summary=summary,
        entries=entries,
        page=page,
        total_entries=total_entries,
        total_pages=total_pages,
        start_entry=start_entry,
        end_entry=end_entry,
        selected_type=entry_type,
        selected_start_date=start_date,
        selected_end_date=end_date,
        cash_in_categories=CASH_IN_CATEGORIES,
        cash_out_categories=CASH_OUT_CATEGORIES,
    )


# ─────────────────────────────────────────────
# API ROUTES
# ─────────────────────────────────────────────

@cash_bp.route("/api/cash/summary")
def cash_summary_api():
    branch_id = _get_branch_id()
    summary   = get_cash_summary(branch_id=branch_id)
    return jsonify(summary)


@cash_bp.route("/api/cash/entries")
def cash_entries_api():
    branch_id  = _get_branch_id()
    limit      = request.args.get("limit", type=int)
    offset     = request.args.get("offset", type=int)
    entry_type = request.args.get("type") or None
    start_date = request.args.get("start_date") or None
    end_date   = request.args.get("end_date") or None

    entries = get_cash_entries(
        branch_id=branch_id,
        limit=limit,
        offset=offset,
        entry_type=entry_type,
        start_date=start_date,
        end_date=end_date,
    )
    return jsonify({"entries": entries})


@cash_bp.route("/api/cash/add", methods=["POST"])
def cash_add_api():
    data = request.get_json()

    try:
        add_cash_entry(
            entry_type=data.get("entry_type"),
            amount=data.get("amount"),
            category=data.get("category"),
            description=data.get("description", ""),
            user_id=session.get("user_id"),
            branch_id=_get_branch_id(),
        )
        return jsonify({"status": "success"}), 200

    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": "Server error: " + str(e)}), 500


@cash_bp.route("/api/cash/delete/<int:entry_id>", methods=["DELETE"])
def cash_delete_api(entry_id):
    if session.get("role") != "admin":
        return jsonify({"status": "error", "message": "Admin access required."}), 403

    try:
        delete_cash_entry(entry_id=entry_id, branch_id=_get_branch_id())
        return jsonify({"status": "success"}), 200

    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": "Server error: " + str(e)}), 500