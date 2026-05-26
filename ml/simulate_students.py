"""
simulate_students.py

Generates synthetic student quiz performance data using Claude as a student simulator.
This is our training data source until enough real student sessions accumulate.

Why simulate instead of just using rules?
  Rules like "if circles < 0.6 → recommend circles" are obvious.
  Claude adds realistic noise and correlations — e.g. students weak in circles
  are often also weak in arc length and sector area, but not necessarily trig.
  That correlation structure is what the ML model needs to learn.

Output: ml/data/simulated_students.csv
"""

import anthropic
import json
import csv
import os
import re
import sys
import time
import random
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not API_KEY:
    print("✗ ANTHROPIC_API_KEY not found in .env")
    sys.exit(1)

client = anthropic.Anthropic(api_key=API_KEY)

OUT_PATH = os.path.join(os.path.dirname(__file__), "data", "simulated_students.csv")

# These are the features our model will train on.
# Each topic maps to a score between 0.0 and 1.0.
# When we add more topics later, add them here and retrain.
TOPICS = [
    "triangle_congruence",
    "similarity",
    "pythagorean_theorem",
    "special_right_triangles",
    "soh_cah_toa",
    "unit_circle",
    "circles",
    "coordinate_geometry",
    "area_and_volume",
    "angle_relationships",
]

# Archetypes define the "personality" of each simulated student.
# Each archetype has primary weak areas and relative strengths.
# We generate multiple students per archetype with slight variations
# so the model learns the pattern, not just a single data point.
ARCHETYPES = [
    {"weak": ["circles", "unit_circle"],           "strong": ["pythagorean_theorem", "similarity"],      "label": "circles"},
    {"weak": ["soh_cah_toa", "special_right_triangles"], "strong": ["angle_relationships", "similarity"], "label": "soh_cah_toa"},
    {"weak": ["coordinate_geometry"],              "strong": ["pythagorean_theorem", "triangle_congruence"], "label": "coordinate_geometry"},
    {"weak": ["triangle_congruence", "similarity"],"strong": ["circles", "area_and_volume"],             "label": "triangle_congruence"},
    {"weak": ["area_and_volume"],                  "strong": ["soh_cah_toa", "angle_relationships"],     "label": "area_and_volume"},
    {"weak": ["angle_relationships"],              "strong": ["coordinate_geometry", "circles"],         "label": "angle_relationships"},
    {"weak": ["unit_circle", "soh_cah_toa"],       "strong": ["triangle_congruence", "similarity"],      "label": "unit_circle"},
    {"weak": ["pythagorean_theorem", "special_right_triangles"], "strong": ["circles", "coordinate_geometry"], "label": "pythagorean_theorem"},
    {"weak": ["similarity"],                       "strong": ["unit_circle", "soh_cah_toa"],             "label": "similarity"},
    {"weak": ["coordinate_geometry", "circles"],   "strong": ["angle_relationships", "triangle_congruence"], "label": "coordinate_geometry"},
]


def build_simulation_prompt(archetype: dict, student_num: int) -> str:
    """
    We're asking Claude to generate a realistic score profile, not to take an
    actual quiz. This is faster and cheaper than simulating full quiz sessions.
    The key is asking for realistic correlation structure, not just random scores.
    """
    return f"""You are simulating a high school geometry student (student #{student_num}).

This student's profile:
- Primary weak areas: {', '.join(archetype['weak'])}
- Relative strengths: {', '.join(archetype['strong'])}

Generate realistic quiz performance scores (0.0 to 1.0) for this student across these topics:
{json.dumps(TOPICS, indent=2)}

Rules for realism:
- Weak topics should score between 0.25 and 0.60 (with some random variation)
- Strong topics should score between 0.70 and 0.95 (with some random variation)  
- Neutral topics (neither weak nor strong) should score between 0.50 and 0.75
- Add slight noise — real students are inconsistent. A weak student still gets lucky sometimes.
- Related topics often correlate: a student weak in soh_cah_toa is often also weak in special_right_triangles
- Do NOT make scores perfectly symmetric or too clean

Respond ONLY in valid JSON, no preamble:
{{
  "scores": {{
    "triangle_congruence": 0.0,
    "similarity": 0.0,
    "pythagorean_theorem": 0.0,
    "special_right_triangles": 0.0,
    "soh_cah_toa": 0.0,
    "unit_circle": 0.0,
    "circles": 0.0,
    "coordinate_geometry": 0.0,
    "area_and_volume": 0.0,
    "angle_relationships": 0.0
  }},
  "reasoning": "one sentence describing this student's pattern"
}}"""


def simulate_student(archetype: dict, student_num: int) -> dict | None:
    """
    Each API call generates one student's score profile.
    We add a small random perturbation on top of Claude's output
    to ensure no two students are identical even from the same archetype.
    """
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            messages=[{"role": "user", "content": build_simulation_prompt(archetype, student_num)}]
        )

        raw = response.content[0].text.strip()
        raw = re.sub(r'^```json\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
        data = json.loads(raw)

        scores = data["scores"]

        # Add a small jitter on top of Claude's scores.
        # This prevents the model from memorizing exact values
        # and forces it to learn the general pattern instead.
        jitter = 0.05
        for topic in TOPICS:
            noise = random.uniform(-jitter, jitter)
            scores[topic] = round(min(1.0, max(0.0, scores[topic] + noise)), 3)

        return {
            "student_id": f"sim_{student_num:04d}",
            "archetype_label": archetype["label"],
            **scores,
            # The label is what the model learns to predict.
            # It's the topic the student most needs to review.
            "weak_topic": archetype["label"],
            "reasoning": data.get("reasoning", ""),
            "is_simulated": 1,
        }

    except (json.JSONDecodeError, KeyError, anthropic.APIError) as e:
        print(f"    ✗ Error on student {student_num}: {e}")
        return None


def main(n_per_archetype: int = 10) -> None:
    """
    Generate n_per_archetype students per archetype.
    Default 10 × 10 archetypes = 100 simulated students.
    This is enough for an initial model but more is better.
    """
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)

    fieldnames = ["student_id", "archetype_label"] + TOPICS + ["weak_topic", "reasoning", "is_simulated"]

    all_rows = []
    student_counter = 0
    errors = 0

    print(f"Simulating {n_per_archetype} students × {len(ARCHETYPES)} archetypes = {n_per_archetype * len(ARCHETYPES)} total\n")

    for archetype in ARCHETYPES:
        print(f"→ archetype: weak in {archetype['label']}")
        for i in range(n_per_archetype):
            student_counter += 1
            result = simulate_student(archetype, student_counter)
            if result:
                all_rows.append(result)
                print(f"   ✓ student {student_counter:03d} | {archetype['label']} | scores: {result[archetype['label']]:.2f} (weak topic)")
            else:
                errors += 1
            time.sleep(0.3)  # avoid rate limiting

    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\n{'='*50}")
    print(f"Generated: {len(all_rows)} students")
    print(f"Errors:    {errors}")
    print(f"Saved to:  {OUT_PATH}")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    main(n_per_archetype=n)
