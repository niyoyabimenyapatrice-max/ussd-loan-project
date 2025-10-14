import os
import sqlite3
from datetime import datetime, timedelta

DB_NAME = os.path.join(os.path.dirname(__file__), "users.db")

# ----------------------
# DATABASE INITIALIZATION
# ----------------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Users table
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        phone TEXT UNIQUE,
        national_id TEXT,
        full_name TEXT,
        address TEXT,
        father_name TEXT,
        mother_name TEXT,
        loan_amount REAL,
        duration INTEGER,
        date_registered TEXT
    )
    """)

    # Repayments table
    c.execute("""
    CREATE TABLE IF NOT EXISTS repayments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        due_date TEXT,
        paid INTEGER DEFAULT 0
    )
    """)

    # MoMoPay accounts table
    c.execute("""
    CREATE TABLE IF NOT EXISTS momopays (
        phone TEXT PRIMARY KEY,
        balance REAL,
        float_shared REAL,
        merged_batch REAL DEFAULT 0
    )
    """)

    conn.commit()
    conn.close()


# ----------------------
# USER FUNCTIONS
# ----------------------
def add_user(session_id, phone, national_id, full_name, address, father_name, mother_name, loan_amount, duration):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    date_registered = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("""
        INSERT INTO users (session_id, phone, national_id, full_name, address, father_name, mother_name, loan_amount, duration, date_registered)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (session_id, phone, national_id, full_name, address, father_name, mother_name, loan_amount, duration, date_registered))
    user_id = c.lastrowid
    conn.commit()
    conn.close()
    return user_id

def search_users(search=""):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    if search:
        c.execute("SELECT * FROM users WHERE full_name LIKE ? OR phone LIKE ?", (f"%{search}%", f"%{search}%"))
    else:
        c.execute("SELECT * FROM users")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_user_by_id(user_id):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_phone(phone):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE phone=?", (phone,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def delete_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE id=?", (user_id,))
    c.execute("DELETE FROM repayments WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


# ----------------------
# REPAYMENT FUNCTIONS
# ----------------------
def generate_repayment_schedule(user_id, loan_amount, duration):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    installment_amount = round(loan_amount / duration, 2)
    today = datetime.now()
    for i in range(duration):
        due_date = (today + timedelta(days=i+1)).strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT INTO repayments (user_id, amount, due_date) VALUES (?, ?, ?)", (user_id, installment_amount, due_date))
    conn.commit()
    conn.close()

def get_repayments_by_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, user_id, amount, due_date, paid FROM repayments WHERE user_id=?", (user_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def mark_repayment_as_paid(repayment_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE repayments SET paid=1 WHERE id=?", (repayment_id,))
    conn.commit()
    conn.close()


# ----------------------
# DASHBOARD SUMMARY
# ----------------------
def get_dashboard_summary():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]

    c.execute("SELECT SUM(loan_amount) FROM users")
    total_loans = c.fetchone()[0] or 0

    c.execute("""
        SELECT COUNT(*) FROM users u
        WHERE NOT EXISTS (
            SELECT 1 FROM repayments r
            WHERE r.user_id = u.id AND r.paid != 1
        )
    """)
    completed_users = c.fetchone()[0]
    in_progress = total_users - completed_users

    conn.close()
    return {
        "total_users": total_users,
        "total_loans": total_loans,
        "completed_users": completed_users,
        "in_progress": in_progress
    }


# ----------------------
# MoMoPay FUNCTIONS
# ----------------------
def get_momopays():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT phone, balance, float_shared, merged_batch FROM momopays")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_momopay(phone, balance, float_shared):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO momopays (phone, balance, float_shared) VALUES (?, ?, ?)", (phone, balance, float_shared))
    conn.commit()
    conn.close()

def update_momopay_balance(phone, amount):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE momopays SET balance = balance - ? WHERE phone=?", (amount, phone))
    conn.commit()
    conn.close()

def get_merged_momopay_summary():
    return get_momopays()

def delete_momopay(phone):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM momopays WHERE phone=?", (phone,))
    conn.commit()
    conn.close()

def share_float(repayment_id):
    # Placeholder: Implement MoMoPay float sharing logic if needed
    pass


# Initialize DB when module is imported
init_db()
