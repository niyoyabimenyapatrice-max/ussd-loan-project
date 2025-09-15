from flask import Flask, request, render_template, redirect, url_for, session, flash, jsonify, send_file
from database import (
    add_user, generate_repayment_schedule, search_users, get_dashboard_summary,
    get_user_by_id, delete_user, get_repayments_by_user, mark_repayment_as_paid,
    get_momopays, add_momopay, update_momopay_balance, get_merged_momopay_summary, delete_momopay, share_float, get_user_by_phone
)
from datetime import datetime
import hashlib
import io
import csv
import sqlite3

app = Flask(__name__)
app.secret_key = "super_secret_key"

# -------------------
# ADMIN LOGIN
# -------------------
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD_HASH = hashlib.sha256("admin123".encode()).hexdigest()

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

# -------------------
# DASHBOARD
# -------------------
@app.route("/dashboard")
def dashboard():
    if "admin" not in session:
        return redirect(url_for("login"))

    summary = get_dashboard_summary()
    search = request.args.get("search", "")
    page = int(request.args.get("page", 1))
    per_page = 5

    all_users = search_users(search)
    today = datetime.now()

    for user in all_users:
        repayments = get_repayments_by_user(user['id'])
        total_paid = sum(r['amount'] for r in repayments if r.get('paid') == 1)
        user['total_paid'] = total_paid
        user['remaining'] = user['loan_amount'] - total_paid

        next_unpaid = None
        for r in repayments:
            due = datetime.strptime(r['due_date'], "%Y-%m-%d %H:%M:%S")
            if r.get('paid') == 0 and due >= today:
                if next_unpaid is None or due < next_unpaid:
                    next_unpaid = due
        user['countdown_seconds'] = max(int((next_unpaid - today).total_seconds()), 0) if next_unpaid else 0

    total = len(all_users)
    start = (page - 1) * per_page
    end = start + per_page
    rows = all_users[start:end]

    momopay_summary = get_merged_momopay_summary()

    return render_template(
        "dashboard.html",
        summary=summary,
        rows=rows,
        search=search,
        page=page,
        total_pages=(total + per_page - 1) // per_page,
        momopay_summary=momopay_summary
    )

# -------------------
# USER DETAILS
# -------------------
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

# -------------------
# DELETE USER
# -------------------
@app.route("/delete_user/<int:user_id>")
def delete_user_route(user_id):
    if "admin" not in session:
        return redirect(url_for("login"))
    delete_user(user_id)
    flash("User deleted successfully", "success")
    return redirect(url_for("dashboard"))

# -------------------
# MARK REPAYMENT PAID
# -------------------
@app.route("/mark_paid/<int:repayment_id>")
def mark_paid_route(repayment_id):
    if "admin" not in session:
        return redirect(url_for("login"))

    mark_repayment_as_paid(repayment_id)
    share_float(repayment_id)

    flash("Repayment marked as paid", "success")
    return redirect(request.referrer or url_for("dashboard"))

# -------------------
# AUTO DEDUCT
# -------------------
@app.route("/auto_deduct")
def auto_deduct_all():
    if "admin" not in session:
        return jsonify({"success": False, "message": "Unauthorized"})

    today = datetime.now()
    users = search_users()
    momopays = get_momopays()
    merged_balance = sum(m['balance'] for m in momopays)

    for user in users:
        repayments = get_repayments_by_user(user['id'])
        for r in repayments:
            if r.get('paid') == 0:
                due_date = datetime.strptime(r['due_date'], "%Y-%m-%d %H:%M:%S")
                if due_date <= today:
                    c_user_momopay = next((m for m in momopays if m["phone"] == user['phone']), None)
                    if c_user_momopay and c_user_momopay['balance'] >= r['amount']:
                        update_momopay_balance(user['phone'], r['amount'])
                    else:
                        proportion = r['amount'] / merged_balance if merged_balance > 0 else 0
                        for m in momopays:
                            deduction = m['balance'] * proportion
                            update_momopay_balance(m['phone'], deduction)
                    mark_repayment_as_paid(r['id'])
                    share_float(r['id'])

    return jsonify({"success": True, "message": "Auto deduction completed"})

# -------------------
# USSD SIMULATION
# -------------------
@app.route("/ussd", methods=["POST"])
def ussd():
    session_id = request.form.get("sessionId")
    service_code = request.form.get("serviceCode")
    phone_number = request.form.get("phoneNumber")
    text = request.form.get("text", "").strip()

    # Normalize phone number to +250 format
    if phone_number.startswith("0"):
        phone_number = "+250" + phone_number[1:]

    user_response = text.split("*")
    response = ""

    if text == "":
        # First screen
        response = "CON Welcome to Loan System\n"
        response += "1. Register\n"
        response += "2. Check Loan Balance\n"
        response += "3. Exit"

    elif user_response[0] == "1":  # Registration flow
        if len(user_response) == 1:
            response = "CON Enter your Full Name:"
        elif len(user_response) == 2:
            response = "CON Enter Loan Amount:"
        elif len(user_response) == 3:
            response = "CON Enter Loan Duration (days):"
        elif len(user_response) == 4:
            full_name = user_response[1]
            loan_amount = float(user_response[2])
            duration = int(user_response[3])

            # Save user in DB
            user_id = add_user(
                session_id,
                phone_number,
                "N/A",  # national_id not asked in USSD for now
                full_name,
                "",  # address
                "",  # father_name
                "",  # mother_name
                loan_amount,
                duration,
            )
            generate_repayment_schedule(user_id, loan_amount, duration)

            response = "END ✅ Registration successful! You will receive SMS confirmation."
        else:
            response = "END Invalid input. Please try again."

    elif user_response[0] == "2":  # Check Loan Balance
        try:
            user = get_user_by_phone(phone_number)
            if user:
                repayments = get_repayments_by_user(user["id"])
                total_paid = sum(r["amount"] for r in repayments if r["status"] == "Paid")
                remaining = user["loan_amount"] - total_paid

                # Find next repayment due
                next_due = None
                for r in repayments:
                    if r["status"] != "Paid":
                        next_due = r["due_date"]
                        break

                response = (
                    f"END 📊 Loan Status\n"
                    f"Loan: {user['loan_amount']}\n"
                    f"Paid: {total_paid}\n"
                    f"Balance: {remaining}\n"
                    f"Next Due: {next_due if next_due else 'None'}"
                )
            else:
                response = "END ❌ No loan record found for your number."
        except Exception as e:
            response = "END ❌ Error checking balance. Please try again later."
            print("USSD Balance Check Error:", e)

    elif user_response[0] == "3":
        response = "END Goodbye!"

    else:
        response = "END Invalid option. Please try again."

    return response



# -------------------
# EXPORT USERS
# -------------------
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
# MoMoPay Routes
# ----------------------
@app.route("/add_momopay", methods=["POST"])
def add_momopay_route():
    phone = request.form.get("phone")
    balance = float(request.form.get("balance", 0))
    float_shared = float(request.form.get("float_shared", 0))
    if phone:
        add_momopay(phone, balance, float_shared)
        flash(f"MoMoPay account {phone} added successfully.", "success")
    else:
        flash("Phone number is required.", "error")
    return redirect(url_for("dashboard"))

@app.route("/update_momopay/<phone>", methods=["POST"])
def update_momopay_route(phone):
    balance = float(request.form.get("balance", 0))
    float_shared = float(request.form.get("float_shared", 0))
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("UPDATE momopays SET balance=?, float_shared=? WHERE phone=?", (balance, float_shared, phone))
    conn.commit()
    conn.close()
    flash(f"MoMoPay account {phone} updated successfully.", "success")
    return redirect(url_for("dashboard"))

@app.route("/delete_momopay/<phone>", methods=["POST"])
def delete_momopay_route(phone):
    delete_momopay(phone)
    flash(f"MoMoPay account {phone} deleted successfully.", "success")
    return redirect(url_for("dashboard"))

# -------------------
if __name__ == "__main__":
    app.run(debug=True)
