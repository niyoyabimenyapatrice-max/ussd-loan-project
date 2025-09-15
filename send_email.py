import smtplib
from email.message import EmailMessage
import os
from dotenv import load_dotenv

# -------------------
# LOAD ENVIRONMENT VARIABLES
# -------------------
load_dotenv()
SENDER = os.getenv("EMAIL_SENDER")
RECEIVER = os.getenv("EMAIL_RECEIVER")
PASSWORD = os.getenv("EMAIL_PASSWORD")

# -------------------
# FUNCTION TO SEND EMAIL WITH ATTACHMENTS
# -------------------
def send_report_email(attachments=None):
    if attachments is None:
        attachments = []

    if not SENDER or not RECEIVER or not PASSWORD:
        print("❌ Email credentials are missing in .env")
        return

    msg = EmailMessage()
    msg["Subject"] = "Loan Reports – Registered Users & Repayment Schedules"
    msg["From"] = SENDER
    msg["To"] = RECEIVER
    msg.set_content("Find attached the latest loan registration and repayment reports.")

    # Attach files if they exist
    for filename in attachments:
        if os.path.exists(filename):
            with open(filename, "rb") as f:
                msg.add_attachment(
                    f.read(),
                    maintype="application",
                    subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    filename=filename
                )
        else:
            print(f"⚠️ File not found, skipping: {filename}")

    # Send email
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(SENDER, PASSWORD)
            smtp.send_message(msg)
        print("✅ Email sent successfully.")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

# -------------------
# RUN DIRECTLY
# -------------------
if __name__ == "__main__":
    send_report_email(["registered_users.xlsx", "scheduled_repayments.xlsx"])
