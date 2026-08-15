# Contributing

Thanks for helping improve hattrick-login.

## Setup

```bash
git clone https://github.com/maximunited/hattrick-login.git
cd hattrick-login
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
```

Do not commit real credentials or browser session data.

## Development

```bash
pytest
python hattrick_login.py --keepalive --visible --debug
```

For hassvm-specific behavior, see [deploy/HASSVM.md](deploy/HASSVM.md).

## Pull Requests

1. Branch from `main`.
2. Keep changes focused.
3. Add or update tests when behavior changes.
4. Use [conventional commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `chore:`, `test:`).
5. Confirm `pytest` passes locally.

## Reporting Bugs

Open an issue with environment details (OS, Docker/native, visible/headless path), command run, and relevant log output. Redact credentials and session paths.
