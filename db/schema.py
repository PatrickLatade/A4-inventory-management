from db.database import get_db

def init_db():
    conn = get_db()

    # =========================
    # ITEMS TABLE
    # =========================
    conn.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,

        -- Core identity
        name TEXT NOT NULL UNIQUE,
        description TEXT,
        category TEXT,

        -- Packaging / structure
        pack_size TEXT,

        -- Pricing & cost
        vendor_price REAL,
        cost_per_piece REAL,
        a4s_selling_price REAL,
        markup REAL,

        -- Operations
        reorder_level INTEGER DEFAULT 0,

        -- Meta / future use
        vendor TEXT,
        mechanic TEXT
    )
    """)

    # =========================
    # USERS TABLE
    # =========================
    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT CHECK(role IN ('admin', 'staff')) NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        created_by INTEGER, -- The ID of the admin who created this user
        FOREIGN KEY (created_by) REFERENCES users(id)
    )
    """)

    # =========================
    # INVENTORY TRANSACTIONS
    # =========================
    conn.execute("""
    CREATE TABLE IF NOT EXISTS inventory_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        transaction_type TEXT CHECK(transaction_type IN ('IN', 'OUT')),
        transaction_date DATETIME DEFAULT CURRENT_TIMESTAMP,

        -- audit trail (added later, safe to be nullable for now)
        user_id INTEGER,
        user_name TEXT,

        FOREIGN KEY (item_id) REFERENCES items(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    conn.commit()
    conn.close()
