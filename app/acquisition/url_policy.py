"""URL security policy and Server-Side Request Forgery (SSRF) protection."""

import ipaddress
import socket
from urllib.parse import urlparse

from app.acquisition.errors import BLOCKED_PRIVATE_ADDRESS, INVALID_URL

# Blocked hostnames known to resolve locally
BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "ip6-localhost",
    "ip6-loopback",
}

ALLOWED_SCHEMES = {"http", "https"}


def is_ip_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check whether an IP address belongs to private, loopback, link-local, or reserved ranges."""
    # Handle IPv4-mapped IPv6 addresses (e.g., ::ffff:127.0.0.1)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped

    return (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def validate_url_policy(url: str) -> tuple[bool, str | None, str | None]:
    """Validate a URL against security and SSRF policies.

    Args:
        url: The candidate URL to validate.

    Returns:
        tuple[bool, str | None, str | None]: (is_allowed, error_code, error_message)
    """
    if not url or not isinstance(url, str):
        return False, INVALID_URL, "URL must be a non-empty string."

    trimmed = url.strip()
    try:
        parsed = urlparse(trimmed)
    except Exception:
        return False, INVALID_URL, f"Malformed URL format: '{trimmed}'."

    # 1. Validate scheme
    scheme = (parsed.scheme or "").lower()
    if scheme not in ALLOWED_SCHEMES:
        return (
            False,
            INVALID_URL,
            f"Unsupported URL scheme '{scheme}'. Only HTTP and HTTPS are permitted.",
        )

    if not parsed.netloc:
        return False, INVALID_URL, f"URL missing network host: '{trimmed}'."

    # 2. Extract host without port
    host = parsed.netloc.split(":")[0].strip("[]").lower()
    if not host:
        return False, INVALID_URL, f"URL missing valid hostname: '{trimmed}'."

    # 3. Check blocked hostnames
    if host in BLOCKED_HOSTNAMES:
        return (
            False,
            BLOCKED_PRIVATE_ADDRESS,
            f"Access to local host '{host}' is prohibited.",
        )

    # 4. Check if host is direct IP address
    try:
        ip_obj = ipaddress.ip_address(host)
        if is_ip_blocked(ip_obj):
            return (
                False,
                BLOCKED_PRIVATE_ADDRESS,
                f"Access to private or local IP address '{host}' is prohibited.",
            )
        return True, None, None
    except ValueError:
        # Not a literal IP, it is a domain name
        pass

    # 5. Resolve hostname to detect DNS-based SSRF
    try:
        addr_info = socket.getaddrinfo(host, None)
        for entry in addr_info:
            sockaddr = entry[4]
            ip_str = sockaddr[0]
            try:
                ip_obj = ipaddress.ip_address(ip_str)
                if is_ip_blocked(ip_obj):
                    return (
                        False,
                        BLOCKED_PRIVATE_ADDRESS,
                        f"Hostname '{host}' resolves to restricted IP '{ip_str}'.",
                    )
            except ValueError:
                continue
    except socket.gaierror:
        # DNS resolution failure will be handled by fetcher as DNS_ERROR if requested
        pass
    except Exception:
        # Fallback safe
        pass

    return True, None, None
