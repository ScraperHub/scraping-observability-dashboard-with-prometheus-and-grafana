"""Metric definitions. Every label here has a small, bounded set of values."""

from __future__ import annotations

from prometheus_client import REGISTRY, CollectorRegistry, Counter, Gauge, Histogram

# Average Crawling API latency is 4 to 10 s, client timeout is 90 s.
LATENCY_BUCKETS = (0.5, 1, 2, 3, 5, 7.5, 10, 15, 20, 30, 45, 60, 90)
SIZE_BUCKETS = (0, 1_000, 10_000, 50_000, 100_000, 250_000, 500_000, 1_000_000, 5_000_000)


def status_label(code: int | None) -> str:
    """Status codes stay as-is (0 is real: no upstream answer). Missing is "none", junk is "other"."""
    if code is None:
        return "none"
    return str(code) if 0 <= code <= 999 else "other"


class CrawlMetrics:
    """Metrics recorded by the instrumented Crawling API client."""

    def __init__(self, registry: CollectorRegistry = REGISTRY) -> None:
        # Every call, success or not. Created at 0 the first time a domain is
        # seen, so rate() never misses the first failure (see client.preregister).
        self.attempts = Counter(
            "crawlbase_attempts",
            "Crawling API calls finished, including ones that timed out.",
            ["domain", "token_type"],
            registry=registry,
        )
        self.requests = Counter(
            "crawlbase_requests",
            "Crawling API requests by outcome.",
            ["domain", "cb_status", "original_status", "http_status", "token_type", "billable"],
            registry=registry,
        )
        self.latency = Histogram(
            "crawlbase_latency_seconds",
            "Wall-clock time of a Crawling API call.",
            ["domain", "complexity"],
            buckets=LATENCY_BUCKETS,
            registry=registry,
        )
        self.response_bytes = Histogram(
            "crawlbase_response_bytes",
            "Size of the response body returned by the Crawling API.",
            ["domain"],
            buckets=SIZE_BUCKETS,
            registry=registry,
        )
        self.client_errors = Counter(
            "crawlbase_client_errors",
            "Calls that never got an HTTP response (timeouts, connection errors).",
            ["domain", "token_type", "reason"],
            registry=registry,
        )


class AccountMetrics:
    """Gauges set by the Account API reconciler."""

    def __init__(self, registry: CollectorRegistry = REGISTRY) -> None:
        self.remaining_credits = Gauge(
            "crawlbase_account_remaining_credits",
            "Credits left this month. source=account_api when the API returns it, "
            "source=budget when derived from CRAWLBASE_MONTHLY_BUDGET.",
            ["source"],
            registry=registry,
        )
        self.total_success = Gauge(
            "crawlbase_account_total_success", "Successful requests this month.", registry=registry
        )
        self.total_failed = Gauge(
            "crawlbase_account_total_failed", "Failed requests this month.", registry=registry
        )
        self.total_due = Gauge(
            "crawlbase_account_total_due_usd", "Amount due this month in USD.", registry=registry
        )
        self.domain_success_rate = Gauge(
            "crawlbase_account_domain_success_rate",
            "Per-site success ratio (0 to 1) from Account API domainStats.",
            ["domain"],
            registry=registry,
        )
        self.domain_requests = Gauge(
            "crawlbase_account_domain_requests",
            "Per-site request total this month from Account API domainStats.",
            ["domain"],
            registry=registry,
        )
        self.last_success = Gauge(
            "crawlbase_account_last_poll_timestamp_seconds",
            "Unix time of the last successful Account API call.",
            registry=registry,
        )
        self.api_calls = Counter(
            "crawlbase_account_api_calls",
            "Account API calls actually sent, by result.",
            ["result"],
            registry=registry,
        )
        for result in ("ok", "error", "timeout"):
            self.api_calls.labels(result=result)
        self.cache_hits = Counter(
            "crawlbase_account_cache_hits",
            "Polls answered from cache because the 5 minute guard was active.",
            registry=registry,
        )


class CrawlerStatsMetrics:
    """Gauges from GET /crawler/<TOKEN>/stats (optional)."""

    def __init__(self, registry: CollectorRegistry = REGISTRY) -> None:
        self.totals = Gauge(
            "crawlbase_crawler_totals",
            "Account-wide Crawler counters (crawls, fails, retries, waiting, concurrency).",
            ["field"],
            registry=registry,
        )
        self.waiting = Gauge(
            "crawlbase_crawler_waiting", "URLs waiting in a crawler queue.", ["crawler"], registry=registry
        )
        self.concurrency = Gauge(
            "crawlbase_crawler_concurrency", "Active concurrency per crawler.", ["crawler"], registry=registry
        )
        self.latency = Gauge(
            "crawlbase_crawler_latency", "Crawler latency as reported by the stats endpoint.",
            ["crawler"], registry=registry,
        )
        self.paused = Gauge(
            "crawlbase_crawler_paused", "1 if the crawler is paused.", ["crawler"], registry=registry
        )
