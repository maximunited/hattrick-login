"""Optional ntfy.sh notifications for keepalive runs."""

from __future__ import annotations

import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

DEFAULT_NTFY_SERVER = "https://ntfy.sh"
_ALLOWED_NTFY_SCHEMES = frozenset({"https", "http"})
_UNSAFE_TOPIC = re.compile(r"[\s/\\?#@:%]")


@dataclass(frozen=True)
class NtfyConfig:
    server: str
    topic: str
    token: str | None = None


def sanitize_ntfy_server(raw: str) -> str:
    """Return a safe ntfy base URL or the default public server."""
    candidate = raw.strip().rstrip("/") or DEFAULT_NTFY_SERVER
    parsed = urllib.parse.urlparse(candidate)
    if parsed.scheme not in _ALLOWED_NTFY_SCHEMES or not parsed.hostname:
        return DEFAULT_NTFY_SERVER
    if parsed.username or parsed.password:
        return DEFAULT_NTFY_SERVER
    if parsed.path not in ("", "/"):
        return DEFAULT_NTFY_SERVER
    if parsed.params or parsed.query or parsed.fragment:
        return DEFAULT_NTFY_SERVER
    return f"{parsed.scheme}://{parsed.netloc}"


def sanitize_ntfy_topic(raw: str) -> str:
    """Return a topic safe for path construction, or empty when invalid."""
    topic = raw.strip()
    if not topic or _UNSAFE_TOPIC.search(topic):
        return ""
    return topic


def build_ntfy_url(server: str, topic: str) -> str:
    base = server.rstrip("/") + "/"
    return urllib.parse.urljoin(base, urllib.parse.quote(topic, safe="-_."))


def get_ntfy_config() -> NtfyConfig | None:
    topic = sanitize_ntfy_topic(
        os.getenv("HATTRICK_NTFY_TOPIC", os.getenv("NTFY_TOPIC", ""))
    )
    if not topic:
        return None
    server = sanitize_ntfy_server(
        os.getenv("HATTRICK_NTFY_SERVER", os.getenv("NTFY_SERVER", DEFAULT_NTFY_SERVER))
    )
    token = os.getenv("HATTRICK_NTFY_TOKEN", os.getenv("NTFY_TOKEN", "")).strip() or None
    return NtfyConfig(server=server, topic=topic, token=token)


def notify_keepalive(
    *,
    success: bool,
    message: str,
    exit_code: int,
    debug: bool = False,
) -> bool:
    """Send a keepalive result to ntfy.sh. Returns True if a notification was sent."""
    config = get_ntfy_config()
    if config is None:
        return False

    title = "Hattrick keepalive OK" if success else f"Hattrick keepalive failed ({exit_code})"
    tags = ["white_check_mark", "soccer"] if success else ["x", "warning", "soccer"]
    priority = "default" if success else "high"
    body = message.strip() or title

    headers = {
        "User-Agent": "hattrick-login",
        "Title": title,
        "Tags": ",".join(tags),
        "Priority": priority,
    }
    if config.token:
        headers["Authorization"] = f"Bearer {config.token}"

    request = urllib.request.Request(
        build_ntfy_url(config.server, config.topic),
        data=body.encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if debug:
                print(f"ntfy notified: HTTP {response.status}")
            return True
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"WARNING: ntfy notify failed: {exc}")
        return False
