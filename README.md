# ZKas Dual Alert v0.2.2

## Unofficial Community Tool

**ZKas Dual Alert is an independent, community-developed utility. It is not affiliated with, endorsed by, sponsored by, or maintained by the ZKas project or its developers.** The ZKas name is used only to describe compatibility with ZKas/Kaspa mining setups.

Read-only block and bridge alerts for compatible ZKas/Kaspa `solo-dual-mode` setups.

## What is ready now
- Local web setup UI: `http://127.0.0.1:3040`
- Default login: `admin` / `12345678`
- Automatic background monitor
- ZKAS block alerts
- KAS block alerts
- KAS reward alerts when reward data is exposed by the bridge
- Bridge offline / recovered alerts
- Gmail/SMTP email alerts
- Discord webhook alerts
- Safe **Simulate ZKAS Block** and **Simulate KAS Block** buttons
- **Send Test Alert** with real per-channel success/failure reporting
- Windows automatic startup
- JSON `/api/stats` first, Prometheus `/metrics` fallback
- v1.0.7 bridge field support plus schema aliases for additive/renamed fields
- No seed phrases, private keys, spending access, node control, or miner control

Phone Push and SMS/Text remain marked **Coming Soon** in the UI.

## Windows clean install
1. Extract the release ZIP.
2. Open PowerShell **as Administrator** in the extracted folder.
3. Run:
   `powershell -ExecutionPolicy Bypass -File .\INSTALL.ps1`
4. Open `http://127.0.0.1:3040`.
5. Login with `admin / 12345678`.
6. Configure Email, Discord, or both.
7. Save Settings and run the test/simulation buttons.

The Windows installer uses the stable folder:
`C:\ProgramData\ZKasDualAlert`

The scheduled task runs as SYSTEM, waits 90 seconds after boot, and starts the web app plus monitor automatically.

## Migrate an existing v0.2.x install
Run:
`powershell -ExecutionPolicy Bypass -File .\INSTALL.ps1 -MigrateFrom "C:\path\to\old\zkas-dual-alert-folder"`

The installer copies `config.json`, `web_config.json`, `state.json`, and `alert.log` into the protected `data` folder. It does not delete the old folder.

## Gmail
Gmail requires a Google App Password. Enter the Gmail address and App Password in the web UI. The password is stored locally in the protected Windows data folder.

## Discord
Paste a real Discord webhook URL (`/api/webhooks/...`), not a server invite URL. The UI never redisplays the saved webhook after it is stored.

## Safety
The web UI binds to `127.0.0.1` by default, so it is local-only. Do not expose port 3040 directly to the public Internet, especially while using the default password.

## Verify
Run:
`powershell -ExecutionPolicy Bypass -File C:\ProgramData\ZKasDualAlert\VERIFY.ps1`

## Update
Extract a newer release and run its `UPDATE.ps1` as Administrator. The `data` folder is preserved.

## Portable mode
For testing without installing a Scheduled Task:
`powershell -ExecutionPolicy Bypass -File .\run-web.ps1`

## Requirements
- Python 3.10+
- Windows 10/11 for the included installer/task scripts
- ZKas/Kaspa bridge dashboard reachable from the machine (default `http://127.0.0.1:3033`)

## Compatibility note
The parser is intentionally tolerant of several field aliases, but no third-party bridge integration can be guaranteed forever if upstream telemetry changes incompatibly.

## Public release scope
The supported public target for v0.2.2 is **Windows 10/11** running a compatible ZKas/Kaspa solo-dual/merge-mining bridge. The included installer and startup scripts are Windows-specific. Linux and macOS are not supported by this release.

The default bridge endpoint is `http://127.0.0.1:3033`. Other miners can use the application when their bridge exposes telemetry compatible with the JSON `/api/stats` or Prometheus `/metrics` formats understood by this version. Compatibility with unrelated mining software is not implied.

## Before publishing or sharing a build
Never package the installed `data` directory. It can contain notification credentials and local runtime state. Public releases should contain `config.example.json`, not a populated `config.json`.

For GitHub release packaging on Windows, run:
`powershell -ExecutionPolicy Bypass -File .\scripts\package-release.ps1 -Version v0.2.2`

The script creates a sanitized ZIP and SHA-256 file under `dist`.

## Suggested GitHub repository description
**Unofficial community-developed Windows monitoring and alert companion for compatible ZKas/Kaspa dual-mining setups. Not affiliated with or endorsed by the ZKas project.**

## Naming / affiliation notice
The repository may use the descriptive name `zkas-dual-alert`, but the product should be presented publicly as:

**ZKas Dual Alert — Unofficial Community Tool**

Do not present this project as an official ZKas application, service, wallet, node, or release.
