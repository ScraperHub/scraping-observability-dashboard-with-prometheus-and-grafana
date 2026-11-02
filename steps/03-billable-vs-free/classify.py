"""Print the billing decision for the status combinations seen in the live runs."""

from billing import is_billable

# (http_status, cb_status, original_status, note) - all observed live in Nov 2026
CASES = [
    (200, 200, 200, "normal success"),
    (200, 200, 404, "page gone, still a valid answer"),
    (520, 576, 403, "blocked, Normal token on a protected site"),
    (520, 503, 403, "block or CAPTCHA detected"),
    (520, 705, 403, "target answered 403"),
    (520, 702, 429, "target rate limited us"),
    (520, 704, 500, "target answered 5xx"),
    (520, 515, 515, "DNS failure"),
    (520, 0, 0, "no upstream answer at all"),
]


def main() -> None:
    print(f"{'http':>4} {'cb':>4} {'orig':>4}  {'billable':<8}  note")
    for http, cb, orig, note in CASES:
        print(f"{http:>4} {cb:>4} {orig:>4}  {str(is_billable(cb, orig)).lower():<8}  {note}")
    print(f"\ncustom_success_codes=403: 200/403 billable = {is_billable(200, 403, {403})}")


if __name__ == "__main__":
    main()
