#!/usr/bin/env bash
set -euo pipefail

repo="${1:-$HOME/projects/hattrick-login}"
unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

mkdir -p "$unit_dir"

sed "s|%h/projects/hattrick-login|${repo}|g" \
  "$repo/deploy/systemd/hattrick-keepalive.service" \
  >"$unit_dir/hattrick-keepalive.service"

cp "$repo/deploy/systemd/hattrick-keepalive.timer" "$unit_dir/hattrick-keepalive.timer"

systemctl --user daemon-reload
systemctl --user enable --now hattrick-keepalive.timer
systemctl --user list-timers hattrick-keepalive.timer

echo
echo "Installed user timer. Check logs with:"
echo "  journalctl --user -u hattrick-keepalive.service -n 50"
