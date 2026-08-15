# Security Policy

## Supported Versions

Security fixes are applied to the latest commit on `main`.

## Reporting a Vulnerability

Do not open a public issue for credential leaks, session theft, or other security problems.

Instead:

1. Open a [private security advisory](https://github.com/maximunited/hattrick-login/security/advisories/new) on GitHub, or
2. Contact the maintainer through an existing private channel if you already have one.

Include steps to reproduce, affected versions, and impact if known. You should receive an acknowledgment within a few days.

## Sensitive Data

Never commit `.env`, browser profiles, cookie exports, or keepalive logs. This repository ships `.env.example` only.

Operational security guidance: [docs/security.md](docs/security.md)
