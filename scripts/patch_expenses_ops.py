#!/usr/bin/env python3
"""Patch expenses.html: replace Proof + Create New header/alert with ops layout."""
path = "templates/expenses.html"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Replace lines 32-126 (0-based: 31-125) with new block
new_block = """    <div class="ops-tabs-wrap">
        <div class="ops-tabs" role="tablist">
            <button type="button" class="ops-tab active" data-panel="panel-quick">{{ _('Quick Proof / إثبات مصروف سريع') }}</button>
            <button type="button" class="ops-tab" data-panel="panel-invoice">{{ _('Expense Invoice / فاتورة مصروفات') }}</button>
        </div>
    </div>
    <div class="ops-body">
        <aside class="ops-sidebar">
            <div class="ops-sidebar-card">
                <h3 class="ops-card-title">{{ _('Instructions / تعليمات') }}</h3>
                <ol>
                    <li>{{ _('Choose operation type (expense, withdrawal, deposit, payment).') }}<br><span class="text-muted small">اختر نوع العملية (مصروف، سحب، إيداع، سداد).</span></li>
                    <li>{{ _('For payments, choose sub-type to link automatically.') }}<br><span class="text-muted small">في السداد اختر النوع الفرعي لربط العملية آلياً.</span></li>
                    <li>{{ _('Ensure correct bank account for bank payments.') }}<br><span class="text-muted small">تأكد من الحساب البنكي عند الدفع البنكي.</span></li>
                    <li>{{ _('Review the accounting entry before saving.') }}<br><span class="text-muted small">راجع القيد المحاسبي قبل الحفظ.</span></li>
                </ol>
            </div>
            <div class="ops-sidebar-card ops-card-info">
                <h3 class="ops-card-title">{{ _('Accounting Info / معلومات محاسبية') }}</h3>
                <ul>
                    <li>{{ _('Expenses affect the income statement.') }}<br><span class="text-muted small">المصروفات تؤثر على قائمة الدخل.</span></li>
                    <li>{{ _('Payment closes liabilities, not a new expense.') }}<br><span class="text-muted small">السداد يغلق الالتزامات ولا يعتبر مصروفاً جديداً.</span></li>
                    <li>{{ _('Withdrawals and deposits only affect cash.') }}<br><span class="text-muted small">السحب والإيداع يؤثران فقط على النقدية.</span></li>
                </ul>
            </div>
        </aside>
        <main class="ops-main">
            <div id="panel-quick" class="ops-panel" data-panel>
                <div class="ops-form-card">
                    <div class="ops-form-head">{{ _('Operation Type / نوع العملية') }}</div>
                    <div class="ops-form-body">
                        <div class="d-flex flex-wrap gap-2 mb-3">
                            <button type="button" class="ops-tab" onclick="openScenario('salaries')">سداد رواتب</button>
                            <button type="button" class="ops-tab" onclick="openScenario('vat')">سداد VAT</button>
                            <button type="button" class="ops-tab" onclick="openScenario('purchase_no_vat')">مشتريات تشغيل</button>
                            <button type="button" class="ops-tab" onclick="openScenario('maintenance')">صيانة/خدمات</button>
                            <button type="button" class="ops-tab" onclick="openScenario('prepaid_rent')">إيجار مقدّم</button>
                            <button type="button" class="ops-tab" onclick="openScenario('cash_deposit')">إيداع نقدي</button>
                        </div>
                        <div id="scenarioForm" style="display:none">
                            <div class="row g-3">
                                <div class="col-md-3"><label class="form-label">الفرع</label><select id="scBranch" class="form-select"><option value="all" selected>الكل</option><option value="place_india">Place India</option><option value="china_town">China Town</option></select></div>
                                <div class="col-md-3"><label class="form-label">التاريخ</label><input id="scDate" type="date" class="form-control" value=""></div>
                                <div class="col-md-3"><label class="form-label">طريقة الدفع</label><select id="scPM" class="form-select"><option value="cash">نقداً</option><option value="bank">بنك</option><option value="creditor">موردين</option></select></div>
                                <div class="col-md-3"><label class="form-label">المبلغ</label><div class="input-group"><span class="input-group-text">﷼</span><input id="scAmount" type="number" step="0.01" class="form-control" placeholder="0.00"></div></div>
                                <div class="col-md-3" id="scVatBox" style="display:none"><div class="form-check mt-3"><input class="form-check-input" type="checkbox" id="scApplyVat"><label class="form-check-label" for="scApplyVat">ضريبة مدخلات 15%</label></div></div>
                                <div class="col-md-3" id="scPurchaseBox" style="display:none"><label class="form-label">نوع المشتريات</label><select id="scPurchaseType" class="form-select"></select></div>
                                <div class="col-md-3" id="scPurchaseItemBox" style="display:none"><label class="form-label">الصنف</label><select id="scPurchaseItem" class="form-select"></select></div>
                                <div class="col-md-3" id="scBankFeeBox" style="display:none"><label class="form-label">عمولة بنك</label><div class="input-group"><span class="input-group-text">﷼</span><input id="scBankFee" type="number" step="0.01" class="form-control" placeholder="0.00"></div></div>
                                <div class="col-md-6"><label class="form-label">ملاحظة</label><input id="scNote" type="text" class="form-control" placeholder="اختياري"></div>
                            </div>
                            <div class="alert alert-secondary mt-3" id="scPreview"></div>
                            <div class="d-flex gap-2"><button type="button" class="btn ops-confirm-btn" onclick="submitScenario()">{{ _('Confirm / تأكيد') }}</button><button type="button" class="btn btn-outline-secondary" onclick="closeScenario()">{{ _('Cancel / إلغاء') }}</button><button type="button" class="btn btn-outline-info btn-sm" id="scAutoBtn" style="display:none"></button></div>
                        </div>
                    </div>
                </div>
            </div>
            <div id="panel-invoice" class="ops-panel d-none" data-panel>
                <div class="alert alert-info border-0 mb-3 py-2"><i class="fas fa-info-circle me-2"></i><strong>{{ _('Tip / نصيحة') }}:</strong> {{ _('Record all business expenses (utilities, rent, supplies, etc.).') }}</div>

"""

out = lines[:31] + [new_block] + lines[126:]
with open(path, "w", encoding="utf-8") as f:
    f.writelines(out)
print("Patched lines 32-126")

# Fix closing divs: after </form> we need </div> panel-invoice, </main>, </div> ops-body
content = "".join(out)
old_close = "        </form>\n    </div>\n\n    <!-- قائمة الفواتير"
new_close = "        </form>\n            </div>\n        </main>\n    </div>\n\n    <!-- قائمة الفواتير"
if old_close in content:
    content = content.replace(old_close, new_close)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Fixed closing divs")
else:
    print("Closing block not found, skipping")

# Replace expenses-card with ops-form-card for invoices list
content = open(path, "r", encoding="utf-8").read()
content = content.replace('class="expenses-card"', 'class="ops-form-card"')
open(path, "w", encoding="utf-8").write(content)
print("Replaced expenses-card with ops-form-card")
