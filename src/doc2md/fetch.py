"""Safe URL fetching with SSRF protection and download size limits.

Every URL passed by an MCP client is validated *before* a request is made:
only http/https schemes are allowed, and every IP address the hostname
resolves to must be a public unicast address. Redirects are followed
manually (max 5 hops) and each hop is re-validated.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import anyio
import httpx

MAX_DOWNLOAD_BYTES = 30 * 1024 * 1024  # 30 MB
MAX_REDIRECTS = 5
DEFAULT_TIMEOUT = 30.0
USER_AGENT = "doc2md/0.1 (+https://github.com/zhao-cyc/doc2md)"

_REDIRECT_STATUS = {301, 302, 303, 307, 308}


class FetchError(RuntimeError):
    """Raised when a URL cannot be fetched safely or successfully."""


def _reject_non_public(ip_str: str) -> None:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError as exc:  # pragma: no cover - defensive
        raise FetchError(f"Unparseable IP address: {ip_str!r}") from exc
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    ):
        raise FetchError(
            f"Refusing to fetch {ip_str}: private, loopback, link-local or "
            "reserved addresses are not allowed (SSRF protection)."
        )


def validate_url(url: str) -> None:
    """Validate scheme, host and *all* resolved IP addresses of a URL.

    Blocking helper — run it in a worker thread from async code.
    """
    try:
        parsed = urlparse(url)
    except ValueError as exc:
        raise FetchError(f"Malformed URL: {exc}") from exc

    if parsed.scheme not in ("http", "https"):
        raise FetchError(
            f"URL scheme {parsed.scheme!r} is not allowed; use http or https."
        )
    host = parsed.hostname
    if not host:
        raise FetchError("URL has no hostname.")

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise FetchError(f"Cannot resolve hostname {host!r}: {exc}") from exc
    if not infos:
        raise FetchError(f"Hostname {host!r} does not resolve to any address.")
    for info in infos:
        _reject_non_public(info[4][0])


async def fetch_url(url: str) -> tuple[bytes, str, str]:
    """Download a document from a URL.

    Returns ``(content_bytes, content_type, final_url)``.
    Raises :class:`FetchError` on validation errors, too many redirects,
    oversized payloads or HTTP errors.
    """
    current = url
    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(
        follow_redirects=False,
        timeout=httpx.Timeout(DEFAULT_TIMEOUT),
        headers=headers,
    ) as client:
        for _ in range(MAX_REDIRECTS + 1):
            await anyio.to_thread.run_sync(validate_url, current)
            try:
                async with client.stream("GET", current) as response:
                    if response.status_code in _REDIRECT_STATUS:
                        location = response.headers.get("location")
                        if not location:
                            raise FetchError(
                                f"Redirect {response.status_code} without Location header."
                            )
                        current = urljoin(current, location)
                        continue
                    if response.status_code >= 400:
                        raise FetchError(
                            f"HTTP {response.status_code} while fetching {current}"
                        )
                    chunks: list[bytes] = []
                    total = 0
                    async for chunk in response.aiter_bytes(65536):
                        total += len(chunk)
                        if total > MAX_DOWNLOAD_BYTES:
                            raise FetchError(
                                "Document exceeds the "
                                f"{MAX_DOWNLOAD_BYTES // (1024 * 1024)} MB download limit."
                            )
                        chunks.append(chunk)
                    content_type = response.headers.get("content-type", "")
                    return b"".join(chunks), content_type, str(response.url)
            except httpx.HTTPError as exc:
                raise FetchError(f"Network error fetching {current}: {exc}") from exc
        raise FetchError(f"Too many redirects (>{MAX_REDIRECTS}) starting from {url}.")
