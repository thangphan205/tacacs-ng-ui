import os
from pathlib import Path

import pytest
from sqlmodel import Session

from app.crud.tacacs_configs import (
    _parse_syntax_output,
    generate_tacacs_ng_config,
    validate_config_text,
)

TAC_PLUS_NG_BIN = "/usr/local/sbin/tac_plus-ng"


def test_parse_success_empty_output() -> None:
    result = _parse_syntax_output(returncode=0, raw_output="", filename="candidate.cfg")
    assert result["status"] == "success"
    assert result["line"] == 0
    assert result["message"] == "Syntax check successful."


def test_parse_success_with_warning_line() -> None:
    raw = "candidate.cfg:?:7:deprecated directive\n"
    result = _parse_syntax_output(
        returncode=0, raw_output=raw, filename="candidate.cfg"
    )
    assert result["status"] == "success"
    assert result["line"] == 7
    assert result["message"] == "deprecated directive"


def test_parse_error_extracts_line_and_message() -> None:
    raw = "candidate.cfg:?:12:syntax error near '}'\n"
    result = _parse_syntax_output(
        returncode=1, raw_output=raw, filename="candidate.cfg"
    )
    assert result["status"] == "error"
    assert result["line"] == 12
    assert result["message"] == "syntax error near '}'"


def test_parse_error_prefers_line_containing_filename() -> None:
    raw = (
        "starting up\nreading configuration\ncandidate.cfg:?:34:unknown keyword 'foo'\n"
    )
    result = _parse_syntax_output(
        returncode=1, raw_output=raw, filename="candidate.cfg"
    )
    assert result["line"] == 34
    assert result["message"] == "unknown keyword 'foo'"


def test_parse_error_message_may_contain_colons() -> None:
    raw = "candidate.cfg:?:5:bad value: expected int: got 'x'\n"
    result = _parse_syntax_output(
        returncode=1, raw_output=raw, filename="candidate.cfg"
    )
    assert result["line"] == 5
    assert result["message"] == "bad value: expected int: got 'x'"


def test_parse_error_two_part_fallback() -> None:
    raw = "candidate.cfg: cannot open file\n"
    result = _parse_syntax_output(
        returncode=1, raw_output=raw, filename="candidate.cfg"
    )
    assert result["status"] == "error"
    assert result["line"] == 0
    assert result["message"] == "cannot open file"


def test_parse_error_single_part_fallback() -> None:
    raw = "catastrophic failure\n"
    result = _parse_syntax_output(
        returncode=1, raw_output=raw, filename="candidate.cfg"
    )
    assert result["line"] == 0
    assert result["message"] == "catastrophic failure"


def test_parse_error_non_integer_line_keeps_whole_line() -> None:
    raw = "candidate.cfg:?:notanumber:something broke\n"
    result = _parse_syntax_output(
        returncode=1, raw_output=raw, filename="candidate.cfg"
    )
    assert result["line"] == 0
    assert result["message"] == "candidate.cfg:?:notanumber:something broke"


def test_parse_error_empty_output() -> None:
    result = _parse_syntax_output(returncode=1, raw_output="", filename="candidate.cfg")
    assert result["status"] == "error"
    assert result["message"] == "Unknown error during syntax check."
    assert result["raw_output"] == "Unknown error during syntax check."


def test_generate_config_does_not_write_cwd_artifact(db: Session) -> None:
    """generate_tacacs_ng_config must be side-effect free (no cwd artifact).

    It used to write `<cwd>/tacacs-ng.conf` on every call — including on the
    read-only GET /tacacs_configs/preview path, where four uvicorn workers
    raced to write the same file.
    """
    artifact = Path.cwd() / "tacacs-ng.conf"
    assert not artifact.exists(), "stale artifact present before the call"

    generate_tacacs_ng_config(session=db)

    assert not artifact.exists()


@pytest.mark.skipif(
    not os.path.exists(TAC_PLUS_NG_BIN),
    reason="tac_plus-ng binary only present inside the backend container",
)
def test_validate_config_text_rejects_garbage() -> None:
    result = validate_config_text(text="this is not a config {{{\n")
    assert result["status"] == "error"


@pytest.mark.skipif(
    not os.path.exists(TAC_PLUS_NG_BIN),
    reason="tac_plus-ng binary only present inside the backend container",
)
def test_validate_config_text_accepts_generated_config(db: Session) -> None:
    config = generate_tacacs_ng_config(session=db)
    result = validate_config_text(text=config)
    assert result["status"] == "success", result["raw_output"]
