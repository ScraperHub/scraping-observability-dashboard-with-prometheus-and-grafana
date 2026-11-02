"""Live checks of the assumptions in notes.md. Real tokens, real credits.

Run with `pytest -m live`. The Account API test goes through AccountPoller and its
state file, so it never calls more than once per 5 minutes. Stop the reconciler
first if it shares the state file: its in-memory guard won't see this call.
"""

from __future__ import annotations

import re

import httpx
import pytest
from prometheus_client import CollectorRegistry

from cbwatch.account import AccountPoller
from cbwatch.client import InstrumentedCrawlingAPI
from cbwatch.config import Settings
from cbwatch.metrics import AccountMetrics, CrawlMetrics

pytestmark = pytest.mark.live

TIER = re.compile(r"^[a-z][a-z0-9_]{0,23}$")


@pytest.fixture(scope="module")
def settings() -> Settings:
    s = Settings.from_env()
    assert s.normal_token and s.js_token, "set CRAWLBASE_NORMAL_TOKEN and CRAWLBASE_JS_TOKEN"
    return s


@pytest.fixture()
def client(settings):
    def make(token_type: str = "normal") -> InstrumentedCrawlingAPI:
        return InstrumentedCrawlingAPI(
            settings.token_for(token_type), token_type, CrawlMetrics(CollectorRegistry()),
            base_url=settings.api_base, timeout=settings.request_timeout,
        )
    return make


def test_html_format_sends_complexity_as_header(settings):
    r = httpx.get(
        f"{settings.api_base}/",
        params={"token": settings.normal_token, "url": "https://example.com/"},
        timeout=settings.request_timeout,
    )
    assert r.status_code == 200
    assert "x-domain-complexity" in r.headers
    assert TIER.match(r.headers["x-domain-complexity"])
    assert "cb_status" in r.headers or "pc_status" in r.headers
    assert r.headers.get("original_status") == "200"


def test_json_format_sends_complexity_as_field(client):
    with client() as api:
        result = api.get("https://example.com/", format="json")
    assert result.ok
    assert TIER.match(result.signals.complexity)
    assert "domain_complexity" in httpx.Response(200, content=result.body).json()


def test_target_404_is_a_valid_billable_answer(client):
    with client() as api:
        result = api.get("https://example.com/does-not-exist")
    assert (result.signals.http_status, result.signals.cb_status, result.signals.original_status) == (200, 200, 404)
    assert result.billable


def test_normal_token_on_protected_site_fails_as_free_520_or_succeeds_billed(client):
    with client("normal") as api:
        result = api.get("https://www.glassdoor.com/Reviews/index.htm")
    if result.ok:
        assert result.billable
    else:
        assert result.signals.http_status == 520
        assert result.signals.cb_status != 200
        assert not result.billable


def test_js_token_fetches_page(client):
    with client("js") as api:
        result = api.get("https://example.org/", javascript="true")
    assert result.token_type == "js"
    assert result.ok and result.billable
    assert b"Example Domain" in result.body


def test_account_api_shape_through_the_guard(settings):
    raw: list[dict] = []

    def capture(response: httpx.Response) -> None:
        response.read()
        if response.status_code == 200:
            raw.append(response.json())

    http = httpx.Client(timeout=60, event_hooks={"response": [capture]})
    poller = AccountPoller(
        settings.normal_token, product=settings.account_product, base_url=settings.api_base,
        state_file=settings.account_state_file, http=http,
    )
    snapshot = poller.poll(AccountMetrics(CollectorRegistry()))
    assert snapshot is not None, "no fresh call allowed and no cached snapshot in the state file"
    assert poller.seconds_until_allowed() > 0

    assert snapshot.total_success >= 0 and snapshot.total_failed >= 0
    assert snapshot.domains, "domainStats is empty"
    assert all("." not in d.domain for d in snapshot.domains), "expected bare site names"
    assert all(0.0 <= d.success_rate <= 1.0 for d in snapshot.domains)

    if raw:  # fresh call: check the raw shape too
        month = raw[0]["currentMonth"]
        assert isinstance(month["totalSuccess"], str)
        entry = month["domainStats"][0]
        assert set(entry) >= {"domain", "metrics"}
        assert {"totalRequests", "success", "failure", "successRate"} <= set(entry["metrics"])
        assert str(entry["metrics"]["successRate"]).endswith("%")
