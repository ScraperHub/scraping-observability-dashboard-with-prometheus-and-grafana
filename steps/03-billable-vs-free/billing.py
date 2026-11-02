"""Step 03: billable vs free, straight from the Crawling API pricing rules.

Charged only when cb_status is 200 or 207 AND original_status is in the list
below, or in custom_success_codes. Everything else is free.
"""

CHARGED_CB_STATUSES = frozenset({200, 207})
CHARGED_ORIGINAL_STATUSES = frozenset({200, 201, 301, 302, 303, 307, 308, 404, 410})


def is_billable(cb_status, original_status, custom_success_codes=()):
    if cb_status not in CHARGED_CB_STATUSES or original_status is None:
        return False
    return original_status in CHARGED_ORIGINAL_STATUSES or original_status in set(custom_success_codes)
