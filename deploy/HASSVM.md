# hassvm deployment notes

## What is installed

- Repo: `~/projects/hattrick-login`
- Env: `~/projects/hattrick-login/.env`
- ntfy topic: `malter_hattrick`
- systemd user timer: every 14 days via Docker
- crontab safety net: 1st and 15th at 09:00

## Cloudflare caveat

Hattrick blocks headless/server logins from hassvm. FlareSolverr (already on `:8191`) also timed out on the challenge.

Until a Linux browser session is seeded successfully once, scheduled runs will fail and ntfy will alert you.

## First successful Linux session

Use X11 to your desktop once to seed the Linux profile:

```bash
export DISPLAY=your-windows-ip:0.0   # VcXsrv / X410 / etc.
cd ~/projects/hattrick-login
./deploy/hassvm-run.sh --keepalive --visible --debug
```

## Headless / scheduled runs

After the profile exists, headless uses the same native Chromium under xvfb (not Docker):

```bash
unset DISPLAY
./deploy/hassvm-run.sh --keepalive --headless --debug
```

Docker is optional (`HATTRICK_USE_DOCKER=1`) but not recommended — root in the container fights the user-owned Chrome profile.

After one successful Linux login, Docker headless runs should reuse `/data/session` in the `hattrick-login_hattrick-session` volume.

## Commands

```bash
# manual run
cd ~/projects/hattrick-login
docker compose run --rm keepalive

# logs
journalctl --user -u hattrick-keepalive.service -n 50
tail -f ~/.local/share/hattrick-login/cron.log
```
