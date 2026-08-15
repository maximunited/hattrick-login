#!/usr/bin/env python3
"""Log in to Hattrick.org and fetch authenticated pages."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from hattrick_client import (
    DASHBOARD_URL,
    configure_stdio,
    export_requests_session,
    fetch_page_with_browser,
    finances_url,
    get_session_dir,
    is_first_run,
    browser_login,
    save_cookies_snapshot,
)

try:
    from dotenv import load_dotenv

    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_NEEDS_HUMAN = 2


def get_credentials() -> tuple[str | None, str | None]:
    return os.getenv("HATTRICK_USERNAME"), os.getenv("HATTRICK_PASSWORD")


def run_login_flow(
    *,
    headless: bool,
    debug: bool,
    fetch: str | None,
    team_id: str | None,
    save_cookies: bool,
) -> int:
    username, password = get_credentials()
    if not username or not password:
        print("ERROR: set HATTRICK_USERNAME and HATTRICK_PASSWORD in .env or the environment")
        return EXIT_ERROR

    driver = None
    try:
        driver, result = browser_login(
            username,
            password,
            headless=headless,
            debug=debug,
        )
        print(result.message)
        if debug:
            print(f"URL: {result.final_url}")
            print(f"Title: {result.title}")

        if not result.ok or driver is None:
            if result.message.startswith("Login form not available"):
                return EXIT_NEEDS_HUMAN
            return EXIT_ERROR

        if fetch == "dashboard":
            status, body = fetch_page_with_browser(driver, DASHBOARD_URL)
            print(f"Dashboard HTTP {status}")
            if status == 200 and ("/MyHattrick/" in body or "Dashboard" in body):
                print("Dashboard fetch looks authenticated.")
            else:
                print(body[:2000])
                return EXIT_ERROR
        elif fetch == "finances":
            if not team_id:
                print("ERROR: set HATTRICK_TEAM_ID or pass --team-id for finances fetch")
                return EXIT_ERROR
            url = finances_url(team_id)
            status, body = fetch_page_with_browser(driver, url)
            print(f"Finances HTTP {status} ({url})")
            if status != 200:
                print(body[:2000])
                return EXIT_ERROR
            print(body[:4000])

        if save_cookies:
            session = export_requests_session(driver)
            cookie_path = get_session_dir() / "cookies.json"
            save_cookies_snapshot(session, cookie_path)
            print(f"Saved cookie snapshot to {cookie_path}")
        return EXIT_OK
    finally:
        if driver is not None:
            driver.quit()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Log in to Hattrick.org")
    parser.add_argument("--visible", action="store_true", help="Force visible browser")
    parser.add_argument("--headless", action="store_true", help="Force headless browser")
    parser.add_argument("--debug", action="store_true", help="Verbose output")
    parser.add_argument(
        "--fetch",
        choices=("dashboard", "finances"),
        help="Fetch a page after login",
    )
    parser.add_argument(
        "--team-id",
        help="Hattrick team ID for finances fetch (overrides HATTRICK_TEAM_ID)",
    )
    parser.add_argument(
        "--save-cookies",
        action="store_true",
        help="Write exported cookies to the session directory",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    args = build_parser().parse_args(argv)

    session_dir = get_session_dir()
    first = is_first_run(session_dir)
    if args.visible:
        headless = False
    elif args.headless:
        headless = True
    else:
        headless = not first
        if first:
            print(
                "First run detected — opening the browser visibly so Cloudflare can be cleared."
            )
            print("Future runs will default to headless using the saved browser profile.")

    team_id = args.team_id or os.getenv("HATTRICK_TEAM_ID")
    return run_login_flow(
        headless=headless,
        debug=args.debug,
        fetch=args.fetch,
        team_id=team_id,
        save_cookies=args.save_cookies,
    )


if __name__ == "__main__":
    raise SystemExit(main())
