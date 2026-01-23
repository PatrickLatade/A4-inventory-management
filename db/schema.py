from db.database import get_db

def init_db():
    conn = get_db()

    conn.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        description TEXT,
        pack_size TEXT,
        cost_per_piece REAL,
        selling_price REAL,
        category TEXT,
        reorder_level INTEGER DEFAULT 0,
        vendor TEXT,
        mechanic TEXT
    )
    """)

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
