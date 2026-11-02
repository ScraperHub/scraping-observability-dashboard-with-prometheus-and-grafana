import httpx
import respx

from cbwatch.crawler_stats import CrawlerStatsPoller, apply_stats

from .conftest import FAKE_TOKEN

STATS = {
    "timestamp": "2026-11-02T13:57:00Z",
    "crawls": 1200, "fails": 30, "concurrency": 4, "waiting": 55, "retries": 7,
    "crawlers": [
        {"name": "product-monitor", "waiting": 50, "concurrency": 3, "latency": 4, "paused": False},
        {"name": "news-feed", "waiting": 5, "concurrency": 1, "latency": 2, "paused": True},
    ],
    "success": {"November 2026": {"total": 10}},
    "history": {"2026-11-02": {"crawls": 3, "fails": 1}},
}


def test_apply_stats(registry, stats_metrics):
    assert apply_stats(STATS, stats_metrics) == 2
    g = registry.get_sample_value
    assert g("crawlbase_crawler_totals", {"field": "waiting"}) == 55
    assert g("crawlbase_crawler_totals", {"field": "fails"}) == 30
    assert g("crawlbase_crawler_waiting", {"crawler": "product-monitor"}) == 50
    assert g("crawlbase_crawler_paused", {"crawler": "news-feed"}) == 1


def test_apply_stats_tolerates_missing_fields(stats_metrics):
    assert apply_stats({}, stats_metrics) == 0


@respx.mock
def test_poller_puts_token_in_path(stats_metrics):
    route = respx.get(f"https://api.crawlbase.com/crawler/{FAKE_TOKEN}/stats").mock(
        return_value=httpx.Response(200, json=STATS)
    )
    assert CrawlerStatsPoller(FAKE_TOKEN, stats_metrics).poll() is True
    assert route.called


@respx.mock
def test_poller_handles_errors(stats_metrics):
    respx.get(f"https://api.crawlbase.com/crawler/{FAKE_TOKEN}/stats").mock(side_effect=httpx.ReadTimeout("x"))
    assert CrawlerStatsPoller(FAKE_TOKEN, stats_metrics).poll() is False
