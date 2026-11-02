import pytest
from prometheus_client import CollectorRegistry

from cbwatch.metrics import AccountMetrics, CrawlerStatsMetrics, CrawlMetrics

# Obviously fake token. Real tokens never appear in tests or fixtures.
FAKE_TOKEN = "test-token-not-real"


@pytest.fixture
def registry():
    return CollectorRegistry()


@pytest.fixture
def crawl_metrics(registry):
    return CrawlMetrics(registry)


@pytest.fixture
def account_metrics(registry):
    return AccountMetrics(registry)


@pytest.fixture
def stats_metrics(registry):
    return CrawlerStatsMetrics(registry)


class FakeClock:
    def __init__(self, start: float = 1_000_000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock():
    return FakeClock()
