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
from app.models import AccountingStatistics
from scripts._log_stats_base import get_target_date, to_log_datetime, build_log_file_path

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
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} [+-]\d{4})\s+"
    rf"(?P<nas_ip>{IP_REGEX})\s+"
    r"(?P<username>[\w.-]+)\s+"
    r"(?P<tty>[\w/.-]+)\s+"  # Capture the tty/port field
    rf"(?P<client_ip>{IP_REGEX})\s+"
    r"(?P<action>start|stop)\s*(?P<message>.*)$"
)


def process_accounting_logs():
    """
    Parses accounting logs for a specific date, aggregates start/stop events
    per user/IP, and stores the results in the AccountingStatistics table.
    """
    summary_date = get_target_date()
    target_date_str = summary_date.strftime("%Y-%m-%d")
    log_file_path = build_log_file_path(summary_date, "accounting", settings.TACACS_LOG_DIRECTORY)

    if not os.path.exists(log_file_path):
        print(f"Log file not found for date {target_date_str}: {log_file_path}")
        return

    print(f"Processing log file for date {target_date_str}: {log_file_path}")

    start_events = Counter()
    stop_events = Counter()

    try:
        with open(log_file_path, "r", errors="ignore") as f:
            for line in f:
                if not line.startswith(target_date_str):
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
        print(f"\nNo accounting log entries found for date {target_date_str}.")
        return

    all_keys = set(start_events.keys()) | set(stop_events.keys())

    # --- Print Statistics ---
    print(f"\n--- Accounting Summary for {summary_date} ---")
    print(f"Total Accounting Events: {total_events}")
    print(f"  - Start Events: {total_starts}")
    print(f"  - Stop Events:  {total_stops}")
    print(f"Unique User/NAS/Client combinations: {len(all_keys)}")
    print("--------------------------------------------------")

    save_statistics_to_db(summary_date, all_keys, start_events, stop_events)


def save_statistics_to_db(summary_date, all_keys, start_events, stop_events):
    """
    Inserts or updates accounting statistics in the database for a given date.
    """
    log_dt = to_log_datetime(summary_date)
    print("\nSaving accounting statistics to the database...")
    with Session(engine) as session:
        for username, nas_ip, user_source_ip in sorted(all_keys):
            key = (username, nas_ip, user_source_ip)
            start_count = start_events.get(key, 0)
            stop_count = stop_events.get(key, 0)

            statement = select(AccountingStatistics).where(
                AccountingStatistics.username == username,
                AccountingStatistics.nas_ip == nas_ip,
                AccountingStatistics.user_source_ip == user_source_ip,
                AccountingStatistics.log_date == log_dt,
            )
            db_stat = session.exec(statement).first()

            if db_stat:
                print(f"Updating accounting stats for {username} on {nas_ip}")
                db_stat.start_count = start_count
                db_stat.stop_count = stop_count
            else:
                print(f"Creating new accounting stats for {username} on {nas_ip}")
                db_stat = AccountingStatistics(
                    username=username,
                    nas_ip=nas_ip,
                    user_source_ip=user_source_ip,
                    start_count=start_count,
                    stop_count=stop_count,
                    log_date=log_dt,
                )
            session.add(db_stat)

        session.commit()
        print("\nAccounting statistics saved successfully.")

    if settings.SIEM_FORWARD_TACACS_EVENTS:
        ts = log_dt.timestamp()
        for username, nas_ip, user_source_ip in sorted(all_keys):
            key = (username, nas_ip, user_source_ip)
            if start_events.get(key, 0) > 0:
                forward_tacacs_event_to_siem(
                    "accounting", username, nas_ip, user_source_ip, "start", ts, background=False
                )
            if stop_events.get(key, 0) > 0:
                forward_tacacs_event_to_siem(
                    "accounting", username, nas_ip, user_source_ip, "stop", ts, background=False
                )


if __name__ == "__main__":
    process_accounting_logs()
