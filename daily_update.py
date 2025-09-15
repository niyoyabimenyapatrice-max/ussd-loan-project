from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from database import (
    search_users, get_repayments_by_user, get_momopays,
    update_momopay_balance, mark_repayment_as_paid, share_float
)
from export_data import export_to_excel
from send_email import send_report_email

def auto_deduct_repayments():
    print(f"[{datetime.now()}] Running auto deduction...")
    today = datetime.now()
    users = search_users()
    momopays = get_momopays()
    merged_balance = sum(m['balance'] for m in momopays)

    for user in users:
        repayments = get_repayments_by_user(user['id'])
        for r in repayments:
            if r['status'] != "Paid":
                due_date = datetime.strptime(r['due_date'], "%Y-%m-%d %H:%M:%S")
                if due_date <= today:
                    # Deduct from user's registered MoMoPay if possible
                    c_user_momopay = next((m for m in momopays if m["phone"] == user['phone']), None)
                    if c_user_momopay and c_user_momopay['balance'] >= r['amount']:
                        update_momopay_balance(user['phone'], r['amount'])
                    else:
                        # Deduct proportionally from merged MoMoPay accounts
                        proportion = r['amount'] / merged_balance if merged_balance > 0 else 0
                        for m in momopays:
                            deduction = m['balance'] * proportion
                            update_momopay_balance(m['phone'], deduction)

                    # Mark repayment as paid and share float
                    mark_repayment_as_paid(r['id'])
                    share_float(r['id'])

    print(f"[{datetime.now()}] Auto deduction finished.")

    # -------------------
    # EXPORT AND EMAIL REPORTS
    # -------------------
    export_to_excel()
    send_report_email([
        "registered_users.xlsx",
        "scheduled_repayments.xlsx"
    ])
    print(f"[{datetime.now()}] Reports exported and emailed successfully.")

# -------------------
# SCHEDULER
# -------------------
def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(auto_deduct_repayments, 'interval', minutes=1)  # adjust interval as needed
    scheduler.start()
    print("Scheduler started for auto deduction and report sending.")
