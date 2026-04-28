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
from scripts._log_stats_base import AUTH_LOG_REGEX, get_target_date, to_log_datetime, build_log_file_path


def process_authentication_logs():
    """
    Parses authentication logs for a specific date, aggregates the data per
    user/IP, and stores the results in the AuthenticationStatistics table.
    """
    summary_date = get_target_date()
    target_date_str = summary_date.strftime("%Y-%m-%d")
    log_file_path = build_log_file_path(summary_date, "authentication", settings.TACACS_LOG_DIRECTORY)

    if not os.path.exists(log_file_path):
        print(f"Log file not found for date {target_date_str}: {log_file_path}")
        return

    print(f"Processing log file for date {target_date_str}: {log_file_path}")

    successful_logins = Counter()
    failed_logins = Counter()

    try:
        with open(log_file_path, "r", errors="ignore") as f:
            for line in f:
                if not line.startswith(target_date_str):
                    continue

                match = AUTH_LOG_REGEX.search(line)
                if not match:
                    continue

                log_data = match.groupdict()
                message = log_data["message"]

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
        print(f"\nNo authentication log entries found for date {target_date_str}.")
        return

    all_keys = set(successful_logins.keys()) | set(failed_logins.keys())

    # --- Print Statistics ---
    print(f"\n--- Authentication Summary for {summary_date} ---")
    print(f"Total Authentication Events: {total_events}")
    print(f"  - Successful: {successful_auths}")
    print(f"  - Failed:     {failed_auths}")
    print(f"Unique User/NAS/Client combinations: {len(all_keys)}")
    print("--------------------------------------------------")
    for username, nas_ip, user_source_ip in sorted(all_keys):
        key = (username, nas_ip, user_source_ip)
        success_count = successful_logins.get(key, 0)
        fail_count = failed_logins.get(key, 0)
        print(
            f"User: {username}, NAS IP: {nas_ip}, Client IP: {user_source_ip} "
            f"=> Success: {success_count}, Fail: {fail_count}"
        )

    save_statistics_to_db(summary_date, all_keys, successful_logins, failed_logins)


def save_statistics_to_db(summary_date, all_keys, successful_logins, failed_logins):
    """
    Inserts or updates authentication statistics in the database for a given date.
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
