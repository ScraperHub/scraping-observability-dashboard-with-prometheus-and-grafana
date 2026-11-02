"""Probe the real Crawlbase APIs once and print what actually comes back.

Token values are never printed. Raw JSON is written to output/ (gitignored)
so the shapes can be compared against the docs.

Usage:
    python scripts/live_probe.py crawl            # a few Crawling API calls
    python scripts/live_probe.py account crawling-api
    python scripts/live_probe.py account crawler
    python scripts/live_probe.py crawler-stats
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
API = "https://api.crawlbase.com"

INTERESTING = (
    "cb_status", "pc_status", "original_status", "url", "domain_complexity",
    "x-domain-complexity", "remaining", "rid", "content-type",
)


def tokens() -> tuple[str, str]:
    load_dotenv(ROOT / ".env")
    return os.environ["CRAWLBASE_NORMAL_TOKEN"], os.environ["CRAWLBASE_JS_TOKEN"]


def redact(value: object) -> object:
    """Replace numbers and strings with type placeholders, keep the shape."""
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value[:3]]
    if isinstance(value, bool):
        return "<bool>"
    if isinstance(value, (int, float)):
        return f"<{type(value).__name__}>"
    if isinstance(value, str):
        return "<str>"
    return value


def crawl(targets: list[tuple[str, str, dict]]) -> None:
    normal, js = tokens()
    OUT.mkdir(exist_ok=True)
    with httpx.Client(timeout=90) as client:
        for url, kind, extra in targets:
            token = normal if kind == "normal" else js
            started = time.perf_counter()
            print(f"\n== {url} token={kind} extra={extra}")
            try:
                r = client.get(API + "/", params={"token": token, "url": url, **extra})
            except httpx.HTTPError as exc:
                print(f"client error {type(exc).__name__} after {time.perf_counter() - started:.1f}s")
                continue
            elapsed = time.perf_counter() - started
            print(f"http_status={r.status_code} elapsed={elapsed:.2f}s bytes={len(r.content)}")
            for name, value in r.headers.items():
                if name.lower() in INTERESTING or "complex" in name.lower():
                    print(f"  {name}: {value}")
            if extra.get("format") == "json":
                try:
                    data = r.json()
                    data.pop("body", None)
                    print("  json keys:", sorted(data))
                    print("  json meta:", {k: v for k, v in data.items() if k != "body"})
                except ValueError:
                    print("  body is not JSON")


def account(product: str) -> None:
    normal, _ = tokens()
    OUT.mkdir(exist_ok=True)
    r = httpx.get(API + "/account", params={"token": normal, "product": product}, timeout=60)
    print(f"http_status={r.status_code}")
    try:
        data = r.json()
    except ValueError:
        print("non-JSON body:", r.text[:300])
        return
    (OUT / f"account-{product}.json").write_text(json.dumps(data, indent=2))
    print(json.dumps(redact(data), indent=2))


def crawler_stats() -> None:
    normal, _ = tokens()
    OUT.mkdir(exist_ok=True)
    r = httpx.get(f"{API}/crawler/{normal}/stats", timeout=60)
    print(f"http_status={r.status_code}")
    try:
        data = r.json()
    except ValueError:
        print("non-JSON body:", r.text[:300])
        return
    (OUT / "crawler-stats.json").write_text(json.dumps(data, indent=2))
    print(json.dumps(redact(data), indent=2))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "crawl"
    if cmd == "crawl":
        # Optional args: "js:https://..." uses the JS token, plain URLs use Normal.
        extra = sys.argv[2:]
        if extra:
            targets = [
                (u[3:], "js", {}) if u.startswith("js:") else (u, "normal", {}) for u in extra
            ]
        else:
            targets = [
                ("https://example.com/", "normal", {}),
                ("https://example.com/", "normal", {"format": "json"}),
            ]
        crawl(targets)
    elif cmd == "account":
        account(sys.argv[2] if len(sys.argv) > 2 else "crawling-api")
    elif cmd == "crawler-stats":
        crawler_stats()
    else:
        raise SystemExit(f"unknown command {cmd}")
