"""
qc_questions.py

Automated QC pipeline for the question bank.
Sends each question to Claude to check for correctness, clarity,
difficulty accuracy, and distractor quality.

Verdicts:
  approved — question is correct and well-formed, no changes needed
  revised  — fixable issues found; corrected fields applied to questions table
  rejected — fundamentally flawed (bad answer with no clean fix, misleading)

Results are logged to qc_log. Revised questions are updated in place.

Usage:
    python3 question_bank/scripts/qc_questions.py             # QC all unreviewed questions
    python3 question_bank/scripts/qc_questions.py --all       # re-QC everything
    python3 question_bank/scripts/qc_questions.py --topic circles
    python3 question_bank/scripts/qc_questions.py --dry-run   # print results, no DB writes
"""
from __future__ import annotations

import anthropic
import sqlite3
import json
import re
import os
import sys
import time
import argparse
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

DIFFICULTY_DEFS = """
- easy: single step, standard numbers, tests one concept directly
- medium: two steps, or one concept applied in a slightly unfamiliar way
- hard: multi-step, connects two concepts, requires non-obvious setup
"""

QC_SYSTEM = f"""You are an expert California high school geometry teacher \
performing quality control on a question bank.

IMPORTANT — distractors format:
For multiple_choice questions, the "distractors" array contains ALL FOUR answer choices
shown to the student, including the correct answer. This is intentional — do NOT flag
the correct answer appearing in the distractors array as an error. Only flag if the
correct answer appears MORE THAN ONCE in the distractors array (a true duplicate),
or if there are fewer than 4 total choices.

Review each question for:
1. Mathematical correctness — is the stated answer definitely correct?
2. Difficulty match — does the question fit the stated difficulty level?
3. Format validity — multiple_choice must have exactly 4 items in distractors (including \
the correct answer once); numeric_input must have empty distractors []
4. Distractor quality — the 3 wrong choices must be plausible (real student errors), \
not obviously wrong or trivially different from the correct answer
5. Clarity — unambiguous, appropriate for the stated grade level

Difficulty definitions:{DIFFICULTY_DEFS}
Respond ONLY in valid JSON, no preamble:
{{
  "verdict": "approved|revised|rejected",
  "issues": ["specific problem 1", "specific problem 2"],
  "reasoning": "one sentence",
  "revised": {{
    "question": "...",
    "answer": "...",
    "distractors": ["correct", "wrong1", "wrong2", "wrong3"],
    "common_errors": ["wrong1", "wrong2"],
    "difficulty": "easy|medium|hard"
  }}
}}

Only include fields in "revised" that actually need changing.
Omit the "revised" key entirely for approved or rejected verdicts."""


def build_qc_prompt(q: dict) -> str:
    return f"""Review this geometry question:

Topic:      {q['topic']} → {q['subtopic']}
Grade:      {q['grade_band']} / level {q['grade_level']}
Difficulty: {q['difficulty']}
Standard:   {q['ca_standard']}
Format:     {q['format']}

Question:      {q['question']}
Answer:        {q['answer']}
Distractors:   {q['distractors']}
Common errors: {q['common_errors']}"""


def qc_question(q: dict) -> dict:
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=QC_SYSTEM,
        messages=[{"role": "user", "content": build_qc_prompt(q)}]
    )
    if not response.content:
        raise json.JSONDecodeError("Empty response from API", "", 0)
    raw = response.content[0].text.strip()
    raw = re.sub(r'^```json\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    if not raw:
        raise json.JSONDecodeError("Empty text after stripping", "", 0)
    # Claude sometimes wraps JSON in reasoning text (before or after).
    # raw_decode() parses exactly the first valid JSON object and stops —
    # it doesn't fail on trailing text the way json.loads() does.
    start = raw.find('{')
    if start == -1:
        raise json.JSONDecodeError(f"No JSON object found | raw={raw[:200]!r}", "", 0)
    try:
        obj, _ = json.JSONDecoder().raw_decode(raw, start)
        return obj
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"{e.msg} | raw={raw[:300]!r}", e.doc, e.pos)


def load_questions(conn: sqlite3.Connection, topic: str | None, qc_all: bool) -> list[dict]:
    if qc_all:
        query  = "SELECT q.* FROM questions q"
        where  = []
        params: list = []
    else:
        query  = """
            SELECT q.* FROM questions q
            LEFT JOIN qc_log l ON q.id = l.question_id
            WHERE l.question_id IS NULL
        """
        where  = []
        params = []

    if topic:
        clause = "q.topic = ?"
        if "WHERE" in query:
            query += f" AND {clause}"
        else:
            query += f" WHERE {clause}"
        params.append(topic)

    query += " ORDER BY q.topic, q.difficulty"
    rows = conn.execute(query, params).fetchall()
    questions = []
    for row in rows:
        q = dict(row)
        q["distractors"]   = json.loads(q.get("distractors")   or "[]")
        q["common_errors"] = json.loads(q.get("common_errors") or "[]")
        questions.append(q)
    return questions


def apply_revision(conn: sqlite3.Connection, q_id: str, revised: dict) -> None:
    """Update only the fields Claude flagged as needing correction."""
    update_fields: list[str] = []
    update_vals:   list      = []

    for field in ("question", "answer", "difficulty"):
        if field in revised:
            update_fields.append(f"{field} = ?")
            update_vals.append(revised[field])

    for field in ("distractors", "common_errors"):
        if field in revised:
            update_fields.append(f"{field} = ?")
            update_vals.append(json.dumps(revised[field]))

    if update_fields:
        update_vals.append(q_id)
        conn.execute(
            f"UPDATE questions SET {', '.join(update_fields)} WHERE id = ?",
            update_vals
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="QC the question bank via Claude")
    parser.add_argument("--topic",   help="Filter to a specific topic")
    parser.add_argument("--all",     action="store_true", help="Re-QC already-reviewed questions too")
    parser.add_argument("--dry-run", action="store_true", help="Print results without writing to DB")
    args = parser.parse_args()

    if not os.path.exists(DB_PATH):
        print("✗ Database not found. Run setup_db.py first.")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    questions = load_questions(conn, args.topic, args.all)

    if not questions:
        print("No questions to QC (all already reviewed — use --all to re-check).")
        conn.close()
        return

    dry = args.dry_run
    print(f"QC-ing {len(questions)} questions{' (dry run)' if dry else ''}...\n")

    now                    = datetime.now().isoformat()
    approved = rejected = revised = errors = 0

    for i, q in enumerate(questions, 1):
        label = f"[{i:03d}/{len(questions):03d}] {q['id']}"
        try:
            result  = qc_question(q)
            verdict = result.get("verdict", "rejected")
            issues  = result.get("issues", [])

            symbol = {"approved": "✓", "revised": "~", "rejected": "✗"}.get(verdict, "?")
            print(f"  {symbol} {label} → {verdict}")
            for issue in issues:
                print(f"      • {issue}")

            if not dry:
                conn.execute(
                    "INSERT INTO qc_log (question_id, verdict, issues, checked_at) VALUES (?, ?, ?, ?)",
                    (q["id"], verdict, json.dumps(issues), now)
                )
                if verdict == "revised" and "revised" in result:
                    apply_revision(conn, q["id"], result["revised"])
                conn.commit()

            if verdict == "approved":   approved += 1
            elif verdict == "rejected": rejected += 1
            else:                       revised  += 1

        except json.JSONDecodeError as e:
            print(f"  ? {label} → JSON parse error: {e}")
            # Show the raw DB question so we can spot what's causing it
            print(f"      question text: {q.get('question', '')[:120]!r}")
            errors += 1
        except KeyError as e:
            print(f"  ? {label} → missing field: {e}")
            errors += 1
        except anthropic.APIError as e:
            print(f"  ? {label} → API error: {e}")
            errors += 1

        time.sleep(0.3)

    conn.close()

    print(f"\n{'='*52}")
    print(f"Total:    {len(questions)}")
    print(f"Approved: {approved}")
    print(f"Revised:  {revised}  ← updated in questions table")
    print(f"Rejected: {rejected}  ← logged, not deleted")
    print(f"Errors:   {errors}")
    if dry:
        print("\n(dry run — no changes written to DB)")
    if rejected > len(questions) * 0.3:
        print("\n⚠ >30% rejected — review prompts or generation settings before continuing.")


if __name__ == "__main__":
    main()
