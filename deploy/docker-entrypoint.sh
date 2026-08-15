#!/usr/bin/env bash
set -euo pipefail

cd /app

network_cookies="/data/session/Default/Network/Cookies"
legacy_cookies="/data/session/Default/Cookies"

if [[ ! -f "${network_cookies}" && ! -f "${legacy_cookies}" ]]; then
  exec xvfb-run -a python hattrick_login.py --keepalive --visible "$@"
fi

exec python hattrick_login.py --keepalive --headless "$@"
