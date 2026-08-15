# hassvm deployment notes

Detailed deployment guide: [docs/deployment.md](../docs/deployment.md)

Troubleshooting: [docs/troubleshooting.md](../docs/troubleshooting.md)

## What is installed

- Repo: `~/projects/hattrick-login`
- Env: `~/projects/hattrick-login/.env`
- ntfy topic: `malter_hattrick`
- systemd user timer: every 14 days
- crontab safety net: 1st and 15th at 09:00

## Cloudflare caveat

Hattrick blocks true headless Chrome from hassvm. Scheduled runs use **visible Chrome under xvfb** inside Docker (Google Chrome, not snap Chromium).

FlareSolverr (already on `:8191`) also timed out on the challenge.

## First successful Linux session

Use X11 to your desktop once to seed the Linux profile:

```bash
export DISPLAY=your-windows-ip:0.0   # VcXsrv / X410 / etc.
cd ~/projects/hattrick-login
./deploy/hassvm-run.sh --keepalive --visible --debug
```

That uses native snap Chromium with your real display.

## Scheduled / unattended runs

When `DISPLAY` is unset, `deploy/hassvm-run.sh` runs Docker as your uid with the profile bind-mounted:

```bash
unset DISPLAY
./deploy/hassvm-run.sh --keepalive --headless --debug
```

The `--headless` flag is kept for systemd/cron compatibility; the container still launches visible Chrome under xvfb so Cloudflare accepts the session.

Force native snap Chromium (Docker unavailable or `HATTRICK_NATIVE=1`; uses visible Chrome under xvfb):

```bash
HATTRICK_NATIVE=1 ./deploy/hassvm-run.sh --keepalive --headless --debug
```

## Commands

```bash
# manual run (same path as timer)
cd ~/projects/hattrick-login
./deploy/hassvm-run.sh --keepalive --headless --debug

# direct docker
docker compose run --rm --user "$(id -u):$(id -g)" keepalive --keepalive --headless --debug

# logs
journalctl --user -u hattrick-keepalive.service -n 50
tail -f ~/.local/share/hattrick-login/cron.log
tail -f ~/.hattrick-session/keepalive.jsonl
```
