"""Crawl a few URLs through the instrumented client, then print the metric samples."""

import os

from dotenv import find_dotenv, load_dotenv
from prometheus_client import REGISTRY, generate_latest

from instrumented import InstrumentedCrawlingAPI

URLS = [
    "https://example.com/",
    "https://example.com/?page=2",
    "https://example.com/?page=3",
    "https://example.org/",
]


def main() -> None:
    load_dotenv(find_dotenv(usecwd=True))
    api = InstrumentedCrawlingAPI(os.environ["CRAWLBASE_NORMAL_TOKEN"], "normal")
    for url in URLS:
        r = api.get(url)
        print(f"{r.status_code} cb_status={r.headers.get('cb_status')} {url}")

    print()
    for line in generate_latest(REGISTRY).decode().splitlines():
        if line.startswith(("crawlbase_requests_total", "crawlbase_latency_seconds_count",
                            "crawlbase_response_bytes_sum")):
            print(line)


if __name__ == "__main__":
    main()
