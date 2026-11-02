"""Step 09b: two tokens, one metric family, routed by a per-domain rule.

Domains that the "Normal token blocked" alert flagged move to JS_DOMAINS.
The token_type label keeps both paths apart on the dashboard.

Usage: python multi_token.py
"""

import os

from dotenv import find_dotenv, load_dotenv
from prometheus_client import REGISTRY, generate_latest

from instrumented import InstrumentedCrawlingAPI, domain_label

# Filled from the alert: Normal token gets cb_status 503/576/705 on these.
JS_DOMAINS = {"glassdoor.com"}

URLS = [
    "https://example.com/",
    "https://www.glassdoor.com/Reviews/index.htm",
]


def main() -> None:
    load_dotenv(find_dotenv(usecwd=True))
    clients = {
        "normal": InstrumentedCrawlingAPI(os.environ["CRAWLBASE_NORMAL_TOKEN"], "normal"),
        "js": InstrumentedCrawlingAPI(os.environ["CRAWLBASE_JS_TOKEN"], "js"),
    }
    for url in URLS:
        token_type = "js" if domain_label(url) in JS_DOMAINS else "normal"
        r = clients[token_type].get(url)
        print(f"{token_type:<6} http={r.status_code} cb_status={r.headers.get('cb_status')} {url}")

    print()
    for line in generate_latest(REGISTRY).decode().splitlines():
        if line.startswith("crawlbase_requests_total"):
            print(line)


if __name__ == "__main__":
    main()
