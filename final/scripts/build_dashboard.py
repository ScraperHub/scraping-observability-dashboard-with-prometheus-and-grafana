"""Generate grafana/dashboards/crawlbase.json.

The JSON is committed. Re-run this after changing a panel:
    python scripts/build_dashboard.py
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "grafana" / "dashboards" / "crawlbase.json"
DS = {"type": "prometheus", "uid": "prometheus"}

_next_id = 0


def _id() -> int:
    global _next_id
    _next_id += 1
    return _next_id


def target(expr: str, legend: str = "", ref: str = "A", instant: bool = False) -> dict:
    return {"datasource": DS, "expr": expr, "legendFormat": legend, "refId": ref,
            "instant": instant, "range": not instant}


def stat(title, expr, x, y, unit="none", thresholds=None, decimals=None, desc=""):
    return {
        "id": _id(), "type": "stat", "title": title, "description": desc, "datasource": DS,
        "gridPos": {"x": x, "y": y, "w": 6, "h": 4},
        "targets": [target(expr, instant=True)],
        "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                    "colorMode": "background", "graphMode": "none", "textMode": "value"},
        "fieldConfig": {"defaults": {
            "unit": unit, "decimals": decimals, "noValue": "no data",
            "thresholds": {"mode": "absolute", "steps": thresholds or [{"color": "blue", "value": None}]},
        }, "overrides": []},
    }


def timeseries(title, targets, x, y, w=12, h=8, unit="none", stack=False, desc="", minv=None, maxv=None, draw="line"):
    custom = {"drawStyle": draw, "lineWidth": 2, "fillOpacity": 60 if stack or draw == "bars" else 10,
              "showPoints": "never", "spanNulls": True,
              "stacking": {"mode": "normal" if stack else "none", "group": "A"}}
    defaults = {"unit": unit, "custom": custom}
    if minv is not None:
        defaults["min"] = minv
    if maxv is not None:
        defaults["max"] = maxv
    return {
        "id": _id(), "type": "timeseries", "title": title, "description": desc, "datasource": DS,
        "gridPos": {"x": x, "y": y, "w": w, "h": h}, "targets": targets,
        "fieldConfig": {"defaults": defaults, "overrides": []},
        "options": {"legend": {"displayMode": "table", "placement": "right", "calcs": ["lastNotNull"]},
                    "tooltip": {"mode": "multi", "sort": "desc"}},
    }


def bargauge(title, expr, legend, x, y, w=12, h=8, desc=""):
    return {
        "id": _id(), "type": "bargauge", "title": title, "description": desc, "datasource": DS,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "targets": [target(expr, legend, instant=True)],
        "options": {"orientation": "horizontal", "displayMode": "gradient",
                    "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                    "showUnfilled": True},
        "fieldConfig": {"defaults": {"unit": "short", "min": 0,
                                     "thresholds": {"mode": "absolute", "steps": [
                                         {"color": "orange", "value": None}, {"color": "red", "value": 10}]}},
                        "overrides": []},
    }


def table(title, targets, x, y, w=12, h=8, desc=""):
    return {
        "id": _id(), "type": "table", "title": title, "description": desc, "datasource": DS,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "targets": targets,
        "transformations": [
            {"id": "merge", "options": {}},
            {"id": "organize", "options": {
                "excludeByName": {"Time": True},
                "renameByName": {"Value #A": "Local (1h)", "Value #B": "Account API (month)", "site": "Site"}}},
        ],
        "fieldConfig": {"defaults": {"unit": "percentunit", "decimals": 1}, "overrides": []},
        "options": {"showHeader": True},
    }


def row(title, y, collapsed=False, panels=None):
    return {"id": _id(), "type": "row", "title": title, "collapsed": collapsed,
            "gridPos": {"x": 0, "y": y, "w": 24, "h": 1}, "panels": panels or []}


RATE_STEPS = [{"color": "red", "value": None}, {"color": "orange", "value": 0.9}, {"color": "green", "value": 0.97}]
DAYS_STEPS = [{"color": "red", "value": None}, {"color": "orange", "value": 3}, {"color": "green", "value": 7}]


def build() -> dict:
    global _next_id
    _next_id = 0
    panels = [
        row("Health at a glance", 0),
        stat("Success rate (1h)", "crawlbase:success_ratio:rate1h", 0, 1, "percentunit", RATE_STEPS, 1,
             "Share of requests with cb_status 200 over the last hour. Timeouts count as failures."),
        stat("Credits remaining", "max(crawlbase_account_remaining_credits)", 6, 1, "short",
             desc="From Account API remainingCredits, or CRAWLBASE_MONTHLY_BUDGET minus totalSuccess."),
        stat("Projected days to zero", "crawlbase:credits_days_to_zero", 12, 1, "d", DAYS_STEPS, 1,
             "Remaining credits divided by the last hour of billable requests."),
        stat("Billable share (1h)",
             'sum(increase(crawlbase_requests_total{billable="true"}[1h])) / sum(increase(crawlbase_attempts_total[1h]))',
             18, 1, "percentunit", decimals=1, desc="Requests you pay for. Failures are free."),

        row("Reliability", 5),
        timeseries("Success rate per domain", [target("crawlbase:domain_success_ratio:rate5m", "{{domain}}")],
                   0, 6, unit="percentunit", minv=0, maxv=1,
                   desc="cb_status 200 share per domain, 5 minute window. Alert fires under 90% for 10m."),
        timeseries("p95 latency by complexity tier", [target(
            "histogram_quantile(0.95, sum by (le, complexity) (rate(crawlbase_latency_seconds_bucket[5m])))",
            "{{complexity}}")], 12, 6, unit="s", minv=0,
            desc="domain_complexity comes from the X-Domain-Complexity header."),
        timeseries("cb_status breakdown", [
            target('sum by (cb_status) (increase(crawlbase_requests_total[$__rate_interval]))', "cb {{cb_status}}"),
            target('sum(increase(crawlbase_requests_total{http_status="520"}[$__rate_interval]))', "HTTP 520 (failed crawl)", "B"),
        ], 0, 14, draw="bars", stack=True,
            desc="Requests by cb_status. HTTP 520 is the outer status for any failed crawl."),
        bargauge("Top failing domains (range)",
                 'topk(10, (sum by (domain) (increase(crawlbase_attempts_total[$__range])) - '
                 'sum by (domain) (increase(crawlbase_requests_total{cb_status="200"}[$__range]))) > 0)',
                 "{{domain}}", 12, 14,
                 desc="Non-200 cb_status count over the dashboard time range, timeouts included."),
        timeseries("Normal token blocked (needs JS token)",
                   [target("crawlbase:normal_token_blocked:rate5m * 60", "{{domain}}")],
                   0, 22, unit="reqpm",
                   desc="Normal-token requests answered with cb_status 503, 207, 525, 576 or 705."),
        timeseries("Billable vs free", [
            target('sum by (billable) (rate(crawlbase_requests_total[5m])) * 60', "billable={{billable}}"),
        ], 12, 22, unit="reqpm", stack=True),

        row("Reconciliation with the Account API", 30),
        timeseries("Local vs Account API success rate", [
            target("crawlbase:success_ratio:rate1h", "local (1h window)"),
            target("crawlbase:account_success_ratio", "Account API (month to date)", "B"),
        ], 0, 31, unit="percentunit", minv=0, maxv=1,
            desc="Local counts every attempt. A gap usually means retries or traffic from another client on the same token."),
        table("Per-site success: local vs Account API", [
            {**target("crawlbase:site_success_ratio:rate1h", "", "A", True), "format": "table"},
            {**target("crawlbase:account_site_success_ratio", "", "B", True), "format": "table"},
        ], 12, 31, desc="Joined on site (walmart.com becomes walmart, the Account API form)."),
        stat("Account API data age", "time() - crawlbase_account_last_poll_timestamp_seconds", 0, 39, "s",
             [{"color": "green", "value": None}, {"color": "orange", "value": 600}, {"color": "red", "value": 1800}],
             desc="Seconds since the last successful Account API call. Normal is under 300."),
        stat("Account API calls (24h)", 'sum(increase(crawlbase_account_api_calls_total[24h]))', 6, 39, "short",
             desc="Must stay at or below 288 (one per 5 minutes)."),
        row("Crawler (optional, CRAWLER_STATS_ENABLED=true)", 43, collapsed=True, panels=[
            timeseries("Crawler queue depth", [target("crawlbase_crawler_waiting", "{{crawler}}")], 0, 44),
            timeseries("Crawler concurrency", [target("crawlbase_crawler_concurrency", "{{crawler}}")], 12, 44),
        ]),
    ]
    return {
        "uid": "crawlbase-observability",
        "title": "Crawlbase scraping observability",
        "description": "Web scraping monitoring dashboard for the Crawlbase Crawling API and Account API.",
        "tags": ["crawlbase", "scraping"],
        "timezone": "browser",
        "schemaVersion": 39,
        "version": 1,
        "editable": False,
        "refresh": "30s",
        "time": {"from": "now-1h", "to": "now"},
        "templating": {"list": []},
        "annotations": {"list": []},
        "panels": panels,
    }


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(build(), indent=2) + "\n")
    print(f"wrote {OUT.relative_to(OUT.parents[2])}")
