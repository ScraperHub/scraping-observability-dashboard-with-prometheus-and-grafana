"""Step 01: one plain Crawling API call per URL, print the signals Crawlbase returns.

Usage: python raw_request.py [url ...]
"""

import os
import sys
import time

import httpx
from dotenv import find_dotenv, load_dotenv

API = "https://api.crawlbase.com/"
DEFAULT_URLS = [
    "https://example.com/",
    "https://example.com/does-not-exist",
    "https://www.glassdoor.com/Reviews/index.htm",  # protected site, Normal token
]


def main() -> None:
    load_dotenv(find_dotenv(usecwd=True))
    token = os.environ["CRAWLBASE_NORMAL_TOKEN"]
    urls = sys.argv[1:] or DEFAULT_URLS

    with httpx.Client(timeout=90) as client:
        for url in urls:
            started = time.perf_counter()
            try:
                r = client.get(API, params={"token": token, "url": url})
            except httpx.TimeoutException:
                print(f"{url}\n  client timeout after {time.perf_counter() - started:.1f}s\n")
                continue
            h = r.headers
            print(url)
            print(f"  http_status       {r.status_code}")
            print(f"  cb_status         {h.get('cb_status')}")
            print(f"  original_status   {h.get('original_status')}")
            # html format sends X-Domain-Complexity, format=json uses domain_complexity
            print(f"  domain_complexity {h.get('x-domain-complexity') or h.get('domain_complexity')}")
            print(f"  bytes             {len(r.content)}")
            print(f"  seconds           {time.perf_counter() - started:.1f}\n")


if __name__ == "__main__":
    main()
