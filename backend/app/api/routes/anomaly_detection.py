from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.crud import anomaly_detection as crud_anomaly
from app.crud.ml_anomaly_scorer import run_daily_anomaly_scoring
from app.models import AnomalyDetectionResultsPublic

router = APIRouter(prefix="/anomaly_detection", tags=["anomaly_detection"])


@router.get("/results/", response_model=AnomalyDetectionResultsPublic)
def read_anomaly_results(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
    subject_type: str | None = None,
    is_anomaly_only: bool = False,
    sort_by: str = "anomaly_score",
) -> Any:
    results, count = crud_anomaly.get_results(
        session=session,
        skip=skip,
        limit=limit,
        subject_type=subject_type,
        is_anomaly_only=is_anomaly_only,
        sort_by=sort_by,
    )
    return AnomalyDetectionResultsPublic(data=results, count=count)


@router.post("/retrain/", dependencies=[Depends(get_current_active_superuser)])
def retrain_anomaly_model(session: SessionDep) -> dict[str, Any]:
    scored = run_daily_anomaly_scoring(session=session)
    return {"message": f"Anomaly model retrained. {scored} subjects scored."}
