"""A thin, instrumented wrapper around the Crawling API."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

import httpx

from .billing import is_billable, parse_success_codes
from .domains import DomainLimiter, domain_label
from .headers import CrawlSignals, parse_signals
from .metrics import CrawlMetrics, status_label

DEFAULT_BASE_URL = "https://api.crawlbase.com"
DEFAULT_TIMEOUT = 90.0


@dataclass(frozen=True)
class CrawlResult:
    url: str
    domain: str
    token_type: str
    signals: CrawlSignals
    billable: bool
    elapsed: float
    body: bytes

    @property
    def ok(self) -> bool:
        return self.signals.http_status == 200 and self.signals.cb_status == 200


class InstrumentedCrawlingAPI:
    """Drop-in client: one call to `get()` is one Crawling API request plus metrics.

    Transport errors are recorded, then re-raised so the caller keeps control
    of retries. HTTP 520 is not an exception: it is a normal, labelled outcome.
    """

    def __init__(
        self,
        token: str,
        token_type: str,
        metrics: CrawlMetrics,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        custom_success_codes: Iterable[int] = (),
        domain_limiter: Callable[[str], str] | None = None,
        http: httpx.Client | None = None,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        if not token:
            raise ValueError("Crawlbase token is empty")
        self._token = token
        self.token_type = token_type
        self.metrics = metrics
        self.base_url = base_url.rstrip("/")
        self.custom_success_codes = frozenset(custom_success_codes)
        self._limit_domain = domain_limiter or DomainLimiter()
        self._http = http or httpx.Client(timeout=timeout)
        self._clock = clock
        self._known: set[tuple[str, str]] = set()

    def preregister(self, urls: Iterable[str], token_type: str | None = None) -> None:
        """Create zero-valued series before traffic starts.

        Prometheus only sees a counter once it exists. A series born at 1 between
        two scrapes shows no increase, so the first failure would be invisible.
        """
        for url in urls:
            self._ensure_series(self._limit_domain(domain_label(url)), token_type or self.token_type)

    def _ensure_series(self, domain: str, token_type: str) -> None:
        if (domain, token_type) in self._known:
            return
        self._known.add((domain, token_type))
        self.metrics.attempts.labels(domain=domain, token_type=token_type)
        self.metrics.requests.labels(
            domain=domain, cb_status="200", original_status="200",
            http_status="200", token_type=token_type, billable="true",
        )

    def get(self, url: str, **params: Any) -> CrawlResult:
        domain = self._limit_domain(domain_label(url))
        token_type = "js" if str(params.get("javascript", "")).lower() == "true" else self.token_type
        success_codes = self.custom_success_codes | parse_success_codes(params.get("custom_success_codes"))

        self._ensure_series(domain, token_type)
        started = self._clock()
        try:
            response = self._http.get(
                f"{self.base_url}/", params={"token": self._token, "url": url, **params}
            )
        except httpx.HTTPError as exc:
            self._record_failure(domain, token_type, exc)
            raise
        elapsed = self._clock() - started

        json_body = None
        if params.get("format") == "json":
            try:
                json_body = response.json()
            except ValueError:
                json_body = None
        signals = parse_signals(response.status_code, response.headers, json_body)
        billable = is_billable(signals.cb_status, signals.original_status, success_codes)

        # Counted on completion, next to the outcome, so success <= attempts in any window.
        self.metrics.attempts.labels(domain=domain, token_type=token_type).inc()
        self.metrics.requests.labels(
            domain=domain,
            cb_status=status_label(signals.cb_status),
            original_status=status_label(signals.original_status),
            http_status=status_label(signals.http_status),
            token_type=token_type,
            billable=str(billable).lower(),
        ).inc()
        self.metrics.latency.labels(domain=domain, complexity=signals.complexity).observe(elapsed)
        self.metrics.response_bytes.labels(domain=domain).observe(len(response.content))

        return CrawlResult(url, domain, token_type, signals, billable, elapsed, response.content)

    def _record_failure(self, domain: str, token_type: str, exc: httpx.HTTPError) -> None:
        reason = "timeout" if isinstance(exc, httpx.TimeoutException) else "transport"
        self.metrics.attempts.labels(domain=domain, token_type=token_type).inc()
        self.metrics.client_errors.labels(domain=domain, token_type=token_type, reason=reason).inc()
        # Count it as a request too, so success-rate denominators include it.
        self.metrics.requests.labels(
            domain=domain, cb_status="none", original_status="none",
            http_status="none", token_type=token_type, billable="false",
        ).inc()

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> InstrumentedCrawlingAPI:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
