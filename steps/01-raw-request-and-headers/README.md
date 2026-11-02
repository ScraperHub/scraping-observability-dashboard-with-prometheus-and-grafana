# Step 01: raw request and headers

One plain Crawling API call per URL. Prints the three signals every response carries:

- `cb_status`: what Crawlbase made of the crawl (200 means usable).
- `original_status`: what the target site answered.
- `domain_complexity`: the pricing tier of the domain. In the default html format it arrives as the `x-domain-complexity` header.

Also prints the outer HTTP status. A failed crawl comes back as HTTP 520, with the reason in `cb_status`.

## Run

```bash
pip install -r requirements.txt
python raw_request.py                       # default URLs
python raw_request.py https://example.com/  # your own
```

The token is read from `CRAWLBASE_NORMAL_TOKEN` (a `.env` file in this folder or any parent, see `code/.env.example`).

Cost: successful calls use credits. Failed calls (HTTP 520) are free.
