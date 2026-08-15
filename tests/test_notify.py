import urllib.error
from unittest.mock import MagicMock, patch

import hattrick_notify as notify
from hattrick_notify import DEFAULT_NTFY_SERVER, build_ntfy_url, sanitize_ntfy_server, sanitize_ntfy_topic


def test_get_ntfy_config_missing():
    with patch.dict("os.environ", {}, clear=True):
        assert notify.get_ntfy_config() is None


def test_get_ntfy_config_from_env():
    with patch.dict(
        "os.environ",
        {
            "HATTRICK_NTFY_TOPIC": "my-topic",
            "HATTRICK_NTFY_SERVER": "https://ntfy.example.com",
            "HATTRICK_NTFY_TOKEN": "secret",
        },
        clear=True,
    ):
        config = notify.get_ntfy_config()
        assert config is not None
        assert config.topic == "my-topic"
        assert config.server == "https://ntfy.example.com"
        assert config.token == "secret"


def test_get_ntfy_config_legacy_env_names():
    with patch.dict(
        "os.environ",
        {
            "NTFY_TOPIC": "legacy-topic",
            "NTFY_SERVER": "https://ntfy.example.com/",
            "NTFY_TOKEN": "legacy-token",
        },
        clear=True,
    ):
        config = notify.get_ntfy_config()
        assert config is not None
        assert config.topic == "legacy-topic"
        assert config.server == "https://ntfy.example.com"
        assert config.token == "legacy-token"


def test_sanitize_ntfy_server_rejects_unsafe_values():
    assert sanitize_ntfy_server("file:///etc/passwd") == DEFAULT_NTFY_SERVER
    assert sanitize_ntfy_server("https://ntfy.sh/evil/path") == DEFAULT_NTFY_SERVER
    assert sanitize_ntfy_server("https://user:pass@ntfy.example.com") == DEFAULT_NTFY_SERVER


def test_sanitize_ntfy_server_accepts_valid_base_url():
    assert sanitize_ntfy_server("https://ntfy.example.com/") == "https://ntfy.example.com"


def test_sanitize_ntfy_topic_rejects_path_injection():
    assert sanitize_ntfy_topic("good-topic") == "good-topic"
    assert sanitize_ntfy_topic("../admin") == ""
    assert sanitize_ntfy_topic("topic/with/slash") == ""


def test_build_ntfy_url_encodes_topic():
    assert build_ntfy_url("https://ntfy.sh", "my-topic") == "https://ntfy.sh/my-topic"


def test_get_ntfy_config_rejects_unsafe_topic():
    with patch.dict("os.environ", {"HATTRICK_NTFY_TOPIC": "../secret"}, clear=True):
        assert notify.get_ntfy_config() is None


def test_get_ntfy_config_blank_token_becomes_none():
    with patch.dict(
        "os.environ",
        {"HATTRICK_NTFY_TOPIC": "topic", "HATTRICK_NTFY_TOKEN": "   "},
        clear=True,
    ):
        config = notify.get_ntfy_config()
        assert config is not None
        assert config.token is None


def test_notify_keepalive_success(monkeypatch):
    with patch.dict("os.environ", {"HATTRICK_NTFY_TOPIC": "my-topic"}, clear=True):
        response = MagicMock()
        response.status = 200
        response.__enter__ = MagicMock(return_value=response)
        response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=response) as urlopen:
            sent = notify.notify_keepalive(
                success=True,
                message="ok",
                exit_code=0,
                debug=True,
            )

        assert sent is True
        request = urlopen.call_args.args[0]
        assert request.full_url.endswith("/my-topic")
        assert request.data.decode("utf-8") == "ok"
        assert request.headers["Title"] == "Hattrick keepalive OK"
        assert "white_check_mark" in request.headers["Tags"]


def test_notify_keepalive_failure_headers(monkeypatch):
    with patch.dict("os.environ", {"HATTRICK_NTFY_TOPIC": "my-topic"}, clear=True):
        response = MagicMock()
        response.status = 200
        response.__enter__ = MagicMock(return_value=response)
        response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=response) as urlopen:
            sent = notify.notify_keepalive(success=False, message="", exit_code=2)

        assert sent is True
        request = urlopen.call_args.args[0]
        assert request.headers["Title"] == "Hattrick keepalive failed (2)"
        assert request.headers["Priority"] == "high"
        assert request.data.decode("utf-8") == "Hattrick keepalive failed (2)"


def test_notify_keepalive_uses_bearer_token():
    with patch.dict(
        "os.environ",
        {"HATTRICK_NTFY_TOPIC": "secure-topic", "HATTRICK_NTFY_TOKEN": "token123"},
        clear=True,
    ):
        response = MagicMock()
        response.status = 200
        response.__enter__ = MagicMock(return_value=response)
        response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=response) as urlopen:
            notify.notify_keepalive(success=True, message="ok", exit_code=0)

        request = urlopen.call_args.args[0]
        assert request.headers["Authorization"] == "Bearer token123"


def test_notify_keepalive_failure_without_topic():
    with patch.dict("os.environ", {}, clear=True):
        assert notify.notify_keepalive(success=False, message="bad", exit_code=1) is False


def test_notify_keepalive_network_error(capsys):
    with patch.dict("os.environ", {"HATTRICK_NTFY_TOPIC": "my-topic"}, clear=True):
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
            sent = notify.notify_keepalive(success=False, message="bad", exit_code=1)

    assert sent is False
    assert "WARNING: ntfy notify failed" in capsys.readouterr().out
