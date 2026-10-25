import ipaddress
import socket
from urllib.parse import urlsplit

from app.core.config import settings

BLOCKED_HOSTNAMES = {"localhost", "localhost.localdomain"}

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


class UnsafeTargetError(ValueError):
    pass

def is_public_ip(ip: IPAddress) -> bool:
    # ::ffff:127.0.0.1 is 127.0.0.1 written as IPv6 - check the IPv4 part
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    # is_global is False for private, loopback, link-local, reserved, CGNAT (100.64/10) ...
    return ip.is_global and not ip.is_multicast


def check_url_host(url: str) -> None:
    """Reject localhost and non-public IP literals without doing DNS."""
    if settings.ALLOW_PRIVATE_TARGETS:
        return

    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    if not host:
        raise UnsafeTargetError("URL has no host")
    if host in BLOCKED_HOSTNAMES or host.endswith(".localhost"):
        raise UnsafeTargetError("Monitoring localhost is not allowed")

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return  # a hostname - checked after DNS resolution in the worker

    if not is_public_ip(ip):
        raise UnsafeTargetError(f"Monitoring non-public address {ip} is not allowed")


def ensure_public_target(url: str) -> None:
    check_url_host(url)
    if settings.ALLOW_PRIVATE_TARGETS:
        return

    parts = urlsplit(url)
    port = parts.port or (443 if parts.scheme == "https" else 80)
    infos = socket.getaddrinfo(parts.hostname, port, type=socket.SOCK_STREAM)

    for *_, sockaddr in infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if not is_public_ip(ip):
            raise UnsafeTargetError(f"{parts.hostname} resolves to non-public address {ip}")
