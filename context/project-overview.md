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
| **Question generation** | Anthropic API (`claude-sonnet-4-20250514`) | ✅ decided |
| **Database** | SQLite (dev) → PostgreSQL (prod) | ✅ decided |
| **Backend / API** | Python + Flask | ✅ decided |
| **ML model** | scikit-learn | ✅ decided |
| **Frontend** | ⚠️ TBD — see [Section 10](#10-frontend-decision--pending) | ❌ pending |
| **Auth** | TBD | ❌ pending |
| **Hosting** | TBD | ❌ pending |

---

## 4. Project Phases

### Phase 1 — Question Bank ← YOU ARE HERE
- Design and finalize question schema
- Manually enter anchor questions (geometry first)
- Build Claude API generation pipeline
- Build automated QC pipeline
- Store all questions in SQLite

### Phase 2 — Quiz Website (Frontend)
- Serve questions to students
- Handle multiple choice and numeric input formats
- Display score and basic feedback by topic
- No backend required yet — can run off static files

### Phase 3 — Backend API
- Flask API serves questions and receives quiz submissions
- Saves student results to database
- Student performance tracked by topic and standard

### Phase 4 — ML Model
- Generate simulated student data (via Claude API)
- Train scikit-learn classifier to predict struggling topics
- Expose predictions via Flask endpoint

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

### student_results table (Phase 3)
```
id                  INTEGER PRIMARY KEY
student_id          TEXT
question_id         TEXT
answer_given        TEXT
is_correct          INTEGER
time_spent_seconds  INTEGER
created_at          TEXT
```

### students table (Phase 3)
```
id                  TEXT PRIMARY KEY
name                TEXT
grade_level         INTEGER
created_at          TEXT
```

---

## 6. Question Bank Structure

### Topics (geometry first, expanding later)
| Topic | Subtopics | Grade Band | CA Standards |
|---|---|---|---|
| triangles | angle_sum, triangle_types, exterior_angles | middle | 8.G.A.5 |
| pythagorean_theorem | find_hypotenuse, find_leg, real_world | middle/high | 8.G.B.7, 8.G.B.8 |
| soh_cah_toa | find_side, find_angle, word_problems | high | HSG.SRT.C.6 |
| unit_circle | radian_degree, trig_values, quadrants | high | HSF.TF.A.2 |

### Difficulty definitions
These definitions are used in every generation prompt — do not change without updating prompts.

- **easy** — single step, standard numbers, tests one concept directly
- **medium** — two steps, or one concept applied in a slightly unfamiliar way
- **hard** — multi-step, connects two concepts, or requires non-obvious setup

### Question bank targets
| Topic | Easy | Medium | Hard | Total |
|---|---|---|---|---|
| triangles | 10 | 10 | 10 | 30 |
| pythagorean_theorem | 10 | 10 | 10 | 30 |
| soh_cah_toa | 10 | 10 | 10 | 30 |
| unit_circle | 10 | 10 | 10 | 30 |
| **Total** | | | | **120** |

---

## 7. ML Model Plan

### Training data strategy
1. Build question bank (Phase 1)
2. Write student simulation script using Claude API
3. Generate ~300–500 synthetic student result rows
4. Add noise to simulate realistic inconsistency
5. Train initial decision tree / logistic regression in scikit-learn
6. Validate against rule-based baseline
7. Retrain as real student data accumulates

### Feature vector (per student, per session)
```
[triangles_score, pythagorean_score, soh_cah_toa_score, unit_circle_score,
 avg_time_per_question, total_attempts]
```

### Prediction target
```
struggling_topic: "triangles" | "pythagorean_theorem" | "soh_cah_toa" | "unit_circle"
```

---

## 8. UI/UX Guidelines

- Clean, uncluttered, student-friendly
- Mobile-first (students use phones)
- Clear feedback after each question — not just right/wrong, but *why*
- Progress visible at all times (topic coverage, score by topic)
- No login required for basic quiz (Phase 2); login added in Phase 3

---

## 9. Key Routes (Phase 3+)

| Route | Description |
|---|---|
| `GET /api/questions` | Fetch questions (filterable by topic, grade, difficulty) |
| `POST /api/results` | Submit a quiz result |
| `GET /api/students/:id/performance` | Get performance summary by topic |
| `GET /api/recommend/:student_id` | Get ML topic recommendation |

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
