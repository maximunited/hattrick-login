#!/usr/bin/env bash
set -euo pipefail

cd /app

export HOME=/tmp/chrome-home
mkdir -p "${HOME}"

start_xvfb() {
  if [[ -n "${DISPLAY:-}" ]]; then
    return 0
  fi
  mkdir -p /tmp/.X11-unix
  chmod 1777 /tmp/.X11-unix 2>/dev/null || true
  export DISPLAY=:99
  Xvfb "${DISPLAY}" -screen 0 1920x1080x24 -nolisten tcp &
  XVFB_PID=$!
  for _ in $(seq 1 50); do
    if [[ -S "/tmp/.X11-unix/X${DISPLAY#:}" ]]; then
      return 0
    fi
    sleep 0.1
  done
  echo "Xvfb failed to become ready on ${DISPLAY}" >&2
  exit 1
}

stop_xvfb() {
  if [[ -n "${XVFB_PID:-}" ]]; then
    kill "${XVFB_PID}" 2>/dev/null || true
  fi
}

trap stop_xvfb EXIT
start_xvfb

# Cloudflare blocks true headless; keep a real window under xvfb for scheduled runs.
exec python -u hattrick_login.py --keepalive --visible "$@"
