from db.database import get_db
from datetime import datetime

def add_transaction(item_id, quantity, transaction_type, user_id=None, user_name=None):
    # Generate the current time in your local system's time
    # This will now capture your 12:35 AM correctly.
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    conn = get_db()
    conn.execute("""
        INSERT INTO inventory_transactions 
        (item_id, quantity, transaction_type, transaction_date, user_id, user_name)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (item_id, quantity, transaction_type, now, user_id, user_name))
    conn.commit()
    conn.close()
