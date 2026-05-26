"""
routes/students.py

Student data endpoints.

Endpoints:
  GET  /api/students/:id/topics     → full performance map (topic + subtopic + difficulty)
  POST /api/students/:id/create     → create or update a student record
"""

from __future__ import annotations

import sqlite3
import os
import sys
from flask import Blueprint, jsonify, request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "question_bank", "questions.db"
)

students_bp = Blueprint("students", __name__)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row   # rows behave like dicts: row["column_name"]
    return conn


@students_bp.route("/students/<student_id>/topics", methods=["GET"])
def get_topic_map(student_id: str):
    """
    GET /api/students/:id/topics

    Returns the student's full performance map structured as a nested object:
    topics → subtopics → difficulties.

    The frontend uses this to render the progress map at whatever granularity
    the student wants — collapsed topic view or drilled-down subtopic view.

    Response shape:
    {
      "student_id": "abc",
      "topics": {
        "circles": {
          "avg_score": 0.55,
          "trend": -0.05,
          "sessions": 3,
          "subtopics": {
            "arc_length": {
              "avg_score": 0.38,
              "trend": -0.08,
              "sessions": 3,
              "difficulties": {
                "medium": { "avg_score": 0.33, "sessions": 2 }
              }
            }
          }
        }
      }
    }
    """
    if not os.path.exists(DB_PATH):
        return jsonify({"error": "Database not found"}), 500

    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT topic, subtopic, difficulty,
                   sessions, avg_score, last_score, trend
            FROM student_performance
            WHERE student_id = ?
            ORDER BY topic, subtopic, difficulty
        """, (student_id,)).fetchall()
    finally:
        conn.close()

    # Build a nested structure from flat rows.
    # We separate rows by their granularity level using NULL checks:
    #   subtopic IS NULL  → topic-level rollup row
    #   difficulty IS NULL (but subtopic set) → subtopic rollup row
    #   both set → granular row
    topics: dict = {}

    for row in rows:
        topic      = row["topic"]
        subtopic   = row["subtopic"]
        difficulty = row["difficulty"]

        if topic not in topics:
            topics[topic] = {"avg_score": 0, "trend": 0, "sessions": 0, "subtopics": {}}

        if subtopic is None:
            # topic-level rollup — populate the top-level topic entry
            topics[topic].update({
                "avg_score":  row["avg_score"],
                "last_score": row["last_score"],
                "trend":      row["trend"],
                "sessions":   row["sessions"],
            })

        elif difficulty is None:
            # subtopic-level rollup
            if subtopic not in topics[topic]["subtopics"]:
                topics[topic]["subtopics"][subtopic] = {
                    "avg_score": 0, "trend": 0, "sessions": 0, "difficulties": {}
                }
            topics[topic]["subtopics"][subtopic].update({
                "avg_score":  row["avg_score"],
                "last_score": row["last_score"],
                "trend":      row["trend"],
                "sessions":   row["sessions"],
            })

        else:
            # granular row — nested under subtopic → difficulties
            if subtopic not in topics[topic]["subtopics"]:
                topics[topic]["subtopics"][subtopic] = {
                    "avg_score": 0, "trend": 0, "sessions": 0, "difficulties": {}
                }
            topics[topic]["subtopics"][subtopic]["difficulties"][difficulty] = {
                "avg_score":  row["avg_score"],
                "last_score": row["last_score"],
                "sessions":   row["sessions"],
            }

    # If student has no performance data yet, return all known topics at 0
    # so the frontend can still render the full progress map on first visit
    if not topics:
        all_topics = _get_all_topics()
        topics = {
            t: {"avg_score": None, "trend": 0, "sessions": 0, "subtopics": {}}
            for t in all_topics
        }

    return jsonify({"student_id": student_id, "topics": topics}), 200


def _get_all_topics() -> list[str]:
    """Return distinct topics from the question bank."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT DISTINCT topic FROM questions ORDER BY topic"
        ).fetchall()
        return [r["topic"] for r in rows]
    finally:
        conn.close()


@students_bp.route("/students/<student_id>/create", methods=["POST"])
def create_student(student_id: str):
    """
    POST /api/students/:id/create

    Creates a student record if it doesn't exist, or updates name/grade.
    Safe to call multiple times — uses INSERT OR IGNORE then UPDATE.

    Body: { "name": "Alex", "grade_level": 10 }
    """
    data = request.get_json() or {}

    if not os.path.exists(DB_PATH):
        return jsonify({"error": "Database not found"}), 500

    conn = get_db()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO students (id) VALUES (?)",
            (student_id,)
        )
        if "name" in data or "grade_level" in data:
            conn.execute("""
                UPDATE students
                SET name = COALESCE(?, name),
                    grade_level = COALESCE(?, grade_level)
                WHERE id = ?
            """, (data.get("name"), data.get("grade_level"), student_id))
        conn.commit()

        student = dict(conn.execute(
            "SELECT * FROM students WHERE id = ?", (student_id,)
        ).fetchone())

        return jsonify(student), 200
    except sqlite3.Error as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
