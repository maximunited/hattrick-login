# Operations

Day‑2 reference for monitoring and maintaining scheduled keepalive runs.

## Schedules

| Mechanism | Schedule | Entrypoint |
| --------- | -------- | ---------- |
| systemd user timer | Every 14 days | `deploy/hassvm-run.sh --keepalive --headless` |
| crontab safety net | 1st and 15th, 09:00 | same as above |

Biweekly login is intentionally conservative relative to Hattrick's ~7 week deletion window.

## keepalive audit log

Path: `$HATTRICK_SESSION_DIR/keepalive.jsonl` (default `~/.hattrick-session/keepalive.jsonl`).

Each line is JSON:

```json
{"ts": "2026-08-15T16:34:46.611499+00:00", "ok": true, "exit_code": 0, "message": "Dashboard verified; account keepalive succeeded."}
```

Quick checks:

```bash
tail -5 ~/.hattrick-session/keepalive.jsonl
jq 'select(.ok==false)' ~/.hattrick-session/keepalive.jsonl
```

## Notifications

When `HATTRICK_NTFY_TOPIC` is configured:

- Success → `Hattrick keepalive OK`
- Failure → `Hattrick keepalive failed (<exit_code>)` with high priority

Alerts fire unless `--no-notify` is passed.

## Monitoring checklist

Weekly (or after changes):

- [ ] Last `keepalive.jsonl` entry is recent and `"ok": true`
- [ ] ntfy test message received on manual run
- [ ] No stuck Docker keepalive containers (`docker ps --filter name=hattrick`)

Monthly:

- [ ] Rotate ntfy token if your threat model requires it
- [ ] Confirm disk use of Chrome profile is reasonable

## Updating the deployment

```bash
cd ~/projects/hattrick-login
git pull
./deploy/hassvm-run.sh --keepalive --headless --debug
```

If Docker files changed:

```bash
docker compose build keepalive
```

Re-run `./deploy/install-hassvm.sh` only when installer scripts themselves changed.

## Tests and coverage

```bash
pip install -r requirements-dev.txt
pytest
```

Coverage settings live in `pyproject.toml` (90% minimum gate).

## Legacy scripts

`legacy/` contains the old hassvm `requests` scripts. They are sanitized references only and should not be scheduled.
