# Security

This document expands the repository [SECURITY.md](../SECURITY.md) with operational guidance.

## Threat model

The tool stores enough state to act as you on hattrick.org:

- `.env` holds your password
- The Chrome profile holds Cloudflare and Hattrick session cookies
- Optional `cookies.json` exports HTTP cookies in plain JSON

Assume anyone with read access to those files can access your account.

## Secrets handling

| Asset | Guidance |
| ----- | -------- |
| `.env` | Never commit. `chmod 600 .env` on Linux. Restrict directory ACLs on Windows. |
| Chrome profile | Keep under your home directory. Do not sync via cloud backup unless encrypted. |
| `cookies.json` | Only create with `--save-cookies` when needed. Delete when done. |
| ntfy topic/token | Use a private topic. Prefer token-protected topics on public ntfy servers. |

## Built-in hardening

- `.env`, session dirs, and cookie exports are gitignored
- `keepalive.jsonl` and `cookies.json` are chmod `600` after write (best effort)
- ntfy server URLs must use `http`/`https` with no embedded credentials or extra path segments; invalid values fall back to `https://ntfy.sh`
- ntfy topics containing `/`, whitespace, or URL-special characters are rejected
- Notification URLs are built with `urllib.parse.urljoin` + quoting

## What this tool does **not** protect against

- Malware on the same machine reading your profile or `.env`
- Shoulder surfing during a visible Cloudflare clearance
- Hattrick or Cloudflare policy changes blocking automation
- Leaking logs that you paste into public issues (redact paths, topics, and cookies)

## Reporting vulnerabilities

Use [GitHub private security advisories](https://github.com/maximunited/hattrick-login/security/advisories/new). Do not open public issues for exploit details.

## Recovery after suspected compromise

1. Change your Hattrick password immediately
2. Delete `HATTRICK_SESSION_DIR` entirely
3. Rotate your ntfy topic/token if notifications were configured
4. Re-run a visible keepalive to seed a fresh profile
5. Review `keepalive.jsonl` for unexpected timestamps

## Safe logging practices

When opening issues or sharing logs:

- Redact `HATTRICK_USERNAME`, password, and ntfy token
- Remove cookie values and Cloudflare clearance tokens
- Replace absolute home paths with `~/.hattrick-session` placeholders

## Docker notes

- Compose bind-mounts your real profile into the container
- Containers run as your uid (`--user $(id -u):$(id -g)`) so profile ownership stays consistent
- Do not run the keepalive container as root against a user-owned profile
