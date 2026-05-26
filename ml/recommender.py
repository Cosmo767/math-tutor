"""
recommender.py

The single interface for getting topic recommendations.
Everything else in the app calls get_recommendation() or get_both_recommendations().

Two recommendation paths:
  - Claude API: natural language, explainable, reliable with little data
  - SGDClassifier: instant, free, improves with real student data over time

get_both_recommendations() runs both in parallel using concurrent.futures.
The model result arrives almost instantly; Claude streams in word by word.
This lets the frontend show the model result immediately while Claude is still typing.

Why concurrent.futures instead of asyncio?
  Flask is synchronous by default. concurrent.futures.ThreadPoolExecutor lets
  us run blocking calls (API request, model inference) in separate threads
  without switching to an async framework. Simpler for where we are now.
  If we move to FastAPI later, we'd replace this with async/await.
"""

from __future__ import annotations

import os
import re
import json
import joblib
import numpy as np
import anthropic
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Generator
from dotenv import load_dotenv

load_dotenv()

MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "recommender.pkl")
META_PATH  = os.path.join(os.path.dirname(__file__), "models", "model_meta.pkl")

MIN_REAL_SESSIONS_FOR_MODEL = 10

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

# Lazy-loaded globals — populated on first use, not at import time
_model = None
_meta  = None


def _load_model() -> tuple | None:
    global _model, _meta
    if _model is not None:
        return _model, _meta
    if not os.path.exists(MODEL_PATH):
        return None
    _model = joblib.load(MODEL_PATH)
    _meta  = joblib.load(META_PATH)
    return _model, _meta


# ── Model recommendation ──────────────────────────────────────────────────────

def _model_recommendation(scores: dict[str, float]) -> dict:
    """
    Runs the trained SGDClassifier. Returns in milliseconds.
    predict_proba() gives a confidence score per topic, not just the top pick —
    useful for showing "also consider" secondary recommendations.
    """
    result = _load_model()
    if result is None:
        raise RuntimeError("Model not found. Run train_model.py first.")

    model, meta = result
    encoder = meta["encoder"]

    X = np.array([[scores.get(t, 0.5) for t in TOPICS]])
    proba = model.predict_proba(X)[0]

    ranked_indices = np.argsort(proba)[::-1]
    ranked = [
        {"topic": encoder.classes_[i], "confidence": round(float(proba[i]), 3)}
        for i in ranked_indices
    ]

    return {
        "method": "model",
        "recommendation": ranked[0]["topic"],
        "confidence": ranked[0]["confidence"],
        "full_ranking": ranked,
        "n_training_rows": meta.get("n_training_rows", "unknown"),
    }


# ── Claude recommendation (non-streaming) ────────────────────────────────────

def _claude_recommendation(scores: dict[str, float]) -> dict:
    """
    Standard (non-streaming) Claude call. Used when we just need the result
    without streaming — e.g. when running both in parallel and only want
    the final output, not word-by-word delivery.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=api_key)
    score_lines = "\n".join(
        f"  {topic}: {score:.0%}" for topic, score in sorted(scores.items())
    )

    prompt = f"""You are an expert high school geometry tutor reviewing a student's quiz performance.

Student's topic scores:
{score_lines}

Based on these scores:
1. Identify the topic the student most needs to review
2. Identify 1-2 secondary topics worth attention
3. Give a brief, encouraging explanation for the student (2-3 sentences max)

Topic names must exactly match one of:
{json.dumps(TOPICS)}

Respond ONLY in valid JSON, no preamble:
{{
  "recommendation": "topic_name",
  "secondary": ["topic_name"],
  "explanation": "encouraging explanation for the student",
  "reasoning": "brief internal reasoning (not shown to student)"
}}"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text.strip()
    raw = re.sub(r'^```json\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    data = json.loads(raw)

    return {
        "method": "claude",
        "recommendation": data["recommendation"],
        "secondary": data.get("secondary", []),
        "explanation": data.get("explanation", ""),
        "reasoning": data.get("reasoning", ""),
    }


# ── Claude recommendation (streaming) ────────────────────────────────────────

def _claude_recommendation_stream(scores: dict[str, float]) -> Generator[str, None, None]:
    """
    Streaming version of the Claude call. Instead of waiting for the full
    response, yields text chunks as they arrive from the API.

    This is a Python generator — each `yield` sends one chunk to the caller.
    The Flask SSE route iterates this generator and pushes each chunk to
    the browser as a Server-Sent Event.

    Why stream Claude but not the model?
      The model is instant (~1ms). Streaming adds complexity for no benefit.
      Claude takes 1-2 seconds. Streaming makes it feel responsive immediately.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        yield json.dumps({"error": "ANTHROPIC_API_KEY not set"})
        return

    client = anthropic.Anthropic(api_key=api_key)
    score_lines = "\n".join(
        f"  {topic}: {score:.0%}" for topic, score in sorted(scores.items())
    )

    prompt = f"""You are an expert high school geometry tutor reviewing a student's quiz performance.

Student's topic scores:
{score_lines}

Give a recommendation in this exact format — write it naturally, not as JSON.
Start with: "I recommend focusing on [topic]."
Then 2-3 sentences of encouragement and specific advice.
Then: "You might also review: [topic1], [topic2]."

Keep it under 80 words total. Be warm and specific."""

    # context manager syntax ensures the stream connection is always closed,
    # even if the client disconnects mid-stream
    with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}]
    ) as stream:
        for text_chunk in stream.text_stream:
            # Each chunk is a small string — a word or partial word.
            # We wrap it in SSE format here so the generator is self-contained.
            yield text_chunk


# ── Parallel dual recommender ─────────────────────────────────────────────────

def get_both_recommendations(
    scores: dict[str, float],
    show_claude: bool = True
) -> Generator[str, None, None]:
    """
    Runs both recommendations and yields SSE-formatted events as results arrive.

    Server-Sent Events (SSE) format:
      Each event is a string: "data: {json}\\n\\n"
      The double newline signals the end of one event to the browser.
      The browser's EventSource API fires an 'onmessage' event for each one.

    Event types we send:
      {"type": "model", ...}          → model result, arrives first (~instant)
      {"type": "claude_chunk", ...}   → one streamed text chunk from Claude
      {"type": "claude_done"}         → Claude finished streaming
      {"type": "model_unavailable"}   → no model file found yet
      {"type": "error", ...}          → something went wrong

    show_claude: controlled by the student's preference in the DB.
      If False, we skip the Claude API call entirely — no cost, no latency.
    """

    def format_sse(data: dict) -> str:
        """Wrap a dict as an SSE event string."""
        return f"data: {json.dumps(data)}\n\n"

    # ── Step 1: model result (instant, no threading needed) ──────────────────
    model_result = _load_model()
    if model_result is not None:
        try:
            result = _model_recommendation(scores)
            yield format_sse({"type": "model", **result})
        except Exception as e:
            yield format_sse({"type": "error", "source": "model", "message": str(e)})
    else:
        yield format_sse({
            "type": "model_unavailable",
            "message": "Model not trained yet. Run ml/train_model.py first."
        })

    # ── Step 2: Claude streaming (if enabled) ────────────────────────────────
    if not show_claude:
        yield format_sse({"type": "claude_disabled"})
        return

    try:
        full_text = ""
        for chunk in _claude_recommendation_stream(scores):
            full_text += chunk
            yield format_sse({"type": "claude_chunk", "chunk": chunk})

        # Send the complete text at the end so the frontend has it in one piece
        # for logging, feedback buttons, etc.
        yield format_sse({"type": "claude_done", "full_text": full_text})

    except Exception as e:
        yield format_sse({"type": "error", "source": "claude", "message": str(e)})


# ── Single recommendation (original interface, kept for compatibility) ─────────

def get_recommendation(scores: dict[str, float], real_session_count: int = 0) -> dict:
    """
    Original non-streaming interface. Still used by routes that just need
    a single result — e.g. the /api/update endpoint, internal calls.
    """
    use_model = (
        real_session_count >= MIN_REAL_SESSIONS_FOR_MODEL
        and os.path.exists(MODEL_PATH)
    )

    if use_model:
        try:
            return _model_recommendation(scores)
        except Exception as e:
            print(f"Model failed ({e}), falling back to Claude")
            return _claude_recommendation(scores)
    else:
        return _claude_recommendation(scores)


# ── Incremental model update ──────────────────────────────────────────────────

def update_model(scores: dict[str, float], confirmed_weak_topic: str) -> bool:
    """
    partial_fit() updates the model with one new real data point without
    full retraining. Called after a student session confirms a weak topic.
    """
    result = _load_model()
    if result is None:
        print("No model to update. Run train_model.py first.")
        return False

    model, meta = result
    encoder = meta["encoder"]

    if confirmed_weak_topic not in encoder.classes_:
        print(f"Unknown topic: {confirmed_weak_topic}")
        return False

    X = np.array([[scores.get(t, 0.5) for t in TOPICS]])
    y = encoder.transform([confirmed_weak_topic])

    model.partial_fit(X, y, classes=np.arange(len(encoder.classes_)))
    meta["n_training_rows"] = meta.get("n_training_rows", 0) + 1

    joblib.dump(model, MODEL_PATH)
    joblib.dump(meta, META_PATH)

    print(f"✓ Model updated. Total training rows: {meta['n_training_rows']}")
    return True
