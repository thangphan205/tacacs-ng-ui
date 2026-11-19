import ipaddress
import logging
import os
import threading
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
from starlette.datastructures import Headers
from starlette.types import Scope

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


_Network = ipaddress.IPv4Network | ipaddress.IPv6Network
_Address = ipaddress.IPv4Address | ipaddress.IPv6Address

AUTO_TRUSTED_PROXIES = "auto"
_LOOPBACK: tuple[_Network, ...] = (
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
)
_ROUTE_FILE = "/proc/net/route"
_NET_CLASS_DIR = "/sys/class/net"
# Interface names that exist only in a host's own network namespace. Seeing
# one means the backend runs with host networking, where "the networks I am
# attached to" is the office LAN, not a compose network of proxies.
_HOST_NETNS_PREFIXES = (
    "docker0",
    "br-",
    "veth",
    "cni",
    "flannel",
    "cali",
    "vxlan",
    "weave",
    "kube-",
    "podman",
)
_AUTO_REFRESH_SECONDS = 300.0


@lru_cache(maxsize=8)
def _explicit_networks(raw: str) -> tuple[_Network, ...]:
    networks: list[_Network] = []
    for item in raw.split(","):
        item = item.strip()
        if not item or item.lower() == AUTO_TRUSTED_PROXIES:
            continue
        try:
            networks.append(ipaddress.ip_network(item, strict=False))
        except ValueError:
            logger.warning("Ignoring invalid TRUSTED_PROXIES entry %r", item)
    return tuple(networks)


def _hex_ipv4(value: str) -> ipaddress.IPv4Address:
    """An address as /proc/net/route prints it (hex, host byte order)."""
    return ipaddress.IPv4Address(int(value, 16).to_bytes(4, "little"))


def attached_networks(
    route_table: str, interfaces: list[str]
) -> tuple[tuple[_Network, ...], frozenset[_Address]]:
    """The IPv4 networks this container is directly attached to, and the
    addresses inside them that are not proxies.

    From ``/proc/net/route``: a route with no gateway is a network an interface
    sits on (each compose network the backend joins: ``default``,
    ``traefik-public``), which is where the frontend's nginx and Traefik live.
    Excluded inside them: every gateway the table names, and each network's
    first host address -- Docker's bridge gateway, i.e. the host, from which a
    published port's userland proxy would forward any LAN caller.

    Empty under host networking (see ``_HOST_NETNS_PREFIXES``): the attached
    network would then be the office LAN, whose clients must never be skipped
    as proxy hops.
    """
    host_netns = [name for name in interfaces if name.startswith(_HOST_NETNS_PREFIXES)]
    if host_netns:
        logger.warning(
            "TRUSTED_PROXIES=auto: interface %s means this container shares the "
            "host's network, so only loopback is trusted. Set TRUSTED_PROXIES to "
            "your reverse proxy's address.",
            host_netns[0],
        )
        return (), frozenset()
    networks: list[_Network] = []
    excluded: set[_Address] = set()
    for line in route_table.splitlines()[1:]:
        fields = line.split()
        if len(fields) < 8 or fields[0] == "lo":
            continue
        try:
            destination = _hex_ipv4(fields[1])
            gateway = _hex_ipv4(fields[2])
            mask = _hex_ipv4(fields[7])
            flags = int(fields[3], 16)
        except ValueError:
            continue
        if not flags & 0x1:  # RTF_UP
            continue
        if int(gateway):
            excluded.add(gateway)
            continue
        if not int(destination):
            continue
        try:
            network = ipaddress.IPv4Network(f"{destination}/{mask}")
        except ValueError:
            continue
        networks.append(network)
        if network.num_addresses > 2:
            excluded.add(network.network_address + 1)
    return tuple(networks), frozenset(excluded)


def _read_attached_networks() -> tuple[tuple[_Network, ...], frozenset[_Address]]:
    try:
        with open(_ROUTE_FILE) as fh:
            route_table = fh.read()
    except OSError:
        return (), frozenset()  # not Linux (a developer's host): loopback only
    try:
        interfaces = os.listdir(_NET_CLASS_DIR)
    except OSError:
        interfaces = []
    return attached_networks(route_table, interfaces)


_auto_cache: tuple[float, tuple[_Network, ...], frozenset[_Address]] | None = None
_auto_lock = threading.Lock()


def _auto_networks() -> tuple[tuple[_Network, ...], frozenset[_Address]]:
    """``attached_networks`` for this container, re-read every few minutes so
    a ``docker network connect`` is picked up without a restart."""
    global _auto_cache
    now = time.monotonic()
    with _auto_lock:
        cached = _auto_cache
        if cached is not None and now - cached[0] < _AUTO_REFRESH_SECONDS:
            return cached[1], cached[2]
        networks, excluded = _read_attached_networks()
        if cached is None or (cached[1], cached[2]) != (networks, excluded):
            logger.info(
                "TRUSTED_PROXIES=auto: trusting loopback and %s (excluding %s)",
                ", ".join(str(n) for n in networks) or "no attached network",
                ", ".join(sorted(str(a) for a in excluded)) or "nothing",
            )
        _auto_cache = (now, networks, excluded)
        return networks, excluded


def _uses_auto(raw: str) -> bool:
    return AUTO_TRUSTED_PROXIES in (p.strip().lower() for p in raw.split(","))


def _unmap(addr: _Address) -> _Address:
    """``::ffff:172.18.0.2`` (a dual-stack socket) is the IPv4 address."""
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        return addr.ipv4_mapped
    return addr


def _is_trusted(addr: _Address) -> bool:
    addr = _unmap(addr)

    def _within(networks: tuple[_Network, ...]) -> bool:
        return any(addr in net for net in networks if net.version == addr.version)

    raw = settings.TRUSTED_PROXIES
    if _within(_explicit_networks(raw)):
        return True
    if not _uses_auto(raw):
        return False
    if _within(_LOOPBACK):
        return True
    # The exclusions narrow only what auto found; an address listed
    # explicitly (above) is trusted even if it is a gateway.
    attached, excluded = _auto_networks()
    return addr not in excluded and _within(attached)


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

    A proxy outside ``TRUSTED_PROXIES`` (an ingress controller on another
    node's subnet, or any proxy under host networking) has its X-Forwarded-For
    ignored, so each client resolves to
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


def resolve_client_ip(scope: Scope) -> str | None:
    """The caller's address, believing proxy headers only from our own proxies.

    Takes the ASGI scope so non-route code (the MCP mount's API-key allow-list)
    resolves it exactly as the routes do. The socket peer comes from
    ``RawPeerMiddleware`` (``scope["raw_client"]``; ProxyHeadersMiddleware
    overwrites ``scope["client"]`` from X-Forwarded-For). A peer that is not in ``TRUSTED_PROXIES`` -- a LAN host or
    anyone reaching the backend port directly -- is the client, whatever headers
    it sends. Behind a trusted peer, X-Forwarded-For is walked from the right
    (see ``_forwarded_client_ip``).
    """
    headers = Headers(scope=scope)
    # Only ``raw_client``: ``scope["client"]`` is what ProxyHeadersMiddleware
    # rewrites from the caller's X-Forwarded-For, so falling back to it (a
    # missing key, a unix-socket listener) would read a forged address as the
    # peer. No recorded peer means an unknown one.
    client = scope.get("raw_client")
    peer = client[0] if client else None
    try:
        peer_addr = _unmap(ipaddress.ip_address(peer)) if peer else None
    except ValueError:
        peer_addr = None
    # Every X-Forwarded-For line, in order: a proxy that adds its own line
    # (HAProxy's ``option forwardfor``) rather than appending to the caller's
    # leaves the caller-written one first, so reading only the first line would
    # believe the forgery. RFC 9110 makes repeated lines one comma list, which
    # is also how uvicorn's ProxyHeadersMiddleware reads them.
    forwarded_for = ", ".join(headers.getlist("X-Forwarded-For"))
    if peer_addr is None or not _is_trusted(peer_addr):
        if peer_addr is not None and forwarded_for:
            _warn_untrusted_forwarder(str(peer_addr), forwarded_for)
        return str(peer_addr) if peer_addr else peer
    if forwarded_for:
        # Present but unusable: do not fall through to X-Real-IP.
        return _forwarded_client_ip(forwarded_for) or str(peer_addr)
    real_ip = headers.get("X-Real-IP")
    if real_ip:
        parsed = _parse_forwarded_entry(real_ip)
        if parsed is not None:
            return str(parsed)
    return str(peer_addr)


def get_client_ip(request: Request) -> str | None:
    return resolve_client_ip(request.scope)
