"""Billable vs free classification for Crawling API responses.

Rule from https://crawlbase.com/docs/crawling-api/ (Billable requests):
a request is charged only when cb_status is 200 or 207 AND original_status
is one of the listed codes, or a code you passed in custom_success_codes.
Everything else is free, including HTTP 520 and client-side timeouts.
"""

from __future__ import annotations

from collections.abc import Iterable

CHARGED_CB_STATUSES = frozenset({200, 207})
CHARGED_ORIGINAL_STATUSES = frozenset({200, 201, 301, 302, 303, 307, 308, 404, 410})


def is_billable(
    cb_status: int | None,
    original_status: int | None,
    custom_success_codes: Iterable[int] = (),
) -> bool:
    if cb_status not in CHARGED_CB_STATUSES or original_status is None:
        return False
    return original_status in CHARGED_ORIGINAL_STATUSES or original_status in set(custom_success_codes)


def parse_success_codes(value: str | Iterable[int] | None) -> frozenset[int]:
    """Accept "403,429" (the query-string form) or an iterable of ints."""
    if value is None:
        return frozenset()
    if isinstance(value, str):
        return frozenset(int(part) for part in value.split(",") if part.strip().isdigit())
    return frozenset(int(v) for v in value)
