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

ensure_xvfb() {
  if command -v xvfb-run >/dev/null 2>&1; then
    return 0
  fi
  local root="${HOME}/lib/xvfb"
  if [[ -x "${root}/usr/bin/xvfb-run" ]]; then
    export PATH="${root}/usr/bin:${PATH}"
    return 0
  fi
  mkdir -p "${root}"
  local tmp
  tmp="$(mktemp -d)"
  (
    cd "${tmp}"
    apt-get download -o Dir::Cache="${tmp}" xvfb xauth >/dev/null
    for deb in xvfb*.deb xauth*.deb; do
      dpkg-deb -x "${deb}" "${root}/"
    done
  )
  rm -rf "${tmp}"
  export PATH="${root}/usr/bin:${PATH}"
}

ensure_chrome_libs

if [[ -z "${DISPLAY:-}" && "${HATTRICK_USE_DOCKER:-}" == "1" && -f "${repo}/docker-compose.yml" ]] \
  && command -v docker >/dev/null 2>&1; then
  cd "${repo}"
  exec docker compose run --rm keepalive "$@"
fi

export HATTRICK_CHROME_BINARY="${HATTRICK_CHROME_BINARY:-/usr/bin/chromium-browser}"

if [[ -z "${DISPLAY:-}" ]]; then
  ensure_xvfb
  args=()
  for arg in "$@"; do
    if [[ "${arg}" == "--headless" ]]; then
      continue
    fi
    args+=("${arg}")
  done
  has_keepalive=false
  for arg in "${args[@]}"; do
    [[ "${arg}" == "--keepalive" ]] && has_keepalive=true
  done
  if [[ "${has_keepalive}" == "true" ]]; then
    exec xvfb-run -a "${repo}/run.sh" --keepalive --visible "${args[@]}"
  fi
  exec xvfb-run -a "${repo}/run.sh" "${args[@]}"
fi

cd "${repo}"
exec ./run.sh "$@"
