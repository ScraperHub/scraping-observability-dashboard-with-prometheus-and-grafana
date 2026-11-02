"""Optional poller for GET /crawler/<TOKEN>/stats (Enterprise Crawler).

Observed live shape: top-level crawls, fails, concurrency, waiting, retries,
plus a "crawlers" list with name, waiting, concurrency, latency, paused.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import httpx

from .metrics import CrawlerStatsMetrics

log = logging.getLogger(__name__)

TOTAL_FIELDS = ("crawls", "fails", "retries", "waiting", "concurrency")


def apply_stats(payload: Mapping[str, Any], metrics: CrawlerStatsMetrics) -> int:
    """Set gauges from a stats payload. Returns the number of crawlers seen."""
    for name in TOTAL_FIELDS:
        value = payload.get(name)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            metrics.totals.labels(field=name).set(value)
    crawlers = payload.get("crawlers") or []
    for crawler in crawlers:
        name = str(crawler.get("name", "unknown"))
        metrics.waiting.labels(crawler=name).set(float(crawler.get("waiting") or 0))
        metrics.concurrency.labels(crawler=name).set(float(crawler.get("concurrency") or 0))
        metrics.latency.labels(crawler=name).set(float(crawler.get("latency") or 0))
        metrics.paused.labels(crawler=name).set(1.0 if crawler.get("paused") else 0.0)
    return len(crawlers)


class CrawlerStatsPoller:
    def __init__(
        self,
        token: str,
        metrics: CrawlerStatsMetrics,
        *,
        base_url: str = "https://api.crawlbase.com",
        http: httpx.Client | None = None,
    ) -> None:
        self._token = token
        self.metrics = metrics
        self.base_url = base_url.rstrip("/")
        self._http = http or httpx.Client(timeout=60)

    def poll(self) -> bool:
        try:
            response = self._http.get(f"{self.base_url}/crawler/{self._token}/stats")
            response.raise_for_status()
            apply_stats(response.json(), self.metrics)
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("Crawler stats call failed: %s", type(exc).__name__)
            return False
        return True
