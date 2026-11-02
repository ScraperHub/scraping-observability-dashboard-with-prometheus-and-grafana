import json

import httpx
import pytest
import respx

from cbwatch.account import (
    MIN_INTERVAL_SECONDS,
    AccountPoller,
    apply_snapshot,
    parse_account,
    parse_domain_stat,
)

from .conftest import FAKE_TOKEN

ACCOUNT_URL = "https://api.crawlbase.com/account"

# Shape observed from the live API (values replaced).
OBSERVED = {
    "currentMonth": {
        "totalSuccess": "19",
        "totalFailed": "10",
        "totalDue": 0.0,
        "domainStats": [
            {"domain": "walmart", "metrics": {"totalRequests": 5, "success": 5, "failure": 0, "successRate": "100.0%"}},
            {"domain": "amazon", "metrics": {"totalRequests": 4, "success": 3, "failure": 1, "successRate": "75.0%"}},
        ],
    }
}

# Flat shape from the documentation table.
DOCUMENTED = {
    "totalSuccess": 900,
    "totalFailed": 100,
    "totalDue": 1.5,
    "remainingCredits": 4100,
    "domainStats": [
        {"domain": "example.com", "totalRequests": 1000, "success": 900, "failure": 100, "successRate": 90.0},
    ],
}


def test_parse_observed_shape():
    snap = parse_account(OBSERVED)
    assert (snap.total_success, snap.total_failed, snap.total_due) == (19, 10, 0.0)
    assert snap.remaining_credits is None
    assert [d.domain for d in snap.domains] == ["walmart", "amazon"]
    assert snap.domains[1].success_rate == pytest.approx(0.75)


def test_parse_documented_shape():
    snap = parse_account(DOCUMENTED)
    assert snap.remaining_credits == 4100
    assert snap.domains[0].success_rate == pytest.approx(0.9)


@pytest.mark.parametrize("raw,expected", [("98.5%", 0.985), (98.5, 0.985), (0.985, 0.985), ("100.0%", 1.0), ("0.0%", 0.0)])
def test_success_rate_fallback_when_totals_missing(raw, expected):
    stat = parse_domain_stat({"domain": "x", "metrics": {"successRate": raw}})
    assert stat.success_rate == pytest.approx(expected)


def test_counts_win_over_success_rate_string():
    stat = parse_domain_stat({"domain": "x", "metrics": {"totalRequests": 10, "success": 9, "successRate": "1.0%"}})
    assert stat.success_rate == pytest.approx(0.9)


def test_empty_domain_stats_for_crawler_product():
    snap = parse_account({"currentMonth": {"totalSuccess": "0", "totalFailed": "0", "totalDue": 0.0, "domainStats": []}})
    assert snap.domains == ()


def make_poller(clock, tmp_path=None, **kw):
    state = tmp_path / "state.json" if tmp_path else None
    return AccountPoller(FAKE_TOKEN, clock=clock, state_file=state, http=httpx.Client(), **kw)


@respx.mock
def test_poll_sends_token_and_product(clock, account_metrics):
    route = respx.get(ACCOUNT_URL).mock(return_value=httpx.Response(200, json=OBSERVED))
    snap = make_poller(clock).poll(account_metrics)
    assert snap.total_success == 19
    params = route.calls.last.request.url.params
    assert params["token"] == FAKE_TOKEN and params["product"] == "crawling-api"


@respx.mock
def test_five_minute_guard_serves_cache(clock, registry, account_metrics):
    route = respx.get(ACCOUNT_URL).mock(return_value=httpx.Response(200, json=OBSERVED))
    poller = make_poller(clock)
    first = poller.poll(account_metrics)
    for _ in range(10):
        clock.advance(29)
        assert poller.poll(account_metrics) is first
    assert route.call_count == 1
    assert registry.get_sample_value("crawlbase_account_cache_hits_total") == 10
    clock.advance(MIN_INTERVAL_SECONDS - 290)
    poller.poll(account_metrics)
    assert route.call_count == 2


def test_api_call_series_exist_before_first_call(registry, account_metrics):
    for result in ("ok", "error", "timeout"):
        assert registry.get_sample_value("crawlbase_account_api_calls_total", {"result": result}) == 0


def test_interval_below_limit_is_clamped(clock):
    assert make_poller(clock, min_interval=10).min_interval == MIN_INTERVAL_SECONDS


@respx.mock
def test_failed_call_still_counts_against_limit(clock, registry, account_metrics):
    route = respx.get(ACCOUNT_URL).mock(return_value=httpx.Response(429, json={"error": "rate limited"}))
    poller = make_poller(clock)
    assert poller.poll(account_metrics) is None
    clock.advance(60)
    poller.poll(account_metrics)
    assert route.call_count == 1
    assert registry.get_sample_value("crawlbase_account_api_calls_total", {"result": "error"}) == 1


@respx.mock
def test_timeout_returns_cached(clock, registry, account_metrics):
    respx.get(ACCOUNT_URL).mock(side_effect=[httpx.Response(200, json=OBSERVED), httpx.ReadTimeout("slow")])
    poller = make_poller(clock)
    first = poller.poll(account_metrics)
    clock.advance(MIN_INTERVAL_SECONDS)
    assert poller.poll(account_metrics) is first
    assert registry.get_sample_value("crawlbase_account_api_calls_total", {"result": "timeout"}) == 1


@respx.mock
def test_invalid_json_returns_cached(clock, account_metrics):
    respx.get(ACCOUNT_URL).mock(return_value=httpx.Response(200, content=b"<html>"))
    assert make_poller(clock).poll(account_metrics) is None


@respx.mock
def test_guard_survives_restart(clock, tmp_path, account_metrics):
    route = respx.get(ACCOUNT_URL).mock(return_value=httpx.Response(200, json=OBSERVED))
    make_poller(clock, tmp_path).poll(account_metrics)
    clock.advance(120)
    restarted = make_poller(clock, tmp_path)
    assert restarted.cached.total_success == 19
    assert restarted.seconds_until_allowed() == pytest.approx(180)
    restarted.poll(account_metrics)
    assert route.call_count == 1


def test_state_file_never_contains_token(clock, tmp_path):
    with respx.mock:
        respx.get(ACCOUNT_URL).mock(return_value=httpx.Response(200, json=OBSERVED))
        make_poller(clock, tmp_path).poll()
    assert FAKE_TOKEN not in (tmp_path / "state.json").read_text()


def test_corrupt_state_is_ignored(clock, tmp_path):
    (tmp_path / "state.json").write_text("{not json")
    assert make_poller(clock, tmp_path).seconds_until_allowed() == 0


def test_apply_snapshot_sets_gauges(registry, account_metrics):
    apply_snapshot(parse_account(OBSERVED), account_metrics, monthly_budget=1000, now=123.0)
    g = registry.get_sample_value
    assert g("crawlbase_account_total_success") == 19
    assert g("crawlbase_account_total_failed") == 10
    assert g("crawlbase_account_remaining_credits", {"source": "budget"}) == 981
    assert g("crawlbase_account_remaining_credits", {"source": "account_api"}) is None
    assert g("crawlbase_account_domain_success_rate", {"domain": "amazon"}) == pytest.approx(0.75)
    assert g("crawlbase_account_last_poll_timestamp_seconds") == 123.0


def test_apply_snapshot_prefers_api_credits(registry, account_metrics):
    apply_snapshot(parse_account(DOCUMENTED), account_metrics, monthly_budget=1000)
    assert registry.get_sample_value("crawlbase_account_remaining_credits", {"source": "account_api"}) == 4100
    assert registry.get_sample_value("crawlbase_account_remaining_credits", {"source": "budget"}) is None


def test_apply_snapshot_caps_domains(registry, account_metrics):
    payload = json.loads(json.dumps(OBSERVED))
    apply_snapshot(parse_account(payload), account_metrics, max_domains=1)
    assert registry.get_sample_value("crawlbase_account_domain_success_rate", {"domain": "walmart"}) == 1.0
    assert registry.get_sample_value("crawlbase_account_domain_success_rate", {"domain": "amazon"}) is None
