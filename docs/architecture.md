# Architecture

## Goal

Keep a Hattrick.org account active by performing a real website login before the ~7 week inactivity deletion window. The tool verifies authenticated access to `/MyHattrick/` and optionally alerts you through ntfy.sh.

## Components

```text
hattrick_login.py   CLI entrypoint, scheduling hooks, keepalive audit log
hattrick_client.py  Browser session, Cloudflare-aware login flow, cookie export
hattrick_notify.py  Optional ntfy.sh notifications
deploy/*            hassvm wrappers, systemd/cron installers, Docker entrypoint
legacy/*            Obsolete requests-only scripts (reference only)
```

## Login flow

1. Load credentials from the environment (`.env` locally, env vars in Docker/systemd).
2. Open Chrome through `undetected-chromedriver` with a persistent profile in `HATTRICK_SESSION_DIR` (default `~/.hattrick-session`).
3. Navigate to `https://www.hattrick.org/en-us/`.
4. If already authenticated, skip the login form and verify the dashboard.
5. If Cloudflare appears, a visible browser run lets you clear the challenge once; later runs reuse cookies from the saved profile.
6. Submit the Hattrick login form when needed.
7. Verify `https://www.hattrick.org/en-us/MyHattrick/` contains protected content.
8. Optionally fetch additional pages (`--fetch`) or export cookies (`--save-cookies`).

## Keepalive mode

`--keepalive` is the scheduler-facing path:

- Forces dashboard verification after login
- Appends one JSON line to `keepalive.jsonl`
- Sends ntfy success/failure notifications unless `--no-notify` is set

Exit code `2` means human interaction is required (usually Cloudflare in a headless context).

## hassvm unattended path

When `DISPLAY` is unset, `deploy/hassvm-run.sh` routes scheduled runs through Docker:

- Google Chrome inside the container
- Manual Xvfb startup (not `xvfb-run` as PID 1)
- Host user ID so the bind-mounted Chrome profile stays owned by you
- Visible Chrome under xvfb to satisfy Cloudflare

Manual seeding still uses native Chromium with X11 to your desktop once.

## Data written to disk

| Path | Contents | Sensitivity |
| ---- | -------- | ----------- |
| `~/.hattrick-session/` | Chrome profile, Cloudflare cookies | High |
| `keepalive.jsonl` | Timestamped run results | Medium |
| `cookies.json` | Exported HTTP cookies when `--save-cookies` is used | High |

Sensitive files are chmod `600` where the OS supports it.

## External dependencies

| Service | Purpose |
| ------- | ------- |
| Hattrick.org | Target site |
| Chrome / Chromium | Browser automation |
| ntfy.sh (optional) | Push notifications |
| Docker + Xvfb (hassvm) | Unattended Linux runs |

FlareSolverr is **not** used by this project; it did not reliably bypass Hattrick's Cloudflare challenge during testing.
