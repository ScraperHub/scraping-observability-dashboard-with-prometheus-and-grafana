"""Settings from environment variables (a local .env file is loaded if present)."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_TARGETS = ",".join([
    "normal|https://example.com/",
    "normal|https://example.org/",
    "normal|https://example.com/?page=2",
    "normal|https://example.com/does-not-exist",
    "normal|https://httpbin.org/status/500",
    "js|https://example.org/",
    # Deliberate mistake: a protected site on the Normal token (blocked, cb_status 576).
    "normal|https://www.glassdoor.com/Reviews/index.htm",
    "js|https://www.glassdoor.com/Reviews/index.htm",
])


def _bool(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _float_or_none(value: str | None) -> float | None:
    return float(value) if value and value.strip() else None


@dataclass(frozen=True)
class Settings:
    normal_token: str
    js_token: str
    api_base: str
    request_timeout: float
    metrics_port: int
    account_product: str
    account_poll_interval: float
    account_state_file: str
    account_max_domains: int
    monthly_budget: float | None
    crawler_stats_enabled: bool
    crawler_stats_interval: float
    max_domains: int
    demo_targets: tuple[tuple[str, str], ...]
    demo_max_requests: int
    demo_interval: float
    demo_workers: int
    demo_warmup: float

    @property
    def secrets(self) -> tuple[str, ...]:
        return tuple(t for t in (self.normal_token, self.js_token) if t)

    def token_for(self, token_type: str) -> str:
        return self.js_token if token_type == "js" else self.normal_token

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None, dotenv: Path | None = None) -> Settings:
        if env is None:
            load_dotenv(dotenv or Path.cwd() / ".env")
            env = os.environ
        targets = []
        for item in env.get("DEMO_TARGETS", DEFAULT_TARGETS).split(","):
            if "|" in item:
                token_type, url = item.strip().split("|", 1)
                targets.append((token_type.strip(), url.strip()))
        return cls(
            normal_token=env.get("CRAWLBASE_NORMAL_TOKEN", ""),
            js_token=env.get("CRAWLBASE_JS_TOKEN", ""),
            api_base=env.get("CRAWLBASE_API_BASE", "https://api.crawlbase.com"),
            request_timeout=float(env.get("CRAWLBASE_TIMEOUT", "90")),
            metrics_port=int(env.get("METRICS_PORT", "8000")),
            account_product=env.get("ACCOUNT_PRODUCT", "crawling-api"),
            account_poll_interval=max(300.0, float(env.get("ACCOUNT_POLL_INTERVAL", "300"))),
            account_state_file=env.get("ACCOUNT_STATE_FILE", "state/account_state.json"),
            account_max_domains=int(env.get("ACCOUNT_MAX_DOMAINS", "50")),
            monthly_budget=_float_or_none(env.get("CRAWLBASE_MONTHLY_BUDGET")),
            crawler_stats_enabled=_bool(env.get("CRAWLER_STATS_ENABLED")),
            crawler_stats_interval=float(env.get("CRAWLER_STATS_INTERVAL", "60")),
            max_domains=int(env.get("MAX_DOMAINS", "200")),
            demo_targets=tuple(targets),
            demo_max_requests=int(env.get("DEMO_MAX_REQUESTS", "40")),
            demo_interval=float(env.get("DEMO_INTERVAL", "2")),
            demo_workers=int(env.get("DEMO_WORKERS", "4")),
            demo_warmup=float(env.get("DEMO_WARMUP", "20")),
        )
