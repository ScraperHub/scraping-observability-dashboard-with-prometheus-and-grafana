import httpx
import pytest
import respx

from cbwatch.client import InstrumentedCrawlingAPI
from cbwatch.domains import DomainLimiter
from cbwatch.metrics import status_label

from .conftest import FAKE_TOKEN

API = "https://api.crawlbase.com/"


def make_client(metrics, clock=None, **kw):
    ticks = iter([10.0, 12.5] * 50)
    return InstrumentedCrawlingAPI(
        FAKE_TOKEN, "normal", metrics, clock=clock or (lambda: next(ticks)), **kw
    )


def sample(registry, name, **labels):
    return registry.get_sample_value(name, labels)


@respx.mock
def test_success_records_counter_histogram_and_bytes(registry, crawl_metrics):
    respx.get(API).mock(return_value=httpx.Response(
        200, content=b"x" * 1500,
        headers={"cb_status": "200", "original_status": "200", "x-domain-complexity": "standard"},
    ))
    client = make_client(crawl_metrics)
    result = client.get("https://www.example.com/products/1?ref=abc")

    assert result.ok and result.billable and result.domain == "example.com"
    labels = dict(domain="example.com", cb_status="200", original_status="200",
                  http_status="200", token_type="normal", billable="true")
    assert sample(registry, "crawlbase_requests_total", **labels) == 1
    assert sample(registry, "crawlbase_latency_seconds_count", domain="example.com", complexity="standard") == 1
    assert sample(registry, "crawlbase_latency_seconds_sum", domain="example.com", complexity="standard") == 2.5
    assert sample(registry, "crawlbase_latency_seconds_bucket", domain="example.com", complexity="standard", le="3.0") == 1
    assert sample(registry, "crawlbase_latency_seconds_bucket", domain="example.com", complexity="standard", le="2.0") == 0
    assert sample(registry, "crawlbase_response_bytes_sum", domain="example.com") == 1500


@respx.mock
def test_token_and_url_sent_as_query_params(crawl_metrics):
    route = respx.get(API).mock(return_value=httpx.Response(200, headers={"cb_status": "200", "original_status": "200"}))
    make_client(crawl_metrics).get("https://example.com/a?b=c", country="US")
    params = route.calls.last.request.url.params
    assert params["token"] == FAKE_TOKEN
    assert params["url"] == "https://example.com/a?b=c"
    assert params["country"] == "US"


@respx.mock
def test_520_failure_is_labelled_not_raised(registry, crawl_metrics):
    respx.get(API).mock(return_value=httpx.Response(
        520, content=b"",
        headers={"cb_status": "576", "original_status": "403", "x-domain-complexity": "complex"},
    ))
    result = make_client(crawl_metrics).get("https://www.glassdoor.com/Reviews/index.htm")
    assert not result.ok and not result.billable
    assert sample(registry, "crawlbase_requests_total", domain="glassdoor.com", cb_status="576",
                  original_status="403", http_status="520", token_type="normal", billable="false") == 1
    assert sample(registry, "crawlbase_latency_seconds_count", domain="glassdoor.com", complexity="complex") == 1


@respx.mock
def test_404_is_billable(registry, crawl_metrics):
    respx.get(API).mock(return_value=httpx.Response(200, headers={"cb_status": "200", "original_status": "404"}))
    assert make_client(crawl_metrics).get("https://example.com/missing").billable is True


@respx.mock
def test_custom_success_codes_per_call(crawl_metrics):
    respx.get(API).mock(return_value=httpx.Response(200, headers={"cb_status": "200", "original_status": "403"}))
    client = make_client(crawl_metrics)
    assert client.get("https://a.test/", custom_success_codes="403,429").billable is True
    assert client.get("https://a.test/").billable is False


@respx.mock
def test_javascript_param_switches_token_type_label(registry, crawl_metrics):
    respx.get(API).mock(return_value=httpx.Response(200, headers={"cb_status": "200", "original_status": "200"}))
    make_client(crawl_metrics).get("https://a.test/", javascript="true")
    assert sample(registry, "crawlbase_requests_total", domain="a.test", cb_status="200",
                  original_status="200", http_status="200", token_type="js", billable="true") == 1


@respx.mock
def test_json_format_reads_body(registry, crawl_metrics):
    respx.get(API).mock(return_value=httpx.Response(200, json={
        "cb_status": 200, "original_status": 200, "url": "https://a.test/", "domain_complexity": "moderate", "body": "<html/>",
    }))
    result = make_client(crawl_metrics).get("https://a.test/", format="json")
    assert result.signals.complexity == "moderate"


@respx.mock
def test_json_format_with_invalid_body(crawl_metrics):
    respx.get(API).mock(return_value=httpx.Response(200, content=b"not json", headers={"cb_status": "200", "original_status": "200"}))
    assert make_client(crawl_metrics).get("https://a.test/", format="json").signals.cb_status == 200


@respx.mock
def test_timeout_records_error_and_reraises(registry, crawl_metrics):
    respx.get(API).mock(side_effect=httpx.ReadTimeout("timed out"))
    with pytest.raises(httpx.ReadTimeout):
        make_client(crawl_metrics).get("https://www.indeed.com/jobs?q=python")
    assert sample(registry, "crawlbase_client_errors_total", domain="indeed.com", token_type="normal", reason="timeout") == 1
    assert sample(registry, "crawlbase_requests_total", domain="indeed.com", cb_status="none",
                  original_status="none", http_status="none", token_type="normal", billable="false") == 1


@respx.mock
def test_connect_error_is_transport(registry, crawl_metrics):
    respx.get(API).mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(httpx.ConnectError):
        make_client(crawl_metrics).get("https://a.test/")
    assert sample(registry, "crawlbase_client_errors_total", domain="a.test", token_type="normal", reason="transport") == 1


@respx.mock
def test_domain_limiter_applies(registry, crawl_metrics):
    respx.get(API).mock(return_value=httpx.Response(200, headers={"cb_status": "200", "original_status": "200"}))
    client = make_client(crawl_metrics, domain_limiter=DomainLimiter(1))
    client.get("https://a.test/")
    client.get("https://b.test/")
    assert sample(registry, "crawlbase_requests_total", domain="other", cb_status="200",
                  original_status="200", http_status="200", token_type="normal", billable="true") == 1


def test_empty_token_rejected(crawl_metrics):
    with pytest.raises(ValueError):
        InstrumentedCrawlingAPI("", "normal", crawl_metrics)


@pytest.mark.parametrize("code,label", [(None, "none"), (0, "0"), (200, "200"), (576, "576"), (-1, "other"), (1000, "other")])
def test_status_label(code, label):
    assert status_label(code) == label


@respx.mock
def test_attempts_counted_for_every_call(registry, crawl_metrics):
    respx.get(API).mock(side_effect=[
        httpx.Response(200, headers={"cb_status": "200", "original_status": "200"}),
        httpx.Response(520, headers={"cb_status": "0", "original_status": "0"}),
        httpx.ReadTimeout("slow"),
    ])
    client = make_client(crawl_metrics)
    client.get("https://httpbin.org/a")
    client.get("https://httpbin.org/b")
    with pytest.raises(httpx.ReadTimeout):
        client.get("https://httpbin.org/c")
    assert sample(registry, "crawlbase_attempts_total", domain="httpbin.org", token_type="normal") == 3
    total = sum(
        s.value for m in registry.collect() if m.name == "crawlbase_requests"
        for s in m.samples if s.name == "crawlbase_requests_total" and s.labels["domain"] == "httpbin.org"
    )
    assert total == 3  # attempts and outcomes always move together
    assert sample(registry, "crawlbase_requests_total", domain="httpbin.org", cb_status="0",
                  original_status="0", http_status="520", token_type="normal", billable="false") == 1


def test_preregister_creates_zero_series(registry, crawl_metrics):
    client = make_client(crawl_metrics)
    client.preregister(["https://www.glassdoor.com/Reviews/index.htm", "https://example.com/"])
    assert sample(registry, "crawlbase_attempts_total", domain="glassdoor.com", token_type="normal") == 0
    assert sample(registry, "crawlbase_requests_total", domain="example.com", cb_status="200",
                  original_status="200", http_status="200", token_type="normal", billable="true") == 0
