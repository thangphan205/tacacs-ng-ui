import re
import sys
import os
from datetime import datetime, timedelta
from collections import Counter

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select
from app.core.config import settings
from app.core.db import engine
from app.models import AuthorizationStatistics

# --- Configuration ---
# The script will process all authorization-*.log files for the previous day.
# It will filter for log entries on the specific date below.
yesterday = datetime.now() - timedelta(days=1)
TARGET_DATE_STR = yesterday.strftime("%Y-%m-%d")

# --- REGEX CONFIGURATION ---
# Regex for the provided log format.
# Example: "2025-12-04 21:20:30 +0700 42.117.111.77	user_admin	ssh	172.20.20.1	tacacs_super_user_profile	permit	junos-exec"
# Example: "2025-12-06 14:56:11 +0700 42.117.111.77	user_level15	vty14	172.20.20.1	tacacs_cisco15_profile	permit	shell	show ip interface brief <cr>"
# Example: "2025-12-06 14:55:28 +0700 42.117.111.77	admin	vty12	3fff:172:20:20::1		deny	shell	ip tacacs source-interface Management0 <cr>"
IP_REGEX = r"([a-fA-F0-9:.]+|[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})"
LOG_REGEX = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \+\d{4})\s+"
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
    # Construct the log file path from settings for the target date
    # This uses the default format from the TacacsNgSetting model
    log_file_format = settings.TACACS_LOG_DIRECTORY + "%Y/%m/authorization-%Y-%m-%d.log"
    log_file_path = yesterday.strftime(log_file_format)

    if not os.path.exists(log_file_path):
        print(f"Log file not found for date {TARGET_DATE_STR}: {log_file_path}")
        return

    print(f"Processing log file for date {TARGET_DATE_STR}: {log_file_path}")

    permitted_authorizations = Counter()
    denied_authorizations = Counter()

    try:
        with open(log_file_path, "r", errors="ignore") as f:
            for line in f:
                # Quick check to ensure the line is for the correct day
                if not line.startswith(TARGET_DATE_STR):
                    continue

                match = LOG_REGEX.search(line)
                if not match:
                    continue

                log_data = match.groupdict()
                message = log_data["message"].strip()

                # We only care about authorization events containing 'permit' or 'deny'
                if "permit" in message or "deny" in message:
                    username = log_data["username"]
                    nas_ip = log_data["nas_ip"]
                    client_ip = log_data["client_ip"]
                    key = (username, nas_ip, client_ip)

                    # Check for permit/deny in the message
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
        print(f"\nNo authorization log entries found for date {TARGET_DATE_STR}.")
        return

    all_keys = set(permitted_authorizations.keys()) | set(denied_authorizations.keys())
    summary_date = yesterday.date()

    # --- Print Statistics ---
    print(f"\n--- Authorization Summary for {summary_date} ---")
    print(f"Total Command Events: {total_events}")
    print(f"  - Permitted: {total_permitted}")
    print(f"  - Denied:    {total_denied}")
    print(f"Unique User/NAS/Client combinations: {len(all_keys)}")
    print("--------------------------------------------------")

    # Save the summary to the database
    save_statistics_to_db(
        summary_date, all_keys, permitted_authorizations, denied_authorizations
    )


def save_statistics_to_db(
    summary_date, all_keys, permitted_authorizations, denied_authorizations
):
    """
    Inserts or updates authorization statistics in the database for a given date.
    """
    print("\nSaving authorization statistics to the database...")
    with Session(engine) as session:
        for username, nas_ip, user_source_ip in sorted(all_keys):
            key = (username, nas_ip, user_source_ip)
            permit_count = permitted_authorizations.get(key, 0)
            deny_count = denied_authorizations.get(key, 0)

            # Check if a record already exists for this combination on this date
            statement = select(AuthorizationStatistics).where(
                AuthorizationStatistics.username == username,
                AuthorizationStatistics.nas_ip == nas_ip,
                AuthorizationStatistics.user_source_ip == user_source_ip,
                AuthorizationStatistics.log_date == summary_date,
            )
            db_stat = session.exec(statement).first()

            if db_stat:
                # Update existing record
                print(f"Updating authorization stats for {username} on {nas_ip}")
                db_stat.permit_count = permit_count
                db_stat.deny_count = deny_count
            else:
                # Create new record
                print(f"Creating new authorization stats for {username} on {nas_ip}")
                db_stat = AuthorizationStatistics(
                    username=username,
                    nas_ip=nas_ip,
                    user_source_ip=user_source_ip,
                    permit_count=permit_count,
                    deny_count=deny_count,
                    log_date=summary_date,
                )
            session.add(db_stat)

        session.commit()
        print("\nAuthorization statistics saved successfully.")


if __name__ == "__main__":
    process_authorization_logs()
