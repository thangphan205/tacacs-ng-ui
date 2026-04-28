import re
import sys
import os
from collections import Counter

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select
from app.core.config import settings
from app.core.db import engine
from app.crud.tacacs_siem import forward_tacacs_event_to_siem
from app.models import AuthorizationStatistics
from scripts._log_stats_base import get_target_date, to_log_datetime, build_log_file_path

# --- REGEX CONFIGURATION ---
# Regex for the provided log format.
# Example: "2025-12-04 21:20:30 +0700 42.117.111.77	user_admin	ssh	172.20.20.1	tacacs_super_user_profile	permit	junos-exec"
# Example: "2025-12-06 14:56:11 +0700 42.117.111.77	user_level15	vty14	172.20.20.1	tacacs_cisco15_profile	permit	shell	show ip interface brief <cr>"
# Example: "2025-12-06 14:55:28 +0700 42.117.111.77	admin	vty12	3fff:172:20:20::1		deny	shell	ip tacacs source-interface Management0 <cr>"
IP_REGEX = r"([a-fA-F0-9:.]+|[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})"
LOG_REGEX = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} [+-]\d{4})\s+"
    rf"(?P<nas_ip>{IP_REGEX})\s+"
    r"(?P<username>[\w.-]+)\s+"
    r"(?P<tty>[\w/.-]+)\s+"  # Capture the tty/port field
    rf"(?P<client_ip>{IP_REGEX})\s+"
    # Optional profile name, followed by the rest of the message (permit/deny + command)
    r"(?:(?P<profile>[\w.-]+)\s+)?(?P<message>.*)$"
)


def process_authorization_logs():
    """
    Parses authorization logs for a specific date, aggregates command data per
    user/IP, and stores the results in the AuthorizationStatistics table.
    """
    summary_date = get_target_date()
    target_date_str = summary_date.strftime("%Y-%m-%d")
    log_file_path = build_log_file_path(summary_date, "authorization", settings.TACACS_LOG_DIRECTORY)

    if not os.path.exists(log_file_path):
        print(f"Log file not found for date {target_date_str}: {log_file_path}")
        return

    print(f"Processing log file for date {target_date_str}: {log_file_path}")

    permitted_authorizations = Counter()
    denied_authorizations = Counter()

    try:
        with open(log_file_path, "r", errors="ignore") as f:
            for line in f:
                if not line.startswith(target_date_str):
                    continue

                match = LOG_REGEX.search(line)
                if not match:
                    continue

                log_data = match.groupdict()
                message = log_data["message"].strip()

                if "permit" in message or "deny" in message:
                    username = log_data["username"]
                    nas_ip = log_data["nas_ip"]
                    client_ip = log_data["client_ip"]
                    key = (username, nas_ip, client_ip)

                    if "permit" in message:
                        permitted_authorizations[key] += 1
                    elif "deny" in message:
                        denied_authorizations[key] += 1
    except IOError as e:
        print(f"Error reading file {log_file_path}: {e}")

    total_permitted = sum(permitted_authorizations.values())
    total_denied = sum(denied_authorizations.values())
    total_events = total_permitted + total_denied

    if total_events == 0:
        print(f"\nNo authorization log entries found for date {target_date_str}.")
        return

    all_keys = set(permitted_authorizations.keys()) | set(denied_authorizations.keys())

    # --- Print Statistics ---
    print(f"\n--- Authorization Summary for {summary_date} ---")
    print(f"Total Command Events: {total_events}")
    print(f"  - Permitted: {total_permitted}")
    print(f"  - Denied:    {total_denied}")
    print(f"Unique User/NAS/Client combinations: {len(all_keys)}")
    print("--------------------------------------------------")

    save_statistics_to_db(summary_date, all_keys, permitted_authorizations, denied_authorizations)


def save_statistics_to_db(summary_date, all_keys, permitted_authorizations, denied_authorizations):
    """
    Inserts or updates authorization statistics in the database for a given date.
    """
    log_dt = to_log_datetime(summary_date)
    print("\nSaving authorization statistics to the database...")
    with Session(engine) as session:
        for username, nas_ip, user_source_ip in sorted(all_keys):
            key = (username, nas_ip, user_source_ip)
            permit_count = permitted_authorizations.get(key, 0)
            deny_count = denied_authorizations.get(key, 0)

            statement = select(AuthorizationStatistics).where(
                AuthorizationStatistics.username == username,
                AuthorizationStatistics.nas_ip == nas_ip,
                AuthorizationStatistics.user_source_ip == user_source_ip,
                AuthorizationStatistics.log_date == log_dt,
            )
            db_stat = session.exec(statement).first()

            if db_stat:
                print(f"Updating authorization stats for {username} on {nas_ip}")
                db_stat.permit_count = permit_count
                db_stat.deny_count = deny_count
            else:
                print(f"Creating new authorization stats for {username} on {nas_ip}")
                db_stat = AuthorizationStatistics(
                    username=username,
                    nas_ip=nas_ip,
                    user_source_ip=user_source_ip,
                    permit_count=permit_count,
                    deny_count=deny_count,
                    log_date=log_dt,
                )
            session.add(db_stat)

        session.commit()
        print("\nAuthorization statistics saved successfully.")

    if settings.SIEM_FORWARD_TACACS_EVENTS:
        ts = log_dt.timestamp()
        for username, nas_ip, user_source_ip in sorted(all_keys):
            key = (username, nas_ip, user_source_ip)
            if permitted_authorizations.get(key, 0) > 0:
                forward_tacacs_event_to_siem(
                    "authorization", username, nas_ip, user_source_ip, "permit", ts, background=False
                )
            if denied_authorizations.get(key, 0) > 0:
                forward_tacacs_event_to_siem(
                    "authorization", username, nas_ip, user_source_ip, "deny", ts, background=False
                )


if __name__ == "__main__":
    process_authorization_logs()
