"""The reader in Chromium: turning, chapters, jumping, rectos, resume, nothing spilling.

Skipped when no Chromium is found: Playwright's own download, or a system one.
"""

import os
import shutil
from pathlib import Path

import pytest

pytestmark = pytest.mark.browser
playwright = pytest.importorskip("playwright.sync_api")

PHONE = {"viewport": {"width": 390, "height": 844}, "is_mobile": True, "has_touch": True}
DESK = {"viewport": {"width": 1440, "height": 900}}
CHAPTERS = ["chap-faro", "capítulo-de-la-tormenta", "chap-regreso"]


def _chromium(p):
    paths = [os.environ.get("SCRIPTORIUM_CHROMIUM"), p.chromium.executable_path,
             shutil.which("chromium-browser"), shutil.which("chromium"), shutil.which("google-chrome")]
    for path in paths:
        if path and Path(path).exists():
            return p.chromium.launch(executable_path=path)
    pytest.skip("no Chromium found")


@pytest.fixture(scope="module")
def browser():
    with playwright.sync_playwright() as p:
        b = _chromium(p)
        yield b
        b.close()


@pytest.fixture(scope="module")
def url(site, serve):
    return serve(site)


def _open(browser, url, device):
    ctx = browser.new_context(**device)
    page = ctx.new_page()
    page.errors = []
    page.on("pageerror", lambda e: page.errors.append(str(e)))
    page.on("console", lambda m: page.errors.append(m.text)
            if m.type in ("error", "warning") and "Failed to load resource" not in m.text else None)
    page.on("response", lambda r: page.errors.append(f"{r.status} {r.url}")
            if r.status >= 400 and not r.url.endswith("/favicon.ico") else None)
    page.goto(url)
    page.wait_for_function("window.scriptoriumReader && scriptoriumReader.counted")
    page.wait_for_timeout(200)
    return ctx, page


def _page(page):
    return page.evaluate("scriptoriumReader.page")


def _on_screen(page, element_id):
    return page.evaluate("""(id) => {
        const el = document.getElementById(id);
        if (!el) return false;
        const r = el.getBoundingClientRect(), s = document.querySelector('#stage').getBoundingClientRect();
        return r.left >= s.left - 1 && r.left < s.right;
    }""", element_id)


@pytest.mark.parametrize("device", [PHONE, DESK], ids=["phone", "desktop"])
def test_toc_jump_turn_and_resume(browser, url, device):
    ctx, page = _open(browser, url, device)
    page.evaluate("document.querySelector('#btn-toc').click()")
    page.click("#toc-list a[data-id='capítulo-de-la-tormenta']")
    page.wait_for_function("scriptoriumReader.chapter === 2")
    page.wait_for_timeout(200)
    assert _on_screen(page, "capítulo-de-la-tormenta")
    landed = _page(page)
    page.keyboard.press("ArrowRight")
    page.wait_for_timeout(400)
    assert _page(page) == landed + 1
    page.reload()
    page.wait_for_function("window.scriptoriumReader && scriptoriumReader.counted")
    page.wait_for_timeout(200)
    assert _page(page) == landed + 1
    ctx.close()


@pytest.mark.parametrize("device", [PHONE, DESK], ids=["phone", "desktop"])
def test_arrows_walk_every_page_across_chapters(browser, url, device):
    ctx, page = _open(browser, url, device)
    pages = page.evaluate("scriptoriumReader.pages")
    seen = []
    for _ in range(pages):
        seen.append((_page(page), page.evaluate("scriptoriumReader.chapter")))
        page.keyboard.press("ArrowRight")
        page.wait_for_timeout(150)
    assert [p for p, _ in seen] == list(range(pages))
    assert sorted({c for _, c in seen}) == [0, 1, 2, 3]
    page.keyboard.press("ArrowLeft")
    page.wait_for_timeout(150)
    assert _page(page) == pages - 2
    ctx.close()


def test_a_swipe_that_starts_on_an_image_turns(browser, url):
    ctx, page = _open(browser, url, PHONE)
    page.evaluate("scriptoriumReader.goToId('fig-faro')")
    page.wait_for_function("scriptoriumReader.chapter === 1")
    page.wait_for_timeout(200)
    before = _page(page)
    box = page.locator("#fig-faro img").bounding_box()
    y = box["y"] + box["height"] / 2
    page.mouse.move(340, y)
    page.mouse.down()
    for x in range(340, 60, -20):
        page.mouse.move(x, y)
    page.mouse.up()
    page.wait_for_timeout(400)
    assert _page(page) == before + 1
    ctx.close()


def test_rectos_in_a_spread(browser, url):
    ctx, page = _open(browser, url, DESK)
    sides = []
    for ident in CHAPTERS:
        page.evaluate("(id) => scriptoriumReader.goToId(id)", ident)
        page.wait_for_function("(id) => document.getElementById(id)", arg=ident)
        page.wait_for_timeout(200)
        sides.append(page.evaluate("""(id) => {
            const s = document.querySelector('#stage').getBoundingClientRect();
            return document.getElementById(id).getBoundingClientRect().left - s.left > s.width / 2 ? 'right' : 'left';
        }""", ident))
    assert sides == ["right", "right", "right"]
    ctx.close()


@pytest.mark.parametrize("device", [PHONE, DESK], ids=["phone", "desktop"])
def test_nothing_spills_out_of_its_page(browser, url, device):
    ctx, page = _open(browser, url, device)
    spills = []
    for ident in CHAPTERS:
        page.evaluate("(id) => scriptoriumReader.goToId(id)", ident)
        page.wait_for_function("(id) => document.getElementById(id)", arg=ident)
        spills += page.evaluate("""() => {
            const out = [];
            const css = getComputedStyle(document.documentElement);
            const pad = parseFloat(css.getPropertyValue('--m'));
            const step = parseFloat(css.getPropertyValue('--col')) + 2 * pad;
            const left = document.querySelector('#book').getBoundingClientRect().left;
            for (const el of document.querySelectorAll('#book .unit p, #book .unit pre, #book .unit table, #book figure img')) {
                for (const r of el.getClientRects()) {
                    const x = r.left - left - pad;
                    const colRight = (Math.floor((x + 2) / step) + 1) * step - 2 * pad;
                    if (x + r.width > colRight + 1) out.push(el.tagName + ' ' + el.textContent.slice(0, 30));
                }
            }
            return out;
        }""")
    assert spills == []
    ctx.close()


def test_a_link_to_another_chapter_loads_it(browser, url):
    ctx, page = _open(browser, url, PHONE)
    page.evaluate("scriptoriumReader.goToId('chap-regreso')")
    page.wait_for_function("scriptoriumReader.chapter === 3")
    page.evaluate("document.querySelector('a.ref-chap').click()")
    page.wait_for_function("scriptoriumReader.chapter === 1")
    page.wait_for_timeout(200)
    assert _on_screen(page, "chap-faro")
    ctx.close()


def test_a_reference_in_the_same_chapter_turns_to_it(browser, url):
    ctx, page = _open(browser, url, PHONE)
    page.evaluate("scriptoriumReader.goToId('chap-faro')")
    page.wait_for_function("scriptoriumReader.chapter === 1")
    page.evaluate("scriptoriumReader.goTo(document.querySelector('a.ref-fig'))")
    page.evaluate("document.querySelector('a.ref-fig').click()")
    page.wait_for_timeout(300)
    assert _on_screen(page, "fig-faro")
    ctx.close()


def test_font_change_keeps_the_first_block(browser, url):
    ctx, page = _open(browser, url, PHONE)
    page.evaluate("scriptoriumReader.goToId('capítulo-de-la-tormenta')")
    page.wait_for_function("scriptoriumReader.chapter === 2")
    page.wait_for_timeout(200)
    page.evaluate("document.querySelector('[data-font=\"1\"]').click()")
    page.evaluate("document.querySelector('[data-font=\"1\"]').click()")
    page.wait_for_timeout(500)
    assert _on_screen(page, "capítulo-de-la-tormenta")
    ctx.close()


def test_a_hash_opens_at_its_target(browser, url):
    ctx = browser.new_context(**PHONE)
    page = ctx.new_page()
    page.goto(url + "#chap-regreso")
    page.wait_for_function("window.scriptoriumReader && scriptoriumReader.chapter === 3")
    page.wait_for_timeout(200)
    # a chapter opens on its first page: here its full-page illustration
    first = page.evaluate("document.querySelector('#book .chapter').firstElementChild.getBoundingClientRect().left")
    stage = page.evaluate("document.querySelector('#stage').getBoundingClientRect().left")
    assert abs(first - stage) < 80
    ctx.close()


@pytest.mark.parametrize("device", [PHONE, DESK], ids=["phone", "desktop"])
def test_no_errors_in_the_console(browser, url, device):
    ctx, page = _open(browser, url, device)
    for _ in range(6):
        page.keyboard.press("ArrowRight")
        page.wait_for_timeout(120)
    assert page.errors == []
    ctx.close()


# ---------- install, offline, updates ----------

def _controlled(page):
    page.wait_for_function("navigator.serviceWorker.controller !== null", timeout=20000)
    page.wait_for_function(
        "caches.keys().then(k => k.some(n => n.startsWith('book:' + new URL('./', location).pathname)))",
        timeout=20000)


def test_offline_reload_shows_the_book_and_every_image(browser, url):
    ctx, page = _open(browser, url, PHONE)
    _controlled(page)
    ctx.set_offline(True)
    page.reload()
    page.wait_for_function("window.scriptoriumReader && scriptoriumReader.counted")
    page.wait_for_timeout(300)
    assert page.inner_text("#foot-offline") == "✓ sin conexión"
    # every chapter and its images come from the cache, not only the open one
    for ident in ("chap-faro", "chap-regreso"):
        page.evaluate("(id) => scriptoriumReader.goToId(id)", ident)
        page.wait_for_function("(id) => document.getElementById(id)", arg=ident)
        page.wait_for_function("[...document.images].every(i => i.complete)")
        assert page.evaluate("[...document.images].length > 0 && [...document.images].every(i => i.naturalWidth > 0)")
    ctx.close()


def test_a_new_edition_shows_the_notice_and_update_shows_it(browser, serve, tmp_path):
    from conftest import build_example
    from scriptorium.cli import main

    site = build_example(tmp_path / "book")
    ctx, page = _open(browser, serve(site), PHONE)
    _controlled(page)
    page.evaluate("scriptoriumReader.goToId('capítulo-de-la-tormenta')")
    page.wait_for_function("scriptoriumReader.chapter === 2")
    for md in (tmp_path / "book").glob("*.md"):
        md.write_text(md.read_text(encoding="utf-8").replace("cerillas", "fósforos"), encoding="utf-8")
    assert main(["render", str(tmp_path / "book" / "scriptorium.yaml"), "--only", "web"]) == 0
    page.evaluate("navigator.serviceWorker.getRegistration().then(r => r.update())")
    page.wait_for_function("document.querySelector('#toast').classList.contains('show')", timeout=20000)
    assert "edición nueva" in page.inner_text("#toast")
    page.click("#toast button")
    page.wait_for_function("window.scriptoriumReader && scriptoriumReader.chapter === 2")
    assert "fósforos" in page.inner_text("#book")
    ctx.close()


def test_updating_one_book_leaves_the_others_cache(browser, serve, tmp_path):
    from conftest import build_example

    root = tmp_path / "root"
    root.mkdir()
    a1 = build_example(tmp_path / "a1")
    shutil.copytree(a1, root / "a")
    shutil.copytree(a1, root / "b")
    base = serve(root)
    ctx = browser.new_context(**PHONE)
    page = ctx.new_page()
    for book in ("b", "a"):
        page.goto(base + book + "/")
        _controlled(page)
    before = page.evaluate("caches.keys()")
    a2 = build_example(tmp_path / "a2", replace=("cerillas", "fósforos"))
    shutil.rmtree(root / "a")
    shutil.copytree(a2, root / "a")
    page.evaluate("navigator.serviceWorker.getRegistration().then(r => r.update())")
    page.wait_for_function("document.querySelector('#toast').classList.contains('show')", timeout=20000)
    # the new worker takes control as it activates, and deletes the old cache just after
    old_a = [k for k in before if k.startswith("book:/a/:")][0]
    for _ in range(20):
        if old_a not in page.evaluate("caches.keys()"):
            break
        page.wait_for_timeout(250)
    after = page.evaluate("caches.keys()")
    b_keys = [k for k in before if k.startswith("book:/b/:")]
    a_before = [k for k in before if k.startswith("book:/a/:")]
    assert len(b_keys) == 1 and b_keys[0] in after
    assert len(a_before) == 1 and a_before[0] not in after
    assert len([k for k in after if k.startswith("book:/a/:")]) == 1
    ctx.close()
