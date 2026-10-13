/* Shared site behavior: theme switch (system / light / dark) and presentation mode.
   Loaded in <head> without defer so the saved theme applies before first paint. */
(function () {
  var KEY = 'ans-theme';
  var root = document.documentElement;

  function readTheme() {
    try { return localStorage.getItem(KEY) || 'system'; } catch (e) { return 'system'; }
  }
  function applyTheme(t) {
    if (t === 'light' || t === 'dark') root.setAttribute('data-theme', t);
    else root.removeAttribute('data-theme');
  }
  applyTheme(readTheme());

  var ICONS = {
    system: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8"/><path d="M12 4a8 8 0 0 0 0 16z" fill="currentColor" stroke="none"/></svg>',
    light: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>',
    dark: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/></svg>',
    present: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="12" rx="1.5"/><path d="M12 16v4M8 20h8"/></svg>',
    prev: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 5l-7 7 7 7"/></svg>',
    next: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 5l7 7-7 7"/></svg>',
    close: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>'
  };
  var LABEL = { system: '테마: 시스템 설정', light: '테마: 라이트', dark: '테마: 다크' };
  var ORDER = ['system', 'light', 'dark'];

  function btn(cls, label, icon) {
    var b = document.createElement('button');
    b.type = 'button'; b.className = 'tool-btn ' + cls;
    b.setAttribute('aria-label', label); b.title = label; b.innerHTML = icon;
    return b;
  }

  /* ---------- presentation mode ---------- */
  var slides = [], cur = 0, on = false, bar, counter, progress;

  function fit() {
    var s = slides[cur]; if (!s) return;
    var w0 = s.querySelector(':scope > .wrap') || s;   // scale the content, not the full-screen box
    w0.style.zoom = 1;
    var availH = s.clientHeight - 48, availW = s.clientWidth;
    var zw = availW / w0.offsetWidth;
    var z = Math.min(zw, availH / w0.offsetHeight, 1.6);
    // long slides (big tables) stay readable and scroll with the wheel or ↑/↓ instead of shrinking
    if (z < 0.75) z = Math.min(zw, 1);
    w0.style.zoom = z;
  }
  function show(i) {
    cur = Math.max(0, Math.min(slides.length - 1, i));
    slides.forEach(function (s, k) { s.classList.toggle('slide-on', k === cur); });
    counter.textContent = (cur + 1) + ' / ' + slides.length;
    progress.style.width = ((cur + 1) / slides.length * 100) + '%';
    var s = slides[cur]; s.scrollTop = 0;
    fit();
    try { history.replaceState(null, '', '?present=' + (cur + 1) + location.hash); } catch (e) {}
  }
  function enter(start) {
    if (on) return; on = true;
    root.classList.add('presenting');
    bar.hidden = false;
    show(typeof start === 'number' ? start : 0);   // always start from the first slide
    if (root.requestFullscreen && !document.fullscreenElement) root.requestFullscreen().catch(function () {});
  }
  function exit() {
    if (!on) return; on = false;
    var s = slides[cur];
    root.classList.remove('presenting');
    bar.hidden = true;
    slides.forEach(function (x) {
      x.classList.remove('slide-on');
      var w = x.querySelector(':scope > .wrap'); if (w) w.style.zoom = '';
    });
    if (document.fullscreenElement && document.exitFullscreen) document.exitFullscreen().catch(function () {});
    try { history.replaceState(null, '', location.pathname + location.hash); } catch (e) {}
    if (s) s.scrollIntoView({ block: 'start' });
  }
  function init() {
    var main = document.querySelector('main');
    if (!main) return;
    slides = Array.prototype.filter.call(main.children, function (el) { return /^(SECTION|HEADER)$/.test(el.tagName); });
    slides.forEach(function (s) { s.classList.add('slide'); });

    // nav tools
    var navlinks = document.querySelector('nav .navlinks');
    var tools = document.createElement('div'); tools.className = 'nav-tools';
    var tbtn = btn('theme-btn', LABEL[readTheme()], ICONS[readTheme()]);
    var theme2 = btn('', LABEL[readTheme()], ICONS[readTheme()]);
    tbtn.addEventListener('click', function () {
      var t = ORDER[(ORDER.indexOf(readTheme()) + 1) % ORDER.length];
      try { localStorage.setItem(KEY, t); } catch (e) {}
      applyTheme(t);
      [tbtn, theme2].forEach(function (b) { b.innerHTML = ICONS[t]; b.title = LABEL[t]; b.setAttribute('aria-label', LABEL[t]); });
    });
    var pbtn = btn('present-btn', '발표 모드 (P)', ICONS.present + '<span>발표</span>');
    pbtn.addEventListener('click', function () { enter(); });
    tools.appendChild(tbtn); tools.appendChild(pbtn);
    if (navlinks) {
      var primary = navlinks.querySelector('.btn-primary');
      navlinks.insertBefore(tools, primary || null);
    }

    // presenter control bar
    bar = document.createElement('div'); bar.className = 'present-bar'; bar.hidden = true;
    bar.setAttribute('role', 'toolbar'); bar.setAttribute('aria-label', '발표 컨트롤');
    progress = document.createElement('i'); progress.className = 'present-progress';
    var prev = btn('', '이전 슬라이드', ICONS.prev), next = btn('', '다음 슬라이드', ICONS.next);
    var close = btn('', '발표 종료 (Esc)', ICONS.close);
    theme2.addEventListener('click', function () { tbtn.click(); });
    counter = document.createElement('span'); counter.className = 'present-count';
    prev.addEventListener('click', function () { show(cur - 1); });
    next.addEventListener('click', function () { show(cur + 1); });
    close.addEventListener('click', exit);
    [prev, counter, next, theme2, close].forEach(function (x) { bar.appendChild(x); });
    document.body.appendChild(progress); document.body.appendChild(bar);

    document.addEventListener('keydown', function (e) {
      if (e.altKey || e.ctrlKey || e.metaKey) return;
      var tag = (e.target && e.target.tagName) || '';
      if (/INPUT|TEXTAREA|SELECT/.test(tag)) return;
      if (!on) { if (e.key === 'p' || e.key === 'P') { e.preventDefault(); enter(); } return; }
      var k = e.key;
      if (k === 'ArrowRight' || k === 'PageDown' || k === ' ' || k === 'Enter') { e.preventDefault(); show(cur + 1); }
      else if (k === 'ArrowLeft' || k === 'PageUp' || k === 'Backspace') { e.preventDefault(); show(cur - 1); }
      else if (k === 'Home') { e.preventDefault(); show(0); }
      else if (k === 'End') { e.preventDefault(); show(slides.length - 1); }
      else if (k === 'Escape' || k === 'p' || k === 'P') { e.preventDefault(); exit(); }
      else if (k === 'f' || k === 'F') {
        e.preventDefault();
        if (document.fullscreenElement) document.exitFullscreen(); else if (root.requestFullscreen) root.requestFullscreen().catch(function () {});
      }
    });
    // in-slide links to other sections jump to that slide
    document.addEventListener('click', function (e) {
      if (!on) return;
      var a = e.target.closest && e.target.closest('a[href^="#"]');
      if (!a) return;
      var t = document.querySelector(a.getAttribute('href'));
      var idx = t ? slides.findIndex(function (s) { return s === t || s.contains(t); }) : -1;
      if (idx >= 0) { e.preventDefault(); show(idx); }
    });
    addEventListener('resize', function () { if (on) fit(); });
    // fonts change heights after load; refit once they are ready
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { if (on) fit(); });

    var m = /[?&]present(?:=(\d+))?/.exec(location.search);
    if (m) enter(m[1] ? parseInt(m[1], 10) - 1 : 0);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
