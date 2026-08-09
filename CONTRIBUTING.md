# Contributing

**ZKas Dual Alert — Unofficial Community Tool** is independently developed and is not affiliated with or endorsed by the ZKas project.

ZKas Dual Alert v0.2.2 is intentionally a small, Windows-focused monitoring tool.

## Before submitting a change
1. Do not commit personal configuration, logs, state, credentials, wallet information, or worker-specific data.
2. Keep the application read-only. Do not add wallet spending, miner control, or node-control capabilities without an explicit project decision.
3. Run the test suite:
   `python -m unittest discover -s tests -p "test_*.py"`
4. Keep Windows 10/11 installation and startup behavior working.
5. Document any bridge telemetry/schema assumptions.

Bug reports should include the app version, Windows version, bridge version if known, and sanitized error output. Never include passwords, webhook URLs, wallet secrets, or private keys.
