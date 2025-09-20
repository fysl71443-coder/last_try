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
  });
})();

