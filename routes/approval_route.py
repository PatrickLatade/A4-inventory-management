from flask import Blueprint, jsonify, request, session

from auth.utils import admin_required, login_required
from services.approval_service import (
    approve_request,
    cancel_request,
    get_approval_request,
    get_approval_request_with_history,
    list_approval_requests,
    resubmit_request,
    request_revisions,
)
from services.transactions_service import (
    approve_purchase_order,
    cancel_purchase_order,
    request_po_revisions,
)

approval_bp = Blueprint("approval", __name__)


@approval_bp.route("/api/admin/approvals", methods=["GET"])
@admin_required
def admin_list_approvals():
    try:
        status = request.args.get("status") or None
        approval_type = request.args.get("approval_type") or None
        rows = list_approval_requests(status=status, approval_type=approval_type)
        return jsonify({"requests": rows})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@approval_bp.route("/api/admin/approvals/<int:approval_request_id>", methods=["GET"])
@admin_required
def admin_get_approval_request(approval_request_id):
    try:
        data = get_approval_request_with_history(approval_request_id)
        if not data:
            return jsonify({"error": "Approval request not found."}), 404
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@approval_bp.route("/api/admin/approvals/<int:approval_request_id>/approve", methods=["POST"])
@admin_required
def admin_approve_request(approval_request_id):
    payload = request.get_json(silent=True) or {}
    try:
        request_row = get_approval_request(approval_request_id)
        if not request_row:
            return jsonify({"error": "Approval request not found."}), 404

        if request_row["approval_type"] == "PURCHASE_ORDER" and request_row["entity_type"] == "purchase_order":
            details = approve_purchase_order(
                po_id=request_row["entity_id"],
                admin_user_id=session.get("user_id"),
                notes=(payload.get("notes") or "").strip() or None,
            )
            return jsonify({"status": "success", "details": details})

        row = approve_request(
            approval_request_id=approval_request_id,
            admin_user_id=session.get("user_id"),
            notes=(payload.get("notes") or "").strip() or None,
        )
        return jsonify({"status": "success", "request": row})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@approval_bp.route("/api/admin/approvals/<int:approval_request_id>/revisions", methods=["POST"])
@admin_required
def admin_request_revisions(approval_request_id):
    payload = request.get_json(silent=True) or {}
    try:
        request_row = get_approval_request(approval_request_id)
        if not request_row:
            return jsonify({"error": "Approval request not found."}), 404

        if request_row["approval_type"] == "PURCHASE_ORDER" and request_row["entity_type"] == "purchase_order":
            details = request_po_revisions(
                po_id=request_row["entity_id"],
                admin_user_id=session.get("user_id"),
                notes=(payload.get("notes") or "").strip(),
                revision_items=payload.get("revision_items") or [],
            )
            return jsonify({"status": "success", "details": details})

        row = request_revisions(
            approval_request_id=approval_request_id,
            admin_user_id=session.get("user_id"),
            notes=(payload.get("notes") or "").strip(),
            revision_items=payload.get("revision_items") or [],
        )
        return jsonify({"status": "success", "request": row})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@approval_bp.route("/api/admin/approvals/<int:approval_request_id>/cancel", methods=["POST"])
@admin_required
def admin_cancel_request(approval_request_id):
    payload = request.get_json(silent=True) or {}
    try:
        request_row = get_approval_request(approval_request_id)
        if not request_row:
            return jsonify({"error": "Approval request not found."}), 404

        if request_row["approval_type"] == "PURCHASE_ORDER" and request_row["entity_type"] == "purchase_order":
            details = cancel_purchase_order(
                po_id=request_row["entity_id"],
                user_id=session.get("user_id"),
                user_role=session.get("role"),
                notes=(payload.get("notes") or "").strip(),
            )
            return jsonify({"status": "success", "details": details})

        row = cancel_request(
            approval_request_id=approval_request_id,
            actor_id=session.get("user_id"),
            actor_role=session.get("role"),
            notes=(payload.get("notes") or "").strip(),
        )
        return jsonify({"status": "success", "request": row})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@approval_bp.route("/api/approvals/<int:approval_request_id>/cancel", methods=["POST"])
@login_required
def requester_cancel_request(approval_request_id):
    payload = request.get_json(silent=True) or {}
    try:
        request_row = get_approval_request(approval_request_id)
        if not request_row:
            return jsonify({"error": "Approval request not found."}), 404

        if request_row["approval_type"] == "PURCHASE_ORDER" and request_row["entity_type"] == "purchase_order":
            details = cancel_purchase_order(
                po_id=request_row["entity_id"],
                user_id=session.get("user_id"),
                user_role=session.get("role"),
                notes=(payload.get("notes") or "").strip() or None,
            )
            return jsonify({"status": "success", "details": details})

        row = cancel_request(
            approval_request_id=approval_request_id,
            actor_id=session.get("user_id"),
            actor_role=session.get("role"),
            notes=(payload.get("notes") or "").strip() or None,
        )
        return jsonify({"status": "success", "request": row})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@approval_bp.route("/api/approvals/<int:approval_request_id>", methods=["GET"])
@login_required
def requester_get_approval_request(approval_request_id):
    try:
        data = get_approval_request_with_history(approval_request_id)
        if not data:
            return jsonify({"error": "Approval request not found."}), 404

        requester_id = session.get("user_id")
        if int(data["requested_by"]) != int(requester_id) and session.get("role") != "admin":
            return jsonify({"error": "You do not have access to this approval request."}), 403

        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@approval_bp.route("/api/approvals/<int:approval_request_id>/resubmit", methods=["POST"])
@login_required
def requester_resubmit_request(approval_request_id):
    payload = request.get_json(silent=True) or {}
    try:
        request_row = get_approval_request(approval_request_id)
        if not request_row:
            return jsonify({"error": "Approval request not found."}), 404

        if request_row["approval_type"] == "PURCHASE_ORDER" and request_row["entity_type"] == "purchase_order":
            return jsonify({"error": "Purchase orders must be edited through the PO update flow before resubmission."}), 400

        row = resubmit_request(
            approval_request_id=approval_request_id,
            requester_id=session.get("user_id"),
            metadata=payload.get("metadata"),
            notes=(payload.get("notes") or "").strip() or None,
        )
        return jsonify({"status": "success", "request": row})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
