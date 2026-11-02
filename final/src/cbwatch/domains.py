"""Turn a target URL into a low-cardinality `domain` label."""

from __future__ import annotations

import threading
from urllib.parse import urlsplit

INVALID = "invalid"
OTHER = "other"


def domain_label(url: str) -> str:
    """Hostname only, lowercased, IDNA-encoded, with a leading www. removed.

    Never returns the path or query string: one label value per site, not per page.
    """
    if not url:
        return INVALID
    candidate = url if "://" in url else f"http://{url}"
    try:
        host = urlsplit(candidate).hostname
    except ValueError:
        return INVALID
    if not host:
        return INVALID
    host = host.rstrip(".").lower()
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError:
        return INVALID
    if host.startswith("www."):
        host = host[4:]
    return host or INVALID


class DomainLimiter:
    """Cap the number of distinct domain label values a process can create.

    The first `max_domains` domains keep their name. Anything after that is
    reported as "other" so a runaway URL list cannot explode the series count.
    """

    def __init__(self, max_domains: int = 200) -> None:
        self.max_domains = max_domains
        self._seen: set[str] = set()
        self._lock = threading.Lock()

    def __call__(self, domain: str) -> str:
        with self._lock:
            if domain in self._seen:
                return domain
            if len(self._seen) < self.max_domains:
                self._seen.add(domain)
                return domain
        return OTHER
