from db.database import get_db

def add_transaction(item_id, quantity, transaction_type):
    conn = get_db()
    conn.execute("""
        INSERT INTO inventory_transactions (item_id, quantity, transaction_type)
        VALUES (?, ?, ?)
    """, (item_id, quantity, transaction_type))
    conn.commit()
    conn.close()
