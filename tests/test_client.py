from hattrick_client import (
    AUTH_FAILED_MARKER,
    CLOUDFLARE_TITLE,
    is_cloudflare_challenge,
    is_logged_in_page,
    is_first_run,
    finances_url,
)


def test_cloudflare_detection():
    assert is_cloudflare_challenge("Just a moment...", "<html></html>")
    assert not is_cloudflare_challenge("Hattrick", "<html></html>")


def test_logged_in_detection():
    assert is_logged_in_page("Dashboard", "<html>/MyHattrick/Dashboard</html>", require_protected=True)
    assert not is_logged_in_page("Login", f"<html>{AUTH_FAILED_MARKER}</html>")
    assert not is_logged_in_page(
        "Hattrick",
        '<html><input name="ctl00$CPContent$ucLogin$txtUserName"></html>',
    )


def test_first_run(tmp_path):
    assert is_first_run(tmp_path)


def test_finances_url():
    assert finances_url("1844625").endswith("teamId=1844625")
