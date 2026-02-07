from db.database import get_db
from datetime import datetime

def add_transaction(item_id, quantity, transaction_type, user_id=None, user_name=None, 
                    reference_id=None, reference_type=None, change_reason=None, 
                    unit_price=None, transaction_date=None, external_conn=None):
    """
    The Universal Ledger Entry. 
    Can handle Sales, Returns, Purchase Orders, Swaps, etc.
    """
    # 1. Use existing connection or get a new one
    conn = external_conn if external_conn else get_db()
    
    # 2. UNIFORM TIME LOGIC
    if transaction_date:
        final_time = transaction_date.replace('T', ' ')
        if len(final_time) == 16:
            final_time += ":00"
    else:
        final_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 3. EXECUTE - Updated to use the new "Golden" columns
    conn.execute("""
        INSERT INTO inventory_transactions 
        (item_id, quantity, transaction_type, transaction_date, user_id, user_name, 
        reference_id, reference_type, change_reason, unit_price)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        item_id, quantity, transaction_type, final_time, user_id, user_name, 
        reference_id, reference_type, change_reason, unit_price
    ))
    
    # 4. Only commit/close if we opened the connection ourselves
    if not external_conn:
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
