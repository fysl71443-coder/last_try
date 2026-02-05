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
  let MENU_CACHE = {};       // category_id -> [items]; filled once from all-items or preload
  let ALL_ITEMS_LOADED = false;
  const POS_CACHE_KEY = 'pos_menu_items';
  const POS_CACHE_TTL_MS = 5 * 60 * 1000;  // 5 min
  let PREFETCH_IN_PROGRESS = false;
  let INVOICE_LOCKED = false;
  let SAVE_TIMER = null;
  let SCREEN_READY = false;
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
        discount_pct: effectiveDiscountPct(),
        tax_pct: number(qs('#taxPct')?.value || VAT_RATE),
        payment_method: (qs('#payMethod')?.value || '')
      };
      const token = document.querySelector('meta[name="csrf-token"]')?.content || '';
      const headers = {'Content-Type':'application/json'}; if(token) headers['X-CSRFToken']=token;
      const body = JSON.stringify(payload);
      if(typeof fetch === 'function'){
        fetch(`/api/draft-order/${BRANCH}/${TABLE_NO}`, { method:'POST', headers, body, credentials:'same-origin', keepalive:true });
      } else if(navigator && typeof navigator.sendBeacon === 'function'){
        const blob = new Blob([body], { type: 'application/json' });
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

  /** Load draft from API and apply to state + form. Call on screen entry, independent of customer. */
  async function loadDraftFromAPI(){
    if(!BRANCH || !TABLE_NO) return;
    const resp = await fetch(`/api/draft/${BRANCH}/${TABLE_NO}`, { credentials:'same-origin' });
    if(!resp.ok) return;
    const j = await resp.json().catch(()=>({}));
    const rec = (j.draft !== undefined && j.draft !== null) ? j.draft : (j.items ? { items: j.items, draft_id: j.draft_id, customer: j.customer || {}, discount_pct: j.discount_pct, tax_pct: j.tax_pct, payment_method: j.payment_method || '' } : {});
    const draftItems = rec.items || [];
    if(Array.isArray(draftItems) && draftItems.length > 0){
      items.length = 0;
      draftItems.forEach(function(d){
        items.push({
          meal_id: d.meal_id || d.id,
          name: d.name || '',
          unit: number(d.price || d.unit),
          qty: number(d.quantity || d.qty || 1)
        });
      });
    }
    if(rec.draft_id){ CURRENT_DRAFT_ID = String(rec.draft_id).trim() || null; }
    const customer = rec.customer || {};
    const name = (customer.name||'').trim();
    const phone = (customer.phone||'').trim();
    const disc = rec.discount_pct;
    const tax = rec.tax_pct;
    const pay = (rec.payment_method||'').toString().trim().toUpperCase();
    const custNameEl = qs('#custName'); if(custNameEl) custNameEl.value = name || custNameEl.value || '';
    const custPhoneEl = qs('#custPhone'); if(custPhoneEl) custPhoneEl.value = phone || custPhoneEl.value || '';
    // Restore draft values in full; do not overwrite saved discount
    if(typeof disc !== 'undefined' && disc !== null){ const el = qs('#discountPct'); if(el) el.value = String(number(disc)); }
    if(typeof tax !== 'undefined' && tax !== null){ const el = qs('#taxPct'); if(el) el.value = String(number(tax)); }
    if(pay){ const el = qs('#payMethod'); if(el) el.value = pay; }
    const custIdEl = qs('#custId');
    var hasRegisteredCustomer = custIdEl && (custIdEl.value||'').trim().length > 0;
    // Only force 0% and readonly when no registered customer AND draft did not provide a discount (preserve saved discount)
    if(!hasRegisteredCustomer && (typeof disc === 'undefined' || disc === null)){
      const dp = qs('#discountPct'); if(dp){ dp.value = '0'; dp.setAttribute('readonly',''); dp.classList.add('bg-light'); dp.title = 'لا خصم — عميل غير مسجل'; }
    }
    setTotals();
  }

  // --- DOM Helpers ---
  function qs(sel, ctx=document){ return ctx.querySelector(sel); }
  function qsa(sel, ctx=document){ return Array.from(ctx.querySelectorAll(sel)); }

  function number(v, def=0){ const n = parseFloat(v); return isNaN(n) ? def : n; }
  /** Effective discount: value from field (so saved draft discount is preserved and used for save/totals). */
  function effectiveDiscountPct(){
    return number(qs('#discountPct')?.value || 0, 0);
  }
  function showToast(msg){ try{ let el = document.createElement('div'); el.textContent = msg; el.style.position = 'fixed'; el.style.top = '12px'; el.style.left = '50%'; el.style.transform = 'translateX(-50%)'; el.style.background = '#000'; el.style.color = '#fff'; el.style.padding = '10px 14px'; el.style.borderRadius = '8px'; el.style.zIndex = '2000'; el.style.fontWeight = '700'; document.body.appendChild(el); setTimeout(()=>{ try{ el.remove(); }catch(_e){} }, 2500); }catch(_e){} }

  /** Recompute totals from in-memory items only (no API). Single pass: subtotal += item.unit*item.qty. */
  function setTotals(){
    const taxPct = number(qs('#taxPct')?.value || VAT_RATE);
    const discountPct = number(qs('#discountPct')?.value || 0);
    let subtotal = 0;
    items.forEach(it=>{ subtotal += it.unit * it.qty; });
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

  /** Show items for category: from memory (MENU_CACHE). If not loaded yet, ensure load runs once then show. */
  async function openCategory(catId, catName){
    if(!SCREEN_READY){ showToast('جاري التحميل... / Loading...'); return; }
    const modalEl = qs('#catModal'); const modalTitle = qs('#catModalTitle'); const grid = qs('#catGrid'); const empty = qs('#catEmpty');
    if(!modalEl || !grid) return;
    modalTitle && (modalTitle.textContent = catName || 'Items');
    grid.innerHTML = ''; if(empty){ empty.textContent = ''; empty.classList.remove('d-none'); }
    if(window.bootstrap && bootstrap.Modal){
      if(!window.__catModalInstance){ window.__catModalInstance = new bootstrap.Modal(modalEl, { backdrop:true, keyboard:true }); }
      window.__catModalInstance.show();
    } else { modalEl.classList.add('show'); modalEl.style.display='block'; }
    let data = [];
    if(!catId){ data = []; }
    else if(MENU_CACHE[catId]){ data = MENU_CACHE[catId]; }
    else {
      try{ await loadAllMenuItemsOnce(); data = MENU_CACHE[catId] || []; }catch(_e){ data = []; }
    }
    grid.innerHTML = '';
    if(data.length === 0){ if(empty){ empty.textContent = 'No items in this category yet'; empty.classList.remove('d-none'); } return; } else { empty && empty.classList.add('d-none'); }
    const frag = document.createDocumentFragment();
    data.forEach(function(m){
      const col = document.createElement('div'); col.className = 'col-6 col-md-4 col-lg-3';
      const card = document.createElement('div'); card.className = 'card meal-card item-card h-100 reveal';
      const body = document.createElement('div'); body.className = 'card-body d-flex flex-column justify-content-between';
      // Small circular avatar next to name
      const header = document.createElement('div'); header.className = 'd-flex align-items-center justify-content-between';
      const left = document.createElement('div'); left.className = 'd-flex align-items-center gap-2';
      const avatar = document.createElement('img'); avatar.alt = (m.name||''); avatar.loading='lazy'; avatar.style.width='28px'; avatar.style.height='28px'; avatar.style.borderRadius='50%'; avatar.style.objectFit='cover'; avatar.style.flex='0 0 28px';
      const nameEl = document.createElement('div'); nameEl.className='fw-bold'; nameEl.textContent = m.name || '';
      left.appendChild(avatar); left.appendChild(nameEl);
      const priceEl = document.createElement('div'); priceEl.className='text-muted small'; priceEl.textContent = number(m.price||0).toFixed(2);
      header.appendChild(left); header.appendChild(priceEl);
      body.appendChild(header);
      card.appendChild(body); col.appendChild(card);
      try{
        const u = (m.image_url || '').trim() || '/static/logo.svg';
        if(u.indexOf('images.unsplash.com') !== -1){
          const widths = [400,800,1200,1600];
          const srcs = widths.map(function(w){ try{ return u.replace(/w=\d+/,'w='+w); }catch(_){ return u; } });
          avatar.setAttribute('data-src', srcs[srcs.length-1]);
          avatar.setAttribute('data-srcset', srcs.map(function(s, i){ return s + ' ' + widths[i] + 'w'; }).join(', '));
          avatar.sizes = '(min-width:1200px) 25vw, (min-width:768px) 33vw, 50vw';
        } else {
          avatar.setAttribute('data-src', u);
        }
        try{ avatar.decoding = 'async'; }catch(_)
        {}
        try{ avatar.referrerPolicy = 'no-referrer'; }catch(_)
        {}
        try{ avatar.fetchPriority = 'low'; }catch(_)
        {}
        avatar.className = (avatar.className||'') + ' meal-avatar';
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
      qsa('#catGrid img.meal-avatar').forEach(function(im){ ioImg.observe(im); });
    }catch(_e){}
  }

  /** Try sessionStorage cache first; then one request for all items. Build MENU_CACHE by category. No per-click requests. */
  function readMenuFromCache(){
    try{
      const raw = sessionStorage.getItem(POS_CACHE_KEY);
      if(!raw) return false;
      const obj = JSON.parse(raw);
      const ts = obj.timestamp || 0;
      if(Date.now() - ts > POS_CACHE_TTL_MS) return false;
      const list = obj.items || obj;
      if(!Array.isArray(list) || list.length === 0) return false;
      const byCat = {};
      list.forEach(function(it){
        const cid = it.category_id != null ? String(it.category_id) : (it.categoryId != null ? String(it.categoryId) : '');
        if(!byCat[cid]) byCat[cid] = [];
        byCat[cid].push({ id: it.id, meal_id: it.meal_id || it.id, name: it.name || '', price: number(it.price), image_url: it.image_url || '' });
      });
      Object.keys(byCat).forEach(function(cid){ MENU_CACHE[cid] = byCat[cid]; });
      return true;
    }catch(e){ return false; }
  }
  function writeMenuToCache(){
    try{
      const flat = [];
      Object.keys(MENU_CACHE).forEach(function(cid){
        (MENU_CACHE[cid] || []).forEach(function(it){
          flat.push({ id: it.id, meal_id: it.meal_id, name: it.name, price: it.price, category_id: cid });
        });
      });
      sessionStorage.setItem(POS_CACHE_KEY, JSON.stringify({ items: flat, timestamp: Date.now() }));
    }catch(_e){}
  }

  /** Load once: use cache or GET /api/menu/all-items (with timeout), then filter locally. No request per category. */
  async function loadAllMenuItemsOnce(){
    if(ALL_ITEMS_LOADED) return;
    if(readMenuFromCache()){ ALL_ITEMS_LOADED = true; return; }
    const FETCH_TIMEOUT_MS = 12000;
    var timeoutId = null;
    try{
      var resp;
      if(typeof AbortController !== 'undefined'){
        var controller = new AbortController();
        timeoutId = setTimeout(function(){ controller.abort(); }, FETCH_TIMEOUT_MS);
        resp = await fetch('/api/menu/all-items', { credentials:'same-origin', signal: controller.signal });
      } else {
        resp = await fetch('/api/menu/all-items', { credentials:'same-origin' });
      }
      if(timeoutId){ clearTimeout(timeoutId); timeoutId = null; }
      const j = await resp.json().catch(()=>({}));
      const list = j.items || [];
      if(list.length === 0){ await preloadMenuItemsFallback(); return; }
      const byCat = {};
      list.forEach(function(it){
        const cid = it.category_id != null ? String(it.category_id) : '';
        if(!byCat[cid]) byCat[cid] = [];
        byCat[cid].push({ id: it.id, meal_id: it.meal_id || it.id, name: it.name || '', price: number(it.price), image_url: it.image_url || '' });
      });
      Object.keys(byCat).forEach(function(cid){ MENU_CACHE[cid] = byCat[cid]; });
      writeMenuToCache();
      ALL_ITEMS_LOADED = true;
    }catch(_e){
      if(timeoutId){ clearTimeout(timeoutId); }
      await preloadMenuItemsFallback();
    }
  }

  /** Fallback: fetch per category in parallel (when all-items not available). */
  async function preloadMenuItemsFallback(){
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
            MENU_CACHE[cid] = Array.isArray(data) ? data : [];
          }catch(_e){ MENU_CACHE[cid] = []; }
        }
      }
      await Promise.all(Array(4).fill(0).map(()=>worker()));
      writeMenuToCache();
      ALL_ITEMS_LOADED = true;
    }catch(_e){}
    PREFETCH_IN_PROGRESS = false;
  }

  async function preloadMenuItems(){
    await loadAllMenuItemsOnce();
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
            discount_pct: effectiveDiscountPct(),
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
            discount_pct: effectiveDiscountPct(),
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
    if(!(pm==='CASH' || pm==='CARD' || pm==='CREDIT')){ await window.showAlert('يرجى اختيار طريقة الدفع (CASH أو CARD أو آجل) / Please choose payment method (CASH, CARD or Credit)'); return; }
    const custIdVal = (qs('#custId')?.value || '').trim();
    if(pm === 'CREDIT' && !custIdVal){ await window.showAlert('يجب اختيار عميل آجل مسجل من القائمة / Select a registered credit customer from the list'); return; }
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
            discount_pct: effectiveDiscountPct(),
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
        const custIdVal = (qs('#custId')?.value || '').trim();
        const res = await fetch('/api/draft/checkout', { method:'POST', headers, credentials:'same-origin', body: JSON.stringify({
          draft_id: CURRENT_DRAFT_ID,
          customer_id: custIdVal ? parseInt(custIdVal, 10) : null,
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

    const custIdVal = (qs('#custId')?.value || '').trim();
    const custName = (qs('#custName')?.value || '').trim();
    const custPhone = (qs('#custPhone')?.value || '').trim();
    const pm = (qs('#payMethod')?.value || '').trim().toUpperCase();

    if(pm === 'CREDIT' && !custIdVal){
      await window.showAlert('يجب اختيار عميل آجل مسجل من القائمة — لا يمكن إصدار فاتورة آجلة لعميل غير مسجل / Select a registered credit customer from the list'); return;
    }
    if(custName && !custIdVal && pm === 'CREDIT'){
      await window.showAlert('العميل المدخل غير مسجل كعميل آجل — اختر عميلاً من القائمة أو غيّر طريقة الدفع / Entered customer is not registered as credit'); return;
    }

    if(custName){
      if(custPhone && custPhone.replace(/\D/g,'').length < 8){ await window.showAlert('رقم هاتف العميل غير صالح / Invalid customer phone'); return; }
    }

    if(!(pm==='CASH' || pm==='CARD' || pm==='CREDIT')){ await window.showAlert('يرجى اختيار طريقة الدفع (CASH أو CARD أو آجل) / Please choose payment method (CASH, CARD or Credit)'); return; }

    // Validate discount/tax (effective discount is 0 when no registered customer)
    const disc = effectiveDiscountPct();
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
      const sendCustId = custIdVal ? parseInt(custIdVal, 10) : null;
      const sendCustName = (pm === 'CREDIT' && sendCustId) ? custName : (pm !== 'CREDIT' ? custName : '');
      const sendCustPhone = (pm === 'CREDIT' && sendCustId) ? custPhone : (pm !== 'CREDIT' ? custPhone : '');
      const res = await fetch('/api/sales/checkout', { 
        method:'POST', headers, credentials:'same-origin',
        body: JSON.stringify({
          draft_id: CURRENT_DRAFT_ID,
          items: items.map(x=>({ meal_id:x.meal_id, name:x.name, price:x.unit, qty:x.qty })),
          customer_id: sendCustId,
          customer_name: sendCustName,
          customer_phone: sendCustPhone,
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

  // --- POS Lifecycle (Gate pattern) ---
  // 1. isReady = false → Loading overlay visible, screen gated (no interaction).
  // 2. init: loadBranchSettings → loadDraftFromAPI → loadAllMenuItemsOnce (await all) → render + bind.
  // 3. setScreenReady() ONLY after step 2 completes. No other place must hide overlay or ungate.
  // 4. Category click = local filter from MENU_CACHE only; no API calls.
  function setScreenReady(){
    SCREEN_READY = true;
    var overlay = document.getElementById('pos-loading-overlay');
    if(overlay){ overlay.style.display = 'none'; overlay.setAttribute('aria-hidden', 'true'); }
    try{ document.body.classList.add('pos-screen-ready'); }catch(_){}
    var screenEl = document.getElementById('pos-screen');
    if(screenEl){ screenEl.classList.remove('pos-gated'); screenEl.classList.add('pos-ready'); }
  }

  window.addEventListener('DOMContentLoaded', function(){
    var init = qs('#pos-init');
    BRANCH = (init && init.getAttribute('data-branch')) || (document.body && document.body.dataset.branch) || '';
    TABLE_NO = (init && init.getAttribute('data-table')) || (document.body && document.body.dataset.table) || '';
    VAT_RATE = number((init && init.getAttribute('data-vat')) || 0);
    VOID_PASSWORD = ((init && init.getAttribute('data-void-password')) || '').trim() || '1991';

    // Optional server-rendered draft (may be overwritten by loadDraftFromAPI)
    try {
      var draftRaw = (init && init.getAttribute('data-draft')) || '[]';
      var draft = JSON.parse(draftRaw);
      if(Array.isArray(draft)) draft.forEach(function(d){ items.push({ meal_id: d.meal_id || d.id, name: d.name || '', unit: number(d.price || d.unit), qty: number(d.quantity || d.qty || 1) }); });
    }catch(e){}
    CURRENT_DRAFT_ID = ((init && init.getAttribute('data-draft-id')) || '').trim() || null;
    try{
      var initCustName = (init && init.getAttribute('data-cust-name')) || '';
      var initCustPhone = (init && init.getAttribute('data-cust-phone')) || '';
      var initDisc = (init && init.getAttribute('data-disc')) || '';
      var initTax = (init && init.getAttribute('data-tax')) || '';
      var initPay = (init && init.getAttribute('data-pay')) || '';
      var el = qs('#custName'); if(el) el.value = initCustName;
      el = qs('#custPhone'); if(el) el.value = initCustPhone;
      el = qs('#discountPct'); if(el) el.value = String(number(initDisc));
      el = qs('#taxPct'); if(el) el.value = String(number(initTax));
      el = qs('#payMethod'); if(el) el.value = (initPay || '').toString().toUpperCase();
      var custIdEl = qs('#custId');
      if(!custIdEl || !(custIdEl.value||'').trim()){
        el = qs('#discountPct'); if(el){ el.value = '0'; el.setAttribute('readonly',''); el.classList.add('bg-light'); el.title = 'لا خصم — عميل غير مسجل'; }
      }
    }catch(_e){}

    try{ CAT_MAP = JSON.parse((init && init.getAttribute('data-cat-map')) || '{}') || {}; }catch(e){ CAT_MAP = {}; }
    var CAT_IMAGES = {};
    try{ CAT_IMAGES = JSON.parse((init && init.getAttribute('data-cat-images')) || '{}') || {}; }catch(_e){}

    // Blocking init: load all data first, then bind UI, then allow interaction
    (async function(){
      try {
        await loadBranchSettings();
        await loadDraftFromAPI();
        await loadAllMenuItemsOnce();
      } catch(e) {
        console.warn('POS init load warning', e);
        if(!ALL_ITEMS_LOADED) ALL_ITEMS_LOADED = true;
      }
      try {
        renderItems();
        setTotals();
      } catch(_e) {}

      try {
      (function bindUI(){
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
          if(!thumb){ thumb = document.createElement('div'); thumb.className = 'thumb'; thumb.style.width='100%'; thumb.style.height='36px'; thumb.style.borderRadius='12px'; thumb.style.overflow='hidden'; thumb.style.background='linear-gradient(180deg, rgba(28,44,88,.06), rgba(28,44,88,.02))'; body.insertBefore(thumb, body.firstChild); }
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
    // If user types KEETA/HUNGER as customer, apply discount immediately without requiring phone
    const custInputSpecial = qs('#custName');
    custInputSpecial?.addEventListener('change', function(){
      const up = (custInputSpecial.value||'').trim().toUpperCase();
      if(up === 'KEETA' || up === 'HUNGER'){
        // Discount already handled in handleCustInput on 'input'; ensure totals update
        setTotals(); scheduleSave();
      }
    });
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

    function updatePaymentMethodFromCustomer(){
      const paySel = qs('#payMethod'); if(!paySel) return;
      const custIdEl = qs('#custId');
      const hasRegisteredCustomer = custIdEl && (custIdEl.value || '').trim().length > 0;
      if(!hasRegisteredCustomer){
        setDiscountFieldForCustomer(false, 0);
        paySel.innerHTML = '<option value="">-- اختر طريقة الدفع --</option><option value="CASH">CASH</option><option value="CARD">CARD</option>';
        if((paySel.value || '').toUpperCase() === 'CREDIT') paySel.value = 'CASH';
        scheduleSave();
        return;
      }
      const custNameVal = (custInput?.value || '').trim().toLowerCase();
      const customerType = custIdEl.getAttribute('data-customer-type') || '';
      const isCredit = (customerType === 'credit') || (custNameVal.indexOf('keeta') !== -1) || (custNameVal.indexOf('hunger') !== -1);
      const cur = (paySel.value || '').toUpperCase();
      const dp = qs('#discountPct');
      if(isCredit){
        paySel.innerHTML = '<option value="">-- اختر --</option><option value="CREDIT">Credit / آجل</option>';
        paySel.value = 'CREDIT';
        if(dp){ try{ dp.removeAttribute('readonly'); dp.classList.remove('bg-light'); dp.title = 'قابل للتعديل — عميل آجل'; }catch(_e){} }
      } else {
        paySel.innerHTML = '<option value="">-- اختر طريقة الدفع --</option><option value="CASH">CASH</option><option value="CARD">CARD</option>';
        if(cur === 'CREDIT') paySel.value = 'CASH';
        else if(cur && cur !== 'CASH' && cur !== 'CARD') paySel.value = 'CASH';
        const currentPct = number(dp?.value || 0, 0);
        setDiscountFieldForCustomer(false, currentPct);
      }
      scheduleSave();
    }

    async function fetchCustomers(q){
      try{
        const resp = await fetch(`/api/customers/search?q=${encodeURIComponent(q)}`, { credentials:'same-origin' });
        if(!resp.ok) return [];
        const j = await resp.json().catch(()=>({results:[]}));
        // API may return { results: [...] } or a raw array; normalize customer_type/discount_percent
        let list = Array.isArray(j.results) ? j.results : (Array.isArray(j) ? j : []);
        return list.map(function(r){
          var t = (r.customer_type || 'cash').toString().toLowerCase();
          if(t === 'آجل') t = 'credit';
          return {
            id: r.id,
            name: r.name || '',
            phone: r.phone || '',
            discount_percent: typeof r.discount_percent !== 'undefined' ? number(r.discount_percent, 0) : number(r.discount, 0),
            customer_type: t === 'credit' ? 'credit' : 'cash'
          };
        });
      }catch(e){ return []; }
    }

    function setDiscountFieldForCustomer(isCredit, discountPct){
      const dp = qs('#discountPct');
      if(!dp) return;
      const pct = number(discountPct, 0);
      if(isCredit){
        dp.value = String(pct);
        try{ dp.removeAttribute('readonly'); dp.classList.remove('bg-light'); dp.title = 'قابل للتعديل — عميل آجل'; }catch(_e){}
      } else {
        dp.value = String(pct);
        try{ dp.setAttribute('readonly',''); dp.classList.add('bg-light'); dp.title = pct > 0 ? 'خصم ثابت للعميل النقدي المسجل' : 'لا خصم — عميل غير مسجل'; }catch(_e){}
      }
      setTotals(); scheduleSave();
    }
    window.setDiscountFieldForCustomer = setDiscountFieldForCustomer;
    window.updatePaymentMethodFromCustomer = updatePaymentMethodFromCustomer;

    async function checkCreditCustomer(name, phone){
      try{
        let url = `/api/customers/check-credit?q=${encodeURIComponent((name||'').trim())}`;
        if(phone && (phone||'').trim()) url += `&phone=${encodeURIComponent((phone||'').trim())}`;
        const resp = await fetch(url, { credentials: 'same-origin' });
        if(!resp.ok) return { found: false };
        const j = await resp.json().catch(()=>({}));
        return j;
      }catch(e){ return { found: false }; }
    }

    async function handleCustInput(){
      const val = (custInput?.value || '').trim();
      const custIdEl = qs('#custId');
      if(!val){ if(custIdEl){ custIdEl.value = ''; custIdEl.removeAttribute('data-customer-type'); } updatePaymentMethodFromCustomer(); hideCustList(); return; }
      const up = val.toUpperCase();
      if(up === 'KEETA' || up === 'HUNGER'){
        const dp = qs('#discountPct');
        if(dp){ try{ dp.removeAttribute('readonly'); dp.classList.remove('bg-light'); dp.title = 'Special discount for KEETA/HUNGER'; }catch(_e){} }
        const p = await (window.showPrompt ? window.showPrompt('أدخل نسبة خصم خاصة % / Enter special discount %') : Promise.resolve(prompt('أدخل نسبة خصم خاصة % / Enter special discount %')));
        if(p!==null){ const n = number(p, 0); if(dp){ dp.value = String(n); } setTotals(); scheduleSave(); }
      }
      else {
        if(!custIdEl || !(custIdEl.value||'').trim()){ setDiscountFieldForCustomer(false, 0); }
        else { updatePaymentMethodFromCustomer(); }
      }
      clearTimeout(custFetchTimer);
      if(!val){ hideCustList(); return; }
      updatePaymentMethodFromCustomer();
      custFetchTimer = setTimeout(async ()=>{
        const results = await fetchCustomers(val);
        if(!custList) return;
        custList.innerHTML = '';
        results.forEach(r=>{
          const a = document.createElement('a'); a.href='#'; a.className='list-group-item list-group-item-action';
          const typeLabel = (r.customer_type||'cash')==='credit' ? ' (آجل)' : '';
          a.textContent = `${r.name}${r.phone ? ' ('+r.phone+')' : ''}${typeLabel} — خصم ${number(r.discount_percent||0).toFixed(2)}%`;
          a.addEventListener('click', (e)=>{
            e.preventDefault();
            const custIdEl = qs('#custId');
            if(custIdEl){
              custIdEl.value = r.id ? String(r.id) : '';
              custIdEl.setAttribute('data-customer-type', (r.customer_type || 'cash'));
            }
            if(custInput) custInput.value = r.name || '';
            if(custPhone) custPhone.value = r.phone || '';
            hideCustList();
            if((r.customer_type||'cash')==='credit'){
              setDiscountFieldForCustomer(true, number(r.discount_percent||0));
            } else {
              setDiscountFieldForCustomer(false, number(r.discount_percent||0));
            }
            updatePaymentMethodFromCustomer();
          });
          custList.appendChild(a);
        });
        if(results.length){ showCustList(); } else { hideCustList(); }
      }, 80);
    }

    custInput?.addEventListener('input', handleCustInput);

    custInput?.addEventListener('blur', async function(){
      const custIdEl = qs('#custId');
      if(custIdEl && (custIdEl.value||'').trim()) return;
      const name = (custInput?.value || '').trim();
      if(!name) return;
      const phone = (custPhone?.value || '').trim();
      const j = await checkCreditCustomer(name, phone);
      if(!j.found){
        custInput.value = ''; if(custPhone) custPhone.value = '';
        if(custIdEl){ custIdEl.value = ''; custIdEl.removeAttribute('data-customer-type'); }
        setDiscountFieldForCustomer(false, 0);
        updatePaymentMethodFromCustomer();
        showToast('العميل غير مسجل — لا خصم');
        return;
      }
      if(j.is_credit){
        custIdEl.value = String(j.id); custIdEl.setAttribute('data-customer-type', 'credit');
        if(custInput) custInput.value = j.name || name;
        if(custPhone) custPhone.value = j.phone || phone || '';
        setDiscountFieldForCustomer(true, number(j.discount_percent||0));
      } else {
        custIdEl.value = String(j.id); custIdEl.setAttribute('data-customer-type', 'cash');
        if(custInput) custInput.value = j.name || name;
        if(custPhone) custPhone.value = j.phone || phone || '';
        setDiscountFieldForCustomer(false, number(j.discount_percent||0));
      }
      updatePaymentMethodFromCustomer();
    });

    document.addEventListener('click', (e)=>{ if(!custList) return; if(!custList.contains(e.target) && e.target !== custInput){ hideCustList(); } });
    updatePaymentMethodFromCustomer();

    renderItems();
    })();
      } catch(e) { console.error('POS bindUI error', e); }
      setScreenReady();
    })();

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
