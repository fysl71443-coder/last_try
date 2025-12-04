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

    try{
      const savedTheme = localStorage.getItem('theme') || '';
      if(savedTheme === 'dark'){ document.body.classList.add('dark'); }
      const savedDensity = localStorage.getItem('density') || '';
      if(savedDensity === 'compact'){ document.body.classList.add('compact'); }
    }catch(e){}

    const themeBtn = document.getElementById('btnThemeToggle');
    if(themeBtn){
      themeBtn.addEventListener('click', function(){
        const isDark = document.body.classList.toggle('dark');
        try{ localStorage.setItem('theme', isDark ? 'dark' : 'light'); }catch(e){}
        this.textContent = isDark ? '☀️' : '🌙';
      });
      const isDarkInit = document.body.classList.contains('dark');
      themeBtn.textContent = isDarkInit ? '☀️' : '🌙';
    }

    const densBtn = document.getElementById('btnDensityToggle');
    if(densBtn){
      densBtn.addEventListener('click', function(){
        const isCompact = document.body.classList.toggle('compact');
        try{ localStorage.setItem('density', isCompact ? 'compact' : 'comfortable'); }catch(e){}
        this.textContent = isCompact ? '📐' : '📏';
      });
      const isCompactInit = document.body.classList.contains('compact');
      densBtn.textContent = isCompactInit ? '📐' : '📏';
    }
  });

  // Warn on unload if dirty
  window.addEventListener('beforeunload', function(e){
    if(__dirty){
      e.preventDefault();
      e.returnValue = '';
    }
  });
  if(typeof window.showToast !== 'function'){
    window.showToast = function(msg, type){
      try{
        var t = document.getElementById('toast');
        if(!t){ t = document.createElement('div'); t.id='toast'; t.className='toast'; document.body.appendChild(t); }
        t.textContent = msg || t.textContent || '';
        t.style.transition='transform .4s ease, opacity .4s';
        t.style.transform='translateY(100px)';
        t.style.opacity='1';
        setTimeout(function(){ t.style.transform='translateY(-100px)'; t.style.opacity='0'; }, 3000);
      }catch(e){ console.log(msg); }
    };
  }
})();

