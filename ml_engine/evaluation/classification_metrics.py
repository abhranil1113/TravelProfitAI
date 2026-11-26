"""
ml_engine/evaluation/classification_metrics.py

Binary classification evaluation metrics with zero-division protection and threshold calibration.
"""

from typing import Dict, Any, Union
import numpy as np


class ClassificationMetrics:
    """Calculates classification performance, confusion matrices, and calibration metrics."""

    @staticmethod
    def calculate_all(
        y_true: Union[np.ndarray, list],
        y_prob: Union[np.ndarray, list],
        threshold: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Computes Confusion Matrix, Precision, Recall, Specificity, F1, Accuracy, and Brier Score.
        """
        yt = np.asarray(y_true, dtype=int)
        yp_prob = np.asarray(y_prob, dtype=float)
        yp = (yp_prob >= threshold).astype(int)

        if len(yt) == 0:
            return {
                "threshold": threshold,
                "accuracy": None,
                "precision": None,
                "recall": None,
                "specificity": None,
                "f1_score": None,
                "brier_score": None,
                "confusion_matrix": {
                    "true_positives": 0,
                    "false_positives": 0,
                    "true_negatives": 0,
                    "false_negatives": 0,
                },
                "sample_count": 0,
            }

        tp = int(np.sum((yt == 1) & (yp == 1)))
        fp = int(np.sum((yt == 0) & (yp == 1)))
        tn = int(np.sum((yt == 0) & (yp == 0)))
        fn = int(np.sum((yt == 1) & (yp == 0)))

        acc = float((tp + tn) / max(1, len(yt)))
        prec = float(tp / max(1, tp + fp))
        rec = float(tp / max(1, tp + fn))
        spec = float(tn / max(1, tn + fp))
        f1 = float((2 * prec * rec) / max(1e-9, prec + rec))

        # Brier score
        brier = float(np.mean((yp_prob - yt) ** 2))

        return {
            "threshold": threshold,
            "accuracy": round(acc, 4),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "specificity": round(spec, 4),
            "f1_score": round(f1, 4),
            "brier_score": round(brier, 4),
            "confusion_matrix": {
                "true_positives": tp,
                "false_positives": fp,
                "true_negatives": tn,
                "false_negatives": fn,
            },
        }
