# Configuration

## Environment variables

Copy `.env.example` to `.env` for local runs. Schedulers should inject the same values through systemd, cron, or Docker Compose.

| Variable | Required | Default | Purpose |
| -------- | -------- | ------- | ------- |
| `HATTRICK_USERNAME` | yes | — | Hattrick login name |
| `HATTRICK_PASSWORD` | yes | — | Hattrick password |
| `HATTRICK_TEAM_ID` | no | — | Default team ID for `--fetch finances` |
| `HATTRICK_SESSION_DIR` | no | `~/.hattrick-session` | Chrome profile, keepalive log, cookie export directory |
| `HATTRICK_CHROME_BINARY` | no | auto-detect | Chrome/Chromium executable path |
| `HATTRICK_NTFY_TOPIC` | no | — | ntfy topic name |
| `HATTRICK_NTFY_SERVER` | no | `https://ntfy.sh` | ntfy server base URL (`http`/`https` only) |
| `HATTRICK_NTFY_TOKEN` | no | — | Bearer token for protected topics |
| `HATTRICK_NATIVE` | no | unset | hassvm: force native Chromium + xvfb instead of Docker |

Legacy aliases `NTFY_TOPIC`, `NTFY_SERVER`, and `NTFY_TOKEN` are still accepted.

## CLI flags

| Flag | Effect |
| ---- | ------ |
| `--visible` | Force a visible browser window |
| `--headless` | Force headless Chrome (may fail against Cloudflare) |
| `--keepalive` | Login, verify dashboard, write `keepalive.jsonl`, notify |
| `--debug` | Verbose logging |
| `--fetch dashboard` | Fetch dashboard HTML after login |
| `--fetch finances` | Fetch finances page (`--team-id` or `HATTRICK_TEAM_ID`) |
| `--save-cookies` | Write `cookies.json` into the session directory |
| `--no-notify` | Skip ntfy even when configured |
| `--team-id` | Override `HATTRICK_TEAM_ID` |

If neither `--visible` nor `--headless` is passed:

- First run (no saved cookies) defaults to **visible**
- Later runs default to **headless**

## Example `.env`

```env
HATTRICK_USERNAME=your-hattrick-username
HATTRICK_PASSWORD=your-hattrick-password
HATTRICK_NTFY_TOPIC=your-private-topic
HATTRICK_NTFY_SERVER=https://ntfy.sh
# HATTRICK_NTFY_TOKEN=optional-bearer-token
```

## ntfy topic guidance

- Use a long, unguessable topic name
- Prefer a protected topic with `HATTRICK_NTFY_TOKEN`
- Do not reuse a public topic name

The client rejects topic names containing `/`, whitespace, or other URL-special characters to prevent request URL manipulation.

## Chrome profile notes

- Do not copy a Windows profile to Linux (or vice versa) — seed each OS once with `--visible`
- The profile contains Cloudflare and Hattrick session cookies; treat it like a password
- Delete the profile directory to force a fresh login + Cloudflare clearance
