"""Keep Crawlbase tokens out of logs, exceptions, and printed URLs."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable

MASK = "***"
_QUERY_TOKEN = re.compile(r"(?i)\b(token=)[^&\s\"'#]+")
_CRAWLER_PATH = re.compile(r"(/crawler/)[^/?\s\"']+")


def redact(text: str, secrets: Iterable[str] = ()) -> str:
    text = _QUERY_TOKEN.sub(rf"\g<1>{MASK}", text)
    text = _CRAWLER_PATH.sub(rf"\g<1>{MASK}", text)
    for secret in secrets:
        if secret:
            text = text.replace(secret, MASK)
    return text


class RedactingFilter(logging.Filter):
    """Logging filter that rewrites every record through `redact`."""

    def __init__(self, secrets: Iterable[str] = ()) -> None:
        super().__init__()
        self.secrets = tuple(s for s in secrets if s)

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage(), self.secrets)
        record.args = None
        return True


def install_log_redaction(secrets: Iterable[str] = ()) -> None:
    """Attach the filter to every root handler. Call after logging.basicConfig."""
    filt = RedactingFilter(secrets)
    for handler in logging.getLogger().handlers:
        handler.addFilter(filt)
    # httpx logs full request URLs (with token=) at INFO.
    logging.getLogger("httpx").setLevel(logging.WARNING)
