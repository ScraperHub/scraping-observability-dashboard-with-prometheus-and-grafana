"""Integration smoke test against a running `docker compose up` stack.

Run inside the compose network:
    docker run --rm --network cbwatch_default -v "$PWD:/app" -w /app cbwatch-dev \
        python scripts/smoke_test.py

Or from the host with SMOKE_HOST=localhost.
"""

from __future__ import annotations

import os
import sys
import time

import httpx

LOCAL = os.environ.get("SMOKE_HOST") == "localhost"
PROM = "http://localhost:9090" if LOCAL else "http://prometheus:9090"
GRAFANA = "http://localhost:3000" if LOCAL else "http://grafana:3000"
SCRAPER = "http://localhost:8000" if LOCAL else "http://scraper:8000"
RECONCILER = "http://localhost:8001" if LOCAL else "http://reconciler:8001"
AUTH = ("admin", os.environ.get("GRAFANA_ADMIN_PASSWORD", "admin"))
# stack (step 06), dashboard (step 07), full (step 08 and code/final)
EXPECT = os.environ.get("SMOKE_EXPECT", "full")

SCRAPER_SERIES = ["crawlbase_attempts_total", "crawlbase_requests_total", "crawlbase_latency_seconds_bucket", "crawlbase_response_bytes_bucket"]
ACCOUNT_SERIES = ["crawlbase_account_total_success", "crawlbase_account_total_failed",
                  "crawlbase_account_last_poll_timestamp_seconds", "crawlbase_account_api_calls_total"]
RECORDED = ["crawlbase:domain_success_ratio:rate5m", "crawlbase:success_ratio:rate1h",
            "crawlbase:billable_requests:rate1h", "crawlbase:account_success_ratio"]
ALERT_UIDS = {"cb-domain-success-low", "cb-normal-token-blocked", "cb-credits-low"}

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}{': ' + detail if detail else ''}")
    if not ok:
        failures.append(name)


def wait_for(url: str, timeout: float = 120, **kw) -> httpx.Response | None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(url, timeout=10, **kw)
            if r.status_code == 200:
                return r
        except httpx.HTTPError:
            pass
        time.sleep(3)
    return None


def prom_query(expr: str) -> list:
    r = httpx.get(f"{PROM}/api/v1/query", params={"query": expr}, timeout=10)
    return r.json()["data"]["result"]


def main() -> int:
    check("prometheus ready", wait_for(f"{PROM}/-/ready") is not None)
    check("grafana healthy", wait_for(f"{GRAFANA}/api/health") is not None)

    # Targets: wait until both have been scraped at least once.
    deadline = time.time() + 120
    targets = []
    while time.time() < deadline:
        targets = httpx.get(f"{PROM}/api/v1/targets", timeout=10).json()["data"]["activeTargets"]
        if targets and all(t["health"] == "up" for t in targets):
            break
        time.sleep(5)
    jobs = {t["labels"]["job"]: t["health"] for t in targets}
    check("prometheus targets up", jobs == {"crawlbase-scraper": "up", "crawlbase-account": "up"}, str(jobs))

    scraper_text = httpx.get(f"{SCRAPER}/metrics", timeout=10).text
    for series in SCRAPER_SERIES:
        check(f"scraper /metrics exposes {series}", series in scraper_text)
    recon_text = httpx.get(f"{RECONCILER}/metrics", timeout=10).text
    for series in ACCOUNT_SERIES:
        check(f"reconciler /metrics exposes {series}", series in recon_text)

    for series in SCRAPER_SERIES + ACCOUNT_SERIES:
        check(f"prometheus has {series}", len(prom_query(series)) > 0)

    domains = sorted({s["metric"]["domain"] for s in prom_query("crawlbase_attempts_total")})
    check("domain label is hostname only", domains and all("/" not in d for d in domains), str(domains))

    ds = httpx.get(f"{GRAFANA}/api/datasources/uid/prometheus/health", auth=AUTH, timeout=10)
    check("grafana datasource healthy", ds.status_code == 200 and ds.json().get("status") == "OK", ds.text[:120])

    if EXPECT == "stack":
        print(f"\n{len(failures)} failure(s)")
        return 1 if failures else 0

    # Recording rules need a couple of evaluation cycles.
    deadline = time.time() + 120
    missing = RECORDED
    while time.time() < deadline and missing:
        missing = [r for r in RECORDED if not prom_query(r)]
        if missing:
            time.sleep(10)
    check("recording rules produce data", not missing, f"missing={missing}" if missing else "")

    r = httpx.get(f"{GRAFANA}/api/search", params={"query": "Crawlbase"}, auth=AUTH, timeout=10)
    uids = {d.get("uid") for d in r.json()}
    check("grafana dashboard provisioned", "crawlbase-observability" in uids)
    dash = httpx.get(f"{GRAFANA}/api/dashboards/uid/crawlbase-observability", auth=AUTH, timeout=10).json()
    check("dashboard has panels", len(dash["dashboard"]["panels"]) >= 15, str(len(dash["dashboard"]["panels"])))

    if EXPECT == "dashboard":
        print(f"\n{len(failures)} failure(s)")
        return 1 if failures else 0

    rules = httpx.get(f"{GRAFANA}/api/v1/provisioning/alert-rules", auth=AUTH, timeout=10).json()
    found = {rule["uid"] for rule in rules}
    check("grafana alert rules provisioned", ALERT_UIDS <= found, str(sorted(found)))

    # Rules must evaluate without errors against the live datasource.
    deadline = time.time() + 150
    health: dict[str, str] = {}
    while time.time() < deadline:
        data = httpx.get(f"{GRAFANA}/api/prometheus/grafana/api/v1/rules", auth=AUTH, timeout=10).json()
        health = {
            r["name"]: r.get("health", "?")
            for g in data["data"]["groups"] for r in g["rules"]
        }
        if len(health) == 3 and all(h in {"ok", "nodata"} for h in health.values()):
            break
        time.sleep(10)
    check("grafana alert rules evaluate cleanly", len(health) == 3 and all(h in {"ok", "nodata"} for h in health.values()), str(health))

    print(f"\n{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
