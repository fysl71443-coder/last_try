(function(){
  function qs(s,r){return (r||document).querySelector(s)}
  function qsa(s,r){return Array.from((r||document).querySelectorAll(s))}

  async function fetchJSON(url, opts){
    const csrf = (document.querySelector('meta[name="csrf-token"]')||{}).getAttribute ? (document.querySelector('meta[name="csrf-token"]').getAttribute('content')||'') : '';
    const baseHeaders = {'X-CSRFToken': csrf};
    const merged = Object.assign({credentials:'same-origin', headers:baseHeaders}, opts||{});
    // merge headers if caller provided some
    if(opts && opts.headers){ merged.headers = Object.assign({}, baseHeaders, opts.headers); }
    const res = await fetch(url, merged);
    if(!res.ok) throw new Error('HTTP '+res.status);
    return await res.json().catch(()=>({}));
  }

  function sectionEl(name){
    const wrap = document.createElement('div');
    wrap.className = 'card mb-3';
    wrap.innerHTML = `
      <div class="card-header d-flex justify-content-between align-items-center">
        <div class="d-flex align-items-center gap-2">
          <input class="form-control form-control-sm sec-name" style="width:240px" value="${name||''}" placeholder="Section name">
          <button class="btn btn-sm btn-outline-secondary add-row">Add Row</button>
        </div>
        <div>
          <button class="btn btn-sm btn-outline-danger remove-sec">Remove</button>
        </div>
      </div>
      <div class="card-body rows"></div>
    `;
    return wrap;
  }

  function rowEl(){
    const r = document.createElement('div');
    r.className = 'd-flex flex-wrap align-items-center gap-2 mb-2 row-holder';
    r.dataset.dropzone = '1';
    const tools = document.createElement('div');
    tools.className = 'btn-group btn-group-sm';
    tools.innerHTML = `
      <button class="btn btn-outline-secondary add-table">+Table</button>
      <button class="btn btn-outline-secondary move-up">↑</button>
      <button class="btn btn-outline-secondary move-down">↓</button>
      <button class="btn btn-outline-danger remove-row">×</button>
    `;
    r.appendChild(tools);
    r.addEventListener('dragover', ev=>ev.preventDefault());
    r.addEventListener('drop', ev=>{
      ev.preventDefault();
      const id = ev.dataTransfer.getData('text/plain');
      const el = document.getElementById(id);
      if(el) r.appendChild(el);
    });
    return r;
  }

  let uid = 0; function nextId(){ return 'tbl_'+(++uid); }
  function tableChip(number){
    const a = document.createElement('div');
    a.className = 'badge rounded-pill bg-primary p-2 px-3';
    a.textContent = 'T'+String(number||'');
    const id = nextId();
    a.id = id;
    a.setAttribute('draggable','true');
    a.dataset.table = String(number||'');
    a.addEventListener('dragstart', ev=>{
      ev.dataTransfer.setData('text/plain', id);
    });
    a.style.cursor = 'grab';
    a.style.userSelect = 'none';
    a.style.margin = '2px';
    // editable number on click or dblclick (accept digits only)
    function edit(){
      const cur = (a.dataset.table||'');
      const n = prompt('رقم الطاولة (أرقام فقط):', cur);
      if(n===null) return;
      const nn = String(n).trim();
      if(!/^\d+$/.test(nn)){
        alert('من فضلك أدخل أرقام فقط');
        return;
      }
      a.dataset.table = nn;
      a.textContent = 'T'+nn;
    }
    a.addEventListener('dblclick', edit);
    a.addEventListener('click', function(ev){
      if(ev.detail===2) return; // handled by dblclick
      // single click edit when holding Alt for convenience
      if(ev.altKey){ edit(); }
    });
    return a;
  }

  async function loadLayout(branch){
    const data = await fetchJSON(`/api/table-layout/${branch}`);
    return (data && data.layout) || { sections: [] };
  }

  function renderLayout(root, layout){
    const cont = qs('#sections', root); cont.innerHTML = '';
    (layout.sections||[]).forEach(sec=>{
      const sEl = sectionEl(sec.name||'');
      cont.appendChild(sEl);
      const rowsHost = qs('.rows', sEl);
      (sec.rows||[]).forEach(row=>{
        const r = rowEl(); rowsHost.appendChild(r);
        (row||[]).forEach(t=>{ r.appendChild(tableChip(t)); });
      });
    });
  }

  function captureLayout(root){
    const out = { sections: [] };
    qsa('#sections > .card', root).forEach(sec=>{
      const name = qs('.sec-name', sec).value.trim();
      const rows = [];
      qsa('.row-holder', sec).forEach(r=>{
        const ts = qsa('[data-table]', r).map(e=>e.dataset.table).filter(Boolean);
        if(ts.length) rows.push(ts);
      });
      out.sections.push({ name, rows });
    });
    return out;
  }

  async function saveLayout(branch, layout){
    await fetchJSON(`/api/table-layout/${branch}`,{
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(layout)
    });
  }

  window.addEventListener('DOMContentLoaded', async function(){
    const root = qs('#manager-root'); if(!root) return;
    const branch = root.getAttribute('data-branch');

    // load and render
    try{ renderLayout(root, await loadLayout(branch)); }catch(e){ renderLayout(root, {sections:[]}); }

    // add section
    qs('#addSectionBtn').addEventListener('click', ()=>{
      const name = qs('#newSectionName').value.trim() || 'Section';
      qs('#newSectionName').value = '';
      const sEl = sectionEl(name);
      qs('#sections').appendChild(sEl);
    });

    // delegated events
    document.body.addEventListener('click', (ev)=>{
      const btn = ev.target.closest('button'); if(!btn) return;
      if(btn.classList.contains('add-row')){
        const card = btn.closest('.card');
        qs('.rows', card).appendChild(rowEl());
      } else if(btn.classList.contains('remove-sec')){
        const card = btn.closest('.card'); card.remove();
      } else if(btn.classList.contains('add-table')){
        const holder = btn.closest('.row-holder');
        const n = prompt('رقم الطاولة (أرقام فقط):','');
        if(n===null) return;
        const nn = String(n).trim();
        if(!/^\d+$/.test(nn)){
          alert('من فضلك أدخل أرقام فقط');
          return;
        }
        holder.appendChild(tableChip(nn));
      } else if(btn.classList.contains('remove-row')){
        const holder = btn.closest('.row-holder'); holder.remove();
      } else if(btn.classList.contains('move-up')){
        const holder = btn.closest('.row-holder');
        if(holder.previousElementSibling) holder.parentElement.insertBefore(holder, holder.previousElementSibling);
      } else if(btn.classList.contains('move-down')){
        const holder = btn.closest('.row-holder');
        if(holder.nextElementSibling) holder.parentElement.insertBefore(holder.nextElementSibling, holder);
      }
    });

    // save
    qs('#saveLayoutBtn').addEventListener('click', async ()=>{
      const layout = captureLayout(root);
      await saveLayout(branch, layout);
      alert('Saved');
    });
  });
})();



