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
from scripts._log_stats_base import get_target_date, to_log_datetime, parse_authorization_logs


def process_authorization_logs(node_name: str | None = None) -> None:
    """
    Parses authorization logs for a specific date, aggregates command data per
    user/IP, and stores the results in the AuthorizationStatistics table.
    """
    if node_name is None:
        node_name = settings.NODE_NAME

    summary_date = get_target_date()
    target_date_str = summary_date.strftime("%Y-%m-%d")

    print(f"Processing authorization log file for date {target_date_str} (node: {node_name})")

    permitted_authorizations, denied_authorizations = parse_authorization_logs(
        summary_date, settings.TACACS_LOG_DIRECTORY
    )

    total_permitted = sum(permitted_authorizations.values())
    total_denied = sum(denied_authorizations.values())
    total_events = total_permitted + total_denied

    if total_events == 0:
        print(f"\nNo authorization log entries found for date {target_date_str}.")
        return

    all_keys = set(permitted_authorizations.keys()) | set(denied_authorizations.keys())

    print(f"\n--- Authorization Summary for {summary_date} (node: {node_name}) ---")
    print(f"Total Command Events: {total_events}")
    print(f"  - Permitted: {total_permitted}")
    print(f"  - Denied:    {total_denied}")
    print(f"Unique User/NAS/Client combinations: {len(all_keys)}")
    print("--------------------------------------------------")

    save_statistics_to_db(summary_date, all_keys, permitted_authorizations, denied_authorizations, node_name)


def save_statistics_to_db(
    summary_date,
    all_keys,
    permitted_authorizations: Counter,
    denied_authorizations: Counter,
    node_name: str,
) -> None:
    """
    Inserts or updates authorization statistics in the database for a given date and node.
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
                AuthorizationStatistics.node_name == node_name,
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
                    node_name=node_name,
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
