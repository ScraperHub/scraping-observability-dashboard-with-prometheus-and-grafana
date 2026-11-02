"""Demo scraper: crawl a few targets through the instrumented client and serve /metrics.

Run: python -m cbwatch.demo
It stops sending requests after DEMO_MAX_REQUESTS (to protect your credits)
but keeps serving /metrics so Prometheus can still scrape the counters.
"""

from __future__ import annotations

import argparse
import itertools
import logging
import signal
import threading
from concurrent.futures import ThreadPoolExecutor

import httpx
from prometheus_client import start_http_server

from .client import InstrumentedCrawlingAPI
from .config import Settings
from .domains import DomainLimiter
from .metrics import CrawlMetrics
from .redact import install_log_redaction

log = logging.getLogger("cbwatch.demo")


def build_clients(settings: Settings, metrics: CrawlMetrics) -> dict[str, InstrumentedCrawlingAPI]:
    limiter = DomainLimiter(settings.max_domains)
    clients = {}
    for token_type in ("normal", "js"):
        token = settings.token_for(token_type)
        if token:
            clients[token_type] = InstrumentedCrawlingAPI(
                token, token_type, metrics,
                base_url=settings.api_base,
                timeout=settings.request_timeout,
                domain_limiter=limiter,
            )
    return clients


def crawl_one(client: InstrumentedCrawlingAPI, url: str) -> None:
    try:
        r = client.get(url)
        s = r.signals
        log.info(
            "%s token_type=%s http=%s cb_status=%s original_status=%s complexity=%s billable=%s %.1fs",
            r.domain, r.token_type, s.http_status, s.cb_status, s.original_status,
            s.complexity, r.billable, r.elapsed,
        )
    except httpx.HTTPError as exc:
        log.warning("%s token_type=%s client error: %s", url, client.token_type, type(exc).__name__)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="exit after the request budget is spent")
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    install_log_redaction(settings.secrets)

    metrics = CrawlMetrics()
    clients = build_clients(settings, metrics)
    if not clients:
        raise SystemExit("Set CRAWLBASE_NORMAL_TOKEN and/or CRAWLBASE_JS_TOKEN")

    jobs = [(t, u) for t, u in settings.demo_targets if t in clients]
    for token_type, client in clients.items():
        client.preregister(u for t, u in jobs if t == token_type)

    start_http_server(settings.metrics_port)
    log.info("serving /metrics on :%d", settings.metrics_port)

    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())

    # Let Prometheus scrape the zero values once before the first request.
    stop.wait(settings.demo_warmup)
    plan = list(itertools.islice(itertools.cycle(jobs), settings.demo_max_requests))
    with ThreadPoolExecutor(max_workers=settings.demo_workers) as pool:
        for token_type, url in plan:
            if stop.is_set():
                break
            pool.submit(crawl_one, clients[token_type], url)
            stop.wait(settings.demo_interval)

    log.info("request budget of %d spent", len(plan))
    if not args.once:
        stop.wait()


if __name__ == "__main__":
    main()
