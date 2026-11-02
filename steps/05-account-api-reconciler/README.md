# Step 05: Account API reconciler

Polls `GET /account?token=...&product=crawling-api` and turns the response into gauges. The documented rate limit is 1 request per 5 minutes, so the poller:

- refuses to call again within 300 seconds and returns the cached response instead
- writes the call time to `.account_state.json` **before** the request, so a crash or an error still counts against the limit
- reloads that file on start, so a restart loop can't break the limit

The real response shape (November 2026) puts everything under `currentMonth` and nests per-domain numbers under `metrics`. `successRate` is a string like `"100.0%"`. `remainingCredits` only appears on subscription plans.

## Run

```bash
pip install -r requirements.txt
python run.py
```

The first run makes one API call. Runs within the next 5 minutes are answered from `.account_state.json` (gitignored). Set `CRAWLBASE_MONTHLY_BUDGET` to get a `remaining_credits{source="budget"}` gauge when the API doesn't return credits.

Note: the guard is per state file. This step's file is not the Docker volume the stacks in steps 06 to 08 and `code/final` use. After running this step, wait 5 minutes before starting any stack, and stop any running stack 5 minutes before running this step. The API rejects early calls with an error (seen live).
