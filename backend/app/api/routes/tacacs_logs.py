import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import func, select

from app.api.deps import SessionDep, get_current_user
from app.core.config import settings
from app.models import (
    TacacsLog,
    TacacsLogDailySummary,
    TacacsLogEvent,
    TacacsLogEventsPublic,
    TacacsLogPublic,
    TacacsLogTypeSummary,
    TacacsLogsPublic,
)

router = APIRouter(prefix="/tacacs_logs", tags=["tacacs_logs"])

LOG_DIRECTORY = "/var/log/tacacs"

IP_REGEX = r"([a-fA-F0-9:.]+|[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})"
_LOG_REGEX = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} [+-]\d{4})\s+"
    rf"(?P<nas_ip>{IP_REGEX})\s+"
    r"(?P<username>[\w.-]+)\s+"
    r"(?P<port>[\w/.-]+)\s+"  # tty / port field (e.g. vty14, tty0, ssh)
    rf"(?P<client_ip>{IP_REGEX})\s+"
    r"(?P<message>.*)$"
)

# Regex to strip the leading profile name from authorization messages:
# e.g. "tacacs_super_user_profile permit shell show ip route" → group(permit/deny/...) + command
_AUTHZ_CMD_REGEX = re.compile(
    r"^(?:[\w.-]+\s+)?"
    r"(?:permit|deny)\s+"
    r"(?:[\w.-]+\s+)?"  # optional service token (shell, junos-exec, …)
    r"(?P<command>.+?)\s*$",
    re.IGNORECASE,
)
_ACCT_CMD_REGEX = re.compile(
    r"(?:start|stop)\s+"
    r"(?:[\w.-]+\s+)?"  # optional service token
    r"(?P<command>.+?)\s*$",
    re.IGNORECASE,
)

_AUTH_RESULT_MAP = {
    "succeeded": "success",
    "failed": "failed",
    "denied": "failed",
}
_AUTHZ_RESULT_MAP = {
    "permit": "permit",
    "deny": "deny",
}
_ACCT_RESULT_MAP = {
    "start": "start",
    "stop": "stop",
}


def _classify_result(log_type: str, message: str) -> str:
    msg = message.lower()
    if log_type == "authentication":
        for kw, result in _AUTH_RESULT_MAP.items():
            if kw in msg:
                return result
        return "unknown"
    if log_type == "authorization":
        for kw, result in _AUTHZ_RESULT_MAP.items():
            if kw in msg:
                return result
        return "unknown"
    if log_type == "accounting":
        for kw, result in _ACCT_RESULT_MAP.items():
            if kw in msg:
                return result
        return "unknown"
    return "unknown"


def _log_file_path(log_type: str, date: datetime) -> str:
    """Return the absolute path for a log file of the given type and date."""
    year = date.strftime("%Y")
    month = date.strftime("%m")
    day = date.strftime("%d")
    filename = f"{log_type}-{year}-{month}-{day}.log"
    return os.path.join(settings.TACACS_LOG_DIRECTORY, year, month, filename)


def _extract_command(log_type: str, message: str) -> str | None:
    """Best-effort extraction of a human-readable command from the raw log message."""
    if log_type == "authorization":
        m = _AUTHZ_CMD_REGEX.match(message.strip())
        if m:
            cmd = m.group("command").strip()
            # Strip trailing <cr> artifact common in TACACS+ authz messages
            return cmd.removesuffix("<cr>").strip() or None
    if log_type == "accounting":
        m = _ACCT_CMD_REGEX.search(message.strip())
        if m:
            cmd = m.group("command").strip()
            return cmd.removesuffix("<cr>").strip() or None
    return None


def _parse_log_file(log_type: str, path: str) -> list[TacacsLogEvent]:
    """Parse a single log file, returning structured events."""
    events: list[TacacsLogEvent] = []
    if not os.path.exists(path):
        return events
    try:
        with open(path, errors="ignore") as f:
            for line in f:
                m = _LOG_REGEX.match(line.rstrip())
                if not m:
                    continue
                d = m.groupdict()
                message = d["message"]
                result = _classify_result(log_type, message)
                port = d.get("port") or None
                command = _extract_command(log_type, message)
                # Session ID: deterministic grouping key (no DB needed)
                session_key_parts = [
                    d["username"],
                    d["nas_ip"],
                    d["client_ip"],
                    port or "",
                ]
                session_id = "|".join(session_key_parts)
                events.append(
                    TacacsLogEvent(
                        timestamp=d["timestamp"],
                        log_type=log_type,
                        username=d["username"],
                        nas_ip=d["nas_ip"],
                        client_ip=d["client_ip"],
                        result=result,
                        message=message,
                        command=command,
                        port=port,
                        session_id=session_id,
                    )
                )
    except OSError:
        pass
    return events


@router.get(
    "/events/summary",
    dependencies=[Depends(get_current_user)],
    response_model=TacacsLogDailySummary,
)
def get_log_events_summary(
    date: str | None = None,
) -> Any:
    """
    Return count totals for auth/authz/acct log events for a given date (default: today).
    """
    try:
        target_date = (
            datetime.strptime(date, "%Y-%m-%d") if date else datetime.now(timezone.utc)
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")

    date_str = target_date.strftime("%Y-%m-%d")
    summary: dict[str, TacacsLogTypeSummary] = {
        lt: TacacsLogTypeSummary()
        for lt in ("authentication", "authorization", "accounting")
    }

    for lt in ("authentication", "authorization", "accounting"):
        path = _log_file_path(lt, target_date)
        events = _parse_log_file(lt, path)
        s = summary[lt]
        for ev in events:
            s.total += 1
            if ev.result == "success":
                s.success += 1
            elif ev.result == "failed":
                s.failed += 1
            elif ev.result == "permit":
                s.permit += 1
            elif ev.result == "deny":
                s.deny += 1
            elif ev.result == "start":
                s.start += 1
            elif ev.result == "stop":
                s.stop += 1

    return TacacsLogDailySummary(
        date=date_str,
        authentication=summary["authentication"],
        authorization=summary["authorization"],
        accounting=summary["accounting"],
    )


@router.get(
    "/events",
    dependencies=[Depends(get_current_user)],
    response_model=TacacsLogEventsPublic,
)
def list_log_events(
    date: str | None = None,
    log_type: str = "all",
    result: str | None = None,
    username: str | None = None,
    nas_ip: str | None = None,
    skip: int = 0,
    limit: int = 20,
) -> Any:
    """
    Return structured TACACS+ log events parsed from log files.
    date: YYYY-MM-DD (default: today). log_type: authentication|authorization|accounting|all.
    """
    try:
        target_date = (
            datetime.strptime(date, "%Y-%m-%d") if date else datetime.now(timezone.utc)
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")

    log_types = (
        ["authentication", "authorization", "accounting"]
        if log_type == "all"
        else [log_type]
    )
    valid_types = {"authentication", "authorization", "accounting", "all"}
    if log_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"log_type must be one of: {', '.join(sorted(valid_types))}",
        )

    all_events: list[TacacsLogEvent] = []
    for lt in log_types:
        path = _log_file_path(lt, target_date)
        all_events.extend(_parse_log_file(lt, path))

    # Sort newest-first by timestamp string (ISO-ish format sorts lexicographically)
    all_events.sort(key=lambda e: e.timestamp, reverse=True)

    # Apply filters
    if result:
        all_events = [e for e in all_events if e.result == result]
    if username:
        lower = username.lower()
        all_events = [e for e in all_events if lower in e.username.lower()]
    if nas_ip:
        all_events = [e for e in all_events if nas_ip in e.nas_ip]

    count = len(all_events)
    page = all_events[skip : skip + limit]
    return TacacsLogEventsPublic(data=page, count=count)


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
            relative_path = os.path.relpath(os.path.join(root, file), LOG_DIRECTORY)

            existing = session.exec(
                select(TacacsLog).where(TacacsLog.filepath == relative_path)
            ).first()
            if not existing:
                try:
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
    search: str | None = None,
) -> Any:
    """
    Read a specific TACACS+ log file. Can be filtered by a search term.
    """
    db_tacacs_log = session.get(TacacsLog, id)
    if not db_tacacs_log:
        raise HTTPException(status_code=404, detail="Log file not found in database.")

    log_path = os.path.join(LOG_DIRECTORY, db_tacacs_log.filepath)
    if not os.path.exists(log_path):
        raise HTTPException(status_code=404, detail="Log file not found.")

    try:
        with open(log_path, errors="ignore") as f:
            file_content_lines = f.readlines()

        if search:
            file_content_lines = [
                line for line in file_content_lines if search.lower() in line.lower()
            ]

        tacacs_log_result = TacacsLogPublic.model_validate(db_tacacs_log)
        tacacs_log_result.data = "".join(file_content_lines)
        return tacacs_log_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading log file: {e}")
