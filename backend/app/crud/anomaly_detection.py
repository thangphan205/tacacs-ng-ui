import uuid
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, func, select

from app.models import (
    AnomalyDetectionResult,
    AuthenticationStatistics,
    AuthorizationStatistics,
)


def upsert_result(
    *,
    session: Session,
    subject_type: str,
    subject_value: str,
    score: float,
    is_anomaly: bool,
    risk_level: str,
    features_json: str,
) -> AnomalyDetectionResult:
    existing = session.exec(
        select(AnomalyDetectionResult)
        .where(AnomalyDetectionResult.subject_type == subject_type)
        .where(AnomalyDetectionResult.subject_value == subject_value)
    ).first()

    now = datetime.now(timezone.utc)
    if existing:
        existing.anomaly_score = score
        existing.is_anomaly = is_anomaly
        existing.risk_level = risk_level
        existing.feature_snapshot = features_json
        existing.scored_at = now
        existing.updated_at = now
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    result = AnomalyDetectionResult(
        id=uuid.uuid4(),
        subject_type=subject_type,
        subject_value=subject_value,
        anomaly_score=score,
        is_anomaly=is_anomaly,
        risk_level=risk_level,
        feature_snapshot=features_json,
        scored_at=now,
    )
    session.add(result)
    session.commit()
    session.refresh(result)
    return result


def get_results(
    *,
    session: Session,
    skip: int = 0,
    limit: int = 100,
    subject_type: str | None = None,
    is_anomaly_only: bool = False,
    sort_by: str = "anomaly_score",
) -> tuple[list[AnomalyDetectionResult], int]:
    query = select(AnomalyDetectionResult)
    count_query = select(func.count()).select_from(AnomalyDetectionResult)

    if subject_type:
        query = query.where(AnomalyDetectionResult.subject_type == subject_type)
        count_query = count_query.where(AnomalyDetectionResult.subject_type == subject_type)
    if is_anomaly_only:
        query = query.where(AnomalyDetectionResult.is_anomaly == True)  # noqa: E712
        count_query = count_query.where(AnomalyDetectionResult.is_anomaly == True)  # noqa: E712

    if sort_by == "anomaly_score":
        query = query.order_by(AnomalyDetectionResult.anomaly_score)
    elif sort_by == "scored_at":
        query = query.order_by(AnomalyDetectionResult.scored_at.desc())  # type: ignore[attr-defined]
    else:
        query = query.order_by(AnomalyDetectionResult.subject_value)

    count = session.exec(count_query).one()
    results = session.exec(query.offset(skip).limit(limit)).all()
    return list(results), count


def get_feature_matrix(
    *, session: Session, days: int = 30
) -> dict[str, dict[str, float]]:
    """Build per-username feature vectors from statistics tables."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    auth_rows = session.exec(
        select(
            AuthenticationStatistics.username,
            AuthenticationStatistics.user_source_ip,
            AuthenticationStatistics.fail_count,
            AuthenticationStatistics.success_count,
            AuthenticationStatistics.log_date,
        ).where(AuthenticationStatistics.log_date >= cutoff)
    ).all()

    authz_rows = session.exec(
        select(
            AuthorizationStatistics.username,
            AuthorizationStatistics.deny_count,
            AuthorizationStatistics.permit_count,
        ).where(AuthorizationStatistics.log_date >= cutoff)
    ).all()

    # Aggregate per username
    user_data: dict[str, dict] = {}

    for row in auth_rows:
        u = row.username
        if u not in user_data:
            user_data[u] = {
                "fail_counts": [],
            "unique_ips": set(),
            "total_success": 0,
            "total_fail": 0,
        }
        user_data[u]["fail_counts"].append(row.fail_count)
        user_data[u]["unique_ips"].add(row.user_source_ip)
        user_data[u]["total_success"] += row.success_count
        user_data[u]["total_fail"] += row.fail_count

    authz_agg: dict[str, dict] = {}
    for row in authz_rows:
        u = row.username
        if u not in authz_agg:
            authz_agg[u] = {"deny": 0, "permit": 0}
        authz_agg[u]["deny"] += row.deny_count
        authz_agg[u]["permit"] += row.permit_count

    matrix: dict[str, dict[str, float]] = {}
    for username, data in user_data.items():
        fails = data["fail_counts"]
        avg_fails = sum(fails) / max(len(fails), 1)
        mean = avg_fails
        stddev = (sum((f - mean) ** 2 for f in fails) / max(len(fails), 1)) ** 0.5
        unique_ip_count = float(len(data["unique_ips"]))
        az = authz_agg.get(username, {"deny": 0, "permit": 0})
        total_authz = az["deny"] + az["permit"]
        deny_ratio = az["deny"] / total_authz if total_authz > 0 else 0.0

        matrix[username] = {
            "avg_daily_fails": avg_fails,
            "stddev_fails": stddev,
            "unique_ip_count": unique_ip_count,
            "deny_ratio": deny_ratio,
        }

    return matrix
