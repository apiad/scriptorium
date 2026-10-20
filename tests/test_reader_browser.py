"""The reader in Chromium: turning, jumping, rectos, resume, nothing spilling.

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
            if m.type == "error" and "Failed to load resource" not in m.text else None)
    page.on("response", lambda r: page.errors.append(f"{r.status} {r.url}")
            if r.status >= 400 and not r.url.endswith("/favicon.ico") else None)
    page.goto(url)
    page.wait_for_function("window.scriptoriumReader && scriptoriumReader.pages > 1")
    page.wait_for_timeout(300)
    return ctx, page


def _page(page):
    return page.evaluate("scriptoriumReader.page")


@pytest.mark.parametrize("device", [PHONE, DESK], ids=["phone", "desktop"])
def test_toc_jump_turn_and_resume(browser, url, device):
    ctx, page = _open(browser, url, device)
    page.evaluate("document.querySelector('#btn-toc').click()")
    page.click("#toc-list a[data-id='capítulo-de-la-tormenta']")
    page.wait_for_timeout(300)
    landed = _page(page)
    chapter_page = page.evaluate("""() => {
        const h = document.getElementById('capítulo-de-la-tormenta');
        const stage = document.querySelector('#stage').getBoundingClientRect();
        return Math.floor((h.getBoundingClientRect().left - stage.left) / stage.width);
    }""")
    assert chapter_page == 0  # the chapter's heading is on the screen we landed on
    page.keyboard.press("ArrowRight")
    page.wait_for_timeout(400)
    assert _page(page) == landed + 1
    page.reload()
    page.wait_for_function("window.scriptoriumReader && scriptoriumReader.pages > 1")
    page.wait_for_timeout(300)
    assert _page(page) == landed + 1
    ctx.close()


def test_a_swipe_that_starts_on_an_image_turns(browser, url):
    ctx, page = _open(browser, url, PHONE)
    page.evaluate("scriptoriumReader.goTo(document.querySelector('#fig-faro'))")
    page.wait_for_timeout(300)
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
    sides = page.evaluate("""() => {
        const stage = document.querySelector('#stage').getBoundingClientRect();
        const half = stage.width / 2;
        return [...document.querySelectorAll('.recto')].map((sec) => {
            const h = sec.querySelector(':scope > .unit > h1, :scope > .unit > h2');
            scriptoriumReader.goTo(h);
            const x = h.getBoundingClientRect().left - stage.left;
            return x > half ? 'right' : 'left';
        });
    }""")
    assert sides == ["right", "right", "right"]
    ctx.close()


@pytest.mark.parametrize("device", [PHONE, DESK], ids=["phone", "desktop"])
def test_nothing_spills_out_of_its_page(browser, url, device):
    ctx, page = _open(browser, url, device)
    spills = page.evaluate("""() => {
        const out = [];
        const stage = document.querySelector('#stage').getBoundingClientRect();
        const pad = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--m'));
        const step = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--col')) + 2 * pad;
        for (const el of document.querySelectorAll('#book .unit p, #book .unit pre, #book .unit table, #book figure img')) {
            for (const r of el.getClientRects()) {
                const x = r.left - document.querySelector('#book').getBoundingClientRect().left - pad;
                const colRight = (Math.floor((x + 2) / step) + 1) * step - 2 * pad;
                if (x + r.width > colRight + 1) out.push(el.tagName + ' ' + el.textContent.slice(0, 30));
            }
        }
        return out;
    }""")
    assert spills == []
    ctx.close()


def test_a_reference_link_turns_to_its_target(browser, url):
    ctx, page = _open(browser, url, PHONE)
    page.evaluate("scriptoriumReader.goTo(document.querySelector('a.ref-fig'))")
    page.wait_for_timeout(300)
    page.evaluate("scriptoriumReader.go(scriptoriumReader.pages - 1)")
    page.wait_for_timeout(300)
    page.evaluate("document.querySelector('a.ref-fig').click()")
    page.wait_for_timeout(300)
    fig_page = page.evaluate("""() => {
        const f = document.getElementById('fig-faro').getBoundingClientRect();
        return f.left >= 0 && f.left < innerWidth;
    }""")
    assert fig_page
    ctx.close()


def test_font_change_keeps_the_first_block(browser, url):
    ctx, page = _open(browser, url, PHONE)
    page.evaluate("scriptoriumReader.goTo(document.getElementById('capítulo-de-la-tormenta'))")
    page.wait_for_timeout(300)
    page.evaluate("document.querySelector('[data-font=\"1\"]').click()")
    page.evaluate("document.querySelector('[data-font=\"1\"]').click()")
    page.wait_for_timeout(400)
    on_screen = page.evaluate("""() => {
        const r = document.getElementById('capítulo-de-la-tormenta').getBoundingClientRect();
        return r.left >= 0 && r.left < innerWidth;
    }""")
    assert on_screen
    ctx.close()


@pytest.mark.parametrize("device", [PHONE, DESK], ids=["phone", "desktop"])
def test_no_errors_in_the_console(browser, url, device):
    ctx, page = _open(browser, url, device)
    for _ in range(3):
        page.keyboard.press("ArrowRight")
    page.wait_for_timeout(300)
    assert page.errors == []
    ctx.close()
