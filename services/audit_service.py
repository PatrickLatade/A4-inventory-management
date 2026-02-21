from db.database import get_db
from utils.formatters import format_date

PER_PAGE = 50

def get_audit_trail(page=1, start_date=None, end_date=None, movement_type=None):
    """
    Paginated audit trail with optional filters.
    
    - movement_type: 'IN', 'OUT', 'ORDER', or None for all
    - start_date / end_date: YYYY-MM-DD strings
    - Returns dict with rows, pagination metadata
    
    NOTE (future branches): add branch_id filter here when ready.
    """
    conn = get_db()
    offset = (page - 1) * PER_PAGE

    # Base WHERE conditions
    conditions = []
    params = []

    if start_date:
        conditions.append("DATE(t.transaction_date) >= ?")
        params.append(start_date)

    if end_date:
        conditions.append("DATE(t.transaction_date) <= ?")
        params.append(end_date)

    if movement_type:
        conditions.append("t.transaction_type = ?")
        params.append(movement_type)

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    # Count total matching rows BEFORE pagination
    # We group by reference_id + date + type + reason (same as display query)
    # so we count groups, not raw transaction rows
    count_query = f"""
        SELECT COUNT(*) FROM (
            SELECT 1
            FROM inventory_transactions t
            JOIN items i ON t.item_id = i.id
            {where_clause}
            GROUP BY t.reference_id, t.transaction_date, t.transaction_type, t.change_reason
        )
    """
    total = conn.execute(count_query, params).fetchone()[0]
    total_pages = max(1, -(-total // PER_PAGE))  # ceiling division

    # Main query — same grouping logic as before, now with LIMIT/OFFSET
    data_query = f"""
        SELECT 
            t.transaction_date,
            t.transaction_type,
            SUM(t.quantity) AS total_qty,
            t.user_name,
            t.change_reason,
            t.reference_type,
            t.reference_id,
            t.notes,
            s.sales_number,
            po.po_number,
            GROUP_CONCAT(i.name, ', ') AS items_summary
        FROM inventory_transactions t
        JOIN items i ON t.item_id = i.id
        LEFT JOIN sales s 
            ON t.reference_id = s.id AND t.reference_type = 'SALE'
        LEFT JOIN purchase_orders po 
            ON t.reference_id = po.id AND t.reference_type = 'PURCHASE_ORDER'
        {where_clause}
        GROUP BY t.reference_id, t.transaction_date, t.transaction_type, t.change_reason
        ORDER BY t.transaction_date DESC
        LIMIT ? OFFSET ?
    """

    rows = conn.execute(data_query, params + [PER_PAGE, offset]).fetchall()
    conn.close()

    formatted = [
        {**dict(r), "transaction_date": format_date(r["transaction_date"], show_time=True)}
        for r in rows
    ]

    return {
        "rows":        formatted,
        "total":       total,
        "page":        page,
        "per_page":    PER_PAGE,
        "total_pages": total_pages,
    }