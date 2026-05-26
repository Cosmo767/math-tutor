# Feature History

Completed features, earliest to latest.

---

## chore: initial project scaffolding
- **Completed:** 2026-05-25
- **Commit:** fe0a6d3
- **Summary:** Created full project structure including context docs, DB schema, question bank scripts (setup_db, seed_anchors, generate_anchors), ML pipeline (simulate_students, train_model, recommender), Flask backend with SSE streaming recommendation routes, and frontend SSE test page.

## feat: quiz and student routes + Python 3.9 fixes
- **Completed:** 2026-05-26
- **Commit:** 439ad82
- **Summary:** Added quiz.py (adaptive quiz builder, submit/scoring, performance upsert at 3 granularity levels) and students.py (create student, nested topic performance map). Added quick_add.py conversational question entry. Replaced student_topic_history with student_performance schema. Fixed Python 3.9 type hint compatibility. Port changed to 8000 (macOS AirPlay conflict on 5000). Added flask-cors.

## feat: generate HS anchor questions, train recommendation model
- **Completed:** 2026-05-26
- **Commit:** bd5309c
- **Summary:** Generated 108 HS geometry anchor questions across 12 topics via Claude API. Generated 100 simulated students, trained SGDClassifier (98% CV accuracy, 10 topics). Model now live — activates automatically after 10 real sessions. Built frontend SPA (login, dashboard, quiz, results) served by Flask at /. Added seed_demo_student.py for testing.
