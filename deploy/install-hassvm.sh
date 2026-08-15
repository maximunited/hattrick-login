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

unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p "${unit_dir}"
cat >"${unit_dir}/hattrick-keepalive.service" <<EOF
[Unit]
Description=Hattrick keepalive login
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=${repo}
EnvironmentFile=-${repo}/.env
ExecStart=${repo}/deploy/hassvm-run.sh --keepalive --headless
Nice=10

[Install]
WantedBy=default.target
EOF
cp "${repo}/deploy/systemd/hattrick-keepalive.timer" "${unit_dir}/hattrick-keepalive.timer"
systemctl --user daemon-reload
systemctl --user enable --now hattrick-keepalive.timer

mkdir -p "${HOME}/.local/share/hattrick-login"
( crontab -l 2>/dev/null | grep -v 'hattrick-login' || true
  echo "0 9 1,15 * * ${repo}/deploy/hassvm-run.sh --keepalive --headless >> ${HOME}/.local/share/hattrick-login/cron.log 2>&1"
) | crontab -

echo "Installed hassvm keepalive timer + crontab safety net."
systemctl --user list-timers hattrick-keepalive.timer
