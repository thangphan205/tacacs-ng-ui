import os
import sys
from collections import Counter

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import engine
from app.crud.tacacs_siem import forward_tacacs_event_to_siem
from app.models import AccountingStatistics
from scripts._log_stats_base import (
    get_target_date,
    parse_accounting_logs,
    to_log_datetime,
)


def process_accounting_logs(node_name: str | None = None) -> None:
    """
    Parses accounting logs for a specific date, aggregates start/stop events
    per user/IP, and stores the results in the AccountingStatistics table.
    """
    if node_name is None:
        node_name = settings.NODE_NAME

    summary_date = get_target_date()
    target_date_str = summary_date.strftime("%Y-%m-%d")

    print(
        f"Processing accounting log file for date {target_date_str} (node: {node_name})"
    )

    start_events, stop_events = parse_accounting_logs(
        summary_date, settings.TACACS_LOG_DIRECTORY
    )

    total_starts = sum(start_events.values())
    total_stops = sum(stop_events.values())
    total_events = total_starts + total_stops

    if total_events == 0:
        print(f"\nNo accounting log entries found for date {target_date_str}.")
        return

    all_keys = set(start_events.keys()) | set(stop_events.keys())

    print(f"\n--- Accounting Summary for {summary_date} (node: {node_name}) ---")
    print(f"Total Accounting Events: {total_events}")
    print(f"  - Start Events: {total_starts}")
    print(f"  - Stop Events:  {total_stops}")
    print(f"Unique User/NAS/Client combinations: {len(all_keys)}")
    print("--------------------------------------------------")

    save_statistics_to_db(summary_date, all_keys, start_events, stop_events, node_name)


def save_statistics_to_db(
    summary_date,
    all_keys,
    start_events: Counter,
    stop_events: Counter,
    node_name: str,
) -> None:
    """
    Inserts or updates accounting statistics in the database for a given date and node.
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
                AccountingStatistics.node_name == node_name,
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
                    node_name=node_name,
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
                    "accounting",
                    username,
                    nas_ip,
                    user_source_ip,
                    "start",
                    ts,
                    background=False,
                )
            if stop_events.get(key, 0) > 0:
                forward_tacacs_event_to_siem(
                    "accounting",
                    username,
                    nas_ip,
                    user_source_ip,
                    "stop",
                    ts,
                    background=False,
                )


if __name__ == "__main__":
    process_accounting_logs()
