(function(){
  'use strict';

  // -------- Sales --------
  async function loadSalesReport() {
    const btn = document.getElementById('btnLoadSales');
    try {
      if(btn){ btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span> Loading...'; }
      const resp = await fetch('/api/reports/sales', {credentials:'same-origin'});
      const data = await resp.json();
      window.salesReportData = data;
      renderSalesTable(data);
    } catch (err) {
      console.error('Error loading sales report:', err);
      alert('فشل تحميل تقرير المبيعات');
    } finally {
      if(btn){ btn.disabled = false; btn.textContent = 'Show Report / عرض التقرير'; }
    }
  }

  function renderSalesTable(data) {
    let totalAll = 0, taxAll = 0, discAll = 0, countAll = 0;
    // China Town
    const chinaBody = document.getElementById('china-sales-body-live');
    if(chinaBody){
      chinaBody.innerHTML = '';
      let total = 0, tax = 0, discount = 0;
      (data.china||[]).forEach(row => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${row.date}</td>
          <td>${row.invoice}</td>
          <td>${row.item}</td>
          <td>${row.amount}</td>
          <td>${row.tax}</td>
          <td>${row.payment}</td>
          <td>${row.discount}</td>`;
        chinaBody.appendChild(tr);
        total += Number(row.amount||0);
        tax += Number(row.tax||0);
        discount += Number(row.discount||0);
      });
      const foot = chinaBody.parentElement.querySelector('tfoot tr');
      if(foot){
        foot.children[3].textContent = total.toFixed(2);
        foot.children[4].textContent = tax.toFixed(2);
        foot.children[6].textContent = discount.toFixed(2);
      }
      totalAll += total; taxAll += tax; discAll += discount; countAll += (data.china||[]).length;
    }
    // Palace India
    const indiaBody = document.getElementById('india-sales-body-live');
    if(indiaBody){
      indiaBody.innerHTML = '';
      let total = 0, tax = 0, discount = 0;
      (data.india||[]).forEach(row => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${row.date}</td>
          <td>${row.invoice}</td>
          <td>${row.item}</td>
          <td>${row.amount}</td>
          <td>${row.tax}</td>
          <td>${row.payment}</td>
          <td>${row.discount}</td>`;
        indiaBody.appendChild(tr);
        total += Number(row.amount||0);
        tax += Number(row.tax||0);
        discount += Number(row.discount||0);
      });
      const foot = indiaBody.parentElement.querySelector('tfoot tr');
      if(foot){
        foot.children[3].textContent = total.toFixed(2);
        foot.children[4].textContent = tax.toFixed(2);
        foot.children[6].textContent = discount.toFixed(2);
      }
      totalAll += total; taxAll += tax; discAll += discount; countAll += (data.india||[]).length;
    }
    // Update summary cards
    const elTotal = document.getElementById('sum-sales-total');
    const elTax = document.getElementById('sum-sales-tax');
    const elDisc = document.getElementById('sum-sales-disc');
    const elCount = document.getElementById('sum-sales-count');
    if(elTotal) elTotal.textContent = totalAll.toFixed(2);
    if(elTax) elTax.textContent = taxAll.toFixed(2);
    if(elDisc) elDisc.textContent = discAll.toFixed(2);
    if(elCount) elCount.textContent = String(countAll);
  }

  function printSalesReport(){
    if(!window.salesReportData){ alert('الرجاء تحميل التقرير أولاً'); return; }
    window.print();
  }

  function exportSalesExcel(){
    if(!window.salesReportData){ alert('الرجاء تحميل التقرير أولاً'); return; }
    const rows = [["Date","Invoice","Item","Amount","Tax","Payment","Discount"]];
    (window.salesReportData.china||[]).forEach(r=> rows.push([r.date,r.invoice,r.item,r.amount,r.tax,r.payment,r.discount]));
    (window.salesReportData.india||[]).forEach(r=> rows.push([r.date,r.invoice,r.item,r.amount,r.tax,r.payment,r.discount]));
    downloadCsv(rows, 'sales_report.csv');
  }

  // Generic export placeholder
  function exportReport(){ alert('Export feature coming soon.'); }

  // Print active tab generic
  function printReport(){
    const activeTab = document.querySelector('.nav-link.active');
    const tabId = activeTab ? activeTab.getAttribute('data-bs-target').substring(1) : '';
    if(tabId === 'sales'){ printSalesReport(); return; }
    const tabContent = document.getElementById(tabId);
    let tableHtml = '';
    if(tabContent){ tabContent.querySelectorAll('table').forEach(tbl=> tableHtml += tbl.outerHTML); }
    if(!tableHtml){ tableHtml = '<div class="alert alert-info">لا توجد بيانات لتقديم تقرير لهذا القسم</div>'; }
    const w = window.open('', '', 'height=800,width=1200');
    w.document.write('<html><head><title>تقرير</title>');
    w.document.write('<link rel="stylesheet" href="/static/bootstrap.min.css">');
    w.document.write('</head><body style="direction:rtl;">');
    w.document.write('<div style="padding:0 24px">'+tableHtml+'</div>');
    w.document.write('</body></html>');
    w.document.close(); w.focus();
    setTimeout(()=>{ w.print(); w.close(); }, 500);
  }

  // -------- Purchases --------
  function getReportFilters(){
    const form = document.querySelector('form');
    const start_date = form?.start_date?.value || '';
    const end_date = form?.end_date?.value || '';
    const branch = form?.branch?.value || 'all';
    const payment_method = form?.payment_method?.value || 'all';
    return new URLSearchParams({start_date,end_date,branch,payment_method}).toString();
  }

  async function loadPurchasesReport(){
    const btn = document.getElementById('btnLoadPurchases');
    try{
      if(btn){ btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span> Loading...'; }
      const resp = await fetch('/api/reports/purchases?'+getReportFilters(), {credentials:'same-origin'});
      const data = await resp.json();
      window.purchasesReportData = data; renderPurchasesTable(data);
    }catch(err){ console.error('Load purchases failed', err); alert('فشل تحميل تقرير المشتريات'); }
    finally{ if(btn){ btn.disabled = false; btn.textContent = 'Show Report / عرض التقرير'; } }
  }
  function renderPurchasesTable(data){
    const body = document.getElementById('purchases-body'); if(!body) return;
    body.innerHTML = ''; let totalAmount=0, totalTax=0; const rows=(data.purchases||[]);
    rows.forEach(r=>{
      const amount = Number(r.amount||r.amount_before_tax||0), tax = Number(r.tax||r.tax_amount||0);
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${r.date??''}</td>
        <td>${r.invoice??r.invoice_number??''}</td>
        <td>${r.item??r.item_name??''}</td>
        <td class="text-end">${amount.toFixed(2)}</td>
        <td class="text-end">${tax.toFixed(2)}</td>
        <td>${r.payment??r.supplier_or_payment??''}</td>`;
      body.appendChild(tr); totalAmount += amount; totalTax += tax;
    });
    const foot = body.parentElement.querySelector('tfoot tr');
    if(foot){ foot.children[3].textContent = totalAmount.toFixed(2); foot.children[4].textContent = totalTax.toFixed(2); }
    const elT = document.getElementById('sum-purch-total'); if(elT) elT.textContent = totalAmount.toFixed(2);
    const elX = document.getElementById('sum-purch-tax'); if(elX) elX.textContent = totalTax.toFixed(2);
    const elC = document.getElementById('sum-purch-count'); if(elC) elC.textContent = String(rows.length);
  }
  function exportPurchasesExcel(){
    const data = window.purchasesReportData || { purchases: [] };
    const rows = [['Date','Invoice/PO','Item','Amount Before Tax','Tax','Payment/Supplier']];
    (data.purchases||[]).forEach(r=> rows.push([r.date||'', r.invoice||'', r.item||'', r.amount||0, r.tax||0, r.payment||'']));
    downloadCsv(rows, 'purchases_report.csv');
  }

  // -------- Expenses --------
  async function loadExpensesReport(){
    const btn = document.getElementById('btnLoadExpenses');
    try{
      if(btn){ btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span> Loading...'; }
      const resp = await fetch('/api/reports/expenses?'+getReportFilters(), {credentials:'same-origin'});
      const data = await resp.json();
      window.expensesReportData = data; renderExpensesTable(data);
    }catch(err){ console.error('Load expenses failed', err); alert('فشل تحميل تقرير المصروفات'); }
    finally{ if(btn){ btn.disabled = false; btn.textContent = 'Show Report / عرض التقرير'; } }
  }
  function renderExpensesTable(data){
    const body = document.getElementById('expenses-body'); if(!body) return;
    body.innerHTML = ''; let total=0; const rows=(data.expenses||[]);
    rows.forEach(r=>{
      const amount = Number(r.amount||0);
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${r.date??''}</td>
        <td>${r.voucher??r.voucher_number??''}</td>
        <td>${r.type??r.expense_type??''}</td>
        <td class="text-end">${amount.toFixed(2)}</td>
        <td>${r.payment??r.payment_method??''}</td>`;
      body.appendChild(tr); total += amount;
    });
    const foot = body.parentElement.querySelector('tfoot tr');
    if(foot){ foot.children[3].textContent = total.toFixed(2); }
    const elT = document.getElementById('sum-exp-total'); if(elT) elT.textContent = total.toFixed(2);
    const elC = document.getElementById('sum-exp-count'); if(elC) elC.textContent = String(rows.length);
  }
  function exportExpensesExcel(){
    const data = window.expensesReportData || { expenses: [] };
    const rows = [['Date','Voucher','Type','Amount','Payment']];
    (data.expenses||[]).forEach(r=> rows.push([r.date||'', r.voucher||'', r.type||'', r.amount||0, r.payment||'']));
    downloadCsv(rows, 'expenses_report.csv');
  }

  // -------- Payroll --------
  async function loadPayrollReport(){
    try{
      const resp = await fetch('/api/reports/payroll?'+getReportFilters(), {credentials:'same-origin'});
      const data = await resp.json();
      window.payrollReportData = data; renderPayrollTable(data);
    }catch(err){ console.error('Load payroll failed', err); alert('فشل تحميل تقرير الرواتب'); }
  }
  function renderPayrollTable(data){
    const body = document.getElementById('payroll-body'); if(!body) return;
    body.innerHTML = '';
    (data.payroll||[]).forEach(r=>{
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${r.month??''}</td>
        <td>${r.basic??r.total_basic??0}</td>
        <td>${r.allowances??r.total_allowances??0}</td>
        <td>${r.deductions??r.total_deductions??0}</td>
        <td>${r.net??r.net_paid??0}</td>
        <td>${r.employees??r.employee_count??0}</td>`;
      body.appendChild(tr);
    });
  }
  function exportPayrollExcel(){
    const data = window.payrollReportData || { payroll: [] };
    const rows = [['Month','Basic Total','Allowances Total','Deductions Total','Net Paid','Employees']];
    (data.payroll||[]).forEach(r=> rows.push([r.month||'', r.basic||r.total_basic||0, r.allowances||r.total_allowances||0, r.deductions||r.total_deductions||0, r.net||r.net_paid||0, r.employees||r.employee_count||0]));
    downloadCsv(rows, 'payroll_report.csv');
  }
  // -------- All Invoices (Unified) --------
  async function loadAllInvoicesReport(){
    try{
      const resp = await fetch('/api/reports/all-invoices?'+getReportFilters(), {credentials:'same-origin'});
      const data = await resp.json();
      window.allInvoicesData = data; renderAllInvoicesTable(data);
    }catch(err){ console.error('Load all invoices failed', err); alert('فشل تحميل تقرير كل الفواتير'); }
  }
  function renderAllInvoicesTable(data){
    const body = document.getElementById('allinv-body'); if(!body) return;
    body.innerHTML = '';
    const rows = (data.invoices||[]).slice().sort((a,b)=> (a.branch||'').localeCompare(b.branch||'') || (b.date||'').localeCompare(a.date||''));
    let currentBranch = null;
    rows.forEach(r=>{
      if(r.branch !== currentBranch){
        currentBranch = r.branch;
        const hdr = document.createElement('tr');
        hdr.className = 'table-info fw-bold';
        hdr.innerHTML = `<td colspan="10">Branch: ${currentBranch??''}</td>`;
        body.appendChild(hdr);
      }
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${r.branch??''}</td>
        <td>${r.date??''}</td>
        <td>${r.invoice_number??''}</td>
        <td>${r.item_name??''}</td>
        <td>${Number(r.quantity||0)}</td>
        <td>${Number(r.price||0).toFixed(2)}</td>
        <td>${Number(r.discount||0).toFixed(2)}</td>
        <td>${Number(r.vat||0).toFixed(2)}</td>
        <td>${Number(r.total||0).toFixed(2)}</td>
        <td>${r.payment_method??''}</td>`;
      body.appendChild(tr);
    });
    const tfoot = body.parentElement.querySelector('tfoot');
    if(tfoot){
      tfoot.innerHTML = '';
      const branchTotals = data.branch_totals || {};
      Object.keys(branchTotals).sort().forEach(b=>{
        const t = branchTotals[b] || {amount:0,discount:0,vat:0,total:0};
        const tr = document.createElement('tr');
        tr.className = 'table-warning fw-bold';
        tr.innerHTML = `
          <td colspan="5" class="text-end">Branch Totals:</td>
          <td>${Number(t.amount||0).toFixed(2)}</td>
          <td>${Number(t.discount||0).toFixed(2)}</td>
          <td>${Number(t.vat||0).toFixed(2)}</td>
          <td>${Number(t.total||0).toFixed(2)}</td>
          <td></td>`;
        tfoot.appendChild(tr);
      });
      const overall = data.overall_totals || data.summary || {amount:0,discount:0,vat:0,total:0};
      const tro = document.createElement('tr');
      tro.className = 'table-secondary fw-bold';
      tro.innerHTML = `
        <td colspan="5" class="text-end">Overall Totals:</td>
        <td>${Number(overall.amount||0).toFixed(2)}</td>
        <td>${Number(overall.discount||0).toFixed(2)}</td>
        <td>${Number(overall.vat||0).toFixed(2)}</td>
        <td>${Number(overall.total||0).toFixed(2)}</td>
        <td></td>`;
      tfoot.appendChild(tro);
    }
  }
  function exportAllInvoicesExcel(){
    const data = window.allInvoicesData || { invoices: [], summary:{amount:0,discount:0,vat:0,total:0} };
    const rows = [[
      'Branch','Date','Invoice No.','Item','Qty','Amount','Discount','VAT','Total','Payment'
    ]];
    (data.invoices||[]).forEach(r=> rows.push([
      r.branch||'', r.date||'', r.invoice_number||'', r.item_name||'', Number(r.quantity||0),
      Number(r.price||0), Number(r.discount||0), Number(r.vat||0), Number(r.total||0), r.payment_method||''
    ]));
    rows.push([]);
    rows.push(['Totals','','','','', Number(data.summary.amount||0), Number(data.summary.discount||0), Number(data.summary.vat||0), Number(data.summary.total||0), '' ]);
    downloadCsv(rows, 'all_invoices.csv');
  }

  // -------- All Purchases (Unified, no branch) --------
  async function loadAllPurchasesReport(){
    try{
      const resp = await fetch('/api/reports/all-purchases?'+getReportFilters(), {credentials:'same-origin'});
      const data = await resp.json();
      window.allPurchasesData = data; renderAllPurchasesTable(data);
    }catch(err){ console.error('Load all purchases failed', err); alert('فشل تحميل تقرير المشتريات'); }
  }
  function renderAllPurchasesTable(data){
    const body = document.getElementById('allpurch-body'); if(!body) return;
    body.innerHTML = '';
    const rows = (data.purchases||[]).slice().sort((a,b)=> (b.date||'').localeCompare(a.date||''));
    rows.forEach(r=>{
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${r.date??''}</td>
        <td>${r.purchase_number??''}</td>
        <td>${r.item_name??''}</td>
        <td class="text-end">${Number(r.quantity||0)}</td>
        <td class="text-end">${Number(r.price||0).toFixed(2)}</td>
        <td class="text-end">${Number(r.discount||0).toFixed(2)}</td>
        <td class="text-end">${Number(r.vat||0).toFixed(2)}</td>
        <td class="text-end">${Number(r.total||0).toFixed(2)}</td>
        <td>${r.payment_method??''}</td>`;
      body.appendChild(tr);
    });
    const tfoot = document.getElementById('allpurch-summary');
    if(tfoot){
      tfoot.innerHTML = '';
      const t = data.overall_totals || {amount:0,discount:0,vat:0,total:0};
      const tr = document.createElement('tr'); tr.className = 'table-secondary fw-bold';


      tr.innerHTML = `
        <td colspan="4" class="text-end">Overall Totals:</td>
        <td>${Number(t.amount||0).toFixed(2)}</td>
        <td>${Number(t.discount||0).toFixed(2)}</td>
        <td>${Number(t.vat||0).toFixed(2)}</td>
        <td>${Number(t.total||0).toFixed(2)}</td>
        <td></td>`;
      tfoot.appendChild(tr);
    }
  }
  function exportAllPurchasesExcel(){
    const data = window.allPurchasesData || { purchases: [], overall_totals: {amount:0,discount:0,vat:0,total:0} };
    const rows = [[ 'Date','Purchase No.','Item','Qty','Amount','Discount','VAT','Total','Payment Method' ]];
    (data.purchases||[]).forEach(r=> rows.push([
      r.date||'', r.purchase_number||'', r.item_name||'', Number(r.quantity||0),
      Number(r.price||0), Number(r.discount||0), Number(r.vat||0), Number(r.total||0), r.payment_method||''
    ]));
    rows.push([]);
    const t = data.overall_totals || {amount:0,discount:0,vat:0,total:0};
    rows.push(['Totals','','','', Number(t.amount||0), Number(t.discount||0), Number(t.vat||0), Number(t.total||0), '' ]);
    downloadCsv(rows, 'all_purchases.csv');
  }


  function downloadCsv(rows, filename){
    const csv = rows.map(r=> r.map(x=> String(x).includes(',') ? '"'+String(x).replaceAll('"','""')+'"' : String(x)).join(',')).join('\n');
    const blob = new Blob([csv], {type:'text/csv;charset=utf-8;'});
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = filename; a.click();
  }

  // Bind UI events (no inline)
  window.addEventListener('DOMContentLoaded', function(){
    document.getElementById('btnExportGeneric')?.addEventListener('click', exportReport);

    document.getElementById('btnLoadSales')?.addEventListener('click', loadSalesReport);
    document.getElementById('btnPrintSales')?.addEventListener('click', printSalesReport);
    document.getElementById('btnExportSales')?.addEventListener('click', exportSalesExcel);

    document.getElementById('btnLoadPurchases')?.addEventListener('click', loadPurchasesReport);
    document.getElementById('btnPrintPurchases')?.addEventListener('click', printReport);
    document.getElementById('btnExportPurchases')?.addEventListener('click', exportPurchasesExcel);

    document.getElementById('btnLoadExpenses')?.addEventListener('click', loadExpensesReport);
    document.getElementById('btnPrintExpenses')?.addEventListener('click', printReport);
    document.getElementById('btnExportExpenses')?.addEventListener('click', exportExpensesExcel);

    document.getElementById('btnLoadPayroll')?.addEventListener('click', loadPayrollReport);
    document.getElementById('btnPrintPayroll')?.addEventListener('click', printReport);
    document.getElementById('btnExportPayroll')?.addEventListener('click', exportPayrollExcel);

    document.getElementById('btnLoadAllPurchases')?.addEventListener('click', loadAllPurchasesReport);
    document.getElementById('btnPrintAllPurchases')?.addEventListener('click', printReport);
    document.getElementById('btnExportAllPurchases')?.addEventListener('click', exportAllPurchasesExcel);

  });
})();


