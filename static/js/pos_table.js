(function(){
  'use strict';

  // --- State ---
  let BRANCH = '';
  let TABLE_NO = '';
  let VAT_RATE = 0;
  let VOID_PASSWORD = '1991'; // Default, will be loaded from settings
  let CURRENT_DRAFT_ID = null;
  let items = [];
  let CAT_MAP = {};
  let SAVE_TIMER = null;
  function scheduleSave(opts){
    if(SAVE_TIMER){ clearTimeout(SAVE_TIMER); }
    SAVE_TIMER = setTimeout(()=>{ SAVE_TIMER=null; saveDraftOrder(opts); }, 250);
  }
  function flushPendingSave(){
    if(SAVE_TIMER){ clearTimeout(SAVE_TIMER); SAVE_TIMER=null; return saveDraftOrder(); }
    return Promise.resolve();
  }

  // Ensure we persist the latest draft when the page loses visibility or unloads
  function saveDraftBeacon(){
    try{
      if(!BRANCH || !TABLE_NO) return;
      if(!items || !items.length) return;
      const payload = {
        items: items.map(x=>({ id:x.meal_id, name:x.name, price:x.unit, quantity:x.qty })),
        customer: { name: qs('#custName')?.value || '', phone: qs('#custPhone')?.value || '' },
        discount_pct: number(qs('#discountPct')?.value || 0),
        tax_pct: number(qs('#taxPct')?.value || VAT_RATE),
        payment_method: (qs('#payMethod')?.value || '')
      };
      const blob = new Blob([JSON.stringify(payload)], { type: 'application/json' });
      if(navigator && typeof navigator.sendBeacon === 'function'){
        navigator.sendBeacon(`/api/draft-order/${BRANCH}/${TABLE_NO}`, blob);
      }
    }catch(_e){ /* ignore */ }
  }

  // Load branch settings (void password, etc.)
  async function loadBranchSettings() {
    if (!BRANCH) return;
    try {
      const response = await fetch(`/api/branch-settings/${BRANCH}`);
      if (response.ok) {
        const settings = await response.json();
        VOID_PASSWORD = settings.void_password || '1991';
        console.log(`Loaded void password for ${BRANCH}: ${VOID_PASSWORD}`);
      }
    } catch (error) {
      console.error('Failed to load branch settings:', error);
    }
  }

  // Expose function to reload settings (called when settings are updated)
  window.reloadBranchSettings = loadBranchSettings;

  // --- DOM Helpers ---
  function qs(sel, ctx=document){ return ctx.querySelector(sel); }
  function qsa(sel, ctx=document){ return Array.from(ctx.querySelectorAll(sel)); }

  function number(v, def=0){ const n = parseFloat(v); return isNaN(n) ? def : n; }

  function setTotals(){
    const taxPct = number(qs('#taxPct')?.value || VAT_RATE);
    const discountPct = number(qs('#discountPct')?.value || 0);
    let subtotal = 0, tax = 0;
    items.forEach(it=>{ const sub=it.unit*it.qty; subtotal+=sub; tax += sub*(taxPct/100); });
    // Apply discount to subtotal only, then calculate tax on discounted amount
    const discountVal = subtotal * (discountPct/100);
    const discountedSubtotal = subtotal - discountVal;
    const taxOnDiscounted = discountedSubtotal * (taxPct/100);
    const grand = discountedSubtotal + taxOnDiscounted;
    if(qs('#subtotal')) qs('#subtotal').textContent = subtotal.toFixed(2);
    if(qs('#tax')) qs('#tax').textContent = taxOnDiscounted.toFixed(2);
    if(qs('#discount')) qs('#discount').textContent = discountVal.toFixed(2);
    if(qs('#grand')) qs('#grand').textContent = grand.toFixed(2);
  }

  function renderItems(){
    const body = qs('#itemsBody'); if(!body) return;
    body.innerHTML = '';
    items.forEach((it, idx)=>{
      const tr = document.createElement('tr');
      const nameTd = document.createElement('td'); nameTd.textContent = it.name; tr.appendChild(nameTd);
      const qtyTd = document.createElement('td'); qtyTd.className = 'text-center';
      const controls = document.createElement('div'); controls.className = 'd-flex align-items-center justify-content-center gap-1';
      const minusBtn = document.createElement('button'); minusBtn.type='button'; minusBtn.className='btn btn-sm btn-outline-secondary'; minusBtn.textContent='-';
      const qtyText = document.createElement('input'); qtyText.type='text'; qtyText.readOnly = true; qtyText.value = String(it.qty); qtyText.className = 'form-control form-control-sm text-center'; qtyText.style.width = '50px';
      const plusBtn = document.createElement('button'); plusBtn.type='button'; plusBtn.className='btn btn-sm btn-outline-secondary'; plusBtn.textContent='+';
      minusBtn.addEventListener('click', async ()=>{
        const pwd = await (window.showPasswordPrompt ? window.showPasswordPrompt('أدخل كلمة سر المشرف / Enter supervisor password') : Promise.resolve(prompt('Enter supervisor password')));
        if(pwd===null) return; if(String(pwd).trim() !== VOID_PASSWORD){ if(window.showAlert) await window.showAlert('Incorrect password'); else alert('Incorrect password'); return; }
        if((it.qty||1) <= 1){
          items.splice(idx,1);
        } else {
          it.qty = (it.qty||1) - 1;
        }
        renderItems(); scheduleSave({ supervisor_password: pwd });
      });
      plusBtn.addEventListener('click', async ()=>{
        it.qty = (it.qty||1) + 1; renderItems(); scheduleSave();
      });
      controls.appendChild(minusBtn); controls.appendChild(qtyText); controls.appendChild(plusBtn);
      qtyTd.appendChild(controls); tr.appendChild(qtyTd);
      const unitTd = document.createElement('td'); unitTd.className = 'text-end'; unitTd.textContent = it.unit.toFixed(2); tr.appendChild(unitTd);
      const lineTd = document.createElement('td'); lineTd.className = 'text-end';
      const lineSub = it.unit * it.qty; 
      const discountPct = number(qs('#discountPct')?.value || 0);
      const discountedLineSub = lineSub * (1 - discountPct/100);
      const tax = discountedLineSub * (number(qs('#taxPct')?.value || VAT_RATE)/100);
      lineTd.textContent = (discountedLineSub + tax).toFixed(2); tr.appendChild(lineTd);
      const rmTd = document.createElement('td');
      const rmBtn = document.createElement('button'); rmBtn.className='btn btn-sm btn-outline-danger'; rmBtn.textContent = '×';
      rmBtn.addEventListener('click', async ()=>{
        const pwd = await window.showPasswordPrompt('أدخل كلمة سر المشرف / Enter supervisor password');
        if(pwd===null) return; if(String(pwd).trim() !== VOID_PASSWORD){ await window.showAlert('Incorrect password'); return; }
        items.splice(idx,1); renderItems(); scheduleSave({ supervisor_password: pwd });
      });
      rmTd.appendChild(rmBtn); tr.appendChild(rmTd);
      body.appendChild(tr);
    });
    setTotals();
  }

  async function addMenuItem(mealId, name, unit){
    const existing = items.find(x=> x.meal_id === mealId);
    if(existing){ existing.qty += 1; }
    else { items.push({ meal_id: mealId, name: name, unit: number(unit), qty: 1 }); }
    renderItems(); scheduleSave();
  }

  async function openCategory(catId, catName){
    const modalEl = qs('#catModal'); const modalTitle = qs('#catModalTitle'); const grid = qs('#catGrid'); const empty = qs('#catEmpty');
    if(!modalEl || !grid) return;
    modalTitle && (modalTitle.textContent = catName || 'Items');
    grid.innerHTML = ''; empty && empty.classList.add('d-none');
    let data = [];
    if(!catId){
      // No mapping for this category; just show empty message
      data = [];
    } else {
      try{
        const resp = await fetch(`/api/menu/${catId}/items`, {credentials:'same-origin'});
        if(resp.ok) data = await resp.json(); else data = [];
      }catch(e){ data = []; }
    }

    if(data.length === 0){ if(empty){ empty.classList.remove('d-none'); } }
    data.forEach(m=>{
      const col = document.createElement('div'); col.className = 'col-6 col-md-4 col-lg-3';
      const card = document.createElement('div'); card.className = 'card meal-card h-100';
      const body = document.createElement('div'); body.className = 'card-body d-flex flex-column justify-content-between';
      const nm = document.createElement('div'); nm.className='fw-bold'; nm.textContent = m.name || '';
      const pr = document.createElement('div'); pr.className='text-muted'; pr.textContent = 'Price: ' + number(m.price||0).toFixed(2);
      body.appendChild(nm); body.appendChild(pr); card.appendChild(body); col.appendChild(card);
      card.addEventListener('click', ()=> addMenuItem(m.meal_id ?? m.id, m.name, number((m.price ?? m.unit ?? 0))) );
      grid.appendChild(col);
    });

    if(window.bootstrap && bootstrap.Modal){
      if(!window.__catModalInstance){ window.__catModalInstance = new bootstrap.Modal(modalEl, { backdrop:true, keyboard:true }); }
      window.__catModalInstance.show();
    } else {
      modalEl.classList.add('show'); modalEl.style.display='block';
    }
  }

  async function saveDraftOrder(opts){
    try{
      const token = document.querySelector('meta[name="csrf-token"]')?.content || '';
      const headers = {'Content-Type':'application/json'}; if(token) headers['X-CSRFToken']=token;

      // If items are empty: clear draft for this table and mark table available
      if(!items.length){
        await fetch(`/api/draft-order/${BRANCH}/${TABLE_NO}`, {
          method:'POST', headers, credentials:'same-origin', keepalive:true,
          body: JSON.stringify({ items: [] })
        });
        return;
      }

      // If no draft yet: create or update via branch/table endpoint (server will create if not exists)
      if(!CURRENT_DRAFT_ID){
        const resp = await fetch(`/api/draft-order/${BRANCH}/${TABLE_NO}`, {
          method:'POST', headers, credentials:'same-origin', keepalive:true,
          body: JSON.stringify({
            items: items.map(x=>({ id:x.meal_id, name:x.name, price:x.unit, quantity:x.qty })),
            customer: { name: qs('#custName')?.value || '', phone: qs('#custPhone')?.value || '' },
            discount_pct: number(qs('#discountPct')?.value || 0),
            tax_pct: number(qs('#taxPct')?.value || VAT_RATE),
            payment_method: (qs('#payMethod')?.value || '')
          })
        });
        const data = await resp.json().catch(()=>({}));
        if(resp.ok && data.draft_id){ CURRENT_DRAFT_ID = data.draft_id; }
      } else {
        // Update existing draft: this endpoint expects 'qty' per item
        await fetch(`/api/draft_orders/${CURRENT_DRAFT_ID}/update`, {
          method:'POST', headers, credentials:'same-origin', keepalive:true,
          body: JSON.stringify({
            items: items.map(x=>({ meal_id:x.meal_id, qty:x.qty })),
            customer_name: qs('#custName')?.value || '',
            customer_phone: qs('#custPhone')?.value || '',
            payment_method: (qs('#payMethod')?.value || ''),
            discount_pct: number(qs('#discountPct')?.value || 0),
            tax_pct: number(qs('#taxPct')?.value || VAT_RATE),
            supervisor_password: opts && opts.supervisor_password ? opts.supervisor_password : undefined
          })
        });
      }
    }catch(e){ console.error('saveDraftOrder failed', e); }
  }

  async function payAndPrint(){
    if(items.length === 0){ await window.showAlert('Add at least one item'); return; }
    const pm = (qs('#payMethod')?.value || '').toUpperCase();
    if(!(pm==='CASH' || pm==='CARD')){ await window.showAlert('يرجى اختيار طريقة الدفع (CASH أو CARD)'); return; }

    // Ensure latest items are saved as draft and we have a draft id
    await flushPendingSave();
    if(!CURRENT_DRAFT_ID){
      try{
        const token = document.querySelector('meta[name="csrf-token"]')?.content || '';
        const headers = {'Content-Type':'application/json'}; if(token) headers['X-CSRFToken']=token;
        const resp = await fetch(`/api/draft-order/${BRANCH}/${TABLE_NO}`, {
          method:'POST', headers, credentials:'same-origin',
          body: JSON.stringify({
            items: items.map(x=>({ id:x.meal_id, name:x.name, price:x.unit, quantity:x.qty })),
            customer: { name: qs('#custName')?.value || '', phone: qs('#custPhone')?.value || '' },
            discount_pct: number(qs('#discountPct')?.value || 0),
            tax_pct: number(qs('#taxPct')?.value || VAT_RATE),
            payment_method: pm
          })
        });
        const j = await resp.json().catch(()=>({}));
        if(resp.ok && j.draft_id){ CURRENT_DRAFT_ID = j.draft_id; }
      }catch(e){ /* ignore */ }
    }

    // Ask user to confirm printing after preview
    const askPrintedAndPaid = async ()=>{
      if(typeof window.showConfirm === 'function'){
        return await window.showConfirm('هل تم طباعة الفاتورة والدفع؟');
      }
      return window.confirm('هل تم طباعة الفاتورة والدفع؟');
    };
    let userDecision = null;
    let confirmPromiseStarted = false;
    let confirmPromise = null;
    function startConfirm(){
      if(confirmPromiseStarted) return;
      confirmPromiseStarted = true;
      const msg = 'هل اكتملت الطباعة؟\nDid printing complete?';
      const okText = 'Printing Completed ✅';
      const cancelText = 'Cancel ❌';
      if (typeof window.showConfirmChoice === 'function'){
        confirmPromise = window.showConfirmChoice(msg, okText, cancelText, 'تأكيد الطباعة / Print Confirmation')
          .then(function(res){ userDecision = !!res; })
          .catch(function(){ userDecision = false; });
      } else {
        confirmPromise = askPrintedAndPaid()
          .then(function(res){ userDecision = !!res; })
          .catch(function(){ userDecision = false; });
      }
    }

    // Open preview first, then finalize upon confirmation
    const prevBypass = !!window.DISABLE_PRINT_MODAL;
    window.DISABLE_PRINT_MODAL = true;
    let w = null;
    try{
      const url = `/print/order-preview/${BRANCH}/${TABLE_NO}`;
      try{ w = window.open(url, '_blank', 'width=800,height=600,scrollbars=yes'); }catch(_e){ w=null; }
      window.KEEP_CONFIRM_BEHIND = true;
      window.__PRINT_WINDOW = w || null;
      setTimeout(function(){ startConfirm(); try{ if(w) w.focus(); }catch(_e){} }, 150);
      setTimeout(function(){ window.DISABLE_PRINT_MODAL = prevBypass; }, 1500);

      if(!confirmPromiseStarted) startConfirm();
      if(confirmPromise){ try{ await confirmPromise; }catch(_e){} }
      const tablesUrl = `/sales/${BRANCH}/tables`;
      if(userDecision === true){
        // Finalize and redirect preview to final receipt
        const token = document.querySelector('meta[name="csrf-token"]')?.content || '';
        const headers = {'Content-Type':'application/json'}; if(token) headers['X-CSRFToken']=token;
        const res = await fetch('/api/draft/checkout', { method:'POST', headers, credentials:'same-origin', body: JSON.stringify({
          draft_id: CURRENT_DRAFT_ID,
          customer_name: qs('#custName')?.value || '',
          customer_phone: qs('#custPhone')?.value || '',
          discount_pct: number(qs('#discountPct')?.value || 0),
          tax_pct: number(qs('#taxPct')?.value || VAT_RATE),
          payment_method: pm
        })});
        if(!res.ok){ const txt = await res.text(); await window.showAlert(txt || ('HTTP '+res.status)); return; }
        const data = await res.json().catch(()=>null);
        try{
          const h = {'Content-Type':'application/json'}; if(token) h['X-CSRFToken']=token;
          await fetch('/api/invoice/confirm-print', { method:'POST', headers:h, credentials:'same-origin', body: JSON.stringify({
            invoice_id: data?.invoice_id, payment_method: data?.payment_method, total_amount: data?.total_amount, branch_code: BRANCH, table_number: Number(TABLE_NO)
          })});
        }catch(_e){}
        try{ if(w && !w.closed && data && data.print_url){ w.location = data.print_url; w.focus(); } }catch(_e){}
        items = []; renderItems(); window.KEEP_CONFIRM_BEHIND=false; window.__PRINT_WINDOW=null; window.location.href = tablesUrl;
      } else {
        try{ if(w && !w.closed) w.close(); }catch(_e){}
        window.KEEP_CONFIRM_BEHIND=false; window.__PRINT_WINDOW=null;
      }
    }catch(e){ window.DISABLE_PRINT_MODAL = prevBypass; window.KEEP_CONFIRM_BEHIND=false; window.__PRINT_WINDOW=null; await window.showAlert('Network error'); }
  }

  async function voidInvoice(){
    if(items.length === 0){ await window.showAlert('Invoice is already empty'); return; }
    const pwd = await window.showPasswordPrompt('أدخل كلمة سر الإلغاء / Enter void password'); if(pwd===null) return; if(String(pwd).trim() !== VOID_PASSWORD){ await window.showAlert('Incorrect password'); return; }
    try{
      const token = document.querySelector('meta[name="csrf-token"]')?.content || '';
      const headers = {'Content-Type':'application/json'}; if(token) headers['X-CSRFToken']=token;
      if(CURRENT_DRAFT_ID){
        const resp = await fetch(`/api/draft_orders/${CURRENT_DRAFT_ID}/cancel`, { method:'POST', headers, credentials:'same-origin', body: JSON.stringify({ supervisor_password: pwd }) });
        const j = await resp.json().catch(()=>({success:false})); if(!resp.ok || !j.success){ await window.showAlert(j.error||'Incorrect password'); return; }
      } else {
        const resp = await fetch('/api/sales/void-check', { method:'POST', headers, credentials:'same-origin', body: JSON.stringify({ password: pwd }) });
        const j = await resp.json().catch(()=>({ok:false})); if(!resp.ok || !j.ok){ await window.showAlert('Incorrect password'); return; }
      }
      items.length = 0; renderItems(); await window.showAlert('Invoice cancelled'); window.location.href = `/sales/${BRANCH}/tables`;
    }catch(e){ await window.showAlert('Error'); }
  }

  // Expose for other scripts if needed
  window.payAndPrint = payAndPrint;
  window.voidInvoice = voidInvoice;

  // --- Init ---
  window.addEventListener('DOMContentLoaded', function(){
    // Read init data
    const init = qs('#pos-init');
    BRANCH = init?.getAttribute('data-branch') || document.body.dataset.branch || '';
    TABLE_NO = init?.getAttribute('data-table') || document.body.dataset.table || '';
    VAT_RATE = number(init?.getAttribute('data-vat') || 0);
    
    // Load branch-specific settings
    loadBranchSettings();
    const draftRaw = init?.getAttribute('data-draft') || '[]';
    try{
      const draft = JSON.parse(draftRaw);
      (draft||[]).forEach(d=> items.push({ meal_id: d.meal_id, name: d.name, unit: number(d.price), qty: number(d.quantity||d.qty||1) }));
    }catch(e){ /* ignore */ }
    CURRENT_DRAFT_ID = (init?.getAttribute('data-draft-id') || '').trim() || null;
    const catMapRaw = init?.getAttribute('data-cat-map') || '{}';
    try{ CAT_MAP = JSON.parse(catMapRaw) || {}; }catch(e){ CAT_MAP = {}; }

    // Bind category cards (no inline)
    qsa('.cat-card').forEach(card=>{
      card.setAttribute('tabindex','0');
      const name = card.textContent.trim();
      const idAttr = card.getAttribute('data-cat-id');
      const up = name && name.toUpperCase ? name.toUpperCase() : name;
      const id = idAttr || CAT_MAP[name] || CAT_MAP[up] || null;
      card.addEventListener('click', ()=> openCategory(id, name));
      card.addEventListener('keydown', (e)=>{ if(e.key==='Enter'||e.key===' '){ e.preventDefault(); openCategory(id, name); } });
    });

    // Bind primary buttons
    qs('#btnPayPrint')?.addEventListener('click', payAndPrint);
    qs('#btnVoidInvoice')?.addEventListener('click', voidInvoice);

    // Bind auto-save for customer/payment fields
    qs('#custName')?.addEventListener('blur', ()=> scheduleSave());
    qs('#custPhone')?.addEventListener('blur', ()=> scheduleSave());
    qs('#payMethod')?.addEventListener('change', ()=> scheduleSave());
    qs('#discountPct')?.addEventListener('input', ()=> { setTotals(); scheduleSave(); });
    qs('#taxPct')?.addEventListener('input', ()=> { setTotals(); scheduleSave(); });

    // Pre-print (thermal receipt before payment)
    function prePrint(){
      if(!BRANCH || !TABLE_NO){ return; }
      const url = `/print/order-preview/${BRANCH}/${TABLE_NO}`;
      const w = window.open(url, '_blank', 'width=800,height=600,scrollbars=yes');
      if(w){ setTimeout(()=>{ try{ w.focus(); }catch(_e){} }, 200); }
    }
    const preBtn = document.querySelector('#btnPrePrint');
    if(preBtn){ preBtn.addEventListener('click', prePrint); }

    // Customer search + special discount codes
    const custInput = qs('#custName');
    const custPhone = qs('#custPhone');
    const custList = qs('#custList');
    let custFetchTimer = null;

    function hideCustList(){ if(custList){ custList.style.display='none'; custList.innerHTML=''; } }
    function showCustList(){ if(custList){ custList.style.display='block'; } }

    async function fetchCustomers(q){
      try{
        const resp = await fetch(`/api/customers/search?q=${encodeURIComponent(q)}`, { credentials:'same-origin' });
        if(!resp.ok) return [];
        const j = await resp.json().catch(()=>({results:[]}));
        return Array.isArray(j.results) ? j.results : [];
      }catch(e){ return []; }
    }

    async function handleCustInput(){
      const val = (custInput?.value || '').trim();
      const up = val.toUpperCase();
      if(up === 'KEETA' || up === 'HUNGER'){
        const p = await (window.showPrompt ? window.showPrompt('أدخل نسبة خصم خاصة %') : Promise.resolve(prompt('أدخل نسبة خصم خاصة %')));
        if(p!==null){ const n = number(p, 0); const dp = qs('#discountPct'); if(dp){ dp.value = String(n); } setTotals(); saveDraftOrder(); }
      }
      clearTimeout(custFetchTimer);
      if(!val){ hideCustList(); return; }
      custFetchTimer = setTimeout(async ()=>{
        const results = await fetchCustomers(val);
        if(!custList) return;
        custList.innerHTML = '';
        results.forEach(r=>{
          const a = document.createElement('a'); a.href='#'; a.className='list-group-item list-group-item-action';
          a.textContent = `${r.name}${r.phone ? ' ('+r.phone+')' : ''} — خصم ${number(r.discount_percent||0).toFixed(2)}%`;
          a.addEventListener('click', (e)=>{
            e.preventDefault();
            if(custInput) custInput.value = r.name || '';
            if(custPhone) custPhone.value = r.phone || '';
            const dp = qs('#discountPct'); if(dp){ dp.value = String(number(r.discount_percent||0)); }
            hideCustList(); setTotals(); saveDraftOrder();
          });
          custList.appendChild(a);
        });
        if(results.length){ showCustList(); } else { hideCustList(); }
      }, 250);
    }
    custInput?.addEventListener('input', handleCustInput);
    document.addEventListener('click', (e)=>{ if(!custList) return; if(!custList.contains(e.target) && e.target !== custInput){ hideCustList(); } });

    // Initial render
    renderItems();

    // Persist drafts when the tab loses visibility or the page is unloading
    document.addEventListener('visibilitychange', function(){ if(document.visibilityState === 'hidden'){ try{ flushPendingSave(); saveDraftBeacon(); }catch(_e){} } });
    window.addEventListener('pagehide', function(){ try{ saveDraftBeacon(); }catch(_e){} });
    window.addEventListener('beforeunload', function(){ try{ saveDraftBeacon(); }catch(_e){} });
  });
})();

