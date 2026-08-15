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

SSH has no display; `./deploy/hassvm-run.sh` automatically uses Docker (Google Chrome + xvfb) unless you set `HATTRICK_NATIVE=1`.

```bash
cd ~/projects/hattrick-login
git pull
./deploy/hassvm-run.sh --keepalive --visible --debug
```

That runs inside Docker with a virtual display. Force broken host snap Chromium only if you really want native:

```bash
HATTRICK_NATIVE=1 ./deploy/hassvm-run.sh --keepalive --visible --debug
```

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
