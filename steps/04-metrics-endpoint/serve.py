"""Step 04: expose /metrics with start_http_server while the scraper runs.

Usage: python serve.py   then   curl -s localhost:8000/metrics | grep crawlbase_
"""

import os
import threading
import time

from dotenv import find_dotenv, load_dotenv
from prometheus_client import start_http_server

from instrumented import InstrumentedCrawlingAPI

URLS = ["https://example.com/", "https://example.org/"]
PORT = int(os.environ.get("METRICS_PORT", "8000"))
KEEP_SERVING = int(os.environ.get("KEEP_SERVING", "120"))


def main() -> None:
    load_dotenv(find_dotenv(usecwd=True))
    api = InstrumentedCrawlingAPI(os.environ["CRAWLBASE_NORMAL_TOKEN"], "normal")

    # Runs in a daemon thread. Your scraper keeps doing its work on the main thread.
    start_http_server(PORT)
    print(f"serving http://localhost:{PORT}/metrics")

    for url in URLS:
        r = api.get(url)
        print(f"{r.status_code} cb_status={r.headers.get('cb_status')} {url}")

    print(f"done crawling, serving /metrics for {KEEP_SERVING}s more (Ctrl+C to stop)")
    threading.Event().wait(KEEP_SERVING)


if __name__ == "__main__":
    main()
