import sqlite3

DB_NAME = "users.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # USERS TABLE
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            phone TEXT,
            national_id TEXT,
            full_name TEXT,
            address TEXT,
            father_name TEXT,
            mother_name TEXT,
            loan_amount REAL,
            duration INTEGER,
            date_registered TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    # REPAYMENTS TABLE
    c.execute("""
        CREATE TABLE IF NOT EXISTS repayments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            due_date TEXT,
            paid INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # MOMOPAYS TABLE
    c.execute("""
        CREATE TABLE IF NOT EXISTS momopays (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT UNIQUE,
            balance REAL DEFAULT 0,
            float_shared REAL DEFAULT 0,
            merged_batch REAL DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()
    print("✅ Database initialized successfully!")

if __name__ == "__main__":
    init_db()
