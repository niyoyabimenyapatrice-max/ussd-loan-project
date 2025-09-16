from waitress import serve
from app import app  # Make sure your Flask app is called `app` in app.py

serve(app, host="0.0.0.0", port=5000)
