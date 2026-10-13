/* Shared site behavior: theme switch (system / light / dark) and presentation mode.
   Loaded in <head> without defer so the saved theme applies before first paint. */
(function () {
  var KEY = 'ans-theme';
  var SELF = (document.currentScript && document.currentScript.src) || '';
  var root = document.documentElement;

  /* ---------- language (ko / en) ---------- */
  var LKEY = 'ans-lang', EN = (root.lang || '').toLowerCase().indexOf('en') === 0;
  var ROOT = (function () { try { return new URL('../', SELF || location.href).href; } catch (e) { return '/'; } })();
  function counterpart() {            // same page in the other language
    var here = location.href.split('#')[0].split('?')[0];
    var rel = here.indexOf(ROOT) === 0 ? here.slice(ROOT.length) : '';
    if (EN) rel = rel.replace(/^en\//, '');
    return ROOT + (EN ? '' : 'en/') + rel + location.search + location.hash;
  }
  (function autoLang() {               // first visit: follow the browser language; an explicit choice wins
    var pref = null; try { pref = localStorage.getItem(LKEY); } catch (e) {}
    var wantEN;
    if (pref === 'ko' || pref === 'en') wantEN = pref === 'en';
    else {
      var nl = ((navigator.languages && navigator.languages[0]) || navigator.language || 'ko').toLowerCase();
      wantEN = nl.indexOf('ko') !== 0;
    }
    if (wantEN === EN || !/^https?:/.test(location.protocol)) return;
    // switch only if the other-language page exists, so a missing translation never ends in a 404
    var target = counterpart();
    try {
      fetch(target.split('#')[0].split('?')[0], { method: 'HEAD', cache: 'no-cache' })
        .then(function (r) { if (r.ok) location.replace(target); }).catch(function () {});
    } catch (e) {}
  })();
  var T = EN ? {
    theme: { system: 'Theme: system', light: 'Theme: light', dark: 'Theme: dark' },
    search: 'Search services', menu: 'Service menu', site: 'Site menu', open: 'Open menu (/)', empty: 'No matching services.',
    pricing: 'Pricing', priceThis: 'Pricing for this service', priceAll: 'Pricing by service',
    present: 'Presentation mode (P)', ctrl: 'Presentation controls', first: 'First slide (Home)', last: 'Last slide (End)',
    prev: 'Previous slide', next: 'Next slide', close: 'Exit presentation (Esc)', lang: '한국어로 보기', langCode: 'KO'
  } : {
    theme: { system: '테마: 시스템 설정', light: '테마: 라이트', dark: '테마: 다크' },
    search: '서비스 검색', menu: '서비스 메뉴', site: '사이트 메뉴', open: '메뉴 열기 (/)', empty: '일치하는 서비스가 없습니다.',
    pricing: '가격표', priceThis: '이 서비스의 가격표 보기', priceAll: '서비스별 가격표 보기',
    present: '발표 모드 (P)', ctrl: '발표 컨트롤', first: '처음 슬라이드 (Home)', last: '마지막 슬라이드 (End)',
    prev: '이전 슬라이드', next: '다음 슬라이드', close: '발표 종료 (Esc)', lang: 'View in English', langCode: 'EN'
  };

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
    first: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 5l-7 7 7 7M7 5v14"/></svg>',
    last: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 5l7 7-7 7M17 5v14"/></svg>',
    prev: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 5l-7 7 7 7"/></svg>',
    next: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 5l7 7-7 7"/></svg>',
    menu: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"/></svg>',
    lang: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 5h9M7.5 3v2M5 5c.9 3.2 3 5.6 6 7M10 5c-.9 3.2-3 5.6-6 7"/><path d="M13 21l4-9 4 9M14.3 18h5.4"/></svg>',
    price: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v18M16.5 7.5c-.6-1.5-2.3-2.5-4.5-2.5-2.5 0-4.5 1.3-4.5 3.3 0 4.5 9 2.7 9 7.2 0 2-2 3.5-4.5 3.5-2.4 0-4.2-1.1-4.8-2.8"/></svg>',
    close: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>'
  };
  var LABEL = T.theme;
  var ORDER = ['system', 'light', 'dark'];

  function esc(t) { return String(t).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
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
  }
  // the slide whose section is on screen; must run BEFORE the page switches to slide mode
  function currentSlide() {
    var line = Math.min(innerHeight * 0.35, 260), best = 0;
    slides.forEach(function (sl, k) { if (sl.getBoundingClientRect().top <= line) best = k; });
    return best;
  }
  function enter(start) {
    var at = typeof start === 'number' ? start : currentSlide();
    if (on) { show(at); return; }
    on = true;
    root.classList.add('presenting');
    bar.hidden = false;
    show(at);                                       // start from the section the viewer is looking at
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
    if (/[?&]present/.test(location.search)) { try { history.replaceState(null, '', location.pathname + location.hash); } catch (e) {} }
    if (s) s.scrollIntoView({ block: 'start' });
  }
  /* ---------- site menu (drawer) ---------- */
  var MENU = [
    ['Application Networking', [['elastic-load-balancing', 'Elastic Load Balancing'], ['vpc-lattice', 'VPC Lattice'], ['api-gateway', 'API Gateway']]],
    ['Edge Networking', [['cloudfront', 'CloudFront'], ['global-accelerator', 'Global Accelerator']]],
    ['Hybrid Networking', [['transit-gateway', 'Transit Gateway'], ['cloud-wan', 'Cloud WAN'], ['privatelink', 'PrivateLink'], ['direct-connect', 'Direct Connect'], ['interconnect', 'Interconnect'], ['site-to-site-vpn', 'Site-to-Site VPN'], ['client-vpn', 'Client VPN']]],
    ['Foundation', [['vpc', 'Amazon VPC'], ['route-53', 'Route 53']]],
    ['Network Security', [['network-firewall', 'Network Firewall'], ['waf', 'AWS WAF'], ['shield', 'AWS Shield'], ['firewall-manager', 'Firewall Manager']]],
    ['Network Observability', [['vpc-flow-logs', 'VPC Flow Logs'], ['reachability-analyzer', 'Reachability Analyzer'], ['network-manager', 'Network Manager'], ['network-flow-monitor', 'Network Flow Monitor']]]
  ];
  var PRICE_TAB = { 'elastic-load-balancing': 'elb', 'vpc-lattice': 'lattice', 'api-gateway': 'apigw', 'cloudfront': 'cloudfront', 'global-accelerator': 'ga',
    'transit-gateway': 'tgw', 'cloud-wan': 'cloudwan', 'privatelink': 'privatelink', 'direct-connect': 'dx', 'interconnect': 'interconnect',
    'site-to-site-vpn': 's2svpn', 'client-vpn': 'clientvpn', 'vpc': 'vpc', 'route-53': 'route53', 'network-firewall': 'nfw', 'waf': 'waf',
    'shield': 'shield', 'firewall-manager': 'fms', 'vpc-flow-logs': 'flowlogs', 'reachability-analyzer': 'reachability',
    'network-manager': 'netmgr', 'network-flow-monitor': 'nfm' };
  var drawer, scrim, menuBtn, lastFocus, search, AREA_KEY = ['app', 'edge', 'hybrid', 'fnd', 'sec', 'obs'];
  function siteRoot() {
    try { return new URL('../', SELF || location.href).href; } catch (e) { return '/'; }
  }
  function openMenu(withSearch) {
    lastFocus = document.activeElement;
    drawer.hidden = false; scrim.hidden = false;
    requestAnimationFrame(function () { root.classList.add('menu-open'); });
    menuBtn.setAttribute('aria-expanded', 'true');
    search.value = ''; filterMenu('');
    if (withSearch) search.focus(); else drawer.focus({ preventScroll: true });
  }
  function closeMenu() {
    if (!drawer || drawer.hidden) return;
    root.classList.remove('menu-open');
    menuBtn.setAttribute('aria-expanded', 'false');
    drawer.hidden = true; scrim.hidden = true;
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }
  function filterMenu(q) {
    q = (q || '').trim().toLowerCase();
    var any = false;
    drawer.querySelectorAll('.mcard').forEach(function (card) {
      var vis = 0;
      card.querySelectorAll('.mi').forEach(function (a) { var ok = !q || a.getAttribute('data-k').indexOf(q) >= 0; a.hidden = !ok; if (ok) vis++; });
      card.hidden = !vis; if (vis) any = true;
    });
    drawer.querySelector('.mempty').hidden = any;
  }
  function buildMenu(tools) {
    var base = siteRoot(), lb = base + (EN ? 'en/' : ''), here = location.href.split('#')[0].split('?')[0];
    function isCur(href) { return here === href || here === href + 'index.html'; }
    function item(slug, name) {
      var href = lb + slug + '/';
      return '<a class="mi" href="' + href + '" data-k="' + (name + ' ' + slug).toLowerCase() + '"' + (isCur(href) ? ' aria-current="page"' : '') + '>' +
        '<img src="' + base + 'assets/icons/' + slug + '.svg" width="20" height="20" alt="" aria-hidden="true"><span>' + name + '</span></a>';
    }
    var home = lb, pricing = lb + 'pricing/';
    var html =
      '<div class="mtop">' +
        '<label class="msearch"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.2-4.2"/></svg>' +
        '<input type="search" placeholder="' + T.search + '" aria-label="' + T.search + '" autocomplete="off"><kbd>/</kbd></label>' +
        '<a class="mquick" href="' + home + '"' + (isCur(home) ? ' aria-current="page"' : '') + '><img src="' + base + 'assets/icons/aws.svg" width="18" height="18" alt="" aria-hidden="true">AWS Networking Services</a>' +
        '<a class="mquick" href="' + pricing + '"' + (isCur(pricing) ? ' aria-current="page"' : '') + '><img src="' + base + 'assets/icons/pricing.svg" width="16" height="16" alt="" aria-hidden="true">' + T.pricing + '</a>' +
      '</div>' +
      '<div class="mgrid" role="navigation" aria-label="' + T.menu + '">' + [[0, 1, 3], [2], [4, 5]].map(function (col) {
        // masonry columns: cards keep their natural height, columns are balanced by item count
        return '<div class="mcol">' + col.map(function (gi) {
          var g = MENU[gi];
          return '<section class="mcard" data-area="' + AREA_KEY[gi] + '"><p class="mg">' + g[0] + '</p>' + g[1].map(function (x) { return item(x[0], x[1]); }).join('') + '</section>';
        }).join('') + '</div>';
      }).join('') + '<p class="mempty" hidden>' + T.empty + '</p></div>';
    drawer = document.createElement('div');
    drawer.className = 'drawer'; drawer.id = 'site-menu'; drawer.hidden = true; drawer.tabIndex = -1;
    drawer.setAttribute('role', 'dialog'); drawer.setAttribute('aria-label', T.site);
    drawer.innerHTML = html;
    search = drawer.querySelector('.msearch input');
    search.addEventListener('input', function () { filterMenu(search.value); });
    search.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') { var a = drawer.querySelector('.mi:not([hidden])'); if (a) { e.preventDefault(); location.href = a.href; } }
    });
    scrim = document.createElement('div'); scrim.className = 'drawer-scrim'; scrim.hidden = true;
    scrim.addEventListener('click', closeMenu);
    document.body.appendChild(scrim); document.body.appendChild(drawer);
    menuBtn = btn('menu-btn', T.open, ICONS.menu);
    menuBtn.setAttribute('aria-controls', 'site-menu'); menuBtn.setAttribute('aria-expanded', 'false');
    menuBtn.addEventListener('click', function () { drawer.hidden ? openMenu() : closeMenu(); });
    var wrap = document.querySelector('nav .wrap'), brand = wrap && wrap.querySelector('.brand');
    if (wrap) {
      var left = document.createElement('div'); left.className = 'nav-left';
      wrap.insertBefore(left, wrap.firstChild);
      left.appendChild(menuBtn); if (brand) left.appendChild(brand);
      wrap.appendChild(tools);              // theme + presentation stay at the right end of the top bar
      // PRICING: jumps to this service's tab on the price table (not shown on the price table itself)
      var slug = (here.slice(lb.length).split('/')[0] || '');
      if (slug !== 'pricing') {
        var tab = PRICE_TAB[slug], pa = document.createElement('a');
        pa.className = 'tool-btn pricing-btn'; pa.href = lb + 'pricing/' + (tab ? '#' + tab : '');
        pa.innerHTML = ICONS.price; pa.title = tab ? T.priceThis : T.priceAll; pa.setAttribute('aria-label', pa.title);
        tools.insertBefore(pa, tools.firstChild);
      }
      // language switch: same page in the other language; remembers the choice
      var lg = btn('lang-btn', T.lang, '<span>' + T.langCode + '</span>');
      lg.addEventListener('click', function () { try { localStorage.setItem(LKEY, EN ? 'ko' : 'en'); } catch (e) {} location.href = counterpart(); });
      tools.insertBefore(lg, tools.querySelector('.theme-btn'));
      if (/^https?:/.test(location.protocol)) { lg.hidden = true; fetch(counterpart().split('#')[0].split('?')[0], { method: 'HEAD', cache: 'no-cache' }).then(function (r) { lg.hidden = !r.ok; }).catch(function () {}); }
    }
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !drawer.hidden) { e.preventDefault(); closeMenu(); return; }
      var tag = (e.target && e.target.tagName) || '';
      if (/INPUT|TEXTAREA|SELECT/.test(tag) || root.classList.contains('presenting')) return;
      if ((e.key === 'k' || e.key === 'K') && (e.metaKey || e.ctrlKey)) { e.preventDefault(); drawer.hidden ? openMenu(true) : closeMenu(); }
      else if (e.key === '/' && drawer.hidden) { e.preventDefault(); openMenu(true); }
    });
    drawer.addEventListener('click', function (e) { if (e.target.closest('a')) closeMenu(); });
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
    var pbtn = btn('present-btn', T.present, ICONS.present);
    pbtn.addEventListener('click', function () { closeMenu(); enter(); });
    tools.appendChild(tbtn); tools.appendChild(pbtn);
    if (navlinks) navlinks.remove();          // top bar keeps only the menu button and the brand
    buildMenu(tools);

    // presenter control bar
    bar = document.createElement('div'); bar.className = 'present-bar'; bar.hidden = true;
    bar.setAttribute('role', 'toolbar'); bar.setAttribute('aria-label', T.ctrl);
    progress = document.createElement('i'); progress.className = 'present-progress';
    var brandEl = document.querySelector('nav .brand');
    var tag = document.createElement('div'); tag.className = 'present-title'; tag.setAttribute('aria-hidden', 'true');
    tag.innerHTML = brandEl ? brandEl.innerHTML : esc(document.title);
    document.body.appendChild(tag);
    var first = btn('', T.first, ICONS.first), last = btn('', T.last, ICONS.last);
    var prev = btn('', T.prev, ICONS.prev), next = btn('', T.next, ICONS.next);
    first.addEventListener('click', function () { show(0); });
    last.addEventListener('click', function () { show(slides.length - 1); });
    var close = btn('', T.close, ICONS.close);
    theme2.addEventListener('click', function () { tbtn.click(); });
    counter = document.createElement('span'); counter.className = 'present-count';
    prev.addEventListener('click', function () { show(cur - 1); });
    next.addEventListener('click', function () { show(cur + 1); });
    close.addEventListener('click', exit);
    [first, prev, counter, next, last, theme2, close].forEach(function (x) { bar.appendChild(x); });
    document.body.appendChild(progress); document.body.appendChild(bar);

    document.addEventListener('keydown', function (e) {
      if (e.altKey || e.ctrlKey || e.metaKey) return;
      var tag = (e.target && e.target.tagName) || '';
      if (/INPUT|TEXTAREA|SELECT/.test(tag)) return;
      if (!on) { if ((e.key === 'p' || e.key === 'P') && (!drawer || drawer.hidden)) { e.preventDefault(); enter(); } return; }
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
