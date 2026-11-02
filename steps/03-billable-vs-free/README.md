# Step 03: billable vs free

One function, `is_billable(cb_status, original_status, custom_success_codes)`, that follows the Crawling API pricing rules:

- Charged only when `cb_status` is 200 or 207 **and** `original_status` is 200, 201, 301, 302, 303, 307, 308, 404 or 410 (or a code you passed in `custom_success_codes`).
- Everything else is free, including every HTTP 520 response.

No token needed. Nothing here calls the API.

## Run

```bash
pip install -r requirements.txt
python classify.py   # decision table for the status combinations seen live
pytest -q            # the tests
```

The final client puts the result in the `billable` label of `crawlbase_requests_total`.
