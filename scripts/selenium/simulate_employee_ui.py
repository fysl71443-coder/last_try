import os
import sys
import time
from datetime import date
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = os.getenv("POS_BASE_URL", "http://127.0.0.1:5000")
POS_USER = os.getenv("POS_USER", "admin")
POS_PASS = os.getenv("POS_PASS", "admin123")
WAIT_SHORT = int(os.getenv("POS_WAIT_SHORT", "10"))
WAIT_LONG = int(os.getenv("POS_WAIT_LONG", "40"))

LOGS = []
def _log(msg: str):
    s = f"[SIM_UI] {msg}"
    LOGS.append(s)
    print(s)

def login(d):
    d.get(f"{BASE_URL}/login")
    WebDriverWait(d, WAIT_SHORT).until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='username'], input#username")))
    WebDriverWait(d, WAIT_SHORT).until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='password'], input#password")))
    WebDriverWait(d, WAIT_SHORT).until(EC.presence_of_element_located((By.CSS_SELECTOR, "button[type='submit'], button.btn-primary, input[type='submit']")))
    try:
        u = d.find_element(By.CSS_SELECTOR, "input[name='username'], input#username")
        u.clear(); u.send_keys(POS_USER)
    except Exception:
        u = d.find_element(By.CSS_SELECTOR, "input[name='username'], input#username")
        u.send_keys(POS_USER)
    try:
        p = d.find_element(By.CSS_SELECTOR, "input[name='password'], input#password")
        p.clear(); p.send_keys(POS_PASS)
    except Exception:
        p = d.find_element(By.CSS_SELECTOR, "input[name='password'], input#password")
        p.send_keys(POS_PASS)
    s = d.find_element(By.CSS_SELECTOR, "button[type='submit'], button.btn-primary, input[type='submit']")
    s.click()
    WebDriverWait(d, WAIT_LONG).until(EC.url_contains("/dashboard"))
    _log("LOGIN_OK")

def open_emp(d):
    d.get(f"{BASE_URL}/employee-uvd")
    WebDriverWait(d, WAIT_SHORT).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".sidebar .nav-item[data-tab]")))
    _log("UVD_OPEN")

def click_tab(d, key):
    el = WebDriverWait(d, WAIT_SHORT).until(EC.element_to_be_clickable((By.CSS_SELECTOR, f".sidebar .nav-item[data-tab='{key}']")))
    d.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    try:
        el.click()
    except Exception:
        pass
    try:
        d.execute_script("arguments[0].click();", el)
    except Exception:
        pass
    _log(f"TAB_CLICKED:{key}")
    try:
        d.execute_script(f"try{{ openPanel('{key}'); }}catch(e){{}}")
    except Exception:
        pass
    _log(f"TAB_OK:{key}")

def pick_first_option(d, sel_css):
    try:
        d.execute_script("var s=document.querySelector(arguments[0]); if(!s) return; var i=0; for(var k=0;k<s.options.length;k++){ var v=(s.options[k].value||'').trim(); if(v){ i=k; break; } } s.selectedIndex=i; s.dispatchEvent(new Event('change'));", sel_css)
        return True
    except Exception:
        return False

def wait_rows(d, tbody_css):
    def has_rows(dd):
        try:
            return len(dd.find_elements(By.CSS_SELECTOR, f"{tbody_css} tr")) > 0
        except Exception:
            return False
    WebDriverWait(d, WAIT_LONG).until(has_rows)
    _log(f"ROWS_OK:{tbody_css}")

def wait_text_not_dash(d, sel_css):
    def has_text(dd):
        try:
            t = dd.find_element(By.CSS_SELECTOR, sel_css).text.strip()
            return t and t != '—'
        except Exception:
            return False
    WebDriverWait(d, WAIT_LONG).until(has_text)
    _log(f"TEXT_OK:{sel_css}")

def flow_prev(d):
    click_tab(d, "prev")
    today = date.today().strftime("%Y-%m")
    try:
        d.execute_script("var el=document.getElementById('prevMonthInline'); if(el){ el.value=arguments[0]; el.dispatchEvent(new Event('change')); }", today)
    except Exception:
        pass
    pick_first_option(d, "#prevEmpInline")
    try:
        d.execute_script("try{ loadPrevInline(); }catch(e){}")
    except Exception:
        pass
    try:
        wait_rows(d, "#prevBodyInline")
    except Exception:
        wait_text_not_dash(d, "#prevSumTotal")

def flow_adv(d):
    click_tab(d, "adv")
    pick_first_option(d, "#advEmpFilter")
    d.find_element(By.CSS_SELECTOR, "#advReload").click()
    try:
        d.execute_script("try{ loadAdvMetrics(); loadAdvList(); }catch(e){}")
    except Exception:
        pass
    try:
        wait_rows(d, "#advBodyInline")
    except Exception:
        wait_text_not_dash(d, "#advKpiTotal")
    t = d.find_element(By.CSS_SELECTOR, "#advKpiTotal").text.strip()
    u = d.find_element(By.CSS_SELECTOR, "#advKpiUnpaid").text.strip()
    _log(f"ADV_KPI:{t}|{u}")

def flow_ledger(d):
    click_tab(d, "ledger")
    pick_first_option(d, "#ledgerEmpInline")
    d.find_element(By.CSS_SELECTOR, "#ledgerReloadInline").click()
    try:
        d.execute_script("try{ loadLedgerInline(); }catch(e){}")
    except Exception:
        pass
    try:
        wait_rows(d, "#ledgerBodyInline")
    except Exception:
        wait_text_not_dash(d, "#ledgerSumDebit")
    s = d.find_element(By.CSS_SELECTOR, "#ledgerSumDebit").text.strip()
    _log(f"LED_SUM:{s}")

def flow_reports(d):
    click_tab(d, "reports")
    try:
        d.execute_script("var el=document.getElementById('repMonthInline'); if(el){ el.value=arguments[0]; el.dispatchEvent(new Event('change')); }", date.today().strftime("%Y-%m"))
    except Exception:
        pass
    pick_first_option(d, "#repEmpInline")
    d.find_element(By.CSS_SELECTOR, "#repReloadInline").click()
    try:
        d.execute_script("try{ loadMonthlyInline(); }catch(e){}")
    except Exception:
        pass
    try:
        wait_rows(d, "#repBodyInline")
    except Exception:
        wait_text_not_dash(d, "#repKpiPayroll")
    k = d.find_element(By.CSS_SELECTOR, "#repKpiPayroll").text.strip()
    _log(f"REP_KPI:{k}")

def main():
    d = webdriver.Edge()
    d.set_page_load_timeout(WAIT_LONG)
    try:
        login(d)
        open_emp(d)
        flow_prev(d)
        flow_adv(d)
        flow_ledger(d)
        flow_reports(d)
        _log("DONE")
        return 0
    finally:
        try:
            with open("simulation_results.txt", "w", encoding="utf-8") as f:
                f.write("\n".join(LOGS))
        except Exception:
            pass
        time.sleep(2)
        try:
            d.quit()
        except Exception:
            pass

if __name__ == "__main__":
    sys.exit(main())
