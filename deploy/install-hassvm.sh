#!/usr/bin/env bash
set -euo pipefail

repo="${1:-$HOME/projects/hattrick-login}"
cd "${repo}"

chmod +x run.sh deploy/hassvm-run.sh deploy/install-systemd.sh

if [[ ! -f .env ]]; then
  echo "Missing ${repo}/.env — copy .env.example and edit credentials first." >&2
  exit 1
fi

if [[ ! -d venv ]]; then
  python3 -m venv venv
  ./venv/bin/pip install -r requirements.txt
fi

# Native timer using wrapper that supplies Chrome libs without sudo
./deploy/install-systemd.sh "${repo}"

# Replace ExecStart to use hassvm wrapper
unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
sed "s|ExecStart=.*|ExecStart=${repo}/deploy/hassvm-run.sh --keepalive --headless|" \
  "${unit_dir}/hattrick-keepalive.service" >"${unit_dir}/hattrick-keepalive.service.tmp"
mv "${unit_dir}/hattrick-keepalive.service.tmp" "${unit_dir}/hattrick-keepalive.service"
systemctl --user daemon-reload
systemctl --user enable --now hattrick-keepalive.timer

# User crontab backup timer on 1st/15th as a safety net
mkdir -p "${HOME}/.local/share/hattrick-login"
( crontab -l 2>/dev/null | grep -v 'hattrick-login/deploy/hassvm-run.sh' || true
  echo "0 9 1,15 * * ${repo}/deploy/hassvm-run.sh --keepalive --headless >> ${HOME}/.local/share/hattrick-login/cron.log 2>&1"
) | crontab -

echo "Installed hassvm keepalive timer + crontab safety net."
systemctl --user list-timers hattrick-keepalive.timer
