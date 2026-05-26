"""
routes/recommendations.py

Flask Blueprint for recommendation endpoints.

Endpoints:
  GET  /api/status           → which method is active, session counts
  POST /api/recommend        → single recommendation (non-streaming)
  GET  /api/recommend/stream → dual streaming recommendation (SSE)
  POST /api/update           → incremental model update after a session

Why is the streaming endpoint GET not POST?
  SSE requires the browser to open a persistent connection using EventSource.
  The browser's EventSource API only supports GET requests — it's a browser
  limitation, not an HTTP rule. So we pass scores as query params instead of
  a request body. For larger payloads in production you'd use a POST to create
  a "session token" first, then GET the stream using that token.
"""

from __future__ import annotations

import sqlite3
import os
import sys
import json

from flask import Blueprint, request, jsonify, Response, stream_with_context

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from ml.recommender import get_recommendation, get_both_recommendations, update_model

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "question_bank", "questions.db"
)

MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "ml", "models", "recommender.pkl"
)

recommendations_bp = Blueprint("recommendations", __name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_real_session_count() -> int:
    if not os.path.exists(DB_PATH):
        return 0
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.execute(
            "SELECT COUNT(DISTINCT session_id) FROM student_results WHERE is_simulated = 0"
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except sqlite3.OperationalError:
        return 0


def get_student_claude_preference(student_id: str) -> bool:
    """
    Look up whether this student has Claude recommendations enabled.
    Returns True (enabled) if student not found — safe default.
    """
    if not os.path.exists(DB_PATH):
        return True
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            "SELECT show_claude_recommendation FROM students WHERE id = ?",
            (student_id,)
        ).fetchone()
        conn.close()
        return bool(row[0]) if row else True
    except sqlite3.OperationalError:
        return True


def validate_scores(scores: dict) -> str | None:
    """Returns an error message string if invalid, None if valid."""
    if not isinstance(scores, dict) or len(scores) == 0:
        return "scores must be a non-empty object"
    for topic, score in scores.items():
        if not isinstance(score, (int, float)) or not (0.0 <= float(score) <= 1.0):
            return f"score for '{topic}' must be a number between 0.0 and 1.0"
    return None


# ── Routes ────────────────────────────────────────────────────────────────────

@recommendations_bp.route("/status", methods=["GET"])
def status():
    """
    GET /api/status
    Useful for debugging — shows which method is active and session counts.
    """
    real_sessions = get_real_session_count()
    return jsonify({
        "real_session_count": real_sessions,
        "model_exists": os.path.exists(MODEL_PATH),
        "active_method": "model" if real_sessions >= 10 and os.path.exists(MODEL_PATH) else "claude",
        "min_sessions_for_model": 10,
    }), 200


@recommendations_bp.route("/recommend", methods=["POST"])
def recommend():
    """
    POST /api/recommend
    Standard non-streaming recommendation. Returns a single JSON response.
    Used internally and for API clients that don't need streaming.

    Body: { "student_id": "...", "scores": { "circles": 0.4, ... } }
    """
    data = request.get_json()
    if not data or "scores" not in data:
        return jsonify({"error": "scores field required"}), 400

    error = validate_scores(data["scores"])
    if error:
        return jsonify({"error": error}), 400

    real_sessions = get_real_session_count()

    try:
        result = get_recommendation(data["scores"], real_session_count=real_sessions)
        return jsonify(result), 200
    except Exception as e:
        print(f"Recommendation error: {e}")
        return jsonify({"error": "Could not generate recommendation"}), 500


@recommendations_bp.route("/recommend/stream", methods=["GET"])
def recommend_stream():
    """
    GET /api/recommend/stream?scores={"circles":0.4,...}&student_id=abc

    Streaming SSE endpoint — runs model and Claude in parallel and pushes
    results to the browser as they arrive.

    Why SSE instead of WebSockets?
      SSE is one-directional (server → client) and much simpler to set up.
      WebSockets are bidirectional — overkill for just pushing results.
      SSE works over regular HTTP, no special protocol needed.

    The browser connects with:
      const evtSource = new EventSource('/api/recommend/stream?scores=...')
      evtSource.onmessage = (e) => { const data = JSON.parse(e.data); ... }
    """
    # Parse scores from query string
    scores_raw = request.args.get("scores")
    student_id = request.args.get("student_id", "anonymous")

    if not scores_raw:
        return jsonify({"error": "scores query param required"}), 400

    try:
        scores = json.loads(scores_raw)
    except json.JSONDecodeError:
        return jsonify({"error": "scores must be valid JSON"}), 400

    error = validate_scores(scores)
    if error:
        return jsonify({"error": error}), 400

    show_claude = get_student_claude_preference(student_id)

    def generate():
        """
        Generator function passed to Flask's stream_with_context.
        stream_with_context keeps the Flask request context alive across
        the lifetime of the generator — required for accessing request data
        inside a streaming response.
        """
        yield from get_both_recommendations(scores, show_claude=show_claude)

    return Response(
        stream_with_context(generate()),
        # text/event-stream is the MIME type that tells the browser
        # this is an SSE stream, not a regular HTTP response
        mimetype="text/event-stream",
        headers={
            # Disable buffering — without this, some servers (nginx, gunicorn)
            # buffer the response and the browser gets nothing until it's done,
            # which defeats the purpose of streaming
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
            # Keep the connection alive between events
            "Connection": "keep-alive",
        }
    )


@recommendations_bp.route("/recommend/toggle-claude", methods=["POST"])
def toggle_claude():
    """
    POST /api/recommend/toggle-claude
    Saves the student's Claude preference to the database.
    Called when the student clicks the Claude toggle button in the UI.

    Body: { "student_id": "...", "enabled": true }
    """
    data = request.get_json()
    if not data or "student_id" not in data or "enabled" not in data:
        return jsonify({"error": "student_id and enabled required"}), 400

    if not os.path.exists(DB_PATH):
        return jsonify({"error": "Database not initialized"}), 500

    try:
        conn = sqlite3.connect(DB_PATH)
        # INSERT OR IGNORE creates the student row if it doesn't exist yet,
        # then UPDATE sets the preference. Two-step because we may not have
        # a full student record at toggle time.
        conn.execute(
            "INSERT OR IGNORE INTO students (id) VALUES (?)",
            (data["student_id"],)
        )
        conn.execute(
            "UPDATE students SET show_claude_recommendation = ? WHERE id = ?",
            (1 if data["enabled"] else 0, data["student_id"])
        )
        conn.commit()
        conn.close()
        return jsonify({"status": "updated", "claude_enabled": data["enabled"]}), 200
    except sqlite3.Error as e:
        print(f"DB error toggling Claude: {e}")
        return jsonify({"error": "Database error"}), 500


@recommendations_bp.route("/update", methods=["POST"])
def update():
    """
    POST /api/update
    Incremental model update after a confirmed student session.

    Body: { "scores": {...}, "confirmed_weak_topic": "circles" }
    """
    data = request.get_json()
    if not data or "scores" not in data or "confirmed_weak_topic" not in data:
        return jsonify({"error": "scores and confirmed_weak_topic required"}), 400

    success = update_model(data["scores"], data["confirmed_weak_topic"])
    if success:
        return jsonify({"status": "updated"}), 200
    else:
        return jsonify({"error": "Model update failed"}), 500
