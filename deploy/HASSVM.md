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

Pick one:

1. From a machine with a desktop, SSH with X11 forwarding and run:

   ```bash
   ssh -X hassvm
   cd ~/projects/hattrick-login
   ./deploy/hassvm-run.sh --keepalive --visible --debug
   ```

2. Keep using your Windows session on a biweekly Task Scheduler job as the primary keepalive until hassvm login succeeds once.

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
