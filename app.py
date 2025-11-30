# app.py (UPDATED)
import os
import sqlite3
from datetime import datetime, timedelta
import hashlib
from flask import Flask, request, render_template, redirect, url_for, session, flash, Response, send_file
import io
import csv

# ----------------------
# APP SETUP
# ----------------------
app = Flask(__name__)
app.secret_key = "super_secret_key"

# ----------------------
# DATABASE
# ----------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "users.db")

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
    # Users
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
    # Repayments
    c.execute("""
    CREATE TABLE IF NOT EXISTS repayments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        due_date TEXT,
        paid INTEGER DEFAULT 0
    )
    """)
    # USSD sessions (persist multi-step USSD inputs)
    c.execute("""
    CREATE TABLE IF NOT EXISTS ussd_sessions (
        session_id TEXT PRIMARY KEY,
        phone TEXT,
        step INTEGER DEFAULT 0,
        national_id TEXT,
        full_name TEXT,
        address TEXT,
        father_name TEXT,
        mother_name TEXT,
        loan_amount REAL
    )
    """)
    conn.commit()
    conn.close()

init_db()  # Ensure DB exists

# ----------------------
# DB HELPERS
# ----------------------
def _get_conn():
    return sqlite3.connect(DB_NAME)

# ----------------------
# USER FUNCTIONS
# ----------------------
def add_user(session_id, phone, national_id, full_name, address, father_name, mother_name, loan_amount, duration):
    conn = _get_conn()
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

def update_user(user_id, **fields):
    conn = _get_conn()
    c = conn.cursor()
    set_parts = []
    vals = []
    for k, v in fields.items():
        set_parts.append(f"{k}=?")
        vals.append(v)
    if set_parts:
        sql = "UPDATE users SET " + ", ".join(set_parts) + " WHERE id=?"
        vals.append(user_id)
        c.execute(sql, tuple(vals))
        conn.commit()
    conn.close()

def search_users(search=""):
    conn = _get_conn()
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
    conn = _get_conn()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_phone(phone):
    conn = _get_conn()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE phone=?", (phone,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def delete_user(user_id):
    conn = _get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE id=?", (user_id,))
    c.execute("DELETE FROM repayments WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

# ----------------------
# REPAYMENT FUNCTIONS
# ----------------------
def generate_repayment_schedule(user_id, loan_amount, duration):
    conn = _get_conn()
    c = conn.cursor()
    installment_amount = round(loan_amount / duration, 2) if duration > 0 else 0
    today = datetime.now()
    for i in range(duration):
        due_date = (today + timedelta(days=i+1)).strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT INTO repayments (user_id, amount, due_date) VALUES (?, ?, ?)", (user_id, installment_amount, due_date))
    conn.commit()
    conn.close()

def get_repayments_by_user(user_id):
    conn = _get_conn()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM repayments WHERE user_id=? ORDER BY due_date ASC", (user_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def mark_repayment_as_paid(repayment_id):
    conn = _get_conn()
    c = conn.cursor()
    c.execute("UPDATE repayments SET paid=1 WHERE id=?", (repayment_id,))
    conn.commit()
    conn.close()

def compute_user_paid_and_remaining(user):
    repayments = get_repayments_by_user(user['id'])
    total_paid = sum(r['amount'] for r in repayments if r.get('paid') == 1)
    remaining = (user.get('loan_amount') or 0) - total_paid
    return round(total_paid, 2), round(remaining, 2)

# ----------------------
# USSD SESSIONS HELPERS
# ----------------------
def get_ussd_session(session_id):
    conn = _get_conn()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM ussd_sessions WHERE session_id=?", (session_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def upsert_ussd_session(session_id, phone=None, step=None, **kwargs):
    conn = _get_conn()
    c = conn.cursor()
    existing = c.execute("SELECT session_id FROM ussd_sessions WHERE session_id=?", (session_id,)).fetchone()
    if existing:
        fields = []
        values = []
        if phone is not None:
            fields.append("phone=?"); values.append(phone)
        if step is not None:
            fields.append("step=?"); values.append(step)
        for k, v in kwargs.items():
            if k in ("national_id", "full_name", "address", "father_name", "mother_name", "loan_amount"):
                fields.append(f"{k}=?"); values.append(v)
        if fields:
            sql = "UPDATE ussd_sessions SET " + ", ".join(fields) + " WHERE session_id=?"
            values.append(session_id)
            c.execute(sql, tuple(values))
    else:
        columns = ["session_id"]
        placeholders = ["?"]
        values = [session_id]
        if phone is not None:
            columns.append("phone"); placeholders.append("?"); values.append(phone)
        if step is not None:
            columns.append("step"); placeholders.append("?"); values.append(step)
        for k, v in kwargs.items():
            if k in ("national_id", "full_name", "address", "father_name", "mother_name", "loan_amount"):
                columns.append(k); placeholders.append("?"); values.append(v)
        sql = f"INSERT INTO ussd_sessions ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
        c.execute(sql, tuple(values))
    conn.commit()
    conn.close()

def clear_ussd_session(session_id):
    conn = _get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM ussd_sessions WHERE session_id=?", (session_id,))
    conn.commit()
    conn.close()

# ----------------------
# DASHBOARD SUMMARY
# ----------------------
def get_dashboard_summary():
    conn = _get_conn()
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
        "total_loans": round(total_loans, 2),
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
    # compute totals per user for display
    today = datetime.now()
    for u in all_users:
        repayments = get_repayments_by_user(u['id'])
        total_paid = sum(r['amount'] for r in repayments if r.get('paid') == 1)
        u['total_paid'] = round(total_paid, 2)
        u['remaining'] = round((u.get('loan_amount') or 0) - total_paid, 2)
        # compute next unpaid countdown seconds
        next_unpaid = None
        for r in repayments:
            if r.get('paid') == 0:
                due = datetime.strptime(r['due_date'], "%Y-%m-%d %H:%M:%S")
                if next_unpaid is None or due < next_unpaid:
                    next_unpaid = due
        u['countdown_seconds'] = max(int((next_unpaid - today).total_seconds()), 0) if next_unpaid else 0

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
# USSD ROUTE
# ----------------------
@app.route("/ussd", methods=["POST"])
def ussd():
    """
    Supports:
     - Single-request registration where provider sends all fields in one text: "1*id*name*address*father*mother*amount*duration"
     - Step-by-step registration via sessionId using ussd_sessions table.
    """
    session_id = request.form.get("sessionId") or request.form.get("session_id") or ""
    phone_number = request.form.get("phoneNumber") or request.form.get("phone") or ""
    text = request.form.get("text", "") or ""

    user_response = text.split("*") if text else []
    response_text = ""

    # Main menu
    if text == "" or text is None:
        response_text = "CON Welcome to USSD Loan Service\n1. Register\n2. Check Loan\n3. View Repayments"
        return Response(response_text, mimetype="text/plain")

    # If user sent a single combined registration in one request (len >= 8)
    if user_response and user_response[0] == "1" and len(user_response) >= 8:
        try:
            national_id = user_response[1].strip()
            full_name = user_response[2].strip()
            address = user_response[3].strip()
            father_name = user_response[4].strip()
            mother_name = user_response[5].strip()
            loan_amount = float(user_response[6])
            duration = int(user_response[7])
        except Exception:
            response_text = "END Invalid registration data. Please try again."
            return Response(response_text, mimetype="text/plain")

        existing_user = get_user_by_phone(phone_number)
        if existing_user:
            response_text = f"END You are already registered, {existing_user['full_name']}."
            return Response(response_text, mimetype="text/plain")

        user_id = add_user(session_id, phone_number, national_id, full_name, address, father_name, mother_name, loan_amount, duration)
        generate_repayment_schedule(user_id, loan_amount, duration)
        clear_ussd_session(session_id)
        response_text = "END ✅ Registration successful! You will receive SMS confirmation."
        return Response(response_text, mimetype="text/plain")

    # Otherwise treat as step-by-step using ussd_sessions
    sess = get_ussd_session(session_id) or {}
    step = sess.get("step", 0)

    if user_response and user_response[0] == "1" and len(user_response) == 1:
        upsert_ussd_session(session_id, phone=phone_number, step=1)
        response_text = "CON Enter your National ID:"
        return Response(response_text, mimetype="text/plain")

    if sess:
        last_answer = user_response[-1].strip() if user_response else ""
        try:
            step = int(sess.get("step", 1))
        except Exception:
            step = 1

        if step == 1:
            upsert_ussd_session(session_id, national_id=last_answer, step=2)
            response_text = "CON Enter your Full Name:"
            return Response(response_text, mimetype="text/plain")
        elif step == 2:
            upsert_ussd_session(session_id, full_name=last_answer, step=3)
            response_text = "CON Enter your Address (village, cell, sector):"
            return Response(response_text, mimetype="text/plain")
        elif step == 3:
            upsert_ussd_session(session_id, address=last_answer, step=4)
            response_text = "CON Enter your Father's Name:"
            return Response(response_text, mimetype="text/plain")
        elif step == 4:
            upsert_ussd_session(session_id, father_name=last_answer, step=5)
            response_text = "CON Enter your Mother's Name:"
            return Response(response_text, mimetype="text/plain")
        elif step == 5:
            upsert_ussd_session(session_id, mother_name=last_answer, step=6)
            response_text = "CON Enter desired Loan Amount (RWF):"
            return Response(response_text, mimetype="text/plain")
        elif step == 6:
            try:
                loan_amount = float(last_answer)
            except Exception:
                response_text = "END Invalid amount. Session cancelled."
                clear_ussd_session(session_id)
                return Response(response_text, mimetype="text/plain")
            upsert_ussd_session(session_id, loan_amount=loan_amount, step=7)
            response_text = "CON Enter loan duration (in days):"
            return Response(response_text, mimetype="text/plain")
        elif step == 7:
            try:
                duration = int(last_answer)
            except Exception:
                response_text = "END Invalid duration. Session cancelled."
                clear_ussd_session(session_id)
                return Response(response_text, mimetype="text/plain")
            s = get_ussd_session(session_id)
            if not s:
                response_text = "END Session expired. Please start again."
                return Response(response_text, mimetype="text/plain")
            national_id = s.get("national_id")
            full_name = s.get("full_name")
            address = s.get("address")
            father_name = s.get("father_name")
            mother_name = s.get("mother_name")
            loan_amount = s.get("loan_amount")
            if not all([national_id, full_name, address, father_name, mother_name, loan_amount]):
                response_text = "END Missing data in your session. Please start again."
                clear_ussd_session(session_id)
                return Response(response_text, mimetype="text/plain")
            existing_user = get_user_by_phone(phone_number)
            if existing_user:
                response_text = f"END You are already registered, {existing_user['full_name']}."
                clear_ussd_session(session_id)
                return Response(response_text, mimetype="text/plain")
            user_id = add_user(session_id, phone_number, national_id, full_name, address, father_name, mother_name, float(loan_amount), duration)
            generate_repayment_schedule(user_id, float(loan_amount), duration)
            clear_ussd_session(session_id)
            response_text = "END ✅ Registration successful! You will receive SMS confirmation."
            return Response(response_text, mimetype="text/plain")
        else:
            response_text = "END Invalid session state. Please start again."
            clear_ussd_session(session_id)
            return Response(response_text, mimetype="text/plain")

    # Check loan (option 2)
    if user_response and user_response[0] == "2":
        user = get_user_by_phone(phone_number)
        if not user:
            response_text = "END You are not registered yet."
        else:
            response_text = f"END Hello {user['full_name']}, Loan Amount: RWF {user['loan_amount']}, Duration: {user['duration']} days"
        return Response(response_text, mimetype="text/plain")

    # View repayments (option 3)
    if user_response and user_response[0] == "3":
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
        return Response(response_text, mimetype="text/plain")

    # Fallback
    response_text = "END Invalid choice or format. Please try again."
    return Response(response_text, mimetype="text/plain")

# ----------------------
# USER DETAILS & REPAYMENTS
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
        # readable remaining string
        if delta.total_seconds() < 0:
            remaining_text = f"{abs(delta.days)} days ago"
            status_override = "Overdue" if r.get("paid") == 0 else "Paid"
        else:
            remaining_text = f"{delta.days} days"
            status_override = "Paid" if r.get("paid") == 1 else "Unpaid"

        r["remaining_time"] = remaining_text
        r["status"] = status_override

    total_paid, remaining = compute_user_paid_and_remaining(user)
    user_summary = {"total_paid": total_paid, "remaining": remaining}

    return render_template("user_details.html", user=user, repayments=repayments, summary=user_summary)

# mark repayment as paid (used by templates)
@app.route("/mark_paid/<int:repayment_id>")
def mark_paid(repayment_id):
    mark_repayment_as_paid(repayment_id)
    flash("Repayment marked as Paid.", "success")
    return redirect(request.referrer or url_for("dashboard"))

# view repayment full schedule page
@app.route("/user/<int:user_id>/repayments")
def view_repayments(user_id):
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
        r["remaining_time"] = f"{delta.days} days" if delta.total_seconds() >= 0 else f"{abs(delta.days)} days ago"
        r["status"] = "Paid" if r.get("paid") == 1 else ("Overdue" if delta.total_seconds() < 0 else "Unpaid")
    return render_template("repayments.html", user=user, repayments=repayments)

# ----------------------
# EDIT USER
# ----------------------
@app.route("/user/<int:user_id>/edit", methods=["GET", "POST"])
def edit_user(user_id):
    if "admin" not in session:
        return redirect(url_for("login"))
    user = get_user_by_id(user_id)
    if not user:
        flash("User not found", "error")
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        # accept fields to update
        full_name = request.form.get("full_name", user.get("full_name"))
        phone = request.form.get("phone", user.get("phone"))
        national_id = request.form.get("national_id", user.get("national_id"))
        address = request.form.get("address", user.get("address"))
        father_name = request.form.get("father_name", user.get("father_name"))
        mother_name = request.form.get("mother_name", user.get("mother_name"))
        loan_amount = request.form.get("loan_amount", user.get("loan_amount"))
        duration = request.form.get("duration", user.get("duration"))
        update_user(user_id,
                    full_name=full_name,
                    phone=phone,
                    national_id=national_id,
                    address=address,
                    father_name=father_name,
                    mother_name=mother_name,
                    loan_amount=float(loan_amount),
                    duration=int(duration))
        flash("User updated successfully.", "success")
        return redirect(url_for("user_details", user_id=user_id))
    return render_template("edit_user.html", user=user)

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
# RUN APP
# ----------------------
if __name__ == "__main__":
    app.run(debug=True)
