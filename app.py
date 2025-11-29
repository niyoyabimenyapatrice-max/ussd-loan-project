import os
import sqlite3
from datetime import datetime, timedelta
import hashlib
import io
import csv

from flask import Flask, request, render_template, redirect, url_for, session, flash, send_file, Response

# ----------------------
# APP SETUP
# ----------------------
app = Flask(__name__)
app.secret_key = "super_secret_key"

# ----------------------
# DATABASE
# ----------------------
DB_NAME = os.path.join(os.path.dirname(__file__), "users.db")

# ----------------------
# ADMIN LOGIN
# ----------------------
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD_HASH = hashlib.sha256("admin123".encode()).hexdigest()

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

    conn.commit()
    conn.close()

init_db()

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
# REPAYMENTS
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
# ADMIN ROUTES
# ----------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if username == ADMIN_USERNAME and hashlib.sha256(password.encode()).hexdigest() == ADMIN_PASSWORD_HASH:
            session["admin"] = True
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username or password", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    if "admin" not in session:
        return redirect(url_for("login"))

    search = request.args.get("search", "")
    all_users = search_users(search)
    page = int(request.args.get("page", 1))
    per_page = 5
    total = len(all_users)
    start = (page - 1) * per_page
    end = start + per_page
    rows = all_users[start:end]

    summary = get_dashboard_summary()

    return render_template("dashboard.html",
                           summary=summary,
                           rows=rows,
                           search=search,
                           page=page,
                           total_pages=(total + per_page - 1) // per_page)

# ----------------------
# USER DETAILS
# ----------------------
@app.route("/user/<int:user_id>")
def user_details(user_id):
    if "admin" not in session:
        return redirect(url_for("login"))

    user = get_user_by_id(user_id)
    if not user:
        flash("User not found", "error")
        return redirect(url_for("dashboard"))

    repayments = get_repayments_by_user(user_id)
    today = datetime.now()
    for r in repayments:
        due_date = datetime.strptime(r["due_date"], "%Y-%m-%d %H:%M:%S")
        delta = due_date - today
        r["countdown"] = f"{delta.days} days" if delta.days > 0 else "0 days"
        r["status"] = "Paid" if r.get("paid") == 1 else "Unpaid"

    return render_template("user_details.html", user=user, repayments=repayments)

@app.route("/mark_paid/<int:repayment_id>")
def mark_paid(repayment_id):
    mark_repayment_as_paid(repayment_id)
    flash("Repayment marked as Paid.", "success")
    return redirect(request.referrer or url_for("dashboard"))

# ----------------------
# DELETE USER
# ----------------------
@app.route("/delete_user/<int:user_id>")
def delete_user_route(user_id):
    if "admin" not in session:
        return redirect(url_for("login"))
    delete_user(user_id)
    flash("User deleted successfully", "success")
    return redirect(url_for("dashboard"))

# ----------------------
# EXPORT USERS
# ----------------------
@app.route("/export")
def export_users():
    users = search_users()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Session ID", "Phone", "National ID", "Full Name",
        "Address", "Father", "Mother", "Loan Amount", "Duration", "Date Registered"
    ])
    for u in users:
        writer.writerow([
            u["id"], u["session_id"], u["phone"], u["national_id"], u["full_name"],
            u["address"], u["father_name"], u["mother_name"], u["loan_amount"], u["duration"],
            u.get("date_registered", "")
        ])
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype="text/csv",
        as_attachment=True,
        download_name="users_export.csv"
    )

# ----------------------
# USSD ROUTE
# ----------------------
@app.route("/ussd", methods=["POST"])
def ussd():
    session_id = request.form.get("sessionId")
    phone_number = request.form.get("phoneNumber")
    text = request.form.get("text", "")

    user_response = text.split("*")

    if text == "":
        response_text = "CON Welcome to USSD Loan Service\n1. Register\n2. Check Loan\n3. View Repayments"
    
    elif user_response[0] == "1":  # Registration
        if len(user_response) == 1:
            response_text = "CON Enter your National ID:"
        elif len(user_response) == 2:
            session["national_id"] = user_response[1]
            response_text = "CON Enter your Full Name:"
        elif len(user_response) == 3:
            session["full_name"] = user_response[2]
            response_text = "CON Enter your Address:"
        elif len(user_response) == 4:
            session["address"] = user_response[3]
            response_text = "CON Enter your Father's Name:"
        elif len(user_response) == 5:
            session["father_name"] = user_response[4]
            response_text = "CON Enter your Mother's Name:"
        elif len(user_response) == 6:
            session["mother_name"] = user_response[5]
            response_text = "CON Enter Loan Amount:"
        elif len(user_response) == 7:
            session["loan_amount"] = float(user_response[6])
            response_text = "CON Enter Loan Duration (in days):"
        elif len(user_response) == 8:
            duration = int(user_response[7])
            user_id = add_user(
                session_id,
                phone_number,
                session.get("national_id"),
                session.get("full_name"),
                session.get("address"),
                session.get("father_name"),
                session.get("mother_name"),
                session.get("loan_amount"),
                duration
            )
            generate_repayment_schedule(user_id, session.get("loan_amount"), duration)
            response_text = "END ✅ Registration successful!"

    elif user_response[0] == "2":  # Check Loan
        user = get_user_by_phone(phone_number)
        if not user:
            response_text = "END You are not registered yet."
        else:
            response_text = f"END Hello {user['full_name']}, Loan Amount: RWF {user['loan_amount']}, Duration: {user['duration']} days"

    elif user_response[0] == "3":  # View Repayments
        user = get_user_by_phone(phone_number)
        if not user:
            response_text = "END You are not registered yet."
        else:
            repayments = get_repayments_by_user(user["id"])
            if not repayments:
                response_text = "END No repayment schedule found."
            else:
                lines = []
                for r in repayments[-5:]:
                    status = "Paid" if r["paid"] else "Unpaid"
                    lines.append(f"{r['due_date'].split()[0]}: RWF {r['amount']} - {status}")
                response_text = "END Last repayments:\n" + "\n".join(lines)

    else:
        response_text = "END Invalid choice."

    return Response(response_text, mimetype="text/plain")

# ----------------------
# RUN APP
# ----------------------
if __name__ == "__main__":
    app.run(debug=True)
