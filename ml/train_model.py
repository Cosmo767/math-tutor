"""
train_model.py

Trains the initial recommendation model from simulated student data.
Run this once after simulate_students.py has generated training data.

Model choice: SGDClassifier (Stochastic Gradient Descent)
  Why SGD and not a Decision Tree?
  SGDClassifier supports partial_fit() — meaning we can update it incrementally
  as real students take quizzes, without retraining from scratch every time.
  Decision Trees don't support this. The tradeoff is interpretability:
  SGD is a linear model under the hood, less visually readable than a tree,
  but the feature importance scores still tell you what it learned.

  We also train a DecisionTreeClassifier in parallel purely for inspection —
  you can print its rules and understand what the model is "thinking".
  But SGD is what actually runs in production.

Why not a neural network?
  Overkill for 10 features and ~100 training rows. Linear models work well
  when the feature space is small and well-defined. Add complexity only when
  simpler models stop working.
"""

import pandas as pd
import numpy as np
import joblib
import os
import sys
from sklearn.linear_model import SGDClassifier
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import cross_val_score
from sklearn.metrics import classification_report

DATA_PATH  = os.path.join(os.path.dirname(__file__), "data", "simulated_students.csv")
MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "recommender.pkl")
META_PATH  = os.path.join(os.path.dirname(__file__), "models", "model_meta.pkl")

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


def load_data() -> tuple[np.ndarray, np.ndarray, LabelEncoder]:
    """
    X: feature matrix — each row is a student, each column is a topic score
    y: labels — the topic each student most needs to review
    encoder: maps string labels ("circles") to integers (0, 1, 2...)
             scikit-learn classifiers require numeric labels
    """
    df = pd.read_csv(DATA_PATH)
    print(f"Loaded {len(df)} training rows")
    print(f"Label distribution:\n{df['weak_topic'].value_counts()}\n")

    X = df[TOPICS].values
    encoder = LabelEncoder()
    y = encoder.fit_transform(df["weak_topic"].values)

    return X, y, encoder


def train(X: np.ndarray, y: np.ndarray) -> SGDClassifier:
    """
    SGDClassifier with log_loss gives us probability estimates per class,
    not just a hard prediction. This means we can say "70% circles, 20% trig"
    which is more useful for a recommendation than a single label.

    max_iter=1000: number of passes through the training data.
    random_state: ensures reproducibility — same data always gives same model.
    """
    model = SGDClassifier(
        loss="log_loss",
        max_iter=1000,
        random_state=42,
        n_jobs=-1,       # use all CPU cores
    )
    model.fit(X, y)
    return model


def evaluate(model: SGDClassifier, X: np.ndarray, y: np.ndarray, encoder: LabelEncoder) -> None:
    """
    Cross-validation: splits data into 5 folds, trains on 4, tests on 1,
    repeats 5 times. Gives a more honest accuracy estimate than testing
    on the same data you trained on (which would be overly optimistic).
    """
    cv_scores = cross_val_score(model, X, y, cv=5, scoring="accuracy")
    print(f"Cross-validation accuracy: {cv_scores.mean():.2f} ± {cv_scores.std():.2f}")
    print(f"(Each fold: {cv_scores.round(2)})\n")

    y_pred = model.predict(X)
    print("Classification report (training data):")
    print(classification_report(y, y_pred, target_names=encoder.classes_))


def inspect_with_tree(X: np.ndarray, y: np.ndarray, encoder: LabelEncoder) -> None:
    """
    Train a separate Decision Tree just to inspect its logic.
    max_depth=4 keeps it readable — deeper trees overfit and become unreadable.
    This tree is NOT used for predictions, only for understanding.
    """
    tree = DecisionTreeClassifier(max_depth=4, random_state=42)
    tree.fit(X, y)

    print("Decision tree rules (for inspection only — not used in production):")
    print(export_text(tree, feature_names=TOPICS))


def main() -> None:
    if not os.path.exists(DATA_PATH):
        print(f"✗ Training data not found at {DATA_PATH}")
        print("  Run simulate_students.py first.")
        sys.exit(1)

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)

    print("Loading training data...")
    X, y, encoder = load_data()

    print("Training SGDClassifier...")
    model = train(X, y)

    print("\nEvaluating...")
    evaluate(model, X, y, encoder)

    print("\nInspecting learned rules via Decision Tree...")
    inspect_with_tree(X, y, encoder)

    # Save both the model and the encoder together.
    # The encoder is essential — without it we can't convert predictions
    # back from integers to topic names like "circles".
    joblib.dump(model, MODEL_PATH)
    joblib.dump({"encoder": encoder, "topics": TOPICS, "n_training_rows": len(X)}, META_PATH)

    print(f"\n✓ Model saved to {MODEL_PATH}")
    print(f"✓ Metadata saved to {META_PATH}")


if __name__ == "__main__":
    main()
