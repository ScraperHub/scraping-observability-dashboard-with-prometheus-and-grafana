"""Step 09a: Crawler stats endpoint to gauges (behind a flag in the final stack).

Usage: python crawler_stats.py
"""

import os

import httpx
from dotenv import find_dotenv, load_dotenv
from prometheus_client import REGISTRY, Gauge, generate_latest

TOTALS = Gauge("crawlbase_crawler_totals", "Account-wide Crawler counters.", ["field"])
WAITING = Gauge("crawlbase_crawler_waiting", "URLs waiting in a crawler queue.", ["crawler"])
CONCURRENCY = Gauge("crawlbase_crawler_concurrency", "Active concurrency per crawler.", ["crawler"])
PAUSED = Gauge("crawlbase_crawler_paused", "1 if the crawler is paused.", ["crawler"])


def poll(token: str) -> None:
    # Token goes in the path here, not the query string. Never log this URL.
    r = httpx.get(f"https://api.crawlbase.com/crawler/{token}/stats", timeout=60)
    r.raise_for_status()
    stats = r.json()
    for field in ("crawls", "fails", "retries", "waiting", "concurrency"):
        if isinstance(stats.get(field), (int, float)):
            TOTALS.labels(field=field).set(stats[field])
    for c in stats.get("crawlers", []):
        WAITING.labels(crawler=c["name"]).set(c.get("waiting") or 0)
        CONCURRENCY.labels(crawler=c["name"]).set(c.get("concurrency") or 0)
        PAUSED.labels(crawler=c["name"]).set(1 if c.get("paused") else 0)


if __name__ == "__main__":
    load_dotenv(find_dotenv(usecwd=True))
    poll(os.environ["CRAWLBASE_NORMAL_TOKEN"])
    for line in generate_latest(REGISTRY).decode().splitlines():
        if line.startswith("crawlbase_crawler"):
            print(line)
