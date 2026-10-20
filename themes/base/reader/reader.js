// The HTML book's reader. CSS multi-column layout makes the pages; this
// script never measures text. It sizes the stage, moves the column strip one
// screen at a time, handles gestures and keys, and remembers the place.
(() => {
  const $ = (s) => document.querySelector(s);
  const root = document.documentElement, body = document.body;
  const stage = $('#stage'), book = $('#book');
  const S = window.BOOK.strings;
  const KEY = 'book:' + new URL('./', location).pathname;
  const saved = JSON.parse(localStorage.getItem(KEY) || '{}');
  const SIZES = [15, 16, 17, 18, 19, 20, 22, 24, 26, 28];

  let fontIdx = saved.font ?? (innerWidth < 500 ? 3 : 4);
  let mode = saved.mode || 'light';
  let W = 0, colStep = 0, perScreen = 1, M = 0, screens = 1, cur = 0;
  let blocks = [], anchor = saved.anchor || null, folioStart = 0, noFolio = new Set();

  const save = () => localStorage.setItem(KEY, JSON.stringify({ font: fontIdx, mode, anchor }));
  const emit = (name, detail) => document.dispatchEvent(new CustomEvent(name, { detail }));

  // ---------- geometry ----------
  // A screen is always a whole number of columns: with side padding M and a
  // column gap of 2M, one column plus one gap is exactly the stage width (one
  // page), or two columns plus two gaps are (a spread).
  function layout() {
    const vw = innerWidth, vh = innerHeight;
    const spread = vw >= 900 && vw / vh >= 1.15;
    let sw, sh;
    if (spread) { sh = vh - 56; sw = Math.min(vw - 56, Math.round(sh * 1.42)); }
    else if (vw >= 680) { sh = vh - 48; sw = Math.min(vw - 48, Math.round(sh * 0.74)); }
    else { sh = vh; sw = vw; }
    sw -= sw % 2;
    const sx = Math.round((vw - sw) / 2), sy = Math.round((vh - sh) / 2);
    M = Math.round(Math.max(20, Math.min(spread ? 64 : 56, sw * (spread ? 0.045 : 0.07))));
    const padY = Math.round(Math.max(34, Math.min(72, sh * 0.065)));
    perScreen = spread ? 2 : 1;
    const col = spread ? sw / 2 - 2 * M : sw - 2 * M;
    W = sw; colStep = col + 2 * M;
    body.classList.toggle('spread', spread);
    const set = (k, v) => root.style.setProperty(k, v + 'px');
    set('--stage-x', sx); set('--stage-y', sy); set('--stage-w', sw); set('--stage-h', sh);
    set('--m', M); set('--pad-y', padY); set('--col', col); set('--gap', 2 * M);
    root.style.setProperty('--reader-size', SIZES[fontIdx] + 'px');

    // Rectos. Multi-column layout cannot start a block on a given side, so in
    // a spread a blank page goes before any recto that lands on a left page.
    // The first blank puts the cover on a right-hand page, as in print.
    book.querySelectorAll('.blank').forEach((b) => b.remove());
    if (spread) {
      const first = book.firstElementChild;
      if (first) first.before(blank());
      // what must land on the right is the chapter's heading: an illustration
      // that opens the chapter then faces it from the left
      for (const el of book.querySelectorAll('.recto')) {
        const heading = el.querySelector(':scope > .unit > h1, :scope > .unit > h2') || el;
        if (colOf(heading) % 2 === 0) el.before(blank());
      }
    }

    blocks = [...book.querySelectorAll('.fullpage, .titlepage, .chapter > *')];
    screens = screenOf($('#end')) + 1;
    $('#scrub').max = screens - 1;
    const firstChapter = book.querySelector('.chapter');
    folioStart = firstChapter ? colOf(firstChapter) : 0;
    noFolio = new Set([...book.querySelectorAll('.fullpage, .titlepage, .blank')].map(colOf));
    emit('reader:layout', { pages: screens });
  }
  function blank() { const b = document.createElement('div'); b.className = 'blank'; return b; }

  // column index of an element's first fragment: the one measurement made,
  // and it reads a layout the browser already did
  function colOf(el) {
    const x = el.getBoundingClientRect().left - book.getBoundingClientRect().left;
    return Math.max(0, Math.floor((x - M + 2) / colStep));
  }
  const screenOf = (el) => Math.floor(colOf(el) / perScreen);

  // ---------- place ----------
  // The place is a block and how many screens into it, not a page number, so
  // it survives a resize or a font change.
  // The first block visible on this screen: one running in from the previous
  // screen if there is one, else the first block that starts here.
  function captureAnchor() {
    let lo = 0, hi = blocks.length;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (screenOf(blocks[mid]) < cur) lo = mid + 1; else hi = mid;
    }
    const prev = blocks[lo - 1];
    if (prev && lastScreenOf(prev) >= cur) anchor = { i: lo - 1, d: cur - screenOf(prev) };
    else anchor = blocks[lo] ? { i: lo, d: 0 } : null;
    save();
  }
  function lastScreenOf(el) {
    const rects = el.getClientRects();
    if (!rects.length) return screenOf(el);
    const x = rects[rects.length - 1].left - book.getBoundingClientRect().left;
    return Math.floor(Math.max(0, Math.floor((x - M + 2) / colStep)) / perScreen);
  }
  function restoreAnchor() {
    if (!anchor || !blocks[anchor.i]) return go(0, false);
    go(screenOf(blocks[anchor.i]) + (anchor.d || 0), false);
  }

  // ---------- turning ----------
  function place(offset = 0, animate = true) {
    book.classList.toggle('animate', animate);
    book.style.transform = `translateX(${-cur * W + offset}px)`;
  }
  function go(n, animate = true) {
    cur = Math.max(0, Math.min(screens - 1, n));
    place(0, animate);
    paint();
  }
  const turn = (n) => { go(n); captureAnchor(); };
  const next = () => turn(cur + 1);
  const prev = () => turn(cur - 1);
  const goTo = (el, animate = false) => { go(screenOf(el), animate); captureAnchor(); };

  const chapters = (window.BOOK.toc || []).map((t) => ({ ...t, el: document.getElementById(t.id) }));
  let lastChapter;
  function paint() {
    const c = cur * perScreen;
    $('#folio-l').textContent = folio(c);
    $('#folio-r').textContent = folio(c + 1);
    $('#scrub').value = cur;
    $('#foot-page').textContent = `${cur + 1} / ${screens}`;
    let here = null;
    for (const ch of chapters) if (ch.el && screenOf(ch.el.closest('.chapter') || ch.el) <= cur) here = ch;
    $('#foot-chapter').textContent = here ? here.title : '';
    document.querySelectorAll('#toc-list a').forEach((a) => a.classList.toggle('here', !!here && a.dataset.id === here.id));
    lastChapter = here ? here.title : '';
    emit('reader:page', { page: cur, pages: screens, chapter: lastChapter });
  }
  function folio(col) {
    return col >= folioStart && col < screens * perScreen && !noFolio.has(col) ? String(col - folioStart + 1) : '';
  }

  // ---------- input ----------
  // a native image drag fires pointercancel and swallows the swipe
  stage.addEventListener('dragstart', (e) => e.preventDefault());
  let down = null;
  stage.addEventListener('pointerdown', (e) => {
    if (e.button !== 0) return;
    // a table or listing that scrolls sideways keeps its own horizontal drag
    const scroller = e.target.closest('table, pre');
    if (scroller && scroller.scrollWidth > scroller.clientWidth) return;
    down = { x: e.clientX, y: e.clientY, t: performance.now(), drag: false, id: e.pointerId };
  });
  stage.addEventListener('pointermove', (e) => {
    if (!down || e.pointerId !== down.id) return;
    const dx = e.clientX - down.x, dy = e.clientY - down.y;
    if (!down.drag && Math.abs(dx) > 10 && Math.abs(dx) > Math.abs(dy) * 1.2) {
      down.drag = true; stage.setPointerCapture(e.pointerId);
    }
    if (down.drag) {
      const edge = (cur === 0 && dx > 0) || (cur === screens - 1 && dx < 0);
      place(edge ? dx * 0.25 : dx, false);
    }
  });
  stage.addEventListener('pointerup', (e) => {
    if (!down || e.pointerId !== down.id) return;
    const dx = e.clientX - down.x, dt = performance.now() - down.t;
    const d = down; down = null;
    if (d.drag) {
      const fast = Math.abs(dx) / dt > 0.45 && Math.abs(dx) > 24;
      if (dx < -W * 0.14 || (fast && dx < 0)) next();
      else if (dx > W * 0.14 || (fast && dx > 0)) prev();
      else place(0, true);
      return;
    }
    if (Math.abs(dx) > 10 || Math.abs(e.clientY - d.y) > 10) return;
    if (e.target.closest('a[href]')) return;  // the click handler follows links
    if (closePanels()) return;
    const x = (e.clientX - stage.getBoundingClientRect().left) / W;
    if (x < 0.3) { hideChrome(); prev(); }
    else if (x > 0.7) { hideChrome(); next(); }
    else body.classList.toggle('chrome');
  });
  stage.addEventListener('pointercancel', () => { if (down?.drag) place(0, true); down = null; });

  // in-book links (references, notes, back-links) turn to their target
  book.addEventListener('click', (e) => {
    const a = e.target.closest('a[href^="#"]');
    if (!a) return;
    const target = document.getElementById(decodeURIComponent(a.getAttribute('href').slice(1)));
    if (!target) return;
    e.preventDefault();
    goTo(target);
  });

  document.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT') return;
    if (['ArrowRight', 'PageDown'].includes(e.key) || (e.key === ' ' && !e.shiftKey)) { e.preventDefault(); next(); }
    else if (['ArrowLeft', 'PageUp'].includes(e.key) || (e.key === ' ' && e.shiftKey)) { e.preventDefault(); prev(); }
    else if (e.key === 'Home') turn(0);
    else if (e.key === 'End') turn(screens - 1);
    else if (e.key === 'Escape') { closePanels(); hideChrome(); }
  });

  let wheelAcc = 0, wheelLock = 0;
  addEventListener('wheel', (e) => {
    if (e.target.closest('.panel')) return;
    e.preventDefault();
    const now = performance.now();
    if (now < wheelLock) return;
    wheelAcc += Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY;
    if (Math.abs(wheelAcc) > 40) { wheelAcc > 0 ? next() : prev(); wheelAcc = 0; wheelLock = now + 380; }
  }, { passive: false });

  $('#scrub').addEventListener('input', (e) => go(+e.target.value, false));
  $('#scrub').addEventListener('change', captureAnchor);

  // ---------- chrome and panels ----------
  const hideChrome = () => body.classList.remove('chrome');
  function closePanels() {
    const open = document.querySelectorAll('.panel[data-open]');
    open.forEach((p) => p.removeAttribute('data-open'));
    return open.length > 0;
  }
  const openPanel = (id) => { closePanels(); $(id).setAttribute('data-open', ''); };
  $('#btn-toc').onclick = () => openPanel('#toc');
  $('#btn-settings').onclick = () => openPanel('#settings');

  const esc = (t) => t.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
  $('#toc-list').innerHTML = chapters
    .map((c) => `<li><a href="#${esc(c.id)}" data-id="${esc(c.id)}">${esc(c.title)}</a></li>`).join('');
  $('#toc-list').addEventListener('click', (e) => {
    const a = e.target.closest('a'); if (!a) return;
    e.preventDefault();
    const el = document.getElementById(a.dataset.id);
    goTo(el.closest('.chapter') || el);
    closePanels(); hideChrome();
  });

  function relayout() { layout(); restoreAnchor(); }
  document.querySelectorAll('[data-font]').forEach((b) => b.onclick = () => {
    fontIdx = Math.max(0, Math.min(SIZES.length - 1, fontIdx + +b.dataset.font));
    save(); relayout();
  });
  function applyMode() {
    root.dataset.mode = mode;
    document.querySelectorAll('button[data-mode]').forEach((b) => b.classList.toggle('on', b.dataset.mode === mode));
    document.querySelector('meta[name=theme-color]').content = getComputedStyle(root).getPropertyValue('--desk').trim();
  }
  document.querySelectorAll('button[data-mode]').forEach((b) => b.onclick = () => { mode = b.dataset.mode; save(); applyMode(); });

  let resizeT;
  addEventListener('resize', () => { clearTimeout(resizeT); resizeT = setTimeout(relayout, 120); });

  function toast(html, ms = 4000) {
    const t = $('#toast'); t.innerHTML = html; t.classList.add('show');
    clearTimeout(t._h); if (ms) t._h = setTimeout(() => t.classList.remove('show'), ms);
    return t;
  }

  window.scriptoriumReader = {
    go: (n) => turn(n), goTo: (el) => goTo(el), relayout,
    get page() { return cur; }, get pages() { return screens; },
    toast, captureAnchor,
  };

  // ---------- start ----------
  applyMode();
  document.fonts.ready.then(() => {
    layout();
    const hash = decodeURIComponent(location.hash.slice(1));
    const target = hash && document.getElementById(hash);
    if (target) goTo(target.closest('.chapter') && target.matches('h1, h2') ? target.closest('.chapter') : target);
    else restoreAnchor();
    addEventListener('load', relayout);
    emit('reader:ready', { pages: screens });
  });
})();
