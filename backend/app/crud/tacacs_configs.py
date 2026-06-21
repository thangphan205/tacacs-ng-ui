import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import httpx
from fastapi import HTTPException
from sqlmodel import Session, select

from app.crud import profiles, rulesets
from app.models import (
    ConfigurationOption,
    Host,
    Mavis,
    TacacsConfig,
    TacacsConfigCreate,
    TacacsConfigUpdate,
    TacacsGroup,
    TacacsNgSetting,
    TacacsUser,
)

log = logging.getLogger(__name__)

# Change to default paths for tacacs config
SHARED_BASE_PATH = "/app/tacacs_config/"
CONFIG_PATH = os.path.join(SHARED_BASE_PATH, "etc")
CONFIG_FILE_PATH = os.path.join(SHARED_BASE_PATH, "etc/tac_plus-ng.cfg")


def generate_tacacs_mavis_setting(*, session: Session) -> Any:
    statement = select(Mavis)
    mavises_db = session.exec(statement).all()
    mavis_template = ""
    for mavis in mavises_db:
        # MAVIS_OVERRIDE_<KEY> env var takes precedence — allows per-zone LDAP server config
        value = os.environ.get(f"MAVIS_OVERRIDE_{mavis.mavis_key}", mavis.mavis_value)
        mavis_template += f"""setenv {mavis.mavis_key}="{value}"
        """

    mavises_template = f"""mavis module = external {{
        # Set environment variables for LDAP connection
        {mavis_template}
        exec = /usr/local/lib/mavis/mavis_tacplus-ng_ldap.pl
    }}"""
    return mavises_template


def reload_active_config_from_db(*, session: Session) -> None:
    """Regenerate tac_plus-ng.cfg from DB state and reload the daemon.

    Used by HA standby auto-sync watcher and the manual sync endpoint.
    """
    config_text = generate_tacacs_ng_config(session=session)
    try:
        os.makedirs(CONFIG_PATH, exist_ok=True)
        with open(CONFIG_FILE_PATH, "w") as f:
            f.write(config_text)
    except OSError as e:
        log.error("Failed to write config file during HA sync: %s", e)
        raise

    try:
        result = subprocess.run(
            ["supervisorctl", "-c", "/etc/supervisor/conf.d/supervisord.conf", "restart", "tacacs"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            log.warning("supervisorctl restart failed during HA sync: %s", result.stderr or result.stdout)
        else:
            log.info("tac_plus-ng reloaded via HA sync.")
    except Exception as e:
        log.warning("Failed to reload tac_plus-ng during HA sync: %s", e)


def generate_tacacs_ng_config(*, session: Session) -> Any:
    """
    Generate TACACS+ configuration file content based on database settings.
    1. Fetch TacacsNgSetting, Mavis, Hosts, TacacsGroups, TacacsUsers, Profiles, and Rulesets from the database.
    2. Construct the TACACS+ configuration file content as a string.
    3. Write the configuration to a temporary file and return the file path.
    4. If writing to a temp file fails, return the configuration content as a string.
    5. Return the configuration content.
    6. Handle any exceptions that may occur during file operations.
    7. Ensure proper formatting of the configuration file according to TACACS+ syntax.
    8. Use the 'profiles' and 'rulesets' modules to generate their respective sections.
    9. Return the configuration content as a string.
    """

    statement = select(TacacsNgSetting).limit(1)
    tacacs_ng_basic = session.exec(statement).first()
    tacacs_ng_info = tacacs_ng_basic.model_dump()

    mavises_template = generate_tacacs_mavis_setting(session=session)

    config_file_template = """#!/usr/local/sbin/tac_plus-ng
id = spawnd {{
    listen = {{
        address = {addr}
        port = {port}
    }}
    spawn = {{
        instances min = {inst_min}
        instances max = {inst_max}
    }}
    background = {bg}
}}
id = tac_plus-ng {{
    log accesslog {{ destination = {accesslog} }}
    log authenticationlog {{ destination = {authenticationlog} }}
    log authorizationlog {{ destination = {authorizationlog} }}
    log accountinglog {{ destination = {accountinglog} }}
    
    access log = accesslog
    authentication log = authenticationlog
    authorization log = authorizationlog
    accounting log = accountinglog
    
    {mavises_template}

    login backend = mavis
    user backend = mavis
    pap backend = mavis""".format(
        addr=tacacs_ng_info["ipv4_address"],
        port=tacacs_ng_info["ipv4_port"],
        inst_min=tacacs_ng_info["instances_min"],
        inst_max=tacacs_ng_info["instances_max"],
        bg=str(tacacs_ng_info["background"]).lower(),
        accesslog=tacacs_ng_info["access_logfile_destination"],
        authenticationlog=tacacs_ng_info["authentication_logfile_destination"],
        authorizationlog=tacacs_ng_info["authorization_logfile_destination"],
        accountinglog=tacacs_ng_info["accounting_logfile_destination"],
        mavises_template=mavises_template,
    )

    # Begin host
    hosts_template = ""
    statement_configuration_host = select(ConfigurationOption).where(
        ConfigurationOption.name == "host"
    )
    configuration_host_options = session.exec(statement_configuration_host).all()
    if configuration_host_options:
        for configuration_host_option in configuration_host_options:
            hosts_template += "\n   # Host Configuration Options"
            hosts_template += f"""   {configuration_host_option.config_option}\n"""
            hosts_template += "\n    # End of Host Configuration Options\n"
    statement = select(Host).where(Host.generate_config == True)
    host_basic = session.exec(statement).all()

    for host in host_basic:
        host_info = host.model_dump()
        hosts_template += """   
    host = {host_name} {{
        address = {host_address}
        key = "{host_key}"
    }}""".format(
            host_name=host_info["name"],
            host_address=host_info["ipv4_address"],
            host_key=host_info["secret_key"],
        )

    statement_configuration_group = select(ConfigurationOption).where(
        ConfigurationOption.name == "group"
    )
    configuration_group_options = session.exec(statement_configuration_group).all()
    tacacs_groups_template = ""
    if configuration_group_options:
        tacacs_groups_template += "\n    # Group Configuration Options\n"
        for configuration_group_option in configuration_group_options:
            tacacs_groups_template += (
                f"""    {configuration_group_option.config_option}\n"""
            )
        tacacs_groups_template += "    # End of Group Configuration Options\n"
    statement = select(TacacsGroup).where(TacacsGroup.generate_config == True)
    tacacs_group_basic = session.exec(statement).all()

    for tacacs_group in tacacs_group_basic:
        tacacs_group_info = tacacs_group.model_dump()
        tacacs_groups_template += """
    group = {group_name}""".format(group_name=tacacs_group_info["group_name"])

    # Begin user
    statement_configuration_user = select(ConfigurationOption).where(
        ConfigurationOption.name == "user"
    )
    configuration_user_options = session.exec(statement_configuration_user).all()
    tacacs_users_template = ""
    if configuration_user_options:
        tacacs_users_template += "\n    # User Configuration Options\n"
        for configuration_user_option in configuration_user_options:
            tacacs_users_template += (
                f"""    {configuration_user_option.config_option}\n"""
            )
        tacacs_users_template += "    # End of User Configuration Options\n"

    statement = select(TacacsUser).where(TacacsUser.generate_config == True)
    tacacs_users_basic = session.exec(statement).all()

    for tacacs_user in tacacs_users_basic:
        tacacs_user_info = tacacs_user.model_dump()
        if tacacs_user_info["password_type"] == "mavis":
            tacacs_users_template += """
    user {username} {{
        password login = mavis
        member = {member}
    }}""".format(
                username=tacacs_user_info["username"],
                member=tacacs_user_info["member"],
            )
        else:
            tacacs_users_template += """
    user {username} {{
        password login = {mavis_type} "{mavis_password}"
        member = {member}
    }}""".format(
                username=tacacs_user_info["username"],
                mavis_type=tacacs_user_info["password_type"],
                mavis_password=tacacs_user_info["password"],
                member=tacacs_user_info["member"],
            )

    # Begin profile
    tacacs_profiles_template = profiles.profile_generator(session=session)
    # Begin ruleset
    tacacs_rulesets_template = rulesets.ruleset_generator(session=session)

    config_file_template += (
        hosts_template
        + tacacs_groups_template
        + tacacs_users_template
        + tacacs_profiles_template
        + tacacs_rulesets_template
        + "\n}\n"
    )

    config_path = Path.cwd() / "tacacs-ng.conf"
    try:
        config_path.write_text(config_file_template, encoding="utf-8")
    except OSError:
        tf = tempfile.NamedTemporaryFile(
            delete=False, suffix=".conf", prefix="tacacs-ng-"
        )
        tf.write(config_file_template.encode("utf-8"))
        tf.close()
        config_path = Path(tf.name)

    return config_file_template


def _notify_peer_reload() -> None:
    """Fire-and-forget call to peer node's internal reload endpoint (auto-sync mode only)."""
    from app.core.config import settings  # local import avoids circular dep

    if settings.NODE_ROLE != "primary" or settings.SYNC_MODE != "auto":
        return
    if not settings.PEER_BACKEND_URL or not settings.INTERNAL_SYNC_TOKEN:
        return

    url = f"{settings.PEER_BACKEND_URL.rstrip('/')}/api/v1/sync/internal/reload-config"
    try:
        with httpx.Client(timeout=10) as client:
            r = client.post(url, headers={"X-Internal-Token": settings.INTERNAL_SYNC_TOKEN})
        if r.status_code != 200:
            log.warning("Peer reload returned HTTP %s: %s", r.status_code, r.text)
        else:
            log.info("Peer node reloaded config successfully.")
    except Exception as e:
        log.warning("Failed to notify peer node for config reload: %s", e)


def get_tacacs_config_by_name(*, session: Session, name: str) -> TacacsConfig | None:
    statement = select(TacacsConfig).where(TacacsConfig.filename == name)
    session_tacacs_config = session.exec(statement).first()
    return session_tacacs_config


def get_tacacs_config_by_filename(filename: str) -> str | None:
    # Basic security check to prevent directory traversal
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    file_path = os.path.join(CONFIG_PATH, filename + ".cfg")

    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        raise HTTPException(
            status_code=404,
            detail=f"Configuration file '{filename}' not found.",
        )

    try:
        with open(file_path) as f:
            content = f.read()
        return content
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error reading config file '{filename}': {e}"
        )


def generate_preview_tacacs_config(*, session: Session) -> Any:
    tacacs_config = generate_tacacs_ng_config(session=session)
    return tacacs_config


def create_tacacs_config(
    *, session: Session, tacacs_config_create: TacacsConfigCreate
) -> TacacsConfig:
    tacacs_config = generate_tacacs_ng_config(session=session)

    # 1. Create a unique filename and save the content

    filepath = os.path.join(CONFIG_PATH, tacacs_config_create.filename + ".cfg")

    try:
        with open(filepath, "w") as f:
            f.write(tacacs_config)
    except Exception as e:
        log.exception(f"Exception log: {e}")
        return False

    # 2. Save the filename to the database
    db_obj = TacacsConfig.model_validate(tacacs_config_create)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_tacacs_config(
    *,
    session: Session,
    db_tacacs_config: TacacsConfig,
    tacacs_config_in: TacacsConfigUpdate,
) -> Any:
    filename = db_tacacs_config.filename + ".cfg"
    # Basic security check to prevent directory traversal
    if ".." in filename or "/" in filename:
        return f"Path traversal attack detected: {filename}"

    source_file_path = os.path.join(CONFIG_PATH, filename)

    # 1. If configuration data is provided, save it to the candidate config file on disk first
    if tacacs_config_in.data is not None:
        try:
            with open(source_file_path, "w", encoding="utf-8") as f:
                f.write(tacacs_config_in.data)
        except Exception as e:
            return f"Error writing source file: {e}"

    # Determine if we should perform activation logic (default to True if active is not specified for backwards compatibility)
    should_activate = (
        tacacs_config_in.active if tacacs_config_in.active is not None else True
    )

    if should_activate:
        # Read the content from the specified source file
        try:
            if not os.path.exists(source_file_path) or not os.path.isfile(
                source_file_path
            ):
                return f"Source file not found:{source_file_path}"

            with open(source_file_path) as f:
                config_data = f.read()
        except Exception as e:
            return f"Error reading source file: {e}"

        # 2. Save the new configuration to the main config file and create a backup
        try:
            # Write new content, overwriting the old file
            with open(CONFIG_FILE_PATH, "w") as f:
                f.write("#!/usr/local/sbin/tac_plus-ng\n")
                f.write(f"# Tacacs config from {filename}\n")
                f.write(f"# Description: {db_tacacs_config.description}\n")
                f.write(config_data)

        except Exception as e:
            log.exception(f"Exception log: {e}")

        # 3. Trigger automatic reload
        try:
            # Reload tac_plus-ng using supervisorctl
            result = subprocess.run(
                [
                    "supervisorctl",
                    "-c",
                    "/etc/supervisor/conf.d/supervisord.conf",
                    "restart",
                    "tacacs",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                log.warning(
                    f"Supervisorctl reload failed: {result.stderr or result.stdout}"
                )
            else:
                log.info("tac_plus-ng reloaded via supervisorctl.")
        except Exception as e:
            log.warning(f"Failed to reload tac_plus-ng via supervisorctl: {e}")

        # 4. Notify peer (standby) node to sync config if auto-sync is enabled
        _notify_peer_reload()

        # 4. Set all other configs to inactive
        statement = select(TacacsConfig).where(TacacsConfig.id != db_tacacs_config.id)
        other_configs = session.exec(statement).all()
        for config in other_configs:
            if config.active:
                config.active = False
                session.add(config)

    # 5. Update database object
    tacacs_config_data = tacacs_config_in.model_dump(exclude_unset=True)
    # Remove 'data' as it's not a database column
    tacacs_config_data.pop("data", None)

    # If active was not set, force it to False to prevent DB activation
    if tacacs_config_in.active is None and not should_activate:
        tacacs_config_data["active"] = False
    elif tacacs_config_in.active is not None:
        tacacs_config_data["active"] = tacacs_config_in.active

    db_tacacs_config.sqlmodel_update(tacacs_config_data)
    session.add(db_tacacs_config)
    session.commit()
    session.refresh(db_tacacs_config)

    return db_tacacs_config


def delete_tacacs_config(*, session: Session, db_tacacs_config: TacacsConfig) -> Any:
    filename = db_tacacs_config.filename + ".cfg"
    # Basic security check to prevent directory traversal
    if ".." in filename or "/" in filename:
        # This should ideally not happen if data is controlled, but as a safeguard.
        log.error(f"Attempted to delete a file with an invalid path: {filename}")
        return None

    file_path = os.path.join(CONFIG_PATH, filename)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        try:
            os.remove(file_path)
        except OSError as e:
            log.error(f"Error removing file {file_path}: {e}")
            # Decide if you want to stop the DB deletion if file deletion fails.
            # For now, we'll proceed to delete the DB record.

    session.delete(db_tacacs_config)
    session.commit()
    return db_tacacs_config


def get_active_tacacs_config(*, session: Session) -> TacacsConfig | None:
    statement = select(TacacsConfig).where(TacacsConfig.active == True)
    active_tacacs_config = session.exec(statement).first()

    return active_tacacs_config


def check_tacacs_config_by_id(*, session: Session, id: int) -> dict[str, Any]:
    """
    Check the syntax of a TACACS+ config file by running 'tac_plus-ng -P configfile.cfg'
    inside the tac_plus-ng container using Docker.
    """
    # Get the config object from DB
    config_obj = session.get(TacacsConfig, id)
    if not config_obj:
        raise HTTPException(status_code=404, detail=f"Config with id {id} not found.")

    filename = config_obj.filename + ".cfg"
    # Since both services are in the same container, we can use the shared path directly.
    config_file_path = os.path.join(CONFIG_PATH, filename)

    # Build the command to call the binary directly
    command = [
        "/usr/local/sbin/tac_plus-ng",
        "-P",
        config_file_path,
    ]

    try:
        result = subprocess.run(
            command, capture_output=True, text=True, check=False, timeout=10
        )
        logging.info(f"Command error: {result.stderr}")
        raw_output = result.stderr or result.stdout or ""
        line = 0
        message = "Syntax check successful."

        if result.returncode == 0:
            status = "success"
            if raw_output:
                lines = [
                    line_str.strip()
                    for line_str in raw_output.splitlines()
                    if line_str.strip()
                ]
                if lines:
                    parts = lines[0].split(":")
                    if len(parts) >= 4:
                        try:
                            line = int(parts[2].strip())
                            message = ":".join(parts[3:]).strip()
                        except ValueError:
                            message = lines[0]
                    elif len(parts) >= 2:
                        message = ":".join(parts[1:]).strip()
                    else:
                        message = lines[0]
        else:
            status = "error"
            if raw_output:
                lines = [
                    line_str.strip()
                    for line_str in raw_output.splitlines()
                    if line_str.strip()
                ]
                if lines:
                    # Find a line containing the filename to extract the exact error details
                    matched_line = None
                    for line_item in lines:
                        if filename in line_item and len(line_item.split(":")) >= 4:
                            matched_line = line_item
                            break
                    if not matched_line:
                        matched_line = lines[0]

                    parts = matched_line.split(":")
                    if len(parts) >= 4:
                        try:
                            line = int(parts[2].strip())
                            message = ":".join(parts[3:]).strip()
                        except ValueError:
                            message = matched_line
                    elif len(parts) >= 2:
                        message = ":".join(parts[1:]).strip()
                    else:
                        message = matched_line
            else:
                message = "Unknown error during syntax check."

        return {
            "status": status,
            "raw_output": raw_output or message,
            "line": line,
            "message": message,
        }
    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail="`tac_plus-ng` command not found. Is it installed in the container and in the system's PATH?",
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Syntax check command timed out.")
