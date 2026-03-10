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
        category TEXT NOT NULL,
        is_active INTEGER DEFAULT 1
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
        status TEXT CHECK(status IN ('Paid', 'Unresolved', 'Partial')) NOT NULL,
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
        transaction_type TEXT CHECK(transaction_type IN ('IN', 'OUT', 'ORDER')),
        transaction_date DATETIME DEFAULT (DATETIME('now', 'localtime')),
        user_id INTEGER,
        user_name TEXT,
        FOREIGN KEY (item_id) REFERENCES items(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    # 7. SERVICES TABLE (The Master List of Labor Types)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS services (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        category TEXT DEFAULT 'Labor',
        is_active INTEGER DEFAULT 1
    )
    """)

    # 8. SALES SERVICES TABLE (The "Labor" Ledger)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS sales_services (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sale_id INTEGER NOT NULL,
        service_id INTEGER NOT NULL,
        price REAL NOT NULL,
        FOREIGN KEY (sale_id) REFERENCES sales(id),
        FOREIGN KEY (service_id) REFERENCES services(id)
    )
    """)

    # 9. SALES ITEMS TABLE (Item-level sales & discounts)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS sales_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,

        sale_id INTEGER NOT NULL,
        item_id INTEGER NOT NULL,

        quantity INTEGER NOT NULL,

        original_unit_price REAL NOT NULL,
        discount_percent REAL DEFAULT 0,
        discount_amount REAL DEFAULT 0,
        final_unit_price REAL NOT NULL,

        discounted_by INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (sale_id) REFERENCES sales(id),
        FOREIGN KEY (item_id) REFERENCES items(id),
        FOREIGN KEY (discounted_by) REFERENCES users(id)
    )
    """)

    # 10. PURCHASE ORDERS (The Header)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS purchase_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        po_number TEXT UNIQUE,
        vendor_name TEXT,
        status TEXT CHECK(status IN ('PENDING', 'PARTIAL', 'COMPLETED', 'CANCELLED')) DEFAULT 'PENDING',
        total_amount REAL DEFAULT 0,
        created_at DATETIME DEFAULT (DATETIME('now', 'localtime')),
        received_at DATETIME,
        created_by INTEGER,
        notes TEXT,
        FOREIGN KEY (created_by) REFERENCES users(id)
    )
    """)

    # 11. PURCHASE ORDER ITEMS (The Details)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS po_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        po_id INTEGER NOT NULL,
        item_id INTEGER NOT NULL,
        quantity_ordered INTEGER NOT NULL,
        quantity_received INTEGER DEFAULT 0,
        unit_cost REAL,
        FOREIGN KEY (po_id) REFERENCES purchase_orders(id),
        FOREIGN KEY (item_id) REFERENCES items(id)
    )
    """)

    # 12. CUSTOMERS TABLE
    conn.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_no TEXT NOT NULL UNIQUE,
        customer_name TEXT NOT NULL,
        is_active INTEGER DEFAULT 1,
        created_at DATETIME DEFAULT (DATETIME('now', 'localtime'))
    )
    """)

    # 13. VEHICLES TABLE
    conn.execute("""
    CREATE TABLE IF NOT EXISTS vehicles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        vehicle_name TEXT NOT NULL,
        is_active INTEGER DEFAULT 1,
        created_at DATETIME DEFAULT (DATETIME('now', 'localtime')),
        updated_at DATETIME DEFAULT (DATETIME('now', 'localtime')),
        FOREIGN KEY (customer_id) REFERENCES customers(id)
    )
    """)

    # 13. LOYALTY PROGRAMS TABLE
    # program_type: 'SERVICE' = stamps earned per qualifying service visit
    #               'ITEM'    = stamps earned per qualifying item purchase
    #
    # qualifying_id: points to services.id (SERVICE type) or items.id (ITEM type)
    #   - enforced at app level; no composite FK at DB level (SQLite limitation)
    #
    # reward_type options:
    #   FREE_SERVICE     → reward_value = services.id of the free service
    #   FREE_ITEM        → reward_value = items.id of the free item
    #   DISCOUNT_PERCENT → reward_value = percent off (e.g. 10 = 10%)
    #   DISCOUNT_AMOUNT  → reward_value = flat peso off
    #
    # branch_id: NULL means the program applies to ALL branches (global)
    #   When Branch 2 opens, set branch_id = that branch's ID for branch-specific promos.
    #
    # stamps_expire_with_period: enforced at query level (stamp must be within period dates).
    conn.execute("""
    CREATE TABLE IF NOT EXISTS loyalty_programs (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        name                TEXT    NOT NULL,
        program_type        TEXT    NOT NULL CHECK(program_type IN ('SERVICE', 'ITEM')),
        qualifying_id       INTEGER NOT NULL,
        threshold           INTEGER NOT NULL DEFAULT 10,
        reward_type         TEXT    NOT NULL CHECK(reward_type IN (
                                'FREE_SERVICE', 'FREE_ITEM',
                                'DISCOUNT_PERCENT', 'DISCOUNT_AMOUNT'
                            )),
        reward_value        REAL    NOT NULL DEFAULT 0,
        reward_description  TEXT,
        period_start        DATE    NOT NULL,
        period_end          DATE    NOT NULL,
        branch_id           INTEGER DEFAULT NULL,
        is_active           INTEGER DEFAULT 1,
        created_at          DATETIME DEFAULT (DATETIME('now', 'localtime')),
        created_by          INTEGER REFERENCES users(id)
    )
    """)

    # 14. LOYALTY STAMPS TABLE
    # One row = one qualifying transaction earned toward a program.
    # redemption_id = NULL means the stamp is unconsumed / still active.
    # redemption_id = set  means the stamp was consumed in that redemption.
    #
    # Eligibility count = COUNT(*) WHERE redemption_id IS NULL
    #                     AND stamped_at BETWEEN program.period_start AND program.period_end
    #
    # The period date filter is what implements "stamps expire with the period."
    # No backfilling to the next period is possible without a new stamp row.
    conn.execute("""
    CREATE TABLE IF NOT EXISTS loyalty_stamps (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id     INTEGER NOT NULL REFERENCES customers(id),
        program_id      INTEGER NOT NULL REFERENCES loyalty_programs(id),
        sale_id         INTEGER NOT NULL REFERENCES sales(id),
        redemption_id   INTEGER DEFAULT NULL,
        stamped_at      DATETIME DEFAULT (DATETIME('now', 'localtime'))
    )
    """)

    # 15. LOYALTY REDEMPTIONS TABLE
    # One row = one reward granted to a customer.
    # reward_snapshot: frozen JSON of the reward at time of redemption.
    #   Critical for history accuracy — program config can change later.
    # applied_on_sale_id: the sale where the reward was applied (discount/free item).
    conn.execute("""
    CREATE TABLE IF NOT EXISTS loyalty_redemptions (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id         INTEGER NOT NULL REFERENCES customers(id),
        program_id          INTEGER NOT NULL REFERENCES loyalty_programs(id),
        applied_on_sale_id  INTEGER NOT NULL REFERENCES sales(id),
        redeemed_by         INTEGER REFERENCES users(id),
        reward_snapshot     TEXT    NOT NULL,
        stamps_consumed     INTEGER NOT NULL,
        redeemed_at         DATETIME DEFAULT (DATETIME('now', 'localtime'))
    )
    """)

    # 16. Debt Table
    conn.execute("""
    CREATE TABLE IF NOT EXISTS debt_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sale_id INTEGER NOT NULL,
        amount_paid REAL NOT NULL,
        payment_method_id INTEGER,
        reference_no TEXT,
        notes TEXT,
        paid_by INTEGER,
        paid_at DATETIME DEFAULT (DATETIME('now', 'localtime')),
        FOREIGN KEY (sale_id) REFERENCES sales(id),
        FOREIGN KEY (payment_method_id) REFERENCES payment_methods(id),
        FOREIGN KEY (paid_by) REFERENCES users(id)
    )
    """)

    # 17. CASH ENTRIES (Petty Cash Ledger)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS cash_entries (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        branch_id       INTEGER NOT NULL DEFAULT 1,
        entry_type      TEXT CHECK(entry_type IN ('CASH_IN', 'CASH_OUT')) NOT NULL,
        amount          REAL NOT NULL,
        category        TEXT NOT NULL,
        description     TEXT,
        payout_for_date DATE,
        reference_type  TEXT NOT NULL DEFAULT 'MANUAL',
        reference_id    INTEGER,
        user_id         INTEGER,
        created_at      DATETIME DEFAULT (DATETIME('now', 'localtime')),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    # --- CUSTOMER MIGRATIONS ---
    try:
        conn.execute("ALTER TABLE sales ADD COLUMN customer_id INTEGER REFERENCES customers(id)")
    except:
        pass

    try:
        conn.execute("ALTER TABLE sales ADD COLUMN vehicle_id INTEGER REFERENCES vehicles(id)")
    except:
        pass

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
    try:
        conn.execute("ALTER TABLE debt_payments ADD COLUMN service_portion REAL DEFAULT 0")
    except:
        pass

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

    try:
        conn.execute("ALTER TABLE sales ADD COLUMN paid_at DATETIME")
    except:
        pass

    try:
        conn.execute("ALTER TABLE payment_methods ADD COLUMN is_active INTEGER DEFAULT 1")
    except:
        pass

    # 5. Add notes to inventory_transactions (human-readable reason, e.g. for over-receives)
    # change_reason stays as machine-readable code (BONUS_STOCK, PO_ARRIVAL, etc.)
    # notes is the free-text field staff fills in to explain why
    try:
        conn.execute("ALTER TABLE inventory_transactions ADD COLUMN notes TEXT")
    except:
        pass

    # 4. Clean up legacy data: If it has a reference_id but no type, it was a Sale.
    conn.execute("""
        UPDATE inventory_transactions 
        SET reference_type = 'SALE' 
        WHERE reference_id IS NOT NULL AND reference_type IS NULL
    """)

    # --- CASH ENTRIES MIGRATION (for existing databases) ---
    # CREATE TABLE IF NOT EXISTS already handles new databases.
    # These alters guard existing DBs that were created before this table existed.
    # Safe to run every startup ALTER TABLE fails silently on already-existing columns.
    try:
        conn.execute("ALTER TABLE cash_entries ADD COLUMN branch_id INTEGER NOT NULL DEFAULT 1")
    except: pass
    try:
        conn.execute("ALTER TABLE cash_entries ADD COLUMN reference_type TEXT NOT NULL DEFAULT 'MANUAL'")
    except: pass
    try:
        conn.execute("ALTER TABLE cash_entries ADD COLUMN reference_id INTEGER")
    except: pass
    try:
        conn.execute("ALTER TABLE cash_entries ADD COLUMN payout_for_date DATE")
    except:
        pass
    try:
        conn.execute("""
            UPDATE cash_entries
            SET payout_for_date = DATE(created_at)
            WHERE reference_type = 'MECHANIC_PAYOUT'
            AND payout_for_date IS NULL
        """)
    except:
        pass

    # --- IMPROVED SEEDING LOGIC ---

    # 1. Seed Services (Only if empty)
    service_count = conn.execute("SELECT COUNT(*) FROM services").fetchone()[0]
    if service_count == 0:
        initial_services = [
            ('Oil Change', 'Maintenance'),
            ('Tire Mounting', 'Labor'),
            ('Brake Cleaning', 'Maintenance'),
            ('Tune-up', 'Labor'),
            ('Chain Adjustment', 'Labor'),
            ('Engine Overhaul', 'Major Repair')
        ]
        conn.executemany("INSERT INTO services (name, category) VALUES (?, ?)", initial_services)
        print("Services seeded successfully.")

    # 2. Seed Payment Methods (Only if empty)
    pm_count = conn.execute("SELECT COUNT(*) FROM payment_methods").fetchone()[0]
    payment_data = [
        ('Cash', 'Cash'),
        ('GCash', 'Online'),
        ('PayMaya', 'Online'),
        ('Bank Transfer', 'Bank'),
        ('Others', 'Others'),
        ('BPI', 'Bank'),
        ('BDO', 'Bank'),
        ('Utang', 'Debt')
    ]

    if pm_count == 0:
        conn.executemany("INSERT INTO payment_methods (name, category) VALUES (?, ?)", payment_data)
        print("Payment methods seeded successfully.")
    else:
        # If they already exist, we just update the categories to keep them in sync
        # This UPDATE won't burn IDs!
        for name, cat in payment_data:
            conn.execute("UPDATE payment_methods SET category = ? WHERE name = ?", (cat, name))

    conn.commit()
    conn.close()
