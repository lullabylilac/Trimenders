import argparse
import logging
import os
import pickle
import shutil
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.logging_config import configure_logging
from detection.training_data import TRAINING_DATA


DEFAULT_CLASSIFIER_PATH = Path(
    os.getenv("FALL_CLASSIFIER_PATH", PROJECT_ROOT / "models" / "fall_classifier.pkl")
)
DEFAULT_EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the first-stage fall classifier.")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_CLASSIFIER_PATH),
        help="Path to save the trained .pkl classifier.",
    )
    parser.add_argument(
        "--embedding-model",
        default=DEFAULT_EMBEDDING_MODEL,
        help="SentenceTransformer model name used to embed training sentences.",
    )
    parser.add_argument("--max-iter", type=int, default=1000, help="LogisticRegression max_iter.")
    parser.add_argument("--no-backup", action="store_true", help="Overwrite an existing model without backup.")
    parser.add_argument("--dry-run", action="store_true", help="Train and validate, but do not save the model.")
    return parser.parse_args()


def build_training_arrays() -> tuple[list[str], np.ndarray]:
    texts = [text for text, _ in TRAINING_DATA]
    labels = np.array([label for _, label in TRAINING_DATA])
    return texts, labels


def train_classifier(embedding_model_name: str, max_iter: int) -> LogisticRegression:
    texts, labels = build_training_arrays()
    label_counts = Counter(labels)
    logger.info("Training data loaded: total=%s, normal=%s, alert=%s", len(texts), label_counts[0], label_counts[1])

    embedding_model = SentenceTransformer(embedding_model_name)
    embeddings = embedding_model.encode(texts, show_progress_bar=True)

    classifier = LogisticRegression(max_iter=max_iter, random_state=42)
    min_class_count = min(label_counts.values())
    if min_class_count >= 2:
        cv_splits = min(5, min_class_count)
        scores = cross_val_score(classifier, embeddings, labels, cv=cv_splits)
        logger.info("Cross validation accuracy: %.3f (+/- %.3f)", scores.mean(), scores.std())

    classifier.fit(embeddings, labels)
    return classifier


def backup_existing_model(output_path: Path) -> Path | None:
    if not output_path.exists():
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = output_path.with_name(f"{output_path.name}.{timestamp}.bak")
    shutil.copy2(output_path, backup_path)
    return backup_path


def save_classifier(classifier: LogisticRegression, output_path: Path, no_backup: bool) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not no_backup:
        backup_path = backup_existing_model(output_path)
        if backup_path:
            logger.info("Existing classifier backed up: %s", backup_path)

    with output_path.open("wb") as f:
        pickle.dump(classifier, f)

    logger.info("Classifier saved: %s", output_path)


def main() -> int:
    configure_logging()
    args = parse_args()
    output_path = Path(args.output)

    classifier = train_classifier(args.embedding_model, args.max_iter)
    if args.dry_run:
        logger.info("Dry run complete. Model was not saved.")
        return 0

    save_classifier(classifier, output_path, args.no_backup)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
