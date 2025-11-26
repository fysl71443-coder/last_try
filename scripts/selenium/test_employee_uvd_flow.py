import os, time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.microsoft import EdgeChromiumDriverManager

BASE_URL = os.environ.get('APP_BASE_URL', 'http://127.0.0.1:5000')
USERNAME = os.environ.get('APP_USER', 'admin')
PASSWORDS = [os.environ.get('APP_PASS', 'admin'), 'admin123']
OUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'screenshots', 'employee_uvd'))
REPORT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'reports', 'employee_uvd_test_report.md'))

os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(os.path.dirname(REPORT), exist_ok=True)

def screenshot(driver, name):
    path = os.path.join(OUT_DIR, f"{name}.png")
    driver.save_screenshot(path)
    return path

def get_console_logs(driver):
    logs = []
    try:
        logs = driver.get_log('browser')
    except Exception:
        pass
    return logs

def write_report(results):
    with open(REPORT, 'w', encoding='utf-8') as f:
        f.write("# تقرير فحص شاشة الموظفين الجديدة\n\n")
        f.write(f"تاريخ الفحص: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        def sec(title):
            f.write(f"## {title}\n")
        sec("الأزرار التي تعمل")
        for k,v in results.items():
            if isinstance(v, dict) and v.get('status')=='PASS':
                f.write(f"- {k}: ✅ تعمل — {v.get('note','')}\n")
        f.write("\n")
        sec("الأزرار التي بها مشاكل")
        for k,v in results.items():
            if isinstance(v, dict) and v.get('status')=='FAIL':
                f.write(f"- {k}: ❌ مشكلة — {v.get('note','')}\n")
        f.write("\n")
        sec("الأخطاء في الكونسول")
        logs = results.get('console_logs', [])
        if not logs:
            f.write("- لا توجد أخطاء ظاهرة\n")
        else:
            for l in logs:
                f.write(f"- {l.get('message','')}\n")
        f.write("\n")
        sec("لقطات شاشة")
        for k,v in results.items():
            if isinstance(v, dict):
                img = v.get('screenshot')
                if img and os.path.exists(img):
                    f.write(f"- {k}: ![]({img})\n")

def main():
    results = {}
    opts = webdriver.EdgeOptions(); opts.use_chromium = True
    drv_path = os.environ.get('APP_EDGEDRIVER')
    try:
        if drv_path and os.path.exists(drv_path):
            service = EdgeService(executable_path=drv_path)
        else:
            service = EdgeService(EdgeChromiumDriverManager().install())
        driver = webdriver.Edge(service=service, options=opts)
    except Exception:
        driver = webdriver.Edge(options=opts)
    wait = WebDriverWait(driver, 25)
    try:
        driver.set_window_size(1400, 900)
        driver.get(BASE_URL + '/login')
        # login
        try:
            user = wait.until(EC.presence_of_element_located((By.NAME, 'username')))
            pwd = driver.find_element(By.NAME, 'password')
            user.clear(); user.send_keys(USERNAME)
            ok = False
            for p in PASSWORDS:
                try:
                    pwd.clear(); pwd.send_keys(p)
                    driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
                    time.sleep(1.2)
                    if '/dashboard' in driver.current_url or '/employee-uvd' in driver.current_url:
                        ok = True; break
                except Exception:
                    continue
            results['Login'] = {'status': 'PASS' if ok else 'FAIL', 'note': driver.current_url}
        except Exception as e:
            results['Login'] = {'status':'FAIL','note':str(e)}

        driver.get(BASE_URL + '/employee-uvd')
        if '/login' in driver.current_url:
            driver.get(BASE_URL + '/login')
            try:
                u = wait.until(EC.presence_of_element_located((By.NAME, 'username')))
                p = driver.find_element(By.NAME, 'password')
                u.clear(); u.send_keys(USERNAME)
                ok2 = False
                for _pw in PASSWORDS:
                    try:
                        p.clear(); p.send_keys(_pw)
                        driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
                        time.sleep(1.0)
                        if '/dashboard' in driver.current_url:
                            ok2 = True; break
                    except Exception:
                        continue
            except Exception:
                pass
        driver.get(BASE_URL + '/employee-uvd')
        wait.until(lambda d: d.find_elements(By.CSS_SELECTOR, '.uvd-container') or d.find_elements(By.ID, 'btnAddEmp') or d.find_elements(By.CSS_SELECTOR, '.add-btn') or d.find_elements(By.CSS_SELECTOR, '#panel-employees'))
        results['Open UVD'] = {'status':'PASS','screenshot': screenshot(driver, 'open_uvd')}

        try:
            try:
                driver.find_element(By.ID, 'btnAddEmp').click()
            except Exception:
                try:
                    driver.find_element(By.CSS_SELECTOR, '.add-btn').click()
                except Exception:
                    driver.find_element(By.XPATH, "//a[contains(@href,'/employees/create')]").click()
            wait.until(EC.presence_of_element_located((By.ID, 'addEmpForm')))
            driver.find_element(By.NAME, 'full_name').send_keys('موظف اختبار Selenium')
            driver.find_element(By.NAME, 'national_id').send_keys(str(int(time.time())))
            driver.find_element(By.NAME, 'department').send_keys('kitchen')
            driver.find_element(By.NAME, 'position').send_keys('شيف')
            driver.find_element(By.NAME, 'phone').send_keys('0551234567')
            driver.find_element(By.NAME, 'email').send_keys('selenium@example.com')
            driver.find_element(By.NAME, 'base_salary').clear()
            driver.find_element(By.NAME, 'base_salary').send_keys('3200')
            driver.find_element(By.CSS_SELECTOR, '#addEmpForm button[type="submit"]').click()
            time.sleep(1.2)
            results['Add Employee'] = {'status':'PASS','screenshot': screenshot(driver, 'add_employee')}
        except Exception as e:
            results['Add Employee'] = {'status':'FAIL','note':str(e), 'screenshot': screenshot(driver, 'add_employee_fail')}

        try:
            gs = driver.find_element(By.ID, 'globalSearch')
            gs.clear(); gs.send_keys('موظف')
            time.sleep(0.6)
            sb = driver.find_element(By.ID, 'suggestBox')
            ok = sb.is_displayed() or ('display: none' not in (sb.get_attribute('style') or ''))
            results['Global Search'] = {'status':'PASS' if ok else 'FAIL','screenshot': screenshot(driver, 'global_search')}
        except Exception as e:
            results['Global Search'] = {'status':'FAIL','note':str(e)}

        try:
            driver.get(BASE_URL + '/reports/monthly')
            wait.until(EC.presence_of_element_located((By.ID, 'btnNewRep')))
            results['Reports Monthly'] = {'status':'PASS','screenshot': screenshot(driver, 'reports_monthly')}
            driver.get(BASE_URL + '/employee-uvd')
            wait.until(lambda d: d.find_elements(By.ID, 'btnAddEmp') or d.find_elements(By.CSS_SELECTOR, '.add-btn'))
        except Exception as e:
            results['Reports Monthly'] = {'status':'FAIL','note':str(e)}
            try:
                driver.get(BASE_URL + '/employee-uvd')
            except Exception:
                pass

        # Filter by department
        try:
            driver.find_element(By.CSS_SELECTOR, '.dept-tab[data-dept="kitchen"]').click()
            time.sleep(0.6)
            results['Filter Dept'] = {'status':'PASS','screenshot': screenshot(driver, 'filter_kitchen')}
        except Exception as e:
            results['Filter Dept'] = {'status':'FAIL','note':str(e)}

        # Open ops menu and Edit
        try:
            btns = driver.find_elements(By.CSS_SELECTOR, '.ops-btn')
            btns[0].click()
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.ops-menu .it[data-op="edit"]')))
            driver.find_element(By.CSS_SELECTOR, '.ops-menu .it[data-op="edit"]').click()
            wait.until(EC.presence_of_element_located((By.ID, 'editEmpForm')))
            nm = driver.find_element(By.NAME, 'full_name')
            nm.clear(); nm.send_keys('موظف معدل')
            driver.find_element(By.CSS_SELECTOR, '#editEmpForm button[type="submit"]').click()
            time.sleep(1.0)
            results['Edit Employee'] = {'status':'PASS','screenshot': screenshot(driver, 'edit_employee')}
        except Exception as e:
            results['Edit Employee'] = {'status':'FAIL','note':str(e)}

        # Grant advance + verify journal & lists
        try:
            btns = driver.find_elements(By.CSS_SELECTOR, '.ops-btn')
            target_btn = btns[0]
            try:
                driver.execute_script("arguments[0].scrollIntoView({behavior:'smooth',block:'center'});", target_btn)
            except Exception:
                pass
            try:
                driver.execute_script("arguments[0].click();", target_btn)
            except Exception:
                target_btn.click()
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.ops-menu .it[data-op="advance"]')))
            # Read employee id from row
            try:
                tr = target_btn.find_element(By.XPATH, './ancestor::tr')
                emp_id = tr.get_attribute('data-id') or ''
            except Exception:
                emp_id = ''
            adv_item = driver.find_element(By.CSS_SELECTOR, '.ops-menu .it[data-op="advance"]')
            try:
                driver.execute_script("arguments[0].click();", adv_item)
            except Exception:
                adv_item.click()
            wait.until(EC.presence_of_element_located((By.ID, 'advForm')))
            driver.find_element(By.NAME, 'amount').send_keys('250')
            # optional: method select remains default 'cash'
            driver.find_element(By.CSS_SELECTOR, '#advForm button[type="submit"]').click()
            time.sleep(1.2)
            results['Grant Advance'] = {'status':'PASS','screenshot': screenshot(driver, 'grant_advance')}

            # Verify via API: employee ledger shows recent advance
            try:
                script = (
                    "var cb=arguments[arguments.length-1];"
                    "fetch('/api/employee-ledger?emp_id="+str(emp_id)+"',{credentials:'same-origin'})"
                    ".then(r=>r.json()).then(j=>cb(j)).catch(e=>cb({ok:false,error:String(e)}));"
                )
                j = driver.execute_async_script(script)
                ok = bool(j.get('ok')) and len(j.get('rows') or [])>0
                if ok:
                    rows = j['rows'] or []
                    cond_any = False
                    pick = None
                    for it in rows:
                        desc = str(it.get('desc',''))
                        if (('advance' in desc.lower()) or ('سلفة' in desc)) and (float(it.get('debit',0))>0):
                            cond_any = True; pick = it; break
                    results['Verify Journal API'] = {'status':'PASS' if cond_any else 'FAIL', 'note': str(pick or rows[-1])}
                else:
                    results['Verify Journal API'] = {'status':'FAIL','note': str(j)}
            except Exception as e:
                results['Verify Journal API'] = {'status':'FAIL','note':str(e)}

            # Reload UVD and check advances panel contains entry for employee
            try:
                driver.get(BASE_URL + '/employee-uvd')
                wait.until(lambda d: d.find_elements(By.CSS_SELECTOR, '#panel-adv tbody tr[data-row="adv"]'))
                rows = driver.find_elements(By.CSS_SELECTOR, f"#panel-adv tbody tr[data-row='adv'][data-emp='{emp_id}']") if emp_id else driver.find_elements(By.CSS_SELECTOR, "#panel-adv tbody tr[data-row='adv']")
                results['Advances Panel'] = {'status':'PASS' if len(rows)>0 else 'FAIL', 'screenshot': screenshot(driver, 'panel_adv')}
            except Exception as e:
                results['Advances Panel'] = {'status':'FAIL','note':str(e)}

            # Verify ledger list API also returns entries for employee
            try:
                if emp_id:
                    script2 = (
                        "var cb=arguments[arguments.length-1];"
                        "fetch('/api/ledger/list?type=advance&emp_id="+str(emp_id)+"',{credentials:'same-origin'})"
                        ".then(r=>r.json()).then(j=>cb(j)).catch(e=>cb({ok:false,error:String(e)}));"
                    )
                    jl = driver.execute_async_script(script2)
                    ok2 = bool(jl.get('ok')) and len(jl.get('rows') or [])>0
                    results['Ledger List API'] = {'status':'PASS' if ok2 else 'FAIL', 'note': f"rows={len(jl.get('rows') or [])}"}
                else:
                    results['Ledger List API'] = {'status':'FAIL','note':'no employee id'}
            except Exception as e:
                results['Ledger List API'] = {'status':'FAIL','note':str(e)}
        except Exception as e:
            results['Grant Advance'] = {'status':'FAIL','note':str(e)}

        # Pay salary (opens iframe)
        try:
            btns = driver.find_elements(By.CSS_SELECTOR, '.ops-btn')
            btns[0].click()
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.ops-menu .it[data-op="pay"]')))
            driver.find_element(By.CSS_SELECTOR, '.ops-menu .it[data-op="pay"]').click()
            time.sleep(1.0)
            iframe = driver.find_element(By.ID, 'panelIframe')
            src = iframe.get_attribute('src')
            results['Pay Salary'] = {'status':'PASS' if '/employees/' in src and '/pay' in src else 'FAIL', 'note': src, 'screenshot': screenshot(driver, 'pay_salary')}
        except Exception as e:
            results['Pay Salary'] = {'status':'FAIL','note':str(e)}

        # Preview journal
        try:
            btns = driver.find_elements(By.CSS_SELECTOR, '.ops-btn')
            btns[0].click()
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.ops-menu .it[data-op="journal"]')))
            driver.find_element(By.CSS_SELECTOR, '.ops-menu .it[data-op="journal"]').click()
            time.sleep(0.8)
            results['Preview Journal'] = {'status':'PASS','screenshot': screenshot(driver, 'preview_journal')}
        except Exception as e:
            results['Preview Journal'] = {'status':'FAIL','note':str(e)}

        # Delete employee (test on last row to reduce impact)
        try:
            btns = driver.find_elements(By.CSS_SELECTOR, '.ops-btn')
            btns[-1].click()
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.ops-menu .it[data-op="delete"]')))
            driver.find_element(By.CSS_SELECTOR, '.ops-menu .it[data-op="delete"]').click()
            alert = driver.switch_to.alert
            alert.accept()
            time.sleep(1.0)
            results['Delete Employee'] = {'status':'PASS','screenshot': screenshot(driver, 'delete_employee')}
        except Exception as e:
            results['Delete Employee'] = {'status':'FAIL','note':str(e)}

        # Collect console logs
        results['console_logs'] = get_console_logs(driver)

    finally:
        try:
            driver.quit()
        except Exception:
            pass
        write_report(results)

if __name__ == '__main__':
    main()
