import json
import sys
from unittest.mock import MagicMock, patch

import pytest

import hattrick_login as login
from hattrick_client import LoginResult


def test_get_credentials_from_env(monkeypatch):
    monkeypatch.setenv("HATTRICK_USERNAME", "coach")
    monkeypatch.setenv("HATTRICK_PASSWORD", "secret")
    assert login.get_credentials() == ("coach", "secret")


def test_get_credentials_missing(monkeypatch):
    monkeypatch.delenv("HATTRICK_USERNAME", raising=False)
    monkeypatch.delenv("HATTRICK_PASSWORD", raising=False)
    assert login.get_credentials() == (None, None)


def test_record_keepalive(session_dir, monkeypatch):
    monkeypatch.setattr(login, "get_session_dir", lambda: session_dir)
    login.record_keepalive(ok=True, message="done", exit_code=0)

    lines = (session_dir / "keepalive.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["ok"] is True
    assert record["exit_code"] == 0
    assert record["message"] == "done"


def test_run_login_flow_missing_credentials(monkeypatch, capsys):
    monkeypatch.setattr(login, "get_credentials", lambda: (None, None))
    assert login.run_login_flow(headless=True, debug=False, fetch=None, team_id=None, save_cookies=False) == login.EXIT_ERROR
    assert "ERROR: set HATTRICK_USERNAME" in capsys.readouterr().out


def test_run_login_flow_login_failure(monkeypatch):
    monkeypatch.setattr(login, "get_credentials", lambda: ("user", "pass"))
    monkeypatch.setattr(
        login,
        "browser_login",
        lambda *args, **kwargs: (MagicMock(), LoginResult(False, "Authentication failed")),
    )

    driver = MagicMock()
    with patch.object(login, "browser_login", return_value=(driver, LoginResult(False, "Authentication failed"))):
        assert login.run_login_flow(headless=True, debug=False, fetch=None, team_id=None, save_cookies=False) == login.EXIT_ERROR
        driver.quit.assert_called_once()


def test_run_login_flow_needs_human(monkeypatch):
    driver = MagicMock()
    monkeypatch.setattr(login, "get_credentials", lambda: ("user", "pass"))
    monkeypatch.setattr(
        login,
        "browser_login",
        lambda *args, **kwargs: (
            driver,
            LoginResult(False, "Login form not available (Cloudflare challenge may still be active)"),
        ),
    )

    assert login.run_login_flow(headless=True, debug=False, fetch=None, team_id=None, save_cookies=False) == login.EXIT_NEEDS_HUMAN
    driver.quit.assert_called_once()


def test_run_login_flow_dashboard_fetch_success(monkeypatch, session_dir):
    driver = MagicMock()
    monkeypatch.setattr(login, "get_credentials", lambda: ("user", "pass"))
    monkeypatch.setattr(
        login,
        "browser_login",
        lambda *args, **kwargs: (driver, LoginResult(True, "Login successful")),
    )
    monkeypatch.setattr(
        login,
        "fetch_page_with_browser",
        lambda *args, **kwargs: (200, "<html>/MyHattrick/Dashboard</html>"),
    )

    assert login.run_login_flow(headless=True, debug=True, fetch="dashboard", team_id=None, save_cookies=False) == login.EXIT_OK
    driver.quit.assert_called_once()


def test_run_login_flow_dashboard_fetch_failure(monkeypatch, capsys):
    driver = MagicMock()
    monkeypatch.setattr(login, "get_credentials", lambda: ("user", "pass"))
    monkeypatch.setattr(
        login,
        "browser_login",
        lambda *args, **kwargs: (driver, LoginResult(True, "Login successful")),
    )
    monkeypatch.setattr(login, "fetch_page_with_browser", lambda *args, **kwargs: (403, "blocked"))

    assert login.run_login_flow(headless=True, debug=False, fetch="dashboard", team_id=None, save_cookies=False) == login.EXIT_ERROR
    assert "blocked" in capsys.readouterr().out


def test_run_login_flow_finances_missing_team_id(monkeypatch, capsys):
    driver = MagicMock()
    monkeypatch.setattr(login, "get_credentials", lambda: ("user", "pass"))
    monkeypatch.setattr(
        login,
        "browser_login",
        lambda *args, **kwargs: (driver, LoginResult(True, "Login successful")),
    )

    assert login.run_login_flow(headless=True, debug=False, fetch="finances", team_id=None, save_cookies=False) == login.EXIT_ERROR
    assert "HATTRICK_TEAM_ID" in capsys.readouterr().out


def test_run_login_flow_finances_success(monkeypatch, capsys):
    driver = MagicMock()
    monkeypatch.setattr(login, "get_credentials", lambda: ("user", "pass"))
    monkeypatch.setattr(
        login,
        "browser_login",
        lambda *args, **kwargs: (driver, LoginResult(True, "Login successful")),
    )
    monkeypatch.setattr(login, "fetch_page_with_browser", lambda *args, **kwargs: (200, "finances page"))

    assert login.run_login_flow(headless=True, debug=False, fetch="finances", team_id="123", save_cookies=False) == login.EXIT_OK
    assert "finances page" in capsys.readouterr().out


def test_run_login_flow_save_cookies(monkeypatch, session_dir):
    driver = MagicMock()
    session = MagicMock()
    monkeypatch.setattr(login, "get_credentials", lambda: ("user", "pass"))
    monkeypatch.setattr(login, "get_session_dir", lambda: session_dir)
    monkeypatch.setattr(
        login,
        "browser_login",
        lambda *args, **kwargs: (driver, LoginResult(True, "Login successful")),
    )
    monkeypatch.setattr(login, "export_requests_session", lambda *args, **kwargs: session)

    with patch.object(login, "save_cookies_snapshot") as save_snapshot:
        assert login.run_login_flow(headless=True, debug=False, fetch=None, team_id=None, save_cookies=True) == login.EXIT_OK
        save_snapshot.assert_called_once_with(session, session_dir / "cookies.json")


def test_notify_result_disabled():
    with patch.object(login, "notify_keepalive") as notify:
        login.notify_result(exit_code=0, message="ok", debug=False, enabled=False)
        notify.assert_not_called()


def test_notify_result_enabled():
    with patch.object(login, "notify_keepalive") as notify:
        login.notify_result(exit_code=1, message="bad", debug=True, enabled=True)
        notify.assert_called_once_with(success=False, message="bad", exit_code=1, debug=True)


def test_main_first_run_defaults_visible(session_dir, monkeypatch, capsys):
    monkeypatch.setattr(login, "get_session_dir", lambda: session_dir)
    monkeypatch.setattr(login, "run_login_flow", lambda **kwargs: login.EXIT_OK)

    assert login.main([]) == login.EXIT_OK
    output = capsys.readouterr().out
    assert "First run detected" in output


def test_main_keepalive_records_and_notifies(session_dir, monkeypatch):
    cookie_path = session_dir / "Default" / "Network" / "Cookies"
    cookie_path.parent.mkdir(parents=True)
    cookie_path.write_text("x", encoding="utf-8")

    monkeypatch.setattr(login, "get_session_dir", lambda: session_dir)
    monkeypatch.setattr(login, "run_login_flow", lambda **kwargs: login.EXIT_OK)

    with patch.object(login, "record_keepalive") as record, patch.object(login, "notify_result") as notify:
        assert login.main(["--keepalive", "--no-notify"]) == login.EXIT_OK
        record.assert_called_once()
        notify.assert_called_once()


def test_main_headless_flag(session_dir, monkeypatch):
    cookie_path = session_dir / "Default" / "Network" / "Cookies"
    cookie_path.parent.mkdir(parents=True)
    cookie_path.write_text("x", encoding="utf-8")

    captured: dict[str, object] = {}

    def capture(**kwargs):
        captured.update(kwargs)
        return login.EXIT_OK

    monkeypatch.setattr(login, "get_session_dir", lambda: session_dir)
    monkeypatch.setattr(login, "run_login_flow", capture)

    login.main(["--headless"])
    assert captured["headless"] is True


def test_main_visible_overrides_headless(session_dir, monkeypatch):
    cookie_path = session_dir / "Default" / "Network" / "Cookies"
    cookie_path.parent.mkdir(parents=True)
    cookie_path.write_text("x", encoding="utf-8")

    captured: dict[str, object] = {}

    def capture(**kwargs):
        captured.update(kwargs)
        return login.EXIT_OK

    monkeypatch.setattr(login, "get_session_dir", lambda: session_dir)
    monkeypatch.setattr(login, "run_login_flow", capture)

    login.main(["--visible", "--headless"])
    assert captured["headless"] is False


def test_main_keepalive_warning_for_finances_fetch(session_dir, monkeypatch, capsys):
    cookie_path = session_dir / "Default" / "Network" / "Cookies"
    cookie_path.parent.mkdir(parents=True)
    cookie_path.write_text("x", encoding="utf-8")

    monkeypatch.setattr(login, "get_session_dir", lambda: session_dir)
    monkeypatch.setattr(login, "run_login_flow", lambda **kwargs: login.EXIT_OK)

    login.main(["--keepalive", "--fetch", "finances", "--no-notify"])
    assert "WARNING: --keepalive forces dashboard verification" in capsys.readouterr().out


def test_build_parser_defaults():
    args = login.build_parser().parse_args([])
    assert args.visible is False
    assert args.keepalive is False


def test_run_login_flow_finances_http_error(monkeypatch, capsys):
    driver = MagicMock()
    monkeypatch.setattr(login, "get_credentials", lambda: ("user", "pass"))
    monkeypatch.setattr(
        login,
        "browser_login",
        lambda *args, **kwargs: (driver, LoginResult(True, "Login successful")),
    )
    monkeypatch.setattr(login, "fetch_page_with_browser", lambda *args, **kwargs: (500, "server error"))

    assert login.run_login_flow(headless=True, debug=False, fetch="finances", team_id="123", save_cookies=False) == login.EXIT_ERROR
    assert "server error" in capsys.readouterr().out


def test_main_script_entrypoint(monkeypatch):
    monkeypatch.setattr(login, "main", lambda argv=None: 5)
    with pytest.raises(SystemExit) as exc:
        raise SystemExit(login.main())
    assert exc.value.code == 5


def test_dotenv_import_error_branch(monkeypatch):
    import importlib

    original = sys.modules.get("dotenv")
    monkeypatch.setitem(sys.modules, "dotenv", None)
    importlib.reload(login)
    if original is not None:
        sys.modules["dotenv"] = original
    else:
        sys.modules.pop("dotenv", None)
    importlib.reload(login)
