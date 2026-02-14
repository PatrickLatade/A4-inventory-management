from db.database import get_db


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


def get_sales_report_by_date(report_date):
    """
    Pulls all completed sales for a given date for the End-of-Day PDF report.

    Mechanic cut logic:
      - Sum all services billed under that sale (from sales_services)
      - Multiply by the mechanic's commission_rate (e.g. 0.80 = 80%)
      - That portion goes to the mechanic; the remainder goes to the shop
      - Parts/products are NOT commissionable

    NOTE: When adding multi-branch support later, add a branch_id column to the
    sales table and filter by branch_id here.
    """
    conn = get_db()

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
            m.name            AS mechanic_name,
            m.commission_rate,
            pm.name           AS payment_method
        FROM sales s
        LEFT JOIN mechanics m        ON m.id = s.mechanic_id
        LEFT JOIN payment_methods pm ON pm.id = s.payment_method_id
        WHERE DATE(s.transaction_date) = ?
        ORDER BY s.transaction_date ASC
    """, (report_date,)).fetchall()

    if not sales_rows:
        conn.close()
        return []

    sale_ids = [row["id"] for row in sales_rows]
    placeholders = ",".join("?" * len(sale_ids))

    # --- Items per sale ---
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

    # --- Services per sale ---
    services_rows = conn.execute(f"""
        SELECT
            ss.sale_id,
            sv.name   AS service_name,
            ss.price
        FROM sales_services ss
        JOIN services sv ON sv.id = ss.service_id
        WHERE ss.sale_id IN ({placeholders})
        ORDER BY ss.sale_id, sv.name
    """, sale_ids).fetchall()

    conn.close()

    # --- Group by sale_id ---
    items_by_sale = {}
    for row in items_rows:
        items_by_sale.setdefault(row["sale_id"], []).append(dict(row))

    services_by_sale = {}
    for row in services_rows:
        services_by_sale.setdefault(row["sale_id"], []).append(dict(row))

    MECHANIC_QUOTA = 500.0  # Minimum services total before commission applies

    # --- Build report ---
    paid_sales      = []
    unresolved      = []
    total_gross     = 0.0
    total_mech_cut  = 0.0
    total_shop_topup = 0.0

    for sale in sales_rows:
        sale_id         = sale["id"]
        total_amount    = sale["total_amount"] or 0.0
        commission_rate = sale["commission_rate"] or 0.0

        # Sum all services billed for this sale
        services_total = sum(svc["price"] for svc in services_by_sale.get(sale_id, []))

        # Quota logic:
        # If services rendered are below the quota, the shop tops up the
        # difference as an expense so the mechanic is paid on the quota floor.
        # Commission is then applied to whichever is higher: actual or quota.
        #
        # e.g. quota=500, services=450, rate=0.80
        #   -> shop tops up 50 so effective base = 500
        #   -> mech_cut = 500 * 0.80 = 400
        #   -> shop_topup = 50 (recorded as expense, not deducted from gross)
        #
        # e.g. quota=500, services=600, rate=0.80
        #   -> no top-up needed
        #   -> mech_cut = 600 * 0.80 = 480
        if services_total > 0 and services_total < MECHANIC_QUOTA:
            shop_topup     = round(MECHANIC_QUOTA - services_total, 2)
            effective_base = MECHANIC_QUOTA
        else:
            shop_topup     = 0.0
            effective_base = services_total

        mech_cut = round(effective_base * commission_rate, 2)

        row = {
            "sales_number":    sale["sales_number"] or f"#{sale_id}",
            "customer_name":   sale["customer_name"] or "Walk-in",
            "mechanic_name":   sale["mechanic_name"] or "—",
            "commission_rate": commission_rate,
            "services_total":  round(services_total, 2),
            "effective_base":  round(effective_base, 2),
            "shop_topup":      shop_topup,
            "mechanic_cut":    mech_cut,
            "total_amount":    total_amount,
            "status":          sale["status"],
            "payment_method":  sale["payment_method"] or "—",
            "notes":           sale["notes"] or "",
            "products":        items_by_sale.get(sale_id, []),
            "services":        services_by_sale.get(sale_id, []),
        }

        if sale["status"] == "Paid":
            # Only paid sales count toward the financials
            total_gross      += total_amount
            total_mech_cut   += mech_cut
            total_shop_topup += shop_topup
            paid_sales.append(row)
        else:
            # Unresolved — tracked separately, excluded from totals
            unresolved.append(row)

    return {
        "sales":            paid_sales,
        "unresolved":       unresolved,
        "total_gross":      round(total_gross, 2),
        "total_mech_cut":   round(total_mech_cut, 2),
        "total_shop_topup": round(total_shop_topup, 2),
        "net_revenue":      round(total_gross - total_mech_cut - total_shop_topup, 2),
    }