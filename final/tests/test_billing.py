import pytest

from cbwatch.billing import (
    CHARGED_ORIGINAL_STATUSES,
    is_billable,
    parse_success_codes,
)

CHARGED_ORIGINALS = sorted(CHARGED_ORIGINAL_STATUSES)
FREE_ORIGINALS = [202, 204, 304, 400, 401, 403, 429, 500, 502, 503, 515]
# Documented failure cb_status values plus the ones observed live (0, 515, 576, 702).
FAILED_CB = [0, 503, 504, 515, 520, 525, 576, 595, 599, 601, 702, 704, 705, 706, 999]


@pytest.mark.parametrize("cb", [200, 207])
@pytest.mark.parametrize("original", CHARGED_ORIGINALS)
def test_success_with_charged_original_is_billable(cb, original):
    assert is_billable(cb, original) is True


@pytest.mark.parametrize("cb", [200, 207])
@pytest.mark.parametrize("original", FREE_ORIGINALS)
def test_success_with_other_original_is_free(cb, original):
    assert is_billable(cb, original) is False


@pytest.mark.parametrize("cb", FAILED_CB)
@pytest.mark.parametrize("original", CHARGED_ORIGINALS + [403, 429, 500])
def test_failed_cb_status_is_always_free(cb, original):
    assert is_billable(cb, original) is False


def test_documented_charged_list_is_exact():
    assert CHARGED_ORIGINAL_STATUSES == {200, 201, 301, 302, 303, 307, 308, 404, 410}


@pytest.mark.parametrize("cb,original", [(None, 200), (200, None), (None, None)])
def test_missing_status_is_free(cb, original):
    assert is_billable(cb, original) is False


def test_custom_success_codes_are_charged():
    assert is_billable(200, 403, custom_success_codes={403, 429}) is True
    assert is_billable(200, 429, custom_success_codes=[403, 429]) is True
    assert is_billable(200, 500, custom_success_codes={403}) is False


def test_custom_success_codes_do_not_rescue_failed_cb_status():
    assert is_billable(705, 403, custom_success_codes={403}) is False


def test_parse_success_codes():
    assert parse_success_codes("403,429, 503") == {403, 429, 503}
    assert parse_success_codes("") == frozenset()
    assert parse_success_codes(None) == frozenset()
    assert parse_success_codes([403]) == {403}
