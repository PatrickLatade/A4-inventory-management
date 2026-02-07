from db.database import get_db

def init_db():
    conn = get_db()

    # 1. USERS TABLE
    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT CHECK(role IN ('admin', 'staff')) NOT NULL,
        is_active INTEGER DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        created_by INTEGER,
        FOREIGN KEY (created_by) REFERENCES users(id)
    )
    """)

    # 2. MECHANICS TABLE (Updated to include all fields)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS mechanics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        commission_rate REAL DEFAULT 0.80,
        phone TEXT,
        is_active INTEGER DEFAULT 1
    )
    """)

    # 3. ITEMS TABLE
    conn.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        description TEXT,
        category TEXT,
        pack_size TEXT,
        vendor_price REAL,
        cost_per_piece REAL,
        a4s_selling_price REAL,
        markup REAL,
        reorder_level INTEGER DEFAULT 0,
        vendor TEXT,
        mechanic TEXT
    )
    """)

    # 4. PAYMENT METHODS TABLE
    conn.execute("""
    CREATE TABLE IF NOT EXISTS payment_methods (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        category TEXT NOT NULL
    )
    """)

    # 5. SALES TABLE
    conn.execute("""
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sales_number TEXT,
        customer_name TEXT,
        total_amount REAL NOT NULL,
        payment_method_id INTEGER,
        reference_no TEXT,
        status TEXT CHECK(status IN ('Paid', 'Unresolved')) NOT NULL,
        notes TEXT,
        user_id INTEGER,
        transaction_date DATETIME DEFAULT (DATETIME('now', 'localtime')),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (payment_method_id) REFERENCES payment_methods(id)
    )
    """)

    # 6. INVENTORY TRANSACTIONS
    conn.execute("""
    CREATE TABLE IF NOT EXISTS inventory_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        transaction_type TEXT CHECK(transaction_type IN ('IN', 'OUT')),
        transaction_date DATETIME DEFAULT (DATETIME('now', 'localtime')),
        user_id INTEGER,
        user_name TEXT,
        FOREIGN KEY (item_id) REFERENCES items(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    # --- THE SURGICAL MIGRATIONS (10% ONLY) ---
    
    # Add mechanic_id to sales
    try:
        conn.execute("ALTER TABLE sales ADD COLUMN mechanic_id INTEGER REFERENCES mechanics(id)")
    except:
        pass 

    # Add service_fee to sales
    try:
        conn.execute("ALTER TABLE sales ADD COLUMN service_fee REAL DEFAULT 0")
    except:
        pass

    # Existing migrations...
    try:
        conn.execute("ALTER TABLE inventory_transactions ADD COLUMN sale_id INTEGER REFERENCES sales(id)")
    except: pass
    try:
        conn.execute("ALTER TABLE inventory_transactions ADD COLUMN unit_price REAL")
    except: pass
    try:
        conn.execute("ALTER TABLE sales ADD COLUMN reference_no TEXT")
    except: pass
    try:
        conn.execute("ALTER TABLE mechanics ADD COLUMN phone TEXT")
    except: pass
    try:
        conn.execute("ALTER TABLE mechanics ADD COLUMN is_active INTEGER DEFAULT 1")
    except: pass

    # --- THE GOLDEN LEDGER MIGRATION ---

    # 1. Rename sale_id to reference_id (The "Universal Key")
    try:
        conn.execute("ALTER TABLE inventory_transactions RENAME COLUMN sale_id TO reference_id")
    except:
        # If the column doesn't exist yet (new DB), add it directly
        try:
            conn.execute("ALTER TABLE inventory_transactions ADD COLUMN reference_id INTEGER")
        except:
            pass

    # 2. Add the "Map" (Reference Type) - This tells us if ID is a Sale, PO, or Swap
    try:
        conn.execute("ALTER TABLE inventory_transactions ADD COLUMN reference_type TEXT")
    except:
        pass

    # 3. Add the "Reason" (Change Reason) - This tells us the 'Why' (Return, Recall, etc.)
    try:
        conn.execute("ALTER TABLE inventory_transactions ADD COLUMN change_reason TEXT")
    except:
        pass

    # 4. Clean up legacy data: If it has a reference_id but no type, it was a Sale.
    conn.execute("""
        UPDATE inventory_transactions 
        SET reference_type = 'SALE' 
        WHERE reference_id IS NOT NULL AND reference_type IS NULL
    """)

    # 7. SEED DATA
    payment_data = [
        ('Cash', 'Cash'),
        ('GCash', 'Online'),
        ('PayMaya', 'Online'),
        ('Bank Transfer', 'Online'),
        ('Utang', 'Debt')
    ]
    conn.executemany("INSERT OR IGNORE INTO payment_methods (name, category) VALUES (?, ?)", payment_data)

    conn.commit()
    conn.close()