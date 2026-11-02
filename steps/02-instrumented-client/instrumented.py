"""Step 02: InstrumentedCrawlingAPI with a counter and a histogram."""

import time
from urllib.parse import urlsplit

import httpx
from prometheus_client import Counter, Histogram

API = "https://api.crawlbase.com/"

REQUESTS = Counter(
    "crawlbase_requests",
    "Crawling API requests by outcome.",
    ["domain", "cb_status", "original_status", "http_status", "token_type"],
)
LATENCY = Histogram(
    "crawlbase_latency_seconds",
    "Wall-clock time of a Crawling API call.",
    ["domain", "complexity"],
    buckets=(0.5, 1, 2, 3, 5, 7.5, 10, 15, 20, 30, 45, 60, 90),
)
RESPONSE_BYTES = Histogram(
    "crawlbase_response_bytes",
    "Size of the response body.",
    ["domain"],
    buckets=(0, 1_000, 10_000, 50_000, 100_000, 250_000, 500_000, 1_000_000, 5_000_000),
)


def domain_label(url: str) -> str:
    """Hostname only. Never the path: one series per site, not per page."""
    host = (urlsplit(url).hostname or "invalid").lower()
    return host[4:] if host.startswith("www.") else host


def status_label(value: str | None) -> str:
    return value if value and value.isdigit() and len(value) <= 3 else "none"


class InstrumentedCrawlingAPI:
    def __init__(self, token: str, token_type: str, timeout: float = 90):
        self._token = token
        self.token_type = token_type
        self._http = httpx.Client(timeout=timeout)

    def get(self, url: str, **params) -> httpx.Response:
        domain = domain_label(url)
        started = time.perf_counter()
        r = self._http.get(API, params={"token": self._token, "url": url, **params})
        elapsed = time.perf_counter() - started

        h = r.headers
        complexity = (h.get("x-domain-complexity") or h.get("domain_complexity") or "unknown").lower()
        REQUESTS.labels(
            domain=domain,
            cb_status=status_label(h.get("cb_status")),
            original_status=status_label(h.get("original_status")),
            http_status=str(r.status_code),
            token_type=self.token_type,
        ).inc()
        LATENCY.labels(domain=domain, complexity=complexity).observe(elapsed)
        RESPONSE_BYTES.labels(domain=domain).observe(len(r.content))
        return r
