"""
setup_db.py
Initialize the math-tutor SQLite database from schema file.
Usage: python question_bank/scripts/setup_db.py
"""

import sqlite3
import os

DB_PATH     = os.path.join(os.path.dirname(__file__), "..", "questions.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "001_initial_schema.sql")


def setup_database() -> None:
    db_path     = os.path.abspath(DB_PATH)
    schema_path = os.path.abspath(SCHEMA_PATH)

    print(f"Initializing database at: {db_path}")

    with open(schema_path, "r") as f:
        schema_sql = f.read()

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(schema_sql)
        conn.commit()
        print("✓ Schema applied\n")

        # Print all tables and their row counts so you can verify
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()

        print("Tables created:")
        for (table,) in tables:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {table:<30} {count} rows")

    except sqlite3.Error as e:
        print(f"✗ Database error: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    setup_database()
