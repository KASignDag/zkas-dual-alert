# Security Policy

> **ZKas Dual Alert — Unofficial Community Tool.** This project is independently developed and is not affiliated with, endorsed by, sponsored by, or maintained by the ZKas project or its developers.

## Scope
ZKas Dual Alert — Unofficial Community Tool is a read-only monitoring companion. It does not need wallet seed phrases, private keys, spending permissions, miner control, or node-control credentials.

## Local-only web interface
The web UI binds to `127.0.0.1:3040` by default. Do not expose port 3040 directly to the public Internet. Change the default `admin / 12345678` login password after installation.

## Stored notification credentials
SMTP passwords and Discord webhook URLs are stored locally under `C:\ProgramData\ZKasDualAlert\data`. The Windows installer restricts that directory to SYSTEM and Administrators. Treat Discord webhook URLs and Gmail App Passwords as secrets and rotate them if they are ever exposed.

## What must never be submitted in an issue
Do not post seed phrases, private keys, wallet files, viewing keys, signatures, Gmail App Passwords, Discord webhook URLs, access tokens, or other credentials.

## Reporting a vulnerability
Open a GitHub issue only for non-sensitive security questions. For an actual vulnerability that would require publishing a secret or exploit details, use GitHub's private vulnerability reporting feature if it is enabled for the repository.
