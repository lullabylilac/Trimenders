import os
import pickle
from pathlib import Path

from sentence_transformers import SentenceTransformer


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLASSIFIER_PATH = Path(
    os.getenv("FALL_CLASSIFIER_PATH", PROJECT_ROOT / "models" / "fall_classifier.pkl")
)
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
THRESHOLD = float(os.getenv("FALL_CLASSIFIER_THRESHOLD", "0.65"))

_embedding_model = None
_classifier = None


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _embedding_model


def get_classifier():
    global _classifier
    if _classifier is None:
        if not CLASSIFIER_PATH.exists():
            raise FileNotFoundError(
                f"Fall classifier was not found: {CLASSIFIER_PATH}. "
                "Run `python -m detection.train_classifier` from the project root to create it."
            )
        with CLASSIFIER_PATH.open("rb") as f:
            _classifier = pickle.load(f)
    return _classifier


def embedding_classify(sentence: str) -> dict:
    embedding = get_embedding_model().encode([sentence])
    probabilities = get_classifier().predict_proba(embedding)[0]
    alert_prob = probabilities[1]
    return {
        "detected": alert_prob >= THRESHOLD,
        "confidence": alert_prob,
        "label": "ALERT" if alert_prob >= 0.5 else "NORMAL",
    }
