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


def _forwarded_client_ip(forwarded_for: str) -> str | None:
    """Client address from X-Forwarded-For, immune to a forged leftmost entry.

    Proxies append on the right, so the caller controls only what sits to the
    left of the first entry a proxy of ours added. Walk from the right, skip
    addresses in ``TRUSTED_PROXIES``; the first one that is not a trusted proxy
    is the client. Works for any chain length, unlike taking the first entry
    (forgeable) or the Nth from the right (wrong behind a different chain).
    A chain made only of trusted addresses (an internal client) yields its
    leftmost entry. An unparseable entry ends the walk: nothing is trusted.
    """
    trusted = _trusted_proxy_networks(settings.TRUSTED_PROXIES)
    parts = [p.strip() for p in forwarded_for.split(",") if p.strip()]
    for entry in reversed(parts):
        try:
            addr = ipaddress.ip_address(entry)
        except ValueError:
            return None
        if not any(addr in net for net in trusted):
            return str(addr)
    if parts:
        try:
            return str(ipaddress.ip_address(parts[0]))
        except ValueError:
            return None
    return None


def get_client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        client = _forwarded_client_ip(forwarded_for)
        if client:
            return client
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip[:45]
    return request.client.host if request.client else None
