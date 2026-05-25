"""
seed_anchors.py
Import anchor questions from data/anchors.csv into the questions database.
Usage: python question_bank/scripts/seed_anchors.py
"""

import sqlite3
import csv
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "questions.db")
CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "anchors.csv")


def seed_anchors() -> None:
    db_path = os.path.abspath(DB_PATH)
    csv_path = os.path.abspath(CSV_PATH)

    if not os.path.exists(db_path):
        print("✗ Database not found. Run setup_db.py first.")
        return

    if not os.path.exists(csv_path):
        print(f"✗ Anchor CSV not found at: {csv_path}")
        return

    conn = sqlite3.connect(db_path)
    inserted = 0
    skipped = 0
    errors = 0

    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    conn.execute("""
                        INSERT OR IGNORE INTO questions
                        (id, topic, subtopic, grade_band, grade_level, difficulty,
                         ca_standard, format, question, answer, common_errors,
                         distractors, is_anchor)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        row["id"],
                        row["topic"],
                        row["subtopic"],
                        row["grade_band"],
                        int(row["grade_level"]),
                        row["difficulty"],
                        row["ca_standard"],
                        row["format"],
                        row["question"],
                        row["answer"],
                        row["common_errors"],
                        row["distractors"],
                        int(row["is_anchor"]),
                    ))

                    if conn.execute(
                        "SELECT changes()"
                    ).fetchone()[0] > 0:
                        inserted += 1
                        print(f"  ✓ inserted: {row['id']}")
                    else:
                        skipped += 1
                        print(f"  ~ skipped (already exists): {row['id']}")

                except (sqlite3.Error, KeyError, ValueError) as e:
                    errors += 1
                    print(f"  ✗ error on row {row.get('id', '?')}: {e}")

        conn.commit()

    finally:
        conn.close()

    print(f"\nDone — inserted: {inserted}, skipped: {skipped}, errors: {errors}")


if __name__ == "__main__":
    seed_anchors()
