import ipaddress
import logging
import time
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


def _unmap(
    addr: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    """``::ffff:172.18.0.2`` (a dual-stack socket) is the IPv4 address."""
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        return addr.ipv4_mapped
    return addr


def _is_trusted(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    addr = _unmap(addr)
    return any(
        addr in net
        for net in _trusted_proxy_networks(settings.TRUSTED_PROXIES)
        if net.version == addr.version
    )


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
        return _unmap(ipaddress.ip_address(entry))
    except ValueError:
        return None


def _forwarded_client_ip(forwarded_for: str) -> str | None:
    """Client address from X-Forwarded-For, immune to a forged leftmost entry.

    Proxies append on the right, so the caller controls only what sits to the
    left of the first entry a proxy of ours added. Walk from the right, skip
    addresses in ``TRUSTED_PROXIES``; the first one that is not a trusted proxy
    is the client. Works for any chain length. An entry that is not an address
    is skipped. Only call this for a request whose socket peer is trusted.

    A chain made only of trusted addresses (a client inside a listed range, or
    a list that is too wide) yields its *rightmost* entry, the one our own
    proxy appended. The leftmost would be caller-written. This fails toward a
    shared address, never toward a forgeable one; the fix for that is a
    narrower ``TRUSTED_PROXIES``, which ``_warn_untrusted_forwarder`` and the
    deployment docs point at.
    """
    addrs = [
        a
        for a in (_parse_forwarded_entry(p) for p in forwarded_for.split(","))
        if a is not None
    ]
    for addr in reversed(addrs):
        if not _is_trusted(addr):
            return str(addr)
    return str(addrs[-1]) if addrs else None


_warned_peers: dict[str, float] = {}
_WARN_EVERY_SECONDS = 3600.0


def _warn_untrusted_forwarder(peer: str, forwarded_for: str) -> None:
    """Say why every user may look like one address, once an hour per peer.

    A proxy outside ``TRUSTED_PROXIES`` (a compose network in 10.x or
    192.168.x, say) has its X-Forwarded-For ignored, so each client resolves to
    the proxy and shares one throttle bucket and one audit address. The same
    symptom is a direct caller forging the header; the message covers both.
    """
    now = time.monotonic()
    last = _warned_peers.get(peer)
    if last is not None and now - last < _WARN_EVERY_SECONDS:
        return
    if len(_warned_peers) > 256:
        _warned_peers.clear()
    _warned_peers[peer] = now
    logger.warning(
        "X-Forwarded-For %r arrived from %s, which is not in TRUSTED_PROXIES, so "
        "it is ignored and %s is recorded as the client. If %s is your reverse "
        "proxy, add it (or its network) to TRUSTED_PROXIES, otherwise every user "
        "shares one sign-in throttle bucket; if not, someone is sending the "
        "header directly.",
        forwarded_for[:200],
        peer,
        peer,
        peer,
    )


def get_client_ip(request: Request) -> str | None:
    """The caller's address, believing proxy headers only from our own proxies.

    The socket peer comes from ``RawPeerMiddleware`` (uvicorn overwrites
    ``request.client`` from X-Forwarded-For). A peer that is not in
    ``TRUSTED_PROXIES`` -- a LAN host or anyone reaching the backend port
    directly -- is the client, whatever headers it sends. Behind a trusted peer,
    X-Forwarded-For is walked from the right (see ``_forwarded_client_ip``).
    """
    client = request.scope.get("raw_client") or request.scope.get("client")
    peer = client[0] if client else None
    try:
        peer_addr = _unmap(ipaddress.ip_address(peer)) if peer else None
    except ValueError:
        peer_addr = None
    if peer_addr is None or not _is_trusted(peer_addr):
        if peer_addr is not None and request.headers.get("X-Forwarded-For"):
            _warn_untrusted_forwarder(
                str(peer_addr), request.headers["X-Forwarded-For"]
            )
        return str(peer_addr) if peer_addr else peer
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Present but unusable: do not fall through to X-Real-IP.
        return _forwarded_client_ip(forwarded_for) or str(peer_addr)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        parsed = _parse_forwarded_entry(real_ip)
        if parsed is not None:
            return str(parsed)
    return str(peer_addr)
