import logging

from cbwatch.config import Settings
from cbwatch.redact import RedactingFilter, redact

from .conftest import FAKE_TOKEN


def test_redacts_query_token():
    url = f"https://api.crawlbase.com/?token={FAKE_TOKEN}&url=https%3A%2F%2Fexample.com"
    out = redact(url)
    assert FAKE_TOKEN not in out
    assert "token=***&url=" in out


def test_redacts_crawler_path_token():
    out = redact(f"GET https://api.crawlbase.com/crawler/{FAKE_TOKEN}/stats failed")
    assert FAKE_TOKEN not in out and "/crawler/***/stats" in out


def test_redacts_known_secret_anywhere():
    assert redact(f"oops {FAKE_TOKEN} leaked", [FAKE_TOKEN]) == "oops *** leaked"


def test_logging_filter(caplog):
    logger = logging.getLogger("cbwatch.test")
    logger.addFilter(RedactingFilter([FAKE_TOKEN]))
    with caplog.at_level(logging.INFO, logger="cbwatch.test"):
        logger.info("calling %s", f"https://api.crawlbase.com/?token={FAKE_TOKEN}")
    assert FAKE_TOKEN not in caplog.text


def test_settings_from_env():
    s = Settings.from_env({
        "CRAWLBASE_NORMAL_TOKEN": "n", "CRAWLBASE_JS_TOKEN": "j",
        "ACCOUNT_POLL_INTERVAL": "30", "CRAWLER_STATS_ENABLED": "true",
        "DEMO_TARGETS": "normal|https://a.test/, js|https://b.test/",
        "CRAWLBASE_MONTHLY_BUDGET": "5000",
    })
    assert s.account_poll_interval == 300
    assert s.crawler_stats_enabled is True
    assert s.demo_targets == (("normal", "https://a.test/"), ("js", "https://b.test/"))
    assert s.token_for("js") == "j" and s.token_for("normal") == "n"
    assert s.monthly_budget == 5000
    assert s.secrets == ("n", "j")


def test_settings_defaults():
    s = Settings.from_env({})
    assert s.crawler_stats_enabled is False
    assert s.monthly_budget is None
    assert any("glassdoor" in url for t, url in s.demo_targets if t == "normal")
