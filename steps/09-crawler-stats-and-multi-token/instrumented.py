"""Step 02 client plus the step 03 billable label."""

import time
from urllib.parse import urlsplit

import httpx
from prometheus_client import Counter, Histogram

API = "https://api.crawlbase.com/"
CHARGED_ORIGINAL_STATUSES = frozenset({200, 201, 301, 302, 303, 307, 308, 404, 410})

REQUESTS = Counter(
    "crawlbase_requests",
    "Crawling API requests by outcome.",
    ["domain", "cb_status", "original_status", "http_status", "token_type", "billable"],
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
    host = (urlsplit(url).hostname or "invalid").lower()
    return host[4:] if host.startswith("www.") else host


def to_int(value: str | None) -> int | None:
    return int(value) if value and value.isdigit() else None


def is_billable(cb_status, original_status, custom_success_codes=()):
    if cb_status not in (200, 207) or original_status is None:
        return False
    return original_status in CHARGED_ORIGINAL_STATUSES or original_status in set(custom_success_codes)


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
        cb, orig = to_int(h.get("cb_status")), to_int(h.get("original_status"))
        complexity = (h.get("x-domain-complexity") or h.get("domain_complexity") or "unknown").lower()
        REQUESTS.labels(
            domain=domain,
            cb_status=str(cb) if cb is not None else "none",
            original_status=str(orig) if orig is not None else "none",
            http_status=str(r.status_code),
            token_type=self.token_type,
            billable=str(is_billable(cb, orig)).lower(),
        ).inc()
        LATENCY.labels(domain=domain, complexity=complexity).observe(elapsed)
        RESPONSE_BYTES.labels(domain=domain).observe(len(r.content))
        return r
