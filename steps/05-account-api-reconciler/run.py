"""Poll the Account API once, show the response shape (values hidden), prove the guard.

Usage: python run.py
"""

import json
import os

from dotenv import find_dotenv, load_dotenv
from prometheus_client import REGISTRY, generate_latest

from poller import AccountPoller, apply


def shape(value):
    if isinstance(value, dict):
        return {k: shape(v) for k, v in value.items()}
    if isinstance(value, list):
        return [shape(value[0])] if value else []
    return f"<{type(value).__name__}>"


def main() -> None:
    load_dotenv(find_dotenv(usecwd=True))
    poller = AccountPoller(os.environ["CRAWLBASE_NORMAL_TOKEN"])

    payload, fresh = poller.poll()
    print(f"first poll: {'fresh API call' if fresh else 'served from cache (5 minute guard)'}")
    if payload is None:
        print("no cached data yet, try again in a few minutes")
        return
    print(json.dumps(shape(payload), indent=2))

    _, fresh = poller.poll()
    print(f"second poll right after: {'fresh API call' if fresh else 'served from cache (5 minute guard)'}")

    apply(payload, monthly_budget=float(os.environ.get("CRAWLBASE_MONTHLY_BUDGET") or 0) or None)
    print()
    for line in generate_latest(REGISTRY).decode().splitlines():
        if line.startswith("crawlbase_account"):
            print(line)


if __name__ == "__main__":
    main()
