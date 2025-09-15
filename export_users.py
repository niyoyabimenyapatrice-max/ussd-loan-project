import sqlite3
import argparse
from math import ceil
from database import search_users, get_repayments_by_user, get_momopays
from datetime import datetime

def view_users(show_unpaid_only=False, national_id=None, name=None, min_loan=None, max_loan=None, duration=None, sort_by='id', sort_order='asc', page=1, page_size=10):
    try:
        users = search_users()
        momopays = get_momopays()
        today = datetime.now()

        # Filter users
        filtered = []
        for u in users:
            if show_unpaid_only:
                repayments = get_repayments_by_user(u['id'])
                if all(r['status'] == 'Paid' for r in repayments):
                    continue

            if national_id and u['national_id'] != national_id:
                continue
            if name and name.lower() not in u['full_name'].lower():
                continue
            if min_loan is not None and u['loan_amount'] < min_loan:
                continue
            if max_loan is not None and u['loan_amount'] > max_loan:
                continue
            if duration is not None and u['duration'] != duration:
                continue

            # Enrich with repayment info
            repayments = get_repayments_by_user(u['id'])
            total_paid = sum(r['amount'] for r in repayments if r['status'] == 'Paid')
            u['total_paid'] = total_paid
            u['remaining'] = u['loan_amount'] - total_paid

            next_unpaid = None
            for r in repayments:
                due = datetime.strptime(r['due_date'], "%Y-%m-%d %H:%M:%S")
                if r['status'] != 'Paid' and due >= today:
                    if next_unpaid is None or due < next_unpaid:
                        next_unpaid = due
            u['next_due'] = next_unpaid.strftime("%Y-%m-%d %H:%M:%S") if next_unpaid else "Completed"

            # MoMoPay info
            momo = next((m for m in momopays if m['phone'] == u['phone']), None)
            u['momo_balance'] = momo['balance'] if momo else 0
            u['float_shared'] = momo['float_shared'] if momo else 0

            filtered.append(u)

        # Sort
        filtered.sort(key=lambda x: x.get(sort_by, 0), reverse=(sort_order.lower()=='desc'))

        # Pagination
        total_users = len(filtered)
        total_pages = max(1, ceil(total_users / page_size))
        if page < 1: page = 1
        elif page > total_pages: page = total_pages
        start = (page-1)*page_size
        end = start + page_size
        page_users = filtered[start:end]

        if not page_users:
            print("⚠️ No users found matching criteria.")
            return

        print(f"📋 Registered Users (Page {page} of {total_pages}):\n")
        for u in page_users:
            print(f"ID: {u['id']}, Name: {u['full_name']}, Phone: {u['phone']}, Loan: {u['loan_amount']}, Duration: {u['duration']} days")
            print(f"Total Paid: {u['total_paid']}, Remaining: {u['remaining']}, Next Due: {u['next_due']}")
            print(f"MoMo Balance: {u['momo_balance']}, Float Shared: {u['float_shared']}")
            print("-"*50)

        print(f"Showing {len(page_users)} users out of {total_users} total matching users.")

    except Exception as e:
        print(f"❌ Failed to load users: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="View registered users with MoMoPay info")
    parser.add_argument('--unpaid', action='store_true', help='Show only users with unpaid loans')
    parser.add_argument('--national_id', type=str, help='Filter by exact national ID')
    parser.add_argument('--name', type=str, help='Filter users whose full name contains substring (case-insensitive)')
    parser.add_argument('--min_loan', type=float, help='Filter users with loan amount >= value')
    parser.add_argument('--max_loan', type=float, help='Filter users with loan amount <= value')
    parser.add_argument('--duration', type=int, help='Filter users with exact loan duration')
    parser.add_argument('--sort_by', type=str, default='id', help='Sort by field: id, full_name, loan_amount, duration')
    parser.add_argument('--sort_order', type=str, default='asc', help='Sort order: asc or desc')
    parser.add_argument('--page', type=int, default=1, help='Page number')
    parser.add_argument('--page_size', type=int, default=10, help='Users per page')

    args = parser.parse_args()

    view_users(
        show_unpaid_only=args.unpaid,
        national_id=args.national_id,
        name=args.name,
        min_loan=args.min_loan,
        max_loan=args.max_loan,
        duration=args.duration,
        sort_by=args.sort_by,
        sort_order=args.sort_order,
        page=args.page,
        page_size=args.page_size
    )
