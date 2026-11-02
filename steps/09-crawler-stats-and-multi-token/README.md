# Step 09: Crawler stats and multi-token setups

## Crawler stats

`GET https://api.crawlbase.com/crawler/<TOKEN>/stats` returns account-wide `crawls`, `fails`, `retries`, `waiting`, and `concurrency`, plus a `crawlers` list (`name`, `waiting`, `concurrency`, `latency`, `paused`). `crawler_stats.py` turns that into gauges. Crawler names are yours, so the label stays small.

The token is part of the URL path here. Never log that URL.

The final stack runs this inside the reconciler when `CRAWLER_STATS_ENABLED=true`. The Account API also accepts `product=crawler` (verified live). It returns the same shape as `crawling-api`.

## Multi-token

`multi_token.py` keeps one client per token and routes by domain. Domains flagged by the "Normal token blocked" alert go to the JS token. Both clients write to the same metric family with a different `token_type` label, so the dashboard compares them directly.

`instrumented.py` is the step 04 client, copied here so this folder runs on its own.

## Run

```bash
pip install -r requirements.txt
python crawler_stats.py
python multi_token.py
```
