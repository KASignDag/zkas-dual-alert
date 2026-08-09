# ZKas Dual Alert v0.2.2 — Unofficial Community Tool

Cleanup / release-candidate build.

**Unofficial Community Tool:** independently developed and not affiliated with, endorsed by, sponsored by, or maintained by the ZKas project or its developers.

- Fixed the leftover `v0.1.0 monitoring` label.
- Replaced the fragile WindowsApps Python alias with automatic real-Python discovery.
- Added a stable Windows install location under `C:\ProgramData\ZKasDualAlert`.
- Added automatic migration of v0.2.x settings/state.
- Added a protected `data` directory for settings, state, logs, and notification credentials.
- Changed the monitor from a child process to an in-process background thread to reduce duplicate/orphan monitor risk.
- Added safe ZKAS/KAS block simulations.
- Test notifications now report actual Email/Discord success or failure instead of showing a generic success when a channel failed.
- Saved SMTP passwords and Discord webhooks are no longer rendered back into the web page.
- Added INSTALL, UPDATE, VERIFY, and startup scripts.
- Phone Push and SMS/Text remain Coming Soon.
