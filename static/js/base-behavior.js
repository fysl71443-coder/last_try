(function(){
  'use strict';

  function getCsrf() {
    const el = document.querySelector('meta[name="csrf-token"]');
    return el ? el.content : '';
  }
  // Expose global CSRF token
  window.csrfToken = getCsrf();

  // Unsaved-changes guard
  let __dirty = false;
  function markDirty(){ __dirty = true; }
  function clearDirty(){ __dirty = false; }

  window.safeBack = function(url){
    try{
      if(__dirty){
        if(!window.confirm('You have unsaved changes. Are you sure you want to go back?')) return;
      }
      if(url){ window.location.href = url; } else { history.back(); }
    }catch(e){ if(url) window.location.href = url; else history.back(); }
  };

  window.addEventListener('DOMContentLoaded', function(){
    // Track form edits
    document.querySelectorAll('form').forEach(f=>{
      f.addEventListener('input', markDirty);
      f.addEventListener('change', markDirty);
      f.addEventListener('submit', clearDirty);
    });
    // Back button binding (no inline)
    const backBtn = document.getElementById('global-back-button');
    if(backBtn){
      backBtn.addEventListener('click', function(){
        const url = this.getAttribute('data-back-url') || '';
        window.safeBack(url);
      });
    }
  });

  // Warn on unload if dirty
  window.addEventListener('beforeunload', function(e){
    if(__dirty){
      e.preventDefault();
      e.returnValue = '';
    }
  });
})();

