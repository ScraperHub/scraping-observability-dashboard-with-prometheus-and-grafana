"""Parse the Crawlbase signals out of a Crawling API response."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

# Documented tiers are standard, moderate and complex, but live responses also
# return values like "complex_ii". Keep any short slug, reject anything else.
_TIER = re.compile(r"^[a-z][a-z0-9_]{0,23}$")
UNKNOWN = "unknown"


@dataclass(frozen=True)
class CrawlSignals:
    http_status: int
    cb_status: int | None
    original_status: int | None
    complexity: str
    final_url: str | None
    remaining: int | None = None


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except ValueError:
        return None


def _normalise(headers: Mapping[str, str]) -> dict[str, str]:
    # "CB-Status", "cb_status" and "X-Domain-Complexity" all appear in the wild.
    return {k.lower().replace("-", "_"): v for k, v in headers.items()}


def _complexity(value: Any) -> str:
    tier = str(value).strip().lower() if value is not None else ""
    return tier if _TIER.match(tier) else UNKNOWN


def parse_signals(
    http_status: int,
    headers: Mapping[str, str],
    json_body: Mapping[str, Any] | None = None,
) -> CrawlSignals:
    """Read signals from headers (format=html) or the JSON envelope (format=json).

    Complexity arrives as `X-Domain-Complexity` in headers and as
    `domain_complexity` in JSON. Both spellings are accepted from either source.
    """
    h = _normalise(headers)
    body = dict(json_body or {})

    def pick(*keys: str) -> Any:
        for key in keys:
            if key in h:
                return h[key]
            if key in body:
                return body[key]
        return None

    return CrawlSignals(
        http_status=http_status,
        cb_status=_to_int(pick("cb_status", "pc_status")),
        original_status=_to_int(pick("original_status")),
        complexity=_complexity(pick("x_domain_complexity", "domain_complexity")),
        final_url=pick("url"),
        remaining=_to_int(h.get("remaining")),
    )
