(function(){
  'use strict';

  function getCsrf() {
    const el = document.querySelector('meta[name="csrf-token"]');
    return el ? el.content : '';
  }
  // Expose global CSRF token
  window.csrfToken = getCsrf();

  // Force English numerals (Latin digits) everywhere
  // Maps Arabic-Indic (U+0660–U+0669) and Eastern Arabic-Indic (U+06F0–U+06F9) to 0-9
  // Also normalizes Arabic decimal separator (٫) to '.' and thousands (٬) to ',' (or removed in numeric fields)
  function toLatinDigits(str, forNumericField){
    if (str == null) return str;
    var s = String(str);
    // Arabic-Indic
    s = s.replace(/[\u0660-\u0669]/g, function(ch){ return String(ch.charCodeAt(0) - 0x0660); });
    // Eastern Arabic-Indic (Persian)
    s = s.replace(/[\u06F0-\u06F9]/g, function(ch){ return String(ch.charCodeAt(0) - 0x06F0); });
    // Arabic decimal separator → '.'
    s = s.replace(/\u066B/g, '.');
    // Arabic thousands separator → ',' (or remove in numeric fields)
    if (forNumericField) s = s.replace(/\u066C/g, ''); else s = s.replace(/\u066C/g, ',');
    // Arabic comma → ','
    s = s.replace(/\u060C/g, ',');
    return s;
  }
  window.toLatinDigits = toLatinDigits;

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
    // Enforce English (Latin) digits rendering for numeric inputs and month pickers
    try{
      document.querySelectorAll('input[type="number"], input[type="month"], input[inputmode="decimal"], input[inputmode="numeric"], input[type="tel"]').forEach(function(inp){
        // Force English locale for numerals in affected controls
        if (!inp.hasAttribute('lang')) inp.setAttribute('lang', 'en');
        // Keep numeric fields left-to-right for consistent visual order
        if (!inp.style.direction) inp.style.direction = 'ltr';
        // Align numbers left to reduce bidi mixing issues
        if (!inp.style.textAlign) inp.style.textAlign = 'left';
      });
    }catch(e){ /* noop */ }

    // Normalize all existing text nodes to Latin digits
    try{
      var walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
      var node;
      while((node = walker.nextNode())){
        var t = node.nodeValue;
        var nt = toLatinDigits(t, false);
        if (nt !== t) node.nodeValue = nt;
      }
    }catch(e){ /* noop */ }

    // Normalize inputs on input/change
    try{
      document.querySelectorAll('input, textarea').forEach(function(inp){
        function handler(){
          var start = inp.selectionStart, end = inp.selectionEnd;
          var isNumeric = (inp.type === 'number') || /number|tel/.test(inp.inputMode || '') || /\d/.test(inp.value);
          var v = toLatinDigits(inp.value, isNumeric);
          if (inp.value !== v){ inp.value = v; try{ inp.setSelectionRange(start, end); }catch(e){} }
        }
        inp.addEventListener('input', handler);
        inp.addEventListener('change', handler);
        // Initial pass
        handler();
      });
    }catch(e){ /* noop */ }

    // Observe DOM changes to keep digits normalized in dynamic content
    try{
      var mo = new MutationObserver(function(muts){
        muts.forEach(function(m){
          if (m.type === 'childList'){
            m.addedNodes && m.addedNodes.forEach(function(n){
              if (n.nodeType === 3){
                var nt = toLatinDigits(n.nodeValue, false);
                if (nt !== n.nodeValue) n.nodeValue = nt;
              } else if (n.nodeType === 1){
                // Normalize new subtree text
                var w = document.createTreeWalker(n, NodeFilter.SHOW_TEXT, null);
                var nn; while((nn = w.nextNode())){
                  var t2 = nn.nodeValue, nt2 = toLatinDigits(t2, false);
                  if (nt2 !== t2) nn.nodeValue = nt2;
                }
                // Normalize inputs inside new subtree
                n.querySelectorAll && n.querySelectorAll('input, textarea').forEach(function(inp){
                  var isNumeric = (inp.type === 'number') || /number|tel/.test(inp.inputMode || '') || /\d/.test(inp.value);
                  var v = toLatinDigits(inp.value, isNumeric);
                  if (inp.value !== v) inp.value = v;
                });
              }
            });
          } else if (m.type === 'characterData'){
            var nv = toLatinDigits(m.target.nodeValue, false);
            if (nv !== m.target.nodeValue) m.target.nodeValue = nv;
          }
        });
      });
      mo.observe(document.body, { childList:true, characterData:true, subtree:true });
    }catch(e){ /* noop */ }
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

