import sqlite3
from datetime import datetime, timedelta
import random

def seed_database():
    conn = sqlite3.connect("inventory.db")
    cursor = conn.cursor()

    # We are only targeting ID 3
    target_id = 3

    # Check if Item ID 3 exists first
    item = cursor.execute("SELECT name FROM items WHERE id = ?", (target_id,)).fetchone()
    
    if item is None:
        print(f"Error: Item with ID {target_id} not found in the database.")
        conn.close()
        return

    print(f"Generating 30 days of data for '{item[0]}' (ID: {target_id})...")

    today = datetime.now()

    # Loop through the last 30 days
    for i in range(30):
        # Calculate the date for 'i' days ago
        target_date = today - timedelta(days=i)
        date_str = target_date.strftime("%Y-%m-%d %H:%M:%S")

        # Generate "IN" transaction (Restock)
        in_qty = random.randint(10, 20)
        cursor.execute("""
            INSERT INTO inventory_transactions (item_id, quantity, transaction_type, transaction_date)
            VALUES (?, ?, ?, ?)
        """, (target_id, in_qty, 'IN', date_str))

        # Generate "OUT" transaction (Sale)
        out_qty = random.randint(5, 15)
        cursor.execute("""
            INSERT INTO inventory_transactions (item_id, quantity, transaction_type, transaction_date)
            VALUES (?, ?, ?, ?)
        """, (target_id, out_qty, 'OUT', date_str))

    conn.commit()
    conn.close()
    print(f"Done! Successfully added 60 transactions for Item ID {target_id}.")

if __name__ == "__main__":
    seed_database()