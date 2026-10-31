from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit

from app.providers.base import InvalidRecipeURL


def _is_private_address(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return not ip.is_global


async def ensure_public_url(url: str, *, allow_private: bool = False) -> None:
    """Reject non-HTTP and (by default) private-network URLs to limit SSRF."""
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"}:
        raise InvalidRecipeURL("Nur http- und https-URLs werden unterstützt.")
    if not parts.hostname:
        raise InvalidRecipeURL("Die URL enthält keinen gültigen Hostnamen.")
    if allow_private:
        return

    def resolve() -> list[str]:
        default_port = 443 if parts.scheme == "https" else 80
        infos = socket.getaddrinfo(
            parts.hostname, parts.port or default_port, type=socket.SOCK_STREAM
        )
        return sorted({info[4][0] for info in infos})

    try:
        addresses = await asyncio.to_thread(resolve)
    except OSError as exc:
        raise InvalidRecipeURL("Der Hostname konnte nicht aufgelöst werden.") from exc
    if not addresses or any(_is_private_address(address) for address in addresses):
        raise InvalidRecipeURL("Lokale oder private Adressen sind nicht erlaubt.")
