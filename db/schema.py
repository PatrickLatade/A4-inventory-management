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

    # 2. ITEMS TABLE
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

    # 3. PAYMENT METHODS TABLE (The New Addition)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS payment_methods (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        category TEXT NOT NULL
    )
    """)

    # 4. SALES TABLE (The New Addition)
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

    # 5. INVENTORY TRANSACTIONS
    # Note: We define the core table first
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

    # --- THE MIGRATION SECTION ---
    # This keeps the schema in sync even if you move to a new machine.
    
    # Add sale_id if it doesn't exist
    try:
        conn.execute("ALTER TABLE inventory_transactions ADD COLUMN sale_id INTEGER REFERENCES sales(id)")
    except:
        pass # Column already exists

    # Add unit_price if it doesn't exist
    try:
        conn.execute("ALTER TABLE inventory_transactions ADD COLUMN unit_price REAL")
    except:
        pass # Column already exists

    # NEW MIGRATION: Add reference_no to sales table for your current DB
    try:
        conn.execute("ALTER TABLE sales ADD COLUMN reference_no TEXT")
    except:
        pass

    # 6. SEED DATA (Pre-fill payment methods)
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
