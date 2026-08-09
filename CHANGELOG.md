# Changelog

**Project branding:** ZKas Dual Alert — Unofficial Community Tool. Independent community software; not affiliated with or endorsed by the ZKas project.

## v0.2.2 - 2026-08-09
- Stable Windows installer targeting `C:\ProgramData\ZKasDualAlert`.
- Automatic startup through Windows Task Scheduler with a 90-second boot delay.
- Automatic background monitor startup from the web application.
- ZKAS and KAS block alerts.
- KAS reward alert support when reward information is exposed by the bridge.
- Bridge offline and recovered alerts.
- Gmail/SMTP and Discord webhook notifications.
- Safe simulated ZKAS/KAS block tests.
- Per-channel notification success/failure reporting.
- JSON `/api/stats` telemetry with Prometheus `/metrics` fallback.
- Local-only web UI on `127.0.0.1:3040` by default.
- Credentials and runtime state moved into a protected Windows data directory.
