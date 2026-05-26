# math-tutor — Project Overview

> An adaptive math tutorial website targeting California middle and high school students,
> with a question bank, quiz engine, and ML-driven topic recommendations.

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Target Users](#2-target-users)
3. [Tech Stack](#3-tech-stack)
4. [Project Phases](#4-project-phases)
5. [Data Models](#5-data-models)
6. [Question Bank Structure](#6-question-bank-structure)
7. [ML Model Plan](#7-ml-model-plan)
8. [UI/UX Guidelines](#8-uiux-guidelines)
9. [Key Routes](#9-key-routes)
10. [Frontend Decision — Pending](#10-frontend-decision--pending)

---

## 1. Problem Statement

Students learning math need feedback that goes beyond a score. They need to know
*which specific concepts* they are struggling with and *what to review next* — without
waiting for a teacher to diagnose it manually.

**math-tutor** provides:
- Short, targeted quizzes organized by topic and grade level
- Automatic scoring and performance tracking
- ML-driven recommendations for what to review next
- Eventually: adaptive questioning that adjusts difficulty in real time

---

## 2. Target Users

| User | Need |
|---|---|
| **Middle school student (6–8)** | Practice geometry, fractions, ratios, early algebra |
| **High school student (9–10)** | Practice algebra, geometry, trig, unit circle |
| **Teacher / Instructor** | Assign quizzes, view student performance by standard |

California math standards (CA CCSS) are the reference framework for all content.

---

## 3. Tech Stack

| Layer | Technology | Status |
|---|---|---|
| **Question bank scripts** | Python 3 | ✅ decided |
| **Question generation** | Anthropic API (`claude-sonnet-4-6`) | ✅ decided |
| **Database** | SQLite (dev) → PostgreSQL (prod) | ✅ decided |
| **Backend / API** | Python + Flask | ✅ decided |
| **ML model** | scikit-learn | ✅ decided |
| **Frontend** | ⚠️ TBD — see [Section 10](#10-frontend-decision--pending) | ❌ pending |
| **Auth** | TBD | ❌ pending |
| **Hosting** | TBD | ❌ pending |

---

## 4. Project Phases

### Phase 1 — Question Bank ✅ complete (anchor set)
- ✅ Design and finalize question schema
- ✅ `generate_anchors.py` — 108 HS geometry anchor questions across 12 domains
- ✅ `seed_anchors.py` — imports any CSV into SQLite (accepts optional path arg)
- ✅ 118 questions total in DB (108 HS + 10 middle school)
- ⬜ Automated QC pipeline (`qc_questions.py`)
- ⬜ Bulk question generation beyond anchor set (`generate_questions.py`)

### Phase 2 — Quiz Website (Frontend) ✅ v1 live
- ✅ `frontend/index.html` — SPA served by Flask at `http://localhost:8000/`
- ✅ Login, topic dashboard with score bars, adaptive quiz, results screen
- ✅ Session persisted in `sessionStorage` (survives page refresh)
- ✅ `seed_demo_student.py` — seeds fake scores for UI testing
- ⬜ Teacher/instructor view
- ⬜ Auth (login with real accounts)

### Phase 3 — Backend API ✅ complete
- ✅ Flask app with blueprint routing, served on port 8000
- ✅ `/api/quiz/build` — adaptive quiz builder (weakness-focused or custom)
- ✅ `/api/quiz/submit` — scores answers, updates `student_performance`
- ✅ `/api/students/:id/topics` — nested performance map (topic/subtopic/difficulty)
- ✅ `/api/students/:id/create` — upsert student record
- ✅ `/api/recommend` endpoints (non-streaming + SSE streaming)

### Phase 4 — ML Model ✅ trained and live
- ✅ 100 simulated students generated via Claude API (10 archetypes × 10)
- ✅ SGDClassifier trained — 98% CV accuracy across 10 topics
- ✅ Model active — switches automatically after 10 real student sessions
- ✅ `partial_fit()` updates model incrementally after each real session

### Phase 5 — Adaptive Quiz Engine
- Use difficulty tags already on questions to route adaptively
- Replace fixed question order with model-guided selection
- Compare adaptive vs. rule-based recommendations

---

## 5. Data Models

### questions table
```
id                  TEXT PRIMARY KEY     -- e.g. geo_tri_ms_med_001
topic               TEXT                 -- e.g. triangles
subtopic            TEXT                 -- e.g. angle_sum
grade_band          TEXT                 -- middle | high
grade_level         INTEGER              -- 6, 7, 8, 9, 10
difficulty          TEXT                 -- easy | medium | hard
ca_standard         TEXT                 -- e.g. 8.G.A.5
format              TEXT                 -- multiple_choice | numeric_input
question            TEXT
answer              TEXT
common_errors       TEXT                 -- JSON array of wrong answers
distractors         TEXT                 -- JSON array (for multiple choice)
is_anchor           INTEGER              -- 1 if manually entered anchor question
created_at          TEXT
```

### student_results table
```
id                  INTEGER PRIMARY KEY AUTOINCREMENT
student_id          TEXT NOT NULL
session_id          TEXT NOT NULL          -- groups all questions from one quiz sitting
question_id         TEXT NOT NULL
topic               TEXT NOT NULL          -- denormalized from questions for faster queries
answer_given        TEXT
is_correct          INTEGER NOT NULL DEFAULT 0
time_spent_seconds  INTEGER
is_simulated        INTEGER NOT NULL DEFAULT 0   -- 0 = real, 1 = Claude-generated training data
created_at          TEXT
```

### students table
```
id                              TEXT PRIMARY KEY
name                            TEXT
grade_level                     INTEGER
show_claude_recommendation      INTEGER NOT NULL DEFAULT 1   -- persists Claude toggle preference
created_at                      TEXT
```

### student_topic_history table
```
student_id    TEXT NOT NULL
topic         TEXT NOT NULL
sessions      INTEGER          -- total quiz sessions on this topic
avg_score     REAL             -- rolling average (0.0–1.0)
last_score    REAL
trend         REAL             -- positive = improving, negative = declining
updated_at    TEXT
PRIMARY KEY (student_id, topic)
```

### qc_log table
```
id            INTEGER PRIMARY KEY AUTOINCREMENT
question_id   TEXT
verdict       TEXT             -- approved | rejected | revised
issues        TEXT
checked_at    TEXT
```

---

## 6. Question Bank Structure

### Topics — HS Geometry (current focus)
| Topic | Key Subtopics | Grade Level | CA Standard |
|---|---|---|---|
| triangle_congruence | SSS/SAS/ASA/AAS, CPCTC | 9 | HSG.CO.B.8 |
| similarity | AA/SAS/SSS, scale factor, proportions | 9 | HSG.SRT.A.3 |
| transformations | reflections, rotations, translations, dilations | 9 | HSG.CO.A.2 |
| pythagorean_theorem | find hypotenuse/leg, converse, real world | 9 | HSG.SRT.B.4 |
| special_right_triangles | 30-60-90, 45-45-90 | 9 | HSG.SRT.C.6 |
| soh_cah_toa | find side/angle, inverse trig, word problems | 9 | HSG.SRT.C.6 |
| unit_circle | radian/degree, exact trig values, reference angles | 10 | HSF.TF.A.2 |
| circles | arc length, sector area, inscribed/central angles | 10 | HSG.C.A.2 |
| coordinate_geometry | distance, midpoint, slope, parallel/perpendicular | 10 | HSG.GPE.B.4 |
| area_and_volume | polygon/circle area, surface area, volume | 10 | HSG.GMD.A.3 |
| angle_relationships | parallel lines/transversals, polygon angles | 9 | HSG.CO.C.9 |
| proofs_and_reasoning | two-column proofs, paragraph proofs, properties | 10 | HSG.CO.C.9 |

Note: The ML model tracks 10 topics (excludes `transformations` and `proofs_and_reasoning`).

### Difficulty definitions
These definitions are used in every generation prompt — do not change without updating prompts.

- **easy** — single step, standard numbers, tests one concept directly
- **medium** — two steps, or one concept applied in a slightly unfamiliar way
- **hard** — multi-step, connects two concepts, or requires non-obvious setup

### Question bank — anchor set (generated by `generate_anchors.py`)
9 questions per topic (3 per difficulty) × 12 topics = **108 anchor questions**
These seed the database. Bulk generation expands to ~30 per topic.

---

## 7. ML Model Plan

### Model: SGDClassifier (scikit-learn)
Chosen because `partial_fit()` allows incremental updates as real students take quizzes — no full retraining needed. Also trains a DecisionTree in parallel for inspection only.

### Training data strategy
1. ✅ `simulate_students.py` — generates synthetic data via Claude (10 archetypes × N students)
2. ✅ `train_model.py` — trains model, saves `recommender.pkl` + `model_meta.pkl`
3. Model activates after **10 real student sessions**; below that threshold, Claude handles all recommendations
4. `update_model()` in `recommender.py` calls `partial_fit()` after each confirmed session

### Feature vector (per student)
```
[triangle_congruence, similarity, pythagorean_theorem, special_right_triangles,
 soh_cah_toa, unit_circle, circles, coordinate_geometry, area_and_volume, angle_relationships]
```
Each value is a score 0.0–1.0 for that topic.

### Prediction target
```
weak_topic: one of the 10 topics above
```

---

## 8. UI/UX Guidelines

- Clean, uncluttered, student-friendly
- Mobile-first (students use phones)
- Clear feedback after each question — not just right/wrong, but *why*
- Progress visible at all times (topic coverage, score by topic)
- No login required for basic quiz (Phase 2); login added in Phase 3

---

## 9. Key Routes

### Built (`backend/routes/recommendations.py`)
| Route | Description |
|---|---|
| `GET /health` | Server health check |
| `GET /api/status` | Active method (claude vs model), session counts |
| `POST /api/recommend` | Single recommendation, JSON response |
| `GET /api/recommend/stream` | Dual SSE stream — model result first, then Claude streams |
| `POST /api/recommend/toggle-claude` | Save student's Claude preference to DB |
| `POST /api/update` | Incremental model update after a confirmed session |

### Planned (Phase 3 completion)
| Route | Description |
|---|---|
| `GET /api/questions` | Fetch questions (filterable by topic, grade, difficulty) |
| `POST /api/results` | Submit quiz results |
| `GET /api/students/:id/performance` | Performance summary by topic |

---

## 10. Frontend Decision — Pending

### Options under consideration

| Option | Pros | Cons |
|---|---|---|
| **Plain HTML/CSS/JS** | No build step, fast to start, easy to host | Gets messy at scale, no component reuse |
| **React (Vite)** | Component model, good for quiz UI, large ecosystem | Build step, more setup |
| **Next.js + TypeScript** | SSR, API routes built in, scales well | Most complex setup, overkill for early phases |

### Decision criteria
- If frontend stays simple (static quiz pages, no auth) → Plain HTML or React/Vite
- If we add auth, dashboards, teacher views → Next.js makes more sense
- **Decision should be made before Phase 2 begins**

---

*Last updated: May 2026*
