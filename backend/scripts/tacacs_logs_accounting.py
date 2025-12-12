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
from app.models import AccountingStatistics

# --- Configuration ---
# The script will process all accounting-*.log files for the previous day.
# It will filter for log entries on the specific date below.
yesterday = datetime.now() - timedelta(days=0)
TARGET_DATE_STR = yesterday.strftime("%Y-%m-%d")

# --- REGEX CONFIGURATION ---
# Regex for the provided log format.
# Example: "2025-12-07 22:00:00 +0700 10.1.1.1	user_admin	tty1	192.168.1.100	start"
# Example: "2025-12-12 22:57:03 +0700 10.1.1.1	user_admin	2	172.20.20.1	start	shell	login
# Example: "2025-12-12 22:57:03 +0700 10.1.1.1	user_admin	2	172.20.20.1	stop	shell	show version <cr>
# Example: "2025-12-12 22:57:28 +0700 10.1.1.1	user_admin	2	172.20.20.1	stop	shell	exit <cr>
# Example: "2025-12-12 22:57:28 +0700 10.1.1.1	user_admin	2	172.20.20.1	stop	shell	logout
# Now supports IPv4 and IPv6 addresses.
IP_REGEX = r"([a-fA-F0-9:.]+|[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})"
LOG_REGEX = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \+\d{4})\s+"
    rf"(?P<nas_ip>{IP_REGEX})\s+"
    r"(?P<username>[\w.-]+)\s+"
    r"(?P<tty>[\w/.-]+)\s+"  # Capture the tty/port field
    rf"(?P<client_ip>{IP_REGEX})\s+"
    # Capture the action (start/stop) and the rest of the message separately
    r"(?P<action>start|stop)\s*(?P<message>.*)$"
)


def process_accounting_logs():
    """
    Parses accounting logs for a specific date, aggregates start/stop events
    per user/IP, and stores the results in the AccountingStatistics table.
    """
    # Construct the log file path from settings for the target date
    # This uses the default format from the TacacsNgSetting model
    log_file_format = settings.TACACS_LOG_DIRECTORY + "%Y/%m/accounting-%Y-%m-%d.log"
    log_file_path = yesterday.strftime(log_file_format)

    if not os.path.exists(log_file_path):
        print(f"Log file not found for date {TARGET_DATE_STR}: {log_file_path}")
        return

    print(f"Processing log file for date {TARGET_DATE_STR}: {log_file_path}")

    start_events = Counter()
    stop_events = Counter()

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
                action = log_data.get("action")

                if action:
                    username = log_data["username"]
                    nas_ip = log_data["nas_ip"]
                    client_ip = log_data["client_ip"]
                    key = (username, nas_ip, client_ip)
                    if action == "start":
                        start_events[key] += 1
                    elif action == "stop":
                        stop_events[key] += 1
    except IOError as e:
        print(f"Error reading file {log_file_path}: {e}")

    total_starts = sum(start_events.values())
    total_stops = sum(stop_events.values())
    total_events = total_starts + total_stops

    if total_events == 0:
        print(f"\nNo accounting log entries found for date {TARGET_DATE_STR}.")
        return

    all_keys = set(start_events.keys()) | set(stop_events.keys())
    summary_date = yesterday.date()

    # --- Print Statistics ---
    print(f"\n--- Accounting Summary for {summary_date} ---")
    print(f"Total Accounting Events: {total_events}")
    print(f"  - Start Events: {total_starts}")
    print(f"  - Stop Events:  {total_stops}")
    print(f"Unique User/NAS/Client combinations: {len(all_keys)}")
    print("--------------------------------------------------")

    # Save the summary to the database
    save_statistics_to_db(summary_date, all_keys, start_events, stop_events)


def save_statistics_to_db(summary_date, all_keys, start_events, stop_events):
    """
    Inserts or updates accounting statistics in the database for a given date.
    """
    print("\nSaving accounting statistics to the database...")
    with Session(engine) as session:
        for username, nas_ip, user_source_ip in sorted(all_keys):
            key = (username, nas_ip, user_source_ip)
            start_count = start_events.get(key, 0)
            stop_count = stop_events.get(key, 0)

            # Check if a record already exists for this combination on this date
            statement = select(AccountingStatistics).where(
                AccountingStatistics.username == username,
                AccountingStatistics.nas_ip == nas_ip,
                AccountingStatistics.user_source_ip == user_source_ip,
                AccountingStatistics.log_date == summary_date,
            )
            db_stat = session.exec(statement).first()

            if db_stat:
                # Update existing record
                print(f"Updating accounting stats for {username} on {nas_ip}")
                db_stat.start_count = start_count
                db_stat.stop_count = stop_count
            else:
                # Create new record
                print(f"Creating new accounting stats for {username} on {nas_ip}")
                db_stat = AccountingStatistics(
                    username=username,
                    nas_ip=nas_ip,
                    user_source_ip=user_source_ip,
                    start_count=start_count,
                    stop_count=stop_count,
                    log_date=summary_date,
                )
            session.add(db_stat)

        session.commit()
        print("\nAccounting statistics saved successfully.")


if __name__ == "__main__":
    process_accounting_logs()
