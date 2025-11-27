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
  let MENU_CACHE = {};
  let PREFETCH_IN_PROGRESS = false;
  let INVOICE_LOCKED = false;
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
  function showToast(msg){ try{ let el = document.createElement('div'); el.textContent = msg; el.style.position = 'fixed'; el.style.top = '12px'; el.style.left = '50%'; el.style.transform = 'translateX(-50%)'; el.style.background = '#000'; el.style.color = '#fff'; el.style.padding = '10px 14px'; el.style.borderRadius = '8px'; el.style.zIndex = '2000'; el.style.fontWeight = '700'; document.body.appendChild(el); setTimeout(()=>{ try{ el.remove(); }catch(_e){} }, 2500); }catch(_e){} }

  function setTotals(){
    const taxPct = number(qs('#taxPct')?.value || VAT_RATE);
    const discountPct = number(qs('#discountPct')?.value || 0);
    let subtotal = 0;
    items.forEach(it=>{ const sub=it.unit*it.qty; subtotal+=sub; });
    const discountVal = subtotal * (discountPct/100);
    const discountedSubtotal = subtotal - discountVal;
    const taxOnDiscounted = discountedSubtotal * (taxPct/100);
    const grand = discountedSubtotal + taxOnDiscounted;
    const sb = qs('#subtotal'); const tx = qs('#tax'); const dc = qs('#discount'); const gr = qs('#grand');
    if(sb){ if(window.animateNumber) window.animateNumber(sb, subtotal, 0.5); else sb.textContent = subtotal.toFixed(2); }
    if(tx){ if(window.animateNumber) window.animateNumber(tx, taxOnDiscounted, 0.5); else tx.textContent = taxOnDiscounted.toFixed(2); }
    if(dc){ if(window.animateNumber) window.animateNumber(dc, discountVal, 0.5); else dc.textContent = discountVal.toFixed(2); }
    if(gr){ if(window.animateNumber) window.animateNumber(gr, grand, 0.6); else gr.textContent = grand.toFixed(2); try{ gr.animate([{ transform:'scale(1)' }, { transform:'scale(1.05)' }, { transform:'scale(1)' }], { duration:140, easing:'ease-out' }); }catch(_e){} }
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
        if(INVOICE_LOCKED) return;
        const pwd = await (window.showPasswordPrompt ? window.showPasswordPrompt('أدخل كلمة سر المشرف / Enter supervisor password') : Promise.resolve(prompt('Enter supervisor password')));
        if(pwd===null) return; if(String(pwd).trim() !== VOID_PASSWORD){ if(window.showAlert) await window.showAlert('كلمة المرور غير صحيحة / Incorrect password'); else alert('كلمة المرور غير صحيحة / Incorrect password'); return; }
        if((it.qty||1) <= 1){
          try{
            if(window.MotionUI && typeof window.MotionUI.throwToTrash==='function'){
              window.MotionUI.throwToTrash(tr, '.trash-target', {}, ()=>{ items.splice(idx,1); renderItems(); scheduleSave({ supervisor_password: pwd }); });
              return;
            }
          }catch(_e){}
          items.splice(idx,1);
          renderItems(); scheduleSave({ supervisor_password: pwd });
        } else {
          it.qty = (it.qty||1) - 1;
          renderItems(); scheduleSave({ supervisor_password: pwd });
        }
      });
      plusBtn.addEventListener('click', async ()=>{
        if(INVOICE_LOCKED) return;
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
        if(INVOICE_LOCKED) return;
        const pwd = await window.showPasswordPrompt('أدخل كلمة سر المشرف / Enter supervisor password');
        if(pwd===null) return; if(String(pwd).trim() !== VOID_PASSWORD){ await window.showAlert('كلمة المرور غير صحيحة / Incorrect password'); return; }
        try{
          if(window.MotionUI && typeof window.MotionUI.throwToTrash==='function'){
            window.MotionUI.throwToTrash(tr, '.trash-target', {}, ()=>{ items.splice(idx,1); renderItems(); scheduleSave({ supervisor_password: pwd }); });
            return;
          }
        }catch(_e){}
        items.splice(idx,1); renderItems(); scheduleSave({ supervisor_password: pwd });
      });
      rmTd.appendChild(rmBtn); tr.appendChild(rmTd);
      body.appendChild(tr);
    });
    setTotals();
  }

  async function addMenuItem(mealId, name, unit){
    if(INVOICE_LOCKED) return;
    const existing = items.find(x=> x.meal_id === mealId);
    if(existing){ existing.qty += 1; }
    else { items.push({ meal_id: mealId, name: name, unit: number(unit), qty: 1 }); }
    renderItems(); scheduleSave();
  }

  async function openCategory(catId, catName){
    const modalEl = qs('#catModal'); const modalTitle = qs('#catModalTitle'); const grid = qs('#catGrid'); const empty = qs('#catEmpty');
    if(!modalEl || !grid) return;
    modalTitle && (modalTitle.textContent = catName || 'Items');
    grid.innerHTML = ''; if(empty){ empty.textContent = 'Loading...'; empty.classList.remove('d-none'); }
    if(window.bootstrap && bootstrap.Modal){
      if(!window.__catModalInstance){ window.__catModalInstance = new bootstrap.Modal(modalEl, { backdrop:true, keyboard:true }); }
      window.__catModalInstance.show();
    } else { modalEl.classList.add('show'); modalEl.style.display='block'; }
    let data = [];
    if(!catId){ data = []; }
    else if(MENU_CACHE[catId]){ data = MENU_CACHE[catId]; }
    else {
      try{ const resp = await fetch(`/api/menu/${catId}/items`, {credentials:'same-origin'}); data = resp.ok ? (await resp.json()) : []; MENU_CACHE[catId] = data; }catch(e){ data = []; }
    }
    grid.innerHTML = '';
    if(data.length === 0){ if(empty){ empty.textContent = 'No items in this category yet'; empty.classList.remove('d-none'); } return; } else { empty && empty.classList.add('d-none'); }
    const frag = document.createDocumentFragment();
    data.forEach(function(m){
      const col = document.createElement('div'); col.className = 'col-6 col-md-4 col-lg-3';
      const card = document.createElement('div'); card.className = 'card meal-card item-card h-100 reveal';
      const body = document.createElement('div'); body.className = 'card-body d-flex flex-column justify-content-between';
      const thumb = document.createElement('div'); thumb.className = 'thumb'; thumb.style.width='100%'; thumb.style.height='120px'; thumb.style.borderRadius='12px'; thumb.style.overflow='hidden'; thumb.style.marginBottom='8px'; thumb.style.background='linear-gradient(180deg, rgba(28,44,88,.06), rgba(28,44,88,.02))';
      const img = document.createElement('img'); img.alt = (m.name||''); img.loading='lazy'; img.style.width='100%'; img.style.height='100%'; img.style.objectFit='cover';
      const cap = document.createElement('div'); cap.className = 'cap';
      const nm = document.createElement('div'); nm.className='name'; nm.textContent = m.name || '';
      const pr = document.createElement('div'); pr.className='price'; pr.textContent = number(m.price||0).toFixed(2);
      cap.appendChild(nm); cap.appendChild(pr);
      thumb.appendChild(img); thumb.appendChild(cap); body.appendChild(thumb);
      const nmBelow = document.createElement('div'); nmBelow.className='fw-bold'; nmBelow.textContent = m.name || '';
      const prBelow = document.createElement('div'); prBelow.className='text-muted'; prBelow.textContent = 'Price: ' + number(m.price||0).toFixed(2);
      body.appendChild(nmBelow); body.appendChild(prBelow); card.appendChild(body); col.appendChild(card);
      try{
        const u = (m.image_url || '').trim() || '/static/logo.svg';
        if(u.indexOf('images.unsplash.com') !== -1){
          const widths = [400,800,1200,1600];
          const srcs = widths.map(function(w){ try{ return u.replace(/w=\d+/,'w='+w); }catch(_){ return u; } });
          img.setAttribute('data-src', srcs[srcs.length-1]);
          img.setAttribute('data-srcset', srcs.map(function(s, i){ return s + ' ' + widths[i] + 'w'; }).join(', '));
          img.sizes = '(min-width:1200px) 25vw, (min-width:768px) 33vw, 50vw';
        } else {
          img.setAttribute('data-src', u);
        }
        try{ img.decoding = 'async'; }catch(_){}
        try{ img.referrerPolicy = 'no-referrer'; }catch(_){}
        try{ img.fetchPriority = 'low'; }catch(_){}
      }catch(_e){}
      card.addEventListener('click', function(){
        try{
          const tgt = document.querySelector('#itemsList') || document.querySelector('#itemsBody') || document.body;
          if(window.MotionUI && typeof window.MotionUI.flyToTarget==='function'){ window.MotionUI.flyToTarget(card, tgt, {}, null); }
          else if(window.flyToTarget){ window.flyToTarget(card, '#itemsBody'); }
        }catch(_e){}
        addMenuItem(m.meal_id ?? m.id, m.name, number((m.price ?? m.unit ?? 0)));
        try{ if(window.animateListEnter){ window.animateListEnter('#itemsBody tr'); } }catch(_e){}
      });
      frag.appendChild(col);
    });
    grid.appendChild(frag);
    try{
      const ioImg = new IntersectionObserver(function(entries){ entries.forEach(function(entry){ if(entry.isIntersecting){ const im = entry.target; const ds = im.getAttribute('data-src'); if(ds){ im.src = ds; im.removeAttribute('data-src'); } const dss = im.getAttribute('data-srcset'); if(dss){ im.srcset = dss; im.removeAttribute('data-srcset'); } } }); }, { threshold:.01 });
      qsa('#catGrid .thumb img').forEach(function(im){ ioImg.observe(im); });
    }catch(_e){}
  }

  async function preloadMenuItems(){
    if(PREFETCH_IN_PROGRESS) return;
    PREFETCH_IN_PROGRESS = true;
    try{
      const ids = [];
      qsa('.cat-card').forEach(card=>{
        const name = card.textContent.trim();
        const idAttr = card.getAttribute('data-cat-id');
        const up = name && name.toUpperCase ? name.toUpperCase() : name;
        const id = idAttr || CAT_MAP[name] || CAT_MAP[up] || null;
        if(id) ids.push(id);
      });
      const unique = Array.from(new Set(ids));
      let i = 0;
      async function worker(){
        while(i < unique.length){
          const cid = unique[i++];
          if(MENU_CACHE[cid]) continue;
          try{
            const resp = await fetch(`/api/menu/${cid}/items`, { credentials:'same-origin' });
            const data = resp.ok ? (await resp.json()) : [];
            MENU_CACHE[cid] = data;
          }catch(_e){ MENU_CACHE[cid] = []; }
        }
      }
      const concurrency = 4;
      await Promise.all(Array(concurrency).fill(0).map(()=>worker()));
    }catch(_e){}
    PREFETCH_IN_PROGRESS = false;
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
        // Refresh tables status after creating draft
        try{ await fetch(`/api/tables/${BRANCH}`, { credentials:'same-origin' }); }catch(_e){}
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
        // Ping tables status so other clients can poll new state
        try{ await fetch(`/api/tables/${BRANCH}`, { credentials:'same-origin' }); }catch(_e){}
      }
    }catch(e){ console.error('saveDraftOrder failed', e); }
  }

  async function payAndPrint(){
    if(items.length === 0){ await window.showAlert('أضف عنصرًا واحدًا على الأقل / Add at least one item'); return; }
    const pm = (qs('#payMethod')?.value || '').toUpperCase();
    if(!(pm==='CASH' || pm==='CARD')){ await window.showAlert('يرجى اختيار طريقة الدفع (CASH أو CARD) / Please choose payment method (CASH or CARD)'); return; }
    try{ const btn = qs('#btnPayPrint'); if(btn && window.triggerCelebration){ window.triggerCelebration(btn, 26); } }catch(_e){}

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
    }catch(e){ window.DISABLE_PRINT_MODAL = prevBypass; window.KEEP_CONFIRM_BEHIND=false; window.__PRINT_WINDOW=null; await window.showAlert('خطأ في الشبكة / Network error'); }
  }

  async function voidInvoice(){
    if(items.length === 0){ await window.showAlert('الفاتورة فارغة بالفعل / Invoice is already empty'); return; }
    const pwd = await window.showPasswordPrompt('أدخل كلمة سر الإلغاء / Enter void password'); if(pwd===null) return; if(String(pwd).trim() !== VOID_PASSWORD){ await window.showAlert('كلمة المرور غير صحيحة / Incorrect password'); return; }
    try{
      const token = document.querySelector('meta[name="csrf-token"]')?.content || '';
      const headers = {'Content-Type':'application/json'}; if(token) headers['X-CSRFToken']=token;
      if(CURRENT_DRAFT_ID){
        const resp = await fetch(`/api/draft_orders/${CURRENT_DRAFT_ID}/cancel`, { method:'POST', headers, credentials:'same-origin', body: JSON.stringify({ supervisor_password: pwd }) });
        const j = await resp.json().catch(()=>({success:false})); if(!resp.ok || !j.success){ await window.showAlert(j.error||'كلمة المرور غير صحيحة / Incorrect password'); return; }
      } else {
        const resp = await fetch('/api/sales/void-check', { method:'POST', headers, credentials:'same-origin', body: JSON.stringify({ password: pwd }) });
        const j = await resp.json().catch(()=>({ok:false})); if(!resp.ok || !j.ok){ await window.showAlert('كلمة المرور غير صحيحة / Incorrect password'); return; }
      }
      items.length = 0; renderItems(); await window.showAlert('تم إلغاء الفاتورة / Invoice cancelled'); window.location.href = `/sales/${BRANCH}/tables`;
    }catch(e){ await window.showAlert('خطأ / Error'); }
  }

  async function generateInvoice(){
    if(items.length === 0){ await window.showAlert('لا يمكن إصدار فاتورة فارغة / Cannot issue empty invoice'); return; }

    // Validate customer if provided
    const custName = (qs('#custName')?.value || '').trim();
    const custPhone = (qs('#custPhone')?.value || '').trim();
    if(custName){
      if(custPhone && custPhone.replace(/\D/g,'').length < 8){ await window.showAlert('رقم هاتف العميل غير صالح / Invalid customer phone'); return; }
    }

    // Validate payment method
    const pm = (qs('#payMethod')?.value || '').trim().toUpperCase();
    if(!(pm==='CASH' || pm==='CARD')){ await window.showAlert('يرجى اختيار طريقة الدفع (CASH أو CARD) / Please choose payment method (CASH or CARD)'); return; }

    // Validate discount/tax
    const disc = number(qs('#discountPct')?.value || 0);
    const tax = number(qs('#taxPct')?.value || VAT_RATE);
    if(disc < 0 || disc > 100){ await window.showAlert('نسبة الخصم يجب أن تكون بين 0 و 100 / Discount must be between 0 and 100'); return; }
    if(tax < 0 || tax > 100){ await window.showAlert('نسبة الضريبة يجب أن تكون بين 0 و 100 / Tax must be between 0 and 100'); return; }

    try{ const btn = qs('#btnGenerateInvoice'); if(btn && window.triggerCelebration){ window.triggerCelebration(btn, 26); } }catch(_e){}
    INVOICE_LOCKED = true;
    try{ qs('#btnGenerateInvoice')?.setAttribute('disabled','disabled'); }catch(_e){}
    try{ qs('#btnVoidInvoice')?.setAttribute('disabled','disabled'); }catch(_e){}

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
            customer: { name: custName, phone: custPhone },
            discount_pct: disc,
            tax_pct: tax,
            payment_method: pm
          })
        });
        const j = await resp.json().catch(()=>({}));
        if(resp.ok && j.draft_id){ CURRENT_DRAFT_ID = j.draft_id; }
      }catch(e){ /* ignore */ }
    }

    try{
      const token = document.querySelector('meta[name="csrf-token"]')?.content || '';
      const headers = {'Content-Type':'application/json'}; if(token) headers['X-CSRFToken']=token;
      const res = await fetch('/api/sales/checkout', { 
        method:'POST', headers, credentials:'same-origin',
        body: JSON.stringify({
          draft_id: CURRENT_DRAFT_ID,
          items: items.map(x=>({ meal_id:x.meal_id, name:x.name, price:x.unit, qty:x.qty })),
          customer_name: custName,
          customer_phone: custPhone,
          discount_pct: disc,
          tax_pct: tax,
          payment_method: pm,
          branch_code: BRANCH,
          table_number: Number(TABLE_NO)
        })
      });
      if(!res.ok){ const txt = await res.text(); showToast(txt || ('HTTP '+res.status)); INVOICE_LOCKED=false; try{ qs('#btnGenerateInvoice')?.removeAttribute('disabled'); qs('#btnVoidInvoice')?.removeAttribute('disabled'); }catch(_e){} return; }
      const data = await res.json().catch(()=>null);
      if(data && data.invoice_id && data.print_url){
        items = []; renderItems(); try{ await saveDraftOrder(); }catch(_e){}
        showToast('تم ترحيل الفاتورة بنجاح / Invoice posted successfully');
        window.location.replace(data.print_url);
      } else { showToast('فشل إصدار الفاتورة / Failed to issue invoice'); INVOICE_LOCKED=false; try{ qs('#btnGenerateInvoice')?.removeAttribute('disabled'); qs('#btnVoidInvoice')?.removeAttribute('disabled'); }catch(_e){} }
    }catch(e){ showToast('خطأ في الشبكة: ' + e.message + ' / Network error'); INVOICE_LOCKED=false; try{ qs('#btnGenerateInvoice')?.removeAttribute('disabled'); qs('#btnVoidInvoice')?.removeAttribute('disabled'); }catch(_e){} }
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
    const catImagesRaw = init?.getAttribute('data-cat-images') || '{}';
    let CAT_IMAGES = {}; try{ CAT_IMAGES = JSON.parse(catImagesRaw) || {}; }catch(e){ CAT_IMAGES = {}; }

    // Bind category cards (no inline)
    qsa('.cat-card').forEach(card=>{
      card.setAttribute('tabindex','0');
      const name = card.textContent.trim();
      const idAttr = card.getAttribute('data-cat-id');
      const up = name && name.toUpperCase ? name.toUpperCase() : name;
      const id = idAttr || CAT_MAP[name] || CAT_MAP[up] || null;
      card.addEventListener('click', ()=> openCategory(id, name));
      card.addEventListener('keydown', (e)=>{ if(e.key==='Enter'||e.key===' '){ e.preventDefault(); openCategory(id, name); } });
      try{ applyTilt(card); }catch(_e){}
      try{
        const imgUrl = CAT_IMAGES[name] || CAT_IMAGES[up] || '';
        const body = card.querySelector('.card-body');
        if(body && imgUrl){
          let thumb = body.querySelector('.thumb');
          if(!thumb){ thumb = document.createElement('div'); thumb.className = 'thumb'; thumb.style.width='100%'; thumb.style.height='90px'; thumb.style.borderRadius='12px'; thumb.style.overflow='hidden'; thumb.style.background='linear-gradient(180deg, rgba(28,44,88,.06), rgba(28,44,88,.02))'; body.insertBefore(thumb, body.firstChild); }
          let img = thumb.querySelector('img');
          if(!img){ img = document.createElement('img'); img.alt = (name||''); img.loading='lazy'; img.style.width='100%'; img.style.height='100%'; img.style.objectFit='cover'; thumb.appendChild(img); }
          if(imgUrl.indexOf('images.unsplash.com') !== -1){
            const widths = [400,800,1200];
            const srcs = widths.map(function(w){
              try{ return imgUrl.replace(/w=\d+/,'w='+w); }catch(_){ return imgUrl; }
            });
            img.src = srcs[srcs.length-1];
            img.srcset = srcs.map(function(s, i){ return s + ' ' + widths[i] + 'w'; }).join(', ');
            img.sizes = '(min-width:1200px) 25vw, (min-width:768px) 33vw, 50vw';
          } else {
            img.src = imgUrl;
          }
          try{ img.decoding = 'async'; }catch(_){}
          try{ img.referrerPolicy = 'no-referrer'; }catch(_){}
          try{ img.fetchPriority = 'low'; }catch(_){}
          img.style.display = '';
        }
      }catch(_e){}
    });

    preloadMenuItems();

    // Bind primary buttons
    qs('#btnGenerateInvoice')?.addEventListener('click', generateInvoice);
    qs('#btnVoidInvoice')?.addEventListener('click', voidInvoice);

    const pressTargets = [];
    qsa('.cat-card').forEach(el=> pressTargets.push(el));
    qsa('.meal-card').forEach(el=> pressTargets.push(el));
    qsa('.btn').forEach(el=> pressTargets.push(el));
    pressTargets.forEach(function(el){
      el.addEventListener('mousedown', function(){ el.classList.add('pressed3d'); });
      el.addEventListener('mouseup', function(){ el.classList.remove('pressed3d'); });
      el.addEventListener('mouseleave', function(){ el.classList.remove('pressed3d'); });
      el.addEventListener('touchstart', function(){ el.classList.add('pressed3d'); }, { passive:true });
      el.addEventListener('touchend', function(){ el.classList.remove('pressed3d'); }, { passive:true });
    });

    try{
      const btn = qs('#btnGenerateInvoice');
      if(btn){
        btn.addEventListener('click', function(){
          try{ if(!window.triggerCelebration){ btn.animate([{ transform:'scale(1)' }, { transform:'scale(1.06)' }, { transform:'scale(1)' }], { duration:320, easing:'ease-out' }); } }catch(_e){}
        });
      }
    }catch(_e){}

    try{
      const io = new IntersectionObserver(function(entries){ entries.forEach(function(entry){ if(entry.isIntersecting){ entry.target.classList.add('reveal'); } }); }, { threshold: .15 });
      qsa('.cat-card').forEach(function(el){ io.observe(el); });
      qsa('.metrics div').forEach(function(el){ io.observe(el); });
    }catch(_e){}

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
        const p = await (window.showPrompt ? window.showPrompt('أدخل نسبة خصم خاصة % / Enter special discount %') : Promise.resolve(prompt('أدخل نسبة خصم خاصة % / Enter special discount %')));
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

  if(!window.animateNumber){
    window.animateNumber = function(el, value, seconds){
      try{
        const start = parseFloat(el.textContent||'0')||0;
        const to = Number(value||0);
        const dur = Math.max(0.1, Number(seconds||0.5));
        const t0 = performance.now();
        const fmt = function(v){ try{ return Number(v).toFixed(2); }catch(_){ return String(v); } };
        function step(ts){
          const p = Math.min(1, (ts - t0) / (dur*1000));
          const cur = start + (to - start) * (1 - Math.pow(1 - p, 3));
          el.textContent = fmt(cur);
          if(p < 1) requestAnimationFrame(step);
        }
        requestAnimationFrame(step);
      }catch(_e){ try{ el.textContent = Number(value||0).toFixed(2); }catch(_){ el.textContent = String(value||0); } }
    };
  }

  function applyTilt(el){
    if(!el) return;
    let rect = null;
    function onEnter(){ try{ rect = el.getBoundingClientRect(); }catch(_e){} }
    function onMove(e){ if(!rect) return; const cx = rect.left + rect.width/2; const cy = rect.top + rect.height/2; const x = (e.clientX||cx) - cx; const y = (e.clientY||cy) - cy; const rx = Math.max(-6, Math.min(6, (-y/rect.height)*12)); const ry = Math.max(-6, Math.min(6, (x/rect.width)*12)); el.style.transform = `perspective(700px) rotateX(${rx}deg) rotateY(${ry}deg)`; }
    function onLeave(){ el.style.transform = ''; }
    el.addEventListener('mouseenter', onEnter);
    el.addEventListener('mousemove', onMove);
    el.addEventListener('mouseleave', onLeave);
    el.addEventListener('touchstart', function(){ el.classList.add('pressed3d'); }, { passive:true });
    el.addEventListener('touchend', function(){ el.classList.remove('pressed3d'); }, { passive:true });
  }
