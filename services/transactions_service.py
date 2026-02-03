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

def add_item_to_db(data):
    """
    Saves a brand new product to the items table.
    """
    conn = get_db()
    
    # We use a cursor so we can get the ID of the item we just created
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO items (
            name, category, description, pack_size, 
            vendor_price, cost_per_piece, a4s_selling_price, 
            markup, reorder_level, vendor, mechanic
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data['name'], data['category'], data['description'], data['pack_size'], 
        data['vendor_price'], data['cost_per_piece'], data['selling_price'], 
        data['markup'], data['reorder_level'], data['vendor'], data['mechanic']
    ))
    
    # This grabs the ID of the new item (we will need this for the "IN" transaction later!)
    new_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    return new_id
