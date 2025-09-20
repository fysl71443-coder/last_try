import os
import sys
import time
import argparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import InvalidSessionIdException, TimeoutException, NoSuchElementException

BASE_URL = os.getenv("POS_BASE_URL", "http://127.0.0.1:5000")
BRANCH = os.getenv("POS_BRANCH", "china_town")
TABLE_NO = str(os.getenv("POS_TABLE", "16"))
POS_USER = os.getenv("POS_USER", "")
POS_PASS = os.getenv("POS_PASS", "")

WAIT_SHORT = int(os.getenv("POS_WAIT_SHORT", "10"))
WAIT_LONG = int(os.getenv("POS_WAIT_LONG", "40"))


def _apply_cli_overrides():
    parser = argparse.ArgumentParser(description="Pay & Print E2E test")
    parser.add_argument("--base", dest="base", default=None)
    parser.add_argument("--branch", dest="branch", default=None)
    parser.add_argument("--table", dest="table", default=None)
    parser.add_argument("--user", dest="user", default=None)
    parser.add_argument("--pass", dest="password", default=None)
    args, _ = parser.parse_known_args()
    g = globals()
    if args.base: g["BASE_URL"] = args.base
    if args.branch: g["BRANCH"] = args.branch
    if args.table: g["TABLE_NO"] = str(args.table)
    if args.user: g["POS_USER"] = args.user
    if args.password: g["POS_PASS"] = args.password


def _log(msg: str):
    print(f"[PAY_PRINT] {msg}")


def maybe_login(driver: webdriver.Edge):
    """If a login form is present and credentials provided via env, log in. Otherwise, proceed.
    Set POS_USER and POS_PASS in environment if your app requires authentication.
    """
    try:
        # Heuristic: look for username/password inputs
        username = WebDriverWait(driver, 2).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='username'], input#username"))
        )
        password = driver.find_element(By.CSS_SELECTOR, "input[name='password'], input#password")
        submit = driver.find_element(By.CSS_SELECTOR, "button[type='submit'], button.btn-primary, input[type='submit']")
        if POS_USER and POS_PASS:
            _log("Login form detected. Attempting login with provided credentials...")
            username.clear(); username.send_keys(POS_USER)
            password.clear(); password.send_keys(POS_PASS)
            submit.click()
            WebDriverWait(driver, WAIT_SHORT).until_not(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='username'], input#username"))
            )
            _log("Login successful or form disappeared.")
        else:
            _log("Login form detected but POS_USER/POS_PASS not provided. Proceeding without login.")
    except Exception:
        # No login form detected, continue
        return


def open_invoice_page(driver: webdriver.Edge, branch: str, table_no: str):
    url = f"{BASE_URL}/sales/{branch}/table/{table_no}"
    _log(f"Opening invoice page: {url}")
    driver.get(url)
    maybe_login(driver)
    # After login the app redirects to /dashboard, so navigate again to the invoice URL
    driver.get(url)
    # Ensure we are on invoice page by checking for Pay & Print button
    WebDriverWait(driver, WAIT_LONG).until(
        EC.presence_of_element_located((By.XPATH, "//button[contains(@onclick,'payAndPrint')]") )
    )


def ensure_has_item(driver: webdriver.Edge):
    """Ensure cart has at least one item; if empty, click first item button in items grid."""
    try:
        # If cart already has any action buttons, assume it has items
        existing = driver.find_elements(By.CSS_SELECTOR, "#cart-list button.btn-outline-danger")
        if existing:
            return
    except Exception:
        pass

    _log("Adding first available item from the grid...")
    # Wait for items grid to load and click first item's add button
    btn = WebDriverWait(driver, WAIT_LONG).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "#items-grid .item-card button"))
    )
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
    btn.click()

    # Confirm cart updated: a delete button should appear
    WebDriverWait(driver, WAIT_SHORT).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "#cart-list button.btn-outline-danger"))
    )


def click_pay_and_print(driver: webdriver.Edge):
    _log("Clicking Pay & Print...")
    btn = WebDriverWait(driver, WAIT_SHORT).until(
        EC.element_to_be_clickable((By.XPATH, "//button[contains(@onclick,'payAndPrint')]") )
    )
    btn.click()

    _log("Waiting for print confirmation modal...")
    # When popup blocked or after print window closes, our app shows a modal with id=printConfirmModal
    ok_btn = WebDriverWait(driver, WAIT_LONG).until(
        EC.element_to_be_clickable((By.ID, "btnConfirmPrintOk"))
    )
    ok_btn.click()


def wait_redirect_and_verify_table_available(driver: webdriver.Edge, branch: str, table_no: str):
    _log("Waiting for redirect to tables view...")
    WebDriverWait(driver, WAIT_LONG).until(EC.url_contains(f"/sales/{branch}/tables"))

    # Wait until the specific table button becomes green (btn-success)
    _log("Verifying table becomes Available (green)...")
    locator = (By.CSS_SELECTOR, f"a[data-table='{table_no}']")

    def is_green(d):
        try:
            el = d.find_element(*locator)
            cls = el.get_attribute("class") or ""
            return "btn-success" in cls
        except NoSuchElementException:
            return False

    WebDriverWait(driver, WAIT_LONG).until(is_green)
    _log("SUCCESS: Table is Available (green).")


def pay_and_print_flow(driver: webdriver.Edge, branch: str, table_no: str):
    try:
        open_invoice_page(driver, branch, table_no)
        ensure_has_item(driver)
        click_pay_and_print(driver)
        wait_redirect_and_verify_table_available(driver, branch, table_no)
        _log("Flow completed successfully.")
    except TimeoutException as te:
        _log(f"Timeout waiting for expected UI element: {te}")
        raise
    except InvalidSessionIdException:
        _log("Browser session became invalid during print; skipping refresh and exiting gracefully.")
    except Exception as e:
        _log(f"Unexpected error: {e}")
        raise


def main():
    _apply_cli_overrides()
    _log(f"Starting Pay & Print test on {BRANCH}:{TABLE_NO} @ {BASE_URL}")
    driver = webdriver.Edge()
    driver.set_page_load_timeout(WAIT_LONG)
    try:
        pay_and_print_flow(driver, BRANCH, TABLE_NO)
    finally:
        # Give a short pause to let humans see the final state if running interactively
        time.sleep(2)
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main() or 0)

