-- math-tutor question bank schema
-- Version: 001
-- Run via: python question_bank/scripts/setup_db.py

CREATE TABLE IF NOT EXISTS questions (
    id                TEXT PRIMARY KEY,
    topic             TEXT NOT NULL,
    subtopic          TEXT NOT NULL,
    grade_band        TEXT NOT NULL CHECK (grade_band IN ('middle', 'high')),
    grade_level       INTEGER NOT NULL,
    difficulty        TEXT NOT NULL CHECK (difficulty IN ('easy', 'medium', 'hard')),
    ca_standard       TEXT NOT NULL,
    format            TEXT NOT NULL CHECK (format IN ('multiple_choice', 'numeric_input')),
    question          TEXT NOT NULL,
    answer            TEXT NOT NULL,
    common_errors     TEXT NOT NULL DEFAULT '[]',  -- JSON array
    distractors       TEXT NOT NULL DEFAULT '[]',  -- JSON array (multiple choice options)
    is_anchor         INTEGER NOT NULL DEFAULT 0,   -- 1 if manually entered
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS qc_log (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id       TEXT,
    verdict           TEXT NOT NULL,  -- approved | rejected | revised
    issues            TEXT,
    checked_at        TEXT NOT NULL DEFAULT (datetime('now'))
);
