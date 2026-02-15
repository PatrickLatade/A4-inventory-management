from db.database import get_db
from utils.formatters import format_date


def get_sales_by_date(report_date):
    conn = get_db()

    rows = conn.execute("""
        SELECT 
            items.name,
            inventory_transactions.quantity,
            inventory_transactions.transaction_date,
            inventory_transactions.user_name
        FROM inventory_transactions
        JOIN items ON items.id = inventory_transactions.item_id
        WHERE transaction_type = 'OUT'
        AND DATE(transaction_date) = ?
    """, (report_date,)).fetchall()

    conn.close()
    return rows


def get_sales_by_range(start_date, end_date):
    conn = get_db()

    rows = conn.execute("""
        SELECT 
            items.name,
            inventory_transactions.quantity,
            inventory_transactions.transaction_date,
            inventory_transactions.user_name
        FROM inventory_transactions
        JOIN items ON items.id = inventory_transactions.item_id
        WHERE transaction_type = 'OUT'
          AND DATE(transaction_date) BETWEEN ? AND ?
    """, (start_date, end_date)).fetchall()

    conn.close()
    return rows


def get_all_unresolved_sales(conn):
    """
    Pulls ALL sales with status='Unresolved' across every date.
    Called separately from the daily report so the Payables section
    is not limited to the chosen report_date.
    Receives an open connection so the caller can batch queries.
    """
    unresolved_rows = conn.execute("""
        SELECT
            s.id,
            s.sales_number,
            s.customer_name,
            s.total_amount,
            s.status,
            s.notes,
            s.transaction_date,
            m.name  AS mechanic_name,
            pm.name AS payment_method
        FROM sales s
        LEFT JOIN mechanics m        ON m.id = s.mechanic_id
        LEFT JOIN payment_methods pm ON pm.id = s.payment_method_id
        WHERE s.status = 'Unresolved'
        ORDER BY s.transaction_date ASC
    """).fetchall()

    if not unresolved_rows:
        return []

    sale_ids     = [row["id"] for row in unresolved_rows]
    placeholders = ",".join("?" * len(sale_ids))

    items_rows = conn.execute(f"""
        SELECT
            si.sale_id,
            i.name                  AS item_name,
            si.quantity,
            si.original_unit_price,
            si.discount_percent,
            si.discount_amount,
            si.final_unit_price,
            (si.quantity * si.final_unit_price) AS line_total
        FROM sales_items si
        JOIN items i ON i.id = si.item_id
        WHERE si.sale_id IN ({placeholders})
        ORDER BY si.sale_id, i.name
    """, sale_ids).fetchall()

    services_rows = conn.execute(f"""
        SELECT
            ss.sale_id,
            sv.name AS service_name,
            ss.price
        FROM sales_services ss
        JOIN services sv ON sv.id = ss.service_id
        WHERE ss.sale_id IN ({placeholders})
        ORDER BY ss.sale_id, sv.name
    """, sale_ids).fetchall()

    items_by_sale = {}
    for row in items_rows:
        items_by_sale.setdefault(row["sale_id"], []).append(dict(row))

    services_by_sale = {}
    for row in services_rows:
        services_by_sale.setdefault(row["sale_id"], []).append(dict(row))

    result = []
    for sale in unresolved_rows:
        sale_id = sale["id"]
        result.append({
            "sales_number":       sale["sales_number"] or f"#{sale_id}",
            "customer_name":      sale["customer_name"] or "Walk-in",
            "mechanic_name":      sale["mechanic_name"] or "—",
            "total_amount":       sale["total_amount"] or 0.0,
            "status":             sale["status"],
            "payment_method":     sale["payment_method"] or "—",
            "notes":              sale["notes"] or "",
            "transaction_date":   format_date(sale["transaction_date"]),
            "products":           items_by_sale.get(sale_id, []),
            "services":           services_by_sale.get(sale_id, []),
        })

    return result


def get_sales_report_by_date(report_date):
    """
    Pulls all completed sales for a given date for the End-of-Day PDF report.

    Mechanic cut logic (applied per mechanic across the WHOLE day, not per transaction):
    - Sum all services for a mechanic across all their paid sales that day
    - If total < MECHANIC_QUOTA, shop tops up the difference as an expense
    - Commission rate is then applied to max(total, quota)
    - This prevents the quota from triggering unfairly on a mechanic who had one small transaction but a large day overall

    NOTE: When adding multi-branch support later, add a branch_id column to the
    sales table and filter by branch_id here.
    """
    conn = get_db()

    MECHANIC_QUOTA = 500.0

    # --- Main sales rows for the day ---
    sales_rows = conn.execute("""
        SELECT
            s.id,
            s.sales_number,
            s.customer_name,
            s.total_amount,
            s.status,
            s.notes,
            s.transaction_date,
            m.id              AS mechanic_id,
            m.name            AS mechanic_name,
            m.commission_rate,
            pm.name           AS payment_method
        FROM sales s
        LEFT JOIN mechanics m        ON m.id = s.mechanic_id
        LEFT JOIN payment_methods pm ON pm.id = s.payment_method_id
        WHERE DATE(s.transaction_date) = ?
        ORDER BY s.transaction_date ASC
    """, (report_date,)).fetchall()

    # --- All unresolved across ALL dates (not filtered by report_date) ---
    all_unresolved = get_all_unresolved_sales(conn)

    if not sales_rows and not all_unresolved:
        conn.close()
        return []

    # Build placeholders only if there are paid sales to query
    paid_sale_ids = [row["id"] for row in sales_rows if row["status"] == "Paid"]

    items_by_sale    = {}
    services_by_sale = {}

    if paid_sale_ids:
        placeholders = ",".join("?" * len(paid_sale_ids))

        items_rows = conn.execute(f"""
            SELECT
                si.sale_id,
                i.name                  AS item_name,
                si.quantity,
                si.original_unit_price,
                si.discount_percent,
                si.discount_amount,
                si.final_unit_price,
                (si.quantity * si.final_unit_price) AS line_total
            FROM sales_items si
            JOIN items i ON i.id = si.item_id
            WHERE si.sale_id IN ({placeholders})
            ORDER BY si.sale_id, i.name
        """, paid_sale_ids).fetchall()

        services_rows = conn.execute(f"""
            SELECT
                ss.sale_id,
                sv.name   AS service_name,
                ss.price
            FROM sales_services ss
            JOIN services sv ON sv.id = ss.service_id
            WHERE ss.sale_id IN ({placeholders})
            ORDER BY ss.sale_id, sv.name
        """, paid_sale_ids).fetchall()

        for row in items_rows:
            items_by_sale.setdefault(row["sale_id"], []).append(dict(row))

        for row in services_rows:
            services_by_sale.setdefault(row["sale_id"], []).append(dict(row))

    conn.close()

    # --- Build paid transaction rows ---
    paid_sales  = []
    total_gross = 0.0
    mechanic_map = {}

    for sale in sales_rows:
        if sale["status"] != "Paid":
            continue

        sale_id         = sale["id"]
        total_amount    = sale["total_amount"] or 0.0
        mechanic_id     = sale["mechanic_id"]
        mechanic_name   = sale["mechanic_name"] or "—"
        commission_rate = sale["commission_rate"] or 0.0

        services_total = sum(
            svc["price"] for svc in services_by_sale.get(sale_id, [])
        )

        paid_sales.append({
            "sales_number":   sale["sales_number"] or f"#{sale_id}",
            "customer_name":  sale["customer_name"] or "Walk-in",
            "mechanic_name":  mechanic_name,
            "services_total": round(services_total, 2),
            "total_amount":   total_amount,
            "status":         sale["status"],
            "payment_method": sale["payment_method"] or "—",
            "notes":          sale["notes"] or "",
            "products":       items_by_sale.get(sale_id, []),
            "services":       services_by_sale.get(sale_id, []),
        })

        total_gross += total_amount

        if mechanic_id:
            if mechanic_id not in mechanic_map:
                mechanic_map[mechanic_id] = {
                    "mechanic_name":   mechanic_name,
                    "commission_rate": commission_rate,
                    "services_total":  0.0,
                }
            mechanic_map[mechanic_id]["services_total"] += services_total

    # --- Per-mechanic quota + commission ---
    mechanic_summary = []
    total_mech_cut   = 0.0
    total_shop_topup = 0.0

    for mech_id, mech in mechanic_map.items():
        services_total  = round(mech["services_total"], 2)
        commission_rate = mech["commission_rate"]

        if services_total > 0 and services_total < MECHANIC_QUOTA:
            shop_topup     = round(MECHANIC_QUOTA - services_total, 2)
            effective_base = MECHANIC_QUOTA
        else:
            shop_topup     = 0.0
            effective_base = services_total

        mech_cut = round(effective_base * commission_rate, 2)

        total_mech_cut   += mech_cut
        total_shop_topup += shop_topup

        mechanic_summary.append({
            "mechanic_name":   mech["mechanic_name"],
            "commission_rate": commission_rate,
            "services_total":  services_total,
            "effective_base":  round(effective_base, 2),
            "shop_topup":      shop_topup,
            "mechanic_cut":    mech_cut,
        })

    mechanic_summary.sort(key=lambda x: x["mechanic_name"])

    # --- Items summary ---
    items_summary = {}
    for sale in paid_sales:
        for item in sale["products"]:
            key = item["item_name"]
            if key not in items_summary:
                items_summary[key] = {"item_name": item["item_name"], "quantity": 0, "total": 0.0}
            items_summary[key]["quantity"] += item["quantity"]
            items_summary[key]["total"]    += item["line_total"]

    items_summary_list = sorted(items_summary.values(), key=lambda x: x["item_name"])

    total_mech_cut   = round(total_mech_cut, 2)
    total_shop_topup = round(total_shop_topup, 2)

    return {
        "sales":            paid_sales,
        "unresolved":       all_unresolved,   # ALL unresolved, not just today's
        "mechanic_summary": mechanic_summary,
        "items_summary":    items_summary_list,
        "total_gross":      round(total_gross, 2),
        "total_mech_cut":   total_mech_cut,
        "total_shop_topup": total_shop_topup,
        "net_revenue":      round(total_gross - total_mech_cut - total_shop_topup, 2),
    }