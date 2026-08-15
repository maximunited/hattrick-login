# Hattrick Login

Automates login to [Hattrick.org](https://www.hattrick.org/) and can fetch authenticated pages after login.

Migrated from the personal scripts that lived on `hassvm` at `~/scripts/hattrick_login/`.

## Why a browser?

Hattrick is behind Cloudflare now. The old `requests`-only scripts in `legacy/` return HTTP 403 and no longer work reliably. This tool uses `undetected-chromedriver` with a persistent Chrome profile, similar to [indiegala-auto-spin](https://github.com/maximunited/indiegala-auto-spin).

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
./run.sh
```

## First run

On first run the script opens Chrome visibly so you can clear the Cloudflare challenge if one appears. After that, the saved browser profile is reused and later runs default to headless.

```bash
python hattrick_login.py --debug
```

If Cloudflare appears again, rerun with `--visible`.

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
| `HATTRICK_SESSION_DIR` | no | Chrome profile + cookie snapshot directory |

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
