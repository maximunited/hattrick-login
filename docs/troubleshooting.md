# Troubleshooting

## Exit codes

| Code | Meaning | Typical fix |
| ---- | ------- | ----------- |
| `0` | Success | None |
| `1` | Hard failure | Read stderr / logs, rerun with `--debug` |
| `2` | Needs human interaction | Rerun with `--visible` and clear Cloudflare |

## Common errors

### `Failed to start Chrome: ... chrome not reachable`

Usually Chrome crashed before chromedriver connected.

Checklist:

- Remove stale locks: `rm -f ~/.hattrick-session/Singleton* ~/.hattrick-session/Default/Singleton*`
- On hassvm without `DISPLAY`, use `./deploy/hassvm-run.sh` (Docker path), not raw `./run.sh --headless`
- Ensure only one keepalive run uses the profile at a time
- In Docker, confirm the container runs as your uid and `shm_size: 2gb` is set

### `Login form not available (Cloudflare challenge may still be active)`

Cloudflare is still blocking the session.

Fix:

```bash
./deploy/hassvm-run.sh --keepalive --visible --debug
# or locally:
python hattrick_login.py --keepalive --visible --debug
```

Complete the browser challenge, then retry unattended mode.

### `Authentication failed`

Wrong username/password in `.env`, or Hattrick rejected the login.

Verify credentials with a manual browser login first.

### Docker / xvfb hangs with no output

Older builds used `xvfb-run` as PID 1 inside Docker, which could hang forever. Update to the latest `deploy/docker-entrypoint.sh` (manual Xvfb startup).

### `/usr/bin/env: 'bash\r': No such file or directory`

Shell scripts checked out with Windows CRLF line endings. Convert to LF:

```bash
sed -i 's/\r$//' deploy/hassvm-run.sh deploy/docker-entrypoint.sh run.sh
```

The repository `.gitattributes` enforces LF for shell scripts going forward.

### ntfy notifications missing

- Confirm `HATTRICK_NTFY_TOPIC` is set in `.env`
- Test with `--debug` and look for `ntfy notified: HTTP 200`
- Check topic/token on your ntfy server
- Invalid topic names (slashes, spaces) are rejected silently — use alphanumeric + `_`/`-`

### Profile copied from Windows breaks Linux Chrome

Delete the Linux profile and re-seed locally:

```bash
mv ~/.hattrick-session ~/.hattrick-session.bak
./deploy/hassvm-run.sh --keepalive --visible --debug
```

## Useful commands

```bash
# latest keepalive results
tail -3 ~/.hattrick-session/keepalive.jsonl

# hassvm systemd logs
journalctl --user -u hattrick-keepalive.service -n 50

# cron log
tail -f ~/.local/share/hattrick-login/cron.log

# direct docker smoke test
docker compose run --rm --user "$(id -u):$(id -g)" keepalive --keepalive --headless --debug
```

## Still stuck?

Open an issue with:

- OS / deployment path (Windows, hassvm Docker, hassvm native)
- Exact command run
- Exit code
- Redacted `--debug` output

Do **not** attach `.env`, cookie exports, or your Chrome profile.
