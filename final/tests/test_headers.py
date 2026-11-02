import pytest

from cbwatch.headers import parse_signals


def test_html_format_headers_lowercase_x_spelling():
    # Exactly what the live API returned for format=html.
    headers = {
        "pc_status": "200",
        "cb_status": "200",
        "original_status": "200",
        "url": "https://example.com/",
        "x-domain-complexity": "standard",
    }
    s = parse_signals(200, headers)
    assert (s.http_status, s.cb_status, s.original_status) == (200, 200, 200)
    assert s.complexity == "standard"
    assert s.final_url == "https://example.com/"


def test_json_format_body_domain_complexity_spelling():
    body = {"cb_status": 200, "original_status": 404, "url": "https://x.test/", "domain_complexity": "moderate"}
    s = parse_signals(200, {"content-type": "application/json"}, body)
    assert s.cb_status == 200
    assert s.original_status == 404
    assert s.complexity == "moderate"


@pytest.mark.parametrize("name", ["X-Domain-Complexity", "x-domain-complexity", "domain_complexity", "Domain-Complexity"])
def test_both_complexity_spellings_in_headers(name):
    assert parse_signals(200, {name: "complex"}).complexity == "complex"


def test_undocumented_tier_is_kept():
    # Walmart returned "complex_ii" live, which the docs do not list.
    assert parse_signals(200, {"x-domain-complexity": "complex_ii"}).complexity == "complex_ii"


@pytest.mark.parametrize("value", ["", None, "Complex Tier!", "x" * 40, "<script>"])
def test_bad_complexity_becomes_unknown(value):
    headers = {} if value is None else {"x-domain-complexity": value}
    assert parse_signals(200, headers).complexity == "unknown"


def test_complexity_is_lowercased():
    assert parse_signals(200, {"X-Domain-Complexity": " Standard "}).complexity == "standard"


def test_failed_crawl_520():
    headers = {"cb_status": "576", "original_status": "403", "x-domain-complexity": "complex"}
    s = parse_signals(520, headers)
    assert (s.http_status, s.cb_status, s.original_status) == (520, 576, 403)


def test_pc_status_fallback_and_dash_spelling():
    assert parse_signals(200, {"pc_status": "207"}).cb_status == 207
    assert parse_signals(200, {"CB-Status": "503", "Original-Status": "200"}).cb_status == 503


def test_missing_and_garbage_statuses():
    s = parse_signals(401, {"cb_status": "abc"})
    assert s.cb_status is None
    assert s.original_status is None
    assert s.complexity == "unknown"


def test_headers_win_over_json_body():
    s = parse_signals(200, {"cb_status": "200"}, {"cb_status": 503})
    assert s.cb_status == 200


def test_remaining_header_parsed_when_present():
    assert parse_signals(200, {"remaining": "17"}).remaining == 17
    assert parse_signals(200, {}).remaining is None
