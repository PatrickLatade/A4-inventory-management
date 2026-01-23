from db.database import get_db

def get_items_with_stock(snapshot_date=None):
    conn = get_db()

    if snapshot_date:
        query = """
        SELECT 
            items.id,
            items.name,
            COALESCE(SUM(
                CASE 
                    WHEN inventory_transactions.transaction_type = 'IN'
                    THEN inventory_transactions.quantity
                    WHEN inventory_transactions.transaction_type = 'OUT'
                    AND inventory_transactions.transaction_date >= ?
                    THEN -inventory_transactions.quantity
                    ELSE 0
                END
            ), 0) AS current_stock
        FROM items
        LEFT JOIN inventory_transactions
            ON items.id = inventory_transactions.item_id
        GROUP BY items.id;
        """
        items = conn.execute(query, (snapshot_date,)).fetchall()
    else:
        query = """
        SELECT 
            items.id,
            items.name,
            COALESCE(SUM(
                CASE 
                    WHEN inventory_transactions.transaction_type = 'IN'
                    THEN inventory_transactions.quantity
                    ELSE -inventory_transactions.quantity
                END
            ), 0) AS current_stock
        FROM items
        LEFT JOIN inventory_transactions
            ON items.id = inventory_transactions.item_id
        GROUP BY items.id;
        """
        items = conn.execute(query).fetchall()

    conn.close()
    return items
