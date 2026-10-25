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

  document.addEventListener("keydown", function (e) {
    if (e.key !== "/" || !input || e.target.closest("input, textarea, [contenteditable]")) return;
    e.preventDefault();
    input.focus();
  });
})();
