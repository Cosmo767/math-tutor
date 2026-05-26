# math-tutor

An adaptive math tutoring app for California middle/high school students — question bank, quiz engine, and ML-driven topic recommendations.

## Context Files

Read the following to get the full context of the project:

- @context/project-overview.md
- @context/coding-standards.md
- @context/ai-guidelines.md
- @context/current-feature.md

## Commands

```bash
# Backend
python backend/app.py                          # start Flask server (localhost:5000)

# Question bank
python question_bank/scripts/setup_db.py       # initialize SQLite database
python question_bank/scripts/seed_anchors.py   # import anchor questions from CSV
python question_bank/scripts/generate_anchors.py

# ML pipeline
python ml/simulate_students.py                 # generate synthetic training data
python ml/train_model.py                       # train SGDClassifier
python ml/recommender.py                       # test recommender directly

# Tests
pytest                                         # run test suite
```
