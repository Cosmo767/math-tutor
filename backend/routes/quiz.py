"""
routes/quiz.py

Quiz building and submission endpoints.

Endpoints:
  POST /api/quiz/build    → build a question set (custom or weakness-focused)
  POST /api/quiz/submit   → score a completed session, update performance history
"""

from __future__ import annotations

import sqlite3
import os
import sys
import json
import uuid
from datetime import datetime
from flask import Blueprint, jsonify, request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "question_bank", "questions.db"
)

quiz_bp = Blueprint("quiz", __name__)

# Score below this threshold flags a topic/subtopic as weak
WEAKNESS_THRESHOLD = 0.65

# Default quiz length if not specified
DEFAULT_QUIZ_LENGTH = 10


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── Quiz Builder ──────────────────────────────────────────────────────────────

@quiz_bp.route("/quiz/build", methods=["POST"])
def build_quiz():
    """
    POST /api/quiz/build

    Builds a question set two ways:
      1. topics provided → student-selected quiz builder
      2. topics omitted  → weakness-focused quiz (reads student_performance)

    Body:
    {
      "student_id": "abc",
      "topics": ["circles", "soh_cah_toa"],   ← omit for weakness focus
      "subtopics": ["arc_length"],             ← optional further filter
      "difficulty": "mixed",                   ← easy | medium | hard | mixed | adaptive
      "n": 10                                  ← number of questions
    }

    difficulty="adaptive" picks difficulty per topic based on the student's
    current performance level — the most useful setting once history exists.
    difficulty="mixed" samples across all three levels.
    """
    data = request.get_json()
    if not data or "student_id" not in data:
        return jsonify({"error": "student_id required"}), 400

    student_id = data["student_id"]
    topics     = data.get("topics")       # None = use weakness detection
    subtopics  = data.get("subtopics")    # None = all subtopics
    difficulty = data.get("difficulty", "adaptive")
    n          = min(int(data.get("n", DEFAULT_QUIZ_LENGTH)), 30)  # cap at 30

    conn = get_db()
    try:
        # ── Step 1: determine target topics ──────────────────────────────────
        if topics is None:
            # No topics specified — find weak ones from performance history
            topics = _get_weak_topics(conn, student_id)
            if not topics:
                # Student has no history yet — use all available topics
                topics = [r["topic"] for r in conn.execute(
                    "SELECT DISTINCT topic FROM questions"
                ).fetchall()]

        # ── Step 2: determine difficulty per topic ────────────────────────────
        # difficulty_map: { topic: "easy"|"medium"|"hard" }
        if difficulty == "adaptive":
            difficulty_map = _get_adaptive_difficulties(conn, student_id, topics)
        elif difficulty == "mixed":
            difficulty_map = {t: None for t in topics}  # None = no filter
        else:
            difficulty_map = {t: difficulty for t in topics}

        # ── Step 3: fetch questions ───────────────────────────────────────────
        questions = _fetch_questions(conn, topics, subtopics, difficulty_map, n)

        if not questions:
            return jsonify({"error": "No questions found for these criteria"}), 404

        # Generate a session ID for this quiz attempt.
        # The frontend stores this and sends it back with /quiz/submit.
        session_id = str(uuid.uuid4())

        return jsonify({
            "session_id": session_id,
            "student_id": student_id,
            "questions":  questions,
            "meta": {
                "topics":     topics,
                "difficulty": difficulty,
                "n":          len(questions),
                "mode":       "weakness_focus" if data.get("topics") is None else "custom",
            }
        }), 200

    except sqlite3.Error as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


def _get_weak_topics(conn: sqlite3.Connection, student_id: str) -> list[str]:
    """
    Query student_performance for topic-level rollup rows (subtopic IS NULL,
    difficulty IS NULL) where avg_score is below the weakness threshold.
    Ordered by score ascending so weakest topics come first.
    """
    rows = conn.execute("""
        SELECT topic, avg_score, trend
        FROM student_performance
        WHERE student_id = ?
          AND subtopic IS NULL
          AND difficulty IS NULL
          AND avg_score < ?
        ORDER BY avg_score ASC
    """, (student_id, WEAKNESS_THRESHOLD)).fetchall()

    return [r["topic"] for r in rows]


def _get_adaptive_difficulties(
    conn: sqlite3.Connection,
    student_id: str,
    topics: list[str]
) -> dict[str, str | None]:
    """
    For each topic, pick a difficulty level based on current performance:
      score < 0.50  → easy    (build confidence)
      score < 0.75  → medium  (core practice)
      score >= 0.75 → hard    (push forward)
      no history    → medium  (safe default)

    This is the key adaptive logic — the quiz automatically adjusts
    to meet the student where they are without them having to configure anything.
    """
    difficulty_map: dict[str, str | None] = {}

    for topic in topics:
        row = conn.execute("""
            SELECT avg_score FROM student_performance
            WHERE student_id = ? AND topic = ?
              AND subtopic IS NULL AND difficulty IS NULL
        """, (student_id, topic)).fetchone()

        if row is None:
            difficulty_map[topic] = "medium"   # no history → start at medium
        elif row["avg_score"] < 0.50:
            difficulty_map[topic] = "easy"
        elif row["avg_score"] < 0.75:
            difficulty_map[topic] = "medium"
        else:
            difficulty_map[topic] = "hard"

    return difficulty_map


def _fetch_questions(
    conn: sqlite3.Connection,
    topics: list[str],
    subtopics: list[str] | None,
    difficulty_map: dict[str, str | None],
    n: int,
) -> list[dict]:
    """
    Fetch n questions spread across the target topics.
    Questions per topic = n // len(topics), remainder goes to weakest topic.
    Randomized within each topic so the same questions don't repeat.
    """
    questions_per_topic = max(1, n // len(topics))
    all_questions: list[dict] = []

    for topic in topics:
        diff = difficulty_map.get(topic)

        # Build query dynamically based on what filters are active.
        # Parameterized queries (?) prevent SQL injection — never use
        # string formatting to build SQL with user input.
        query = "SELECT * FROM questions WHERE topic = ?"
        params: list = [topic]

        if subtopics:
            placeholders = ",".join("?" * len(subtopics))
            query += f" AND subtopic IN ({placeholders})"
            params.extend(subtopics)

        if diff is not None:
            query += " AND difficulty = ?"
            params.append(diff)

        query += " ORDER BY RANDOM() LIMIT ?"
        params.append(questions_per_topic)

        rows = conn.execute(query, params).fetchall()
        for row in rows:
            q = dict(row)
            # Parse JSON fields back into lists
            q["common_errors"] = json.loads(q.get("common_errors") or "[]")
            q["distractors"]   = json.loads(q.get("distractors") or "[]")
            all_questions.append(q)

    return all_questions[:n]  # trim to exact n if over


# ── Quiz Submission ───────────────────────────────────────────────────────────

@quiz_bp.route("/quiz/submit", methods=["POST"])
def submit_quiz():
    """
    POST /api/quiz/submit

    Receives completed quiz answers, scores them, updates performance history,
    and returns scores broken down by topic and subtopic.

    Body:
    {
      "student_id": "abc",
      "session_id": "uuid-...",
      "answers": [
        {
          "question_id": "circ_arcle_hs_med_001",
          "answer_given": "2pi",
          "time_spent_seconds": 45
        },
        ...
      ]
    }

    Response:
    {
      "session_id": "...",
      "total_score": 0.70,
      "by_topic": {
        "circles": { "score": 0.50, "correct": 2, "total": 4 },
        ...
      },
      "by_subtopic": {
        "circles": {
          "arc_length": { "score": 0.33, "correct": 1, "total": 3 }
        }
      },
      "by_difficulty": { "medium": { "score": 0.60, ... } }
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    required = ["student_id", "session_id", "answers"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"{field} required"}), 400

    student_id = data["student_id"]
    session_id = data["session_id"]
    answers    = data["answers"]

    if not isinstance(answers, list) or len(answers) == 0:
        return jsonify({"error": "answers must be a non-empty array"}), 400

    conn = get_db()
    try:
        # ── Step 1: score each answer ─────────────────────────────────────────
        scored = []
        for ans in answers:
            q_id = ans.get("question_id")
            if not q_id:
                continue

            question = conn.execute(
                "SELECT * FROM questions WHERE id = ?", (q_id,)
            ).fetchone()

            if not question:
                continue

            # Normalize both strings: lowercase, strip whitespace.
            # This handles "2pi" vs "2Pi" vs " 2pi " as all correct.
            # For a more complete solution you'd handle "2π" == "2pi" etc.
            given   = str(ans.get("answer_given", "")).lower().strip()
            correct = str(question["answer"]).lower().strip()
            is_correct = int(given == correct)

            scored.append({
                "question_id":       q_id,
                "topic":             question["topic"],
                "subtopic":          question["subtopic"],
                "difficulty":        question["difficulty"],
                "answer_given":      ans.get("answer_given"),
                "is_correct":        is_correct,
                "time_spent_seconds": ans.get("time_spent_seconds"),
            })

        if not scored:
            return jsonify({"error": "No valid answers could be scored"}), 400

        # ── Step 2: persist raw results ───────────────────────────────────────
        now = datetime.now().isoformat()
        for s in scored:
            conn.execute("""
                INSERT INTO student_results
                (student_id, session_id, question_id, topic, subtopic,
                 difficulty, answer_given, is_correct, time_spent_seconds,
                 is_simulated, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            """, (
                student_id, session_id, s["question_id"],
                s["topic"], s["subtopic"], s["difficulty"],
                s["answer_given"], s["is_correct"],
                s["time_spent_seconds"], now,
            ))

        conn.commit()

        # ── Step 3: compute session scores ────────────────────────────────────
        by_topic, by_subtopic, by_difficulty = _compute_session_scores(scored)
        total_correct = sum(s["is_correct"] for s in scored)
        total_score   = round(total_correct / len(scored), 3)

        # ── Step 4: update performance history ───────────────────────────────
        _update_performance(conn, student_id, by_topic, by_subtopic, scored)
        conn.commit()

        return jsonify({
            "session_id":   session_id,
            "total_score":  total_score,
            "total_correct": total_correct,
            "total_questions": len(scored),
            "by_topic":     by_topic,
            "by_subtopic":  by_subtopic,
            "by_difficulty": by_difficulty,
        }), 200

    except sqlite3.Error as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


def _compute_session_scores(scored: list[dict]) -> tuple[dict, dict, dict]:
    """
    Aggregate scored answers into three views:
      by_topic:      { topic: { score, correct, total } }
      by_subtopic:   { topic: { subtopic: { score, correct, total } } }
      by_difficulty: { difficulty: { score, correct, total } }
    """
    by_topic: dict      = {}
    by_subtopic: dict   = {}
    by_difficulty: dict = {}

    for s in scored:
        topic    = s["topic"]
        subtopic = s["subtopic"]
        diff     = s["difficulty"]
        correct  = s["is_correct"]

        # topic
        if topic not in by_topic:
            by_topic[topic] = {"correct": 0, "total": 0}
        by_topic[topic]["correct"] += correct
        by_topic[topic]["total"]   += 1

        # subtopic
        if topic not in by_subtopic:
            by_subtopic[topic] = {}
        if subtopic not in by_subtopic[topic]:
            by_subtopic[topic][subtopic] = {"correct": 0, "total": 0}
        by_subtopic[topic][subtopic]["correct"] += correct
        by_subtopic[topic][subtopic]["total"]   += 1

        # difficulty
        if diff not in by_difficulty:
            by_difficulty[diff] = {"correct": 0, "total": 0}
        by_difficulty[diff]["correct"] += correct
        by_difficulty[diff]["total"]   += 1

    # Add score ratios
    for d in by_topic.values():
        d["score"] = round(d["correct"] / d["total"], 3)
    for topic_data in by_subtopic.values():
        for d in topic_data.values():
            d["score"] = round(d["correct"] / d["total"], 3)
    for d in by_difficulty.values():
        d["score"] = round(d["correct"] / d["total"], 3)

    return by_topic, by_subtopic, by_difficulty


def _update_performance(
    conn: sqlite3.Connection,
    student_id: str,
    by_topic: dict,
    by_subtopic: dict,
    scored: list[dict],
) -> None:
    """
    Upsert student_performance rows at all three granularity levels.

    Uses INSERT OR REPLACE with explicit perf_id lookup so we update
    existing rows rather than creating duplicates. The UNIQUE index on
    (student_id, topic, COALESCE(subtopic,'__all__'), COALESCE(difficulty,'__all__'))
    enforces one row per combination.

    Rolling average formula:
      new_avg = ((old_avg * old_sessions) + new_score) / (old_sessions + 1)
    This is an incremental mean — no need to store all historical scores.
    """
    now = datetime.now().isoformat()

    def upsert(topic: str, subtopic: str | None, difficulty: str | None, new_score: float):
        # Look up existing row
        existing = conn.execute("""
            SELECT perf_id, avg_score, sessions
            FROM student_performance
            WHERE student_id = ?
              AND topic = ?
              AND COALESCE(subtopic,   '__all__') = COALESCE(?, '__all__')
              AND COALESCE(difficulty, '__all__') = COALESCE(?, '__all__')
        """, (student_id, topic, subtopic, difficulty)).fetchone()

        if existing:
            old_avg      = existing["avg_score"]
            old_sessions = existing["sessions"]
            new_avg      = ((old_avg * old_sessions) + new_score) / (old_sessions + 1)
            trend        = round(new_score - old_avg, 3)
            conn.execute("""
                UPDATE student_performance
                SET avg_score  = ?,
                    last_score = ?,
                    trend      = ?,
                    sessions   = sessions + 1,
                    updated_at = ?
                WHERE perf_id = ?
            """, (round(new_avg, 3), new_score, trend, now, existing["perf_id"]))
        else:
            conn.execute("""
                INSERT INTO student_performance
                (student_id, topic, subtopic, difficulty,
                 sessions, avg_score, last_score, trend, updated_at)
                VALUES (?, ?, ?, ?, 1, ?, ?, 0.0, ?)
            """, (student_id, topic, subtopic, difficulty, new_score, new_score, now))

    # Topic-level rollups
    for topic, data in by_topic.items():
        upsert(topic, None, None, data["score"])

    # Subtopic-level rollups
    for topic, subtopics in by_subtopic.items():
        for subtopic, data in subtopics.items():
            upsert(topic, subtopic, None, data["score"])

    # Granular: subtopic + difficulty
    # Aggregate scored items by (topic, subtopic, difficulty)
    granular: dict = {}
    for s in scored:
        key = (s["topic"], s["subtopic"], s["difficulty"])
        if key not in granular:
            granular[key] = {"correct": 0, "total": 0}
        granular[key]["correct"] += s["is_correct"]
        granular[key]["total"]   += 1

    for (topic, subtopic, difficulty), data in granular.items():
        score = round(data["correct"] / data["total"], 3)
        upsert(topic, subtopic, difficulty, score)
