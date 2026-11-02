"""Print real /metrics lines and the PromQL values behind each dashboard panel.

Run inside the compose network:
    docker run --rm --network cbwatch_default -v "$PWD:/app" -w /app cbwatch-dev python scripts/capture_samples.py
"""

import httpx

PROM = "http://prometheus:9090/api/v1/query"
QUERIES = [
    "crawlbase:success_ratio:rate1h",
    "crawlbase:credits_days_to_zero",
    "max(crawlbase_account_remaining_credits)",
    'sum(increase(crawlbase_requests_total{billable="true"}[1h])) / sum(increase(crawlbase_requests_total[1h]))',
    "histogram_quantile(0.95, sum by (le, complexity) (rate(crawlbase_latency_seconds_bucket[30m])))",
    'sum by (domain) (increase(crawlbase_requests_total{cb_status!="200"}[1h]))',
    "sum by (cb_status, http_status) (crawlbase_requests_total)",
    "sum by (domain) (crawlbase_requests_total)",
    "sum by (domain, token_type, cb_status) (crawlbase_requests_total)",
    "crawlbase:account_success_ratio",
    "crawlbase:site_success_ratio:rate1h",
    "crawlbase:account_site_success_ratio",
    "crawlbase:normal_token_blocked_ratio:rate5m",
    "sum by (billable) (crawlbase_requests_total)",
]


def main() -> None:
    text = httpx.get("http://scraper:8000/metrics").text
    for line in text.splitlines():
        if line.startswith(("crawlbase_attempts_total", "crawlbase_requests_total", "# HELP crawlbase_requests", "# TYPE crawlbase_requests",
                            "crawlbase_latency_seconds_count", "crawlbase_response_bytes_sum")) or (
            "crawlbase_latency_seconds_bucket" in line and "glassdoor" in line
        ):
            print(line)
    print("-----")
    for line in httpx.get("http://reconciler:8001/metrics").text.splitlines():
        if line.startswith("crawlbase_account"):
            print(line)
    print("-----")
    for q in QUERIES:
        result = httpx.get(PROM, params={"query": q}).json()["data"]["result"]
        print(q, "=>", [(s["metric"], s["value"][1]) for s in result])


if __name__ == "__main__":
    main()
