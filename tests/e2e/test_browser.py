"""Сквозные сценарии в настоящем браузере."""
import httpx
import pytest
from selenium.webdriver.common.keys import Keys

from app.search.base import SearchItem
from tests.search.test_service import FakeProvider

PUBLIC_PAGES = ["/", "/video", "/text", "/tariffs", "/features", "/login", "/registration"]
USER_PAGES = ["/editor", "/profile", "/coub", "/youtube", "/tumblr", "/text-editor"]


def test_pages_have_no_js_errors(page, account):
    for path in PUBLIC_PAGES:
        page.open(path)
        page.wait(lambda: page.js("return document.readyState") == "complete")
    page.login(account)
    for path in USER_PAGES:
        page.open(path)
        page.wait(lambda: page.js("return document.readyState") == "complete")
    assert page.console_errors() == []


def test_theme_defaults_to_light_and_persists(page):
    page.open("/")
    assert page.js("return document.documentElement.dataset.theme") == "light"
    page.click("[data-theme-toggle]")
    assert page.js("return document.documentElement.dataset.theme") == "dark"
    page.open("/features")  # выбор сохраняется между страницами
    assert page.js("return document.documentElement.dataset.theme") == "dark"
    background = page.js("return getComputedStyle(document.body).backgroundColor")
    assert background == "rgb(7, 8, 12)"
    page.click("[data-theme-toggle]")
    assert page.js("return localStorage.getItem('theme')") == "light"


def test_registration_and_return_to_requested_page(page):
    page.open("/editor")
    page.wait(lambda: "/login" in page.d.current_url)
    page.click(".auth-switch a")  # «Зарегистрироваться» — ссылка сохраняет next
    page.wait(lambda: "/registration" in page.d.current_url)
    page.q("#identity").send_keys("new-user@example.com")
    page.q("#password").send_keys("secret123")
    page.q("#passwordConfirm").send_keys("secret123")
    page.click("button[type=submit]")
    page.wait(lambda: page.js("return location.pathname") == "/editor")
    assert "new-user@example.com" in page.q(".account-name").text


def test_login_form_shows_server_errors(page):
    page.open("/login")
    page.q("#identity").send_keys("nobody@example.com")
    page.q("#password").send_keys("wrong-pass")
    page.click("button[type=submit]")
    page.wait(lambda: page.visible("#authError"))
    assert page.q("#authError").text == "Неверный логин или пароль"
    page.q("#identity").clear()
    page.q("#identity").send_keys("bad")
    page.click("button[type=submit]")
    assert "корректный email" in page.q("#authError").text  # проверка на клиенте, без запроса


def test_account_menu_and_logout(page, account):
    page.login(account).open("/profile")
    page.click("[data-account-button]")
    page.wait(lambda: page.visible("[data-account-menu] a[href='/logout']"), timeout=3)  # меню появляется с анимацией
    page.click("[data-account-menu] a[href='/logout']")
    page.wait(lambda: page.visible("a[href='/login']"))


def test_search_results_and_editor_modal(page, account, live, fake_download):
    items = [SearchItem(id=str(i), title=f"Ролик {i}", url=f"https://coub.com/view/{i}",
                        preview_url=f"https://example.invalid/{i}.mp4", duration=10) for i in range(6)]
    live.app.state.search.providers["coub"] = FakeProvider(items=items)
    page.login(account).open("/coub")
    page.q("[data-search-input]").send_keys("машины", Keys.ENTER)
    page.wait(lambda: len(page.qa(".clip")) == 6)
    assert page.q("[data-results-meta]").text == "Найдено: 6"
    assert "q=%D0%BC%D0%B0%D1%88%D0%B8%D0%BD%D1%8B" in page.d.current_url  # запрос в адресе — можно поделиться

    page.click(".clip [data-action='edit']")
    page.wait(lambda: page.visible("[data-ce-modal] [data-ce-workspace]"))
    assert page.q("[data-ce-modal-title]").text == "Ролик 0"
    assert "640×360" in page.q("[data-ce-modal] [data-ce-summary]").text
    page.q("body").send_keys(Keys.ESCAPE)
    page.wait(lambda: not page.visible("[data-ce-modal]"))


def test_editor_full_render_flow(page, account, fake_download):
    page.login(account).open("/editor?url=https://coub.com/view/full")
    page.wait(lambda: page.visible("[data-ce-workspace]"))

    page.click(".ce-tab[data-tab='frame']")
    page.click("[data-segmented='aspect'] [data-value='9:16']")
    assert "Итог: 202×360" in page.q("[data-ce-summary]").text  # 9:16 «обрезать»: часть кадра 640×360
    page.click("[data-segmented='fit'] [data-value='blur']")
    assert "Итог: 360×640" in page.q("[data-ce-summary]").text  # «размытый фон»: короткая сторона сохраняется

    page.click(".ce-tab[data-tab='text']")
    # ChromeDriver не печатает эмодзи через send_keys — вставляем как из буфера обмена
    page.js("const t = document.querySelector('textarea[name=text]'); t.value = 'Привет 🔥';"
            "t.dispatchEvent(new Event('input', {bubbles: true}))")
    page.wait(lambda: len(page.qa(".ce-text-line")) == 1)
    page.wait(lambda: page.q("[data-ce-text-count]").get_attribute("textContent") == "9/300", timeout=3)
    assert page.qa(".ce-text-line .ce-emoji")  # эмодзи выделено отдельным элементом

    page.click(".ce-tab[data-tab='export']")
    page.click("[data-segmented='quality'] [data-value='draft']")
    page.click("[data-ce-render]")
    page.wait(lambda: page.visible("[data-ce-result]"), timeout=120, message="рендер не завершился")
    href = page.q("[data-ce-download]").get_attribute("href")
    assert "/api/editor/jobs/" in href and href.endswith("download=1")
    assert page.js("return document.querySelector('[data-ce-result-video]').src").startswith(page.base)

    page.click("[data-ce-back]")
    assert page.visible("[data-ce-workspace]")
    page.wait(lambda: len(page.qa(".my-clip")) == 1)
    assert "Привет" in page.q(".my-clip").text


def test_editor_upload_from_disk(page, account, media_dir):
    page.login(account).open("/editor")
    page.wait(lambda: page.visible("[data-ce-picker]"))
    page.js("document.querySelector('[data-ce-file]').hidden = false")
    page.q("[data-ce-file]").send_keys(str(media_dir / "vertical_silent.mp4"))
    page.wait(lambda: page.visible("[data-ce-workspace]"))
    assert "без звука" in page.q("[data-ce-summary]").text
    assert page.visible("[data-new-video]")


def test_editor_load_error_and_retry(page, account, fake_download):
    fake_download["fail"] = 1
    page.login(account).open("/editor?url=https://coub.com/view/retry")
    page.wait(lambda: page.visible("[data-ce-retry]"))
    assert "недоступно" in page.q("[data-ce-loading-text]").text
    page.click("[data-ce-retry]")
    page.wait(lambda: page.visible("[data-ce-workspace]"))
    assert fake_download["calls"] == 2


def test_editor_validates_timecodes(page, account, fake_download):
    page.login(account).open("/editor?url=https://coub.com/view/time")
    page.wait(lambda: page.visible("[data-ce-workspace]"))
    start = page.q("input[name=trim_start]")
    start.clear()
    start.send_keys("abc")
    page.wait(lambda: "invalid" in start.get_attribute("class"))
    page.click("[data-ce-render]")
    assert page.q("[data-ce-status]").text == "Проверьте время начала и конца фрагмента"
    start.clear()
    start.send_keys("1.5", Keys.TAB)
    assert start.get_attribute("value") == "0:01.5"  # нормализуется к виду м:сс.с
    assert "invalid" not in start.get_attribute("class")


def test_editor_panel_is_disabled_until_video_loaded(page, account):
    page.login(account).open("/editor")
    page.wait(lambda: page.visible("[data-ce-picker]"))
    assert "ce-no-source" in page.q("[data-clip-editor]").get_attribute("class")
    assert page.q("[data-ce-render]").get_attribute("disabled") is not None


def test_admin_platform_toggle(page, live):
    from sqlalchemy import update

    from app.db.base import session_factory
    from app.db.models import User

    with httpx.Client(base_url=live.url) as c:
        c.post("/api/registration", json={"identity": "boss@example.com", "password": "secret123"})
        cookie = c.cookies["session"]

    async def promote():
        async with session_factory()() as db:
            await db.execute(update(User).where(User.email == "boss@example.com").values(is_admin=True))
            await db.commit()

    live.run(promote())
    page.login(cookie).open("/admin/platforms")
    page.wait(lambda: len(page.qa(".platform-admin")) == 6)
    page.click(".platform-admin[data-key='imgur'] input[type=checkbox]")
    page.wait(lambda: page.visible("#confirmationModal"))
    page.click(".modal-confirm")
    page.wait(lambda: "Отключена" in page.q(".platform-admin[data-key='imgur']").text)
    page.open("/imgur")
    assert "Технические работы" in page.q("main").text


@pytest.mark.parametrize("path", ["/", "/video", "/coub", "/editor", "/profile", "/login"])
def test_mobile_layout_has_no_horizontal_scroll(mobile_browser, live, account, path):
    from tests.e2e.conftest import Page

    page = Page(mobile_browser, live.url).login(account).open(path)
    page.wait(lambda: page.js("return document.readyState") == "complete")
    assert page.js("return document.documentElement.scrollWidth") <= 390
