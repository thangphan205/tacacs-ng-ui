import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import (
    SessionDep,
    SuperUser,
    get_client_ip,
    get_current_user,
    require_primary_node,
)
from app.crud import audit_logs as audit_logs_crud
from app.crud import stats_exclusions
from app.models import (
    Message,
    StatsExcludedUserCreate,
    StatsExcludedUserPublic,
    StatsExcludedUsersPublic,
)

router = APIRouter(prefix="/stats_exclusions", tags=["stats_exclusions"])


@router.get(
    "/",
    dependencies=[Depends(get_current_user)],
    response_model=StatsExcludedUsersPublic,
)
def read_stats_exclusions(session: SessionDep) -> Any:
    """
    List usernames excluded from the AAA statistics and dashboards.
    """
    rows = stats_exclusions.list_excluded_users(session=session)
    return StatsExcludedUsersPublic(data=rows, count=len(rows))


@router.post(
    "/",
    dependencies=[Depends(require_primary_node)],
    response_model=StatsExcludedUserPublic,
)
def create_stats_exclusion(
    *,
    session: SessionDep,
    current_user: SuperUser,
    request: Request,
    stats_exclusion_in: StatsExcludedUserCreate,
) -> Any:
    """
    Exclude a username, or a `*` glob such as `svc_*`, from the AAA statistics.

    Statistics only: the account still authenticates, its events still reach the
    raw logs, the log viewer, alerting and SIEM forwarding.
    """
    db_obj = stats_exclusions.create_excluded_user(
        session=session, excluded_user_in=stats_exclusion_in
    )
    if db_obj is None:
        raise HTTPException(
            status_code=409,
            detail=f"'{stats_exclusion_in.pattern}' is already excluded from statistics.",
        )
    # Snapshot before auditing: log_entity_action commits and expires db_obj.
    public = StatsExcludedUserPublic.model_validate(db_obj)
    audit_logs_crud.log_entity_action(
        session=session,
        action="CREATE",
        entity_type="StatsExcludedUser",
        entity_id=str(public.id),
        user_id=current_user.id,
        user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        new_values=public.model_dump_json(),
        description=f"Excluded '{public.pattern}' from AAA statistics",
    )
    return public


@router.delete("/{id}", dependencies=[Depends(require_primary_node)])
def delete_stats_exclusion(
    session: SessionDep, current_user: SuperUser, request: Request, id: uuid.UUID
) -> Message:
    """
    Remove a statistics exclusion; the user's activity is counted again,
    including historical days.
    """
    db_obj = stats_exclusions.get_excluded_user_by_id(session=session, id=id)
    if not db_obj:
        raise HTTPException(status_code=404, detail="Statistics exclusion not found")
    old = StatsExcludedUserPublic.model_validate(db_obj)
    stats_exclusions.delete_excluded_user(session=session, db_obj=db_obj)
    audit_logs_crud.log_entity_action(
        session=session,
        action="DELETE",
        entity_type="StatsExcludedUser",
        entity_id=str(old.id),
        user_id=current_user.id,
        user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        old_values=old.model_dump_json(),
        description=f"Removed '{old.pattern}' from statistics exclusions",
    )
    return Message(message="Statistics exclusion removed")
