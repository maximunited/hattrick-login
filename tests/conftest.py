from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class FakeElement:
    def __init__(self) -> None:
        self.cleared = False
        self.keys: list[str] = []
        self.clicked = False

    def clear(self) -> None:
        self.cleared = True

    def send_keys(self, value: str) -> None:
        self.keys.append(value)

    def click(self) -> None:
        self.clicked = True


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
        self._elements_by_name: dict[str, list[FakeElement]] = {}
        self._elements_by_css: dict[str, list[FakeElement]] = {}

    def get(self, url: str) -> None:
        self.get_urls.append(url)

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
        return []

    def find_element(self, by, value: str) -> FakeElement:
        elements = self.find_elements(by, value)
        if not elements:
            raise AttributeError(f"Element not found: {value}")
        return elements[0]

    def get_cookies(self) -> list[dict[str, str]]:
        return list(self.cookies)

    def add_name_element(self, name: str) -> FakeElement:
        element = FakeElement()
        self._elements_by_name.setdefault(name, []).append(element)
        return element

    def add_submit_button(self) -> FakeElement:
        element = FakeElement()
        self._elements_by_css.setdefault("input[type='submit']", []).append(element)
        return element


@pytest.fixture
def fake_driver() -> FakeDriver:
    return FakeDriver()


@pytest.fixture
def session_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("HATTRICK_SESSION_DIR", str(tmp_path))
    return tmp_path
