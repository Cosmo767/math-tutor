# math-tutor

An adaptive math tutorial website for California middle and high school students.
Quizzes, performance tracking, and ML-driven topic recommendations.

## Project Status
**Phase 1 — Question Bank** (in progress)

## Context Docs
- [`context/project-overview.md`](context/project-overview.md) — what this is, tech stack, phases, data models
- [`context/ai-guidelines.md`](context/ai-guidelines.md) — how to work with AI tools on this project
- [`context/coding-standards.md`](context/coding-standards.md) — code style and patterns
- [`context/current-feature.md`](context/current-feature.md) — active feature being built
- [`context/feature-history.md`](context/feature-history.md) — completed features log

## Setup

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/math-tutor
cd math-tutor

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate      # Windows
source venv/bin/activate   # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# Initialize the database
python question_bank/scripts/setup_db.py
```

## Phases
1. **Question Bank** ← current
2. Quiz Website (frontend)
3. Backend API
4. ML Model
5. Adaptive Quiz Engine
