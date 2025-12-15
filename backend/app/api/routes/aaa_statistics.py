import uuid
from datetime import datetime, time, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import func, select


from app.api.deps import SessionDep, get_current_user
from app.models import (
    AaaStatisticsTodayPublic,
    AaaStatisticsDateRangePublic,
)
from app.crud import aaa_statistics


router = APIRouter(prefix="/aaa_statistics", tags=["aaa_statistics"])


@router.get(
    "/today/",
    dependencies=[Depends(get_current_user)],
    response_model=AaaStatisticsTodayPublic,
)
def read_aaa_statistics(session: SessionDep, skip: int = 0, limit: int = 5) -> Any:
    """
    Retrieve aaa_statistics.
    """

    today = datetime.now().date()
    start_date = datetime.combine(today, time.min)
    end_date = datetime.combine(today, time.max)

    return_statistics = {}
    return_statistics.update(
        aaa_statistics.get_last_7_days_statistics(
            session=session,
        )
    )
    return_statistics.update(
        aaa_statistics.process_authentication_statistics(
            session=session,
            start_date=start_date,
            end_date=end_date,
            skip=skip,
            limit=limit,
        )
    )
    return_statistics.update(
        aaa_statistics.process_authorization_statistics(
            session=session,
            start_date=start_date,
            end_date=end_date,
            skip=skip,
            limit=limit,
        )
    )
    today_results = aaa_statistics.process_today_authentication_statistics(
        session=session,
    )
    if today_results:
        return_statistics.update(today_results)

    return return_statistics


@router.get(
    "/range/",
    dependencies=[Depends(get_current_user)],
    response_model=AaaStatisticsDateRangePublic,
)
def read_aaa_statistics_range(
    session: SessionDep, skip: int = 0, limit: int = 5, range_date: str = None
) -> Any:
    """
    Retrieve aaa_statistics.
    """

    if range_date:
        try:
            start_date_str, end_date_str = range_date.split(",")
            start_date = datetime.fromisoformat(start_date_str)
            # Combine end date with max time to include the whole day
            end_date = datetime.combine(
                datetime.fromisoformat(end_date_str).date(), time.max
            )
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid range_date format. Expected 'YYYY-MM-DD,YYYY-MM-DD'.",
            )
    else:
        # Default to today if no range is provided
        end_date = datetime.utcnow() - timedelta(days=1)
        start_date = end_date - timedelta(days=7)

    return_statistics = {}
    return_statistics.update(
        aaa_statistics.get_date_range_statistics(
            session=session,
            start_date=start_date,
            end_date=end_date,
        )
    )
    return_statistics.update(
        aaa_statistics.process_authentication_statistics(
            session=session,
            start_date=start_date,
            end_date=end_date,
            skip=skip,
            limit=limit,
        )
    )
    return_statistics.update(
        aaa_statistics.process_authorization_statistics(
            session=session,
            start_date=start_date,
            end_date=end_date,
            skip=skip,
            limit=limit,
        )
    )
    today_results = aaa_statistics.process_today_authentication_statistics(
        session=session,
    )
    if today_results:
        return_statistics.update(today_results)

    return return_statistics
