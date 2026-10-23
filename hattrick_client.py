"""Hattrick.org login client with persistent browser session."""

from __future__ import annotations

import json
import os
import platform
import random
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

import requests
import undetected_chromedriver as uc
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

LOGIN_URL = "https://www.hattrick.org/en-us/"
DASHBOARD_URL = "https://www.hattrick.org/en-us/MyHattrick/"
USERNAME_FIELD = "ctl00$CPContent$ucLogin$txtUserName"
PASSWORD_FIELD = "ctl00$CPContent$ucLogin$txtPassword"
MODERN_USERNAME_FIELD = "loginname"
MODERN_PASSWORD_FIELD = "password"
AUTH_FAILED_MARKER = "Authentication failed"
CLOUDFLARE_TITLE = "Just a moment"
MARKETING_TITLE_MARKER = "Join the free football world"
LOGIN_LINK_TEXTS = ("Log In", "Log in", "Login")
LOGOUT_LINK_TEXTS = ("Log out", "Logout", "Sign out")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def restrict_private_file(path: Path) -> None:
    """Best-effort owner-only permissions for secrets written to disk."""
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def get_session_dir() -> Path:
    override = os.getenv("HATTRICK_SESSION_DIR")
    if override:
        return Path(override)
    return Path.home() / ".hattrick-session"


def is_first_run(user_data_dir: Path) -> bool:
    network_cookies = user_data_dir / "Default" / "Network" / "Cookies"
    legacy_cookies = user_data_dir / "Default" / "Cookies"
    return not network_cookies.exists() and not legacy_cookies.exists()


def detect_chrome_version_main() -> int | None:
    system = platform.system()
    try:
        if system == "Windows":
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Google\Chrome\BLBeacon",
            )
            version, _ = winreg.QueryValueEx(key, "version")
            match = re.match(r"(\d+)\.", str(version))
            if match:
                return int(match.group(1))
        for binary in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
            try:
                output = subprocess.check_output(
                    [binary, "--version"],
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=5,
                )
            except (FileNotFoundError, subprocess.SubprocessError):
                continue
            match = re.search(r"(\d+)\.", output)
            if match:
                return int(match.group(1))
    except OSError:
        return None
    return None


def random_delay(min_seconds: float, max_seconds: float) -> None:
    time.sleep(random.uniform(min_seconds, max_seconds))


def is_cloudflare_challenge(title: str, page_source: str) -> bool:
    return CLOUDFLARE_TITLE in title or "challenges.cloudflare.com" in page_source


def is_cloudflare_cookie(name: str) -> bool:
    lowered = name.lower()
    return lowered.startswith("cf_") or lowered.startswith("__cf") or lowered == "_cfuvid"


def clear_hattrick_auth_cookies(driver: WebDriver) -> int:
    """Drop Hattrick session cookies while keeping Cloudflare clearance."""
    removed = 0
    for cookie in list(driver.get_cookies()):
        name = cookie.get("name") or ""
        if is_cloudflare_cookie(name):
            continue
        driver.delete_cookie(name)
        removed += 1
    return removed


def is_logged_in_page(title: str, page_source: str, *, require_protected: bool = False) -> bool:
    if AUTH_FAILED_MARKER in page_source:
        return False
    if MARKETING_TITLE_MARKER in title:
        return False
    if USERNAME_FIELD.replace("$", "_") in page_source or 'name="ctl00$CPContent$ucLogin$txtUserName"' in page_source:
        return False
    if 'id="inputPassword"' in page_source and 'id="inputLoginname"' in page_source:
        return False

    protected_markers = ("MyHattrick/Dashboard", "/MyHattrick/", "Club/Finances")
    public_markers = ("Logout", "Log out", "Sign out")

    if require_protected:
        return any(marker in page_source for marker in protected_markers)

    if any(marker in page_source for marker in protected_markers):
        return True
    return any(marker in page_source for marker in public_markers) and "ucLogin" not in page_source


@dataclass(frozen=True)
class LoginResult:
    ok: bool
    message: str
    final_url: str = ""
    title: str = ""


def detect_chrome_binary() -> str | None:
    override = os.getenv("HATTRICK_CHROME_BINARY", "").strip()
    if override:
        return override
    for binary in (
        "google-chrome-stable",
        "google-chrome",
        "chromium-browser",
        "chromium",
    ):
        path = shutil.which(binary)
        if path:
            return path
    return None


def cleanup_stale_chrome_locks(user_data_dir: Path) -> None:
    for relative in (
        "SingletonLock",
        "SingletonSocket",
        "SingletonCookie",
        "Default/SingletonLock",
        "Default/SingletonSocket",
        "Default/SingletonCookie",
    ):
        path = user_data_dir / relative
        try:
            if path.exists() or path.is_symlink():
                path.unlink()
        except OSError:
            pass


def build_chrome_options(user_data_dir: Path, headless: bool) -> uc.ChromeOptions:
    options = uc.ChromeOptions()
    options.add_argument(f"--user-data-dir={user_data_dir}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-setuid-sandbox")
    if platform.system() == "Linux":
        options.add_argument("--disable-gpu")
        options.add_argument("--use-gl=angle")
        options.add_argument("--use-angle=swiftshader")
    if headless:
        options.add_argument("--headless=new")
    return options


def start_browser(user_data_dir: Path, headless: bool, debug: bool = False) -> WebDriver:
    cleanup_stale_chrome_locks(user_data_dir)
    options = build_chrome_options(user_data_dir, headless=headless)
    version_main = detect_chrome_version_main()
    chrome_binary = detect_chrome_binary()
    kwargs: dict[str, object] = {"options": options, "use_subprocess": True}
    if version_main is not None:
        kwargs["version_main"] = version_main
    if chrome_binary is not None:
        kwargs["browser_executable_path"] = chrome_binary
    if debug:
        print(
            "Starting Chrome "
            f"(headless={headless}, version_main={version_main}, binary={chrome_binary})"
        )
    driver = uc.Chrome(**kwargs)
    driver.set_window_size(1920, 1080)
    return driver


def wait_for_login_form(
    driver: WebDriver,
    *,
    timeout: int,
    visible: bool,
    debug: bool,
    prompt: Callable[[str], None] | None = None,
) -> bool:
    deadline = time.time() + timeout
    prompted = False
    clicked_login = False

    while time.time() < deadline:
        title = driver.title
        source = driver.page_source
        if is_cloudflare_challenge(title, source):
            if visible and not prompted:
                message = (
                    "Cloudflare challenge detected. Complete it in the browser, "
                    "then press Enter here to continue."
                )
                if prompt:
                    prompt(message)
                else:
                    input(message + "\n")
                prompted = True
            random_delay(1.0, 2.0)
            continue

        if login_form_ready(driver):
            return True

        if not clicked_login:
            clicked_login = click_login_entry(driver)
            if clicked_login and debug:
                print("Clicked Log In to reveal the login form")

        random_delay(0.5, 1.0)

    return False


def click_login_entry(driver: WebDriver) -> bool:
    """Open the login form from the public marketing page if it is hidden."""
    for text in LOGIN_LINK_TEXTS:
        for link in driver.find_elements(By.PARTIAL_LINK_TEXT, text):
            try:
                click_element(driver, link)
                return True
            except WebDriverException:
                continue
    return False


def click_logout_entry(driver: WebDriver) -> bool:
    """Best-effort logout when cookies alone do not end the Hattrick session."""
    for text in LOGOUT_LINK_TEXTS:
        for link in driver.find_elements(By.PARTIAL_LINK_TEXT, text):
            try:
                click_element(driver, link)
                return True
            except WebDriverException:
                continue
    return False


def resolve_login_fields(driver: WebDriver) -> tuple[tuple[str, str], tuple[str, str]] | None:
    if driver.find_elements(By.ID, "inputLoginname") and driver.find_elements(By.ID, "inputPassword"):
        return (By.ID, "inputLoginname"), (By.ID, "inputPassword")
    if driver.find_elements(By.NAME, USERNAME_FIELD) and driver.find_elements(By.NAME, PASSWORD_FIELD):
        return (By.NAME, USERNAME_FIELD), (By.NAME, PASSWORD_FIELD)
    if driver.find_elements(By.NAME, MODERN_USERNAME_FIELD) and driver.find_elements(
        By.NAME, MODERN_PASSWORD_FIELD
    ):
        return (By.NAME, MODERN_USERNAME_FIELD), (By.NAME, MODERN_PASSWORD_FIELD)
    return None


def login_form_ready(driver: WebDriver) -> bool:
    fields = resolve_login_fields(driver)
    if fields is None:
        return False

    for locator in fields:
        elements = driver.find_elements(*locator)
        if not elements:
            return False
        if not all(
            getattr(element, "is_displayed", lambda: True)()
            for element in elements
        ):
            return False
    return True


def set_input_value(driver: WebDriver, element: object, value: str) -> None:
    """Set an Angular input so ngModel sees the change."""
    driver.execute_script(
        "document.querySelectorAll('iframe, .video-wrapper').forEach("
        "el => { el.style.visibility = 'hidden'; el.style.pointerEvents = 'none'; });"
        "arguments[0].scrollIntoView({block: 'center'});"
        "arguments[0].focus();",
        element,
    )
    try:
        element.click()
        element.clear()
        element.send_keys(value)
        return
    except Exception:  # noqa: BLE001 - fall back to the native value setter
        pass
    driver.execute_script(
        """
        const el = arguments[0];
        const value = arguments[1];
        el.focus();
        const descriptor = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype, 'value'
        );
        if (descriptor && descriptor.set) {
            descriptor.set.call(el, value);
        } else {
            el.value = value;
        }
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        el.dispatchEvent(new Event('blur', { bubbles: true }));
        """,
        element,
        value,
    )


def find_login_submit(driver: WebDriver):
    buttons = driver.find_elements(By.CSS_SELECTOR, "button.primary-button[type='submit']")
    for button in buttons:
        label = (button.text or "").strip().lower()
        if label in {"log in", "login", "sign in"}:
            return button
    if buttons:
        return buttons[0]
    asp = driver.find_elements(By.ID, "ctl00_CPContent_ucUserAuthentication_btnAspLogin")
    if asp:
        return asp[0]
    fallback = driver.find_elements(By.CSS_SELECTOR, "input[type='submit']")
    return fallback[0] if fallback else None


def click_element(driver: WebDriver, element: object) -> None:
    try:
        element.click()
    except Exception:  # noqa: BLE001 - overlays often block native clicks
        driver.execute_script("arguments[0].click();", element)


def submit_login_form(driver: WebDriver, username: str, password: str, debug: bool = False) -> LoginResult:
    fields = resolve_login_fields(driver)
    if fields is None:
        return LoginResult(False, "Login form fields not found")
    user_loc, pass_loc = fields

    wait = WebDriverWait(driver, 30)
    user_input = wait.until(EC.presence_of_element_located(user_loc))
    password_input = wait.until(EC.presence_of_element_located(pass_loc))
    if user_loc[0] == By.ID:
        set_input_value(driver, user_input, username)
        set_input_value(driver, password_input, password)
    else:
        user_input.clear()
        user_input.send_keys(username)
        password_input.clear()
        password_input.send_keys(password)

    if debug:
        lengths = driver.execute_script(
            "const user = document.getElementById('inputLoginname');"
            "const pw = document.getElementById('inputPassword');"
            "return [user && user.value ? user.value.length : 0,"
            " pw && pw.value ? pw.value.length : 0];"
        )
        if isinstance(lengths, (list, tuple)) and len(lengths) == 2:
            print(f"Login field lengths before submit: user={lengths[0]} password={lengths[1]}")

    submit = find_login_submit(driver)
    if submit is None:
        return LoginResult(False, "Login submit button not found")
    if debug:
        print(
            "Submit control:",
            submit.get_attribute("id"),
            submit.get_attribute("value"),
            (submit.text or "").strip(),
        )
    click_element(driver, submit)
    random_delay(2.0, 4.0)
    if debug:
        print("After submit:", driver.current_url, driver.title)

    page_source = driver.page_source
    if AUTH_FAILED_MARKER in page_source:
        return LoginResult(False, "Authentication failed", driver.current_url, driver.title)

    if is_logged_in_page(driver.title, page_source):
        return verify_logged_in(driver, debug=debug)

    try:
        wait.until(
            lambda d: AUTH_FAILED_MARKER in d.page_source
            or is_logged_in_page(d.title, d.page_source)
        )
    except TimeoutException:
        return LoginResult(
            False,
            "Login result unclear after submit",
            driver.current_url,
            driver.title,
        )

    page_source = driver.page_source
    if AUTH_FAILED_MARKER in page_source:
        return LoginResult(False, "Authentication failed", driver.current_url, driver.title)
    if is_logged_in_page(driver.title, page_source):
        return verify_logged_in(driver, debug=debug)
    return LoginResult(False, "Login result unclear", driver.current_url, driver.title)


def browser_login(
    username: str,
    password: str,
    *,
    headless: bool,
    debug: bool = False,
    prompt: Callable[[str], None] | None = None,
    force_fresh_login: bool = False,
) -> tuple[WebDriver | None, LoginResult]:
    session_dir = get_session_dir()
    session_dir.mkdir(parents=True, exist_ok=True)

    try:
        driver = start_browser(session_dir, headless=headless, debug=debug)
    except Exception as exc:  # noqa: BLE001 - driver startup is a hard failure boundary
        return None, LoginResult(False, f"Failed to start Chrome: {exc}")

    try:
        if debug:
            print(f"Opening {LOGIN_URL}")
        driver.get(LOGIN_URL)
        random_delay(2.0, 4.0)

        already_logged_in = is_logged_in_page(driver.title, driver.page_source)
        if already_logged_in and not force_fresh_login:
            verified = verify_logged_in(driver, debug=debug)
            return driver, verified

        if force_fresh_login:
            removed = clear_hattrick_auth_cookies(driver)
            if debug:
                print(
                    "Fresh login requested; "
                    f"cleared {removed} Hattrick cookie(s)."
                )
            driver.get(LOGIN_URL)
            random_delay(2.0, 4.0)

            if is_logged_in_page(driver.title, driver.page_source):
                if click_logout_entry(driver):
                    if debug:
                        print("Clicked logout after cookie clearing.")
                    driver.get(LOGIN_URL)
                    random_delay(2.0, 4.0)

                if is_logged_in_page(driver.title, driver.page_source):
                    # Give the site a short opportunity to present the login form,
                    # but do not spend the full form timeout if the session persists.
                    if not wait_for_login_form(
                        driver,
                        timeout=15,
                        visible=not headless,
                        debug=debug,
                        prompt=prompt,
                    ):
                        return driver, LoginResult(
                            False,
                            "Existing session could not be cleared for fresh login",
                            driver.current_url,
                            driver.title,
                        )

        if not wait_for_login_form(
            driver,
            timeout=120 if headless else 180,
            visible=not headless,
            debug=debug,
            prompt=prompt,
        ):
            return driver, LoginResult(
                False,
                "Login form not available (Cloudflare challenge may still be active)",
                driver.current_url,
                driver.title,
            )

        result = submit_login_form(driver, username, password, debug=debug)
        return driver, result
    except Exception as exc:  # noqa: BLE001 - keep browser alive for debugging when possible
        return driver, LoginResult(False, f"Unexpected browser error: {exc}")


def is_hattrick_host(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host == "hattrick.org" or host.endswith(".hattrick.org")


def is_authenticated_dashboard_url(url: str) -> bool:
    if "ReturnUrl=" in url:
        return False
    return is_hattrick_host(url) and "/MyHattrick/" in urlparse(url).path


def dashboard_url_for(driver: WebDriver) -> str:
    raw = getattr(driver, "current_url", "") or ""
    if not isinstance(raw, str) or not is_hattrick_host(raw):
        return DASHBOARD_URL
    parsed = urlparse(raw)
    return f"{parsed.scheme}://{parsed.netloc}/MyHattrick/"


def verify_logged_in(driver: WebDriver, debug: bool = False) -> LoginResult:
    if not is_authenticated_dashboard_url(driver.current_url):
        target = dashboard_url_for(driver)
        if debug:
            print(f"Verifying session at {target}")
        driver.get(target)
        random_delay(2.0, 4.0)
    elif debug:
        print(f"Verifying session at {driver.current_url}")

    if not is_authenticated_dashboard_url(driver.current_url):
        if is_cloudflare_challenge(driver.title, driver.page_source):
            return LoginResult(
                False,
                "Cloudflare challenge blocked dashboard access",
                driver.current_url,
                driver.title,
            )
        return LoginResult(False, "Not authenticated", driver.current_url, driver.title)
    if is_logged_in_page(driver.title, driver.page_source, require_protected=True):
        return LoginResult(True, "Login successful", driver.current_url, driver.title)
    if is_cloudflare_challenge(driver.title, driver.page_source):
        return LoginResult(
            False,
            "Cloudflare challenge blocked dashboard access",
            driver.current_url,
            driver.title,
        )
    return LoginResult(False, "Not authenticated", driver.current_url, driver.title)


def fetch_page_with_browser(driver: WebDriver, url: str) -> tuple[int, str]:
    driver.get(url)
    random_delay(1.5, 3.0)
    if is_cloudflare_challenge(driver.title, driver.page_source):
        return 403, driver.page_source
    return 200, driver.page_source


def export_requests_session(driver: WebDriver) -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": DEFAULT_USER_AGENT})
    for cookie in driver.get_cookies():
        session.cookies.set(
            cookie["name"],
            cookie["value"],
            domain=cookie.get("domain"),
            path=cookie.get("path", "/"),
        )
    return session


def fetch_authenticated_page(session: requests.Session, url: str) -> tuple[int, str]:
    response = session.get(url, timeout=30)
    return response.status_code, response.text


def finances_url(team_id: str) -> str:
    return f"https://www.hattrick.org/Club/Finances/?teamId={team_id}"


def save_cookies_snapshot(session: requests.Session, path: Path) -> None:
    cookies = [
        {
            "name": cookie.name,
            "value": cookie.value,
            "domain": cookie.domain,
            "path": cookie.path,
        }
        for cookie in session.cookies
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cookies, indent=2), encoding="utf-8")
    restrict_private_file(path)


def load_cookies_snapshot(path: Path) -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": DEFAULT_USER_AGENT})
    cookies = json.loads(path.read_text(encoding="utf-8"))
    for cookie in cookies:
        session.cookies.set(
            cookie["name"],
            cookie["value"],
            domain=cookie.get("domain"),
            path=cookie.get("path", "/"),
        )
    return session


def configure_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
