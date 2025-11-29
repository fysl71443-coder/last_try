(function(){
  function qs(sel, root){ return (root||document).querySelector(sel); }
  function qsa(sel, root){ return Array.from((root||document).querySelectorAll(sel)); }

  async function refreshTables(){
    try{
      const root = qs('#tables-root'); if(!root) return;
      const branch = root.getAttribute('data-branch'); if(!branch) return;
      // Prefer /api/tables/<branch> which returns rich objects
      const res = await fetch(`/api/tables/${branch}`, { credentials:'same-origin' });
      if(!res.ok) return;
      const data = await res.json(); // [{table_number, status, ...}]

      const byNo = Object.create(null);
      (data||[]).forEach(t => { byNo[String(t.table_number)] = t.status; });

      qsa('a.btn[data-table]', root).forEach(el => {
        const tid = String(el.getAttribute('data-table'));
        const status = byNo[tid] || 'available';
        const badge = el.querySelector('.status-label');
        if(status === 'occupied'){
          el.classList.remove('btn-success'); el.classList.add('btn-danger');
          if(badge){ badge.textContent = 'Occupied'; badge.classList.remove('bg-success'); badge.classList.add('bg-danger'); }
        } else {
          el.classList.remove('btn-danger'); el.classList.add('btn-success');
          if(badge){ badge.textContent = 'Available'; badge.classList.remove('bg-danger'); badge.classList.add('bg-success'); }
        }
      });
    }catch(e){ /* silent */ }
  }

  window.addEventListener('DOMContentLoaded', function(){
    refreshTables();
    setInterval(refreshTables, 5000);

    // Enable basic drag-and-drop layout editor when ?edit=1 is present
    try{
      const url = new URL(window.location.href);
      if(url.searchParams.get('edit') === '1'){
        const root = qs('#tables-root');
        const branch = root && root.getAttribute('data-branch');
        if(root && branch){
          root.classList.add('layout-edit');
          qsa('a.btn[data-table]', root).forEach(el => {
            el.setAttribute('draggable', 'true');
            el.addEventListener('dragstart', ev => {
              ev.dataTransfer.setData('text/plain', el.getAttribute('data-table'));
            });
          });
          // Allow dropping into any row container
          qsa('.row.g-3', root).forEach(row => {
            row.addEventListener('dragover', ev => ev.preventDefault());
            row.addEventListener('drop', ev => {
              ev.preventDefault();
              const tid = ev.dataTransfer.getData('text/plain');
              const el = qs(`a.btn[data-table="${tid}"]`, root);
              if(el){ row.appendChild(el.parentElement); }
            });
          });
          // Add a simple save button floating
          const saveBtn = document.createElement('button');
          saveBtn.textContent = 'Save Layout';
          saveBtn.style.position = 'fixed';
          saveBtn.style.bottom = '20px';
          saveBtn.style.right = '20px';
          saveBtn.className = 'btn btn-primary';
          document.body.appendChild(saveBtn);
          saveBtn.addEventListener('click', async () => {
            // Capture layout as a single default section with rows reflecting DOM order
            const rows = [];
            qsa('.row.g-3', root).forEach(r => {
              const rowTables = [];
              qsa('a.btn[data-table]', r).forEach(a => rowTables.push(a.getAttribute('data-table')));
              if(rowTables.length){ rows.push(rowTables); }
            });
            const payload = { sections: [{ name: 'Default', rows }] };
            await fetch(`/api/table-layout/${branch}`, {
              method: 'POST', headers: { 'Content-Type': 'application/json' },
              credentials: 'same-origin', body: JSON.stringify(payload)
            });
            alert('Layout saved');
          });
        }
      }
    }catch(e){ /* ignore */ }
  });
})();

