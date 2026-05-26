"""
app.py

Flask backend entry point.

Why Flask and not FastAPI or Django?
  Flask is minimal — it does exactly what you ask and nothing else.
  FastAPI is faster and has automatic validation, but adds complexity.
  Django is a full framework with ORM, admin, auth built in — overkill here.
  Flask lets you see exactly what's happening at each layer, which matters
  when you're learning how backends work.

Run locally:
  python backend/app.py

The app will start at http://localhost:5000
"""

import os
import sys

# Add project root to path so we can import from ml/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from dotenv import load_dotenv
from routes.recommendations import recommendations_bp

load_dotenv()

app = Flask(__name__)

# Blueprints are Flask's way of organizing routes into separate files.
# As the app grows, each feature gets its own blueprint:
# recommendations, students, questions, results, etc.
# This keeps app.py clean — it just registers blueprints.
app.register_blueprint(recommendations_bp, url_prefix="/api")

@app.route("/health")
def health():
    """Simple health check — useful for verifying the server is running."""
    return {"status": "ok", "service": "math-tutor-api"}


if __name__ == "__main__":
    # debug=True: auto-reloads when you save a file, shows detailed errors.
    # Never use debug=True in production.
    port = int(os.getenv("PORT", 5000))
    app.run(debug=True, port=port)
