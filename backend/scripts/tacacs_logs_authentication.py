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
from app.models import AuthenticationStatistics

# --- Configuration ---
# The script will process all authentication-*.log files in the current directory.
# It will filter for log entries on the specific date below.
yesterday = datetime.now() - timedelta(days=0)
TARGET_DATE_STR = yesterday.strftime("%Y-%m-%d")

# --- REGEX CONFIGURATION ---
# Regex for the provided log format.
# Example: "2025-11-23 11:39:08 +0000 103.161.38.106	user_admin		10.3.13.20	shell login failed"
# Now supports IPv4 and IPv6 addresses.
IP_REGEX = r"([a-fA-F0-9:.]+|[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})"
LOG_REGEX = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \+\d{4})\s+"
    rf"(?P<nas_ip>{IP_REGEX})\s+"
    r"(?P<username>[\w.-]+)\s+"
    r"(?:[\w.-]+\s+)?"  # Optional non-capturing group for fields like 'ssh'
    rf"(?P<client_ip>{IP_REGEX})\s+"
    r"(?P<message>.*)$"
)


def process_authentication_logs():
    """
    Parses authentication logs for a specific date, aggregates the data per
    user/IP, and stores the results in the AuthenticationStatistics table.
    """
    # Construct the log file path from settings for the target date
    # This uses the default format from the TacacsNgSetting model
    log_file_format = (
        settings.TACACS_LOG_DIRECTORY + "%Y/%m/authentication-%Y-%m-%d.log"
    )
    log_file_path = yesterday.strftime(log_file_format)

    if not os.path.exists(log_file_path):
        print(f"Log file not found for date {TARGET_DATE_STR}: {log_file_path}")
        return

    print(f"Processing log file for date {TARGET_DATE_STR}: {log_file_path}")

    successful_logins = Counter()
    failed_logins = Counter()

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
                message = log_data["message"]

                # We only care about authentication events for this script
                if "login" in message:
                    username = log_data["username"]
                    nas_ip = log_data["nas_ip"]
                    client_ip = log_data["client_ip"]
                    key = (username, nas_ip, client_ip)
                    if "succeeded" in message:
                        successful_logins[key] += 1
                    else:  # Covers "failed" and "denied"
                        failed_logins[key] += 1
    except IOError as e:
        print(f"Error reading file {log_file_path}: {e}")

    successful_auths = sum(successful_logins.values())
    failed_auths = sum(failed_logins.values())
    total_events = successful_auths + failed_auths

    if total_events == 0:
        print(f"\nNo authentication log entries found for date {TARGET_DATE_STR}.")
        return

    all_keys = set(successful_logins.keys()) | set(failed_logins.keys())
    summary_date = yesterday.date()

    # --- Print Statistics ---
    print(f"\n--- Authentication Summary for {summary_date} ---")
    print(f"Total Authentication Events: {total_events}")
    print(f"  - Successful: {successful_auths}")
    print(f"  - Failed:     {failed_auths}")
    print(f"Unique User/NAS/Client combinations: {len(all_keys)}")
    print("--------------------------------------------------")

    # Save the summary to the database
    save_statistics_to_db(summary_date, all_keys, successful_logins, failed_logins)


def save_statistics_to_db(summary_date, all_keys, successful_logins, failed_logins):
    """
    Inserts or updates authentication statistics in the database for a given date.
    """
    print("\nSaving authentication statistics to the database...")
    with Session(engine) as session:
        for username, nas_ip, user_source_ip in sorted(all_keys):
            key = (username, nas_ip, user_source_ip)
            success_count = successful_logins.get(key, 0)
            fail_count = failed_logins.get(key, 0)

            # Check if a record already exists for this combination on this date
            statement = select(AuthenticationStatistics).where(
                AuthenticationStatistics.username == username,
                AuthenticationStatistics.nas_ip == nas_ip,
                AuthenticationStatistics.user_source_ip == user_source_ip,
                AuthenticationStatistics.log_date == summary_date,
            )
            db_stat = session.exec(statement).first()

            if db_stat:
                # Update existing record
                print(
                    f"Updating stats for {username} on {nas_ip} from {user_source_ip}"
                )
                db_stat.success_count = success_count
                db_stat.fail_count = fail_count
            else:
                # Create new record
                print(
                    f"Creating new stats for {username} on {nas_ip} from {user_source_ip}"
                )
                db_stat = AuthenticationStatistics(
                    username=username,
                    nas_ip=nas_ip,
                    user_source_ip=user_source_ip,
                    success_count=success_count,
                    fail_count=fail_count,
                    log_date=summary_date,
                )
            session.add(db_stat)

        session.commit()
        print("\nStatistics saved successfully.")


if __name__ == "__main__":
    process_authentication_logs()
