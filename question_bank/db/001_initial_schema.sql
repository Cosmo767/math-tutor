-- math-tutor database schema
-- Version: 001
-- Run via: python question_bank/scripts/setup_db.py

-- ── Question Bank ─────────────────────────────────────────────────────────────

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
    common_errors     TEXT NOT NULL DEFAULT '[]',
    distractors       TEXT NOT NULL DEFAULT '[]',
    is_anchor         INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS qc_log (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id       TEXT,
    verdict           TEXT NOT NULL CHECK (verdict IN ('approved', 'rejected', 'revised')),
    issues            TEXT,
    checked_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ── Students ──────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS students (
    id                          TEXT PRIMARY KEY,
    name                        TEXT,
    grade_level                 INTEGER,
    show_claude_recommendation  INTEGER NOT NULL DEFAULT 1,
    created_at                  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ── Quiz Sessions ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS student_results (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id          TEXT NOT NULL,
    session_id          TEXT NOT NULL,
    question_id         TEXT NOT NULL,
    topic               TEXT NOT NULL,
    subtopic            TEXT NOT NULL,
    difficulty          TEXT NOT NULL,
    answer_given        TEXT,
    is_correct          INTEGER NOT NULL DEFAULT 0,
    time_spent_seconds  INTEGER,
    is_simulated        INTEGER NOT NULL DEFAULT 0,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ── Performance Tracking ──────────────────────────────────────────────────────

-- Tracks performance at three granularity levels using a surrogate PK.
-- subtopic and difficulty are nullable — NULL means "rolled up across all".
--
-- Three row types per topic after a session:
--   subtopic=NULL,  difficulty=NULL  → overall topic score
--   subtopic=set,   difficulty=NULL  → subtopic score across all difficulties
--   subtopic=set,   difficulty=set   → most granular view
--
-- The UNIQUE index below enforces one row per (student, topic, subtopic, difficulty)
-- combination, using sentinel strings for NULLs so COALESCE works in the index.

CREATE TABLE IF NOT EXISTS student_performance (
    perf_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    TEXT NOT NULL,
    topic         TEXT NOT NULL,
    subtopic      TEXT,
    difficulty    TEXT,
    sessions      INTEGER NOT NULL DEFAULT 0,
    avg_score     REAL NOT NULL DEFAULT 0.0,
    last_score    REAL,
    trend         REAL NOT NULL DEFAULT 0.0,
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ── Indexes ───────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_results_student     ON student_results (student_id);
CREATE INDEX IF NOT EXISTS idx_results_session     ON student_results (session_id);
CREATE INDEX IF NOT EXISTS idx_results_topic       ON student_results (topic);
CREATE INDEX IF NOT EXISTS idx_results_subtopic    ON student_results (subtopic);
CREATE INDEX IF NOT EXISTS idx_perf_student        ON student_performance (student_id);
CREATE INDEX IF NOT EXISTS idx_perf_topic          ON student_performance (student_id, topic);
CREATE INDEX IF NOT EXISTS idx_perf_subtopic       ON student_performance (student_id, topic, subtopic);

-- Enforces uniqueness across the four key columns.
-- COALESCE replaces NULL with a sentinel string '__all__' so the index
-- treats (circles, NULL, NULL) as distinct from (circles, arc_length, NULL).
-- The backend uses INSERT OR REPLACE with the same COALESCE logic when upserting.
CREATE UNIQUE INDEX IF NOT EXISTS idx_perf_unique ON student_performance (
    student_id,
    topic,
    COALESCE(subtopic,   '__all__'),
    COALESCE(difficulty, '__all__')
);
