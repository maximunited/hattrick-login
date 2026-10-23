from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By

import hattrick_client as client
from hattrick_client import (
    AUTH_FAILED_MARKER,
    CLOUDFLARE_TITLE,
    DASHBOARD_URL,
    LOGIN_URL,
    PASSWORD_FIELD,
    USERNAME_FIELD,
    LoginResult,
    finances_url,
    is_cloudflare_challenge,
    is_first_run,
    is_logged_in_page,
)
from tests.conftest import FakeDriver, FakeElement


def test_cloudflare_detection():
    assert is_cloudflare_challenge("Just a moment...", "<html></html>")
    assert is_cloudflare_challenge("Hattrick", "<html>challenges.cloudflare.com</html>")
    assert not is_cloudflare_challenge("Hattrick", "<html></html>")


@pytest.mark.parametrize(
    ("title", "page_source", "require_protected", "expected"),
    [
        ("Dashboard", "<html>/MyHattrick/Dashboard</html>", True, True),
        ("Dashboard", "<html>Logout and /MyHattrick/</html>", False, True),
        ("Dashboard", "<html>Log out</html>", False, True),
        ("Dashboard", "<html>Sign out</html>", False, True),
        ("Login", f"<html>{AUTH_FAILED_MARKER}</html>", False, False),
        (
            "Hattrick",
            '<html><input name="ctl00$CPContent$ucLogin$txtUserName"></html>',
            False,
            False,
        ),
        ("Dashboard", "<html>Logout but ucLogin form</html>", False, False),
        ("Dashboard", "<html>Logout only</html>", True, False),
        (
            "Hattrick",
            '<html><input id="inputLoginname" name="loginname"><input id="inputPassword" name="password"></html>',
            False,
            False,
        ),
        (
            "Hattrick Football Manager Game | Join the free football world",
            "<html>/MyHattrick/</html>",
            True,
            False,
        ),
    ],
)
def test_logged_in_detection(title, page_source, require_protected, expected):
    assert is_logged_in_page(title, page_source, require_protected=require_protected) is expected


def test_first_run_empty_dir(tmp_path):
    assert is_first_run(tmp_path) is True


def test_first_run_with_network_cookies(tmp_path):
    cookie_path = tmp_path / "Default" / "Network" / "Cookies"
    cookie_path.parent.mkdir(parents=True)
    cookie_path.write_text("cookie", encoding="utf-8")
    assert is_first_run(tmp_path) is False


def test_first_run_with_legacy_cookies(tmp_path):
    cookie_path = tmp_path / "Default" / "Cookies"
    cookie_path.parent.mkdir(parents=True)
    cookie_path.write_text("cookie", encoding="utf-8")
    assert is_first_run(tmp_path) is False


def test_finances_url():
    assert finances_url("1844625") == "https://www.hattrick.org/Club/Finances/?teamId=1844625"


def test_get_session_dir_override(session_dir):
    assert client.get_session_dir() == session_dir


def test_get_session_dir_default(monkeypatch):
    monkeypatch.delenv("HATTRICK_SESSION_DIR", raising=False)
    assert client.get_session_dir() == Path.home() / ".hattrick-session"


def test_detect_chrome_binary_override(monkeypatch):
    monkeypatch.setenv("HATTRICK_CHROME_BINARY", "/opt/chrome")
    assert client.detect_chrome_binary() == "/opt/chrome"


def test_detect_chrome_binary_from_path(monkeypatch):
    monkeypatch.delenv("HATTRICK_CHROME_BINARY", raising=False)
    with patch("hattrick_client.shutil.which", return_value="/usr/bin/chromium-browser"):
        assert client.detect_chrome_binary() == "/usr/bin/chromium-browser"


def test_detect_chrome_binary_missing(monkeypatch):
    monkeypatch.delenv("HATTRICK_CHROME_BINARY", raising=False)
    with patch("hattrick_client.shutil.which", return_value=None):
        assert client.detect_chrome_binary() is None


def test_detect_chrome_version_main_linux(monkeypatch):
    monkeypatch.setattr(client.platform, "system", lambda: "Linux")
    with patch(
        "hattrick_client.subprocess.check_output",
        return_value="Google Chrome 151.0.6778.0",
    ):
        assert client.detect_chrome_version_main() == 151


def test_detect_chrome_version_main_windows(monkeypatch):
    monkeypatch.setattr(client.platform, "system", lambda: "Windows")
    fake_winreg = MagicMock()
    fake_winreg.QueryValueEx.return_value = ("151.0.6778.0", None)
    with patch.dict(sys.modules, {"winreg": fake_winreg}):
        assert client.detect_chrome_version_main() == 151


def test_detect_chrome_version_main_oserror(monkeypatch):
    monkeypatch.setattr(client.platform, "system", lambda: "Linux")
    with patch("hattrick_client.subprocess.check_output", side_effect=OSError("boom")):
        assert client.detect_chrome_version_main() is None


def test_detect_chrome_version_main_not_found(monkeypatch):
    monkeypatch.setattr(client.platform, "system", lambda: "Linux")

    def raise_not_found(*args, **kwargs):
        raise FileNotFoundError("missing")

    with patch("hattrick_client.subprocess.check_output", side_effect=raise_not_found):
        assert client.detect_chrome_version_main() is None


def test_random_delay_calls_sleep(monkeypatch):
    values = iter([1.5])

    monkeypatch.setattr(client.random, "uniform", lambda a, b: next(values))
    slept: list[float] = []
    monkeypatch.setattr(client.time, "sleep", slept.append)
    client.random_delay(1.0, 2.0)
    assert slept == [1.5]


def test_cleanup_stale_chrome_locks(tmp_path):
    lock = tmp_path / "SingletonLock"
    lock.write_text("lock", encoding="utf-8")
    client.cleanup_stale_chrome_locks(tmp_path)
    assert not lock.exists()


def test_cleanup_stale_chrome_locks_ignores_unlink_errors(tmp_path, monkeypatch):
    lock = tmp_path / "SingletonLock"
    lock.write_text("lock", encoding="utf-8")

    original_unlink = Path.unlink

    def flaky_unlink(self, missing_ok=False):
        if self.name == "SingletonLock":
            raise OSError("busy")
        return original_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", flaky_unlink)
    client.cleanup_stale_chrome_locks(tmp_path)


def test_wait_for_login_form_cloudflare_uses_input(fake_driver, monkeypatch):
    fake_driver.title = CLOUDFLARE_TITLE
    times = iter([0, 1, 100])

    monkeypatch.setattr(client.time, "time", lambda: next(times))
    monkeypatch.setattr(client, "random_delay", lambda *args, **kwargs: None)
    monkeypatch.setattr("builtins.input", lambda prompt: None)

    assert not client.wait_for_login_form(
        fake_driver,
        timeout=5,
        visible=True,
        debug=False,
    )


def test_wait_for_login_form_polls_until_timeout(fake_driver, monkeypatch):
    fake_driver.title = "Login"
    fake_driver.page_source = "<html>no form yet</html>"
    times = iter([0, 1, 100])
    delays: list[tuple[float, float]] = []

    monkeypatch.setattr(client.time, "time", lambda: next(times))
    monkeypatch.setattr(client, "random_delay", lambda *args, **kwargs: delays.append((args[0], args[1])))

    assert not client.wait_for_login_form(
        fake_driver,
        timeout=5,
        visible=False,
        debug=False,
    )
    assert delays


def test_wait_for_login_form_headless_cloudflare_delays(fake_driver, monkeypatch):
    fake_driver.title = CLOUDFLARE_TITLE
    times = iter([0, 1, 100])
    delays: list[tuple[float, float]] = []

    monkeypatch.setattr(client.time, "time", lambda: next(times))
    monkeypatch.setattr(client, "random_delay", lambda *args, **kwargs: delays.append((args[0], args[1])))

    assert not client.wait_for_login_form(
        fake_driver,
        timeout=5,
        visible=False,
        debug=False,
    )
    assert delays


def test_build_chrome_options_headless_linux(tmp_path, monkeypatch):
    monkeypatch.setattr(client.platform, "system", lambda: "Linux")
    options = client.build_chrome_options(tmp_path, headless=True)
    args = options.arguments
    assert f"--user-data-dir={tmp_path}" in args
    assert "--headless=new" in args
    assert "--disable-gpu" in args
    assert "--use-angle=swiftshader" in args


def test_build_chrome_options_visible_non_linux(tmp_path, monkeypatch):
    monkeypatch.setattr(client.platform, "system", lambda: "Darwin")
    options = client.build_chrome_options(tmp_path, headless=False)
    args = options.arguments
    assert "--headless=new" not in args
    assert "--disable-gpu" not in args


def test_start_browser(monkeypatch, tmp_path):
    fake_driver = MagicMock()
    fake_uc = MagicMock()
    fake_uc.Chrome.return_value = fake_driver

    monkeypatch.setattr(client, "uc", fake_uc)
    monkeypatch.setattr(client, "detect_chrome_version_main", lambda: 120)
    monkeypatch.setattr(client, "detect_chrome_binary", lambda: "/usr/bin/chrome")

    driver = client.start_browser(tmp_path, headless=True, debug=True)
    assert driver is fake_driver
    fake_driver.set_window_size.assert_called_once_with(1920, 1080)
    kwargs = fake_uc.Chrome.call_args.kwargs
    assert kwargs["version_main"] == 120
    assert kwargs["browser_executable_path"] == "/usr/bin/chrome"


def test_wait_for_login_form_clicks_log_in_link(fake_driver, monkeypatch):
    times = iter([0, 1, 2, 3, 100])
    monkeypatch.setattr(client.time, "time", lambda: next(times))
    monkeypatch.setattr(client, "random_delay", lambda *args, **kwargs: None)

    link = fake_driver.add_partial_link("Log In")
    original_click = link.click

    def click_and_reveal() -> None:
        original_click()
        fake_driver.add_id_element("inputLoginname")
        fake_driver.add_id_element("inputPassword")

    link.click = click_and_reveal  # type: ignore[method-assign]

    assert client.wait_for_login_form(
        fake_driver,
        timeout=5,
        visible=False,
        debug=False,
    )
    assert link.clicked


def test_wait_for_login_form_finds_username(fake_driver, monkeypatch):
    fake_driver.add_name_element(USERNAME_FIELD)
    fake_driver.add_name_element(PASSWORD_FIELD)
    times = iter([0, 1, 100])
    monkeypatch.setattr(client.time, "time", lambda: next(times))
    monkeypatch.setattr(client, "random_delay", lambda *args, **kwargs: None)
    assert client.wait_for_login_form(
        fake_driver,
        timeout=5,
        visible=False,
        debug=False,
    )


def test_submit_login_form_auth_failed_after_wait(fake_driver, monkeypatch):
    fake_driver.add_name_element(USERNAME_FIELD)
    fake_driver.add_name_element(PASSWORD_FIELD)
    fake_driver.add_submit_button()
    fake_driver.page_source = "<html>waiting</html>"
    monkeypatch.setattr(client, "random_delay", lambda *args, **kwargs: None)

    user_element = fake_driver._elements_by_name[USERNAME_FIELD][0]

    def until_side_effect(condition):
        if callable(condition) and getattr(condition, "__name__", "") == "_predicate":
            return user_element
        fake_driver.page_source = f"<html>{AUTH_FAILED_MARKER}</html>"
        return condition(fake_driver)

    with patch("hattrick_client.WebDriverWait") as wait_cls:
        wait_cls.return_value.until.side_effect = until_side_effect
        result = client.submit_login_form(fake_driver, "user", "pass")

    assert result.message == "Authentication failed"


def test_wait_for_login_form_cloudflare_with_prompt(fake_driver, monkeypatch):
    fake_driver.title = CLOUDFLARE_TITLE
    fake_driver.page_source = "<html>challenge</html>"
    times = iter([0, 1, 2, 3, 100])

    monkeypatch.setattr(client.time, "time", lambda: next(times))
    monkeypatch.setattr(client, "random_delay", lambda *args, **kwargs: None)

    def add_form_after_prompt(_message: str) -> None:
        fake_driver.title = "Login"
        fake_driver.page_source = "<html>login</html>"
        fake_driver.add_name_element(USERNAME_FIELD)
        fake_driver.add_name_element(PASSWORD_FIELD)

    assert client.wait_for_login_form(
        fake_driver,
        timeout=5,
        visible=True,
        debug=False,
        prompt=add_form_after_prompt,
    )


def test_wait_for_login_form_times_out(fake_driver, monkeypatch):
    fake_driver.title = CLOUDFLARE_TITLE
    times = iter([0, 100])

    monkeypatch.setattr(client.time, "time", lambda: next(times))
    monkeypatch.setattr(client, "random_delay", lambda *args, **kwargs: None)

    assert not client.wait_for_login_form(
        fake_driver,
        timeout=5,
        visible=False,
        debug=False,
    )


def test_submit_login_form_missing_submit(fake_driver, monkeypatch):
    fake_driver.add_name_element(USERNAME_FIELD)
    fake_driver.add_name_element(PASSWORD_FIELD)
    monkeypatch.setattr(client, "random_delay", lambda *args, **kwargs: None)

    result = client.submit_login_form(fake_driver, "user", "pass")
    assert result == LoginResult(False, "Login submit button not found")


def test_submit_login_form_auth_failed(fake_driver, monkeypatch):
    fake_driver.add_name_element(USERNAME_FIELD)
    fake_driver.add_name_element(PASSWORD_FIELD)
    fake_driver.add_submit_button()
    fake_driver.page_source = f"<html>{AUTH_FAILED_MARKER}</html>"
    monkeypatch.setattr(client, "random_delay", lambda *args, **kwargs: None)

    result = client.submit_login_form(fake_driver, "user", "pass")
    assert result.ok is False
    assert result.message == "Authentication failed"


def test_submit_login_form_success_verifies_dashboard(fake_driver, monkeypatch):
    fake_driver.add_name_element(USERNAME_FIELD)
    fake_driver.add_name_element(PASSWORD_FIELD)
    fake_driver.add_submit_button()
    fake_driver.page_source = "<html>/MyHattrick/Dashboard Logout</html>"
    monkeypatch.setattr(client, "random_delay", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        client,
        "verify_logged_in",
        lambda driver, debug=False: LoginResult(True, "Login successful", driver.current_url, driver.title),
    )

    result = client.submit_login_form(fake_driver, "user", "pass", debug=True)
    assert result.ok is True


def test_submit_login_form_timeout(fake_driver, monkeypatch):
    fake_driver.add_name_element(USERNAME_FIELD)
    fake_driver.add_name_element(PASSWORD_FIELD)
    fake_driver.add_submit_button()
    fake_driver.page_source = "<html>waiting</html>"
    monkeypatch.setattr(client, "random_delay", lambda *args, **kwargs: None)

    user_element = fake_driver._elements_by_name[USERNAME_FIELD][0]
    password_element = fake_driver._elements_by_name[PASSWORD_FIELD][0]
    with patch("hattrick_client.WebDriverWait") as wait_cls:
        wait_cls.return_value.until.side_effect = [
            user_element,
            password_element,
            TimeoutException("timeout"),
        ]
        result = client.submit_login_form(fake_driver, "user", "pass")

    assert result.message == "Login result unclear after submit"


def test_submit_login_form_logged_in_after_wait(fake_driver, monkeypatch):
    fake_driver.add_name_element(USERNAME_FIELD)
    fake_driver.add_name_element(PASSWORD_FIELD)
    fake_driver.add_submit_button()
    fake_driver.page_source = "<html>waiting</html>"
    monkeypatch.setattr(client, "random_delay", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        client,
        "verify_logged_in",
        lambda driver, debug=False: LoginResult(True, "Login successful"),
    )

    user_element = fake_driver._elements_by_name[USERNAME_FIELD][0]

    def until_side_effect(condition):
        if callable(condition) and getattr(condition, "__name__", "") == "_predicate":
            return user_element
        fake_driver.page_source = "<html>/MyHattrick/ Logout</html>"
        return condition(fake_driver)

    with patch("hattrick_client.WebDriverWait") as wait_cls:
        wait_cls.return_value.until.side_effect = until_side_effect
        result = client.submit_login_form(fake_driver, "user", "pass")

    assert result.ok is True


def test_submit_login_form_unclear_after_wait(fake_driver, monkeypatch):
    fake_driver.add_name_element(USERNAME_FIELD)
    fake_driver.add_name_element(PASSWORD_FIELD)
    fake_driver.add_submit_button()
    fake_driver.page_source = "<html>still unclear</html>"
    monkeypatch.setattr(client, "random_delay", lambda *args, **kwargs: None)

    user_element = fake_driver._elements_by_name[USERNAME_FIELD][0]

    def until_side_effect(condition):
        if callable(condition) and getattr(condition, "__name__", "") == "_predicate":
            return user_element
        return condition(fake_driver)

    with patch("hattrick_client.WebDriverWait") as wait_cls:
        wait_cls.return_value.until.side_effect = until_side_effect
        result = client.submit_login_form(fake_driver, "user", "pass")

    assert result.message == "Login result unclear"


def test_dashboard_url_for_uses_shard_host(fake_driver):
    fake_driver.current_url = "https://www83.hattrick.org/MyHattrick/Office/"
    assert client.dashboard_url_for(fake_driver) == "https://www83.hattrick.org/MyHattrick/"


def test_verify_logged_in_keeps_shard_host(fake_driver, monkeypatch):
    fake_driver.current_url = "https://www83.hattrick.org/MyHattrick/Office/"
    fake_driver.page_source = "<html>/MyHattrick/Dashboard Logout</html>"
    fake_driver.title = "My office » Hattrick"
    monkeypatch.setattr(client, "random_delay", lambda *args, **kwargs: None)
    result = client.verify_logged_in(fake_driver)
    assert result.ok is True
    assert fake_driver.get_urls == []


def test_verify_logged_in_success(fake_driver, monkeypatch):
    fake_driver.page_source = "<html>/MyHattrick/Dashboard</html>"
    monkeypatch.setattr(client, "random_delay", lambda *args, **kwargs: None)

    result = client.verify_logged_in(fake_driver, debug=True)
    assert result.ok is True
    assert fake_driver.get_urls == ["https://www.hattrick.org/MyHattrick/"]


def test_verify_logged_in_rejects_login_redirect(fake_driver, monkeypatch):
    fake_driver.page_source = "<html>/MyHattrick/</html>"
    fake_driver.title = "Hattrick Football Manager Game | Join the free football world"
    fake_driver.redirect_to = "https://www.hattrick.org/en-us/?ReturnUrl=%2fen-us%2fMyHattrick%2f"
    monkeypatch.setattr(client, "random_delay", lambda *args, **kwargs: None)

    result = client.verify_logged_in(fake_driver)
    assert result.ok is False
    assert result.message == "Not authenticated"


def test_verify_logged_in_cloudflare(fake_driver, monkeypatch):
    fake_driver.title = CLOUDFLARE_TITLE
    fake_driver.page_source = "<html>challenge</html>"
    monkeypatch.setattr(client, "random_delay", lambda *args, **kwargs: None)

    result = client.verify_logged_in(fake_driver)
    assert result.message == "Cloudflare challenge blocked dashboard access"


def test_verify_logged_in_not_authenticated(fake_driver, monkeypatch):
    fake_driver.page_source = "<html>public page</html>"
    monkeypatch.setattr(client, "random_delay", lambda *args, **kwargs: None)

    result = client.verify_logged_in(fake_driver)
    assert result.message == "Not authenticated"


def test_fetch_page_with_browser_success(fake_driver, monkeypatch):
    fake_driver.page_source = "<html>/MyHattrick/</html>"
    monkeypatch.setattr(client, "random_delay", lambda *args, **kwargs: None)

    status, body = client.fetch_page_with_browser(fake_driver, DASHBOARD_URL)
    assert status == 200
    assert body == fake_driver.page_source


def test_fetch_page_with_browser_cloudflare(fake_driver, monkeypatch):
    fake_driver.title = CLOUDFLARE_TITLE
    fake_driver.page_source = "<html>challenge</html>"
    monkeypatch.setattr(client, "random_delay", lambda *args, **kwargs: None)

    status, body = client.fetch_page_with_browser(fake_driver, LOGIN_URL)
    assert status == 403


def test_save_cookies_snapshot_restricts_permissions(tmp_path):
    if os.name == "nt":
        pytest.skip("Unix file modes are not enforced on Windows")

    session = client.export_requests_session(
        FakeDriver(cookies=[{"name": "session", "value": "abc", "domain": ".hattrick.org", "path": "/"}])
    )
    cookie_path = tmp_path / "cookies.json"
    client.save_cookies_snapshot(session, cookie_path)
    assert oct(cookie_path.stat().st_mode & 0o777) == oct(0o600)


def test_export_and_cookie_snapshot_roundtrip(tmp_path):
    driver = FakeDriver(
        cookies=[
            {"name": "session", "value": "abc", "domain": ".hattrick.org", "path": "/"},
        ]
    )
    session = client.export_requests_session(driver)
    cookie_path = tmp_path / "cookies.json"
    client.save_cookies_snapshot(session, cookie_path)

    loaded = client.load_cookies_snapshot(cookie_path)
    assert loaded.cookies.get("session") == "abc"
    saved = json.loads(cookie_path.read_text(encoding="utf-8"))
    assert saved[0]["name"] == "session"


def test_fetch_authenticated_page(monkeypatch):
    response = MagicMock(status_code=200, text="<html>ok</html>")
    with patch("hattrick_client.requests.Session.get", return_value=response):
        session = requests.Session()
        status, text = client.fetch_authenticated_page(session, DASHBOARD_URL)
    assert status == 200
    assert text == "<html>ok</html>"


def test_browser_login_start_failure(monkeypatch, session_dir):
    monkeypatch.setattr(client, "start_browser", MagicMock(side_effect=RuntimeError("chrome down")))

    driver, result = client.browser_login("user", "pass", headless=True)
    assert driver is None
    assert "Failed to start Chrome" in result.message


def test_wait_for_login_form_ready_with_modern_fields(fake_driver, monkeypatch):
    times = iter([0, 1, 100])
    monkeypatch.setattr(client.time, "time", lambda: next(times))
    monkeypatch.setattr(client, "random_delay", lambda *args, **kwargs: None)
    fake_driver.add_id_element("inputLoginname")
    fake_driver.add_id_element("inputPassword")
    assert client.wait_for_login_form(
        fake_driver,
        timeout=5,
        visible=False,
        debug=False,
    )


def test_submit_login_form_modern_fields(fake_driver, monkeypatch):
    user_field = fake_driver.add_id_element("inputLoginname")
    password_field = fake_driver.add_id_element("inputPassword")
    fake_driver.add_submit_button()
    fake_driver.page_source = "<html>/MyHattrick/Dashboard Logout</html>"
    monkeypatch.setattr(client, "random_delay", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        client,
        "verify_logged_in",
        lambda driver, debug=False: LoginResult(True, "Login successful", driver.current_url, driver.title),
    )

    result = client.submit_login_form(fake_driver, "user", "pass", debug=True)
    assert result.ok is True
    assert user_field.keys == ["user"]
    assert password_field.keys == ["pass"]


def test_find_login_submit_prefers_angular_button(fake_driver):
    fake_driver.add_id_element("ctl00_CPContent_ucUserAuthentication_btnAspLogin")
    button = FakeElement()
    button.tag_name = "button"
    button.text = "LOG IN"
    fake_driver._elements_by_css["button.primary-button[type='submit']"] = [button]
    assert client.find_login_submit(fake_driver) is button


def test_set_input_value_types_natively_when_possible():
    element = FakeElement()
    driver = MagicMock()
    client.set_input_value(driver, element, "hello")
    assert element.keys == ["hello"]
    assert element.clicked is True


def test_is_cloudflare_cookie():
    assert client.is_cloudflare_cookie("cf_clearance") is True
    assert client.is_cloudflare_cookie("__cf_bm") is True
    assert client.is_cloudflare_cookie("_cfuvid") is True
    assert client.is_cloudflare_cookie("cf_chl_rc_i") is True
    assert client.is_cloudflare_cookie("ASP.NET_SessionId") is False
    assert client.is_cloudflare_cookie(".ASPXAUTH") is False


def test_clear_hattrick_auth_cookies_keeps_cloudflare(fake_driver):
    fake_driver.cookies = [
        {"name": "cf_clearance", "value": "cf"},
        {"name": "__cf_bm", "value": "bot"},
        {"name": "ASP.NET_SessionId", "value": "sess"},
        {"name": ".ASPXAUTH", "value": "auth"},
    ]
    removed = client.clear_hattrick_auth_cookies(fake_driver)
    names = {cookie["name"] for cookie in fake_driver.cookies}
    assert removed == 2
    assert names == {"cf_clearance", "__cf_bm"}


def test_browser_login_force_fresh_login_submits_form_when_session_exists(monkeypatch, session_dir):
    fake_driver = FakeDriver(
        page_source="<html>/MyHattrick/ Logout</html>",
        cookies=[
            {"name": "cf_clearance", "value": "cf"},
            {"name": "ASP.NET_SessionId", "value": "sess"},
        ],
    )
    submitted: list[bool] = []

    def fake_submit(*args, **kwargs):
        submitted.append(True)
        return LoginResult(True, "Login successful")

    monkeypatch.setattr(client, "start_browser", lambda *args, **kwargs: fake_driver)
    monkeypatch.setattr(client, "random_delay", lambda *args, **kwargs: None)
    monkeypatch.setattr(client, "wait_for_login_form", lambda *args, **kwargs: True)
    monkeypatch.setattr(client, "submit_login_form", fake_submit)
    monkeypatch.setattr(
        client,
        "verify_logged_in",
        lambda driver, debug=False: LoginResult(True, "skipped-session"),
    )

    driver, result = client.browser_login(
        "user",
        "pass",
        headless=True,
        debug=True,
        force_fresh_login=True,
    )
    assert driver is fake_driver
    assert submitted == [True]
    assert result.message == "Login successful"
    assert fake_driver.get_urls == [LOGIN_URL, LOGIN_URL]
    names = {cookie["name"] for cookie in fake_driver.cookies}
    assert "cf_clearance" in names
    assert "ASP.NET_SessionId" not in names


def test_browser_login_already_logged_in(monkeypatch, session_dir):
    fake_driver = FakeDriver(page_source="<html>/MyHattrick/ Logout</html>")
    monkeypatch.setattr(client, "start_browser", lambda *args, **kwargs: fake_driver)
    monkeypatch.setattr(client, "random_delay", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        client,
        "verify_logged_in",
        lambda driver, debug=False: LoginResult(True, "Login successful"),
    )

    driver, result = client.browser_login("user", "pass", headless=True, debug=True)
    assert driver is fake_driver
    assert result.ok is True
    assert fake_driver.get_urls == [LOGIN_URL]


def test_browser_login_form_unavailable(monkeypatch, session_dir):
    fake_driver = FakeDriver(page_source="<html>login page</html>")
    monkeypatch.setattr(client, "start_browser", lambda *args, **kwargs: fake_driver)
    monkeypatch.setattr(client, "random_delay", lambda *args, **kwargs: None)
    monkeypatch.setattr(client, "wait_for_login_form", lambda *args, **kwargs: False)

    driver, result = client.browser_login("user", "pass", headless=True)
    assert driver is fake_driver
    assert result.message.startswith("Login form not available")


def test_browser_login_submits_form(monkeypatch, session_dir):
    fake_driver = FakeDriver(page_source="<html>login page</html>")
    monkeypatch.setattr(client, "start_browser", lambda *args, **kwargs: fake_driver)
    monkeypatch.setattr(client, "random_delay", lambda *args, **kwargs: None)
    monkeypatch.setattr(client, "wait_for_login_form", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        client,
        "submit_login_form",
        lambda *args, **kwargs: LoginResult(True, "Login successful"),
    )

    driver, result = client.browser_login("user", "pass", headless=False)
    assert result.ok is True


def test_browser_login_unexpected_error(monkeypatch, session_dir):
    fake_driver = FakeDriver(page_source="<html>login page</html>")
    monkeypatch.setattr(client, "start_browser", lambda *args, **kwargs: fake_driver)
    monkeypatch.setattr(client, "random_delay", lambda *args, **kwargs: None)
    monkeypatch.setattr(client, "wait_for_login_form", lambda *args, **kwargs: True)
    monkeypatch.setattr(client, "submit_login_form", MagicMock(side_effect=RuntimeError("boom")))

    driver, result = client.browser_login("user", "pass", headless=True)
    assert driver is fake_driver
    assert result.message == "Unexpected browser error: boom"


def test_configure_stdio_reconfigure(monkeypatch):
    stdout = MagicMock()
    stderr = MagicMock()
    monkeypatch.setattr(client.sys, "stdout", stdout)
    monkeypatch.setattr(client.sys, "stderr", stderr)

    client.configure_stdio()
    stdout.reconfigure.assert_called_once_with(encoding="utf-8", errors="replace")
    stderr.reconfigure.assert_called_once_with(encoding="utf-8", errors="replace")


def test_configure_stdio_without_reconfigure(monkeypatch):
    monkeypatch.setattr(client.sys, "stdout", object())
    monkeypatch.setattr(client.sys, "stderr", object())
    client.configure_stdio()


def test_wait_for_login_form_incomplete_pair_times_out(fake_driver, monkeypatch):
    fake_driver.add_name_element(USERNAME_FIELD)
    times = iter([0, 1, 100])
    monkeypatch.setattr(client.time, "time", lambda: next(times))
    monkeypatch.setattr(client, "random_delay", lambda *args, **kwargs: None)
    assert not client.wait_for_login_form(
        fake_driver, timeout=5, visible=False, debug=False
    )


def test_resolve_login_fields_skips_hidden_modern_pair(fake_driver, monkeypatch):
    for field_id in ("inputLoginname", "inputPassword"):
        element = fake_driver.add_id_element(field_id)
        monkeypatch.setattr(element, "is_displayed", lambda: False)
    fake_driver.add_name_element(USERNAME_FIELD)
    fake_driver.add_name_element(PASSWORD_FIELD)
    assert client.resolve_login_fields(fake_driver) == (
        (By.NAME, USERNAME_FIELD), (By.NAME, PASSWORD_FIELD)
    )
    assert client.login_form_ready(fake_driver)


def test_wait_for_login_form_reveals_hidden_inputs(fake_driver, monkeypatch):
    fields = [fake_driver.add_id_element(field_id)
              for field_id in ("inputLoginname", "inputPassword")]
    visible = [False]
    for element in fields:
        monkeypatch.setattr(element, "is_displayed", lambda: visible[0])
    link = fake_driver.add_partial_link("Log In")
    original_click = link.click

    def reveal():
        original_click()
        visible[0] = True

    monkeypatch.setattr(link, "click", reveal)
    times = iter([0, 1, 2, 100])
    monkeypatch.setattr(client.time, "time", lambda: next(times))
    monkeypatch.setattr(client, "random_delay", lambda *args, **kwargs: None)
    assert client.wait_for_login_form(
        fake_driver, timeout=5, visible=False, debug=False
    )
    assert link.clicked
