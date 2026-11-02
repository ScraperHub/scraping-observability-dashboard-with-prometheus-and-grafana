"""Step 05: Account API poller that can never call more than once per 5 minutes."""

import json
import time
from pathlib import Path

import httpx
from prometheus_client import Gauge

MIN_INTERVAL = 300  # documented limit: 1 request per 5 minutes

REMAINING = Gauge("crawlbase_account_remaining_credits", "Credits left this month.", ["source"])
SUCCESS = Gauge("crawlbase_account_total_success", "Successful requests this month.")
FAILED = Gauge("crawlbase_account_total_failed", "Failed requests this month.")
DOMAIN_RATE = Gauge("crawlbase_account_domain_success_rate", "Per-site success ratio (0 to 1).", ["domain"])


def num(value) -> float:
    return float(str(value).rstrip("%")) if value is not None else 0.0


class AccountPoller:
    def __init__(self, token: str, product: str = "crawling-api", state_file: str = ".account_state.json"):
        self._token = token
        self.product = product
        self.state = Path(state_file)
        saved = json.loads(self.state.read_text()) if self.state.exists() else {}
        self.last_call = saved.get("last_call", 0.0)
        self.cached = saved.get("payload")

    def poll(self) -> tuple[dict | None, bool]:
        """Return (payload, fresh). Inside the 5 minute window you get the cache."""
        if time.time() - self.last_call < MIN_INTERVAL:
            return self.cached, False
        self.last_call = time.time()
        self._save()  # before the call: a crash or error still counts
        r = httpx.get(
            "https://api.crawlbase.com/account",
            params={"token": self._token, "product": self.product},
            timeout=60,
        )
        r.raise_for_status()
        self.cached = r.json()
        self._save()
        return self.cached, True

    def _save(self) -> None:
        self.state.write_text(json.dumps({"last_call": self.last_call, "payload": self.cached}))


def apply(payload: dict, monthly_budget: float | None = None) -> None:
    # Live shape: everything under "currentMonth", numbers nested in "metrics".
    month = payload.get("currentMonth", payload)
    SUCCESS.set(num(month.get("totalSuccess")))
    FAILED.set(num(month.get("totalFailed")))
    if "remainingCredits" in month:
        REMAINING.labels(source="account_api").set(num(month["remainingCredits"]))
    elif monthly_budget:
        REMAINING.labels(source="budget").set(monthly_budget - num(month.get("totalSuccess")))
    for entry in month.get("domainStats", []):
        m = entry.get("metrics", entry)
        total, ok = num(m.get("totalRequests")), num(m.get("success"))
        DOMAIN_RATE.labels(domain=entry["domain"]).set(ok / total if total else num(m.get("successRate")) / 100)
