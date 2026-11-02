"""Account API reconciler: poll every 5 minutes, export gauges on /metrics.

Run: python -m cbwatch.reconciler
"""

from __future__ import annotations

import logging
import signal
import threading
import time

from prometheus_client import start_http_server

from .account import AccountPoller, apply_snapshot
from .config import Settings
from .crawler_stats import CrawlerStatsPoller
from .metrics import AccountMetrics, CrawlerStatsMetrics
from .redact import install_log_redaction

log = logging.getLogger("cbwatch.reconciler")


def main() -> None:
    settings = Settings.from_env()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    install_log_redaction(settings.secrets)
    if not settings.normal_token:
        raise SystemExit("Set CRAWLBASE_NORMAL_TOKEN")

    account_metrics = AccountMetrics()
    poller = AccountPoller(
        settings.normal_token,
        product=settings.account_product,
        base_url=settings.api_base,
        min_interval=settings.account_poll_interval,
        state_file=settings.account_state_file,
    )
    stats = None
    if settings.crawler_stats_enabled:
        stats = CrawlerStatsPoller(settings.normal_token, CrawlerStatsMetrics(), base_url=settings.api_base)

    start_http_server(settings.metrics_port)
    log.info("serving /metrics on :%d", settings.metrics_port)

    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())

    # A cached snapshot from before a restart is exported right away.
    if poller.cached:
        apply_snapshot(poller.cached, account_metrics, monthly_budget=settings.monthly_budget,
                       max_domains=settings.account_max_domains)
    log.info("next Account API call in %.0fs (cached snapshot: %s)",
             poller.seconds_until_allowed(), "yes" if poller.cached else "no")

    next_stats = 0.0
    while not stop.is_set():
        wait = poller.seconds_until_allowed()
        if wait == 0:
            snapshot = poller.poll(account_metrics)
            if snapshot:
                apply_snapshot(snapshot, account_metrics, monthly_budget=settings.monthly_budget,
                               max_domains=settings.account_max_domains)
                log.info(
                    "account: success=%d failed=%d domains=%d remaining=%s",
                    snapshot.total_success, snapshot.total_failed,
                    len(snapshot.domains), snapshot.remaining_credits,
                )
            wait = poller.seconds_until_allowed()
        if stats and time.monotonic() >= next_stats:
            stats.poll()
            next_stats = time.monotonic() + settings.crawler_stats_interval
        stop.wait(min(wait, settings.crawler_stats_interval) if stats else wait)


if __name__ == "__main__":
    main()
