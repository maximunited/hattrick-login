# Hattrick Login

Automates login to [Hattrick.org](https://www.hattrick.org/) and can fetch authenticated pages after login.

Migrated from the personal scripts that lived on `hassvm` at `~/scripts/hattrick_login/`.

## Why a browser?

Hattrick is behind Cloudflare now. The old `requests`-only scripts in `legacy/` return HTTP 403 and no longer work reliably. This tool uses `undetected-chromedriver` with a persistent Chrome profile, similar to [indiegala-auto-spin](https://github.com/maximunited/indiegala-auto-spin).

Hattrick deletes inactive teams after about **7 weeks without a website login**. This tool is meant to keep that from happening.

## Setup

```bash
cd hattrick-login
python -m venv venv
pip install -r requirements.txt
cp .env.example .env
# edit .env
```

Windows:

```bat
run.bat
```

Linux:

```bash
chmod +x run.sh deploy/install-systemd.sh
./run.sh
```

## First run

On first run the script opens Chrome visibly so you can clear the Cloudflare challenge if one appears. After that, the saved browser profile is reused and later runs default to headless.

```bash
python hattrick_login.py --keepalive --visible --debug
```

If Cloudflare appears again, rerun with `--visible`.

## Keepalive mode

For schedulers:

```bash
python hattrick_login.py --keepalive --headless
```

This logs in if needed, verifies `/MyHattrick/`, appends a line to `~/.hattrick-session/keepalive.jsonl`, and sends ntfy if configured.

## ntfy.sh notifications

Set a private topic in `.env`:

```env
HATTRICK_NTFY_TOPIC=your-private-topic
```

Optional:

```env
HATTRICK_NTFY_SERVER=https://ntfy.sh
HATTRICK_NTFY_TOKEN=your-token-if-topic-is-protected
```

Notifications fire on both success and failure unless you pass `--no-notify`.

## Automate every 2 weeks

### systemd user timer (recommended)

```bash
git clone https://github.com/maximunited/hattrick-login ~/projects/hattrick-login
cd ~/projects/hattrick-login
cp .env.example .env
# edit .env, then do one visible keepalive first
./deploy/install-systemd.sh
```

The timer runs 30 minutes after boot, then every 14 days after the last successful timer activation.

Check status:

```bash
systemctl --user status hattrick-keepalive.timer
journalctl --user -u hattrick-keepalive.service -n 50
```

### cron alternative

See `deploy/crontab.example` for a twice-monthly cron entry.

## Usage

Login only:

```bash
python hattrick_login.py
```

Fetch dashboard after login:

```bash
python hattrick_login.py --fetch dashboard
```

Fetch finances page:

```bash
python hattrick_login.py --fetch finances --team-id 1844625
```

Save exported cookies to the session directory:

```bash
python hattrick_login.py --save-cookies
```

## Environment variables

| Variable | Required | Purpose |
| -------- | -------- | ------- |
| `HATTRICK_USERNAME` | yes | Hattrick login name |
| `HATTRICK_PASSWORD` | yes | Hattrick password |
| `HATTRICK_TEAM_ID` | no | Default team ID for `--fetch finances` |
| `HATTRICK_SESSION_DIR` | no | Chrome profile + keepalive log directory |
| `HATTRICK_NTFY_TOPIC` | no | ntfy topic for success/failure alerts |
| `HATTRICK_NTFY_SERVER` | no | ntfy server URL (default `https://ntfy.sh`) |
| `HATTRICK_NTFY_TOKEN` | no | Bearer token for protected topics |

## Exit codes

| Code | Meaning |
| ---- | ------- |
| `0` | Success |
| `1` | Hard failure |
| `2` | Needs human interaction (Cloudflare/login form unavailable in headless mode) |

## Legacy scripts

The original hassvm scripts are kept under `legacy/` for reference. They are sanitized and documented as obsolete for current Hattrick access.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```
