#!/usr/bin/env bash
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"

if [[ -f "${repo}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${repo}/.env"
  set +a
fi

# SSH sessions have no DISPLAY; host snap Chromium breaks undetected-chromedriver.
# Use the Docker image (Google Chrome + xvfb) unless explicitly forced native.
if [[ -z "${DISPLAY:-}" && "${HATTRICK_NATIVE:-}" != "1" && -f "${repo}/docker-compose.yml" ]] \
  && command -v docker >/dev/null 2>&1; then
  cd "${repo}"
  exec docker compose run --rm keepalive
fi

lib_dir="${HOME}/lib/chromium-deps/usr/lib/x86_64-linux-gnu"
export LD_LIBRARY_PATH="${lib_dir}${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"

if [[ ! -f "${lib_dir}/libnspr4.so" ]]; then
  mkdir -p "${HOME}/lib/chromium-deps"
  tmp="$(mktemp -d)"
  (
    cd "${tmp}"
    apt-get download -o Dir::Cache="${tmp}" libnspr4 libnss3 >/dev/null
    for deb in libnspr4*.deb libnss3*.deb; do
      dpkg-deb -x "${deb}" "${HOME}/lib/chromium-deps/"
    done
  )
  rm -rf "${tmp}"
fi

if [[ -z "${DISPLAY:-}" ]] && command -v xvfb-run >/dev/null 2>&1; then
  exec xvfb-run -a "${repo}/run.sh" "$@"
fi

cd "${repo}"
exec ./run.sh "$@"
