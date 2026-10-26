"""The docs site in Chromium: no script errors, nothing wider than a phone, the
drawer, search and the audio file.

Skipped when no Chromium is found: Playwright's own download, or a system one.
"""

import pytest
from test_docs import build_docs
from test_reader_browser import DESK, PHONE, browser  # noqa: F401 (a fixture)

pytestmark = pytest.mark.browser
playwright = pytest.importorskip("playwright.sync_api")

PAGES = ["index.html", "sound.html", "what.html", "exercises.html", "strings.html", "exercises-2.html"]


@pytest.fixture(scope="module")
def url(tmp_path_factory, serve):
    return serve(build_docs(tmp_path_factory.mktemp("docs")))


def _open(browser, url, device):
    ctx = browser.new_context(**device)
    page = ctx.new_page()
    page.errors = []
    page.on("pageerror", lambda e: page.errors.append(str(e)))
    page.on("console", lambda m: page.errors.append(m.text) if m.type in ("error", "warning") else None)
    page.on("response", lambda r: page.errors.append(f"{r.status} {r.url}")
            if r.status >= 400 and not r.url.endswith("/favicon.ico") else None)
    page.goto(url)
    return ctx, page


@pytest.mark.parametrize("device", [PHONE, DESK], ids=["phone", "desktop"])
def test_no_script_errors_on_any_page(browser, url, device):
    for name in PAGES:
        ctx, page = _open(browser, url + name, device)
        page.wait_for_load_state("load")
        assert page.errors == [], name
        ctx.close()


def test_nothing_is_wider_than_the_phone(browser, url):
    for name in PAGES:
        ctx, page = _open(browser, url + name, PHONE)
        assert page.evaluate("document.documentElement.scrollWidth") <= 390, name
        ctx.close()


def test_the_menu_opens_the_sidebar_on_a_phone(browser, url):
    ctx, page = _open(browser, url + "what.html", PHONE)
    assert not page.is_visible(".sidebar a[aria-current]")
    page.click(".topbar .menu")
    page.wait_for_timeout(400)
    assert page.is_visible(".sidebar a[aria-current]")
    ctx.close()


def test_a_long_code_line_scrolls_inside_its_block(browser, url):
    ctx, page = _open(browser, url + "strings.html", PHONE)
    pre = page.evaluate("(() => { const p = document.querySelector('main pre');"
                        " return [p.scrollWidth, p.clientWidth, getComputedStyle(p).whiteSpace]; })()")
    assert pre[0] > pre[1] and pre[2] == "pre"
    assert page.evaluate("document.documentElement.scrollWidth") <= 390
    ctx.close()


@pytest.mark.parametrize("how", ["escape", "outside"])
def test_the_drawer_closes_with_escape_or_a_click_outside(browser, url, how):
    ctx, page = _open(browser, url + "what.html", PHONE)
    page.click(".topbar .menu")
    page.wait_for_timeout(400)
    if how == "escape":
        page.keyboard.press("Escape")
    else:
        page.mouse.click(370, 600)
    page.wait_for_timeout(400)
    assert not page.is_visible(".sidebar a[aria-current]") and page.url.endswith("what.html")
    ctx.close()


def test_search_retries_after_a_failed_fetch(browser, url):
    ctx, page = _open(browser, url, DESK)
    page.route("**/search.json", lambda route: route.abort())
    page.click(".topbar .search input")
    page.wait_for_timeout(300)
    page.unroute("**/search.json")
    page.errors.clear()  # the aborted request is the point of the test
    page.click("main")
    page.click(".topbar .search input")
    page.keyboard.type("wav")
    page.wait_for_selector(".search-results a")
    assert page.errors == []
    ctx.close()


@pytest.mark.parametrize("device", [PHONE, DESK], ids=["phone", "desktop"])
def test_search_finds_a_section(browser, url, device):
    ctx, page = _open(browser, url, device)
    page.click(".topbar .search input")
    page.keyboard.type("wav")
    page.wait_for_selector(".search-results a")
    assert page.get_attribute(".search-results a", "href") == "what.html#waves"
    ctx.close()


def test_the_audio_file_loads(browser, url):
    ctx, page = _open(browser, url + "what.html", DESK)
    status = page.evaluate("fetch(document.querySelector('audio').src).then(r => r.status)")
    assert status == 200 and page.get_attribute("audio", "src").startswith("media/")
    ctx.close()
