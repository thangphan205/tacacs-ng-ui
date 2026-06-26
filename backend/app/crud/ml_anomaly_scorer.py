"""ML anomaly scoring using IsolationForest on 30-day rolling stats."""

import json
import logging

import numpy as np
from sklearn.ensemble import IsolationForest
from sqlmodel import Session

from app.crud.anomaly_detection import get_feature_matrix, upsert_result

logger = logging.getLogger(__name__)

_CONTAMINATION = 0.05
_N_ESTIMATORS = 100
_RANDOM_STATE = 42


def _score_to_risk(score: float) -> str:
    if score >= -0.05:
        return "normal"
    if score >= -0.1:
        return "low"
    if score >= -0.2:
        return "medium"
    if score >= -0.3:
        return "high"
    return "critical"


def run_daily_anomaly_scoring(*, session: Session) -> int:
    """Train IsolationForest on feature matrix and upsert results. Returns count scored."""
    matrix = get_feature_matrix(session=session, days=30)

    if len(matrix) < 2:
        logger.info(
            "Not enough subjects to score anomalies (need >= 2, got %d)", len(matrix)
        )
        return 0

    subjects = list(matrix.keys())
    feature_names = ["avg_daily_fails", "stddev_fails", "unique_ip_count", "deny_ratio"]
    X = np.array([[matrix[u].get(f, 0.0) for f in feature_names] for u in subjects])

    model = IsolationForest(
        n_estimators=_N_ESTIMATORS,
        contamination=_CONTAMINATION,
        random_state=_RANDOM_STATE,
    )
    model.fit(X)
    scores = model.score_samples(X)

    for i, subject_value in enumerate(subjects):
        score = float(scores[i])
        is_anomaly = score < -0.1
        risk_level = _score_to_risk(score)
        features_json = json.dumps({**matrix[subject_value], "raw_score": score})

        upsert_result(
            session=session,
            subject_type="username",
            subject_value=subject_value,
            score=score,
            is_anomaly=is_anomaly,
            risk_level=risk_level,
            features_json=features_json,
        )

    logger.info("Anomaly scoring complete: %d subjects scored", len(subjects))
    return len(subjects)
