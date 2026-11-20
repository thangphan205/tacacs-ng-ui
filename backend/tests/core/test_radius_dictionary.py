"""
Custom RADIUS dictionary text is written verbatim inside `id = tac_plus-ng { }`,
so it may hold `radius.dictionary` blocks and nothing else.
"""

import pytest
from pydantic import ValidationError

from app.core.radius_dictionary import (
    MAX_RADIUS_DICTIONARY_BYTES,
    builtin_radius_dictionary,
    check_radius_dictionary,
    normalize_radius_dictionary,
)
from app.models import HostCreate, HostUpdate, TacacsNgSettingUpdate

GOOD = """
# Ubiquiti
radius.dictionary Ubiquiti 41112 {
    attribute Ubiquiti-Admin-Role 1 string
    attribute Ubiquiti-Level 2 integer {
        Read 1
        Admin 2
        802.1X-Only 3
    }
}
radius.dictionary Wide 64999 format = 4, 0 {
    attribute Wide-Role 70000 string
}
radius.dictionary {
    attribute Custom-Standard 241 octets
}
"""


def test_builtin_dictionary_passes_its_own_check() -> None:
    assert check_radius_dictionary(builtin_radius_dictionary()) == []


def test_good_dictionary_is_accepted() -> None:
    assert check_radius_dictionary(GOOD) == []


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        # closing the tac_plus-ng block and adding config
        ("radius.dictionary X 1 { }\n}\nhost evil { address = 0.0.0.0/0 }", "Line 2"),
        ("radius.dictionary X 1 { attribute A 1 string } }", "Line 1"),
        ("include = /etc/passwd", "radius.dictionary"),
        ("radius.dictionary X 1 { attribute include 1 string }", "attribute name"),
        ('radius.dictionary X 1 { attribute "A}" 1 string }', "attribute name"),
        ("radius.dictionary X 1 { attribute A 1 string\n", "end of text"),
        ("radius.dictionary X 1 { attribute A 1 blob }", "attribute type"),
        ("radius.dictionary X 1 { attribute A 0 string }", "at least 1"),
        ("radius.dictionary X 0 { }", "at least 1"),
        ("radius.dictionary X 1 format = 3, 1 { }", "1, 2 or 4"),
        ("radius.dictionary X 1 { attribute A 1 string { Yes 1 } }", "`}`"),
        ("radius.dictionary X 1 { attribute A 1 integer { Yes } }", "value number"),
        (
            "radius.dictionary X 1 {} profile p { script { permit } }",
            "radius.dictionary",
        ),
        ("radius.dictionary X\\ 1 { }", "vendor name"),
        ("radius.dictionary $X 1 { }", "vendor name"),
        ("radius.dictionary X 1 { attribute A 0x10 string }", "attribute number"),
        ("radius.dictionary X 1 { }#comment", "space before `#`"),
    ],
)
def test_bad_dictionary_is_refused(text: str, fragment: str) -> None:
    errors = check_radius_dictionary(text)
    assert errors, text
    assert fragment in " ".join(errors)


def test_oversize_dictionary_is_refused() -> None:
    text = "radius.dictionary X 1 {\n" + "# x\n" * MAX_RADIUS_DICTIONARY_BYTES + "}"
    assert "larger than" in check_radius_dictionary(text)[0]


def test_comments_are_ignored() -> None:
    assert check_radius_dictionary("radius.dictionary X 1 { # } } }\n}") == []


def test_normalize_blank_is_none() -> None:
    assert normalize_radius_dictionary(None) is None
    assert normalize_radius_dictionary("  \n\n ") is None
    with pytest.raises(ValueError):
        normalize_radius_dictionary("}")


def test_settings_update_validates_dictionary_and_ports() -> None:
    TacacsNgSettingUpdate(radius_dictionary_extra=GOOD)
    with pytest.raises(ValidationError):
        TacacsNgSettingUpdate(radius_dictionary_extra="}\nhost x { }")
    with pytest.raises(ValidationError):
        TacacsNgSettingUpdate(radius_auth_port=70000)


# --- host keys ----------------------------------------------------------------


def test_radius_only_host_is_valid() -> None:
    host = HostCreate(
        name="mikrotik", ipv4_address="192.0.2.1/32", radius_secret_key="r4d"
    )
    assert host.secret_key is None


def test_host_needs_some_key_or_a_parent() -> None:
    with pytest.raises(ValidationError):
        HostCreate(name="x", ipv4_address="192.0.2.1/32")
    HostCreate(name="x", ipv4_address="192.0.2.1/32", parent="core")


@pytest.mark.parametrize("field", ["secret_key", "radius_secret_key"])
@pytest.mark.parametrize("value", ['a"b', "a\\b", "a\nb", "a\rb"])
def test_keys_that_would_break_the_config_are_refused(field: str, value: str) -> None:
    for model in (HostCreate, HostUpdate):
        with pytest.raises(ValidationError):
            model(name="x", ipv4_address="192.0.2.1/32", **{field: value})
