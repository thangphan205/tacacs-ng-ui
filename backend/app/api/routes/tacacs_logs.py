import os
from datetime import datetime
from typing import Any, List
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, func

from app.api.deps import SessionDep, get_current_user
from app.models import TacacsLog, TacacsLogPublic, TacacsLogsPublic

router = APIRouter(prefix="/tacacs_logs", tags=["tacacs_logs"])

LOG_DIRECTORY = "/var/log/tacacs"


@router.get(
    "/files",
    dependencies=[Depends(get_current_user)],
    response_model=TacacsLogsPublic,
)
def list_log_files(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    search: str | None = None,
) -> Any:
    """
    List all TACACS+ log files in the log directory and its subfolders.
    Also persist discovered files into the TacacsLog table (id, filename, filepath).
    """
    if not os.path.isdir(LOG_DIRECTORY):
        raise HTTPException(status_code=404, detail="Log directory not found.")

    new_logs = []
    for root, _, files in os.walk(LOG_DIRECTORY):
        for file in files:
            # We'll return the path relative to the log directory
            relative_path = os.path.relpath(os.path.join(root, file), LOG_DIRECTORY)

            # persist to DB if not exists
            existing = session.exec(
                select(TacacsLog).where(TacacsLog.filepath == relative_path)
            ).first()
            if not existing:
                try:
                    # Assuming filename format is like 'access-YYYY-mm-dd.log'
                    date_str = "-".join(file.split("-")[1:4]).split(".")[0]
                    log_date = datetime.strptime(date_str, "%Y-%m-%d")
                except (IndexError, ValueError):
                    log_date = datetime.fromtimestamp(
                        os.path.getmtime(os.path.join(root, file))
                    )
                new_logs.append(
                    TacacsLog(
                        filename=file, filepath=relative_path, created_at=log_date
                    )
                )

    if new_logs:
        session.add_all(new_logs)
        session.commit()

    query = select(TacacsLog)
    if search:
        query = query.where(TacacsLog.filename.ilike(f"%{search}%"))

    count_query = select(func.count()).select_from(query.subquery())
    count = session.exec(count_query).one()

    sort_column = getattr(TacacsLog, sort_by, None)
    if sort_column is None:
        raise HTTPException(status_code=400, detail=f"Invalid sort column: {sort_by}")

    order = sort_column.desc() if sort_order == "desc" else sort_column.asc()
    query = query.order_by(order).offset(skip).limit(limit)

    tacacs_logs = session.exec(query).all()

    return TacacsLogsPublic(data=tacacs_logs, count=count)


@router.get(
    "/{id}",
    dependencies=[Depends(get_current_user)],
    response_model=TacacsLogPublic,
)
def read_log_file(
    id: uuid.UUID,
    session: SessionDep,
) -> Any:
    """
    Read a specific TACACS+ log file.
    """
    db_tacacs_log = session.get(TacacsLog, id)
    if not db_tacacs_log:
        raise HTTPException(status_code=404, detail="Log file not found in database.")
    if not os.path.exists(os.path.join(LOG_DIRECTORY, db_tacacs_log.filepath)):
        raise HTTPException(status_code=404, detail="Log file not found.")
    try:
        file_content = ""
        with open(os.path.join(LOG_DIRECTORY, db_tacacs_log.filepath), "r") as f:
            file_content = f.readlines()
        tacacs_log_result = TacacsLogPublic.model_validate(db_tacacs_log)
        tacacs_log_result.data = "".join(file_content)
        return tacacs_log_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading log file: {e}")
