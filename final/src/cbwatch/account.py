"""Account API poller with a hard 5 minute guard and a cached last response.

Docs: https://crawlbase.com/docs/account-api (rate limit: 1 request per 5 minutes).

Observed live shape (Nov 2026) differs from the docs table: fields sit under
"currentMonth", totals are strings, and each domainStats entry nests its
numbers under "metrics" with successRate as a string like "100.0%".
The parser accepts both the documented flat shape and the observed one.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import httpx

from .metrics import AccountMetrics

log = logging.getLogger(__name__)

MIN_INTERVAL_SECONDS = 300.0
DEFAULT_BASE_URL = "https://api.crawlbase.com"


@dataclass(frozen=True)
class DomainStat:
    domain: str
    total_requests: int
    success: int
    failure: int
    success_rate: float  # 0 to 1


@dataclass(frozen=True)
class AccountSnapshot:
    total_success: int
    total_failed: int
    total_due: float
    remaining_credits: float | None
    domains: tuple[DomainStat, ...] = field(default_factory=tuple)


def _num(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(str(value).strip().rstrip("%").replace(",", ""))
    except ValueError:
        return default


def _rate(metrics: Mapping[str, Any], total: int, success: int) -> float:
    if total > 0:
        return success / total
    raw = metrics.get("successRate")
    if raw is None:
        return 0.0
    value = _num(raw)
    # "98.5%" and 98.5 are percentages. 0.985 is already a ratio.
    return value / 100 if (isinstance(raw, str) and "%" in raw) or value > 1 else value


def parse_domain_stat(entry: Mapping[str, Any]) -> DomainStat:
    metrics = entry.get("metrics", entry)
    total = int(_num(metrics.get("totalRequests")))
    success = int(_num(metrics.get("success")))
    failure = int(_num(metrics.get("failure")))
    return DomainStat(
        domain=str(entry.get("domain", "unknown")),
        total_requests=total,
        success=success,
        failure=failure,
        success_rate=_rate(metrics, total, success),
    )


def parse_account(payload: Mapping[str, Any]) -> AccountSnapshot:
    month = payload.get("currentMonth", payload)
    remaining = month.get("remainingCredits", payload.get("remainingCredits"))
    return AccountSnapshot(
        total_success=int(_num(month.get("totalSuccess"))),
        total_failed=int(_num(month.get("totalFailed"))),
        total_due=_num(month.get("totalDue")),
        remaining_credits=None if remaining is None else _num(remaining),
        domains=tuple(parse_domain_stat(d) for d in month.get("domainStats") or ()),
    )


class AccountPoller:
    """Calls the Account API at most once per 5 minutes, even across restarts.

    The time of the last call is written to `state_file` BEFORE the request is
    sent, so a crash or a failed call still counts against the limit.
    """

    def __init__(
        self,
        token: str,
        *,
        product: str = "crawling-api",
        base_url: str = DEFAULT_BASE_URL,
        min_interval: float = MIN_INTERVAL_SECONDS,
        state_file: str | Path | None = None,
        http: httpx.Client | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._token = token
        self.product = product
        self.base_url = base_url.rstrip("/")
        self.min_interval = max(min_interval, MIN_INTERVAL_SECONDS)
        self.state_file = Path(state_file) if state_file else None
        self._http = http or httpx.Client(timeout=60)
        self._clock = clock
        self._last_call: float | None = None
        self._cached: AccountSnapshot | None = None
        self._load_state()

    @property
    def cached(self) -> AccountSnapshot | None:
        return self._cached

    def seconds_until_allowed(self) -> float:
        if self._last_call is None:
            return 0.0
        return max(0.0, self._last_call + self.min_interval - self._clock())

    def poll(self, metrics: AccountMetrics | None = None) -> AccountSnapshot | None:
        """Return a fresh snapshot if allowed, otherwise the cached one."""
        if self.seconds_until_allowed() > 0:
            if metrics:
                metrics.cache_hits.inc()
            return self._cached

        self._last_call = self._clock()
        self._save_state()
        try:
            response = self._http.get(
                f"{self.base_url}/account", params={"token": self._token, "product": self.product}
            )
            response.raise_for_status()
            snapshot = parse_account(response.json())
        except (httpx.HTTPError, ValueError) as exc:
            result = "timeout" if isinstance(exc, httpx.TimeoutException) else "error"
            status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
            log.warning("Account API call failed (%s): %s status=%s", result, type(exc).__name__, status)
            if metrics:
                metrics.api_calls.labels(result=result).inc()
            return self._cached

        self._cached = snapshot
        self._save_state()
        if metrics:
            metrics.api_calls.labels(result="ok").inc()
        return snapshot

    def _load_state(self) -> None:
        if not self.state_file or not self.state_file.exists():
            return
        try:
            state = json.loads(self.state_file.read_text())
            self._last_call = float(state["last_call"])
            if state.get("snapshot"):
                snap = state["snapshot"]
                snap["domains"] = tuple(DomainStat(**d) for d in snap.get("domains", ()))
                self._cached = AccountSnapshot(**snap)
        except (ValueError, KeyError, TypeError) as exc:
            log.warning("Ignoring unreadable poller state: %s", exc)

    def _save_state(self) -> None:
        if not self.state_file:
            return
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "last_call": self._last_call,
            "snapshot": asdict(self._cached) if self._cached else None,
        }
        self.state_file.write_text(json.dumps(state))


def apply_snapshot(
    snapshot: AccountSnapshot,
    metrics: AccountMetrics,
    *,
    monthly_budget: float | None = None,
    max_domains: int = 50,
    now: float | None = None,
) -> None:
    """Copy a snapshot into gauges. Only the busiest `max_domains` sites are exported."""
    metrics.total_success.set(snapshot.total_success)
    metrics.total_failed.set(snapshot.total_failed)
    metrics.total_due.set(snapshot.total_due)
    if snapshot.remaining_credits is not None:
        metrics.remaining_credits.labels(source="account_api").set(snapshot.remaining_credits)
    elif monthly_budget:
        metrics.remaining_credits.labels(source="budget").set(
            max(0.0, monthly_budget - snapshot.total_success)
        )
    metrics.domain_success_rate.clear()
    metrics.domain_requests.clear()
    busiest = sorted(snapshot.domains, key=lambda d: d.total_requests, reverse=True)[:max_domains]
    for stat in busiest:
        metrics.domain_success_rate.labels(domain=stat.domain).set(stat.success_rate)
        metrics.domain_requests.labels(domain=stat.domain).set(stat.total_requests)
    metrics.last_success.set(now if now is not None else time.time())
