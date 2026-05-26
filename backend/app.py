"""
app.py

Flask backend entry point.
Registers all route blueprints and starts the server.

Run locally:
    python backend/app.py

Server starts at http://localhost:8000
Frontend served at http://localhost:8000/

Endpoints registered:
    GET  /
    GET  /health
    GET  /api/status
    POST /api/recommend
    GET  /api/recommend/stream
    POST /api/recommend/toggle-claude
    POST /api/update
    GET  /api/students/:id/topics
    POST /api/students/:id/create
    POST /api/quiz/build
    POST /api/quiz/submit
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from routes.recommendations import recommendations_bp
from routes.students import students_bp
from routes.quiz import quiz_bp

load_dotenv()

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

app = Flask(__name__)
CORS(app)

app.register_blueprint(recommendations_bp, url_prefix="/api")
app.register_blueprint(students_bp,        url_prefix="/api")
app.register_blueprint(quiz_bp,            url_prefix="/api")


@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/health")
def health():
    return {"status": "ok", "service": "math-tutor-api"}


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    app.run(debug=True, port=port)
