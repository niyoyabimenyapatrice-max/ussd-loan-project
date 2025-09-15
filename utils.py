from datetime import datetime, timedelta

# -------------------
# TIME HELPERS
# -------------------
def format_datetime(dt):
    """Format datetime object to string."""
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def parse_datetime(dt_str):
    """Convert string to datetime object."""
    return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")

def countdown_to(target_dt):
    """Return remaining time in days, hours, minutes."""
    now = datetime.now()
    delta = target_dt - now
    if delta.total_seconds() <= 0:
        return "0 days"
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{days}d {hours}h {minutes}m"

# -------------------
# LOAN HELPERS
# -------------------
def calculate_installment(amount, duration):
    """Compute per-period installment."""
    if duration <= 0:
        return 0
    return round(amount / duration, 2)

def calculate_float(amount, percentage=0.25):
    """Compute float/share based on a percentage of amount."""
    return round(amount * percentage, 2)

# -------------------
# PAGINATION HELPER
# -------------------
def paginate(items, page=1, per_page=10):
    """Return a slice of items for the current page."""
    total = len(items)
    start = (page - 1) * per_page
    end = start + per_page
    total_pages = (total + per_page - 1) // per_page
    return items[start:end], total_pages

# -------------------
# USSD HELPERS
# -------------------
def parse_ussd_input(text):
    """Split USSD input string by '*' and strip whitespace."""
    return [t.strip() for t in text.split("*")]

def build_ussd_response(message, cont=True):
    """
    Build USSD response string.
    cont=True => CON (continue)
    cont=False => END (finish)
    """
    prefix = "CON" if cont else "END"
    return f"{prefix} {message}"
