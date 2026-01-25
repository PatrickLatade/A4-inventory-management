from werkzeug.security import generate_password_hash
from db.database import get_db

ADMINS = [
    ("admin1", "adminpass1"),
    ("admin2", "adminpass2"),
    ("admin3", "adminpass3"),
]

conn = get_db()

for username, password in ADMINS:
    conn.execute("""
        INSERT OR IGNORE INTO users (username, password_hash, role)
        VALUES (?, ?, 'admin')
    """, (
        username,
        generate_password_hash(password)
    ))

conn.commit()
conn.close()

print("✅ Admin accounts seeded")
