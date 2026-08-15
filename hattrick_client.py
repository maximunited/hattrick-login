"""Hattrick.org login client with persistent browser session."""

from __future__ import annotations

import json
import os
import platform
import random
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import requests
import undetected_chromedriver as uc
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

LOGIN_URL = "https://www.hattrick.org/en-us/"
DASHBOARD_URL = "https://www.hattrick.org/en-us/MyHattrick/"
USERNAME_FIELD = "ctl00$CPContent$ucLogin$txtUserName"
PASSWORD_FIELD = "ctl00$CPContent$ucLogin$txtPassword"
AUTH_FAILED_MARKER = "Authentication failed"
CLOUDFLARE_TITLE = "Just a moment"

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


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
            return int(match.group(1)) if match else None
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


def is_logged_in_page(title: str, page_source: str, *, require_protected: bool = False) -> bool:
    if AUTH_FAILED_MARKER in page_source:
        return False
    if USERNAME_FIELD.replace("$", "_") in page_source or 'name="ctl00$CPContent$ucLogin$txtUserName"' in page_source:
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


def build_chrome_options(user_data_dir: Path, headless: bool) -> uc.ChromeOptions:
    options = uc.ChromeOptions()
    options.add_argument(f"--user-data-dir={user_data_dir}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-setuid-sandbox")
    if headless:
        options.add_argument("--headless=new")
    return options


def start_browser(user_data_dir: Path, headless: bool, debug: bool = False) -> WebDriver:
    options = build_chrome_options(user_data_dir, headless=headless)
    version_main = detect_chrome_version_main()
    kwargs: dict[str, object] = {"options": options, "use_subprocess": True}
    if version_main is not None:
        kwargs["version_main"] = version_main
    if debug:
        print(f"Starting Chrome (headless={headless}, version_main={version_main})")
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

        if driver.find_elements(By.NAME, USERNAME_FIELD):
            return True

        random_delay(0.5, 1.0)

    return False


def submit_login_form(driver: WebDriver, username: str, password: str, debug: bool = False) -> LoginResult:
    wait = WebDriverWait(driver, 30)
    user_input = wait.until(EC.presence_of_element_located((By.NAME, USERNAME_FIELD)))
    user_input.clear()
    user_input.send_keys(username)
    driver.find_element(By.NAME, PASSWORD_FIELD).clear()
    driver.find_element(By.NAME, PASSWORD_FIELD).send_keys(password)

    submit = driver.find_elements(By.CSS_SELECTOR, "input[type='submit']")
    if not submit:
        return LoginResult(False, "Login submit button not found")
    submit[0].click()
    random_delay(2.0, 4.0)

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

        if is_logged_in_page(driver.title, driver.page_source):
            verified = verify_logged_in(driver, debug=debug)
            return driver, verified

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


def verify_logged_in(driver: WebDriver, debug: bool = False) -> LoginResult:
    if debug:
        print(f"Verifying session at {DASHBOARD_URL}")
    driver.get(DASHBOARD_URL)
    random_delay(2.0, 4.0)
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
