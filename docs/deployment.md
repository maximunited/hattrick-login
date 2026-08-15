# Deployment

## Windows (manual / Task Scheduler)

```bat
git clone https://github.com/maximunited/hattrick-login
cd hattrick-login
python -m venv venv
venv\Scripts\pip install -r requirements.txt
copy .env.example .env
REM edit .env
run.bat --keepalive --visible --debug
```

After the first visible success:

```bat
run.bat --keepalive --headless
```

Task Scheduler tips:

- Run only after a successful visible seed
- Treat exit code `2` as "open visible browser once"
- Point the task at `run.bat --keepalive --headless`

## Linux (generic)

```bash
git clone https://github.com/maximunited/hattrick-login ~/projects/hattrick-login
cd ~/projects/hattrick-login
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env
./run.sh --keepalive --visible --debug
```

## hassvm (recommended production path)

See also [deploy/HASSVM.md](../deploy/HASSVM.md).

### 1. Install

```bash
git clone https://github.com/maximunited/hattrick-login ~/projects/hattrick-login
cd ~/projects/hattrick-login
cp .env.example .env
# edit .env with credentials + HATTRICK_NTFY_TOPIC
./deploy/install-hassvm.sh
```

This installs:

- systemd user timer (every 14 days)
- crontab safety net (1st and 15th at 09:00)

### 2. Seed the Linux browser profile once

Cloudflare requires a real browser clearance at least once per OS profile:

```bash
export DISPLAY=your-windows-ip:0.0   # VcXsrv / X410 / etc.
cd ~/projects/hattrick-login
./deploy/hassvm-run.sh --keepalive --visible --debug
```

### 3. Verify unattended keepalive

```bash
unset DISPLAY
./deploy/hassvm-run.sh --keepalive --headless --debug
```

Expected: login or session reuse, dashboard HTTP 200, ntfy notification, `ok: true` in `keepalive.jsonl`.

### hassvm routing logic

| Condition | Path |
| --------- | ---- |
| `DISPLAY` set | Native snap Chromium via `./run.sh` |
| `DISPLAY` unset, Docker available | Docker Google Chrome under xvfb as your uid |
| `HATTRICK_NATIVE=1` or no Docker | Native Chromium under local xvfb |

## Docker (direct)

```bash
cp .env.example .env
# edit .env
docker compose build
docker compose run --rm --user "$(id -u):$(id -g)" keepalive --keepalive --headless --debug
```

Requirements:

- Bind-mount your session directory (default `~/.hattrick-session`)
- Seed the profile with a successful run before expecting Cloudflare to pass unattended
- `shm_size: 2gb` is already set in `docker-compose.yml`

## systemd user timer

```bash
./deploy/install-systemd.sh
systemctl --user enable --now hattrick-keepalive.timer
systemctl --user status hattrick-keepalive.timer
journalctl --user -u hattrick-keepalive.service -n 50
```

## cron alternative

See `deploy/crontab.example` for a twice-monthly entry.

Log output is typically appended to `~/.local/share/hattrick-login/cron.log` when using the hassvm installer.

## Post-deploy checklist

- [ ] Visible seed completed on the target OS
- [ ] Unattended `--keepalive --headless` succeeds once
- [ ] ntfy success and failure messages received
- [ ] `keepalive.jsonl` shows `"ok": true`
- [ ] `.env` is not world-readable (`chmod 600 .env`)
