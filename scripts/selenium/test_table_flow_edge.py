import os, time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.microsoft import EdgeChromiumDriverManager


BASE_URL = os.environ.get('POS_BASE_URL', 'http://127.0.0.1:5000')
BRANCH = os.environ.get('POS_BRANCH', 'china_town')
TABLE = os.environ.get('POS_TABLE', '16')  # الافتراضي الآن 16 طبقاً للمشكلة
USERNAME = os.environ.get('POS_USERNAME', 'admin')
PASSWORDS = [os.environ.get('POS_PASSWORD', 'admin'), 'admin123']  # نجرب كليهما

WAIT_SECONDS = int(os.environ.get('POS_WAIT', '15'))


def login(driver):
    driver.get(BASE_URL + "/login")
    wait = WebDriverWait(driver, WAIT_SECONDS)
    wait.until(EC.presence_of_element_located((By.NAME, 'username')))

    driver.find_element(By.NAME, "username").clear()
    driver.find_element(By.NAME, "username").send_keys(USERNAME)

    # جرّب كلمتي مرور محتملتين
    for pwd in PASSWORDS:
        driver.find_element(By.NAME, "password").clear()
        driver.find_element(By.NAME, "password").send_keys(pwd)
        driver.find_element(By.NAME, "password").send_keys(Keys.RETURN)
        # انتظر إعادة توجيه ناجحة أو بقاءنا في نفس الصفحة
        time.sleep(1)
        if 'login' not in driver.current_url.lower():
            return True
    raise AssertionError("فشل تسجيل الدخول: جرّبت كلمتي مرور admin و admin123")


def open_tables(driver):
    tables_url = f"{BASE_URL}/sales/{BRANCH}/tables"
    driver.get(tables_url)
    WebDriverWait(driver, WAIT_SECONDS).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "#tables-root a.btn[data-table]"))
    )
    return tables_url


def select_table_button(driver):
    sel = f"#tables-root a.btn[data-table='{TABLE}']"
    WebDriverWait(driver, WAIT_SECONDS).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
    )
    return driver.find_element(By.CSS_SELECTOR, sel)


def add_first_item(driver):
    # صفحة POS الجديدة تستخدم pos_invoice.html (أزرار .cat-btn وشبكة #items-grid)
    try:
        WebDriverWait(driver, WAIT_SECONDS).until(
            lambda d: d.find_elements(By.CSS_SELECTOR, ".cat-btn, #items-grid")
        )
    except Exception:
        raise AssertionError(f"لم يتم فتح صفحة الفاتورة، العنوان الحالي: {driver.current_url}")

    # انقر أول زر تصنيف
    WebDriverWait(driver, WAIT_SECONDS).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, ".cat-btn"))
    ).click()
    # انتظر ظهور عناصر ضمن الشبكة ثم اختر أول عنصر
    WebDriverWait(driver, WAIT_SECONDS).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "#items-grid .item-card"))
    ).click()
    # تحقق أن السلة أصبح فيها عنصر واحد على الأقل
    WebDriverWait(driver, WAIT_SECONDS).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "#cart-list .d-flex"))
    )


def cancel_invoice(driver):
    # في القالب الحالي زر الإلغاء هو زر بخاصية onclick("cancelInvoice()") وفئته btn-outline-danger
    # اختر زر Cancel بالاسم لتجنب أزرار الحذف الخاصة بعناصر السلة
    cancel_btn = WebDriverWait(driver, WAIT_SECONDS).until(
        EC.element_to_be_clickable((By.XPATH, "//button[contains(@class,'btn-outline-danger') and contains(normalize-space(.), 'Cancel')]"))
    )
    cancel_btn.click()
    # يظهر JavaScript prompt؛ تفاعل معه عبر alert
    WebDriverWait(driver, WAIT_SECONDS).until(EC.alert_is_present())
    alert = driver.switch_to.alert
    alert.send_keys("1991")
    alert.accept()
    # بعد الإلغاء يتم التوجيه إلى شاشة الطاولات
    WebDriverWait(driver, WAIT_SECONDS).until(
        EC.url_contains("/sales/" + BRANCH + "/tables")
    )

def assert_btn_state_is(driver, expected):
    btn = select_table_button(driver)
    classes = btn.get_attribute("class") or ""
    badge = None
    try:
        badge = btn.find_element(By.CSS_SELECTOR, ".status-label").get_attribute("class") or ""
    except Exception:
        badge = ""
    if expected == 'occupied':
        assert 'btn-danger' in classes or 'bg-danger' in badge, f"Expected occupied, got classes={classes}, badge={badge}"
    else:
        assert 'btn-success' in classes or 'bg-success' in badge, f"Expected available, got classes={classes}, badge={badge}"


def wait_for_table_state(driver, expected, timeout=15):
    end = time.time() + timeout
    last = None
    while time.time() < end:
        try:
            btn = select_table_button(driver)
            classes = btn.get_attribute("class") or ""
            badge = ""
            try:
                badge = btn.find_element(By.CSS_SELECTOR, ".status-label").get_attribute("class") or ""
            except Exception:
                pass
            last = (classes, badge)
            if expected == 'occupied':
                if 'btn-danger' in classes or 'bg-danger' in badge:
                    return True
            else:
                if 'btn-success' in classes or 'bg-success' in badge:
                    return True
        except Exception:
            pass
        time.sleep(1)
        driver.refresh()
    raise AssertionError(f"Timeout waiting for table to be {expected}. Last={last}")


def pay_and_print(driver):
    # اضغط زر Pay & Print
    try:
        pay_btn = WebDriverWait(driver, WAIT_SECONDS).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(@class,'btn-success') and contains(normalize-space(.), 'Pay & Print')]"))
        )
    except Exception:
        # بديل: أي زر أخضر في الشريط
        pay_btn = WebDriverWait(driver, WAIT_SECONDS).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.btn-success"))
        )
    pay_btn.click()
    # حاول انتظار فتح نافذة الطباعة (قد تُحجب Popups)
    try:
        WebDriverWait(driver, 5).until(lambda d: len(d.window_handles) > 1)
        # أغلق نافذة الطباعة الجديدة إن فُتحت
        main_handle = driver.current_window_handle
        for h in driver.window_handles:
            if h != main_handle:
                driver.switch_to.window(h)
                driver.close()
        driver.switch_to.window(main_handle)
    except Exception:
        pass



def confirm_print_via_ui(driver):
    """
    يحاكي تدفق الواجهة: إغلاق نافذة الطباعة -> ظهور المودال -> الضغط على نعم -> انتظار التوجيه.
    """
    # انتظر المودال أن يظهر
    try:
        WebDriverWait(driver, WAIT_SECONDS).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "#printConfirmModal.show, #printConfirmModal[aria-modal='true']"))
        )
    except Exception:
        # في بعض الحالات قد يتأخر الحدث؛ امنح الصفحة فرصة بإرجاع التركيز
        try:
            driver.execute_script("window.focus && window.focus();")
        except Exception:
            pass
        WebDriverWait(driver, WAIT_SECONDS).until(
            EC.presence_of_element_located((By.ID, "printConfirmModal"))
        )
    # اضغط نعم
    ok_btn = WebDriverWait(driver, WAIT_SECONDS).until(
        EC.element_to_be_clickable((By.ID, "btnConfirmPrintOk"))
    )
    try:
        ok_btn.click()
    except Exception:
        # إذا كانت نافذة المعاينة (iframe) تعترض النقر، أخفها ثم نفّذ النقر عبر JS
        try:
            driver.execute_script("document.querySelectorAll('iframe').forEach(function(el){ el.style.display='none'; });")
        except Exception:
            pass
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'}); arguments[0].click();", ok_btn)
        except Exception:
            # محاولة أخيرة: trigger click عبر JS مباشرة
            driver.execute_script("arguments[0].dispatchEvent(new MouseEvent('click', {bubbles:true}));", ok_btn)
    # انتظر التوجيه لشاشة الطاولات
    WebDriverWait(driver, WAIT_SECONDS * 2).until(
        EC.url_contains(f"/sales/{BRANCH}/tables")
    )

def get_last_invoice_info(driver):
    # انتظر توفر window.lastInvoiceId من الصفحة بعد الدفع
    def _get_id(d):
        try:
            return d.execute_script("return window.lastInvoiceId || null;")
        except Exception:
            return None
    WebDriverWait(driver, WAIT_SECONDS).until(lambda d: _get_id(d) is not None)
    inv_id = driver.execute_script("return window.lastInvoiceId;")
    total = driver.execute_script("return window.lastTotalAmount || null;")
    # fallback للقراءة من واجهة الصفحات إن لم تتوفر القيمة
    if total is None:
        try:
            t = driver.find_element(By.ID, 't-grand').text.strip()
            total = float(t)
        except Exception:
            total = 0.0
    return int(inv_id), float(total)


def confirm_print(driver, invoice_id, total_amount, method='CASH'):
    # استدعاء API تأكيد الطباعة وتسجيل الدفع ثم تحرير الطاولة
    script = (
        "var cb=arguments[arguments.length-1];"
        "var meta=document.querySelector(\"meta[name='csrf-token']\");"
        "var tok=meta?meta.getAttribute('content'):'';"
        "fetch('/api/invoice/confirm-print', {method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':tok}, body: JSON.stringify({invoice_id: arguments[0], payment_method: arguments[1], total_amount: arguments[2]})})"
        ".then(r=>r.json()).then(j=>cb(j)).catch(e=>cb({ok:false,error:String(e)}));"
    )
    res = driver.execute_async_script(script, int(invoice_id), method, float(total_amount))
    if not (res and res.get('ok') is True):
        raise AssertionError(f"confirm-print failed: {res}")

def main():
    opts = webdriver.EdgeOptions(); opts.use_chromium = True
    drv_path = os.environ.get('POS_EDGEDRIVER')
    driver = None
    try:
        if drv_path and os.path.exists(drv_path):
            service = EdgeService(executable_path=drv_path)
        else:
            service = EdgeService(EdgeChromiumDriverManager().install())
        driver = webdriver.Edge(service=service, options=opts)
    except Exception:
        # Fallback to PATH-based driver
        driver = webdriver.Edge(options=opts)
    driver.set_window_size(1280, 900)
    try:
        print("🔐 تسجيل الدخول...")
        login(driver)

        print("📋 فتح شاشة الطاولات...")
        tables_url = open_tables(driver)

        print("🍽️ اختيار الطاولة وإضافة صنف...")
        btn = select_table_button(driver); href = btn.get_attribute("href"); driver.get(href)
        add_first_item(driver)

        print("↩️ الرجوع لشاشة الطاولات للتحقق من اللون الأحمر")
        driver.get(tables_url)
        WebDriverWait(driver, WAIT_SECONDS).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#tables-root a.btn[data-table]"))
        )
        wait_for_table_state(driver, 'occupied', timeout=15)
        print("✅ بعد الإضافة: الطاولة مشغولة (أحمر)")

        print("🧹 إلغاء الفاتورة وفتح نفس الطاولة")
        btn = select_table_button(driver); href = btn.get_attribute("href"); driver.get(href)
        cancel_invoice(driver)

        print("↩️ الرجوع لشاشة الطاولات للتحقق من اللون الأخضر")
        driver.get(tables_url)
        WebDriverWait(driver, WAIT_SECONDS).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#tables-root a.btn[data-table]"))
        )
        wait_for_table_state(driver, 'available', timeout=20)
        print("✅ بعد الإلغاء: الطاولة متاحة (أخضر)")

        print("💳 الدفع والطباعة للطاولة (مسار الواجهة)")
        btn = select_table_button(driver); href = btn.get_attribute("href"); driver.get(href)
        # أضف صنفاً إن لم يوجد
        try:
            driver.find_element(By.CSS_SELECTOR, "#cart-list .d-flex")
        except Exception:
            add_first_item(driver)
        pay_and_print(driver)

        # أكد عبر واجهة المستخدم (المودال)
        confirm_print_via_ui(driver)

        # بعد العودة لشاشة الطاولات: اطبع تشخيص الحالة والمسودة
        WebDriverWait(driver, WAIT_SECONDS).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#tables-root a.btn[data-table]"))
        )
        diag_script = (
            "var cb=arguments[arguments.length-1];"
            "Promise.all(["
            f"fetch('/api/tables/{BRANCH}/{TABLE}/status').then(r=>r.json()).catch(_=>null),"
            f"fetch('/api/draft-order/{BRANCH}/{TABLE}').then(r=>r.json()).catch(_=>null),"
            f"fetch('/api/tables/{BRANCH}').then(r=>r.json()).catch(_=>null)"
            "]).then(arr=>cb(arr)).catch(e=>cb([null,null,null]));"
        )
        diag = driver.execute_async_script(diag_script)
        try:
            print("🔎 تشخيص بعد العودة من الواجهة:", diag)
        except Exception:
            pass

        # تحقق أن الطاولة أصبحت متاحة
        wait_for_table_state(driver, 'available', timeout=25)
        print("✅ بعد الدفع (واجهة): الطاولة متاحة (أخضر)")

        # افتح صفحة فواتير المبيعات وتأكد وجود صفوف
        inv_url = f"{BASE_URL}/invoices?type=sales"
        driver.get(inv_url)
        WebDriverWait(driver, WAIT_SECONDS).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#invoice-list tr"))
        )
        # حاول العثور على فاتورة مدفوعة
        paid_exists = False
        try:
            driver.find_element(By.CSS_SELECTOR, ".status-badge.status-paid")
            paid_exists = True
        except Exception:
            paid_exists = False
        print("🧾 صفحة فواتير المبيعات فتحت - حالة مدفوعة:", "نعم" if paid_exists else "لا")

        print("🎉 اختبار Edge للطاولة + الدفع والطباعة نجح")
    finally:
        driver.quit()


if __name__ == '__main__':
    main()

