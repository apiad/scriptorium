// The docs page script: the drawer on a phone, the outline entry of the
// section in view, and the / key to search.
(function () {
  "use strict";
  const body = document.body;
  const menu = document.querySelector(".topbar .menu");
  const input = document.querySelector(".topbar .search input");

  if (menu) {
    menu.addEventListener("click", function () {
      const open = body.classList.toggle("drawer-open");
      menu.setAttribute("aria-expanded", String(open));
    });
    document.querySelectorAll(".sidebar a").forEach(function (a) {
      a.addEventListener("click", function () { body.classList.remove("drawer-open"); });
    });
  }

  const links = new Map();
  document.querySelectorAll(".outline a").forEach(function (a) {
    links.set(decodeURIComponent(a.getAttribute("href").slice(1)), a);
  });
  if (links.size && "IntersectionObserver" in window) {
    const seen = new Set();
    const observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { e.isIntersecting ? seen.add(e.target.id) : seen.delete(e.target.id); });
      let current = null;
      for (const id of links.keys()) {
        if (seen.has(id)) { current = id; break; }
      }
      if (!current) return;
      links.forEach(function (a, id) { a.classList.toggle("active", id === current); });
    }, { rootMargin: "0px 0px -60% 0px" });
    links.forEach(function (_, id) {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    });
  }

  // Search: the index is fetched on the box's first focus. Every query word
  // must be a prefix of a word in the entry; a word in the title scores 2,
  // one only in the text scores 1.
  const results = document.querySelector(".topbar .search-results");
  let index = null;
  const words = function (s) { return s.toLowerCase().split(/[^\p{L}\p{N}]+/u).filter(Boolean); };

  function search() {
    const query = words(input.value);
    results.textContent = "";
    if (!query.length || !index) { results.hidden = true; return; }
    const hits = [];
    for (const entry of index) {
      let score = 0;
      for (const q of query) {
        if (entry.titleWords.some(function (w) { return w.startsWith(q); })) score += 2;
        else if (entry.textWords.some(function (w) { return w.startsWith(q); })) score += 1;
        else { score = 0; break; }
      }
      if (score) hits.push([score, entry]);
    }
    hits.sort(function (a, b) { return b[0] - a[0]; });
    if (!hits.length) {
      const none = document.createElement("p");
      none.textContent = "No results";
      results.appendChild(none);
    }
    hits.slice(0, 10).forEach(function (hit) {
      const a = document.createElement("a");
      a.href = hit[1].url;
      a.textContent = hit[1].title;
      const small = document.createElement("small");
      small.textContent = hit[1].page;
      a.appendChild(small);
      results.appendChild(a);
    });
    results.hidden = false;
  }

  if (input && results) {
    input.addEventListener("focus", function () {
      if (index) return;
      fetch("search.json").then(function (r) { return r.json(); }).then(function (entries) {
        index = entries.map(function (e) {
          return Object.assign({ titleWords: words(e.title), textWords: words(e.text) }, e);
        });
        search();
      });
    }, { once: true });
    input.addEventListener("input", search);
    input.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { results.hidden = true; input.blur(); }
      if (e.key === "Enter") {
        const first = results.querySelector("a");
        if (first) location.href = first.href;
      }
    });
    document.addEventListener("click", function (e) {
      if (!e.target.closest(".topbar .search")) results.hidden = true;
    });
  }

  document.addEventListener("keydown", function (e) {
    if (e.key !== "/" || !input || e.target.closest("input, textarea, [contenteditable]")) return;
    e.preventDefault();
    input.focus();
  });
})();
