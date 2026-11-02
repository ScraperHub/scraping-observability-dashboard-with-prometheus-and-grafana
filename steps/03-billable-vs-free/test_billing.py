import pytest

from billing import CHARGED_ORIGINAL_STATUSES, is_billable


@pytest.mark.parametrize("cb", [200, 207])
@pytest.mark.parametrize("original", sorted(CHARGED_ORIGINAL_STATUSES))
def test_charged(cb, original):
    assert is_billable(cb, original)


@pytest.mark.parametrize("cb", [200, 207])
@pytest.mark.parametrize("original", [202, 304, 403, 429, 500])
def test_success_with_other_original_is_free(cb, original):
    assert not is_billable(cb, original)


@pytest.mark.parametrize("cb", [0, 503, 515, 520, 525, 576, 595, 599, 702, 704, 705, 706])
def test_failed_cb_status_is_free(cb):
    assert not is_billable(cb, 200)


def test_custom_success_codes():
    assert is_billable(200, 403, {403})
    assert not is_billable(705, 403, {403})
