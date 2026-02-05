/**
 * Phase 4 – Partial navigation: fetch full page, swap #app-messages + #app-main only.
 * Keeps navbar static; instant-feel navigation. Opt-in via data-partial.
 */
(function () {
  'use strict';

  var LOADING_CLASS = 'app-partial-loading';
  var PARTIAL_ATTR = 'data-partial';

  /** Routes that must do full page load: partial swap only replaces HTML and does not run <script>s, so event handlers and data would never load until refresh. */
  function requiresFullLoad(pathname) {
    var p = (pathname || '').replace(/\/+$/, '');
    if (/\/pos\//i.test(p)) return true;
    if (/\/sales\//i.test(p)) return true;
    if (/\/expenses\/?/i.test(p)) return true;
    if (/\/financials\/?/i.test(p)) return true;
    if (/\/purchases\/?/i.test(p)) return true;
    if (/\/menu\/?/i.test(p)) return true;
    if (/\/journal\/?/i.test(p)) return true;
    if (/\/customers\/?/i.test(p)) return true;
    if (/\/suppliers\/?/i.test(p)) return true;
    if (/\/payments\/?/i.test(p)) return true;
    if (/\/employees\/?/i.test(p)) return true;
    if (/\/users\/?/i.test(p)) return true;
    if (/\/settings\/?/i.test(p)) return true;
    if (/\/invoices\/?/i.test(p)) return true;
    if (/\/archive\/?/i.test(p)) return true;
    if (/\/tables\/?/i.test(p)) return true;
    return false;
  }

  function isPartialLink(a) {
    if (!a || a.tagName !== 'A') return false;
    var h = a.getAttribute('href');
    if (!h || h === '#' || h.startsWith('javascript:')) return false;
    if (a.target === '_blank' || a.hasAttribute('data-full-reload')) return false;
    try {
      var u = new URL(h, location.origin);
      if (u.origin !== location.origin) return false;
      var p = u.pathname || '/';
      if (/\/login\/?$/i.test(p) || /\/logout\/?$/i.test(p)) return false;
      if (u.pathname === location.pathname && (u.hash || '').length > 0) return false;
      if (requiresFullLoad(p)) return false;
    } catch (e) { return false; }
    return a.hasAttribute(PARTIAL_ATTR) || a.closest('[data-partial-links]') !== null;
  }

  function setLoading(on) {
    var main = document.getElementById('app-main');
    if (main) main.classList.toggle(LOADING_CLASS, !!on);
  }

  function getDoc(html) {
    var parser = new DOMParser();
    return parser.parseFromString(html, 'text/html');
  }

  function replaceMessagesAndMain(fetchedDoc) {
    var curMsg = document.getElementById('app-messages');
    var curMain = document.getElementById('app-main');
    var newMsg = fetchedDoc.getElementById('app-messages');
    var newMain = fetchedDoc.getElementById('app-main');
    var title = fetchedDoc.querySelector('title');
    if (title && title.textContent) document.title = title.textContent;
    if (curMain && newMain) {
      curMain.innerHTML = newMain.innerHTML;
    }
    if (curMsg && newMsg) {
      curMsg.innerHTML = newMsg.innerHTML;
      var backBtn = curMsg.querySelector('#global-back-button');
      if (backBtn && typeof window.safeBack === 'function') {
        backBtn.onclick = function () {
          var url = this.getAttribute('data-back-url') || '';
          window.safeBack(url);
        };
      }
    }
  }

  function loadPartial(url, push) {
    try {
      var path = new URL(url, location.origin).pathname || '';
      if (requiresFullLoad(path)) {
        window.location.href = url;
        return;
      }
    } catch (e) {}
    setLoading(true);
    fetch(url, {
      method: 'GET',
      headers: { 'Accept': 'text/html', 'X-Requested-With': 'PartialNav' },
      credentials: 'same-origin'
    })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.text();
      })
      .then(function (html) {
        var doc = getDoc(html);
        var newMain = doc.getElementById('app-main');
        if (!newMain) {
          window.location.href = url;
          return;
        }
        replaceMessagesAndMain(doc);
        if (push !== false) {
          try { history.pushState({ partial: true, url: url }, '', url); } catch (e) {}
        }
      })
      .catch(function () {
        window.location.href = url;
      })
      .finally(function () {
        setLoading(false);
      });
  }

  function handleClick(e) {
    var a = e.target.closest('a');
    if (!isPartialLink(a)) return;
    e.preventDefault();
    var url = a.getAttribute('href');
    if (!url) return;
    loadPartial(url, true);
  }

  function handlePopState(e) {
    var u = (e.state && e.state.url) ? e.state.url : (location.pathname + location.search);
    if (e.state && e.state.partial) {
      loadPartial(u, false);
    }
  }

  document.addEventListener('click', handleClick, true);

  window.addEventListener('popstate', handlePopState);

  document.addEventListener('DOMContentLoaded', function () {
    try {
      if (!history.state || !history.state.partial) {
        history.replaceState({ partial: true, url: location.pathname + location.search }, '', location.pathname + location.search);
      }
    } catch (e) {}
    var style = document.createElement('style');
    style.id = 'nav-partial-styles';
    style.textContent = [
      '#app-main.app-partial-loading { position: relative; min-height: 80px; }',
      '#app-main.app-partial-loading::before {',
      '  content: ""; position: absolute; inset: 0; z-index: 5;',
      '  background: rgba(248,249,250,.85); pointer-events: none;',
      '  border-radius: 12px;',
      '}',
      'body.dark #app-main.app-partial-loading::before { background: rgba(18,18,18,.6); }',
      '#app-main.app-partial-loading::after {',
      '  content: ""; position: absolute; left: 50%; top: 50%; z-index: 6;',
      '  width: 28px; height: 28px; margin: -14px 0 0 -14px;',
      '  border: 3px solid rgba(0,77,64,.2); border-top-color: var(--primary,#004D40);',
      '  border-radius: 50%; animation: nav-partial-spin .6s linear infinite;',
      '}',
      '@keyframes nav-partial-spin { to { transform: rotate(360deg); } }'
    ].join('\n');
    if (!document.getElementById('nav-partial-styles')) document.head.appendChild(style);
  });
})();
