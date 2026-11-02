# Step 06: Docker Compose stack

Four services:

| Service | Port | What it does |
| --- | --- | --- |
| scraper | 8000 | demo scraper with the instrumented client (8 requests, then serves /metrics) |
| reconciler | 8001 | Account API poller, once per 5 minutes |
| prometheus | 9090 | scrapes both every 15 s and 60 s |
| grafana | 3000 | Prometheus datasource provisioned, no dashboard yet |

The scraper and reconciler images are built from `../../final`, the same package as the final project.

## Run

```bash
cp ../../.env.example ../../.env   # once (code/.env), then fill in both tokens
docker compose up -d --build
open http://localhost:9090/targets   # both targets should be UP
docker compose down
```

The reconciler keeps its last Account API call time in the `cbwatch-account-state` volume. Steps 06 to 08 and `code/final` all share that volume, so switching stacks never breaks the 5 minute limit.

Step 07 adds the dashboard. Step 08 adds alerts.
