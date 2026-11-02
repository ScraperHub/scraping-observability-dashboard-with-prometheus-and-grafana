import pytest

from cbwatch.domains import DomainLimiter, domain_label


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.example.com/a/b?c=d#e", "example.com"),
        ("https://Example.COM", "example.com"),
        ("http://catalog.example.com:8080/page-2.html", "catalog.example.com"),
        ("https://shop.example.co.uk/item/123", "shop.example.co.uk"),
        ("https://www.glassdoor.com/Reviews/index.htm", "glassdoor.com"),
        ("example.com/path", "example.com"),
        ("https://example.com./", "example.com"),
        ("https://user:pw@api.example.com/x", "api.example.com"),
        ("https://bücher.de/", "xn--bcher-kva.de"),
        ("https://www2.example.com/", "www2.example.com"),
    ],
)
def test_domain_label(url, expected):
    assert domain_label(url) == expected


@pytest.mark.parametrize("url", ["", "https://", "http://[::1", "https:///path-only"])
def test_invalid_urls(url):
    assert domain_label(url) == "invalid"


def test_path_and_query_never_leak_into_label():
    labels = {domain_label(f"https://example.com/item/{i}?q={i}") for i in range(1000)}
    assert labels == {"example.com"}


def test_limiter_caps_distinct_domains():
    limit = DomainLimiter(max_domains=2)
    assert limit("a.com") == "a.com"
    assert limit("b.com") == "b.com"
    assert limit("c.com") == "other"
    assert limit("a.com") == "a.com"
