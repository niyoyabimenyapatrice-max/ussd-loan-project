import sqlite3
import pandas as pd
from datetime import datetime
import os
from database import get_momopays

DB_FILE = "users.db"

def export_to_excel():
    try:
        conn = sqlite3.connect(DB_FILE)

        # -------------------
        # Export Users
        # -------------------
        users_df = pd.read_sql_query("SELECT * FROM users", conn)

        # -------------------
        # Export Repayments
        # -------------------
        repayments_df = pd.read_sql_query("SELECT * FROM repayments", conn)

        # -------------------
        # Export MoMoPay
        # -------------------
        momopays = get_momopays()
        momopays_df = pd.DataFrame(momopays)

        # -------------------
        # Save files with timestamp
        # -------------------
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        users_file = f"registered_users_{timestamp}.xlsx"
        repayments_file = f"scheduled_repayments_{timestamp}.xlsx"
        momopays_file = f"momopays_{timestamp}.xlsx"

        if not users_df.empty:
            users_df.to_excel(users_file, index=False)
            print(f"✅ Exported users to {users_file}")
        else:
            print("⚠️ No user data found to export.")

        if not repayments_df.empty:
            repayments_df.to_excel(repayments_file, index=False)
            print(f"✅ Exported repayments to {repayments_file}")
        else:
            print("⚠️ No repayment data found to export.")

        if not momopays_df.empty:
            momopays_df.to_excel(momopays_file, index=False)
            print(f"✅ Exported MoMoPay data to {momopays_file}")
        else:
            print("⚠️ No MoMoPay data found to export.")

        conn.close()

    except Exception as e:
        print(f"❌ Failed to export data: {e}")


if __name__ == "__main__":
    export_to_excel()
