// The HTML book's reader. CSS multi-column layout makes the pages; this
// script never measures text. It loads one chapter at a time into the column
// strip, moves the strip one screen at a time, handles gestures and keys,
// counts the other chapters' pages out of sight, and remembers the place.
(() => {
  const $ = (s) => document.querySelector(s);
  const root = document.documentElement, body = document.body;
  const stage = $('#stage'), book = $('#book'), measure = $('#measure .book');
  const B = window.BOOK, S = B.strings, CH = B.chapters;
  const KEY = 'book:' + new URL('./', location).pathname;
  const saved = JSON.parse(localStorage.getItem(KEY) || '{}');
  const SIZES = [15, 16, 17, 18, 19, 20, 22, 24, 26, 28];

  let fontIdx = saved.font ?? (innerWidth < 500 ? 3 : 4);
  let mode = saved.mode || 'light';
  let W = 0, colStep = 0, perScreen = 1, M = 0;
  let ch = -1, cur = 0, screens = 1;         // the loaded chapter, the screen in it, its screens
  let blocks = [], noFolio = new Set(), anchor = saved.anchor || null;
  let counts = [], geomKey = '';              // screens per chapter for this geometry, when known

  const save = () => localStorage.setItem(KEY, JSON.stringify({ font: fontIdx, mode, anchor }));
  const emit = (name, detail) => document.dispatchEvent(new CustomEvent(name, { detail }));
  const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);

  // ---------- chapters ----------
  const texts = new Map();
  function fetchChapter(i) {
    if (!texts.has(i)) texts.set(i, fetch(CH[i].file).then((r) => {
      if (!r.ok) throw new Error(`${CH[i].file}: ${r.status}`);
      return r.text();
    }).catch((e) => { texts.delete(i); throw e; }));
    return texts.get(i);
  }

  // ---------- geometry ----------
  // A screen is always a whole number of columns: with side padding M and a
  // column gap of 2M, one column plus one gap is exactly the stage width (one
  // page), or two columns plus two gaps are (a spread).
  function geometry() {
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
    const key = [sw, sh, perScreen, fontIdx, B.edition].join(':');
    if (key !== geomKey) {
      geomKey = key;
      const c = JSON.parse(localStorage.getItem(KEY + ':counts') || '{}');
      counts = c.key === key ? c.counts : CH.map(() => null);
    }
  }

  // column index of an element's first fragment inside its strip: the one
  // measurement made, and it reads a layout the browser already did
  function colOf(el, strip = book) {
    const x = el.getBoundingClientRect().left - strip.getBoundingClientRect().left;
    return Math.max(0, Math.floor((x - M + 2) / colStep));
  }
  const screenOf = (el, strip = book) => Math.floor(colOf(el, strip) / perScreen);
  function blank() { const b = document.createElement('div'); b.className = 'blank'; return b; }

  // Put chapter i's HTML into a strip and lay it out; returns its screens.
  // Rectos: multi-column layout cannot start a block on a given side, so in a
  // spread a blank page goes first when the chapter's heading would land on a
  // left page; an opening illustration then faces the heading. The front
  // starts with a blank too, so the cover is a right-hand page.
  async function fill(strip, html) {
    strip.innerHTML = html;
    await document.fonts.ready;  // a chapter's text may pull in a face not loaded yet
    if (perScreen === 2) {
      const sec = strip.firstElementChild;
      const heading = sec && sec.querySelector(':scope > .unit > h1, :scope > .unit > h2');
      if (sec && sec.classList.contains('front')) sec.before(blank());
      else if (heading && sec.classList.contains('recto') && colOf(heading, strip) % 2 === 0) sec.before(blank());
    }
    // up to the last fragment of the last block: a marker after a full page
    // would sit in a column of its own and add an empty page
    const sec = strip.querySelector('section.chapter');
    const last = (sec && sec.lastElementChild) || sec || strip;
    return lastScreenOf(last, strip) + 1;
  }

  async function load(i) {
    const html = await fetchChapter(i);
    ch = i;
    screens = await fill(book, html);
    blocks = [...book.querySelectorAll('.chapter > *')];
    noFolio = new Set([...book.querySelectorAll('.fullpage, .titlepage, .blank')].map((el) => colOf(el)));
    setCount(i, screens);
    emit('reader:layout', { chapter: ch, pages: screens });
    fetchChapter(Math.min(i + 1, CH.length - 1)).catch(() => {});
  }

  // ---------- pages across chapters ----------
  function setCount(i, n) {
    if (counts[i] === n) return;
    counts[i] = n;
    localStorage.setItem(KEY + ':counts', JSON.stringify({ key: geomKey, counts }));
  }
  // chapters not counted yet are estimated from their length
  function countOf(i) {
    if (counts[i] != null) return counts[i];
    let n = 0, c = 0;
    counts.forEach((k, j) => { if (k != null) { n += k; c += CH[j].chars; } });
    return Math.max(1, Math.round(CH[i].chars * (c ? n / c : 1 / 1800)));
  }
  const exact = () => counts.every((k) => k != null);
  const before = (i) => { let n = 0; for (let j = 0; j < i; j++) n += countOf(j); return n; };
  const total = () => before(CH.length);
  function locate(page) {
    let i = 0;
    while (i < CH.length - 1 && page >= countOf(i)) { page -= countOf(i); i++; }
    return [i, Math.min(page, countOf(i) - 1)];
  }

  // Count every chapter's pages in the hidden strip, one per idle moment.
  let counting = false;
  const idle = window.requestIdleCallback || ((f) => setTimeout(f, 50));
  function countRest() {
    if (counting) return;
    counting = true;
    const step = async () => {
      const i = counts.findIndex((k) => k == null);
      if (i < 0) { counting = false; measure.innerHTML = ''; paint(); return; }
      try { setCount(i, await fill(measure, await fetchChapter(i))); } catch { counts[i] = countOf(i); }
      paint();
      idle(step);
    };
    idle(step);
  }

  // ---------- place ----------
  // The place is a chapter, a block in it and how many screens into that
  // block, so it survives a resize or a font change. The block is the first
  // one visible: one running in from the previous screen, else the first
  // that starts on this one.
  function captureAnchor() {
    let lo = 0, hi = blocks.length;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (screenOf(blocks[mid]) < cur) lo = mid + 1; else hi = mid;
    }
    const prev = blocks[lo - 1];
    if (prev && lastScreenOf(prev) >= cur) anchor = { c: ch, i: lo - 1, d: cur - screenOf(prev) };
    else anchor = { c: ch, i: lo, d: 0 };
    save();
  }
  function lastScreenOf(el, strip = book) {
    const rects = el.getClientRects();
    if (!rects.length) return screenOf(el, strip);
    const x = rects[rects.length - 1].left - strip.getBoundingClientRect().left;
    return Math.floor(Math.max(0, Math.floor((x - M + 2) / colStep)) / perScreen);
  }
  async function restoreAnchor() {
    const a = anchor && anchor.c != null && anchor.c < CH.length ? anchor : { c: 0, i: 0, d: 0 };
    await load(a.c);
    const el = blocks[a.i];
    go(el ? screenOf(el) + (a.d || 0) : 0, false);
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
  let busy = Promise.resolve();
  // `where`: a screen number, 'last', or an element id in that chapter
  function show(i, where = 0, animate = false) {
    busy = busy.then(async () => {
      if (i !== ch) await load(i);
      let n = where;
      if (where === 'last') n = screens - 1;
      else if (typeof where === 'string') {
        const el = document.getElementById(where);
        n = el ? screenOf(el.matches('h1, h2') && el.closest('.chapter') ? el.closest('.chapter') : el) : 0;
      }
      go(n, animate && i === ch);
      captureAnchor();
    }).catch((e) => console.warn(e));
    return busy;
  }
  function next() {
    if (cur < screens - 1) { go(cur + 1); captureAnchor(); }
    else if (ch < CH.length - 1) show(ch + 1, 0);
    else place(0, true);
  }
  function prev() {
    if (cur > 0) { go(cur - 1); captureAnchor(); }
    else if (ch > 0) show(ch - 1, 'last');
    else place(0, true);
  }
  const goToId = (id) => (id in B.ids ? show(B.ids[id], id) : Promise.resolve());

  let lastChapter = '';
  function paint() {
    const page = before(ch) + cur, all = total();
    const approx = exact() ? '' : '~';
    $('#folio-l').textContent = folio(0);
    $('#folio-r').textContent = folio(1);
    $('#scrub').max = all - 1;
    $('#scrub').value = page;
    $('#foot-page').textContent = `${page + 1} / ${approx}${all}`;
    let here = null;
    for (const t of B.toc) if (t.chapter <= ch) here = t;
    $('#foot-chapter').textContent = here ? here.title : '';
    document.querySelectorAll('#toc-list a').forEach((a) => a.classList.toggle('here', !!here && a.dataset.id === here.id));
    lastChapter = here ? here.title : '';
    emit('reader:page', { page, pages: all, chapter: lastChapter });
  }
  // folios count pages from the first chapter after the front; full pages,
  // the title page and blanks carry none
  function folio(side) {
    const col = cur * perScreen + side;
    if (ch < 1 || noFolio.has(col) || col >= screens * perScreen) return '';
    return String((before(ch) - countOf(0)) * perScreen + col + 1);
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
      const edge = (cur === 0 && dx > 0) || (cur === screens - 1 && dx < 0);
      const far = Math.abs(dx) > W * (edge ? 0.035 : 0.14);  // the edge drag is damped
      if ((far || fast) && dx < 0) next();
      else if ((far || fast) && dx > 0) prev();
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

  // in-book links (references, notes, back-links) turn to their target,
  // loading its chapter first when it is another one
  book.addEventListener('click', (e) => {
    const a = e.target.closest('a[href^="#"]');
    if (!a) return;
    const id = decodeURIComponent(a.getAttribute('href').slice(1));
    if (!(id in B.ids)) return;
    e.preventDefault();
    goToId(id);
  });

  document.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT') return;
    if (['ArrowRight', 'PageDown'].includes(e.key) || (e.key === ' ' && !e.shiftKey)) { e.preventDefault(); next(); }
    else if (['ArrowLeft', 'PageUp'].includes(e.key) || (e.key === ' ' && e.shiftKey)) { e.preventDefault(); prev(); }
    else if (e.key === 'Home') show(0, 0);
    else if (e.key === 'End') show(CH.length - 1, 'last');
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

  $('#scrub').addEventListener('input', (e) => {
    $('#foot-page').textContent = `${+e.target.value + 1} / ${exact() ? '' : '~'}${total()}`;
  });
  $('#scrub').addEventListener('change', (e) => { const [i, n] = locate(+e.target.value); show(i, n); });

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

  $('#toc-list').innerHTML = B.toc
    .map((c) => `<li><a href="#${esc(c.id)}" data-id="${esc(c.id)}">${esc(c.title)}</a></li>`).join('');
  $('#toc-list').addEventListener('click', (e) => {
    const a = e.target.closest('a'); if (!a) return;
    e.preventDefault();
    const t = B.toc.find((x) => x.id === a.dataset.id);
    show(t.chapter, 0);
    closePanels(); hideChrome();
  });

  // a resize or a font change lays out only the open chapter again; the
  // other chapters are recounted out of sight
  async function relayout() {
    if (ch >= 0) captureAnchor();
    geometry();
    texts.forEach((p, i) => { if (i !== ch && i !== ch + 1) texts.delete(i); });
    await restoreAnchor();
    countRest();
  }
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
    go: (page) => { const [i, n] = locate(page); return show(i, n); },
    goTo: (el) => { go(screenOf(el), false); captureAnchor(); },
    goToId, relayout, toast, captureAnchor,
    get page() { return before(ch) + cur; }, get pages() { return total(); },
    get chapter() { return ch; }, get chapterPages() { return screens; },
    get counted() { return exact(); },
  };

  // ---------- install, offline, new editions ----------
  let deferred = null;
  addEventListener('beforeinstallprompt', (e) => { e.preventDefault(); deferred = e; $('#btn-install').hidden = false; });
  $('#btn-install').onclick = async () => {
    if (!deferred) return;
    deferred.prompt(); await deferred.userChoice;
    deferred = null; $('#btn-install').hidden = true;
  };
  const standalone = matchMedia('(display-mode: standalone)').matches || navigator.standalone;
  if (/iphone|ipad|ipod/i.test(navigator.userAgent) && !standalone) $('#install-hint').hidden = false;

  if ('serviceWorker' in navigator && location.protocol !== 'file:') {
    const prefix = 'book:' + new URL('./', location).pathname + ':';
    const markOffline = () => { $('#foot-offline').textContent = S.offline; };
    // the first worker only takes control; every later change is a new edition
    let controlled = !!navigator.serviceWorker.controller;
    navigator.serviceWorker.register('sw.js', { updateViaCache: 'none' }).then((reg) => {
      document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') reg.update(); });
    }).catch(() => {});
    navigator.serviceWorker.addEventListener('message', (e) => { if (e.data?.type === 'cached') markOffline(); });
    navigator.serviceWorker.ready.then(async () => {
      if ((await caches.keys()).some((k) => k.startsWith(prefix))) markOffline();
    });
    navigator.serviceWorker.addEventListener('controllerchange', () => {
      if (!controlled) { controlled = true; return; }
      const t = toast(`${esc(S.update)} <button>${esc(S.update_button)}</button>`, 0);
      t.querySelector('button').onclick = () => { captureAnchor(); location.reload(); };
    });
  }

  // ---------- start ----------
  applyMode();
  document.fonts.ready.then(async () => {
    geometry();
    const hash = decodeURIComponent(location.hash.slice(1));
    if (hash && hash in B.ids) await show(B.ids[hash], hash);
    else await restoreAnchor();
    paint();
    emit('reader:ready', { pages: total() });
    setTimeout(countRest, 300);
  });
})();
