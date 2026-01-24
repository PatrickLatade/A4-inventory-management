from db.database import get_db

def init_db():
    conn = get_db()

    # ITEMS TABLE
    # Stores product identity, pricing, and vendor-related info
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
        vendor_price REAL,        -- price from vendor (per pack or unit, depending on sheet)
        cost_per_piece REAL,      -- normalized cost per piece
        a4s_selling_price REAL,   -- shop selling price
        markup REAL,              -- markup value or percentage (as provided)

        -- Operations
        reorder_level INTEGER DEFAULT 0,

        -- Meta / future use
        vendor TEXT,
        mechanic TEXT
    )
    """)

    # INVENTORY TRANSACTIONS TABLE
    # Stores all stock movement (IN / OUT)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS inventory_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        transaction_type TEXT CHECK(transaction_type IN ('IN', 'OUT')),
        transaction_date DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (item_id) REFERENCES items(id)
    )
    """)

    conn.commit()
    conn.close()
