"""Pre-publish audit: prose rules for the blog, and a secret scan of the repo.

Run from code/final: python scripts/audit.py
Token values are read from code/.env and code/final/.env and never printed.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BLOG = ROOT / "draft" / "scraping-observability-dashboard-with-prometheus-and-grafana.md"
SKIP_DIRS = {"output", ".venv", ".pytest_cache", "__pycache__", ".git", "state"}
TEXT_SUFFIXES = {".md", ".py", ".yml", ".yaml", ".json", ".svg", ".toml", ".txt", ".sh", ".example", ""}
EM_DASH = "\u2014"
EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF]")
FILLER = ("in today's fast-paced", "let's dive in", "dive into", "without further ado")


def prose(markdown: str) -> str:
    text = re.sub(r"```.*?```", " ", markdown, flags=re.S)
    return re.sub(r"`[^`]*`", " ", text)


def files():
    for path in ROOT.rglob("*"):
        if path.is_file() and not SKIP_DIRS & set(path.parts) and path.suffix in TEXT_SUFFIXES:
            if path.name in {"keys.md", "notes.md"} or path.name.endswith(".env"):
                continue
            yield path


def tokens() -> list[str]:
    found = []
    for env in (ROOT / "code" / ".env", ROOT / "code" / "final" / ".env"):
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                key, _, value = line.partition("=")
                if key.strip() in {"CRAWLBASE_NORMAL_TOKEN", "CRAWLBASE_JS_TOKEN"} and value.strip():
                    found.append(value.strip())
    return sorted(set(found))


def main() -> int:
    failures = []
    blog = BLOG.read_text(encoding="utf-8")
    body = prose(blog)
    words = len(re.findall(r"[A-Za-z0-9][\w'.,%/-]*", body))
    semicolons = body.count(";")
    print(f"blog words (no code): {words}")
    print(f"blog prose semicolons: {semicolons}")
    if not 2000 <= words <= 2300:
        failures.append("word count outside 2000-2300")
    if semicolons > 3:
        failures.append("more than 3 semicolons in prose")
    for phrase in FILLER:
        if phrase in body.lower():
            failures.append(f"filler phrase: {phrase}")

    secrets = tokens()
    print(f"token values loaded for scan: {len(secrets)}")
    if len(secrets) < 2:
        failures.append("could not load both token values for the secret scan")
    for path in files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        rel = path.relative_to(ROOT)
        if EM_DASH in text:
            failures.append(f"em dash in {rel}")
        if EMOJI.search(text):
            failures.append(f"emoji in {rel}")
        if any(s in text for s in secrets):
            failures.append(f"TOKEN VALUE in {rel}")

    for f in failures:
        print(f"[FAIL] {f}")
    print(f"{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
