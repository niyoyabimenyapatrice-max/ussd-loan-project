from database import add_user, generate_repayment_schedule

# Sample user
user_id = add_user(
    session_id="sess123",
    phone="+250789036156",
    national_id="123456789",
    full_name="Patrice",
    address="Gitesi Sector, Karongi District",
    father_name="Father Name",
    mother_name="Mother Name",
    loan_amount=5000,
    duration=5
)

# Generate repayment schedule
generate_repayment_schedule(user_id, 5000, 5)

print("✅ Sample user and repayments added!")
