"""
seed_demo_student.py
Creates a demo student with randomized topic scores for frontend testing.
Usage: python3 question_bank/scripts/seed_demo_student.py
"""
from __future__ import annotations

import sqlite3
import random
import os
from datetime import datetime

DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "questions.db")
)

STUDENT_ID   = "demo"
STUDENT_NAME = "Demo Student"


def main() -> None:
    if not os.path.exists(DB_PATH):
        print("✗ Database not found. Run setup_db.py first.")
        return

    conn = sqlite3.connect(DB_PATH)
    now = datetime.now().isoformat()

    conn.execute(
        "INSERT OR IGNORE INTO students (id, name, grade_level) VALUES (?, ?, ?)",
        (STUDENT_ID, STUDENT_NAME, 10)
    )

    topics = [r[0] for r in conn.execute(
        "SELECT DISTINCT topic FROM questions ORDER BY topic"
    ).fetchall()]

    if not topics:
        print("✗ No questions in DB. Run seed_anchors.py first.")
        conn.close()
        return

    print(f"Seeding '{STUDENT_NAME}' with random scores...\n")

    for topic in topics:
        avg_score  = round(random.uniform(0.2, 0.95), 2)
        sessions   = random.randint(1, 6)
        last_score = round(max(0.0, min(1.0, avg_score + random.uniform(-0.15, 0.15))), 2)
        trend      = round(last_score - avg_score, 3)

        existing = conn.execute("""
            SELECT perf_id FROM student_performance
            WHERE student_id = ? AND topic = ?
              AND COALESCE(subtopic,   '__all__') = '__all__'
              AND COALESCE(difficulty, '__all__') = '__all__'
        """, (STUDENT_ID, topic)).fetchone()

        if existing:
            conn.execute("""
                UPDATE student_performance
                SET avg_score=?, last_score=?, trend=?, sessions=?, updated_at=?
                WHERE perf_id=?
            """, (avg_score, last_score, trend, sessions, now, existing[0]))
        else:
            conn.execute("""
                INSERT INTO student_performance
                (student_id, topic, subtopic, difficulty,
                 sessions, avg_score, last_score, trend, updated_at)
                VALUES (?, ?, NULL, NULL, ?, ?, ?, ?, ?)
            """, (STUDENT_ID, topic, sessions, avg_score, last_score, trend, now))

        bar = "█" * int(avg_score * 20) + "░" * (20 - int(avg_score * 20))
        print(f"  {topic:<30} {bar}  {avg_score:.0%}")

    conn.commit()
    conn.close()
    print(f"\n✓ Done. Login as '{STUDENT_NAME}' to see scores.")


if __name__ == "__main__":
    main()
