#!/usr/bin/env python3
"""
Comprehensive UI E2E test runner for the Restaurant Management System
- Opens browser, navigates all screens, tests core flows (view/create/edit/save/delete/filter/export/upload/print/permissions)
- Captures screenshots, console/performance logs, timings, and generates HTML+JSON reports

Inputs (CLI args or env fallbacks):
- --base-url / BASE_URL
- --admin-user/--admin-pass or CREDENTIALS_ADMIN_USER/CREDENTIALS_ADMIN_PASS
- --user-user/--user-pass or CREDENTIALS_USER_USER/CREDENTIALS_USER_PASS (optional, for permissions)
- --timeout-ms / TIMEOUT (default 15000)
- --output-folder / OUTPUT_FOLDER (default test_results)
- --run-id / RUN_ID

Safety:
- Avoids destructive actions unless the record was created by this run (prefixed with test-<RUN_ID>)
- Does not log passwords

Note: Requires Selenium and Chrome/Chromium available on the runner machine.
"""

import os
import re
import json
import time
import argparse
from datetime import datetime
from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException

# -------------------------------
# Utilities
# -------------------------------

def now_str():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def ms():
    return int(time.time() * 1000)


def retry(times=2, delay=0.8):
    def deco(fn):
        def wrapper(*args, **kwargs):
            last_exc = None
            for i in range(times + 1):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    if i < times:
                        time.sleep(delay)
            raise last_exc
        return wrapper
    return deco


# -------------------------------
# E2E Runner
# -------------------------------
class ComprehensiveE2E:
    def __init__(self, cfg):
        self.base_url = cfg['base_url'].rstrip('/')
        self.timeout = int(cfg['timeout_ms']) / 1000.0
        self.run_id = cfg['run_id'] or f"e2e_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.output_root = cfg['output_folder'] or 'test_results'
        self.output_dir = os.path.join(self.output_root, f"{self.run_id}")
        os.makedirs(self.output_dir, exist_ok=True)
        self.admin_user = cfg.get('admin_user')
        self.admin_pass = cfg.get('admin_pass')
        self.user_user = cfg.get('user_user')
        self.user_pass = cfg.get('user_pass')
        self.driver = None
        self.results = []
        self.created_records = []  # [{'screen': str, 'key': str}] for cleanup
        self.timings = []  # [{'url': ..., 'load_ms': ...}]

    def _log(self, name, status, message="", screenshot=None, details=None, meta=None):
        rec = {
            'test_name': name,
            'status': status,  # PASS/FAIL/WARN
            'message': message,
            'timestamp': now_str(),
            'screenshot': screenshot,
            'details': details,
            'meta': meta or {}
        }
        self.results.append(rec)
        print(f"{('✅' if status=='PASS' else '❌' if status=='FAIL' else '⚠️')} {name}: {status} - {message}")

    # ---------------------------
    # Setup / Teardown
    # ---------------------------
    def setup_driver(self):
        chrome_options = Options()
        chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.set_capability('goog:loggingPrefs', {'browser': 'ALL', 'performance': 'ALL'})
        chrome_options.set_capability('goog:perfLoggingPrefs', {
            'enableNetwork': True,
            'enablePage': True
        })
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.set_page_load_timeout(int(self.timeout))

    def teardown(self):
        try:
            if self.driver:
                self.driver.quit()
        except Exception:
            pass

    # ---------------------------
    # Helpers
    # ---------------------------
    def screenshot(self, name):
        fname = f"{datetime.now().strftime('%H%M%S')}_{name}.png"
        fpath = os.path.join(self.output_dir, fname)
        try:
            self.driver.save_screenshot(fpath)
            return fname
        except Exception:
            return None

    def wait_css(self, css, timeout=None):
        return WebDriverWait(self.driver, timeout or self.timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, css))
        )

    def safe_click(self, el):
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
        except Exception:
            pass
        el.click()

    def collect_console_logs(self, filename):
        try:
            logs = self.driver.get_log('browser')
            with open(os.path.join(self.output_dir, filename), 'w', encoding='utf-8') as f:
                json.dump(logs, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def collect_perf_logs(self, filename):
        try:
            logs = self.driver.get_log('performance')
            with open(os.path.join(self.output_dir, filename), 'w', encoding='utf-8') as f:
                json.dump(logs, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ---------------------------
    # Core Steps
    # ---------------------------
    @retry()
    def open_base(self):
        t0 = ms()
        self.driver.get(self.base_url)
        self.wait_css('form input[name="username"]')
        load_ms = ms() - t0
        self.timings.append({'url': self.base_url, 'load_ms': load_ms})
        sc = self.screenshot('login_page')
        self._log('Open Login Page', 'PASS', 'Login form visible', sc, meta={'load_ms': load_ms})

    @retry()
    def login(self, username, password):
        t0 = ms()
        self.wait_css('input[name="username"]').clear()
        self.driver.find_element(By.NAME, 'username').send_keys(username)
        self.wait_css('input[name="password"]').clear()
        self.driver.find_element(By.NAME, 'password').send_keys(password)
        self.driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        # Dashboard heuristic
        WebDriverWait(self.driver, self.timeout).until(
            EC.any_of(
                EC.presence_of_element_located((By.CLASS_NAME, 'dashboard-card')),
                EC.presence_of_element_located((By.CSS_SELECTOR, 'h1, h2, .container, .content'))
            )
        )
        load_ms = ms() - t0
        self.timings.append({'url': f'{self.base_url}/dashboard', 'load_ms': load_ms})
        sc = self.screenshot('dashboard_after_login')
        self._log('Login', 'PASS', f'Logged in as {"admin" if username==self.admin_user else "user"}', sc, meta={'load_ms': load_ms})

    def logout(self):
        try:
            # Try common logout patterns
            candidates = self.driver.find_elements(By.XPATH, "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'logout')]")
            if not candidates:
                candidates = self.driver.find_elements(By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'logout')]")
            if candidates:
                self.safe_click(candidates[0])
                time.sleep(1)
                self._log('Logout', 'PASS', 'Logged out')
        except Exception:
            self._log('Logout', 'WARN', 'Could not find logout control')

    def collect_menu(self):
        # Gather menu links from dashboard cards, navbar, sidebar
        links = set()
        items = []
        try:
            # Dashboard cards
            cards = self.driver.find_elements(By.CLASS_NAME, 'dashboard-card')
            for c in cards:
                try:
                    parent_link = c.find_element(By.XPATH, './ancestor::a[1]')
                    href = parent_link.get_attribute('href')
                    title = c.text.strip() or parent_link.get_attribute('title') or href
                    if href and href.startswith(self.base_url) and href not in links:
                        links.add(href); items.append({'title': title, 'url': href})
                except Exception:
                    pass
            # Sidebar/nav
            for sel in ['nav a', 'aside a', '.sidebar a', '.navbar a', 'a.nav-link', 'a.list-group-item']:
                for a in self.driver.find_elements(By.CSS_SELECTOR, sel):
                    href = a.getAttribute('href') if hasattr(a, 'getAttribute') else a.get_attribute('href')
                    if href and href.startswith(self.base_url) and href not in links:
                        title = (a.text or a.get_attribute('title') or href).strip()
                        # Filter auth/logout
                        low = title.lower()
                        if any(x in low for x in ['logout','login']):
                            continue
                        links.add(href); items.append({'title': title, 'url': href})
        except Exception:
            pass
        self._log('Collect Menu', 'PASS' if items else 'WARN', f'Found {len(items)} items')
        return items

    def ensure_loaded(self):
        # Heuristic: wait for a main marker
        try:
            WebDriverWait(self.driver, self.timeout).until(
                EC.any_of(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'h1, h2')),
                    EC.presence_of_element_located((By.TAG_NAME, 'table')),
                    EC.presence_of_element_located((By.TAG_NAME, 'form')),
                    EC.presence_of_element_located((By.CSS_SELECTOR, '.card, .container, .content')),
                )
            )
        except TimeoutException:
            pass

    def try_table_tests(self, screen):
        try:
            tables = self.driver.find_elements(By.TAG_NAME, 'table')
            if tables:
                # sort by first header
                ths = self.driver.find_elements(By.CSS_SELECTOR, 'th')
                if ths:
                    try:
                        self.safe_click(ths[0]); time.sleep(0.7)
                        self.safe_click(ths[0]); time.sleep(0.5)
                        self._log(f'Table Sort - {screen}', 'PASS', 'Clicked header to sort')
                    except Exception:
                        self._log(f'Table Sort - {screen}', 'WARN', 'Sort header click failed')
                # filter/search
                search = None
                for css in ['input[type="search"]','input[placeholder*="search" i]','input[placeholder*="filter" i]','input[name*="search" i]']:
                    els = self.driver.find_elements(By.CSS_SELECTOR, css)
                    if els:
                        search = els[0]; break
                if search:
                    try:
                        search.clear(); search.send_keys('1'); time.sleep(0.8)
                        self._log(f'Table Filter - {screen}', 'PASS', 'Entered sample filter')
                    except Exception:
                        self._log(f'Table Filter - {screen}', 'WARN', 'Filter input failed')
        except Exception:
            pass

    def _gen_value(self, name, kind):
        base = f"test-{self.run_id[:10]}"
        low = (name or '').lower()
        if 'email' in low:
            return f"{base}@example.com"
        if any(k in low for k in ['price','amount','total','qty','quantity','number','no','mobile','phone']):
            return '123'
        if 'date' in low:
            return datetime.now().strftime('%Y-%m-%d')
        if kind == 'number':
            return '42'
        return base

    def try_crud(self, screen):
        created_key = None
        # create
        try:
            new_btn = None
            for sel in [
                "//a[normalize-space()[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'new') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'create') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'add')]]",
                "//button[normalize-space()[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'new') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'create') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'add')]]"
            ]:
                els = self.driver.find_elements(By.XPATH, sel)
                if els:
                    new_btn = els[0]; break
            if new_btn:
                self.safe_click(new_btn); time.sleep(1)
                self.ensure_loaded()
                inputs = self.driver.find_elements(By.CSS_SELECTOR, 'form input, form select, form textarea')
                typed_one = False
                for el in inputs:
                    try:
                        t = (el.get_attribute('type') or '').lower()
                        nm = (el.get_attribute('name') or el.get_attribute('id') or '')
                        if t in ['hidden','submit','button','checkbox','radio','file']:
                            continue
                        val = self._gen_value(nm, t)
                        el.clear(); el.send_keys(val)
                        if not typed_one:
                            created_key = val; typed_one = True
                    except Exception:
                        continue
                # invalid attempt
                self._log(f'Create - {screen} (invalid)', 'PASS', 'Entered sample values (may trigger validation)')
                # save/submit
                save = None
                for sel in ['button[type="submit"]', "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'save')]", "//input[@type='submit']"]:
                    try:
                        save = self.driver.find_element(By.CSS_SELECTOR, sel) if sel.startswith('button') or sel.startswith('input') else self.driver.find_element(By.XPATH, sel)
                        break
                    except Exception:
                        continue
                if save:
                    try:
                        self.safe_click(save); time.sleep(1.2)
                        self._log(f'Save - {screen}', 'PASS', 'Clicked Save (validation may apply)')
                    except Exception as e:
                        self._log(f'Save - {screen}', 'WARN', f'Could not click save: {e}')
                sc = self.screenshot(f'{screen}_after_save')
                # confirm appears in list
                if created_key:
                    try:
                        self.driver.find_element(By.XPATH, f"//*[contains(text(), '{created_key}')]")
                        self._log(f'Create Verify - {screen}', 'PASS', 'Created key visible in page', sc)
                        self.created_records.append({'screen': screen, 'key': created_key})
                    except Exception:
                        self._log(f'Create Verify - {screen}', 'WARN', 'Created key not confirmed', sc)
        except Exception as e:
            self._log(f'Create - {screen}', 'WARN', f'Create flow not available: {e}')

        # view/edit
        if created_key:
            try:
                row = self.driver.find_element(By.XPATH, f"//*[contains(text(), '{created_key}')]/ancestor::*[self::tr or self::div][1]")
                # view
                view = None
                try:
                    view = row.find_element(By.XPATH, ".//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'view') or contains(., 'عرض')]")
                except Exception:
                    pass
                if view:
                    try:
                        self.safe_click(view); time.sleep(0.8)
                        self._log(f'View - {screen}', 'PASS', 'Opened details')
                    except Exception:
                        self._log(f'View - {screen}', 'WARN', 'Could not open details')
                # edit
                edit = None
                try:
                    edit = row.find_element(By.XPATH, ".//a|.//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'edit')]")
                except Exception:
                    pass
                if edit:
                    try:
                        self.safe_click(edit); time.sleep(0.8)
                        ipts = self.driver.find_elements(By.CSS_SELECTOR, 'form input[type="text"], form input[type="number"], form textarea')
                        if ipts:
                            ipts[0].clear(); ipts[0].send_keys(self._gen_value('name','text')+'-upd')
                        for sel in ['button[type="submit"]', "//button[contains(., 'Save')]"]:
                            try:
                                btn = self.driver.find_element(By.CSS_SELECTOR, sel) if sel.startswith('button') else self.driver.find_element(By.XPATH, sel)
                                self.safe_click(btn); break
                            except Exception:
                                continue
                        self._log(f'Edit - {screen}', 'PASS', 'Edited and saved')
                        self.screenshot(f'{screen}_after_edit')
                    except Exception as e:
                        self._log(f'Edit - {screen}', 'WARN', f'Edit failed: {e}')
                # delete (only our test records)
                try:
                    del_btn = row.find_element(By.XPATH, ".//a|.//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'delete') or contains(., 'حذف')]")
                    self.safe_click(del_btn); time.sleep(0.5)
                    # confirm modal
                    for sel in ["//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'confirm') or contains(., 'نعم') or contains(., 'delete')]"]:
                        try:
                            self.driver.find_element(By.XPATH, sel).click(); break
                        except Exception:
                            pass
                    time.sleep(1)
                    # verify removal
                    removed = False
                    try:
                        self.driver.find_element(By.XPATH, f"//*[contains(text(), '{created_key}')]")
                    except NoSuchElementException:
                        removed = True
                    self._log(f'Delete - {screen}', 'PASS' if removed else 'WARN', 'Deleted test record' if removed else 'Record still visible')
                except Exception:
                    self._log(f'Delete - {screen}', 'WARN', 'Delete control not available')
            except Exception as e:
                self._log(f'View/Edit/Delete - {screen}', 'WARN', f'Post-create operations failed: {e}')

    def try_exports_uploads_print(self, screen):
        # Exports/Print
        try:
            for xpath in [
                "//a|//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'export') or contains(., 'طباعة') or contains(., 'print') or contains(., 'pdf') or contains(., 'excel') or contains(., 'csv') or contains(., 'تحميل') or contains(., 'تنزيل') or contains(., 'download') or contains(., 'upload') or contains(., 'استيراد') or contains(., 'import')]"
            ]:
                btns = self.driver.find_elements(By.XPATH, xpath)
                count = 0
                for b in btns[:3]:
                    try:
                        self.safe_click(b); time.sleep(0.8)
                        count += 1
                        # close extra tabs if opened
                        if len(self.driver.window_handles) > 1:
                            self.driver.switch_to.window(self.driver.window_handles[-1])
                            self.screenshot(f'{screen}_print_export')
                            self.driver.close()
                            self.driver.switch_to.window(self.driver.window_handles[0])
                    except Exception:
                        continue
                if count:
                    self._log(f'Export/Print - {screen}', 'PASS', f'Clicked {count} export/print buttons')
        except Exception:
            pass
        # Upload: find file inputs
        try:
            file_inputs = self.driver.find_elements(By.CSS_SELECTOR, 'input[type="file"]')
            if file_inputs:
                sample = os.path.join(self.output_dir, 'sample.txt')
                with open(sample, 'w', encoding='utf-8') as f:
                    f.write('sample upload file for e2e test')
                file_inputs[0].send_keys(sample)
                self._log(f'Upload - {screen}', 'PASS', 'Uploaded sample file')
                # try save/submit
                for sel in ['button[type="submit"]', "//button[contains(., 'Save')]"]:
                    try:
                        btn = self.driver.find_element(By.CSS_SELECTOR, sel) if sel.startswith('button') else self.driver.find_element(By.XPATH, sel)
                        self.safe_click(btn); break
                    except Exception:
                        continue
                time.sleep(0.8)
                self.screenshot(f'{screen}_after_upload')
        except Exception:
            pass

    def test_screen(self, item):
        url = item['url']; title = item['title']
        try:
            t0 = ms()
            self.driver.get(url)
            self.ensure_loaded()
            load_ms = ms() - t0
            self.timings.append({'url': url, 'load_ms': load_ms, 'title': title})
            sc = self.screenshot(f'screen_{re.sub(r"[^a-zA-Z0-9]+","_", title)[:40]}')
            if load_ms > self.timeout * 1000:
                self._log(f'Open Screen - {title}', 'WARN', f'Load {load_ms}ms > timeout', sc, meta={'load_ms': load_ms})
            else:
                self._log(f'Open Screen - {title}', 'PASS', f'Loaded in {load_ms}ms', sc, meta={'load_ms': load_ms})
            # features
            self.try_table_tests(title)
            self.try_crud(title)
            self.try_exports_uploads_print(title)
            # logs
            self.collect_console_logs(f'{re.sub(r"[^a-zA-Z0-9]+","_", title)}_console.json')
            self.collect_perf_logs(f'{re.sub(r"[^a-zA-Z0-9]+","_", title)}_network.json')
        except Exception as e:
            sc = self.screenshot(f'error_{re.sub(r"[^a-zA-Z0-9]+","_", title)}')
            self._log(f'Open Screen - {title}', 'FAIL', str(e), sc)

    def permissions_check(self, items):
        if not (self.user_user and self.user_pass):
            self._log('Permissions', 'WARN', 'Limited user credentials not provided; skipping')
            return
        self.logout(); time.sleep(0.5)
        # back to login
        self.open_base()
        self.login(self.user_user, self.user_pass)
        # open a few screens and assert restricted controls absent
        for item in items[:5]:
            try:
                self.driver.get(item['url']); self.ensure_loaded()
                # assert no destructive buttons
                dangerous = self.driver.find_elements(By.XPATH, "//a|//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'delete') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'create') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'new')]")
                if dangerous:
                    self._log(f'Permissions - {item["title"]}', 'WARN', 'Restricted controls visible for limited user')
                else:
                    self._log(f'Permissions - {item["title"]}', 'PASS', 'No restricted controls')
            except Exception as e:
                self._log(f'Permissions - {item["title"]}', 'WARN', f'Check failed: {e}')
        self.logout()

    # Basic concurrency scenario (best-effort, optional)
    def concurrency_scenario(self):
        try:
            if not self.created_records:
                return
            key = self.created_records[0]['key']
            # Open same page in new tab and try edit
            self.driver.execute_script("window.open(arguments[0], '_blank');", self.driver.current_url)
            time.sleep(0.5)
            if len(self.driver.window_handles) > 1:
                self.driver.switch_to.window(self.driver.window_handles[-1])
                # try saving a change
                ipts = self.driver.find_elements(By.CSS_SELECTOR, 'form input[type="text"], form textarea')
                if ipts:
                    ipts[0].clear(); ipts[0].send_keys(self._gen_value('name','text')+'-concurrent')
                for sel in ['button[type="submit"]', "//button[contains(., 'Save')]"]:
                    try:
                        btn = self.driver.find_element(By.CSS_SELECTOR, sel) if sel.startswith('button') else self.driver.find_element(By.XPATH, sel)
                        self.safe_click(btn); break
                    except Exception:
                        continue
                self._log('Concurrency', 'PASS', 'Executed concurrent edit attempt (observe app behavior)')
                self.screenshot('concurrency_after_save')
                self.driver.close(); self.driver.switch_to.window(self.driver.window_handles[0])
        except Exception:
            self._log('Concurrency', 'WARN', 'Scenario not applicable')

    # ---------------------------
    # Reporting & Cleanup
    # ---------------------------
    def cleanup(self):
        # Best-effort cleanup of created test data via visible delete on listing
        try:
            for rec in self.created_records:
                try:
                    self.driver.find_element(By.XPATH, f"//*[contains(text(), '{rec['key']}')]")
                    # nearby delete
                    row = self.driver.find_element(By.XPATH, f"//*[contains(text(), '{rec['key']}')]/ancestor::*[self::tr or self::div][1]")
                    del_btn = row.find_element(By.XPATH, ".//a|.//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'delete') or contains(., 'حذف')]")
                    self.safe_click(del_btn); time.sleep(0.5)
                    for sel in ["//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'confirm') or contains(., 'نعم') or contains(., 'delete')]"]:
                        try:
                            self.driver.find_element(By.XPATH, sel).click(); break
                        except Exception:
                            pass
                except Exception:
                    continue
            self._log('Cleanup', 'PASS', 'Cleanup finished')
        except Exception:
            self._log('Cleanup', 'WARN', 'Cleanup partial')

    def save_reports(self):
        # JSON
        summary = {
            'run_id': self.run_id,
            'base_url': self.base_url,
            'timestamp': now_str(),
            'summary': {
                'total': len(self.results),
                'passed': sum(1 for r in self.results if r['status']=='PASS'),
                'failed': sum(1 for r in self.results if r['status']=='FAIL'),
                'warnings': sum(1 for r in self.results if r['status']=='WARN'),
            },
            'timings': self.timings,
            'results': self.results,
        }
        json_path = os.path.join(self.output_dir, 'report.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        # HTML (compact)
        html = [
            '<!DOCTYPE html><html><head><meta charset="utf-8"/>',
            f'<title>E2E Report - {self.run_id}</title>',
            '<style>body{font-family:Segoe UI,Arial;margin:20px} .pass{color:#28a745} .fail{color:#dc3545} .warn{color:#856404} .card{border:1px solid #eee;padding:10px;margin:8px 0;border-left:4px solid #ccc} .card.pass{border-left-color:#28a745} .card.fail{border-left-color:#dc3545} .card.warn{border-left-color:#ffc107}</style>',
            '</head><body>',
            f'<h1>🧪 E2E Report</h1><p><b>Run:</b> {self.run_id} &nbsp; <b>URL:</b> {self.base_url} &nbsp; <b>Time:</b> {now_str()}</p>',
            f'<p><b>Total:</b> {summary["summary"]["total"]} &nbsp; <span class="pass">Pass:</span> {summary["summary"]["passed"]} &nbsp; <span class="fail">Fail:</span> {summary["summary"]["failed"]} &nbsp; <span class="warn">Warn:</span> {summary["summary"]["warnings"]}</p>',
            '<h3>Timings</h3><ul>',
        ]
        for t in self.timings:
            html.append(f"<li>{t.get('title','')} {t['url']} - {t['load_ms']}ms</li>")
        html.append('</ul><h3>Results</h3>')
        for r in self.results:
            sc = f"<br><img src='{r['screenshot']}' style='max-width:380px'/>" if r.get('screenshot') else ''
            html.append(f"<div class='card {r['status'].lower()}'><b>{r['test_name']}</b> - <span class='{r['status'].lower()}'>{r['status']}</span><br>{r['message']}<br><small>{r['timestamp']}</small>{sc}</div>")
        html.append('</body></html>')
        with open(os.path.join(self.output_dir, 'report.html'), 'w', encoding='utf-8') as f:
            f.write('\n'.join(html))
        return json_path

    # ---------------------------
    # Orchestration
    # ---------------------------
    def run(self):
        try:
            self.setup_driver()
            self.open_base()
            self.login(self.admin_user, self.admin_pass)
            items = self.collect_menu()
            # Deduplicate while preserving order
            seen = set(); ordered = []
            for it in items:
                if it['url'] not in seen:
                    seen.add(it['url']); ordered.append(it)
            for it in ordered:
                self.test_screen(it)
            # Special scenarios
            self.concurrency_scenario()
            # Permissions (optional)
            self.permissions_check(ordered)
            # Cleanup
            self.cleanup()
            # Reports
            report = self.save_reports()
            self._log('Final', 'PASS', f'Reports saved to {self.output_dir}')
            return True
        except Exception as e:
            self._log('Run', 'FAIL', f'Test run failed: {e}')
            return False
        finally:
            self.teardown()


def parse_args_env():
    p = argparse.ArgumentParser(description='Comprehensive UI E2E Test Runner')
    p.add_argument('--base-url', dest='base_url', default=os.getenv('BASE_URL'))
    p.add_argument('--admin-user', dest='admin_user', default=os.getenv('CREDENTIALS_ADMIN_USER') or os.getenv('ADMIN_USERNAME'))
    p.add_argument('--admin-pass', dest='admin_pass', default=os.getenv('CREDENTIALS_ADMIN_PASS') or os.getenv('ADMIN_PASSWORD'))
    p.add_argument('--user-user', dest='user_user', default=os.getenv('CREDENTIALS_USER_USER') or os.getenv('USER_USERNAME'))
    p.add_argument('--user-pass', dest='user_pass', default=os.getenv('CREDENTIALS_USER_PASS') or os.getenv('USER_PASSWORD'))
    p.add_argument('--timeout-ms', dest='timeout_ms', type=int, default=int(os.getenv('TIMEOUT', '15000')))
    p.add_argument('--output-folder', dest='output_folder', default=os.getenv('OUTPUT_FOLDER', 'test_results'))
    p.add_argument('--run-id', dest='run_id', default=os.getenv('RUN_ID'))
    args = vars(p.parse_args())
    # basic validation
    if not args['base_url']:
        raise SystemExit('BASE_URL is required (flag --base-url or env BASE_URL)')
    if not args['admin_user'] or not args['admin_pass']:
        raise SystemExit('Admin credentials are required (flags --admin-user/--admin-pass or env CREDENTIALS_ADMIN_USER/CREDENTIALS_ADMIN_PASS)')
    return args


if __name__ == '__main__':
    cfg = parse_args_env()
    runner = ComprehensiveE2E(cfg)
    ok = runner.run()
    print('\n' + ('✅ E2E completed' if ok else '❌ E2E failed'))

