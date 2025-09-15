import sqlite3

DB_FILE = "users.db"

def migrate_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # --- 1. Check if 'status' column exists in repayments ---
    cursor.execute("PRAGMA table_info(repayments)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'status' not in columns:
        print("Migrating 'repayments' table: adding 'status' column based on 'paid'...")
        # Add new 'status' column
        cursor.execute("ALTER TABLE repayments ADD COLUMN status TEXT DEFAULT 'Unpaid'")
        # Update status based on old 'paid' column (0 = Unpaid, 1 = Paid)
        cursor.execute("UPDATE repayments SET status = CASE WHEN paid=1 THEN 'Paid' ELSE 'Unpaid' END")
        print("✅ Repayments table migrated successfully.")
    else:
        print("✅ 'status' column already exists in repayments table.")

    # --- 2. Create momopay table if not exists ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS momopay (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT UNIQUE,
        balance REAL DEFAULT 0,
        merged_batch REAL DEFAULT 0,
        float_shared REAL DEFAULT 0
    )
    """)
    print("✅ momopay table verified/created.")

    # --- 3. Ensure 'date_registered' exists in users ---
    cursor.execute("PRAGMA table_info(users)")
    user_columns = [col[1] for col in cursor.fetchall()]
    if 'date_registered' not in user_columns:
        print("Adding 'date_registered' column to users table...")
        cursor.execute("ALTER TABLE users ADD COLUMN date_registered TEXT")
        print("✅ 'date_registered' added to users table.")
    else:
        print("✅ 'date_registered' column already exists in users table.")

    conn.commit()
    conn.close()
    print("✅ Database migration completed successfully.")

if __name__ == "__main__":
    migrate_db()
