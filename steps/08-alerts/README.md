# Step 08: alerts

Step 07 plus `grafana/provisioning/alerting/crawlbase-alerts.yml`, three Grafana-managed rules that read the Prometheus recording rules:

| Rule | Condition | Severity |
| --- | --- | --- |
| Domain success rate below 90% | `crawlbase:domain_success_ratio:rate5m < 0.9` for 10m, domains with real traffic only | page |
| Normal token blocked | Normal-token `cb_status` 503/207/525/576/705 over 20% for 5m | ticket |
| Credits run out in under 3 days | `crawlbase:credits_days_to_zero < 3` for 15m | page |

Alerts route through Grafana's built-in Alertmanager. Add a contact point (Slack, email, PagerDuty) in Grafana and match on `severity`.

## Run

```bash
docker compose up -d --build
open http://localhost:3000/alerting/list   # admin / admin

# unit tests for the recording rules
docker run --rm -v "$PWD/prometheus:/etc/prometheus:ro" --entrypoint promtool \
  prom/prometheus:v3.1.0 test rules /etc/prometheus/tests/crawlbase.rules.test.yml

docker compose down
```

Annotations use `{{ $labels.domain }}` with a single `$`. Grafana 11 keeps `$$` literally in this field.
