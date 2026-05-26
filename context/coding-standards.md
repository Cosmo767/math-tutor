# Coding Standards

## Python (Backend + Scripts)
- Python 3.11+
- Type hints on all function signatures
- No bare `except` — always catch specific exceptions
- Functions under 50 lines where possible
- Use `snake_case` for variables, functions, files
- Use `SCREAMING_SNAKE_CASE` for constants
- Use dataclasses or TypedDict for structured data — no raw dicts for data models
- Docstrings on all public functions

## File Organization
```
math-tutor/
├── context/                    # project docs (this folder)
├── question_bank/
│   ├── db/
│   │   └── 001_initial_schema.sql   # canonical schema definition
│   ├── scripts/
│   │   ├── setup_db.py              # initialize database
│   │   ├── generate_anchors.py      # generate HS geometry anchors via Claude API
│   │   ├── seed_anchors.py          # import any anchor CSV into SQLite (accepts path arg)
│   │   ├── seed_demo_student.py     # seed fake student scores for UI testing
│   │   ├── quick_add.py             # conversational question entry via Claude API
│   │   ├── generate_questions.py    # ⬜ bulk question generation (not built yet)
│   │   └── qc_questions.py          # ⬜ automated QC pipeline (not built yet)
│   ├── data/
│   │   ├── anchors.csv              # middle school anchor questions (manually written)
│   │   └── anchors_hs_geometry.csv  # HS anchors (output of generate_anchors.py)
│   └── questions.db                 # SQLite database (gitignored)
├── backend/
│   ├── app.py                       # Flask entry point, serves frontend at /
│   └── routes/
│       ├── __init__.py
│       ├── recommendations.py       # /api/recommend, /api/status, /api/update
│       ├── quiz.py                  # /api/quiz/build, /api/quiz/submit
│       └── students.py              # /api/students/:id/create, /api/students/:id/topics
├── frontend/
│   ├── index.html              # main SPA (login, dashboard, quiz, results)
│   └── test_stream.html        # SSE dev test page
├── ml/
│   ├── simulate_students.py
│   ├── train_model.py
│   ├── recommender.py
│   ├── data/                   # populated by simulate_students.py
│   └── models/                 # populated by train_model.py
├── tests/
├── .env                        # gitignored
├── .env.example                # committed, no real values
├── CLAUDE.md                   # auto-loaded by Claude Code CLI
├── requirements.txt
└── README.md
```

## Database
- SQLite for development
- All schema changes go through versioned SQL migration files — never alter the DB manually
- Migration files named: `001_initial_schema.sql`, `002_add_column.sql`, etc.
- Always test migrations on a copy before running on the main DB

## Environment Variables
- All secrets in `.env` — never hardcoded
- `.env` is gitignored — always
- `.env.example` is committed with placeholder values
- Access via `python-dotenv`: `from dotenv import load_dotenv`

## API Calls (Anthropic)
- All Claude API calls go through a single wrapper function — never call the client directly in scripts
- Always set `max_tokens` explicitly
- Always use `try/except` around API calls
- Log failures with enough context to debug (question id, prompt summary)
- Model: `claude-sonnet-4-6`

## Question Generation
- Never hardcode question content — always generated from templates
- Every generated question must pass auto-QC before being inserted into DB
- Anchor questions (manually entered) are marked `is_anchor = 1`
- Difficulty definitions live in `context/project-overview.md` — use them verbatim in prompts

## Error Handling
- Scripts print clear status messages: what succeeded, what failed, counts
- Failed QC questions are logged to a separate file for review — not silently dropped
- If a generation run produces >30% QC failures, stop and report — don't keep running

## Naming
- DB table names: `snake_case`, plural (`questions`, `student_results`)
- Question IDs: `{topic_abbr}_{subtopic_abbr}_{grade_band}_{difficulty}_{###}`
  - Example: `tri_angsum_ms_med_001`
- Script names: verb-first (`generate_questions.py`, `setup_db.py`)

## Code Quality
- No commented-out code unless marked `# TODO:` with a reason
- No unused imports
- All scripts runnable standalone with `python script_name.py`
- Print a usage message if required args are missing
