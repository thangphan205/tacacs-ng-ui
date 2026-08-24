"""Strip secrets out of generated tac_plus-ng config text.

`Host.secret_key`, `TacacsUser.password` and MAVIS LDAP credentials are emitted
in cleartext by the generators, so any config text handed to an LLM client must
be scrubbed first.

Two passes:

* Pass A (authoritative) replaces the *actual* values read from the database.
  This catches a secret no matter what syntax wrapped it, including raw
  ``ConfigurationOption`` passthrough blocks the generators never parse.
* Pass B (defense in depth) matches the syntactic shapes, for text whose
  provenance is a file on disk rather than the current database rows.

`key = "***REDACTED***"` is still valid tac_plus-ng, so redacted text continues
to pass `tac_plus-ng -P`. What is lost is semantic verification and round-trip
safety — which is why there are no write tools and why `validate_generated_config`
validates the unredacted text entirely server-side.
"""

import re
from collections.abc import Iterable

from sqlmodel import Session, select

from app.models import Host, Mavis, TacacsUser

REDACTED = "***REDACTED***"

# Values shorter than this are too likely to collide with unrelated text.
_MIN_SECRET_LENGTH = 4

_SECRET_MAVIS_KEY = re.compile(r"PASSWD|PASSWORD|SECRET|TOKEN|KEY", re.IGNORECASE)

_KEY_RE = re.compile(r'(\bkey\s*=\s*)"[^"]*"')
_PASSWORD_RE = re.compile(
    r"(password\s+(?:login|pap)\s*=\s*"
    r'(?:clear|des|crypt|mavis|permit|deny)\s*)"[^"]*"'
)
_SETENV_RE = re.compile(
    r'(setenv\s+\w*(?:PASSWD|PASSWORD|SECRET|TOKEN)\w*\s*=\s*)"[^"]*"',
    re.IGNORECASE,
)


def collect_secrets(*, session: Session) -> list[str]:
    """Every secret value that can end up in generated config text."""
    secrets: list[str] = []

    for host in session.exec(select(Host)).all():
        if host.secret_key:
            secrets.append(host.secret_key)

    for user in session.exec(select(TacacsUser)).all():
        if user.password:
            secrets.append(user.password)

    for mavis in session.exec(select(Mavis)).all():
        if mavis.mavis_value and _SECRET_MAVIS_KEY.search(mavis.mavis_key or ""):
            secrets.append(mavis.mavis_value)

    return secrets


def redact_config_text(text: str, *, secrets: Iterable[str] = ()) -> tuple[str, int]:
    """Return (redacted_text, number_of_replacements)."""
    count = 0

    # Pass A — longest first, so a secret that contains another is replaced whole.
    candidates = sorted(
        {s for s in secrets if s and len(s) >= _MIN_SECRET_LENGTH},
        key=len,
        reverse=True,
    )
    for secret in candidates:
        occurrences = text.count(secret)
        if occurrences:
            text = text.replace(secret, REDACTED)
            count += occurrences

    # Pass B — syntactic shapes, skipping anything Pass A already handled.
    def _sub(pattern: re.Pattern[str], value: str) -> str:
        nonlocal count

        def _replace(match: re.Match[str]) -> str:
            nonlocal count
            if match.group(0).endswith(f'"{REDACTED}"'):
                return match.group(0)
            count += 1
            return f'{match.group(1)}"{REDACTED}"'

        return pattern.sub(_replace, value)

    text = _sub(_KEY_RE, text)
    text = _sub(_PASSWORD_RE, text)
    text = _sub(_SETENV_RE, text)

    return text, count
