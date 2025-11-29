import os, time
from urllib.parse import urljoin

BASE_URL = os.environ.get('BASE_URL', 'http://127.0.0.1:5000')
USER = os.environ.get('APP_USER', 'admin')
PASS = os.environ.get('APP_PASS', 'admin123')

def main():
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    try:
        from selenium.webdriver.edge.service import Service as EdgeService
        from webdriver_manager.microsoft import EdgeChromiumDriverManager
        opts = webdriver.EdgeOptions(); opts.use_chromium = True
        try:
            service = EdgeService(EdgeChromiumDriverManager().install())
            driver = webdriver.Edge(service=service, options=opts)
        except Exception:
            driver = webdriver.Edge(options=opts)
    except Exception:
        # Fallback to Chrome if Edge not available
        try:
            from selenium.webdriver.chrome.service import Service as ChromeService
            from webdriver_manager.chrome import ChromeDriverManager
            opts = webdriver.ChromeOptions(); opts.add_argument('--no-sandbox'); opts.add_argument('--disable-dev-shm-usage')
            service = ChromeService(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=opts)
        except Exception:
            raise RuntimeError('No Selenium WebDriver available')

    wait = WebDriverWait(driver, 25)
    driver.set_window_size(1400, 900)
    try:
        driver.get(urljoin(BASE_URL, '/login'))
        # Attempt login
        try:
            wait.until(EC.presence_of_element_located((By.NAME, 'username')))
            driver.find_element(By.NAME, 'username').clear(); driver.find_element(By.NAME, 'username').send_keys(USER)
            driver.find_element(By.NAME, 'password').clear(); driver.find_element(By.NAME, 'password').send_keys(PASS)
            # Try submit buttons
            try:
                driver.find_element(By.CSS_SELECTOR, 'button[type="submit"], .btn-primary, .btn-success').click()
            except Exception:
                driver.find_element(By.ID, 'password').submit()
            # Wait for dashboard or direct UVD
            time.sleep(1.0)
        except Exception:
            pass

        # Navigate to UVD
        driver.get(urljoin(BASE_URL, '/employee-uvd'))
        wait.until(lambda d: d.find_elements(By.CSS_SELECTOR, '.uvd-container') or d.find_elements(By.ID, 'panel-employees') or d.find_elements(By.CSS_SELECTOR, '.add-btn'))

        # Open Pay tab
        try:
            driver.find_element(By.CSS_SELECTOR, '.dept-tab[data-tab="pay"]').click()
        except Exception:
            # Try from sidebar nav
            driver.find_element(By.CSS_SELECTOR, '.nav-item[data-tab="pay"]').click()
        # Wait for table rows
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#payBody tr')))

        # Pick first row
        rows = driver.find_elements(By.CSS_SELECTOR, '#payBody tr')
        if not rows:
            raise RuntimeError('No rows available in Pay panel')
        tr = rows[0]
        # Ensure checkbox selected
        try:
            tr.find_element(By.CSS_SELECTOR, '.paySel').click()
        except Exception:
            pass
        # Click pay button
        tr.find_element(By.CSS_SELECTOR, '.rowPay').click()
        time.sleep(1.2)

        # Verify via summary API call using JS
        emp_id = tr.get_attribute('data-id')
        script = (
            "var cb=arguments[arguments.length-1];"
            "var mon=document.getElementById('payMonth')?.value || new Date().toISOString().slice(0,7);"
            "fetch('/api/employees/pay-summary?month='+encodeURIComponent(mon)+'&ids='+encodeURIComponent('"+emp_id+"'),{credentials:'same-origin'})"
            ".then(r=>r.json()).then(j=>cb(j)).catch(e=>cb({ok:false,error:String(e)}));"
        )
        j = driver.execute_async_script(script)
        ok = bool(j.get('ok'))
        rows = (j.get('rows') or [])
        print('Simulation Result:', {'ok': ok, 'rows': rows[:1]})
        if not ok:
            raise RuntimeError('Payment verification failed: '+str(j))
        if rows:
            info = rows[0]
            print('Employee', info.get('id'), 'remaining', info.get('remaining'), 'status', info.get('status'))
    finally:
        try:
            driver.quit()
        except Exception:
            pass

if __name__ == '__main__':
    main()

