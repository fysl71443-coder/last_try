import re
from typing import List, Tuple

from app import app, BRANCH_CODES

# Simple smoke tester for buttons/links presence and misrouting in key screens.
# - Uses Flask test_client with LOGIN_DISABLED to bypass login during GETs
# - Does not mutate data (no POST). Safe for running on dev.
# - Validates: presence of Back buttons, CSRF tokens in forms, payment method select in payments,
#   branch filter in reports, and flags any Back buttons that force redirect to employees.

CHECKS = []  # type: List[Tuple[str, str]]

# Build an ordered list of screens to visit
CHECKS.append(("Sales branches", "/sales"))
# Choose a deterministic first branch for tables page
first_branch = next(iter(BRANCH_CODES.keys())) if BRANCH_CODES else "place_india"
CHECKS.append((f"Sales tables ({first_branch})", f"/sales/{first_branch}/tables"))
CHECKS.append(("Menu admin", "/menu"))
CHECKS.append(("Payments", "/payments"))
CHECKS.append(("Reports", "/reports"))
CHECKS.append(("Settings", "/settings"))


def has_back_button(html: str) -> bool:
    # Look for any button/link with Back/رجوع text or calling safeBack(
    if re.search(r">\s*(Back|رجوع)\s*<", html, re.IGNORECASE):
        return True
    if "safeBack(" in html:
        return True
    return False


def back_points_to_employees(html: str) -> bool:
    # Detect explicit unsafe default to employees in onclick or href
    if re.search(r"safeBack\(['\"]\s*/employees", html):
        return True
    if re.search(r"href=\"/employees\"", html):
        return True
    return False


def count_csrf_tokens(html: str) -> int:
    return len(re.findall(r'name=\"csrf_token\"', html))


def has_pay_method_select(html: str) -> bool:
    return 'class="form-select form-select-sm pay-method"' in html or 'class="pay-method"' in html


def has_reports_branch_filter(html: str) -> bool:
    return 'name="branch"' in html and re.search(r"<select[^>]+name=\"branch\"", html)


def run():
    app.config['LOGIN_DISABLED'] = True  # bypass @login_required during GETs
    passed = 0
    failed = 0
    results = []

    with app.test_client() as client:
        for name, path in CHECKS:
            resp = client.get(path, follow_redirects=True)
            ok = resp.status_code == 200
            html = resp.get_data(as_text=True)
            errs = []
            if not ok:
                errs.append(f"HTTP {resp.status_code}")
            # Back button sanity
            if not has_back_button(html):
                # Not all screens must have Back, so we only warn, not fail
                results.append((name, path, ok, [*errs, "warn: no back button detected"]))
            else:
                if back_points_to_employees(html):
                    errs.append("bad back: points to /employees")
            # Screen-specific checks
            if path == "/payments":
                if count_csrf_tokens(html) == 0:
                    errs.append("missing CSRF token")
                if not has_pay_method_select(html):
                    errs.append("missing payment method select")
            if path == "/reports":
                if not has_reports_branch_filter(html):
                    errs.append("missing reports branch filter")
            results.append((name, path, ok and not errs, errs))

    # Summary
    print("UI Button Smoke Test Results:\n------------------------------")
    for name, path, ok, errs in results:
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name} -> {path}")
        for e in errs:
            if e:
                print(f"    - {e}")
        if not errs:
            print("    - ok")
        if not ok:
            failed += 1
        else:
            passed += 1
    print("------------------------------")
    print(f"Passed: {passed}, Failed: {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(run())

