import os
from datetime import datetime
from typing import Any, List, Dict
import logging
import re
from collections import Counter, defaultdict
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import SessionDep, get_current_user

router = APIRouter(prefix="/tacacs_statistics", tags=["tacacs_statistics"])

logging.basicConfig(level=logging.INFO)

LOG_DIRECTORY = "/var/log/tacacs"


# Directory where your log files are stored
LOG_DIR = os.path.join(os.path.dirname(__file__), "..")

# Regex to parse the log lines. This is more robust than splitting.
# It captures: 1. Timestamp, 2. NAS IP, 3. Username, 4. TTY (optional), 5. User IP, 6. Message
# It requires the User IP to be present.
LOG_PATTERN = re.compile(
    r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \+\d{4})\s+([\d.]+)\t([\w_]+)\t(?:[\w/]*)\t([\d.]+)\t(.*)"
)


class LogSummary(BaseModel):
    successful: int
    failed: int


class TopEntry(BaseModel):
    name: str
    count: int


class UserLoginBreakdown(BaseModel):
    user: str
    successful: int
    failed: int


class TacacsFileLogStatistics(BaseModel):
    parsed_line_count: int
    log_summary: LogSummary
    top_successful_login_users: List[TopEntry]
    top_nas_ips: List[TopEntry]
    top_access_ips: List[TopEntry]
    ip_access_by_users: Dict[str, List[str]]
    user_login_breakdown: List[UserLoginBreakdown]


@router.get(
    "/",
    dependencies=[Depends(get_current_user)],
    response_model=TacacsFileLogStatistics,
)
def get_tacacs_logs_statistics(date_str: str | None = None) -> Any:
    """
    Parses log files from LOG_DIRECTORY and calculates statistics.
    If a date_str is provided (YYYY-MM-DD), it only processes logs from that date.
    Defaults to today's date if no date is provided.
    """

    if date_str is None:
        target_date = datetime.now().date()
    else:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return {"error": "Invalid date format. Please use YYYY-MM-DD."}
    # Data structures to hold our statistics. defaultdict makes it easy to handle nested counts.
    logins_by_user = defaultdict(Counter)
    access_by_user_ip = Counter()
    access_by_nas_ip = Counter()
    access_by_user_ip_users = defaultdict(set)
    log_summary = Counter()
    parsed_line_count = 0

    if not os.path.isdir(LOG_DIRECTORY):
        logging.error(f"Log directory not found at '{LOG_DIRECTORY}'")
        return {"error": f"Log directory not found at '{LOG_DIRECTORY}'"}

    # Determine the target log file name based on the date.
    log_file_date_str = target_date.strftime("%Y-%m-%d")
    target_filename = f"authentication-{log_file_date_str}.log"
    file_path = None

    # Walk through the LOG_DIRECTORY and its subdirectories to find the file.
    for dirpath, _, filenames in os.walk(LOG_DIRECTORY):
        if target_filename in filenames:
            file_path = os.path.join(dirpath, target_filename)
            break  # File found, no need to search further

    if not file_path:
        logging.warning(
            f"Log file for date {target_date.strftime('%Y-%m-%d')} not found at '{file_path}'"
        )
        # Return empty statistics if the log file for the specific date doesn't exist.
        return TacacsFileLogStatistics(
            parsed_line_count=0,
            log_summary=LogSummary(successful=0, failed=0),
            top_successful_login_users=[],
            top_nas_ips=[],
            top_access_ips=[],
            ip_access_by_users={},
            user_login_breakdown=[],
        )

    logging.info(f"Processing file: {target_filename}")

    with open(file_path, "r") as f:
        for line in f:
            match = LOG_PATTERN.match(line.strip())
            if not match:
                logging.warning(
                    f"Skipping line (does not match required format): {line.strip()}"
                )
                continue

            timestamp_str, nas_ip, username, user_ip, message = match.groups()
            parsed_line_count += 1

            # Update statistics
            access_by_user_ip[user_ip] += 1
            access_by_nas_ip[nas_ip] += 1
            access_by_user_ip_users[user_ip].add(username)

            # We are interested in authentication events
            if "login succeeded" in message:
                logins_by_user[username]["successful"] += 1
                log_summary["successful"] += 1
            elif "login failed" in message:
                logins_by_user[username]["failed"] += 1
                log_summary["failed"] += 1

    successful_logins_by_user = Counter(
        {user: counts["successful"] for user, counts in logins_by_user.items()}
    )

    top_users = [
        TopEntry(name=user, count=count)
        for user, count in successful_logins_by_user.most_common(5)
    ]
    top_nas_ips = [
        TopEntry(name=ip, count=count) for ip, count in access_by_nas_ip.most_common(5)
    ]
    top_ips = [
        TopEntry(name=ip, count=count) for ip, count in access_by_user_ip.most_common(5)
    ]

    ip_users = {
        ip: sorted(list(users)) for ip, users in access_by_user_ip_users.items()
    }

    user_breakdown = [
        UserLoginBreakdown(
            user=user,
            successful=counts.get("successful", 0),
            failed=counts.get("failed", 0),
        )
        for user, counts in sorted(logins_by_user.items())
    ]

    return TacacsFileLogStatistics(
        parsed_line_count=parsed_line_count,
        log_summary=LogSummary(
            successful=log_summary["successful"], failed=log_summary["failed"]
        ),
        top_successful_login_users=top_users,
        top_nas_ips=top_nas_ips,
        top_access_ips=top_ips,
        ip_access_by_users=ip_users,
        user_login_breakdown=user_breakdown,
    )
