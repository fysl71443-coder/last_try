// Bind toolbar buttons to API
(function(){
  const table = document.getElementById('usersTable');
  if(!table) return;
  const btnAdd = document.getElementById('btnAdd');
  const btnEdit = document.getElementById('btnEdit');
  const btnDelete = document.getElementById('btnDelete');
  const btnPerms = document.getElementById('btnPerms');
  const branchSelect = document.getElementById('branchSelect');

  function selectedIds(){
    return Array.from(table.querySelectorAll('.rowSel:checked')).map(cb=>cb.closest('tr').dataset.id);
  }
  async function api(method, url, body){
    const res = await fetch(url, { method, headers:{'Content-Type':'application/json'}, body: body?JSON.stringify(body):undefined });
    if(!res.ok){ const t=await res.text(); throw new Error(t||res.status); }
    return res.json();
  }

  btnAdd?.addEventListener('click', async ()=>{
    const username = prompt('اسم المستخدم'); if(!username) return;
    const email = prompt('البريد (اختياري)')||'';
    const role = prompt('الدور (user/admin)')||'user';
    const password = prompt('كلمة المرور'); if(!password) return;
    try{ await api('POST','/api/users',{username,email,role,password}); location.reload(); }catch(e){ alert('خطأ: '+e.message); }
  });

  btnEdit?.addEventListener('click', async ()=>{
    const ids = selectedIds(); if(ids.length!==1) return;
    const row = table.querySelector(`tr[data-id="${ids[0]}"]`);
    const email = prompt('البريد', row.children[3].innerText);
    const role = prompt('الدور', row.children[4].innerText);
    const active = confirm('هل المستخدم نشط؟ موافق=نعم / إلغاء=لا');
    try{ await api('PATCH', `/api/users/${ids[0]}`, {email, role, active}); location.reload(); }catch(e){ alert('خطأ: '+e.message); }
  });

  btnDelete?.addEventListener('click', async ()=>{
    const ids = selectedIds(); if(ids.length===0) return;
    if(!confirm('تأكيد حذف المستخدمين المختارين؟')) return;
    try{ await api('DELETE','/api/users',{ids}); location.reload(); }catch(e){ alert('خطأ: '+e.message); }
  });

  document.getElementById('savePerms')?.addEventListener('click', async ()=>{
    const ids = selectedIds(); if(ids.length===0){ alert('اختر مستخدماً واحداً على الأقل'); return; }
    const uid = ids[0];
    const items = [];
    document.querySelectorAll('#screensList .list-group-item').forEach(item=>{
      const key = item.querySelector('.screenCheck').dataset.key;
      const obj = { screen_key:key };
      item.querySelectorAll('.permCheck').forEach(p=> obj[p.dataset.perm] = p.checked );
      items.push(obj);
    });
    const branch_scope = branchSelect.value;
    try{ await api('POST', `/api/users/${uid}/permissions`, { items, branch_scope }); alert('تم الحفظ'); }catch(e){ alert('خطأ: '+e.message); }
  });
})();
