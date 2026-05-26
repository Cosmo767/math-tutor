-- math-tutor database schema
-- Version: 001
-- Run via: python question_bank/scripts/setup_db.py

-- ── Question Bank ────────────────────────────────────────────────────────────

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
    common_errors     TEXT NOT NULL DEFAULT '[]',   -- JSON array of likely wrong answers
    distractors       TEXT NOT NULL DEFAULT '[]',   -- JSON array for multiple choice options
    is_anchor         INTEGER NOT NULL DEFAULT 0,   -- 1 = manually written, used as generation seed
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Logs QC results for generated questions (approved / rejected / revised)
CREATE TABLE IF NOT EXISTS qc_log (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id       TEXT,
    verdict           TEXT NOT NULL CHECK (verdict IN ('approved', 'rejected', 'revised')),
    issues            TEXT,
    checked_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ── Students ─────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS students (
    id                          TEXT PRIMARY KEY,
    name                        TEXT,
    grade_level                 INTEGER,
    -- preference: whether to show Claude's recommendation alongside the model's
    -- stored here so it persists across sessions and the backend can skip
    -- the API call entirely when turned off
    show_claude_recommendation  INTEGER NOT NULL DEFAULT 1,
    created_at                  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ── Quiz Results ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS student_results (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id        TEXT NOT NULL,
    -- session_id groups all questions from one quiz sitting together.
    -- this lets us compute per-session topic scores, not just per-question.
    session_id        TEXT NOT NULL,
    question_id       TEXT NOT NULL,
    topic             TEXT NOT NULL,   -- denormalized from questions for faster queries
    answer_given      TEXT,
    is_correct        INTEGER NOT NULL DEFAULT 0,
    time_spent_seconds INTEGER,
    -- distinguishes real student data from Claude-simulated training data.
    -- the ML model uses both but we track the split for retraining decisions.
    is_simulated      INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ── Topic History ─────────────────────────────────────────────────────────────

-- Running summary of each student's performance per topic across all sessions.
-- Updated after every quiz session. This is what drives recommendations
-- and the "new test focused on weak points" feature.
CREATE TABLE IF NOT EXISTS student_topic_history (
    student_id    TEXT NOT NULL,
    topic         TEXT NOT NULL,
    sessions      INTEGER NOT NULL DEFAULT 0,    -- total quiz sessions on this topic
    avg_score     REAL NOT NULL DEFAULT 0.0,     -- rolling average score (0.0 - 1.0)
    last_score    REAL,                          -- most recent session score
    -- trend > 0: improving, trend < 0: declining, trend = 0: stable
    -- calculated as (last_score - avg_score) as a simple indicator
    trend         REAL NOT NULL DEFAULT 0.0,
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (student_id, topic)
);

-- ── Indexes ───────────────────────────────────────────────────────────────────

-- Speed up the most common queries
CREATE INDEX IF NOT EXISTS idx_results_student    ON student_results (student_id);
CREATE INDEX IF NOT EXISTS idx_results_session    ON student_results (session_id);
CREATE INDEX IF NOT EXISTS idx_results_topic      ON student_results (topic);
CREATE INDEX IF NOT EXISTS idx_history_student    ON student_topic_history (student_id);
