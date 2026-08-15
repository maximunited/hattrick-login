#!/usr/bin/env bash
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"

if [[ -f "${repo}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${repo}/.env"
  set +a
fi

lib_dir="${HOME}/lib/chromium-deps/usr/lib/x86_64-linux-gnu"
export LD_LIBRARY_PATH="${lib_dir}${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"

ensure_chrome_libs() {
  if [[ -f "${lib_dir}/libnspr4.so" ]]; then
    return 0
  fi
  mkdir -p "${HOME}/lib/chromium-deps"
  local tmp
  tmp="$(mktemp -d)"
  (
    cd "${tmp}"
    apt-get download -o Dir::Cache="${tmp}" libnspr4 libnss3 >/dev/null
    for deb in libnspr4*.deb libnss3*.deb; do
      dpkg-deb -x "${deb}" "${HOME}/lib/chromium-deps/"
    done
  )
  rm -rf "${tmp}"
}

run_native_with_xvfb() {
  ensure_chrome_libs
  export HATTRICK_CHROME_BINARY="${HATTRICK_CHROME_BINARY:-/usr/bin/chromium-browser}"
  cd "${repo}"

  local args=()
  local arg
  for arg in "$@"; do
    if [[ "${arg}" == "--headless" ]]; then
      continue
    fi
    args+=("${arg}")
  done

  mkdir -p /tmp/.X11-unix
  chmod 1777 /tmp/.X11-unix 2>/dev/null || true
  export DISPLAY=:99
  if ! pgrep -f "Xvfb ${DISPLAY} " >/dev/null 2>&1; then
    Xvfb "${DISPLAY}" -screen 0 1920x1080x24 -nolisten tcp &
    for _ in $(seq 1 50); do
      if [[ -S "/tmp/.X11-unix/X${DISPLAY#:}" ]]; then
        break
      fi
      sleep 0.1
    done
  fi

  # Cloudflare blocks true headless; keep a real window under xvfb when Docker is unavailable.
  exec ./run.sh --visible "${args[@]}"
}

# Real X display: native host Chromium (what worked with DISPLAY=windows-ip:0.0)
if [[ -n "${DISPLAY:-}" ]]; then
  ensure_chrome_libs
  export HATTRICK_CHROME_BINARY="${HATTRICK_CHROME_BINARY:-/usr/bin/chromium-browser}"
  cd "${repo}"
  exec ./run.sh "$@"
fi

# No display: Docker Google Chrome under xvfb, running as host user for profile access
if [[ -f "${repo}/docker-compose.yml" ]] && command -v docker >/dev/null 2>&1 \
  && [[ "${HATTRICK_NATIVE:-}" != "1" ]]; then
  cd "${repo}"
  exec docker compose run --rm --user "$(id -u):$(id -g)" keepalive "$@"
fi

ensure_chrome_libs
export HATTRICK_CHROME_BINARY="${HATTRICK_CHROME_BINARY:-/usr/bin/chromium-browser}"
run_native_with_xvfb "$@"
