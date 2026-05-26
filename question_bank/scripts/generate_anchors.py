"""
generate_anchors.py
One-time script to generate a robust HS geometry anchor question set.
Writes to question_bank/data/anchors_hs_geometry.csv

Usage:
    python question_bank/scripts/generate_anchors.py

Requires:
    ANTHROPIC_API_KEY in .env file
"""

import anthropic
import json
import csv
import time
import re
import os
import sys
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not API_KEY:
    print("✗ ANTHROPIC_API_KEY not found. Add it to your .env file.")
    sys.exit(1)

client = anthropic.Anthropic(api_key=API_KEY)

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "anchors_hs_geometry.csv")

DOMAINS = [
    {
        "topic": "triangle_congruence",
        "subtopics": ["sss_sas_asa_aas", "cpctc", "identifying_congruence"],
        "grade_band": "high", "grade_level": 9,
        "ca_standard": "HSG.CO.B.8",
        "description": "Triangle congruence postulates SSS, SAS, ASA, AAS and CPCTC"
    },
    {
        "topic": "similarity",
        "subtopics": ["similar_triangles", "scale_factor", "proportional_sides", "aa_similarity"],
        "grade_band": "high", "grade_level": 9,
        "ca_standard": "HSG.SRT.A.3",
        "description": "Similar triangles, AA/SAS/SSS similarity, scale factor, proportional sides"
    },
    {
        "topic": "transformations",
        "subtopics": ["reflections", "rotations", "translations", "dilations"],
        "grade_band": "high", "grade_level": 9,
        "ca_standard": "HSG.CO.A.2",
        "description": "Rigid transformations and dilations on the coordinate plane"
    },
    {
        "topic": "pythagorean_theorem",
        "subtopics": ["find_hypotenuse", "find_leg", "real_world", "converse"],
        "grade_band": "high", "grade_level": 9,
        "ca_standard": "HSG.SRT.B.4",
        "description": "Pythagorean theorem and its converse, real world applications"
    },
    {
        "topic": "special_right_triangles",
        "subtopics": ["30_60_90", "45_45_90", "mixed"],
        "grade_band": "high", "grade_level": 9,
        "ca_standard": "HSG.SRT.C.6",
        "description": "30-60-90 and 45-45-90 special right triangle side relationships"
    },
    {
        "topic": "soh_cah_toa",
        "subtopics": ["find_side", "find_angle", "word_problems", "inverse_trig"],
        "grade_band": "high", "grade_level": 9,
        "ca_standard": "HSG.SRT.C.6",
        "description": "SOH CAH TOA, finding sides and angles, inverse trig functions"
    },
    {
        "topic": "unit_circle",
        "subtopics": ["radian_degree_conversion", "trig_values", "quadrants", "reference_angles"],
        "grade_band": "high", "grade_level": 10,
        "ca_standard": "HSF.TF.A.2",
        "description": "Unit circle, radian/degree conversion, exact trig values, reference angles"
    },
    {
        "topic": "circles",
        "subtopics": ["arc_length", "sector_area", "inscribed_angles", "central_angles", "chords_tangents"],
        "grade_band": "high", "grade_level": 10,
        "ca_standard": "HSG.C.A.2",
        "description": "Arc length, sector area, inscribed and central angles, chords, tangents"
    },
    {
        "topic": "coordinate_geometry",
        "subtopics": ["distance_formula", "midpoint_formula", "slope", "parallel_perpendicular"],
        "grade_band": "high", "grade_level": 10,
        "ca_standard": "HSG.GPE.B.4",
        "description": "Distance, midpoint, slope, parallel and perpendicular lines on coordinate plane"
    },
    {
        "topic": "area_and_volume",
        "subtopics": ["polygon_area", "circle_area", "surface_area", "volume_prisms_cylinders", "volume_pyramids_cones"],
        "grade_band": "high", "grade_level": 10,
        "ca_standard": "HSG.GMD.A.3",
        "description": "Area of polygons and circles, surface area and volume of 3D figures"
    },
    {
        "topic": "angle_relationships",
        "subtopics": ["parallel_lines_transversal", "polygon_interior_angles", "exterior_angles", "vertical_supplementary"],
        "grade_band": "high", "grade_level": 9,
        "ca_standard": "HSG.CO.C.9",
        "description": "Angle relationships: parallel lines, transversals, polygon angles, vertical/supplementary"
    },
    {
        "topic": "proofs_and_reasoning",
        "subtopics": ["two_column_proof", "paragraph_proof", "identifying_properties"],
        "grade_band": "high", "grade_level": 10,
        "ca_standard": "HSG.CO.C.9",
        "description": "Geometric proofs, reasoning, properties of congruence and equality"
    },
]

DIFFICULTY_DEFS = """
- easy: single step, standard numbers, tests one concept directly, no multi-step reasoning
- medium: two steps, or one concept applied in a slightly unfamiliar way, moderate numbers
- hard: multi-step, connects two concepts, requires non-obvious setup or algebraic manipulation
"""

FIELDNAMES = [
    "id", "topic", "subtopic", "grade_band", "grade_level", "difficulty",
    "ca_standard", "format", "question", "answer", "common_errors",
    "distractors", "is_anchor"
]


def build_prompt(domain: dict, n_per_difficulty: int) -> str:
    return f"""You are an expert California high school geometry teacher writing a question bank.

Generate {n_per_difficulty} questions at EACH difficulty level (easy, medium, hard) for a total of {n_per_difficulty * 3} questions.

DOMAIN: {domain['description']}
Topic: {domain['topic']}
Grade level: {domain['grade_level']}
CA Standard: {domain['ca_standard']}
Subtopics to cover (vary across questions, max 2 per subtopic): {', '.join(domain['subtopics'])}

DIFFICULTY DEFINITIONS:
{DIFFICULTY_DEFS}

FORMAT RULES:
- Use multiple_choice for: conceptual questions, definitions, identifying properties, proof steps
- Use numeric_input for: calculation questions with a clean numerical or expression answer
- multiple_choice: distractors array must have exactly 4 items including the correct answer
- numeric_input: distractors must be empty []
- common_errors: 2-3 realistic wrong answers based on actual student misconceptions
- Language must be clear and grade-appropriate

Respond ONLY in valid JSON, no preamble, no markdown backticks:
{{
  "questions": [
    {{
      "subtopic": "subtopic_name",
      "difficulty": "easy|medium|hard",
      "format": "multiple_choice|numeric_input",
      "question": "full question text",
      "answer": "correct answer",
      "common_errors": ["wrong1", "wrong2"],
      "distractors": ["correct", "wrong1", "wrong2", "wrong3"],
      "difficulty_justification": "one sentence"
    }}
  ]
}}"""


def generate_for_domain(domain: dict, n_per_difficulty: int = 3) -> list[dict]:
    print(f"  Calling API...")
    prompt = build_prompt(domain, n_per_difficulty)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text.strip()
    raw = re.sub(r'^```json\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)

    data = json.loads(raw)
    questions = data["questions"]
    print(f"  ✓ {len(questions)} questions received")
    return questions


def make_id(topic: str, subtopic: str, difficulty: str, index: int) -> str:
    t = topic[:6].replace('_', '')
    s = subtopic[:6].replace('_', '')
    d = difficulty[:3]
    return f"{t}_{s}_hs_{d}_{index:03d}"


def main() -> None:
    all_rows: list[dict] = []
    counters: dict[str, int] = {}
    errors: list[str] = []

    print(f"Generating HS geometry anchor questions across {len(DOMAINS)} domains...\n")

    for domain in DOMAINS:
        print(f"→ {domain['topic']}")
        try:
            questions = generate_for_domain(domain, n_per_difficulty=3)

            for q in questions:
                key = f"{domain['topic']}_{q.get('subtopic', 'general')}_{q['difficulty']}"
                counters[key] = counters.get(key, 0) + 1
                idx = counters[key]

                row = {
                    "id": make_id(domain["topic"], q.get("subtopic", "general"), q["difficulty"], idx),
                    "topic": domain["topic"],
                    "subtopic": q.get("subtopic", "general"),
                    "grade_band": domain["grade_band"],
                    "grade_level": domain["grade_level"],
                    "difficulty": q["difficulty"],
                    "ca_standard": domain["ca_standard"],
                    "format": q["format"],
                    "question": q["question"],
                    "answer": q["answer"],
                    "common_errors": json.dumps(q.get("common_errors", [])),
                    "distractors": json.dumps(q.get("distractors", [])),
                    "is_anchor": 1
                }
                all_rows.append(row)

            time.sleep(1)

        except json.JSONDecodeError as e:
            msg = f"JSON parse error on {domain['topic']}: {e}"
            print(f"  ✗ {msg}")
            errors.append(msg)
        except KeyError as e:
            msg = f"Missing field on {domain['topic']}: {e}"
            print(f"  ✗ {msg}")
            errors.append(msg)
        except anthropic.APIError as e:
            msg = f"API error on {domain['topic']}: {e}"
            print(f"  ✗ {msg}")
            errors.append(msg)

    # write CSV
    out_path = os.path.abspath(OUT_PATH)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(all_rows)

    # summary
    print(f"\n{'='*50}")
    print(f"Total questions generated: {len(all_rows)}")
    print(f"Saved to: {out_path}")

    print("\nBreakdown by topic:")
    topic_counts: dict[str, int] = {}
    for row in all_rows:
        topic_counts[row["topic"]] = topic_counts.get(row["topic"], 0) + 1
    for topic, count in sorted(topic_counts.items()):
        print(f"  {topic}: {count}")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors:
            print(f"  ✗ {e}")
    else:
        print("\n✓ No errors")


if __name__ == "__main__":
    main()
