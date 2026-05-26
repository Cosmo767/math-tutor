"""
quick_add.py

Conversational question addition workflow.
Describe a question in plain English, Claude formats it correctly,
inserts it into the database, and optionally generates similar questions.

Usage:
    python question_bank/scripts/quick_add.py

Requires:
    ANTHROPIC_API_KEY in .env
"""

import anthropic
import sqlite3
import json
import re
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not API_KEY:
    print("✗ ANTHROPIC_API_KEY not found in .env")
    sys.exit(1)

client = anthropic.Anthropic(api_key=API_KEY)

DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "questions.db")
)

TOPICS = [
    "triangle_congruence", "similarity", "transformations",
    "pythagorean_theorem", "special_right_triangles", "soh_cah_toa",
    "unit_circle", "circles", "coordinate_geometry",
    "area_and_volume", "angle_relationships", "proofs_and_reasoning",
]

DIFFICULTY_DEFS = """
- easy: single step, standard numbers, tests one concept directly
- medium: two steps, or one concept applied in a slightly unfamiliar way
- hard: multi-step, connects two concepts, requires non-obvious setup
"""

FORMAT_PROMPT = f"""You are helping build a high school geometry question bank.

The user will describe a math question in plain English.
Your job is to format it as a structured database row.

Valid topics: {json.dumps(TOPICS)}

Difficulty definitions:
{DIFFICULTY_DEFS}

Format rules:
- format: use "multiple_choice" for conceptual/identifying questions, "numeric_input" for calculations
- multiple_choice: distractors must have exactly 4 items including the correct answer
- numeric_input: distractors must be empty []
- common_errors: 2-3 realistic wrong answers students actually make
- ca_standard: best matching California HSG standard code
- grade_level: integer 9 or 10
- grade_band: always "high" for this bank

Respond ONLY in valid JSON, no preamble:
{{
  "topic": "...",
  "subtopic": "...",
  "grade_band": "high",
  "grade_level": 9,
  "difficulty": "easy|medium|hard",
  "ca_standard": "HSG...",
  "format": "multiple_choice|numeric_input",
  "question": "full question text",
  "answer": "correct answer",
  "common_errors": ["wrong1", "wrong2"],
  "distractors": ["correct", "wrong1", "wrong2", "wrong3"],
  "difficulty_justification": "one sentence"
}}"""


VARIATION_PROMPT = """You are helping build a high school geometry question bank.

Generate {n} variations of this anchor question.
Same topic, subtopic, difficulty, and CA standard — different numbers or context.
Each variation must be a distinct question, not just different numbers.
Add realistic common errors students would actually make.

Anchor question:
{anchor}

Difficulty definition for "{difficulty}":
{difficulty_def}

Respond ONLY in valid JSON, no preamble:
{{
  "questions": [
    {{
      "question": "...",
      "answer": "...",
      "common_errors": ["...", "..."],
      "distractors": ["...", "...", "...", "..."],
      "difficulty_justification": "..."
    }}
  ]
}}"""

DIFFICULTY_DEFS_MAP = {
    "easy":   "single step, standard numbers, tests one concept directly",
    "medium": "two steps, or one concept applied in a slightly unfamiliar way",
    "hard":   "multi-step, connects two concepts, requires non-obvious setup",
}


def format_question(description: str) -> dict:
    """Send user's plain English description to Claude, get back a structured row."""
    print("\n  Formatting with Claude...")

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        system=FORMAT_PROMPT,
        messages=[{"role": "user", "content": description}]
    )

    raw = response.content[0].text.strip()
    raw = re.sub(r'^```json\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    return json.loads(raw)


def generate_variations(anchor: dict, n: int) -> list[dict]:
    """Generate n variations of an anchor question."""
    print(f"\n  Generating {n} variations...")

    difficulty_def = DIFFICULTY_DEFS_MAP.get(anchor["difficulty"], "")
    anchor_text = json.dumps({
        "question": anchor["question"],
        "answer": anchor["answer"],
        "topic": anchor["topic"],
        "subtopic": anchor["subtopic"],
        "format": anchor["format"],
    }, indent=2)

    prompt = VARIATION_PROMPT.format(
        n=n,
        anchor=anchor_text,
        difficulty=anchor["difficulty"],
        difficulty_def=difficulty_def,
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text.strip()
    raw = re.sub(r'^```json\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    data = json.loads(raw)
    return data["questions"]


def make_id(topic: str, subtopic: str, difficulty: str) -> str:
    """
    Generate a unique ID by checking the DB for existing IDs with the same prefix
    and incrementing. Ensures no collisions even if you run the script many times.
    """
    t = re.sub(r'[^a-z]', '', topic[:6])
    s = re.sub(r'[^a-z]', '', subtopic[:6])
    d = difficulty[:3]
    prefix = f"{t}_{s}_hs_{d}_"

    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id FROM questions WHERE id LIKE ?",
        (prefix + "%",)
    ).fetchall()
    conn.close()

    existing_nums = []
    for (row_id,) in rows:
        suffix = row_id.replace(prefix, "")
        if suffix.isdigit():
            existing_nums.append(int(suffix))

    next_num = max(existing_nums, default=0) + 1
    return f"{prefix}{next_num:03d}"


def insert_question(q: dict, is_anchor: int = 1) -> str:
    """Insert a question dict into the database. Returns the generated ID."""
    q_id = make_id(q["topic"], q["subtopic"], q["difficulty"])

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            INSERT INTO questions
            (id, topic, subtopic, grade_band, grade_level, difficulty,
             ca_standard, format, question, answer, common_errors,
             distractors, is_anchor, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            q_id,
            q["topic"],
            q["subtopic"],
            q.get("grade_band", "high"),
            q.get("grade_level", 10),
            q["difficulty"],
            q.get("ca_standard", ""),
            q["format"],
            q["question"],
            q["answer"],
            json.dumps(q.get("common_errors", [])),
            json.dumps(q.get("distractors", [])),
            is_anchor,
            datetime.now().isoformat(),
        ))
        conn.commit()
    finally:
        conn.close()

    return q_id


def preview_question(q: dict) -> None:
    """Print a readable preview of a question dict."""
    print(f"""
  ┌─────────────────────────────────────────────────────
  │ Topic:      {q.get('topic')} → {q.get('subtopic')}
  │ Grade:      {q.get('grade_band')} / level {q.get('grade_level')}
  │ Difficulty: {q.get('difficulty')}
  │ Standard:   {q.get('ca_standard')}
  │ Format:     {q.get('format')}
  │
  │ Q: {q.get('question')}
  │ A: {q.get('answer')}
  │
  │ Common errors: {q.get('common_errors')}
  │ Why this difficulty: {q.get('difficulty_justification', '—')}
  └─────────────────────────────────────────────────────""")


def main() -> None:
    if not os.path.exists(DB_PATH):
        print(f"✗ Database not found at {DB_PATH}")
        print("  Run setup_db.py first.")
        sys.exit(1)

    print("\n📐 math-tutor — Quick Add")
    print("Describe your question in plain English.")
    print("Type 'quit' to exit.\n")

    while True:
        # ── Step 1: get description ───────────────────────────────────────────
        print("─" * 60)
        description = input("Describe the question (or 'quit'): ").strip()

        if description.lower() in ("quit", "exit", "q"):
            print("Bye.")
            break

        if not description:
            continue

        # ── Step 2: Claude formats it ─────────────────────────────────────────
        try:
            formatted = format_question(description)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"  ✗ Claude returned unexpected format: {e}")
            print("  Try describing the question differently.")
            continue
        except anthropic.APIError as e:
            print(f"  ✗ API error: {e}")
            continue

        # ── Step 3: preview and confirm ───────────────────────────────────────
        preview_question(formatted)

        confirm = input("\n  Add this question? (y/n/edit): ").strip().lower()

        if confirm == "edit":
            # Allow overriding specific fields
            print("  Which field to edit? (question/answer/difficulty/topic/subtopic/standard)")
            field = input("  Field: ").strip().lower()
            if field in formatted:
                new_val = input(f"  New value for '{field}': ").strip()
                formatted[field] = new_val
                preview_question(formatted)
                confirm = input("  Add now? (y/n): ").strip().lower()

        if confirm != "y":
            print("  Skipped.")
            continue

        # ── Step 4: insert anchor ─────────────────────────────────────────────
        anchor_id = insert_question(formatted, is_anchor=1)
        print(f"\n  ✓ Added anchor: {anchor_id}")

        # ── Step 5: optionally generate variations ────────────────────────────
        gen = input("\n  Generate variations? (enter number, or n): ").strip().lower()

        if gen == "n" or gen == "":
            print("  Done.\n")
            continue

        try:
            n = int(gen)
        except ValueError:
            print("  Not a number — skipping variations.")
            continue

        if n < 1 or n > 20:
            print("  Please enter a number between 1 and 20.")
            continue

        try:
            variations = generate_variations(formatted, n)
        except (json.JSONDecodeError, KeyError, anthropic.APIError) as e:
            print(f"  ✗ Generation error: {e}")
            continue

        inserted = 0
        for v in variations:
            # Variations inherit topic/subtopic/grade/standard from anchor
            v_full = {**formatted, **v}
            v_id = insert_question(v_full, is_anchor=0)
            print(f"  ✓ Added variation: {v_id}  |  {v.get('question', '')[:60]}...")
            inserted += 1

        print(f"\n  Done — 1 anchor + {inserted} variations added.\n")


if __name__ == "__main__":
    main()
