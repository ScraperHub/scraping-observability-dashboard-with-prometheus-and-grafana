# Step 07: the dashboard

Step 06 plus:

- `prometheus/rules/crawlbase.rules.yml`: recording rules (`crawlbase:domain_success_ratio:rate5m`, `crawlbase:credits_days_to_zero`, and others) so panels and alerts share one definition.
- `grafana/dashboards/crawlbase.json`: the dashboard, provisioned into the "Crawlbase" folder.
- `build_dashboard.py`: generates the JSON. Edit panels there, not in the JSON.

Panels: success rate per domain, p95 latency by complexity tier, credits remaining and projected days to zero, top failing domains, `cb_status` breakdown, Normal token blocked, billable vs free, local vs Account API success rate, and a per-site table.

## Run

```bash
docker compose up -d --build
open http://localhost:3000/d/crawlbase-observability   # admin / admin
docker compose down
```

`CRAWLBASE_MONTHLY_BUDGET=1000` gives the credits panels data on pay-as-you-go accounts, where the Account API returns no `remainingCredits`.
