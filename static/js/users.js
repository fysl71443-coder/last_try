// Minimal client-side wiring for Users screen
(function(){
  const $ = (sel,ctx=document)=>ctx.querySelector(sel);
  const $$ = (sel,ctx=document)=>Array.from(ctx.querySelectorAll(sel));

  const table = $('#usersTable');
  const btnAdd = $('#btnAdd');
  const btnEdit = $('#btnEdit');
  const btnDelete = $('#btnDelete');
  const btnPerms = $('#btnPerms');

  // TODO: wire to backend endpoints when implemented
  btnAdd?.addEventListener('click', ()=> alert('سيتم فتح نافذة إضافة مستخدم (لاحقاً).'));
  btnEdit?.addEventListener('click', ()=> alert('سيتم فتح نافذة تعديل المستخدم المختار (لاحقاً).'));
  btnDelete?.addEventListener('click', ()=> alert('سيتم تنفيذ حذف المستخدمين المختارين (لاحقاً).'));

  // Permissions saving demo
  const savePerms = document.getElementById('savePerms');
  savePerms?.addEventListener('click', ()=>{
    // gather selection
    const rowsel = $$('#usersTable .rowSel:checked');
    if(rowsel.length===0){ alert('اختر مستخدماً واحداً على الأقل'); return; }
    const userIds = rowsel.map(cb=> cb.closest('tr').dataset.id);
    const payload = [];
    $$('#screensList .list-group-item').forEach(item=>{
      const key = item.querySelector('.screenCheck').dataset.key;
      const perms = {};
      item.querySelectorAll('.permCheck').forEach(p=>{ perms[p.dataset.perm] = p.checked; });
      payload.push({screen_key:key, ...perms});
    });
    alert('سيتم إرسال الصلاحيات لـ '+userIds.join(', ')+' (لاحقاً).');
  });
})();
