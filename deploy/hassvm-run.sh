#!/usr/bin/env bash
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
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

if [[ ! -f "${HOME}/.hattrick-session/Default/Network/Cookies" && ! -f "${HOME}/.hattrick-session/Default/Cookies" ]]; then
  if command -v xvfb-run >/dev/null 2>&1; then
    exec xvfb-run -a "${repo}/run.sh" --keepalive --visible "$@"
  fi
fi

cd "${repo}"
exec ./run.sh "$@"
