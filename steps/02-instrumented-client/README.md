# Step 02: instrumented client

`InstrumentedCrawlingAPI.get(url)` makes one Crawling API call and records:

- `crawlbase_requests_total{domain,cb_status,original_status,http_status,token_type}`
- `crawlbase_latency_seconds{domain,complexity}` (histogram)
- `crawlbase_response_bytes{domain}` (histogram)

The `domain` label is the hostname only. Four URLs on two sites make two series, not four.

## Run

```bash
pip install -r requirements.txt
python run.py
```

Output: one line per call, then the matching samples from the default registry.

Step 03 adds the `billable` label. The final client (`code/final/src/cbwatch/client.py`) adds timeouts, attempts, and a domain cap.
