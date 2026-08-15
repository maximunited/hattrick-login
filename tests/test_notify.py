import json
from unittest.mock import MagicMock, patch

import hattrick_notify as notify


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
            )

        assert sent is True
        request = urlopen.call_args.args[0]
        assert request.full_url.endswith("/my-topic")
        assert request.data.decode("utf-8") == "ok"
        assert request.headers["Title"] == "Hattrick keepalive OK"


def test_notify_keepalive_failure_without_topic():
    with patch.dict("os.environ", {}, clear=True):
        assert notify.notify_keepalive(success=False, message="bad", exit_code=1) is False
