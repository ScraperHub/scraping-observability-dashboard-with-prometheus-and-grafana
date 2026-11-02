# Crawlbase scraping observability

A web scraping monitoring dashboard for the Crawlbase Crawling API, built with Prometheus and Grafana.

- `InstrumentedCrawlingAPI` records `cb_status`, `original_status`, HTTP status, domain complexity, latency, bytes, token type, and billable vs free for every call. Labels stay small: domain is the hostname only.
- A reconciler polls the Crawlbase Account API at most once per 5 minutes, even across restarts, and exposes the account-wide numbers as gauges.
- Prometheus recording rules, a provisioned Grafana dashboard, and three provisioned Grafana alert rules.
- Optional Crawler stats (`/crawler/<token>/stats`) behind `CRAWLER_STATS_ENABLED`.

## Layout

```text
code/
  .env.example        tokens for the step folders (copy to code/.env)
  steps/              one small, runnable folder per blog section
  final/              the complete project
    src/cbwatch/      client, billing, metrics, Account API poller, demo, reconciler
    prometheus/       prometheus.yml, recording rules, promtool rule tests
    grafana/          datasource, dashboard JSON, alert rules (all provisioned)
    scripts/          dashboard generator, config checks, smoke test, live probe
    tests/            pytest + respx unit tests
```

## Tokens

You need a Crawlbase Normal token and a JS token.

```bash
cp code/.env.example code/.env                 # for the steps
cp code/final/.env.example code/final/.env     # for the final stack
```

Fill in `CRAWLBASE_NORMAL_TOKEN` and `CRAWLBASE_JS_TOKEN`. Both `.env` files are gitignored. Tokens are masked as `***` in every log line.

On accounts where the Account API returns no `remainingCredits`, set `CRAWLBASE_MONTHLY_BUDGET` to get a budget-based credits gauge.

## The steps

Requirements: Python 3.11 for steps 01 to 05 and 09, Docker with Compose for steps 06 to 08.

| Step | What it adds | Run |
| --- | --- | --- |
| `01-raw-request-and-headers` | One raw call, prints the three signals | `python raw_request.py` |
| `02-instrumented-client` | Counters and histograms per call | `python run.py` |
| `03-billable-vs-free` | The billing rule, no token needed | `python classify.py` and `pytest -q` |
| `04-metrics-endpoint` | `/metrics` on port 8000 | `python serve.py` then `python fetch_metrics.py` |
| `05-account-api-reconciler` | Rate-limited Account API poller | `python run.py` |
| `06-docker-compose-stack` | Scraper, reconciler, Prometheus, Grafana | `docker compose up -d --build` |
| `07-dashboard` | Recording rules and the dashboard | `docker compose up -d --build` |
| `08-alerts` | Three Grafana alert rules | `docker compose up -d --build` |
| `09-crawler-stats-and-multi-token` | Crawler stats gauges, per-domain token routing | `python crawler_stats.py`, `python multi_token.py` |

Each folder has its own `requirements.txt` and README. Run `pip install -r requirements.txt` first. Steps 06 to 08 and `final` use the same ports, so run one stack at a time (`docker compose down` before the next).

The Account API allows one request per 5 minutes. The stacks share a Docker volume (`cbwatch-account-state`) for the guard. Step 05 uses its own file. Wait 5 minutes between step 05 and any stack.

## The final project

```bash
cd code/final
docker compose up -d --build
```

- Grafana: http://localhost:3000/d/crawlbase-observability (admin / `GRAFANA_ADMIN_PASSWORD`, default admin)
- Prometheus: http://localhost:9090
- Scraper metrics: http://localhost:8000/metrics
- Reconciler metrics: http://localhost:8001/metrics

The demo scraper sends `DEMO_MAX_REQUESTS` requests (default 40) to a mix of easy and protected sites. It deliberately uses the Normal token on a protected site so the "Normal token blocked" alert fires. Successful requests use credits.

To use the client in your own job:

```python
from prometheus_client import start_http_server
from cbwatch.client import InstrumentedCrawlingAPI
from cbwatch.metrics import CrawlMetrics

metrics = CrawlMetrics()
start_http_server(8000)
with InstrumentedCrawlingAPI(token, "normal", metrics) as api:
    result = api.get("https://example.com/")
```

Edit dashboard panels in `scripts/build_dashboard.py`, then run `python scripts/build_dashboard.py` to regenerate `grafana/dashboards/crawlbase.json`.

## Tests

All from `code/final`.

```bash
pip install -r requirements-dev.txt

# unit tests (no network, HTTP faked with respx)
pytest

# promtool check config, check rules, test rules, plus dashboard and alert JSON/YAML validation
bash scripts/check_configs.sh

# integration smoke test against a running stack
docker compose up -d --build
SMOKE_HOST=localhost python scripts/smoke_test.py

# live tests with real tokens (uses credits, makes at most one Account API call)
pytest -m live
```

`check_configs.sh` runs promtool from the `prom/prometheus:v3.1.0` image, so Docker is enough. The smoke test checks that both targets are up, every expected series is present, recording rules return data, domain labels hold no paths, and Grafana has the dashboard, a healthy datasource, and all three alert rules. For the step stacks, set `SMOKE_EXPECT=stack` (step 06) or `SMOKE_EXPECT=dashboard` (step 07).

---

Copyright 2026 [Crawlbase](https://crawlbase.com/)
