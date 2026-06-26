import sys
import os
from collections import Counter

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select
from app.core.config import settings
from app.core.db import engine
from app.crud.tacacs_siem import forward_tacacs_event_to_siem
from app.models import AuthenticationStatistics
from scripts._log_stats_base import (
    get_target_date,
    to_log_datetime,
    parse_authentication_logs,
)


def process_authentication_logs(node_name: str | None = None) -> None:
    """
    Parses authentication logs for a specific date, aggregates the data per
    user/IP, and stores the results in the AuthenticationStatistics table.
    """
    if node_name is None:
        node_name = settings.NODE_NAME

    summary_date = get_target_date()
    target_date_str = summary_date.strftime("%Y-%m-%d")

    print(f"Processing authentication log file for date {target_date_str} (node: {node_name})")

    successful_logins, failed_logins = parse_authentication_logs(
        summary_date, settings.TACACS_LOG_DIRECTORY
    )

    total_events = sum(successful_logins.values()) + sum(failed_logins.values())

    if total_events == 0:
        print(f"\nNo authentication log entries found for date {target_date_str}.")
        return

    all_keys = set(successful_logins.keys()) | set(failed_logins.keys())

    print(f"\n--- Authentication Summary for {summary_date} (node: {node_name}) ---")
    print(f"Total Authentication Events: {total_events}")
    print(f"  - Successful: {sum(successful_logins.values())}")
    print(f"  - Failed:     {sum(failed_logins.values())}")
    print(f"Unique User/NAS/Client combinations: {len(all_keys)}")
    print("--------------------------------------------------")
    for username, nas_ip, user_source_ip in sorted(all_keys):
        key = (username, nas_ip, user_source_ip)
        print(
            f"User: {username}, NAS IP: {nas_ip}, Client IP: {user_source_ip} "
            f"=> Success: {successful_logins.get(key, 0)}, Fail: {failed_logins.get(key, 0)}"
        )

    save_statistics_to_db(summary_date, all_keys, successful_logins, failed_logins, node_name)


def save_statistics_to_db(
    summary_date,
    all_keys,
    successful_logins: Counter,
    failed_logins: Counter,
    node_name: str,
) -> None:
    """
    Inserts or updates authentication statistics in the database for a given date and node.
    """
    log_dt = to_log_datetime(summary_date)
    print("\nSaving authentication statistics to the database...")
    with Session(engine) as session:
        for username, nas_ip, user_source_ip in sorted(all_keys):
            key = (username, nas_ip, user_source_ip)
            success_count = successful_logins.get(key, 0)
            fail_count = failed_logins.get(key, 0)

            statement = select(AuthenticationStatistics).where(
                AuthenticationStatistics.username == username,
                AuthenticationStatistics.nas_ip == nas_ip,
                AuthenticationStatistics.user_source_ip == user_source_ip,
                AuthenticationStatistics.log_date == log_dt,
                AuthenticationStatistics.node_name == node_name,
            )
            db_stat = session.exec(statement).first()

            if db_stat:
                print(f"Updating stats for {username} on {nas_ip} from {user_source_ip}")
                db_stat.success_count = success_count
                db_stat.fail_count = fail_count
            else:
                print(f"Creating new stats for {username} on {nas_ip} from {user_source_ip}")
                db_stat = AuthenticationStatistics(
                    username=username,
                    nas_ip=nas_ip,
                    user_source_ip=user_source_ip,
                    success_count=success_count,
                    fail_count=fail_count,
                    log_date=log_dt,
                    node_name=node_name,
                )
            session.add(db_stat)

        session.commit()
        print("\nStatistics saved successfully.")

    if settings.SIEM_FORWARD_TACACS_EVENTS:
        ts = log_dt.timestamp()
        for username, nas_ip, user_source_ip in sorted(all_keys):
            key = (username, nas_ip, user_source_ip)
            if successful_logins.get(key, 0) > 0:
                forward_tacacs_event_to_siem(
                    "authentication", username, nas_ip, user_source_ip, "success", ts, background=False
                )
            if failed_logins.get(key, 0) > 0:
                forward_tacacs_event_to_siem(
                    "authentication", username, nas_ip, user_source_ip, "failed", ts, background=False
                )


if __name__ == "__main__":
    process_authentication_logs()
