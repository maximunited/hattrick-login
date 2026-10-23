from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class FakeElement:
    def __init__(self) -> None:
        self.cleared = False
        self.keys: list[str] = []
        self.clicked = False
        self.text = ""
        self.tag_name = "div"

    def clear(self) -> None:
        self.cleared = True

    def send_keys(self, value: str) -> None:
        self.keys.append(value)

    def click(self) -> None:
        self.clicked = True

    def is_displayed(self) -> bool:
        return True

    def is_enabled(self) -> bool:
        return True

    def get_attribute(self, name: str) -> str | None:
        return None


class FakeDriver:
    def __init__(
        self,
        *,
        title: str = "Hattrick",
        page_source: str = "<html></html>",
        current_url: str = "https://www.hattrick.org/en-us/",
        cookies: list[dict[str, str]] | None = None,
    ) -> None:
        self.title = title
        self.page_source = page_source
        self.current_url = current_url
        self.cookies = cookies or []
        self.get_urls: list[str] = []
        self.quit_called = False
        self.window_size: tuple[int, int] | None = None
        self.redirect_to: str | None = None
        self._elements_by_name: dict[str, list[FakeElement]] = {}
        self._elements_by_css: dict[str, list[FakeElement]] = {}
        self._elements_by_partial_link: dict[str, list[FakeElement]] = {}
        self._elements_by_id: dict[str, list[FakeElement]] = {}

    def get(self, url: str) -> None:
        self.get_urls.append(url)
        self.current_url = getattr(self, "redirect_to", None) or url

    def quit(self) -> None:
        self.quit_called = True

    def set_window_size(self, width: int, height: int) -> None:
        self.window_size = (width, height)

    def find_elements(self, by, value: str) -> list[FakeElement]:
        from selenium.webdriver.common.by import By

        if by == By.NAME:
            return self._elements_by_name.get(value, [])
        if by == By.CSS_SELECTOR:
            return self._elements_by_css.get(value, [])
        if by == By.ID:
            return self._elements_by_id.get(value, [])
        if by == By.PARTIAL_LINK_TEXT:
            matches: list[FakeElement] = []
            for text, elements in self._elements_by_partial_link.items():
                if value in text or text in value:
                    matches.extend(elements)
            return matches
        return []

    def find_element(self, by, value: str) -> FakeElement:
        elements = self.find_elements(by, value)
        if not elements:
            raise AttributeError(f"Element not found: {value}")
        return elements[0]

    def get_cookies(self) -> list[dict[str, str]]:
        return list(self.cookies)

    def delete_cookie(self, name: str) -> None:
        self.cookies = [cookie for cookie in self.cookies if cookie.get("name") != name]

    def execute_script(self, script: str, *args):
        if not args:
            return None
        target = args[0]
        compact = "".join(script.split())
        if "arguments[0].click()" in compact:
            target.click()
            return None
        if len(args) > 1:
            target.send_keys(args[1])
        return None

    def add_name_element(self, name: str) -> FakeElement:
        element = FakeElement()
        self._elements_by_name.setdefault(name, []).append(element)
        return element

    def add_submit_button(self) -> FakeElement:
        element = FakeElement()
        element.tag_name = "input"
        self._elements_by_css.setdefault("input[type='submit']", []).append(element)
        return element

    def add_id_element(self, element_id: str) -> FakeElement:
        element = FakeElement()
        self._elements_by_id.setdefault(element_id, []).append(element)
        return element

    def add_partial_link(self, text: str) -> FakeElement:
        element = FakeElement()
        self._elements_by_partial_link.setdefault(text, []).append(element)
        return element


@pytest.fixture
def fake_driver() -> FakeDriver:
    return FakeDriver()


@pytest.fixture
def session_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("HATTRICK_SESSION_DIR", str(tmp_path))
    return tmp_path
