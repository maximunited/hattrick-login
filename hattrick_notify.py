"""Optional ntfy.sh notifications for keepalive runs."""

from __future__ import annotations

import os
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class NtfyConfig:
    server: str
    topic: str
    token: str | None = None


def get_ntfy_config() -> NtfyConfig | None:
    topic = os.getenv("HATTRICK_NTFY_TOPIC", os.getenv("NTFY_TOPIC", "")).strip()
    if not topic:
        return None
    server = os.getenv("HATTRICK_NTFY_SERVER", os.getenv("NTFY_SERVER", "https://ntfy.sh")).rstrip("/")
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
        f"{config.server}/{config.topic}",
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
