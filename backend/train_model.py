"""
Trains the ticket classification model.

Pipeline:  ticket text -> TF-IDF (words + 2-word phrases) -> Logistic Regression
Output:    model/ticket_classifier.joblib  and  model/metrics.json

Usage:
    python train_model.py
"""

import json
import os

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data", "tickets_dataset.csv")
# MODEL_DIR can be overridden (the tests use a temporary folder)
MODEL_DIR = os.getenv("MODEL_DIR", os.path.join(BASE_DIR, "model"))
MODEL_PATH = os.path.join(MODEL_DIR, "ticket_classifier.joblib")
METRICS_PATH = os.path.join(MODEL_DIR, "metrics.json")


def build_pipeline() -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(
            lowercase=True,
            stop_words="english",   # drop words like "the", "is", "my"
            ngram_range=(1, 2),     # single words and 2-word phrases ("password reset")
            min_df=2,               # ignore words that appear only once
            sublinear_tf=True,
        )),
        ("clf", LogisticRegression(max_iter=1000, C=5.0)),
    ])


def train(verbose: bool = True, extra_rows=None) -> dict:
    """extra_rows: optional list of {"text", "category"} dicts, e.g. tickets that
    support agents corrected in the app. They are added to the TRAINING set only,
    so the test score stays comparable between versions."""
    if not os.path.exists(DATA_PATH):
        from generate_dataset import main as generate
        generate()

    df = pd.read_csv(DATA_PATH).dropna()
    df["text"] = df["text"].str.strip()
    df = df.drop_duplicates(subset=["text"])

    x_train, x_test, y_train, y_test = train_test_split(
        df["text"], df["category"], test_size=0.2, random_state=42, stratify=df["category"]
    )

    corrections_used = 0
    if extra_rows:
        extra = pd.DataFrame(extra_rows)[["text", "category"]].dropna()
        corrections_used = len(extra)
        x_train = pd.concat([x_train, extra["text"]], ignore_index=True)
        y_train = pd.concat([y_train, extra["category"]], ignore_index=True)

    model = build_pipeline()
    model.fit(x_train, y_train)

    predictions = model.predict(x_test)
    labels = sorted(df["category"].unique())
    metrics = {
        "train_size": int(len(x_train)),
        "test_size": int(len(x_test)),
        "corrections_used": corrections_used,
        "accuracy": round(float(accuracy_score(y_test, predictions)), 4),
        "labels": labels,
        "report": classification_report(y_test, predictions, output_dict=True, zero_division=0),
        "confusion_matrix": confusion_matrix(y_test, predictions, labels=labels).tolist(),
    }

    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    with open(METRICS_PATH, "w") as f:
        json.dump(metrics, f, indent=2)

    if verbose:
        print(f"Training tickets: {len(x_train)}   Test tickets: {len(x_test)}")
        print(f"Test accuracy: {metrics['accuracy']:.2%}\n")
        print(classification_report(y_test, predictions, zero_division=0))
        print(f"Model saved to {MODEL_PATH}")
    return metrics


if __name__ == "__main__":
    train()
