"""Print the crawlbase_* lines from /metrics (a curl | grep for machines without curl)."""

import sys
import urllib.request

url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/metrics"
for line in urllib.request.urlopen(url).read().decode().splitlines():
    if line.startswith("crawlbase_") and "_created" not in line:
        print(line)
