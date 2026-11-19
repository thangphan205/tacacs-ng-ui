import ipaddress
import logging
from collections.abc import Generator
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel import Session

from app.core import security
from app.core.config import settings
from app.core.db import engine
from app.models import TokenPayload, User

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)


def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


logger = logging.getLogger(__name__)

SessionDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]


def get_current_user(session: SessionDep, token: TokenDep) -> User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    user = session.get(User, token_data.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_active_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_user


SuperUser = Annotated[User, Depends(get_current_active_superuser)]


def require_primary_node() -> None:
    if settings.NODE_ROLE == "standby":
        raise HTTPException(
            status_code=403,
            detail="This node is in standby (read-only) mode. Make changes on the primary node.",
        )


@lru_cache(maxsize=8)
def _trusted_proxy_networks(
    raw: str,
) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            networks.append(ipaddress.ip_network(item, strict=False))
        except ValueError:
            logger.warning("Ignoring invalid TRUSTED_PROXIES entry %r", item)
    return tuple(networks)


def _parse_forwarded_entry(
    entry: str,
) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """One X-Forwarded-For element as an address, tolerating what proxies add:
    ``ip:port`` (IPv4), ``[ip]`` and ``[ip]:port`` (IPv6)."""
    entry = entry.strip()
    if entry.startswith("["):
        host, _, rest = entry[1:].partition("]")
        if rest and not (rest.startswith(":") and rest[1:].isdigit()):
            return None
        entry = host
    elif entry.count(":") == 1:
        host, _, port = entry.partition(":")
        if not port.isdigit():
            return None
        entry = host
    try:
        return ipaddress.ip_address(entry)
    except ValueError:
        return None


def _forwarded_client_ip(forwarded_for: str) -> str | None:
    """Client address from X-Forwarded-For, immune to a forged leftmost entry.

    Proxies append on the right, so the caller controls only what sits to the
    left of the first entry a proxy of ours added. Walk from the right, skip
    addresses in ``TRUSTED_PROXIES``; the first one that is not a trusted proxy
    is the client. Works for any chain length, unlike taking the first entry
    (forgeable) or the Nth from the right (wrong behind a different chain).
    A chain made only of trusted addresses (an internal client) yields its
    leftmost entry. An entry that is not an address is skipped.
    """
    trusted = _trusted_proxy_networks(settings.TRUSTED_PROXIES)
    addrs = [
        a
        for a in (_parse_forwarded_entry(p) for p in forwarded_for.split(","))
        if a is not None
    ]
    for addr in reversed(addrs):
        if not any(addr in net for net in trusted):
            return str(addr)
    return str(addrs[0]) if addrs else None


def get_client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Present but unusable: do not fall through to X-Real-IP, which the
        # caller can write. The socket peer is the proxy, a stable if coarse key.
        return _forwarded_client_ip(forwarded_for) or (
            request.client.host if request.client else None
        )
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip[:45]
    return request.client.host if request.client else None
