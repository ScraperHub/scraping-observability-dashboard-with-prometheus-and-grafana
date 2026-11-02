# Step 04: the /metrics endpoint

`start_http_server(8000)` starts a small HTTP server in a background thread of the scraper process. Prometheus pulls from it. There's no push gateway and no agent.

`instrumented.py` is the client from step 02 with the `billable` label from step 03 added.

## Run

```bash
pip install -r requirements.txt
python serve.py
# in another terminal
curl -s localhost:8000/metrics | grep crawlbase_
# or, without curl
python fetch_metrics.py
```

`KEEP_SERVING=300 python serve.py` keeps the endpoint up longer. `METRICS_PORT` changes the port.
