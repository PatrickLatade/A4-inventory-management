from flask import Blueprint, request, render_template, redirect, url_for, flash
from services.reports_service import (
    get_sales_by_date,
    get_sales_by_range,
    get_sales_report_by_date,
)

reports_bp = Blueprint("reports", __name__)


@reports_bp.route("/reports/daily")
def daily_report():
    report_date = request.args.get("date")

    if not report_date:
        flash("Please select a date.", "warning")
        return redirect(url_for("index"))

    sales = get_sales_by_date(report_date)

    return render_template(
        "reports/daily.html",
        report_date=report_date,
        sales=sales
    )


@reports_bp.route("/reports/range")
def range_report():
    start = request.args.get("start")
    end = request.args.get("end")

    if not start or not end:
        flash("Please select a date range.", "warning")
        return redirect(url_for("index"))

    sales = get_sales_by_range(start, end)

    return render_template(
        "reports/range.html",
        start=start,
        end=end,
        sales=sales
    )


@reports_bp.route("/reports/sales-summary")
def sales_summary_report():
    """
    End-of-Day PDF preview report.
    Triggered from the 'Generate Sales Report' modal in base.html.

    Query param: ?report_date=YYYY-MM-DD

    NOTE for multi-branch: when you add branches, pass branch_id here
    and forward it to get_sales_report_by_date() so each branch only
    sees its own data.
    """
    report_date = request.args.get("report_date")

    if not report_date:
        flash("Please select a date.", "warning")
        return redirect(url_for("index"))

    data = get_sales_report_by_date(report_date)

    # data is a dict with keys: sales, unresolved, total_gross, total_mech_cut, net_revenue
    # If no sales found for the date, service returns [] — normalize to a safe dict.
    if not data:
        data = {
            "sales":          [],
            "unresolved":     [],
            "total_gross":    0.0,
            "total_mech_cut": 0.0,
            "net_revenue":    0.0,
        }

    return render_template(
        "reports/sales_report_pdf.html",
        report_date=report_date,
        data=data,
    )