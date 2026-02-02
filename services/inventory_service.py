from db.database import get_db

def get_items_with_stock(snapshot_date=None):
    conn = get_db()

    if snapshot_date:
        query = """
        SELECT 
            items.id,
            items.name,
            items.a4s_selling_price,
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
            items.a4s_selling_price,
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

from db.database import get_db

def search_items_with_stock(search_query, snapshot_date="2026-01-18"):
    conn = get_db()
    
    # 1. Split query into words for "forgiving" search
    # Example: "shoe brake" -> ["shoe", "brake"]
    words = search_query.split()
    
    if not words:
        # If somehow an empty query reaches here, return the latest items
        rows = conn.execute("SELECT * FROM items ORDER BY id DESC LIMIT 75").fetchall()
    else:
        # Build dynamic WHERE clause: (name LIKE ? OR description LIKE ?) AND ...
        query_parts = []
        params = []
        for word in words:
            query_parts.append("(name LIKE ? OR description LIKE ?)")
            pattern = f"%{word}%"
            params.extend([pattern, pattern])
        
        where_clause = " AND ".join(query_parts)
        
        sql = f"""
            SELECT * FROM items 
            WHERE {where_clause}
            ORDER BY name ASC
            LIMIT 100
        """
        rows = conn.execute(sql, params).fetchall()
    
    # 2. Get stock levels
    # Note: We reuse your existing stock calculation function
    from services.inventory_service import get_items_with_stock
    all_stock = get_items_with_stock(snapshot_date)
    stock_map = {s["id"]: s["current_stock"] for s in all_stock}
    
    conn.close()

    # 3. Merge data into a list of dictionaries
    results = []
    for row in rows:
        d = dict(row)
        d["current_stock"] = stock_map.get(row["id"], 0)
        results.append(d)
        
    return results
