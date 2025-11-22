import os
from pathlib import Path
from typing import Any
import subprocess
import tempfile
from sqlmodel import Session, select
from app.models import (
    TacacsConfig,
    TacacsConfigCreate,
    TacacsConfigUpdate,
    TacacsGroup,
    TacacsNgSetting,
    Mavis,
    Host,
    TacacsGroup,
    TacacsUser,
    TacacsConfigPublic,
)
import logging
from fastapi import HTTPException
from app.crud import profiles, rulesets

log = logging.getLogger(__name__)

# Change to default paths for tacacs config and logs
SHARED_BASE_PATH = "/app/tacacs_config_and_logs"
CONFIG_PATH = os.path.join(SHARED_BASE_PATH, "etc")
LOG_PATH = os.path.join(SHARED_BASE_PATH, "log")
CONFIG_FILE_PATH = os.path.join(SHARED_BASE_PATH, "etc/tac_plus-ng.cfg")
LOG_FILE_PATH = os.path.join(SHARED_BASE_PATH, "log")
RELOAD_TRIGGER_PATH = os.path.join(SHARED_BASE_PATH, "restart_trigger.txt")


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

    statement = select(Mavis).limit(1)
    mavis_basic = session.exec(statement).first()
    mavis_info = mavis_basic.model_dump()

    statement = select(Host)
    host_basic = session.exec(statement).all()

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
    log accountinglog {{ destination = {accountinglog} }}
    log authenticationlog {{ destination = {authenticationlog} }}
    access log = accesslog
    accounting log = accountinglog
    authentication log = authenticationlog
    mavis module = external {{
        # Set environment variables for LDAP connection
        setenv LDAP_SERVER_TYPE = "{ldap_server_type}"
        setenv LDAP_HOSTS = "{ldap_hosts}"
        setenv LDAP_BASE = "{ldap_base}"
        setenv LDAP_USER = "{ldap_user}"
        setenv LDAP_PASSWD = "{ldap_passwd}"
        setenv REQUIRE_TACACS_GROUP_PREFIX = 0
        setenv LDAP_FILTER = "{ldap_filter}"
        setenv TACACS_GROUP_PREFIX = "tacacs_"

        exec = /usr/local/lib/mavis/mavis_tacplus-ng_ldap.pl
    }}
    login backend = mavis
    user backend = mavis
    pap backend = mavis""".format(
        addr=tacacs_ng_info["ipv4_address"],
        port=tacacs_ng_info["ipv4_port"],
        inst_min=tacacs_ng_info["instances_min"],
        inst_max=tacacs_ng_info["instances_max"],
        bg=str(tacacs_ng_info["background"]).lower(),
        accesslog=tacacs_ng_info["access_logfile_destination"],
        accountinglog=tacacs_ng_info["accounting_logfile_destination"],
        authenticationlog=tacacs_ng_info["authentication_logfile_destination"],
        ldap_server_type=mavis_info["ldap_server_type"],
        ldap_hosts=mavis_info["ldap_hosts"],
        ldap_base=mavis_info["ldap_base"],
        ldap_user=mavis_info["ldap_user"],
        ldap_passwd=mavis_info["ldap_passwd"],
        ldap_filter=mavis_info["ldap_filter"],
    )
    hosts_template = ""
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

    statement = select(TacacsGroup)
    tacacs_group_basic = session.exec(statement).all()
    tacacs_groups_template = ""
    for tacacs_group in tacacs_group_basic:
        tacacs_group_info = tacacs_group.model_dump()
        tacacs_groups_template += """
    group = {group_name}""".format(
            group_name=tacacs_group_info["group_name"]
        )

    statement = select(TacacsUser)
    tacacs_users_basic = session.exec(statement).all()
    tacacs_users_template = ""
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
        password login = {mavis_type} {mavis_password}
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
        with open(file_path, "r") as f:
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
        log.exception("Exception log: {}".format(e))
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
        return "Path traversal attack detected: {}".format(filename)

    source_file_path = os.path.join(CONFIG_PATH, filename)

    # 1. Read the content from the specified source file
    try:
        if not os.path.exists(source_file_path) or not os.path.isfile(source_file_path):
            return "Source file not found:{}".format(source_file_path)

        with open(source_file_path, "r") as f:
            config_data = f.read()
    except Exception as e:
        return "Error reading source file: {}".format(e)

    # 2. Save the new configuration to the main config file and create a backup
    try:
        # Write new content, overwriting the old file
        with open(CONFIG_FILE_PATH, "w") as f:
            f.write("#!/usr/local/sbin/tac_plus-ng\n")
            f.write("# Tacacs config from {}\n".format(filename))
            f.write("# Description: {}\n".format(db_tacacs_config.description))
            f.write(config_data)

    except Exception as e:
        log.exception("Exception log: {}".format(e))

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

    # 4. Set all other configs to inactive

    statement = select(TacacsConfig).where(TacacsConfig.id != db_tacacs_config.id)
    other_configs = session.exec(statement).all()
    for config in other_configs:
        if config.active:
            config.active = False
            session.add(config)

    tacacs_config_data = tacacs_config_in.model_dump(exclude_unset=True)
    extra_data = {"active": True}
    db_tacacs_config.sqlmodel_update(tacacs_config_data, update=extra_data)
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
        list_of_lines = ["", "", 0, "Syntax check successful."]
        if result.returncode == 0:
            if result.stderr:
                list_of_lines = result.stderr.split(":")
            return {
                "status": "success",
                "raw_output": result.stderr
                or result.stdout
                or "Syntax check successful.",
                "line": list_of_lines[2],
                "message": list_of_lines[3],
            }
        else:
            output = (
                result.stderr or result.stdout or "Unknown error during syntax check."
            )
            return {"status": "error", "output": output}
    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail="`tac_plus-ng` command not found. Is it installed in the container and in the system's PATH?",
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Syntax check command timed out.")
